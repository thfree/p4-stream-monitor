/**
 * static\js\notifications.js
 * Система уведомлений для пользовательского интерфейса
 * Предоставляет функции для показа временных сообщений разного типа
 * Поддерживает автоматическое скрытие, анимации и различные стили уведомлений
 */
const Notifications = {
    currentTimeout: null, // Таймер для автоматического скрытия текущего уведомления

    /**
     * Показывает уведомление пользователю
     * @param {string} message - Текст сообщения
     * @param {string} type - Тип уведомления (info, success, error)
     * @param {number} duration - Длительность показа в миллисекундах (0 = не скрывать автоматически)
     */
    show(message, type = "info", duration = 4000) {
        // Очищаем предыдущий таймер, если есть
        if (this.currentTimeout) {
            clearTimeout(this.currentTimeout);
            this.currentTimeout = null;
        }

        const feedback = document.getElementById("sync-feedback");

        // Сначала скрываем текущее уведомление, если оно есть
        this._hideImmediately();

        // Устанавливаем новое сообщение и тип
        feedback.textContent = message;
        feedback.className = `sync-feedback ${type}`;

        // Даем время для применения CSS классов, затем показываем с анимацией
        setTimeout(() => {
            feedback.classList.add("show");
        }, 10);

        // Настраиваем автоматическое скрытие, если duration > 0
        if (duration > 0) {
            this.currentTimeout = setTimeout(() => {
                this.hide();
            }, duration);
        }
    },

    /**
     * Плавно скрывает текущее уведомление с анимацией
     */
    hide() {
        const feedback = document.getElementById("sync-feedback");

        if (feedback.classList.contains("show")) {
            // Запускаем анимацию скрытия
            feedback.classList.remove("show");
            feedback.classList.add("hiding");

            // После завершения анимации полностью скрываем элемент
            setTimeout(() => {
                this._hideImmediately();
            }, 400); // Должно совпадать с duration transition в CSS
        } else {
            this._hideImmediately();
        }

        // Очищаем таймер в любом случае
        if (this.currentTimeout) {
            clearTimeout(this.currentTimeout);
            this.currentTimeout = null;
        }
    },

    /**
     * Немедленно скрывает уведомление без анимации
     * @private
     */
    _hideImmediately() {
        const feedback = document.getElementById("sync-feedback");
        feedback.classList.remove("show", "hiding");
        feedback.textContent = "";
        feedback.className = "sync-feedback";
    },

    /**
     * Показывает уведомление об ошибке
     * @param {string} message - Текст ошибки
     * @param {number} duration - Длительность показа (по умолчанию 6000ms)
     */
    showError(message, duration = 6000) {
        this.show(message, "error", duration);
    },

    /**
     * Показывает уведомление об успешном выполнении
     * @param {string} message - Текст сообщения
     * @param {number} duration - Длительность показа (по умолчанию 5000ms)
     */
    showSuccess(message, duration = 5000) {
        this.show(message, "success", duration);
    },

    /**
     * Показывает информационное уведомление
     * @param {string} message - Текст сообщения
     * @param {number} duration - Длительность показа (по умолчанию 4000ms)
     */
    showInfo(message, duration = 4000) {
        this.show(message, "info", duration);
    },

    /**
     * Показывает уведомление о предупреждении
     * @param {string} message - Текст предупреждения
     * @param {number} duration - Длительность показа (по умолчанию 5000ms)
     */
    showWarning(message, duration = 5000) {
        this.show(message, "info", duration);
    },

    /**
     * Показывает уведомление о блокировке операции
     * @param {string} operationType - Тип операции ('синхронизация', 'обновление сервера', 'обновление стрима')
     * @param {string} targetName - Название цели операции (имя сервера/стрима)
     * @param {number} duration - Длительность показа
     */
    showBlockedOperation(operationType, targetName = "", duration = 5000) {
        let message = this.capitalizeFirst(operationType) + " ";

        if (targetName) {
            message += `"${targetName}" `;
        }

        message += I18n.t("notification.blockedOperation");

        this.show(message, "info", duration);
    },

    /**
     * Показывает уведомление о начале массовой операции
     * @param {string} operationType - Тип массовой операции
     * @param {number} duration - Длительность показа
     */
    showMassOperationStart(operationType, duration = 4000) {
        const message = I18n.t("notification.massOperationStart", {
            operation: operationType,
        });
        this.show(message, "info", duration);
    },

    /**
     * Показывает детализированное уведомление об ошибке синхронизации
     * @param {string} serverName - Имя сервера
     * @param {string} details - Детали ошибки
     * @param {number} duration - Длительность показа
     */
    showSyncError(serverName, details = "", duration = 6000) {
        const message = I18n.t("notification.syncError", {
            target: serverName,
            details: details,
        });
        this.show(message, "error", duration);
    },

    /**
     * Показывает детализированное уведомление об ошибке обновления сервера
     * @param {string} serverName - Имя сервера
     * @param {string} details - Детали ошибки
     * @param {number} duration - Длительность показа
     */
    showServerUpdateError(serverName, details = "", duration = 6000) {
        const message = I18n.t("notification.serverUpdateError", {
            server: serverName,
            details: details,
        });
        this.show(message, "error", duration);
    },

    /**
     * Показывает детализированное уведомление об ошибке обновления стрима
     * @param {string} streamName - Имя стрима
     * @param {string} serverName - Имя сервера
     * @param {string} details - Детали ошибки
     * @param {number} duration - Длительность показа
     */
    showStreamUpdateError(
        streamName,
        serverName = "",
        details = "",
        duration = 6000
    ) {
        const message = I18n.t("notification.streamUpdateError", {
            stream: streamName,
            server: serverName,
            details: details,
        });
        this.show(message, "error", duration);
    },

    /**
     * Показывает уведомление о завершении массовой операции
     * @param {string} operationType - Тип операции
     * @param {number} duration - Длительность показа
     */
    showMassOperationComplete(operationType, duration = 5000) {
        const message = I18n.t("notification.massOperationComplete", {
            operation: operationType,
        });
        this.show(message, "success", duration);
    },

    /**
     * Вспомогательная функция для капитализации первой буквы строки
     * @param {string} string - Входная строка
     * @returns {string} Строка с заглавной первой буквой
     * @private
     */
    capitalizeFirst(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    },
};

// Сделать доступным глобально
window.Notifications = Notifications;
