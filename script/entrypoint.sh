#!/bin/bash
# /script/entrypoint.sh

set -e

echo "Starting P4 Monitor initialization..."

# Создаем необходимые директории
mkdir -p /app/instance /app/logs /app/config /app/nginx/conf.d /app/ssl

# Функция для копирования если файл отсутствует
copy_if_missing() {
    local src=$1
    local dest=$2
    if [ ! -f "$dest" ] && [ -f "$src" ]; then
        echo "Creating $dest from default..."
        cp "$src" "$dest"
        chown p4monitor:p4monitor "$dest" 2>/dev/null || true
    fi
}

# Функция для создания директории и копирования содержимого
copy_dir_if_empty() {
    local src_dir=$1
    local dest_dir=$2
    
    # Создаем целевую директорию если не существует
    mkdir -p "$dest_dir"
    
    # Если целевая директория пуста и исходная существует - копируем
    if [ -d "$src_dir" ] && [ -z "$(ls -A "$dest_dir" 2>/dev/null)" ]; then
        echo "Copying default files to $dest_dir..."
        cp -r "$src_dir"/* "$dest_dir"/ 2>/dev/null || true
        chown -R p4monitor:p4monitor "$dest_dir" 2>/dev/null || true
    fi
}

echo "Checking configuration files..."

# Копируем отдельные конфиг файлы если они отсутствуют
copy_if_missing "/app/default_configs/gunicorn.conf.py" "/app/config/gunicorn.conf.py"
copy_if_missing "/app/default_configs/settings.py" "/app/config/settings.py"
copy_if_missing "/app/default_configs/servers.yaml.example" "/app/config/servers.yaml"
copy_if_missing "/app/default_configs/nginx/nginx.conf.example" "/app/nginx/nginx.conf"

# Копируем конфиги nginx если директория пуста
copy_dir_if_empty "/app/default_configs/nginx/conf.d" "/app/nginx/conf.d"

# Проверяем что обязательные файлы существуют
check_required_files() {
    local missing_files=()
    
    [ ! -f "/app/config/gunicorn.conf.py" ] && missing_files+=("gunicorn.conf.py")
    [ ! -f "/app/config/settings.py" ] && missing_files+=("settings.py")
    [ ! -f "/app/nginx/nginx.conf" ] && missing_files+=("nginx.conf")
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        echo "Error: Required config files missing: ${missing_files[*]}"
        echo "Make sure the image was built correctly with all default configs"
        exit 1
    fi
}

# Проверяем обязательные файлы
check_required_files

echo "All configurations are ready"
echo "Starting application..."

exec "$@"