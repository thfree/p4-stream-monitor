# core/logging.py

"""
Модуль настройки логирования приложения.
Реализован как класс для гибкой конфигурации и переиспользования.

# Вариант 1: Через класс
from core.logging import AppLogger
logger = AppLogger.from_settings().setup()

# Вариант 2: Через старую функцию (для совместимости)
from core.logging import setup_logging
logger = setup_logging()

"""

import logging
from pathlib import Path
from typing import Dict, Optional


class AppLogger:
    """
    Класс для управления логированием приложения.

    Args:
        config (Dict): Конфигурация логирования. Должна содержать:
            - level: Уровень логирования (DEBUG, INFO и т.д.)
            - log_file: Путь к файлу логов
            - log_format: Формат сообщений
            - encoding: Кодировка файла
            - console: Флаг вывода в консоль (bool)
    """

    def __init__(self, config: Dict):
        self.config = config
        self._log_level = getattr(logging, config["level"], logging.INFO)
        self._formatter = logging.Formatter(config["log_format"])
        self._root_logger = logging.getLogger()
        self._setup_done = False

    def setup(self) -> logging.Logger:
        """
        Настраивает логирование на основе конфигурации.

        Returns:
            Настроенный root-логгер

        Raises:
            PermissionError: Если нет прав на запись логов
            OSError: При проблемах с файловой системой
        """
        if self._setup_done:
            return self._root_logger

        try:
            self._prepare_log_directory()
            self._clean_handlers()
            self._add_file_handler()

            if self.config.get("console", True):
                self._add_console_handler()

            self._root_logger.setLevel(self._log_level)
            self._setup_done = True
            return self._root_logger

        except Exception as e:
            self._fallback_setup()
            raise

    def _prepare_log_directory(self) -> None:
        """Создает директорию для логов при необходимости."""
        log_path = Path(self.config["log_file"]).parent
        log_path.mkdir(parents=True, exist_ok=True)

    def _clean_handlers(self) -> None:
        """Удаляет все существующие обработчики."""
        for handler in self._root_logger.handlers[:]:
            self._root_logger.removeHandler(handler)
            handler.close()

    def _add_file_handler(self) -> None:
        """Добавляет файловый обработчик логов."""
        file_handler = logging.FileHandler(
            self.config["log_file"], encoding=self.config["encoding"]
        )
        file_handler.setFormatter(self._formatter)
        self._root_logger.addHandler(file_handler)

    def _add_console_handler(self) -> None:
        """Добавляет консольный обработчик."""
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self._formatter)
        self._root_logger.addHandler(console_handler)

    def _fallback_setup(self) -> None:
        """Резервная настройка при ошибках основной конфигурации."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler()],
        )
        logging.warning("Используется резервная конфигурация логирования")

    @classmethod
    def from_settings(cls) -> "AppLogger":
        """
        Альтернативный конструктор для создания из настроек.

        Returns:
            Экземпляр AppLogger с конфигурацией из settings.py
        """
        from config.settings import LOGGING  # Ленивый импорт

        return cls(LOGGING)


def setup_logging() -> logging.Logger:
    """
    Функция-обертка для обратной совместимости.
    Использует AppLogger с настройками по умолчанию.
    """
    return AppLogger.from_settings().setup()
