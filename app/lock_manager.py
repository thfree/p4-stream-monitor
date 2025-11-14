# app/lock_manager.py

"""
Менеджер блокировок для предотвращения конфликтующих операций
"""

import logging
import threading
from contextlib import contextmanager
from typing import Optional

# Используем централизованный логгер
logger = logging.getLogger(__name__)


class LockManager:
    """Менеджер блокировок для операций с Perforce"""

    def __init__(self):
        # Глобальная блокировка для массовых операций
        self._global_lock = threading.RLock()

        # Блокировки для отдельных серверов
        self._server_locks = {}
        self._server_locks_lock = threading.Lock()

        # Флаги состояния операций
        self._mass_update_in_progress = False
        self._server_updates_in_progress = set()
        self._config_sync_in_progress = (
            False  # Новая блокировка для синхронизации конфига
        )

    def _get_server_info(self, server_id: int) -> str:
        """Получает информацию о сервере для логирования"""
        try:
            from flask import current_app

            from app.models import Server

            with current_app.app_context():
                server = Server.query.get(server_id)
                if server:
                    return f"{server.name} (ID: {server_id})"
        except Exception as e:
            logger.debug(f"Не удалось получить информацию о сервере {server_id}: {e}")

        return f"ID: {server_id}"

    def is_mass_update_in_progress(self) -> bool:
        """Проверяет, выполняется ли массовое обновление"""
        with self._global_lock:
            return self._mass_update_in_progress

    def is_server_update_in_progress(self, server_id: int) -> bool:
        """Проверяет, выполняется ли обновление для сервера"""
        with self._global_lock:
            return server_id in self._server_updates_in_progress

    def is_config_sync_in_progress(self) -> bool:
        """Проверяет, выполняется ли синхронизация конфига"""
        with self._global_lock:
            return self._config_sync_in_progress

    def can_start_mass_update(self) -> bool:
        """Проверяет, можно ли начать массовое обновление"""
        with self._global_lock:
            return (
                not self._mass_update_in_progress
                and len(self._server_updates_in_progress) == 0
                and not self._config_sync_in_progress
            )

    def can_start_server_update(self, server_id: int) -> bool:
        """Проверяет, можно ли начать обновление сервера"""
        with self._global_lock:
            return (
                not self._mass_update_in_progress
                and server_id not in self._server_updates_in_progress
                and not self._config_sync_in_progress
            )

    def can_start_stream_update(self, server_id: int) -> bool:
        """Проверяет, можно ли начать обновление стрима"""
        with self._global_lock:
            return (
                not self._mass_update_in_progress
                and server_id not in self._server_updates_in_progress
                and not self._config_sync_in_progress
            )

    def can_start_config_sync(self) -> bool:
        """Проверяет, можно ли начать синхронизацию конфига"""
        with self._global_lock:
            return (
                not self._mass_update_in_progress
                and len(self._server_updates_in_progress) == 0
                and not self._config_sync_in_progress
            )

    @contextmanager
    def mass_update_lock(self):
        """Контекстный менеджер для массового обновления"""
        with self._global_lock:
            if not self.can_start_mass_update():
                raise RuntimeError(
                    "Массовое обновление уже выполняется или выполняется обновление сервера/конфига"
                )

            self._mass_update_in_progress = True
            logger.info("🔒 Захвачена блокировка массового обновления")

        try:
            yield
        finally:
            with self._global_lock:
                self._mass_update_in_progress = False
                logger.info("🔓 Освобождена блокировка массового обновления")

    @contextmanager
    def server_update_lock(self, server_id: int):
        """Контекстный менеджер для обновления сервера"""
        server_info = self._get_server_info(server_id)

        with self._global_lock:
            if not self.can_start_server_update(server_id):
                raise RuntimeError(
                    f"Обновление сервера {server_info} невозможно: массовое обновление или обновление этого сервера уже выполняется"
                )

            self._server_updates_in_progress.add(server_id)
            logger.info(f"🔒 Захвачена блокировка обновления сервера {server_info}")

        try:
            yield
        finally:
            with self._global_lock:
                self._server_updates_in_progress.discard(server_id)
                logger.info(
                    f"🔓 Освобождена блокировка обновления сервера {server_info}"
                )

    @contextmanager
    def stream_update_lock(self, server_id: int):
        """Контекстный менеджер для обновления стрима"""
        server_info = self._get_server_info(server_id)

        with self._global_lock:
            if not self.can_start_stream_update(server_id):
                raise RuntimeError(
                    f"Обновление стрима сервера {server_info} невозможно: массовое обновление или обновление сервера уже выполняется"
                )

            # Захватываем блокировку для сервера при обновлении стрима
            self._server_updates_in_progress.add(server_id)
            logger.info(
                f"🔒 Захвачена блокировка обновления стрима сервера {server_info}"
            )

        try:
            yield
        finally:
            with self._global_lock:
                self._server_updates_in_progress.discard(server_id)
                logger.info(
                    f"🔓 Освобождена блокировка обновления стрима сервера {server_info}"
                )

    @contextmanager
    def server_sync_lock(self, server_id: int):
        """Контекстный менеджер для синхронизации стримов сервера (без расчета размеров)"""
        server_info = self._get_server_info(server_id)

        with self._global_lock:
            if not self.can_start_server_update(server_id):
                raise RuntimeError(
                    f"Синхронизация сервера {server_info} невозможна: массовое обновление или обновление этого сервера уже выполняется"
                )

            self._server_updates_in_progress.add(server_id)
            logger.info(f"🔒 Захвачена блокировка синхронизации сервера {server_info}")

        try:
            yield
        finally:
            with self._global_lock:
                self._server_updates_in_progress.discard(server_id)
                logger.info(
                    f"🔓 Освобождена блокировка синхронизации сервера {server_info}"
                )

    @contextmanager
    def config_sync_lock(self):
        """Контекстный менеджер для синхронизации конфигурации серверов"""
        with self._global_lock:
            if not self.can_start_config_sync():
                raise RuntimeError(
                    "Синхронизация конфига невозможна: массовое обновление или обновление сервера уже выполняется"
                )

            self._config_sync_in_progress = True
            logger.info("🔒 Захвачена блокировка синхронизации конфига")

        try:
            yield
        finally:
            with self._global_lock:
                self._config_sync_in_progress = False
                logger.info("🔓 Освобождена блокировка синхронизации конфига")


# Глобальный экземпляр менеджера блокировок
lock_manager = LockManager()
