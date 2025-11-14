# app/models.py

"""
Модели данных SQLAlchemy для базы данных
Определяет структуру таблиц серверов и стримов
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

# Инициализация объекта базы данных SQLAlchemy
db = SQLAlchemy()


class Server(db.Model):
    """Модель сервера Perforce"""

    # Название таблицы в базе данных
    __tablename__ = "servers"

    # Поля таблицы
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор
    name = db.Column(db.String(100), nullable=False)  # Человеко-читаемое имя
    p4port = db.Column(db.String(200), nullable=False, unique=True)  # Адрес сервера
    p4user = db.Column(db.String(100), nullable=False)  # Имя пользователя
    stream_mask = db.Column(
        db.String(100), default="*role*"
    )  # Маска для фильтрации стримов
    created_at = db.Column(db.DateTime, default=datetime.now)  # Время создания

    # Связь один-ко-многим с таблицей стримов
    streams = db.relationship(
        "Stream", back_populates="server", cascade="all, delete-orphan"
    )

    def __repr__(self):
        """Строковое представление объекта для отладки"""
        return f"<Server {self.name} ({self.p4port})>"


class Stream(db.Model):
    """Модель стрима Perforce"""

    # Название таблицы в базе данных
    __tablename__ = "streams"

    # Поля таблицы
    id = db.Column(db.Integer, primary_key=True)  # Уникальный идентификатор
    name = db.Column(db.String(500), nullable=False)  # Полное имя стрима
    size_bytes = db.Column(db.BigInteger, default=0)  # Размер в байтах
    file_count = db.Column(db.Integer, default=0)  # Количество файлов
    last_updated = db.Column(db.DateTime)  # Время последнего обновления
    server_id = db.Column(
        db.Integer, db.ForeignKey("servers.id"), nullable=False
    )  # Внешний ключ

    # Связь многие-к-одному с таблицей серверов
    server = db.relationship("Server", back_populates="streams")

    def __repr__(self):
        """Строковое представление объекта для отладки"""
        return (
            f"<Stream {self.name} ({self.size_bytes} bytes, {self.file_count} files)>"
        )


class StreamHistory(db.Model):
    """Модель истории изменений размеров стримов"""

    __tablename__ = "stream_history"

    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(
        db.Integer, db.ForeignKey("streams.id", ondelete="CASCADE"), nullable=False
    )
    size_bytes = db.Column(db.BigInteger, nullable=False)
    file_count = db.Column(db.Integer, default=0)
    recorded_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Связь с основным стримом
    stream = db.relationship(
        "Stream", backref=db.backref("history_entries", cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<StreamHistory {self.stream_id}: {self.size_bytes} bytes, {self.file_count} files at {self.recorded_at}>"
