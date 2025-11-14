# app/p4_utils.py

"""
Утилиты для работы с Perforce
Содержит функции для взаимодействия с Perforce серверами
"""

import logging
import os
import subprocess
from typing import Optional, Tuple

import P4

from .config_utils import check_tickets_exist, get_tickets_file_path
from .utils import human_size

# Используем централизованный логгер
logger = logging.getLogger(__name__)


def get_p4_connection(p4port: str, p4user: str) -> Optional[P4.P4]:
    """
    Создает и настраивает соединение с сервером Perforce

    Returns:
        P4.P4: Объект соединения или None при ошибке
    """
    if not check_tickets_exist():
        logger.error("Файл тикетов отсутствует, невозможно создать соединение")
        return None

    try:
        p4 = P4.P4()
        p4.port = p4port
        p4.user = p4user
        p4.ticket_file = str(get_tickets_file_path())

        # Настройка таймаутов
        p4.exception_level = 1  # Только ошибки
        p4.connect()

        logger.debug(f"Успешное подключение к {p4port} пользователем {p4user}")
        return p4

    except P4.P4Exception as e:
        logger.error(f"Ошибка P4 при подключении к {p4port}: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при подключении к {p4port}: {e}")
        return None


def verify_p4_authentication(p4port: str, p4user: str) -> bool:
    """
    Проверяет доступность аутентификации для сервера Perforce

    Returns:
        bool: True если аутентификация доступна, False в противном случае
    """
    p4 = get_p4_connection(p4port, p4user)
    if not p4:
        return False

    try:
        # Проверяем аутентификацию
        result = p4.run_login("-s")
        authenticated = len(result) > 0 and "ticket expires" in result[0]
        logger.debug(f"Проверка аутентификации {p4user}@{p4port}: {authenticated}")
        return authenticated
    except P4.P4Exception as e:
        logger.warning(f"Ошибка аутентификации для {p4user}@{p4port}: {e}")
        return False
    finally:
        p4.disconnect()


def get_streams_list(p4port: str, p4user: str, stream_filter: str) -> Optional[list]:
    """
    Получает список стримов с сервера

    Args:
        p4port: Адрес сервера
        p4user: Имя пользователя
        stream_filter: Фильтр для стримов

    Returns:
        list: Список имен стримов или None при ошибке
    """
    p4 = get_p4_connection(p4port, p4user)
    if not p4:
        return None

    try:
        streams = p4.run("streams", "-F", stream_filter)
        stream_names = [stream["Stream"] for stream in streams]
        logger.debug(
            f"Получено {len(stream_names)} стримов с фильтром: {stream_filter}"
        )
        return stream_names
    except P4.P4Exception as e:
        logger.error(f"Ошибка получения списка стримов: {e}")
        return None
    finally:
        p4.disconnect()


def run_p4_command(
    cmd, env, operation_name: str, input_data: str = None, check: bool = True
):
    """
    Универсальная функция для выполнения команд p4

    Args:
        cmd: Команда для выполнения
        env: Переменные окружения
        operation_name: Название операции для логирования
        input_data: Данные для stdin
        check: Проверять ли код возврата

    Returns:
        subprocess.CompletedProcess
    """
    logger.debug(f"Выполнение команды p4: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, env=env, input=input_data, capture_output=True, text=True, check=check
        )

        if result.returncode == 0:
            logger.debug(f"Команда p4 выполнена успешно: {operation_name}")
        else:
            logger.warning(
                f"Команда p4 завершилась с кодом {result.returncode}: {operation_name}\n"
                f"stderr: {result.stderr.strip()}\n"
                f"stdout: {result.stdout.strip()}"
            )

        return result

    except subprocess.CalledProcessError as e:
        logger.error(
            f"Ошибка выполнения команды p4: {operation_name}\n"
            f"Код ошибки: {e.returncode}\n"
            f"Команда: {' '.join(cmd)}\n"
            f"stderr: {e.stderr.strip()}\n"
            f"stdout: {e.stdout.strip()}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при выполнении команды p4 '{operation_name}': {e}"
        )
        raise


def get_p4_command_with_auth(base_command, p4port: str, p4user: str):
    """
    Формирует команду p4 с аутентификацией
    """
    tickets_file = get_tickets_file_path()

    # Базовые переменные окружения
    env = os.environ.copy()
    env["P4PORT"] = p4port
    env["P4USER"] = p4user
    env["P4TICKETS"] = str(tickets_file)

    # Если файл тикетов существует, используем его
    if not check_tickets_exist():
        logger.warning(
            f"Файл тикетов не найден: {tickets_file}. Команда может запросить пароль"
        )

    # Формируем полную команду
    full_command = base_command.copy()

    return full_command, env


