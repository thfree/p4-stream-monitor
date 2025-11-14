/**
 * static\js\api.js
 * Основной модуль API для взаимодействия с сервером
 * Содержит функции для всех операций: обновление, синхронизация, получение данных
 * Управляет состоянием UI, задержками и обработкой ошибок
 */

// Константы для задержек UI
const UI_DELAY = {
    MIN_OPERATION_DURATION: 800, // Минимальная длительность операции в мс
    SUCCESS_DISPLAY_DURATION: 1200, // Длительность показа успешного состояния
    BUTTON_ANIMATION_DURATION: 500, // Длительность анимации кнопок
};

const DelayHelper = {
    /**
     * Создает задержку для плавности UI
     * @param {number} startTime - Время начала операции (performance.now())
     * @param {number} minDuration - Минимальная длительность операции
     * @returns {Promise<void>}
     */
    async ensureMinDuration(
        startTime,
        minDuration = UI_DELAY.MIN_OPERATION_DURATION
    ) {
        const elapsed = performance.now() - startTime;
        const remaining = minDuration - elapsed;

        if (remaining > 0) {
            await new Promise((resolve) => setTimeout(resolve, remaining));
        }
        return elapsed + (remaining > 0 ? remaining : 0);
    },

    /**
     * Задержка для анимаций UI
     * @param {number} ms - Время задержки в миллисекундах
     * @returns {Promise<void>}
     */
    async forAnimation(ms = UI_DELAY.BUTTON_ANIMATION_DURATION) {
        await new Promise((resolve) => setTimeout(resolve, ms));
    },
};

