#!/bin/bash

# Получение директории скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Загрузка переменных окружения
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Чтение версии из файла VERSION
if [ -f "$PROJECT_ROOT/VERSION" ]; then
    VERSION=$(cat "$PROJECT_ROOT/VERSION" | tr -d '[:space:]')
    echo "Найдена версия: $VERSION"
else
    echo "Предупреждение: Файл VERSION не найден, используется версия по умолчанию"
    VERSION="0.0.0"
fi

# Установка значений по умолчанию
TAG=${TAG:-"$VERSION"}
JFROG_USER=${JFROG_USER:-"admin"}

# Экспорт версии для docker-compose
export VERSION

# Проверка переменных
if [[ -z "$JFROG_REGISTRY" || -z "$REPOSITORY" || -z "$IMAGE_NAME" ]]; then
    echo "Ошибка: Проверьте JFROG_REGISTRY, REPOSITORY и IMAGE_NAME в .env"
    exit 1
fi

# Использование токена из аргумента или переменной
if [[ $# -eq 1 ]]; then
    JFROG_TOKEN=$1
    elif [[ -z "$JFROG_TOKEN" ]]; then
    echo "Ошибка: Укажите токен: ./script.sh <токен> или установите JFROG_TOKEN в .env"
    exit 1
fi

# Основные функции
login_to_jfrog() {
    echo "Вход в JFrog..."
    echo "$JFROG_TOKEN" | docker login "$JFROG_REGISTRY" -u "$JFROG_USER" --password-stdin
    if [ $? -ne 0 ]; then
        echo "Ошибка: Не удалось войти в JFrog"
        exit 1
    fi
}

build_image() {
    echo "Сборка образа версии $VERSION..."
    docker-compose -f "docker-compose.build.yml" build
    if [ $? -ne 0 ]; then
        echo "Ошибка: Сборка образа не удалась"
        exit 1
    fi
}

push_image() {
    echo "Отправка образа версии $VERSION..."
    docker-compose -f "docker-compose.build.yml" push
    if [ $? -ne 0 ]; then
        echo "Ошибка: Отправка образа не удалась"
        exit 1
    fi
}

# Основной процесс
main() {
    set -e
    login_to_jfrog
    build_image
    push_image
    echo "Готово: $JFROG_REGISTRY/$REPOSITORY/$IMAGE_NAME:$TAG (версия: $VERSION)"
}

main "$@"