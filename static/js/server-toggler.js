/**
 * static\js\server-toggler.js
 * Управление сворачиванием/разворачиванием серверов в интерфейсе
 * Обеспечивает функциональность аккордеона для серверов
 * Сохраняет состояние серверов и обновляет кнопки управления
 */

const ServerToggler = {
    /**
     * Переключает состояние отдельного сервера (свернуть/развернуть)
     * @param {string} serverId - ID сервера
     */
    toggleServer(serverId) {
        const server = document.getElementById(`server-${serverId}`);

        if (!server) {
            console.error(`[ServerToggler] Сервер с ID ${serverId} не найден`);
            return;
        }

        const isCollapsed = server.classList.contains("collapsed");

        if (isCollapsed) {
            this.expandServer(serverId);
        } else {
            this.collapseServer(serverId);
        }

        AppState.serversState[serverId] = !isCollapsed;
        // Обновляем кнопку "все свернуть/развернуть"
        this.updateToggleAllButton();
    },

    /**
     * Сворачивает указанный сервер
     * @param {string} serverId - ID сервера
     */
    collapseServer(serverId) {
        const server = document.getElementById(`server-${serverId}`);
        if (server) {
            server.classList.add("collapsed");
            AppState.serversState[serverId] = true;
            this.updateToggleAllButton();
        } else {
            console.error(
                `[ServerToggler] Не удалось свернуть сервер ${serverId}: элемент не найден`
            );
        }
    },

    /**
     * Разворачивает указанный сервер
     * @param {string} serverId - ID сервера
     */
    expandServer(serverId) {
        const server = document.getElementById(`server-${serverId}`);
        if (server) {
            server.classList.remove("collapsed");
            AppState.serversState[serverId] = false;

            // Обновляем подсказки прокрутки после анимации
            setTimeout(() => {
                if (window.AppGlobal && window.AppGlobal.updateScrollHints) {
                    window.AppGlobal.updateScrollHints();
                }
            }, 350);

            this.updateToggleAllButton();
        } else {
            console.error(
                `[ServerToggler] Не удалось развернуть сервер ${serverId}: элемент не найден`
            );
        }
    },

    /**
     * Переключает состояние всех серверов одновременно
     * Сворачивает все, если хотя бы один развернут, и наоборот
     */
    toggleAllServers() {
        const allCollapsed = Object.values(AppState.serversState).every(
            (state) => state
        );
        const newState = !allCollapsed;

        Object.keys(AppState.serversState).forEach((serverId) => {
            const server = document.getElementById(`server-${serverId}`);
            if (newState) {
                server.classList.add("collapsed");
            } else {
                server.classList.remove("collapsed");
            }
            AppState.serversState[serverId] = newState;
        });

        this.updateToggleAllButton();
    },

    /**
     * Обновляет текст кнопки "все свернуть/развернуть" в зависимости от текущего состояния
     */
    updateToggleAllButton() {
        const button = document.getElementById("btn-toggle-all");
        if (!button) {
            console.warn('[ServerToggler] Кнопка "btn-toggle-all" не найдена');
            return;
        }

        const servers = document.querySelectorAll(".server");
        if (servers.length === 0) {
            return;
        }

        const allCollapsed = Array.from(servers).every((server) =>
            server.classList.contains("collapsed")
        );

        // Используем систему i18n для перевода
        if (allCollapsed) {
            button.innerHTML = I18n.t("btn.toggleAllExpanded");
        } else {
            button.innerHTML = I18n.t("btn.toggleAll");
        }

        // Обновляем title атрибут
        button.title = allCollapsed
            ? I18n.t("server.expandAll")
            : I18n.t("server.collapseAll");
    },

    /**
     * Возвращает количество свернутых серверов
     * @returns {number} Количество свернутых серверов
     */
    getCollapsedCount() {
        const count = Object.values(AppState.serversState).filter(
            (state) => state
        ).length;
        return count;
    },

    /**
     * Возвращает общее количество серверов
     * @returns {number} Общее количество серверов
     */
    getTotalCount() {
        const count = Object.keys(AppState.serversState).length;
        return count;
    },

    /**
     * Восстанавливает состояние серверов из глобального состояния
     */
    restoreState() {
        Object.entries(AppState.serversState).forEach(
            ([serverId, isCollapsed]) => {
                const server = document.getElementById(`server-${serverId}`);
                if (server) {
                    if (isCollapsed) {
                        server.classList.add("collapsed");
                    } else {
                        server.classList.remove("collapsed");
                    }
                }
            }
        );

        this.updateToggleAllButton();
    },

    /**
     * Сворачивает все серверы
     */
    collapseAllServers() {
        Object.keys(AppState.serversState).forEach((serverId) => {
            const server = document.getElementById(`server-${serverId}`);
            if (server) {
                server.classList.add("collapsed");
                AppState.serversState[serverId] = true;
            }
        });

        this.updateToggleAllButton();
    },
};

// Сделать доступным глобально
window.ServerToggler = ServerToggler;