// Утилиты для работы с DOM элементами
const DOM = {
    /**
     * Устанавливает состояние загрузки для элемента и связанной кнопки
     * @param {string} elementId - ID элемента (без префикса)
     * @param {string|null} buttonId - ID кнопки (опционально)
     */
    setLoading(elementId, buttonId = null) {
        if (buttonId) {
            const btn = document.getElementById(buttonId);
            if (btn) {
                btn.disabled = true;

                // Специфичная логика для разных типов кнопок
                if (buttonId === "btn-sync") {
                    btn.innerHTML = I18n.t("notification.loading");
                    btn.classList.add("loading");
                } else if (buttonId.startsWith("btn-list")) {
                    btn.innerHTML = "⏳";
                } else if (buttonId.startsWith("btn-sync-streams")) {
                    btn.innerHTML = "⏳";
                } else {
                    btn.innerHTML = "⏳";
                }
            }
        }
        this.setStatus(elementId, I18n.t("notification.loading"), "loading");
    },

    /**
     * Устанавливает состояние успешного завершения операции
     * @param {string} elementId - ID элемента
     * @param {string|null} buttonId - ID кнопки (опционально)
     */
    setSuccess(elementId, buttonId = null) {
        if (buttonId) {
            this.resetButton(buttonId);
            // Специальная обработка для кнопки синхронизации
            if (buttonId === "btn-sync") {
                const btn = document.getElementById(buttonId);
                btn.classList.add("success");
                setTimeout(() => btn.classList.remove("success"), 2000);
            }
        }
        this.setStatus(elementId, I18n.t("notification.success"), "success");
        setTimeout(() => this.clearStatus(elementId), 3000);
    },

    /**
     * Устанавливает состояние ошибки для элемента и кнопки
     * @param {string} elementId - ID элемента
     * @param {string|null} buttonId - ID кнопки (опционально)
     */
    setError(elementId, buttonId = null) {
        if (buttonId) {
            this.resetButton(buttonId);
            if (buttonId === "btn-sync") {
                const btn = document.getElementById(buttonId);
                btn.classList.add("error");
                setTimeout(() => btn.classList.remove("error"), 3000);
            }
        }
        this.setStatus(elementId, I18n.t("notification.error"), "error");
        setTimeout(() => this.clearStatus(elementId), 5000);
    },

    /**
     * Устанавливает текстовый статус для элемента
     * @param {string} elementId - ID элемента
     * @param {string} text - Текст статуса
     * @param {string} type - Тип статуса (loading/success/error)
     */
    setStatus(elementId, text, type) {
        const status = document.getElementById(`status-${elementId}`);
        if (status) {
            status.textContent = text;
            status.className = `status status-${type}`;
        }
    },

    /**
     * Очищает статус элемента
     * @param {string} elementId - ID элемента
     */
    clearStatus(elementId) {
        const status = document.getElementById(`status-${elementId}`);
        if (status) {
            status.textContent = "";
            status.className = "status";
        }
    },

    /**
     * Сбрасывает кнопку в исходное состояние
     * @param {string} buttonId - ID кнопки
     */
    resetButton(buttonId) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = false;

            // Восстанавливаем оригинальный текст в зависимости от типа кнопки
            if (buttonId === "btn-sync") {
                button.innerHTML = I18n.t("btn.syncConfig");
                button.classList.remove("loading", "success", "error");
            } else if (buttonId.startsWith("btn-list")) {
                button.innerHTML = I18n.t("server.listStreams");
            } else if (buttonId.startsWith("btn-sync-streams")) {
                button.innerHTML = I18n.t("server.syncStreams");
            } else if (buttonId.startsWith("btn-stream")) {
                button.innerHTML = "🔄";
            } else if (buttonId.startsWith("btn-server")) {
                button.innerHTML = I18n.t("server.updateWithSizes");
            }
        }
    },

    /**
     * Обновляет временную метку элемента текущим временем
     * @param {string} streamId - ID стрима
     */
    updateTimestamp(streamId) {
        const now = new Date();
        const timestamp = now.toLocaleString("ru-RU", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
        const element = document.getElementById(`timestamp-${streamId}`);
        if (element) {
            element.textContent = I18n.t("stream.updated") + `: ${timestamp}`;
        }
    },

    /**
     * Обновляет отображаемый размер стрима
     * @param {string} streamId - ID стрима
     * @param {string} sizeHuman - Размер в читаемом формате
     */
    updateSize: function (streamId, sizeHuman) {
        const element = document.getElementById(`size-${streamId}`);
        if (element) {
            element.textContent = sizeHuman;
        }
    },

    /**
     * Обновляет отображаемое количество файлов стрима
     * @param {string} streamId - ID стрима
     * @param {number} fileCount - Количество файлов
     */
    updateFileCount: function (streamId, fileCount) {
        const streamElement = document.getElementById(`stream-${streamId}`);
        if (!streamElement) {
            return;
        }

        let element = document.getElementById(`file-count-${streamId}`);
        const formattedExactCount = fileCount.toLocaleString();
        const formattedCount = Utils.formatLargeNumber(fileCount);

        if (!element) {
            const streamInfo = streamElement.querySelector(".stream-info");
            if (streamInfo) {
                element = document.createElement("span");
                element.className = "file-count";
                element.id = `file-count-${streamId}`;
                element.setAttribute(
                    "data-original-count",
                    fileCount.toString()
                );
                element.title = formattedExactCount;

                const timestamp = streamInfo.querySelector(".timestamp");
                if (timestamp) {
                    streamInfo.insertBefore(element, timestamp);
                } else {
                    streamInfo.appendChild(element);
                }
            }
        }

        if (element) {
            const filesText = I18n.t("stream.files");
            element.innerHTML = `• ${formattedCount} ${filesText}`;
            element.title = formattedExactCount;
            element.setAttribute("data-original-count", fileCount.toString());
        }
    },
};

