# app/views.py

"""
Модуль с обработчиками маршрутов (views) Flask приложения
Содержит API endpoints и HTML рендеринг
"""

import logging
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from .config_utils import check_tickets_exist, sync_servers_from_config
from .lock_manager import lock_manager
from .models import Server, Stream, StreamHistory, db
from .p4_utils import (
    get_p4_connection,
    get_stream_size,
    get_streams_list,
    verify_p4_authentication,
)
from .scheduler import _perform_mass_update
from .utils import human_size

# Используем централизованный логгер
logger = logging.getLogger(__name__)

# Создание Blueprint для группировки маршрутов
bp = Blueprint("main", __name__)

# Константы для валидации
MAX_PER_PAGE = 1000
MAX_SEARCH_QUERY_LENGTH = 100
MAX_HISTORY_DAYS = 365
MAX_HISTORY_LIMIT = 1000


class ValidationError(Exception):
    """Кастомное исключение для ошибок валидации"""

    pass


def validate_entity_id(entity_id, entity_name="ID"):
    """
    Валидация ID сущностей

    Args:
        entity_id: ID для проверки
        entity_name: Название сущности для сообщения об ошибке

    Returns:
        bool: True если валидно

    Raises:
        ValidationError: Если ID невалиден
    """
    if not isinstance(entity_id, int) or entity_id <= 0:
        raise ValidationError(
            f"Некорректный {entity_name}: должен быть положительным целым числом"
        )
    return True


def validate_pagination_params(page, per_page):
    """
    Валидация параметров пагинации

    Args:
        page: Номер страницы
        per_page: Элементов на странице

    Returns:
        tuple: (page, per_page) - валидированные значения
    """
    if not isinstance(page, int) or page <= 0:
        raise ValidationError("Номер страницы должен быть положительным целым числом")

    if not isinstance(per_page, int) or per_page <= 0:
        raise ValidationError(
            "Количество элементов на странице должно быть положительным целым числом"
        )

    per_page = min(per_page, MAX_PER_PAGE)  # Ограничение максимального значения

    return page, per_page


def sanitize_search_query(query):
    """
    Санитизация поискового запроса

    Args:
        query: Исходный поисковый запрос

    Returns:
        str: Санитизированный запрос
    """
    if not query:
        return ""

    # Обрезаем длину
    query = query.strip()[:MAX_SEARCH_QUERY_LENGTH]

    # Удаляем потенциально опасные символы (базовая защита)
    query = re.sub(r"[;\"\'\-\-]", "", query)

    return query


