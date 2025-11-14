# app/config_utils.py

"""
Утилиты для работы с конфигурацией
Синхронизирует данные серверов из YAML конфига с базой данных
"""

import logging
import os
from pathlib import Path

import yaml

from app.models import Server, db

# Используем централизованный логгер
logger = logging.getLogger(__name__)


def check_tickets_exist():
    """Проверяет существование файла тикетов и возвращает результат"""
    tickets_file = Path(__file__).parent.parent / "instance" / ".p4tickets"
    exists = tickets_file.exists()

    if not exists:
        logger.warning(f"Файл тикетов не найден: {tickets_file}")
        logger.warning("Запустите tools/p4_auth.py для авторизации на серверах")

    return exists


def get_tickets_file_path():
    """Возвращает путь к файлу тикетов"""
    return Path(__file__).parent.parent / "instance" / ".p4tickets"


def sync_servers_from_config():
    """Синхронизирует серверы из YAML конфига с базой данных"""
    logger.info("Начало синхронизации серверов из конфигурационного файла")

    # Проверяем существование конфигурационного файла
    if not os.path.exists("config/servers.yaml"):
        logger.error("Конфигурационный файл config/servers.yaml не найден")
        return "Конфигурационный файл config/servers.yaml не найден"

    # Читаем и парсим YAML конфиг
    try:
        with open("config/servers.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.debug("Конфигурационный файл успешно прочитан")
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурационного файла: {e}")
        return f"Ошибка чтения конфигурационного файла: {e}"

    # Проверяем наличие секции servers в конфиге
    if not config or "servers" not in config:
        logger.error("В конфигурационном файле отсутствует секция 'servers'")
        return "В конфигурационном файле отсутствует секция 'servers'"

    # Получаем все существующие серверы из БД
    existing_servers = {server.p4port: server for server in Server.query.all()}
    logger.debug(f"Найдено {len(existing_servers)} серверов в базе данных")

    # Создаем словарь серверов из конфига для быстрого поиска
    config_servers = {srv["p4port"]: srv for srv in config["servers"]}
    logger.debug(f"Найдено {len(config_servers)} серверов в конфигурационном файле")

    # Счетчики для статистики изменений
    added = 0  # Добавленные серверы
    updated = 0  # Обновленные серверы
    removed = 0  # Удаленные серверы

    # Добавляем или обновляем серверы из конфига
    for p4port, srv_config in config_servers.items():
        if p4port in existing_servers:
            # Обновляем существующий сервер
            server = existing_servers[p4port]
            server.name = srv_config["name"]
            server.p4user = srv_config["p4user"]
            server.stream_mask = srv_config.get("stream_mask", "*role*")
            updated += 1
            logger.debug(f"Обновлен сервер: {server.name} ({server.p4port})")
        else:
            # Добавляем новый сервер
            server = Server(
                name=srv_config["name"],
                p4port=p4port,
                p4user=srv_config["p4user"],
                stream_mask=srv_config.get("stream_mask", "*role*"),
            )
            db.session.add(server)
            added += 1
            logger.info(f"Добавлен новый сервер: {server.name} ({server.p4port})")

    # Удаляем серверы, которых нет в конфиге
    for p4port, server in existing_servers.items():
        if p4port not in config_servers:
            db.session.delete(server)
            removed += 1
            logger.warning(f"Удален сервер: {server.name} ({server.p4port})")

    # Сохраняем изменения если они есть
    if added > 0 or updated > 0 or removed > 0:
        try:
            db.session.commit()
            result = f"Серверы синхронизированы: +{added} ~{updated} -{removed}"
            logger.info(f"{result}")
            return result
        except Exception as e:
            logger.error(f"Ошибка сохранения изменений в базу данных: {e}")
            db.session.rollback()
            return f"Ошибка сохранения изменений: {e}"
    else:
        logger.info("Серверы уже синхронизированы, изменений не требуется")
        return "Серверы уже синхронизированы"
