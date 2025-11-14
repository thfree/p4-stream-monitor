# config/gunicorn_dev.conf.py
import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Инициализация логирования
from core.logging import setup_logging

# Базовая директория проекта
basedir = os.path.abspath(os.path.dirname(__file__))
rootdir = os.path.dirname(basedir)

# Настройки для разработки
bind = "0.0.0.0:5000"
workers = 1
threads = 2
worker_class = "sync"

# Автоперезагрузка при изменениях
reload = True
reload_engine = "auto"

# Логирование - используем наше кастомное логирование
accesslog = "-"  # stdout через наше логирование
errorlog = "-"  # stdout через наше логирование
loglevel = "debug"
capture_output = True
enable_stdio_inheritance = True

# Таймауты
timeout = 300
graceful_timeout = 10

# Переменные окружения
raw_env = [
    "FLASK_ENV=development",
]


def when_ready(server):
    """Вызывается когда Gunicorn готов принимать соединения"""
    logger = setup_logging()
    logger.info("P4 Stream Monitor запущен в development режиме")


def worker_int(worker):
    """Вызывается при выходе воркера"""
    logger = setup_logging()
    logger.info("Воркер %s завершил работу", worker.pid)


def on_exit(server):
    """Вызывается при завершении Gunicorn"""
    logger = setup_logging()
    logger.info("P4 Stream Monitor остановлен")
