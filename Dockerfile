# Dockerfile
ARG P4_VERSION=r25.1

# 1. Build stage
FROM python:3.13-slim AS builder

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Скачивание Perforce CLI
ARG P4_VERSION
RUN curl -fsSL "https://ftp.perforce.com/perforce/${P4_VERSION}/bin.linux26x86_64/p4" -o /tmp/p4 \
    && chmod +x /tmp/p4

WORKDIR /app

COPY requirements.txt .

# Устанавливаем Python пакеты
RUN pip install --user --no-cache-dir -r requirements.txt

# 2. Final stage
FROM python:3.13-slim

# Аргумент для версии
ARG VERSION=0.0.0

# Метки
LABEL maintainer="ruslan@thfree.ru" \
    version="${VERSION}" \
    description="Web application for monitoring the size of Perforce streams (P4 Stream Monitor)" \
    org.opencontainers.image.title="p4-stream-monitor" \
    org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.description="Web application for monitoring the size of Perforce streams (P4 Stream Monitor)" \
    org.opencontainers.image.authors="@ThFree <ruslan@thfree.ru>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://thfree.ru/" \
    org.opencontainers.image.source="https://git.thfree.ru/ThFree/p4-stream-monitor"

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    libssl3 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя и группу
RUN addgroup --system p4monitor && \
    adduser --system --ingroup p4monitor --home /home/p4monitor --shell /bin/false p4monitor

# Копируем p4 из builder stage
COPY --from=builder /tmp/p4 /usr/local/bin/p4

# Копируем Python пакеты в домашнюю директорию пользователя
COPY --from=builder --chown=p4monitor:p4monitor /root/.local /home/p4monitor/.local

# Создание структуры директорий
RUN mkdir -p /app/logs /app/instance /app/config /app/nginx/conf.d /app/default_configs/nginx \
    && chown -R p4monitor:p4monitor /app

WORKDIR /app

USER p4monitor

# Копирование всего кода за один раз (использует .dockerignore)
COPY --chown=p4monitor:p4monitor . .

# Копируем конфиги по умолчанию в отдельную директорию
RUN cp -r /app/config/* /app/default_configs/ 2>/dev/null || true && \
    cp -r /app/nginx/* /app/default_configs/nginx/ 2>/dev/null || true

# Переменные окружения для production
ENV PATH=/home/p4monitor/.local/bin:$PATH \
    FLASK_ENV=production \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Проверка
RUN p4 -V && python -c "import P4; print('P4 loaded OK')"

# Экспоз порта
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/info', timeout=5)" || exit 1

# Сделаем entrypoint исполняемым
COPY --chown=p4monitor:p4monitor script/entrypoint.sh /script/entrypoint.sh
RUN chmod +x /script/entrypoint.sh

# Используем entrypoint
ENTRYPOINT ["/script/entrypoint.sh"]

# Запуск приложения
CMD ["gunicorn", "--config", "config/gunicorn.conf.py", "run:create_app()"]