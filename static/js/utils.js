/**
 * static\js\utils.js
 * Утилиты для приложения Perforce Stream Monitor
 * Содержит функции форматирования чисел, размеров файлов и другие вспомогательные функции
 * Обеспечивает единообразное отображение данных во всем приложении
 */

const Utils = {
    /**
     * Форматирует большие числа в удобочитаемый вид с суффиксами
     * @param {number} num - Число для форматирования
     * @returns {string} Отформатированное число с суффиксом
     */
    formatLargeNumber(num) {
        if (typeof num !== "number" || isNaN(num)) {
            return "0";
        }

        if (num === 0) return "0";

        const absNum = Math.abs(num);
        const sign = num < 0 ? "-" : "";

        if (absNum >= 1000000000) {
            return sign + (absNum / 1000000000).toFixed(1) + "B";
        } else if (absNum >= 1000000) {
            return sign + (absNum / 1000000).toFixed(1) + "M";
        } else if (absNum >= 1000) {
            return sign + (absNum / 1000).toFixed(1) + "K";
        }

        return sign + absNum.toString();
    },

    /**
     * Форматирует размер в байтах в читаемый вид
     * @param {number} bytes - Размер в байтах
     * @param {boolean} useBinary - Использовать бинарную систему (GiB) вместо десятичной (GB)
     * @returns {string} Отформатированный размер
     */
    formatFileSize: function (bytes, useBinary = false) {
        if (bytes === 0 || bytes === null || bytes === undefined) return "0 B";

        if (useBinary) {
            // Бинарная система (GiB, MiB, KiB)
            const sizes = ["B", "KiB", "MiB", "GiB", "TiB"];
            const i = Math.floor(Math.log(bytes) / Math.log(1024));

            if (i === 0) return bytes + " " + sizes[i];
            return (bytes / Math.pow(1024, i)).toFixed(1) + " " + sizes[i];
        } else {
            // Десятичная система (GB, MB, KB)
            const sizes = ["B", "KB", "MB", "GB", "TB"];
            const i = Math.floor(Math.log(bytes) / Math.log(1000));

            if (i === 0) return bytes + " " + sizes[i];
            return (bytes / Math.pow(1000, i)).toFixed(1) + " " + sizes[i];
        }
    },
};

// Сделать доступным глобально
window.Utils = Utils;
