# tools/p4_auth.py

"""
Скрипт для авторизации на серверах Perforce и получения тикет
Запускается вручную в начале работы с проектом
"""

import getpass
import os
import sys
from pathlib import Path

import P4

# Добавляем корневую директорию проекта в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация логирования
from core.logging import setup_logging

logger = setup_logging()


def read_servers_config():
    """Читает конфигурацию серверов из YAML файла"""
    config_path = project_root / "config" / "servers.yaml"

    if not config_path.exists():
        logger.error(f"Конфигурационный файл {config_path} не найден")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("servers", [])
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурационного файла: {e}")
        return None


def get_password(server_config):
    """Получает пароль из конфига или переменных окружения"""
    p4port = server_config["p4port"]
    p4user = server_config["p4user"]

    # Сначала проверяем пароль в конфиге
    password = server_config.get("password")
    if password:
        logger.info(f"Пароль для {p4user}@{p4port} взят из конфигурационного файла")
        return password, "config"

    # Затем проверяем общий пароль в .env
    env_password = os.getenv("P4_COMMON_PASSWORD")
    if env_password:
        logger.info(
            f"Пароль для {p4user}@{p4port} взят из переменной окружения P4_COMMON_PASSWORD"
        )
        return env_password, "env"

    # Если пароль не найден, запрашиваем у пользователя
    logger.warning(f"Пароль не найден для пользователя {p4user} на сервере {p4port}")
    print(f"Введите пароль для {p4user}@{p4port}: ", end="")
    user_password = getpass.getpass("")
    return user_password, "manual"


def authenticate_server(server_config):
    """
    Выполняет авторизацию на одном сервере
    """
    p4port = server_config["p4port"]
    p4user = server_config["p4user"]

    password, password_source = get_password(server_config)

    if not password:
        logger.error(f"Пароль не указан для сервера {p4port}")
        return False

    logger.info(
        f"Авторизация на сервере {p4port} с пользователем {p4user} (пароль из {password_source})"
    )

    try:
        # Создаем соединение
        p4 = P4.P4()
        p4.port = p4port
        p4.user = p4user
        p4.password = password
        p4.ticket_file = str(project_root / "instance" / ".p4tickets")

        # Устанавливаем уровень исключений
        p4.exception_level = 1

        # Подключаемся к серверу
        p4.connect()

        # Выполняем логин
        result = p4.run_login()

        # Проверяем результат
        if result and len(result) > 0:
            logger.info(f"Успешная авторизация на сервере {p4port}")
            logger.debug(f"Результат логина: {result}")
            return True
        else:
            logger.error(f"Не удалось выполнить логин на сервере {p4port}")
            return False

    except P4.P4Exception as e:
        logger.error(f"Ошибка P4 при авторизации на сервере {p4port}: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при авторизации на сервере {p4port}: {e}")
        return False
    finally:
        # Всегда закрываем соединение
        try:
            if "p4" in locals():
                p4.disconnect()
        except:
            pass


def verify_p4_connection(server_config):
    """
    Дополнительная функция: проверяет соединение после авторизации
    """
    p4port = server_config["p4port"]
    p4user = server_config["p4user"]

    try:
        p4 = P4.P4()
        p4.port = p4port
        p4.user = p4user
        p4.ticket_file = str(project_root / "instance" / ".p4tickets")
        p4.connect()

        # Простая проверка соединения
        result = p4.run("info")
        p4.disconnect()

        logger.info(f"Проверка для {p4user}@{p4port}: УСПЕХ")
        return True

    except Exception as e:
        logger.warning(f"Проверка для {p4user}@{p4port}: {e}")
        return False
    finally:
        # Всегда закрываем соединение
        try:
            if "p4" in locals():
                p4.disconnect()
        except:
            pass


def main():
    """Основная функция скрипта"""
    logger.info("Запуск скрипта авторизации Perforce")

    # Проверяем наличие файла .p4tickets
    tickets_file = project_root / "instance" / ".p4tickets"
    if tickets_file.exists():
        logger.info(f"Файл тикетов уже существует: {tickets_file}")
        response = input("Перезаписать существующие тикеты? (y/N): ")
        if response.lower() != "y":
            logger.info("Авторизация отменена")
            return

    # Читаем конфигурацию серверов
    servers = read_servers_config()
    if not servers:
        logger.error("Не удалось прочитать конфигурацию серверов")
        sys.exit(1)

    logger.info(f"Найдено {len(servers)} серверов для авторизации")

    # Выполняем авторизацию для каждого сервера
    success_count = 0
    for server in servers:
        if authenticate_server(server):
            success_count += 1
            # Дополнительная проверка
            verify_p4_connection(server)

    logger.info(f"Авторизация завершена. Успешно: {success_count}/{len(servers)}")

    if success_count > 0:
        logger.info(f"Тикеты сохранены в: {tickets_file}")
        logger.info("Теперь можно запускать основное приложение")
    else:
        logger.error("Не удалось выполнить авторизацию ни на одном сервере")
        sys.exit(1)


if __name__ == "__main__":
    main()
