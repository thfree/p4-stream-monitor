# app/scheduler.py

"""
Модуль планировщика задач
Отвечает за фоновое обновление данных о стримах по расписанию
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import joinedload

from .lock_manager import lock_manager
from .models import Server, Stream, StreamHistory, db
from .p4_utils import get_stream_size, get_streams_list
from .utils import human_size

# Используем централизованный логгер
logger = logging.getLogger(__name__)


def update_all_streams():
    """Основная функция для обновления всех стримов на всех серверах"""
    logger.info("Запуск планового обновления всех стримов...")

    try:
        with lock_manager.mass_update_lock():
            _perform_mass_update()

    except RuntimeError as e:
        logger.warning(f"Плановое обновление пропущено: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при плановом обновлении: {e}")


def _get_server_streams(server):
    """Получает список стримов для сервера"""
    try:
        stream_filter = f"Name={server.stream_mask}"
        stream_names = get_streams_list(server.p4port, server.p4user, stream_filter)

        if stream_names is not None:
            logger.info(
                f"Для сервера {server.name} найдено {len(stream_names)} стримов"
            )
            return stream_names
        else:
            logger.error(
                f"Не удалось получить список стримов для сервера {server.name}"
            )
            return []

    except Exception as e:
        logger.error(f"Ошибка получения стримов для сервера {server.name}: {e}")
        return []


def _update_single_stream(server, stream_name, size, file_count, existing_stream=None):
    """Обновляет один стрим в базе данных"""
    try:
        # Ищем существующий стрим или создаем новый
        if existing_stream is None:
            stream = Stream.query.filter_by(
                name=stream_name, server_id=server.id
            ).first()
        else:
            stream = existing_stream

        if not stream:
            stream = Stream(name=stream_name, server_id=server.id)
            db.session.add(stream)
            db.session.flush()
            logger.info(f"Добавлен новый стрим: {stream_name}")
        else:
            logger.debug(f"Обновление существующего стрима: {stream_name}")

        # Сохраняем старые значения для сравнения
        old_size = stream.size_bytes if stream.size_bytes else 0
        old_file_count = stream.file_count if stream.file_count else 0

        # Обновляем данные стрима
        stream.size_bytes = size
        stream.file_count = file_count
        stream.last_updated = datetime.now()

        # Сохраняем в историю, если данные изменились
        if size != old_size or file_count != old_file_count or stream.id is None:
            history_record = StreamHistory(
                stream_id=stream.id,
                size_bytes=size,
                file_count=file_count,
                recorded_at=datetime.now(),
            )
            db.session.add(history_record)
            logger.debug(
                f"Сохранена история для стрима {stream_name}: {human_size(size)}, {file_count} файлов"
            )

        # Коммитим изменения для этого стрима
        db.session.commit()
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления стрима {stream_name}: {e}")
        db.session.rollback()
        return False


def _update_server_streams(server):
    """Обновляет стримы для одного сервера"""
    logger.info(f"Обработка сервера: {server.name}")

    # Получаем список стримов
    try:
        stream_names = _get_server_streams(server)
    except Exception as e:
        logger.error(f"Ошибка получения списка стримов для сервера {server.name}: {e}")
        return 0, 0

    if not stream_names:
        logger.warning(f"Для сервера {server.name} не найдено стримов")
        # Удаляем все стримы этого сервера, так как их больше нет на сервере
        removed_count = _remove_orphaned_streams(server, set())
        logger.info(
            f"Завершено обновление сервера {server.name}: "
            f"+0 новых, ~0 обновленных, -{removed_count} удаленных, 0 ошибок"
        )
        return 0, removed_count

    updated_count = 0
    added_count = 0
    failed_count = 0

    total_streams = len(stream_names)
    logger.info(f"Расчет размеров {total_streams} стримов для сервера {server.name}")

    # Константы батчей
    BATCH_SIZE = 20
    BATCH_DB_SIZE = 50

    # Собираем данные по стримам
    stream_data = {}

    for batch_start in range(0, total_streams, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_streams)
        batch_streams = stream_names[batch_start:batch_end]

        logger.info(
            f"Обработка батча стримов {batch_start + 1}-{batch_end} из {total_streams}"
        )

        for global_index, name in enumerate(batch_streams, start=batch_start + 1):
            progress_info = (
                f"Сервер {server.name}: стрим {global_index} из {total_streams}"
            )
            result = get_stream_size(server.p4port, server.p4user, name, progress_info)

            if result is not None:
                size, file_count = result
                stream_data[name] = (size, file_count)
                logger.debug(
                    f"Рассчитан размер стрима {name}: {human_size(size)}, {file_count} файлов"
                )
            else:
                logger.error(f"Не удалось получить размер для стрима {name}")
                failed_count += 1

    # Обновляем/добавляем стримы в БД
    stream_items = list(stream_data.items())

    for batch_start in range(0, len(stream_items), BATCH_DB_SIZE):
        batch_end = min(batch_start + BATCH_DB_SIZE, len(stream_items))
        batch = stream_items[batch_start:batch_end]

        logger.debug(
            f"Обновление батча стримов в БД {batch_start + 1}-{batch_end} из {len(stream_items)}"
        )

        for name, (size, file_count) in batch:
            # Запрашиваем существующий стрим один раз
            existing_stream = Stream.query.filter_by(
                name=name, server_id=server.id
            ).first()

            try:
                if _update_single_stream(
                    server, name, size, file_count, existing_stream
                ):
                    if existing_stream:
                        updated_count += 1
                    else:
                        added_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Ошибка при обновлении стрима {name}: {e}")
                failed_count += 1

    # Удаляем устаревшие стримы
    removed_count = _remove_orphaned_streams(server, set(stream_names))

    logger.info(
        f"Завершено обновление сервера {server.name}: "
        f"+{added_count} новых, ~{updated_count} обновленных, -{removed_count} удаленных, {failed_count} ошибок"
    )

    return added_count + updated_count, removed_count


def _remove_orphaned_streams(server, existing_stream_names):
    """Удаляет стримы, которых больше нет на сервере. Возвращает число успешно удалённых."""
    if not existing_stream_names:
        # Удаляем все стримы сервера
        streams_to_remove_query = Stream.query.filter(Stream.server_id == server.id)
    else:
        # Удаляем только те, которых нет в списке
        streams_to_remove_query = Stream.query.filter(
            Stream.server_id == server.id, ~Stream.name.in_(existing_stream_names)
        )

    total_to_remove = streams_to_remove_query.count()
    if total_to_remove == 0:
        return 0

    logger.info(
        f"Будет удалено {total_to_remove} устаревших стримов для сервера {server.name}"
    )

    removed_count = 0
    BATCH_DELETE_SIZE = 100

    for offset in range(0, total_to_remove, BATCH_DELETE_SIZE):
        try:
            streams_batch = (
                streams_to_remove_query.offset(offset).limit(BATCH_DELETE_SIZE).all()
            )

            if not streams_batch:
                break

            # Удаляем объекты
            for stream in streams_batch:
                db.session.delete(stream)
                logger.warning(f"Удален стрим: {stream.name}")

            # Коммитим батч
            db.session.commit()
            removed_count += len(streams_batch)

        except Exception as e:
            logger.error(f"Ошибка при удалении батча стримов (offset={offset}): {e}")
            db.session.rollback()
            # Продолжаем, не останавливаясь полностью

    return removed_count


def _perform_mass_update():
    """Внутренняя функция для выполнения массового обновления (без проверки блокировки)"""
    # Получаем все серверы из базы данных с оптимизацией запроса
    servers = Server.query.options(joinedload(Server.streams)).all()
    logger.info(f"Найдено {len(servers)} серверов для обновления")

    total_updated = 0
    total_removed = 0
    total_servers_processed = 0
    failed_servers = 0

    for server in servers:
        total_servers_processed += 1

        try:
            # Каждый сервер обрабатываем в отдельном блоке с обработкой ошибок
            logger.info(
                f"Обработка сервера {server.name} ({total_servers_processed}/{len(servers)})"
            )
            updated, removed = _update_server_streams(server)
            total_updated += updated
            total_removed += removed

        except Exception as e:
            logger.error(f"Критическая ошибка при обработке сервера {server.name}: {e}")
            failed_servers += 1
            continue

    logger.info(
        f"Массовое обновление завершено! "
        f"Серверы: {total_servers_processed - failed_servers}/{len(servers)} успешно, {failed_servers} с ошибками, "
        f"Стримы: ~{total_updated} обновленных, -{total_removed} удаленных"
    )


def init_scheduler(app):
    """Инициализация и запуск планировщика задач"""

    logger.info("Инициализация планировщика задач...")

    # Получаем интервал обновления из конфигурации приложения
    update_interval_hours = app.config.get("SCHEDULER_UPDATE_INTERVAL_HOURS", 24)

    # Если интервал = 0, отключаем автоматическое обновление
    if update_interval_hours == 0:
        logger.info("Автоматическое обновление отключено (интервал = 0 часов)")
        return

    logger.info(f"Интервал автоматического обновления: {update_interval_hours} часов")

    # Создаем планировщик в фоновом режиме
    scheduler = BackgroundScheduler()

    # Добавляем задачу обновления стримов
    scheduler.add_job(
        func=lambda: scheduled_update_all_streams(app),  # Функция для выполнения
        trigger="interval",  # Тип триггера - интервал
        hours=update_interval_hours,  # Интервал выполнения из конфига
        id="update_streams",  # Уникальный идентификатор задачи
        replace_existing=False,  # Не заменять существующую задачу
        max_instances=1,  # Не более одного экземпляра
    )

    # Запускаем планировщик
    scheduler.start()
    logger.info(f"Планировщик запущен с интервалом {update_interval_hours} часов")

    # Регистрируем остановку планировщика при завершении приложения
    import atexit

    def shutdown_scheduler():
        logger.info("Остановка планировщика задач...")
        scheduler.shutdown()
        logger.info("Планировщик остановлен")

    atexit.register(shutdown_scheduler)


def scheduled_update_all_streams(app):
    """
    Функция для планировщика - выполняет обновление в контексте приложения
    с обработкой ошибок и проверкой блокировок
    """
    try:
        with app.app_context():
            # Проверяем, не выполняется ли уже обновление
            if lock_manager.is_mass_update_in_progress():
                logger.info("Пропуск планового обновления - уже выполняется")
                return

            logger.info("Запуск планового обновления по расписанию...")

            try:
                update_all_streams()
                logger.info("Плановое обновление завершено успешно")
            except Exception as e:
                logger.error(f"Ошибка при обновлении стримов: {e}")
                # Не прокидываем исключение дальше, чтобы планировщик продолжал работу

    except Exception as e:
        logger.error(f"Неожиданная ошибка в плановом обновлении: {e}")