def get_stream_size(
    p4port: str, p4user: str, stream: str, progress_info: str = ""
) -> Optional[Tuple[int, int]]:
    """
    Возвращает размер стрима в байтах и количество файлов или None при ошибке.
    Использует P4 Python для операций с клиентом и subprocess для fstat (избежание проблем с памятью).

    Args:
        p4port: Адрес сервера Perforce (host:port)
        p4user: Имя пользователя для аутентификации
        stream: Имя стрима для измерения
        progress_info: Информация о прогрессе для логирования

    Returns:
        tuple: (size_bytes, file_count) или None при ошибке
    """
    # Проверяем наличие тикетов перед началом работы
    if not check_tickets_exist():
        logger.error(
            f"Невозможно получить размер стрима {stream}: файл тикетов отсутствует"
        )
        return None

    import getpass
    import os
    import time

    # Генерируем уникальное имя временного клиента
    client_name = f"tmp_calc_{getpass.getuser()}_{int(time.time())}_{os.getpid()}"

    logger.debug(f"Расчет размера стрима: {stream}")

    p4 = None
    try:
        # 1. Создаем соединение с P4
        p4 = get_p4_connection(p4port, p4user)
        if not p4:
            return None

        # 2. Создаем временный клиент для стрима через P4 Python
        client_spec = p4.fetch_client(client_name)

        # Корректируем имя стрима
        if stream.startswith("//"):
            clean_stream = stream
        elif stream.startswith("/"):
            clean_stream = f"/{stream}"
        else:
            clean_stream = f"//{stream}"

        client_spec["Stream"] = clean_stream
        client_spec["Root"] = os.path.abspath("temp")
        client_spec["View"] = [f"{clean_stream}/... //{client_name}/..."]
        client_spec["Options"] = "rmdir compress"
        client_spec["SubmitOptions"] = "submitunchanged"

        p4.save_client(client_spec)
        logger.debug(
            f"Создан временный клиент: {client_name} для стрима {clean_stream}"
        )

        # Логируем информацию о прогрессе
        if progress_info:
            logger.info(f"{progress_info}")

        # 3. Получаем информацию о файлах в стриме через subprocess (fstat)
        # Исключаем удаленные файлы из подсчета
        base_cmd = [
            "p4",
            "-c",
            client_name,
            "-F",
            "%headAction% %fileSize%",
            "fstat",
            "-Ol",
            "-T",
            "headAction,fileSize",
            "//" + client_name + "/...",  # Явно указываем путь клиента
        ]
        cmd, env = get_p4_command_with_auth(base_cmd, p4port, p4user)

        logger.info(f"Начинаем расчет размера стрима {stream}")

        # Выполняем команду fstat через subprocess
        result = run_p4_command(
            cmd,
            env,
            f"Получение размеров файлов для {stream}",
            check=False,  # Не проверяем код возврата, так как могут быть предупреждения
        )

        if result.returncode != 0:
            logger.error(f"Ошибка выполнения fstat для {stream}: {result.returncode}")
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
            return None

        # Обрабатываем результат
        total_size = 0
        file_count = 0

        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(" ", 1)
            head_action = parts[0] if len(parts) > 0 else ""

            # Игнорируем удаленные файлы
            if head_action == "delete":
                continue

            # Обрабатываем только НЕудаленные файлы
            file_size_str = parts[1] if len(parts) > 1 else ""
            if file_size_str and file_size_str.isdigit():
                try:
                    file_size = int(file_size_str)
                    total_size += file_size
                    file_count += 1
                except (ValueError, TypeError):
                    # Пропускаем файлы с некорректным размером
                    continue

        # Проверяем, пустой ли стрим
        if file_count == 0:
            logger.info(f"Стрим {stream} полностью пуст (нет файлов)")

        logger.info(
            f"Расчет размера завершен: {stream} - {human_size(total_size)} "
            f"({file_count} файлов)"
        )

        return total_size, file_count

    except P4.P4Exception as e:
        logger.error(f"Ошибка P4 при расчете размера стрима {stream}: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка для стрима {stream}: {e}")
        return None
    finally:
        # Всегда пытаемся удалить временный клиент через P4 Python
        if p4:
            p4.client = ""  # Сбрасываем клиент
            try:
                p4.run_client("-df", client_name)
                logger.debug(f"Временный клиент {client_name} удален")
            except P4.P4Exception as e:
                if "doesn't exist" not in str(e):
                    logger.warning(f"Ошибка удаления клиента {client_name}: {e}")
            finally:
                p4.disconnect()