// Управление модальными окнами
const Modal = {
    currentServerId: null, // ID сервера, для которого открыто модальное окно
    escapeHandler: null,
    modalClickHandler: null,

    /**
     * Открывает модальное окно со списком стримов
     */
    openStreamsModal() {
        const modal = document.getElementById("streams-modal");
        modal.style.display = "flex";

        // Блокируем прокрутку body через класс
        document.body.classList.add("modal-open");
        this.currentServerId = Modal.currentServerId;

        // Добавляем обработчики
        this._addModalHandlers();
    },

    /**
     * Закрывает модальное окно со списком стримов
     */
    closeStreamsModal() {
        const modal = document.getElementById("streams-modal");
        modal.style.display = "none";
        this.currentServerId = null;

        // Восстанавливаем прокрутку body
        document.body.classList.remove("modal-open");

        // Удаляем обработчики
        this._removeModalHandlers();
    },

    /**
     * Добавляет обработчики для модального окна
     * @private
     */
    _addModalHandlers() {
        // Обработчик клавиши Escape
        this._addEscapeHandler();

        // Обработчик клика вне области модального окна
        this._addOutsideClickHandler();
    },

    /**
     * Удаляет обработчики модального окна
     * @private
     */
    _removeModalHandlers() {
        this._removeEscapeHandler();
        this._removeOutsideClickHandler();
    },

    /**
     * Добавляет обработчик клавиши Escape для закрытия модального окна
     * @private
     */
    _addEscapeHandler() {
        this.escapeHandler = (event) => {
            if (event.key === "Escape") {
                console.log("[Modal] Escape pressed, closing modal");
                this.closeStreamsModal();
            }
        };
        document.addEventListener("keydown", this.escapeHandler);
    },

    /**
     * Удаляет обработчик клавиши Escape
     * @private
     */
    _removeEscapeHandler() {
        if (this.escapeHandler) {
            document.removeEventListener("keydown", this.escapeHandler);
            this.escapeHandler = null;
        }
    },

    /**
     * Добавляет обработчик клика вне области модального окна
     * @private
     */
    _addOutsideClickHandler() {
        this.modalClickHandler = (event) => {
            const modal = document.getElementById("streams-modal");
            // Закрываем только если кликнули на фон (сам modal, а не его содержимое)
            if (event.target === modal) {
                console.log("[Modal] Outside click detected, closing modal");
                this.closeStreamsModal();
            }
        };

        const modal = document.getElementById("streams-modal");
        if (modal) {
            modal.addEventListener("click", this.modalClickHandler);
        }
    },

    /**
     * Удаляет обработчик клика вне области модального окна
     * @private
     */
    _removeOutsideClickHandler() {
        const modal = document.getElementById("streams-modal");
        if (modal && this.modalClickHandler) {
            modal.removeEventListener("click", this.modalClickHandler);
            this.modalClickHandler = null;
        }
    },
};