def validate_search_query(query):
    """
    Валидация поискового запроса

    Args:
        query: Поисковый запрос

    Returns:
        bool: True если валиден

    Raises:
        ValidationError: Если запрос невалиден
    """
    if not query or len(query.strip()) < 2:
        raise ValidationError("Поисковый запрос должен содержать минимум 2 символа")

    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise ValidationError(
            f"Поисковый запрос слишком длинный (максимум {MAX_SEARCH_QUERY_LENGTH} символов)"
        )

    # Проверка на потенциально опасные паттерны
    dangerous_patterns = [
        r"(\b(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER)\b)",
        r"(\b(UNION|SELECT|FROM|WHERE)\b)",
        r"(\b(SCRIPT|JAVASCRIPT|ONLOAD)\b)",
        r"(\.\./)",  # Path traversal
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            raise ValidationError(
                "Поисковый запрос содержит недопустимые символы или слова"
            )

    return True


def validate_history_params(days, limit):
    """
    Валидация параметров истории

    Args:
        days: Количество дней
        limit: Лимит записей

    Returns:
        tuple: (days, limit) - валидированные значения
    """
    if not isinstance(days, int) or days <= 0:
        raise ValidationError("Период в днях должен быть положительным целым числом")

    if not isinstance(limit, int) or limit <= 0:
        raise ValidationError("Лимит записей должен быть положительным целым числом")

    days = min(days, MAX_HISTORY_DAYS)
    limit = min(limit, MAX_HISTORY_LIMIT)

    return days, limit


def validate_server_data(server_data):
    """
    Валидация данных сервера

    Args:
        server_data: Данные сервера

    Raises:
        ValidationError: Если данные невалидны
    """
    if not server_data:
        raise ValidationError("Данные сервера не предоставлены")

    required_fields = ["name", "p4port", "p4user", "stream_mask"]
    for field in required_fields:
        if field not in server_data or not server_data[field]:
            raise ValidationError(f"Обязательное поле '{field}' отсутствует или пустое")

    # Валидация P4 порта
    p4port_pattern = r"^[a-zA-Z0-9\.\-_:]+:\d+$"
    if not re.match(p4port_pattern, server_data["p4port"]):
        raise ValidationError("Некорректный формат P4 порта")

    # Валидация имени пользователя
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", server_data["p4user"]):
        raise ValidationError("Имя пользователя содержит недопустимые символы")

    # Валидация маски стримов
    if len(server_data["stream_mask"]) > 200:
        raise ValidationError("Маска стримов слишком длинная")


import threading
import time


def get_stream_size_with_timeout(
    p4port: str,
    p4user: str,
    stream: str,
    progress_info: str = "",
    timeout_minutes: int = 30,
) -> Optional[tuple]:
    """
    Версия с таймаутом для предотвращения зависаний
    """
    result = [None]  # Используем список для передачи результата из потока

    def worker():
        try:
            result[0] = get_stream_size(p4port, p4user, stream, progress_info)
        except Exception as e:
            logger.error(f"Ошибка в worker потоке для {stream}: {e}")
            result[0] = None

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()

    # Ждем завершения с таймаутом
    thread.join(timeout_minutes * 60)

    if thread.is_alive():
        logger.error(
            f"Расчет размера стрима {stream} превысил таймаут {timeout_minutes} минут"
        )
        return None

    return result[0]


def get_app_version():
    """
    Основная функция получения версии
    Формат: 1.0.0.5338500
    """
    try:
        with open("VERSION", "r") as f:
            base_version = f.read().strip()
    except:
        base_version = "1.0.0"

    try:
        # Получаем короткий хеш (7 символов)
        git_hash = (
            subprocess.check_output(
                ["git", "rev-parse", "--short=7", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )

        return f"{base_version}.{git_hash}"

    except:
        return base_version


# Глобальные обработчики ошибок
@bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Обработчик ошибок валидации"""
    logger.warning(f"Ошибка валидации: {str(error)}")
    return (
        jsonify({"status": "error", "message": str(error), "type": "validation_error"}),
        400,
    )


@bp.errorhandler(400)
def bad_request(error):
    """Обработчик ошибок 400"""
    return (
        jsonify(
            {"status": "error", "message": "Некорректный запрос", "details": str(error)}
        ),
        400,
    )


@bp.errorhandler(422)
def unprocessable_entity(error):
    """Обработчик ошибок 422"""
    return (
        jsonify(
            {"status": "error", "message": "Некорректные данные", "details": str(error)}
        ),
        422,
    )


@bp.errorhandler(404)
def not_found(error):
    """Обработчик ошибок 404"""
    return jsonify({"status": "error", "message": "Ресурс не найден"}), 404


@bp.errorhandler(500)
def internal_server_error(error):
    """Обработчик ошибок 500"""
    logger.error(f"Внутренняя ошибка сервера: {error}")
    return jsonify({"status": "error", "message": "Внутренняя ошибка сервера"}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    """Обработчик ошибок целостности данных (дублирование, внешние ключи)"""
    logger.error(f"Ошибка целостности данных: {error}")
    db.session.rollback()

    # Анализируем тип ошибки
    error_msg = "Ошибка целостности данных"
    if "UNIQUE constraint failed" in str(error):
        error_msg = "Нарушение уникальности данных"
    elif "FOREIGN KEY constraint failed" in str(error):
        error_msg = "Нарушение ссылочной целостности"

    return (
        jsonify({"status": "error", "message": error_msg, "type": "integrity_error"}),
        400,
    )


@bp.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    """Обработчик общих ошибок базы данных"""
    logger.error(f"Ошибка базы данных: {error}")
    db.session.rollback()
    return (
        jsonify(
            {
                "status": "error",
                "message": "Ошибка базы данных",
                "type": "database_error",
            }
        ),
        500,
    )


@bp.errorhandler(OperationalError)
def handle_operational_error(error):
    """Обработчик операционных ошибок БД (соединение, таймауты)"""
    logger.error(f"Операционная ошибка БД: {error}")
    db.session.rollback()

    error_msg = "Временная ошибка базы данных"
    if "locked" in str(error).lower():
        error_msg = "База данных временно заблокирована"
    elif "timeout" in str(error).lower():
        error_msg = "Таймаут операции с базой данных"

    return (
        jsonify(
            {
                "status": "error",
                "message": error_msg,
                "type": "database_operational_error",
            }
        ),
        503,
    )


@bp.route("/")
def index():
    """Главная страница - отображает список серверов и их стримов"""
    # Используем joinedload для оптимизации запроса и избежания N+1
    servers = Server.query.options(joinedload(Server.streams)).all()
    logger.info(f"Отображение главной страницы с {len(servers)} серверами")
    return render_template(
        "index.html", servers=servers, now=datetime.now(), version=get_app_version()
    )


# POST:Массовое обновление всех стримов
@bp.route("/api/update/all", methods=["POST"])
def update_all():
    """
    API endpoint для принудительного обновления всех стримов на всех серверах

    Returns:
        JSON: {status: "success"/"error", message: "сообщение"}

    Status Codes:
        200: Успешный запуск
        423: Массовое обновление уже выполняется
        500: Внутренняя ошибка сервера
    """
    logger.info("Ручной запуск обновления всех стримов через API")

    try:
        # Проверяем возможность выполнения массового обновления
        if not lock_manager.can_start_mass_update():
            logger.warning(
                "Попытка запуска массового обновления при уже выполняющейся операции"
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Массовое обновление уже выполняется или выполняется обновление сервера/конфига",
                    }
                ),
                423,
            )  # 423 - Locked

        # Запускаем обновление с блокировкой
        with lock_manager.mass_update_lock():
            _perform_mass_update()

        logger.info("Ручное обновление всех стримов успешно завершено")
        return jsonify(
            {"status": "success", "message": "Обновление всех стримов запущено"}
        )

    except RuntimeError as e:
        logger.error(f"Ошибка блокировки при массовом обновлении: {e}")
        return jsonify({"status": "error", "message": str(e)}), 423
    except Exception as e:
        logger.error(f"Ошибка при ручном обновлении всех стримов: {e}")
        return jsonify({"status": "error", "message": f"Ошибка обновления: {e}"}), 500


# POST: Обновление конкретного стрима
@bp.route("/api/update/stream/<int:stream_id>", methods=["POST"])
def update_stream(stream_id):
    """
    API endpoint для обновления размера конкретного стрима

    Args:
        stream_id (int): ID стрима для обновления

    Returns:
        JSON: {success: true/false, size_bytes: int, human: string, timestamp: string, message: string}

    Status Codes:
        200: Успешное обновление
        400: Некорректный ID стрима
        404: Стрим не найден
        423: Операция заблокирована
        500: Ошибка обновления
    """
    try:
        # Валидация ID стрима
        validate_entity_id(stream_id, "ID стрима")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    # Ищем стрим по ID
    stream = Stream.query.get(stream_id)
    if not stream:
        logger.warning(f"Стрим с ID {stream_id} не найден")
        return jsonify({"error": "Стрим не найден"}), 404

    # Получаем связанный сервер
    server = stream.server
    logger.info(f"Ручное обновление стрима: {stream.name} на сервере: {server.name}")

    try:
        with lock_manager.stream_update_lock(server.id):
            # Запрашиваем актуальный размер стрима через Perforce
            logger.debug(f"Запрос размера для стрима: {stream.name}")

            # Используем версию с таймаутом
            result = get_stream_size_with_timeout(
                server.p4port,
                server.p4user,
                stream.name,
                progress_info=f"Расчет размера {stream.name}",
                timeout_minutes=45,  # 45 минут для гигантских стримов
            )

            if result is not None:
                size, file_count = result
                logger.debug(
                    f"Полученный размер для {stream.name}: {size}, файлов: {file_count}"
                )

                # Сохраняем старые значения для сравнения
                old_size = stream.size_bytes if stream.size_bytes else 0
                old_file_count = stream.file_count if stream.file_count else 0

                logger.debug(f"Старый размер: {old_size}, новый размер: {size}")
                logger.debug(
                    f"Старое кол-во файлов: {old_file_count}, новое кол-во: {file_count}"
                )

                # Обновляем данные в БД
                stream.size_bytes = size
                stream.file_count = file_count
                stream.last_updated = datetime.now()

                # Сохраняем в историю, если данные изменились
                if (
                    size != old_size
                    or file_count != old_file_count
                    or not stream.last_updated
                ):
                    history_record = StreamHistory(
                        stream_id=stream.id,
                        size_bytes=size,
                        file_count=file_count,
                        recorded_at=datetime.now(),
                    )
                    db.session.add(history_record)
                    logger.debug(
                        f"Сохранена история для стрима {stream.name}: {size} байт, {file_count} файлов"
                    )

                db.session.commit()

                # Обновляем объект из БД
                db.session.refresh(stream)

                # Форматируем время для ответа
                timestamp_iso = (
                    stream.last_updated.isoformat()
                    if stream.last_updated
                    else datetime.now().isoformat()
                )
                size_human = human_size(size)

                logger.info(
                    f"Стрим {stream.name} успешно обновлен: {size_human}, {file_count} файлов"
                )

                return jsonify(
                    {
                        "size_bytes": size,
                        "file_count": file_count,
                        "human": size_human,
                        "timestamp": timestamp_iso,
                        "success": True,
                        "message": f"Стрим обновлен: {size_human}, {file_count} файлов",
                    }
                )
            else:
                logger.error(f"Не удалось получить размер для стрима {stream.name}")

    except RuntimeError as e:
        logger.error(f"Ошибка блокировки при обновлении стрима {stream_id}: {e}")
        return jsonify({"error": str(e), "success": False}), 423
    except Exception as e:
        logger.error(f"Ошибка при обновлении стрима {stream.name}: {e}")
        db.session.rollback()

    return (
        jsonify({"error": "Не удалось получить размер стрима", "success": False}),
        500,
    )


# POST: Обновление всех стримов на сервере (с расчётом размеров)
@bp.route("/api/update/server/<int:server_id>", methods=["POST"])
def update_server(server_id):
    """
    API endpoint для обновления всех стримов на конкретном сервере

    Args:
        server_id (int): ID сервера для обновления

    Returns:
        JSON: {success: true/false, updated: int, added: int, removed: int, message: string}

    Status Codes:
        200: Успешное обновление
        400: Некорректный ID сервера
        404: Сервер не найден
        423: Операция заблокирована
        500: Ошибка обновления
    """
    try:
        # Валидация ID сервера
        validate_entity_id(server_id, "ID сервера")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    server = Server.query.get(server_id)
    if not server:
        logger.warning(f"Сервер с ID {server_id} не найден")
        return jsonify({"error": "Сервер не найден"}), 404

    logger.info(f"Ручное обновление всех стримов на сервере: {server.name}")

    try:
        # Проверяем возможность обновления сервера
        if not lock_manager.can_start_server_update(server_id):
            logger.warning(
                f"Попытка запуска обновления сервера {server_id} при заблокированной операции"
            )
            return (
                jsonify(
                    {
                        "error": "Обновление сервера невозможно: массовое обновление или обновление этого сервера уже выполняется",
                        "success": False,
                    }
                ),
                423,
            )

        # Получаем актуальный список стримов с сервера
        stream_filter = f"Name={server.stream_mask}"
        stream_names = get_streams_list(server.p4port, server.p4user, stream_filter)

        if stream_names is None:
            logger.error(
                f"Не удалось получить список стримов для сервера {server.name}"
            )
            return (
                jsonify({"error": "Ошибка получения списка стримов", "success": False}),
                500,
            )

        logger.info(f"Найдено {len(stream_names)} стримов для сервера {server.name}")

    except Exception as e:
        logger.error(f"Ошибка получения стримов для сервера {server.name}: {e}")
        return (
            jsonify(
                {
                    "error": f"Ошибка получения списка стримов: {e}",
                    "success": False,
                }
            ),
            500,
        )

    # Счетчики для статистики
    updated_count = 0  # Количество обновленных стримов
    added_count = 0  # Количество добавленных стримов

    # Выполняем обновление с блокировкой сервера
    try:
        with lock_manager.server_update_lock(server_id):
            # Обновляем или добавляем стримы
            total_streams = len(stream_names)
            logger.info(f"Обновление {total_streams} стримов для сервера {server.name}")

            # Используем batch processing для избежания переполнения памяти
            BATCH_SIZE = 50
            for batch_start in range(0, total_streams, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_streams)
                batch_streams = stream_names[batch_start:batch_end]

                logger.debug(
                    f"Обработка батча стримов {batch_start}-{batch_end} из {total_streams}"
                )

                for index, stream_name in enumerate(batch_streams, batch_start + 1):
                    stream = Stream.query.filter_by(
                        name=stream_name, server_id=server_id
                    ).first()

                    if not stream:
                        stream = Stream(name=stream_name, server_id=server_id)
                        db.session.add(stream)
                        # Сразу коммитим, чтобы получить ID
                        db.session.flush()
                        added_count += 1
                        logger.info(f"Добавлен новый стрим: {stream_name}")

                    # Формируем информацию о прогрессе
                    progress_info = (
                        f"Сервер {server.name}: стрим {index} из {total_streams}"
                    )

                    # Обновляем размер (новых и существующих)
                    result = get_stream_size(
                        server.p4port, server.p4user, stream_name, progress_info
                    )
                    if result is not None:
                        size, file_count = result
                        old_size = stream.size_bytes if stream.size_bytes else 0
                        old_file_count = stream.file_count if stream.file_count else 0

                        stream.size_bytes = size
                        stream.file_count = file_count
                        stream.last_updated = datetime.now()
                        updated_count += 1

                        if (
                            size != old_size
                            or file_count != old_file_count
                            or not stream.last_updated
                        ):
                            if stream.id is not None:
                                db.session.flush()
                                history_record = StreamHistory(
                                    stream_id=stream.id,
                                    size_bytes=size,
                                    file_count=file_count,
                                    recorded_at=datetime.now(),
                                )
                                db.session.add(history_record)
                                logger.debug(
                                    f"Сохранена история для стрима {stream_name}: {size} байт"
                                )
                            else:
                                logger.error(
                                    f"Не удалось сохранить историю для стрима {stream_name}: ID отсутствует"
                                )

                # Коммитим батч для освобождения памяти
                db.session.commit()
                logger.debug(f"Завершен коммит батча {batch_start}-{batch_end}")

            # Удаляем стримы, которых больше нет на сервере
            existing_stream_names = set(stream_names)

            # Удаляем батчами для избежания переполнения памяти
            streams_to_remove_query = Stream.query.filter(
                Stream.server_id == server_id, ~Stream.name.in_(existing_stream_names)
            )

            total_to_remove = streams_to_remove_query.count()
            removed_count = 0

            # Удаляем порциями
            BATCH_DELETE_SIZE = 100
            for offset in range(0, total_to_remove, BATCH_DELETE_SIZE):
                streams_batch = (
                    streams_to_remove_query.offset(offset)
                    .limit(BATCH_DELETE_SIZE)
                    .all()
                )

                for stream in streams_batch:
                    db.session.delete(stream)
                    removed_count += 1
                    logger.warning(f"Удален стрим: {stream.name}")

                db.session.commit()
                logger.debug(
                    f"Удалено {len(streams_batch)} стримов (батч {offset//BATCH_DELETE_SIZE + 1})"
                )

    except RuntimeError as e:
        logger.error(f"Ошибка блокировки при обновлении сервера {server_id}: {e}")
        return jsonify({"error": str(e), "success": False}), 423
    except Exception as e:
        logger.error(f"Ошибка при обновлении сервера {server.name}: {e}")
        db.session.rollback()
        return jsonify({"error": f"Ошибка обновления: {e}", "success": False}), 500

    logger.info(
        f"Завершено обновление сервера {server.name}: +{added_count} ~{updated_count} -{removed_count}"
    )

    return jsonify(
        {
            "updated": updated_count,
            "added": added_count,
            "removed": removed_count,
            "success": True,
            "message": f"Обновлено: +{added_count} ~{updated_count} -{removed_count}",
        }
    )


# GET: Получение списка стримов для сервера (без расчёта размеров)
@bp.route("/api/server/<int:server_id>/streams", methods=["GET"])
def get_server_streams(server_id):
    """
    API endpoint для получения списка стримов сервера без расчета размеров

    Args:
        server_id (int): ID сервера

    Returns:
        JSON: {success: true/false, server: string, streams: list, count: int}

    Status Codes:
        200: Успешное получение
        400: Некорректный ID сервера
        404: Сервер не найден
        500: Ошибка получения данных
    """
    try:
        # Валидация ID сервера
        validate_entity_id(server_id, "ID сервера")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    server = Server.query.get(server_id)
    if not server:
        logger.warning(f"Сервер с ID {server_id} не найден")
        return jsonify({"error": "Сервер не найден"}), 404

    try:
        # Получаем список стримов с сервера
        stream_filter = f"Name={server.stream_mask}"
        stream_names = get_streams_list(server.p4port, server.p4user, stream_filter)

        if stream_names is None:
            logger.error(
                f"Не удалось получить список стримов для сервера {server.name}"
            )
            return (
                jsonify({"error": "Ошибка получения списка стримов", "success": False}),
                500,
            )

        logger.info(f"Получено {len(stream_names)} стримов для сервера {server.name}")

        return jsonify(
            {
                "server": server.name,
                "streams": stream_names,
                "count": len(stream_names),
                "success": True,
            }
        )

    except Exception as e:
        logger.error(f"Ошибка получения стримов для сервера {server.name}: {e}")
        return (
            jsonify(
                {
                    "error": f"Ошибка получения списка стримов: {e}",
                    "success": False,
                }
            ),
            500,
        )


# POST: Синхронизировать список стримов для сервера (только структура)
@bp.route("/api/update/server/<int:server_id>/sync-streams", methods=["POST"])
def sync_server_streams(server_id):
    """
    API endpoint для синхронизации списка стримов без расчёта размеров

    Args:
        server_id (int): ID сервера для синхронизации

    Returns:
        JSON: {success: true/false, added: int, removed: int, total: int, message: string}

    Status Codes:
        200: Успешная синхронизация
        400: Некорректный ID сервера
        404: Сервер не найден
        423: Операция заблокирована
        500: Ошибка синхронизации
    """
    try:
        # Валидация ID сервера
        validate_entity_id(server_id, "ID сервера")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    server = Server.query.get(server_id)
    if not server:
        logger.warning(f"Сервер с ID {server_id} не найден")
        return jsonify({"error": "Сервер не найден", "success": False}), 404

    logger.info(f"Синхронизация стримов для сервера: {server.name}")

    try:
        # Проверяем возможность синхронизации
        if not lock_manager.can_start_server_update(server_id):
            logger.warning(
                f"Попытка синхронизации сервера {server_id} при заблокированной операции"
            )
            return (
                jsonify(
                    {
                        "error": "Синхронизация сервера невозможна: массовое обновление или обновление этого сервера уже выполняется",
                        "success": False,
                    }
                ),
                423,
            )

        # Выполняем синхронизацию с блокировкой
        with lock_manager.server_sync_lock(server_id):
            # Получаем актуальный список стримов с сервера
            stream_filter = f"Name={server.stream_mask}"
            stream_names = get_streams_list(server.p4port, server.p4user, stream_filter)

            if stream_names is None:
                logger.error(
                    f"Не удалось получить список стримов для сервера {server.name}"
                )
                return (
                    jsonify(
                        {"error": "Ошибка получения списка стримов", "success": False}
                    ),
                    500,
                )

            added_count = 0  # Счетчик добавленных стримов
            removed_count = 0  # Счетчик удаленных стримов

            # Получаем текущие стримы из базы с пагинацией для избежания переполнения памяти
            existing_stream_names = set()
            BATCH_SIZE = 500
            offset = 0

            while True:
                streams_batch = (
                    Stream.query.filter_by(server_id=server_id)
                    .offset(offset)
                    .limit(BATCH_SIZE)
                    .all()
                )
                if not streams_batch:
                    break

                for stream in streams_batch:
                    existing_stream_names.add(stream.name)
                offset += BATCH_SIZE

            # Добавляем новые стримы батчами
            BATCH_ADD_SIZE = 100
            for i in range(0, len(stream_names), BATCH_ADD_SIZE):
                batch = stream_names[i : i + BATCH_ADD_SIZE]

                for stream_name in batch:
                    if stream_name not in existing_stream_names:
                        stream = Stream(
                            name=stream_name, server_id=server_id, size_bytes=0
                        )
                        db.session.add(stream)
                        added_count += 1
                        logger.info(f"Добавлен новый стрим: {stream_name}")

                # Коммитим батч
                db.session.commit()
                logger.debug(
                    f"Завершен коммит батча добавления стримов {i}-{i+len(batch)}"
                )

            # Удаляем стримы, которых больше нет на сервере
            existing_stream_names_set = set(stream_names)

            # Удаляем батчами
            streams_to_remove_query = Stream.query.filter(
                Stream.server_id == server_id,
                ~Stream.name.in_(existing_stream_names_set),
            )

            total_to_remove = streams_to_remove_query.count()

            BATCH_DELETE_SIZE = 100
            for offset in range(0, total_to_remove, BATCH_DELETE_SIZE):
                streams_batch = (
                    streams_to_remove_query.offset(offset)
                    .limit(BATCH_DELETE_SIZE)
                    .all()
                )

                for stream in streams_batch:
                    db.session.delete(stream)
                    removed_count += 1
                    logger.warning(f"Удален стрим: {stream.name}")

                db.session.commit()
                logger.debug(
                    f"Удалено {len(streams_batch)} стримов (батч {offset//BATCH_DELETE_SIZE + 1})"
                )

        logger.info(
            f"Синхронизация стримов завершена для сервера {server.name}: +{added_count} -{removed_count}"
        )

        return jsonify(
            {
                "added": added_count,
                "removed": removed_count,
                "total": len(stream_names),
                "success": True,
                "message": f"Синхронизировано: +{added_count} -{removed_count}",
            }
        )

    except RuntimeError as e:
        logger.error(f"Ошибка блокировки при синхронизации сервера {server_id}: {e}")
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 423
    except Exception as e:
        logger.error(f"Неожиданная ошибка при синхронизации сервера {server_id}: {e}")
        db.session.rollback()
        return jsonify({"error": f"Ошибка синхронизации: {e}", "success": False}), 500


# POST: Синхронизация серверов с конфигом
@bp.route("/api/admin/sync-servers", methods=["POST"])
def sync_servers():
    """
    API endpoint для принудительной синхронизации серверов с конфигурационным файлом

    Returns:
        JSON: {status: "success"/"error", message: "результат операции"}

    Status Codes:
        200: Успешная синхронизация
        423: Операция заблокирована
        500: Ошибка синхронизации
    """
    try:
        logger.info("Ручная синхронизация серверов через API")

        # Проверяем возможность синхронизации конфига
        if not lock_manager.can_start_config_sync():
            logger.warning("Попытка синхронизации конфига при заблокированной операции")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Синхронизация конфига невозможна: массовое обновление или обновление сервера уже выполняется",
                    }
                ),
                423,
            )

        # Выполняем синхронизацию с блокировкой
        with lock_manager.config_sync_lock():
            result = sync_servers_from_config()

        logger.info(f"Синхронизация серверов завершена: {result}")
        return jsonify({"status": "success", "message": result})

    except RuntimeError as e:
        logger.error(f"Ошибка блокировки при синхронизации серверов: {e}")
        return jsonify({"status": "error", "message": str(e)}), 423
    except Exception as e:
        logger.error(f"Ошибка синхронизации серверов: {e}")
        return jsonify({"status": "error", "message": f"Ошибка: {e}"}), 500


# GET: Получение статуса блокировок
@bp.route("/api/status/locks", methods=["GET"])
def get_lock_status():
    """
    API endpoint для получения статуса блокировок системы

    Returns:
        JSON: {mass_update_in_progress: bool, server_updates_in_progress: list, can_start_mass_update: bool, config_sync_in_progress: bool}

    Status Codes:
        200: Успешное получение статуса
    """
    status = {
        "mass_update_in_progress": lock_manager.is_mass_update_in_progress(),
        "server_updates_in_progress": list(lock_manager._server_updates_in_progress),
        "config_sync_in_progress": lock_manager.is_config_sync_in_progress(),
        "can_start_mass_update": lock_manager.can_start_mass_update(),
    }
    return jsonify(status)


# GET: Получение списка всех серверов
@bp.route("/api/servers", methods=["GET"])
def get_servers():
    """
    API endpoint для получения списка всех серверов

    Returns:
        JSON: {success: true/false, servers: list, count: int}

    Status Codes:
        200: Успешное получение
        500: Ошибка получения данных
    """
    try:
        servers = Server.query.options(joinedload(Server.streams)).all()
        server_list = []

        for server in servers:
            server_data = {
                "id": server.id,
                "name": server.name,
                "p4port": server.p4port,
                "p4user": server.p4user,
                "stream_mask": server.stream_mask,
                "created_at": (
                    server.created_at.isoformat() if server.created_at else None
                ),
                "streams_count": len(server.streams),
            }
            server_list.append(server_data)

        logger.info(f"Возвращено {len(server_list)} серверов")
        return jsonify(
            {"servers": server_list, "count": len(server_list), "success": True}
        )

    except Exception as e:
        logger.error(f"Ошибка при получении списка серверов: {e}")
        return (
            jsonify({"error": f"Ошибка получения серверов: {e}", "success": False}),
            500,
        )


# GET: Получение информации о сервере
@bp.route("/api/server/<int:server_id>", methods=["GET"])
def get_server(server_id):
    """
    API endpoint для получения информации о конкретном сервере

    Args:
        server_id (int): ID сервера

    Returns:
        JSON: {success: true/false, server: object}

    Status Codes:
        200: Успешное получение
        400: Некорректный ID сервера
        404: Сервер не найден
        500: Ошибка получения данных
    """
    try:
        # Валидация ID сервера
        validate_entity_id(server_id, "ID сервера")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    try:
        server = Server.query.options(joinedload(Server.streams)).get(server_id)
        if not server:
            logger.warning(f"Сервер с ID {server_id} не найден")
            return jsonify({"error": "Сервер не найден", "success": False}), 404

        server_data = {
            "id": server.id,
            "name": server.name,
            "p4port": server.p4port,
            "p4user": server.p4user,
            "stream_mask": server.stream_mask,
            "created_at": server.created_at.isoformat() if server.created_at else None,
            "streams_count": len(server.streams),
        }

        logger.info(f"Возвращена информация о сервере: {server.name}")
        return jsonify({"server": server_data, "success": True})

    except Exception as e:
        logger.error(f"Ошибка при получении информации о сервере {server_id}: {e}")
        return (
            jsonify({"error": f"Ошибка получения сервера: {e}", "success": False}),
            500,
        )


# GET: Получение списка стримов с пагинацией
@bp.route("/api/streams", methods=["GET"])
def get_streams():
    """
    API endpoint для получения списка стримов с пагинацией и фильтрацией

    Query Parameters:
        page (int): номер страницы (по умолчанию: 1)
        per_page (int): количество элементов на странице (по умолчанию: 50)
        server_id (int): фильтр по ID сервера

    Returns:
        JSON: {success: true/false, streams: list, pagination: object}

    Status Codes:
        200: Успешное получение
        400: Некорректные параметры пагинации
        500: Ошибка получения данных
    """
    try:
        # Параметры пагинации
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        server_id = request.args.get("server_id", type=int)

        # Валидация параметров пагинации
        page, per_page = validate_pagination_params(page, per_page)

        # Валидация server_id если предоставлен
        if server_id is not None:
            validate_entity_id(server_id, "ID сервера")

        # Базовый запрос
        query = Stream.query.options(joinedload(Stream.server))

        # Фильтр по серверу
        if server_id:
            query = query.filter_by(server_id=server_id)

        # Пагинация
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        streams_list = []
        for stream in pagination.items:
            stream_data = {
                "id": stream.id,
                "name": stream.name,
                "size_bytes": stream.size_bytes,
                "file_count": stream.file_count,
                "size_human": human_size(stream.size_bytes),
                "last_updated": (
                    stream.last_updated.isoformat() if stream.last_updated else None
                ),
                "server_id": stream.server_id,
                "server_name": stream.server.name,
            }
            streams_list.append(stream_data)

        logger.info(f"Возвращено {len(streams_list)} стримов (страница {page})")
        return jsonify(
            {
                "streams": streams_list,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_prev": pagination.has_prev,
                    "has_next": pagination.has_next,
                },
                "success": True,
            }
        )

    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        logger.error(f"Ошибка при получении списка стримов: {e}")
        return (
            jsonify({"error": f"Ошибка получения стримов: {e}", "success": False}),
            500,
        )


# GET: Получить информацию о конкретном стриме
@bp.route("/api/stream/<int:stream_id>", methods=["GET"])
def get_stream(stream_id):
    """
    API endpoint для получения информации о конкретном стриме

    Args:
        stream_id (int): ID стрима

    Returns:
        JSON: {success: true/false, stream: object}

    Status Codes:
        200: Успешное получение
        400: Некорректный ID стрима
        404: Стрим не найден
        500: Ошибка получения данных
    """
    try:
        # Валидация ID стрима
        validate_entity_id(stream_id, "ID стрима")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    try:
        stream = Stream.query.options(joinedload(Stream.server)).get(stream_id)
        if not stream:
            logger.warning(f"Стрим с ID {stream_id} не найден")
            return jsonify({"error": "Стрим не найден", "success": False}), 404

        stream_data = {
            "id": stream.id,
            "name": stream.name,
            "size_bytes": stream.size_bytes,
            "file_count": stream.file_count,
            "size_human": human_size(stream.size_bytes),
            "last_updated": (
                stream.last_updated.isoformat() if stream.last_updated else None
            ),
            "server_id": stream.server_id,
            "server_name": stream.server.name,
            "server_p4port": stream.server.p4port,
        }

        logger.info(f"Возвращена информация о стриме: {stream.name}")
        return jsonify({"stream": stream_data, "success": True})

    except Exception as e:
        logger.error(f"Ошибка при получении информации о стриме {stream_id}: {e}")
        return (
            jsonify({"error": f"Ошибка получения стрима: {e}", "success": False}),
            500,
        )


# GET: Получение статистики
@bp.route("/api/stats", methods=["GET"])
def get_stats():
    """
    API endpoint для получения общей статистики по серверам и стримам

    Returns:
        JSON: {success: true/false, stats: object}

    Status Codes:
        200: Успешное получение
        500: Ошибка получения данных
    """
    try:
        # Базовая статистика
        total_servers = Server.query.count()
        total_streams = Stream.query.count()

        # Находим время последнего обновления любого стрима
        last_updated_stream = Stream.query.order_by(Stream.last_updated.desc()).first()
        last_updated_time = (
            last_updated_stream.last_updated if last_updated_stream else None
        )

        # Статистика по серверам
        servers_stats = []
        servers = Server.query.all()

        for server in servers:
            server_streams_count = Stream.query.filter_by(server_id=server.id).count()

            # Время последнего обновления для этого сервера
            server_last_stream = (
                Stream.query.filter_by(server_id=server.id)
                .order_by(Stream.last_updated.desc())
                .first()
            )
            server_last_updated = (
                server_last_stream.last_updated if server_last_stream else None
            )

            servers_stats.append(
                {
                    "server_id": server.id,
                    "server_name": server.name,
                    "streams_count": server_streams_count,
                    "last_updated": (
                        server_last_updated.isoformat() if server_last_updated else None
                    ),
                }
            )

        stats = {
            "total_servers": total_servers,
            "total_streams": total_streams,
            "last_global_update": (
                last_updated_time.isoformat() if last_updated_time else None
            ),
            "servers": servers_stats,
            "note": "Суммарные размеры не отображаются, так как стримы виртуальные и данные пересекаются",
        }

        logger.info("Возвращена статистика приложения")
        return jsonify({"stats": stats, "success": True})

    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return (
            jsonify({"error": f"Ошибка получения статистики: {e}", "success": False}),
            500,
        )


# GET: Получение информации о приложении и версии
@bp.route("/api/info", methods=["GET"])
def get_app_info():
    """API endpoint для получения информации о приложении и версии

    Returns:
        JSON: {success: true/false, app_info: object}

    Status Codes:
        200: Успешное получение
        500: Ошибка получения данных
    """
    try:
        from flask import current_app

        info = {
            "version": get_app_version(),
            "environment": "development" if current_app.debug else "production",
            "debug_mode": current_app.debug,
            "database_uri": current_app.config.get("SQLALCHEMY_DATABASE_URI", "hidden"),
            "scheduler_interval_hours": current_app.config.get(
                "SCHEDULER_UPDATE_INTERVAL_HOURS", 6
            ),
            "start_time": datetime.now().isoformat(),
        }

        logger.info("Возвращена информация о приложении")
        return jsonify({"app_info": info, "success": True})

    except Exception as e:
        logger.error(f"Ошибка при получении информации о приложении: {e}")
        return (
            jsonify({"error": f"Ошибка получения информации: {e}", "success": False}),
            500,
        )


# GET: Поиск стримов
@bp.route("/api/streams/search", methods=["GET"])
def search_streams():
    """
    API endpoint для поиска стримов по имени

    Query Parameters:
        q (string): поисковый запрос (минимум 2 символа)

    Returns:
        JSON: {success: true/false, streams: list, count: int, query: string}

    Status Codes:
        200: Успешный поиск
        400: Некорректный поисковый запрос
        500: Ошибка поиска
    """
    try:
        query = request.args.get("q", "")

        # Санитизация и валидация запроса
        query = sanitize_search_query(query)
        validate_search_query(query)

        # Поиск стримов, содержащих запрос в имени
        streams = (
            Stream.query.options(joinedload(Stream.server))
            .filter(Stream.name.ilike(f"%{query}%"))
            .limit(50)
            .all()
        )

        streams_list = []
        for stream in streams:
            stream_data = {
                "id": stream.id,
                "name": stream.name,
                "size_bytes": stream.size_bytes,
                "file_count": stream.file_count,
                "size_human": human_size(stream.size_bytes),
                "last_updated": (
                    stream.last_updated.isoformat() if stream.last_updated else None
                ),
                "server_id": stream.server_id,
                "server_name": stream.server.name,
            }
            streams_list.append(stream_data)

        logger.info(f"Поиск стримов: найдено {len(streams_list)} по запросу '{query}'")
        return jsonify(
            {
                "streams": streams_list,
                "count": len(streams_list),
                "query": query,
                "success": True,
            }
        )

    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        logger.error(f"Ошибка при поиске стримов: {e}")
        return jsonify({"error": f"Ошибка поиска: {e}", "success": False}), 500


# GET: Получение истории стрима
@bp.route("/api/stream/<int:stream_id>/history", methods=["GET"])
def get_stream_history(stream_id):
    """
    API endpoint для получения истории изменений размера стрима

    Args:
        stream_id (int): ID стрима

    Query Parameters:
        days (int): период в днях (по умолчанию: 30)
        limit (int): максимальное количество записей (по умолчанию: 100)

    Returns:
        JSON: {success: true/false, stream_id: int, stream_name: string, history: list}

    Status Codes:
        200: Успешное получение
        400: Некорректные параметры
        404: Стрим не найден
        500: Ошибка получения данных
    """
    try:
        # Валидация ID стрима
        validate_entity_id(stream_id, "ID стрима")
    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400

    stream = Stream.query.get(stream_id)
    if not stream:
        logger.warning(f"Стрим с ID {stream_id} не найден")
        return jsonify({"error": "Стрим не найден", "success": False}), 404

    try:
        # Параметры: период, лимит записей
        days = request.args.get("days", 30, type=int)
        limit = request.args.get("limit", 100, type=int)

        # Валидация параметров истории
        days, limit = validate_history_params(days, limit)

        # Рассчитываем дату начала периода
        since_date = datetime.now() - timedelta(days=days)

        # Получаем историю из базы данных
        history_query = (
            StreamHistory.query.filter(
                StreamHistory.stream_id == stream_id,
                StreamHistory.recorded_at >= since_date,
            )
            .order_by(StreamHistory.recorded_at.desc())
            .limit(limit)
        )

        history_records = history_query.all()

        # Форматируем данные для ответа
        history_data = []
        for record in history_records:
            history_data.append(
                {
                    "timestamp": record.recorded_at.isoformat(),
                    "size_bytes": record.size_bytes,
                    "size_human": human_size(record.size_bytes),
                    "file_count": record.file_count,
                }
            )

        logger.info(
            f"Возвращено {len(history_data)} записей истории для стрима {stream.name}"
        )

        return jsonify(
            {
                "stream_id": stream_id,
                "stream_name": stream.name,
                "history": history_data,
                "success": True,
            }
        )

    except ValidationError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        logger.error(f"Ошибка при получении истории стрима {stream_id}: {e}")
        return (
            jsonify({"error": f"Ошибка получения истории: {e}", "success": False}),
            500,
        )


# GET: Проверка аутентификации
@bp.route("/api/auth/check", methods=["GET"])
def check_auth_status():
    """
    API endpoint для проверки статуса аутентификации Perforce

    Returns:
        JSON: {success: true/false, tickets_file_exists: bool, servers: list}

    Status Codes:
        200: Успешная проверка
    """
    tickets_exist = check_tickets_exist()

    # Проверяем аутентификацию для каждого сервера
    servers = Server.query.all()
    server_auth_status = []

    for server in servers:
        auth_ok = verify_p4_authentication(server.p4port, server.p4user)
        server_auth_status.append(
            {
                "server_id": server.id,
                "server_name": server.name,
                "p4port": server.p4port,
                "p4user": server.p4user,
                "authenticated": auth_ok,
            }
        )

    return jsonify(
        {
            "tickets_file_exists": tickets_exist,
            "servers": server_auth_status,
            "success": True,
        }
    )
