# run.py

"""
Основной модуль запуска Flask приложения для мониторинга Perforce стримов.
"""

import os

from flask import Flask

from app.config_utils import sync_servers_from_config
from app.models import Server, db
from app.scheduler import init_scheduler
from app.views import bp
from config.settings import SCHEDULER

# Инициализация логирования
from core.logging import setup_logging

logger = setup_logging()

# Получаем базовую директорию проекта
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Базовая конфигурация приложения"""

    # Отключаем отслеживание модификаций SQLAlchemy для экономии памяти
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Отключаем API планировщика в продакшене для безопасности
    SCHEDULER_API_ENABLED = False

    # Загружаем настройки планировщика из settings.py
    SCHEDULER_UPDATE_INTERVAL_HOURS = SCHEDULER.get("update_interval_hours", 24)

    # Увеличиваем лимит размера заголовков
    MAX_HEADER_SIZE = 32 * 1024  # 32KB вместо стандартных 8KB


class DevelopmentConfig(Config):
    """Конфигурация для режима разработки"""

    DEBUG = True  # Включаем режим отладки
    TESTING = True  # Включаем режим тестирования
    # URI для SQLite базы данных в папке instance
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'dev.db')}"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 30,  # Увеличиваем таймаут до 30 секунд
            "check_same_thread": False,  # Разрешаем доступ из разных потоков
        },
        "pool_pre_ping": True,  # Проверка соединения перед использованием
        "pool_recycle": 300,  # Переподключение каждые 5 минут
    }
    HOST = "0.0.0.0"  # Принимаем подключения со всех интерфейсов
    PORT = 5000  # Порт по умолчанию


class ProductionConfig(Config):
    """Конфигурация для продакшн режима"""

    DEBUG = False  # Отключаем режим отладки
    TESTING = False  # Отключаем режим тестирования
    # URI для production базы данных
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(basedir, 'instance', 'prod.db')}"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 30,
            "check_same_thread": False,
        },
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    HOST = "0.0.0.0"
    PORT = 5000  # Порт по умолчанию


def create_app(config_class=None):
    """Фабрика для создания Flask приложения"""

    # Определяем конфигурацию по умолчанию на основе переменной окружения
    if config_class is None:
        if os.environ.get("FLASK_ENV") == "production":
            config_class = ProductionConfig
        else:
            config_class = DevelopmentConfig

    # Создаем экземпляр Flask приложения
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Если URI БД не задан в конфиге, используем значение по умолчанию
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"sqlite:///{os.path.join(basedir, 'instance', 'data.db')}"
        )

    # Настройка статических файлов
    app.static_folder = "static"  # Папка со статическими файлами
    app.static_url_path = "/static"  # URL префикс для статических файлов

    # Инициализация расширений
    db.init_app(app)  # Инициализация базы данных
    app.register_blueprint(bp)  # Регистрация blueprint с маршрутами

    # Работа с контекстом приложения
    with app.app_context():
        # Создаем папку instance если не существует
        instance_path = os.path.join(basedir, "instance")
        os.makedirs(instance_path, exist_ok=True)

        # Создание таблиц в БД
        db.create_all()

        # Синхронизация серверов из конфига с обработкой ошибок
        try:
            sync_result = sync_servers_from_config()
            logger.info(f"Синхронизация серверов: {sync_result}")
        except Exception as e:
            logger.error(f"Ошибка при синхронизации серверов: {e}")

    # Инициализация планировщика для фоновых задач
    init_scheduler(app)

    # Логируем режим запуска
    logger.info(
        f"Приложение запущено в {'режиме разработки' if app.debug else 'продакшен режиме'}"
    )
    logger.info(f"Хост: {app.config['HOST']}, Порт: {app.config['PORT']}")
    logger.info(f"База данных: {app.config['SQLALCHEMY_DATABASE_URI']}")

    return app


if __name__ == "__main__":
    """
    Точка входа для запуска в режиме разработки.
    Используется при прямом запуске файла через python run.py
    """

    # Автоматически определяем среду выполнения
    if os.environ.get("FLASK_ENV") == "production":
        config = ProductionConfig
        logger.info("Запуск в продакшен режиме (через python run.py)")
    else:
        config = DevelopmentConfig
        logger.info("Запуск в режиме разработки (через python run.py)")

    app = create_app(config)

    # В режиме разработки используем настройки для отладки
    logger.info("Flask сервер запускается...")
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
        # Увеличиваем лимит заголовков для Flask
        max_header_size=app.config["MAX_HEADER_SIZE"],
    )