// Основные API функции для взаимодействия с сервером
const API = {
    /**
     * Синхронизирует список серверов с конфигурационным файлом
     * @returns {Promise<void>}
     */
    async syncServers() {
        const startTime = performance.now();

        // Проверяем, не выполняется ли уже другая операция
        if (!AppGlobal.isReadyForOperation()) {
            Notifications.showBlockedOperation(
                I18n.t("notification.syncOperation")
            );
            return;
        }

        AppGlobal.setOperationState(true);
        DOM.setLoading("sync", "btn-sync");
        Notifications.showInfo(I18n.t("notification.syncServersInProgress"), 0);

        try {
            const response = await fetch("/api/admin/sync-servers", {
                method: "POST",
            });
            const data = await response.json();

            // Добавляем минимальную задержку для плавности
            await DelayHelper.ensureMinDuration(startTime);

            if (response.ok && data.status === "success") {
                DOM.setSuccess("sync", "btn-sync");
                Notifications.showSuccess(data.message, 5000);

                // Планируем обновление интерфейса после успешной синхронизации
                setTimeout(() => {
                    Notifications.showInfo(
                        I18n.t("notification.updatingInterface"),
                        2000
                    );
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                }, 2000);
            } else {
                throw new Error(
                    data.message || I18n.t("notification.unknownError")
                );
            }
        } catch (error) {
            console.error("[API] Критическая ошибка при синхронизации:", error);
            DOM.setError("sync", "btn-sync");
            Notifications.showSyncError(
                I18n.t("notification.config"),
                error.message,
                6000
            );
        } finally {
            AppGlobal.setOperationState(false);
        }
    },

    /**
     * Обновляет все стримы на всех серверах
     * @returns {Promise<void>}
     */
    async updateAll() {
        if (!AppGlobal.isReadyForOperation()) {
            return;
        }

        AppGlobal.setOperationState(true);
        const button = document.getElementById("btn-all");

        // Сворачиваем все серверы для лучшего обзора
        ServerToggler.collapseAllServers();

        // Обновляем состояние кнопки
        button.disabled = true;
        button.classList.add("updating");
        button.innerHTML = I18n.t("notification.updatingAllStreams");

        // Помечаем все серверы как обновляемые
        this.markAllServersAsUpdating();

        Notifications.showMassOperationStart(
            I18n.t("notification.updateAllStreams"),
            3000
        );

        try {
            const response = await fetch("/api/update/all", { method: "POST" });

            if (response.ok) {
                // Помечаем все стримы как обновляемые
                const streams = document.querySelectorAll(".stream");

                streams.forEach((stream) => {
                    const streamId = stream.id.replace("stream-", "");
                    DOM.setLoading(streamId, `btn-stream-${streamId}`);
                });

                Notifications.showSuccess(
                    I18n.t("notification.massUpdateStarted"),
                    3000
                );

                setTimeout(() => {
                    location.reload();
                }, 3000);
            } else {
                throw new Error(I18n.t("notification.serverError"));
            }
        } catch (error) {
            console.error(
                "[API] Ошибка при массовом обновлении стримов:",
                error
            );
            Notifications.showError(
                I18n.t("notification.updateAllError"),
                5000
            );

            // Сбрасываем состояние при ошибке
            this.unmarkAllServersAsUpdating();
            button.disabled = false;
            button.classList.remove("updating");
            button.innerHTML = I18n.t("btn.refreshAll");
            AppGlobal.setOperationState(false);
        }
    },

    /**
     * Помечает все серверы как обновляемые
     */
    markAllServersAsUpdating() {
        const servers = document.querySelectorAll(".server");
        servers.forEach((server) => {
            server.classList.add("updating");

            // Добавляем бейдж обновления к заголовку
            const serverTitle = server.querySelector(".server-title");
            if (serverTitle && !serverTitle.querySelector(".updating-badge")) {
                const badge = document.createElement("span");
                badge.className = "updating-badge";
                badge.textContent = I18n.t("notification.updating");
                serverTitle.appendChild(badge);
            }
        });
    },

    /**
     * Снимает пометку обновления со всех серверов
     */
    unmarkAllServersAsUpdating() {
        const servers = document.querySelectorAll(".server");
        servers.forEach((server) => {
            const serverId = server.id.replace("server-", "");
            this.unmarkServerAsUpdating(serverId);
        });
    },

    /**
     * Обновляет сервер с расчетом размеров всех стримов
     * @param {number} serverId - ID сервера
     * @returns {Promise<void>}
     */
    async updateServerWithSizes(serverId) {
        if (!AppGlobal.isReadyForOperation()) {
            const serverElement = document.getElementById(`server-${serverId}`);
            const serverName =
                serverElement?.dataset.serverName ||
                I18n.t("notification.server") + ` ${serverId}`;
            Notifications.showBlockedOperation(
                I18n.t("notification.serverUpdate"),
                serverName
            );
            return;
        }

        AppGlobal.setOperationState(true);
        const buttonId = `btn-server-${serverId}`;
        const serverElement = document.getElementById(`server-${serverId}`);
        const serverName =
            serverElement?.dataset.serverName ||
            I18n.t("notification.server") + ` ${serverId}`;

        // Помечаем сервер как обновляемый (индивидуальный стиль)
        this.markServerAsUpdating(serverId, "individual");

        Notifications.showInfo(
            I18n.t("notification.updatingServerWithSizes", {
                server: serverName,
            }),
            2000
        );

        // Сворачиваем сервер во время обновления
        ServerToggler.collapseServer(serverId);

        // Помечаем все стримы сервера как обновляемые
        const serverStreams = serverElement.querySelectorAll(".stream");

        serverStreams.forEach((stream) => {
            const streamId = stream.id.replace("stream-", "");
            DOM.setLoading(streamId, `btn-stream-${streamId}`);
        });

        try {
            const response = await fetch(`/api/update/server/${serverId}`, {
                method: "POST",
            });
            const data = await response.json();

            if (response.ok && data.success) {
                // Снимаем пометку обновления
                this.unmarkServerAsUpdating(serverId);

                Notifications.showSuccess(
                    I18n.t("notification.serverUpdated", {
                        server: serverName,
                        added: data.added,
                        updated: data.updated,
                        removed: data.removed,
                    }),
                    3000
                );

                // Перезагружаем страницу для отображения актуальных данных
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                throw new Error(
                    data.error || I18n.t("notification.serverError")
                );
            }
        } catch (error) {
            console.error(
                `[API] Ошибка при обновлении сервера ${serverId}:`,
                error
            );

            // Снимаем пометку обновления при ошибке
            this.unmarkServerAsUpdating(serverId);
            DOM.setError(`server-${serverId}`, buttonId);
            Notifications.showServerUpdateError(
                serverName,
                error.message,
                4000
            );
            AppGlobal.setOperationState(false);
        }
    },

    /**
     * Помечает сервер как обновляемый
     * @param {number} serverId - ID сервера
     * @param {string} type - Тип обновления ('mass' или 'individual')
     */
    markServerAsUpdating(serverId, type = "mass") {
        const server = document.getElementById(`server-${serverId}`);
        if (server) {
            const styleClass =
                type === "mass" ? "updating" : "individual-updating";
            const badgeText =
                type === "mass"
                    ? I18n.t("notification.massUpdate")
                    : I18n.t("notification.updating");

            server.classList.add(styleClass);

            // Добавляем бейдж обновления к заголовку
            const serverTitle = server.querySelector(".server-title");
            if (serverTitle && !serverTitle.querySelector(".updating-badge")) {
                const badge = document.createElement("span");
                badge.className = "updating-badge";
                badge.textContent = badgeText;
                serverTitle.appendChild(badge);
            }

            // Добавляем анимацию для иконки
            const toggleIcon = server.querySelector(".toggle-icon");
            if (toggleIcon) {
                if (type === "mass") {
                    toggleIcon.style.animation = "spin 1.5s linear infinite";
                } else {
                    toggleIcon.style.animation = "spin 1.5s linear infinite";
                }
            }
        }
    },

    /**
     * Снимает пометку обновления с сервера
     * @param {number} serverId - ID сервера
     */
    unmarkServerAsUpdating(serverId) {
        const server = document.getElementById(`server-${serverId}`);
        if (server) {
            server.classList.remove("updating", "individual-updating");

            // Удаляем бейдж обновления
            const badge = server.querySelector(".updating-badge");
            if (badge) {
                badge.remove();
            }

            // Убираем анимацию с иконки
            const toggleIcon = server.querySelector(".toggle-icon");
            if (toggleIcon) {
                toggleIcon.style.animation = "";
            }
        }
    },

    /**
     * Получает список стримов для указанного сервера
     * @param {number} serverId - ID сервера
     * @returns {Promise<void>}
     */
    async getServerStreams(serverId) {
        const buttonId = `btn-list-${serverId}`;
        DOM.setLoading("list", buttonId);

        try {
            const response = await fetch(`/api/server/${serverId}/streams`);
            const data = await response.json();

            if (response.ok && data.success) {
                Modal.currentServerId = serverId;

                // Обновляем заголовок модального окна
                document.getElementById("modal-title").textContent = I18n.t(
                    "modal.streamsTitle",
                    {
                        server: data.server,
                        count: data.count,
                    }
                );

                // Заполняем список стримов
                const streamList = document.getElementById("stream-list");
                streamList.innerHTML = data.streams
                    .map((stream) => `<div class="stream-item">${stream}</div>`)
                    .join("");

                Modal.openStreamsModal();
                DOM.setSuccess("list", buttonId);
            } else {
                throw new Error(
                    data.error || I18n.t("notification.getStreamsError")
                );
            }
        } catch (error) {
            console.error(
                `[API] Ошибка при получении стримов сервера ${serverId}:`,
                error
            );
            DOM.setError("list", buttonId);
            Notifications.showError(`${error.message}`, 4000);
        }
    },

    /**
     * Синхронизирует стримы из модального окна
     * @returns {Promise<void>}
     */
    async syncFromModal() {
        if (!Modal.currentServerId) {
            return;
        }

        if (!AppGlobal.isReadyForOperation()) {
            return;
        }

        const startTime = performance.now();

        const modalButton = document.getElementById("modal-sync-btn");
        modalButton.disabled = true;
        modalButton.innerHTML = I18n.t("notification.syncing");

        try {
            const response = await fetch(
                `/api/update/server/${Modal.currentServerId}/sync-streams`,
                {
                    method: "POST",
                }
            );
            const data = await response.json();

            // Добавляем минимальную задержку
            await DelayHelper.ensureMinDuration(startTime);

            if (response.ok && data.success) {
                Notifications.showSuccess(
                    I18n.t("notification.syncCompleted", {
                        added: data.added,
                        removed: data.removed,
                    }),
                    4000
                );
                Modal.closeStreamsModal();

                setTimeout(() => {
                    location.reload();
                }, UI_DELAY.SUCCESS_DISPLAY_DURATION);
            } else {
                throw new Error(data.error || I18n.t("notification.syncError"));
            }
        } catch (error) {
            console.error(
                "[API] Ошибка при синхронизации стримов из модального окна:",
                error
            );
            Notifications.showError(
                I18n.t("notification.syncError") + `: ${error.message}`,
                4000
            );
            modalButton.disabled = false;
            modalButton.innerHTML = I18n.t("modal.sync");
        }
    },

    /**
     * Синхронизирует стримы для указанного сервера
     * @param {number} serverId - ID сервера
     * @returns {Promise<void>}
     */
    async syncServerStreams(serverId) {
        const startTime = performance.now();

        if (!AppGlobal.isReadyForOperation()) {
            const serverElement = document.getElementById(`server-${serverId}`);
            const serverName =
                serverElement?.dataset.serverName ||
                I18n.t("notification.server") + ` ${serverId}`;
            Notifications.showBlockedOperation(
                I18n.t("notification.streamSync"),
                serverName
            );
            return;
        }

        AppGlobal.setOperationState(true);
        const buttonId = `btn-sync-streams-${serverId}`;
        const serverElement = document.getElementById(`server-${serverId}`);
        const serverName =
            serverElement?.dataset.serverName ||
            I18n.t("notification.server") + ` ${serverId}`;

        DOM.setLoading(`sync-streams-${serverId}`, buttonId);
        Notifications.showInfo(
            I18n.t("notification.syncingServerStreams", { server: serverName }),
            2000
        );

        try {
            const response = await fetch(
                `/api/update/server/${serverId}/sync-streams`,
                {
                    method: "POST",
                }
            );
            const data = await response.json();

            // Добавляем минимальную задержку
            await DelayHelper.ensureMinDuration(startTime);

            if (response.ok && data.success) {
                DOM.setSuccess(`sync-streams-${serverId}`, buttonId);
                Notifications.showSuccess(
                    I18n.t("notification.serverStreamsSynced", {
                        server: serverName,
                        added: data.added,
                        removed: data.removed,
                    }),
                    4000
                );

                setTimeout(() => {
                    location.reload();
                }, UI_DELAY.SUCCESS_DISPLAY_DURATION);
            } else {
                throw new Error(data.error || I18n.t("notification.syncError"));
            }
        } catch (error) {
            console.error(
                `[API] Ошибка при синхронизации стримов сервера ${serverId}:`,
                error
            );
            DOM.setError(`sync-streams-${serverId}`, buttonId);
            Notifications.showSyncError(serverName, error.message, 4000);
            AppGlobal.setOperationState(false);
        }
    },

    /**
     * Обновляет отдельный стрим
     * @param {number} streamId - ID стрима
     * @returns {Promise<void>}
     */
    async updateStream(streamId) {
        const startTime = performance.now();

        if (!AppGlobal.isReadyForOperation()) {
            const streamElement = document.getElementById(`stream-${streamId}`);
            const streamName =
                streamElement?.querySelector(".stream-name")?.textContent ||
                I18n.t("notification.stream") + ` ${streamId}`;
            const serverElement = streamElement?.closest(".server");
            const serverName =
                serverElement?.dataset.serverName ||
                I18n.t("notification.unknownServer");

            Notifications.showBlockedOperation(
                I18n.t("notification.streamUpdate"),
                `${streamName} (${serverName})`
            );
            return;
        }

        AppGlobal.setOperationState(true);
        const buttonId = `btn-stream-${streamId}`;
        const streamElement = document.getElementById(`stream-${streamId}`);
        const streamName =
            streamElement?.querySelector(".stream-name")?.textContent ||
            I18n.t("notification.stream") + ` ${streamId}`;
        const serverElement = streamElement?.closest(".server");
        const serverName =
            serverElement?.dataset.serverName ||
            I18n.t("notification.unknownServer");

        DOM.setLoading(streamId, buttonId);
        Notifications.showInfo(
            I18n.t("notification.updatingStream", { stream: streamName }),
            2000
        );

        if (streamElement) {
            streamElement.style.backgroundColor = "#fffbf0";
        }

        try {
            const response = await fetch(`/api/update/stream/${streamId}`, {
                method: "POST",
            });
            const data = await response.json();

            // Добавляем минимальную задержку для быстрых операций
            await DelayHelper.ensureMinDuration(startTime);

            if (response.ok && data.success && data.human) {
                let displaySize;
                if (data.size_bytes !== undefined && data.size_bytes !== null) {
                    // Используем единый формат через утилиту
                    displaySize = Utils.formatFileSize(data.size_bytes, false);
                }

                DOM.updateSize(streamId, displaySize);
                DOM.updateTimestamp(streamId);

                // Обновляем количество файлов если оно есть в ответе
                if (data.file_count !== undefined && data.file_count !== null) {
                    DOM.updateFileCount(streamId, data.file_count);
                }

                DOM.setSuccess(streamId, buttonId);
                Notifications.showSuccess(
                    I18n.t("notification.streamSizeUpdated", {
                        stream: streamName,
                        size: displaySize, // Используем унифицированный размер
                    }),
                    3000
                );
            } else {
                throw new Error(
                    data.error || I18n.t("notification.updateError")
                );
            }
        } catch (error) {
            console.error(
                `[API] Ошибка при обновлении стрима ${streamId}:`,
                error
            );
            DOM.setError(streamId, buttonId);
            Notifications.showStreamUpdateError(
                streamName,
                serverName,
                error.message,
                4000
            );
        } finally {
            // Восстанавливаем нормальный фон стрима
            if (streamElement) {
                streamElement.style.backgroundColor = "";
            }
            AppGlobal.setOperationState(false);
        }
    },
};

// Сделать доступным глобально
window.API = API;
