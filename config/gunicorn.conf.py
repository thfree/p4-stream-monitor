# config/gunicorn.conf.py
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

# Создаем директорию для логов если не существует
os.makedirs(os.path.join(rootdir, "logs"), exist_ok=True)

# ==================== ОСНОВНЫЕ НАСТРОЙКИ ====================
bind = "0.0.0.0:5000"
workers = 2
threads = 2
worker_class = "sync"

# ==================== ТАЙМАУТЫ ====================
timeout = 300  # 5 минут для длинных операций с P4
graceful_timeout = 30
keepalive = 2

# ==================== ЛОГИРОВАНИЕ ====================
# Используем настройки из core.logging
accesslog = "-"  # Используем наше кастомное логирование
errorlog = "-"  # Используем наше кастомное логирование
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True

# Формат логов (будет использоваться из нашего logging.py)
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# ==================== ПРОИЗВОДИТЕЛЬНОСТЬ ====================
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# ==================== БЕЗОПАСНОСТЬ ====================
limit_request_line = 16384
limit_request_fields = 200
limit_request_field_size = 32768

# ==================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ====================
raw_env = [
    "FLASK_ENV=production",
]


# ==================== SPECIAL FOR P4 STREAM MONITOR ====================
def pre_fork(server, worker):
    """Вызывается перед созданием воркера"""
    server.log.info("Создание нового воркера")


def post_fork(server, worker):
    """Вызывается после создания воркера"""
    server.log.info("Воркер %s создан", worker.pid)


def when_ready(server):
    """Вызывается когда Gunicorn готов принимать соединения"""
    logger = setup_logging()
    logger.info("P4 Stream Monitor запущен в production режиме")


def worker_int(worker):
    """Вызывается при выходе воркера"""
    logger = setup_logging()
    logger.info("Воркер %s завершил работу", worker.pid)


def worker_abort(worker):
    """Вызывается при аварийном завершении воркера"""
    logger = setup_logging()
    logger.error("Воркер %s аварийно завершил работу", worker.pid)


def on_exit(server):
    """Вызывается при завершении Gunicorn"""
    logger = setup_logging()
    logger.info("P4 Stream Monitor остановлен")
