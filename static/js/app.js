/**
 * static\js\app.js
 * Основной файл инициализации приложения Perforce Stream Monitor
 * Управляет глобальным состоянием, инициализацией компонентов и обработчиками событий
 * Координирует работу всех модулей приложения
 */

const AppState = {
    /**
     * Флаг выполнения операции для предотвращения конфликтов
     * true - операция выполняется, новые операции блокируются
     * false - система готова к новым операциям
     */
    updateInProgress: false,

    /**
     * Состояние свернутости/развернутости серверов
     * Ключ: serverId, Значение: boolean (true = свернут, false = развернут)
     */
    serversState: {},
};

/**
 * Настраивает обработчик смены языка
 */
function setupLanguageChangeHandler() {
    document.addEventListener("languageChanged", (event) => {
        const { oldLang, newLang } = event.detail;

        // Показываем уведомление о смене языка
        Notifications.showInfo(
            I18n.t("notification.languageChanged", {
                language: I18n.t(`language.${newLang}`),
            }),
            2000
        );
        updateInterfaceAfterLanguageChange();
    });
}

const AppGlobal = {
    /**
     * Форматирует числа файлов при начальной загрузке страницы
     */
    formatInitialFileCounts: function () {
        const fileCountElements = document.querySelectorAll(
            ".file-count[data-exact-count]"
        );

        fileCountElements.forEach((element) => {
            const exactCount = element.getAttribute("data-exact-count");

            // Убираем разделители тысяч и преобразуем в число
            const numericCount = parseInt(exactCount.replace(/,/g, ""));

            if (!isNaN(numericCount)) {
                const formattedCount = Utils.formatLargeNumber(numericCount);
                const formattedExactCount = numericCount.toLocaleString();
                const filesText = I18n.t("stream.files");

                // Обновляем содержимое
                element.innerHTML = `• ${formattedCount} ${filesText}`;
                element.title = formattedExactCount;
                element.setAttribute(
                    "data-original-count",
                    numericCount.toString()
                );
            }
        });
    },

    /**
     * Проверяет необходимость показа подсказки о прокрутке для каждого сервера
     */
    updateScrollHints: function () {
        const servers = document.querySelectorAll(
            ".server:not(.hidden-by-search)"
        );
        let updatedCount = 0;

        servers.forEach((server) => {
            const streamsContainer = server.querySelector(".streams-container");
            const scrollHint = server.querySelector(".scroll-hint");

            if (!streamsContainer || !scrollHint) return;

            // Проверяем только развернутые серверы
            if (!server.classList.contains("collapsed")) {
                // Проверяем, нужна ли прокрутка (добавляем небольшой запас в 5px)
                const needsScroll =
                    streamsContainer.scrollHeight >
                    streamsContainer.clientHeight + 5;

                if (needsScroll) {
                    scrollHint.style.display = "inline";
                    updatedCount++;
                } else {
                    scrollHint.style.display = "none";
                }
            } else {
                // Для свернутых серверов скрываем подсказку
                scrollHint.style.display = "none";
            }
        });
    },

    /**
     * Проверяет, готово ли приложение к выполнению новой операции
     * @returns {boolean} true если можно выполнять новую операцию, false если выполняется другая операция
     */
    isReadyForOperation: function () {
        if (AppState.updateInProgress) {
            if (window.Notifications) {
                Notifications.showInfo(
                    "Система занята выполнением другой операции. Дождитесь завершения.",
                    3000
                );
            }
            return false;
        }
        return true;
    },

    /**
     * Устанавливает состояние выполнения операции
     * @param {boolean} state - true если операция начинается, false если завершается
     */
    setOperationState: function (state) {
        AppState.updateInProgress = state;

        // Визуальная индикация состояния приложения
        if (state) {
            document.body.style.cursor = "wait";
        } else {
            document.body.style.cursor = "";
        }
    },
};

function updateInterfaceAfterLanguageChange() {
    // Обновляем кнопки управления
    if (window.ServerToggler && ServerToggler.updateToggleAllButton) {
        ServerToggler.updateToggleAllButton();
    }

    // Обновляем поиск
    const searchInput = document.getElementById("stream-search");
    if (searchInput && searchInput.value && window.StreamSearch) {
        StreamSearch.performSearch(searchInput.value);
    }

    // Обновляем подсказки прокрутки
    if (AppGlobal.updateScrollHints) {
        AppGlobal.updateScrollHints();
    }

    // Обновляем количество файлов при смене языка
    if (AppGlobal.formatInitialFileCounts) {
        AppGlobal.formatInitialFileCounts();
    }

    // Обновляем модальное окно статистики если оно открыто
    const statsModal = document.getElementById("stats-modal");
    if (statsModal && statsModal.style.display === "flex") {
        if (window.I18n && I18n.updateStatsModal) {
            I18n.updateStatsModal();
        }

        // Перерисовываем график с новыми подписями
        if (window.StreamStats && StreamStats.chart) {
            setTimeout(() => {
                StreamStats.loadStatsData();
            }, 100);
        }
    }
}

/**
 * Определяет серверы с большим количеством стримов и добавляет визуальные индикаторы
 */
function markServersWithManyStreams() {
    const servers = document.querySelectorAll(".server");
    const MANY_STREAMS_THRESHOLD = 15;

    servers.forEach((server) => {
        const streamsCount = parseInt(server.dataset.streamsCount) || 0;

        if (streamsCount > MANY_STREAMS_THRESHOLD) {
            server.classList.add("has-many-streams");
        }
    });
}

/**
 * Инициализирует состояние серверов на основе данных в DOM
 */
function initializeServersState() {
    const servers = document.querySelectorAll(".server");

    servers.forEach((server) => {
        const serverId = server.dataset.serverId;
        const isCollapsed = server.classList.contains("collapsed");

        AppState.serversState[serverId] = isCollapsed;
    });
}

/**
 * Настраивает глобальные обработчики событий для приложения
 */
function setupEventListeners() {
    // Обработчики для заголовков серверов (сворачивание/разворачивание)
    const serverHeaders = document.querySelectorAll(".server-header");
    serverHeaders.forEach((header) => {
        header.addEventListener("click", function (event) {
            if (!event.target.closest("button")) {
                const serverElement = header.closest(".server");
                const serverId = serverElement.dataset.serverId;
                if (window.ServerToggler) {
                    ServerToggler.toggleServer(serverId);
                }
            }
        });
    });

    // Основные кнопки управления
    document.getElementById("btn-toggle-all")?.addEventListener("click", () => {
        if (window.ServerToggler) {
            ServerToggler.toggleAllServers();
        }
    });

    document.getElementById("btn-sync")?.addEventListener("click", () => {
        if (window.API) {
            API.syncServers();
        }
    });

    document.getElementById("btn-all")?.addEventListener("click", () => {
        if (window.API) {
            API.updateAll();
        }
    });

    // Модальное окно списка стримов
    document
        .getElementById("modal-close-btn")
        ?.addEventListener("click", () => {
            if (window.Modal) {
                Modal.closeStreamsModal();
            }
        });

    // Закрытие модального окна статистики по кнопке
    document
        .getElementById("stats-close-btn")
        ?.addEventListener("click", () => {
            if (window.StreamStats) {
                StreamStats.closeStatsModal();
            }
        });

    // Кнопка прокрутки вверх
    document.getElementById("scrollToTop")?.addEventListener("click", () => {
        if (window.ScrollHelper) {
            ScrollHelper.scrollToTop();
        }
    });

    // Обработчики для кнопок серверов
    document.addEventListener("click", function (event) {
        const target = event.target;

        // Обработка кнопок серверов
        if (
            target.matches(".server-controls button, .server-controls button *")
        ) {
            event.stopPropagation();
            const button = target.closest("button");

            if (button.id.startsWith("btn-list-")) {
                const serverId = button.id.replace("btn-list-", "");
                if (window.API) {
                    API.getServerStreams(parseInt(serverId));
                }
            } else if (button.id.startsWith("btn-sync-streams-")) {
                const serverId = button.id.replace("btn-sync-streams-", "");
                if (window.API) {
                    API.syncServerStreams(parseInt(serverId));
                }
            } else if (button.id.startsWith("btn-server-")) {
                const serverId = button.id.replace("btn-server-", "");
                if (window.API) {
                    API.updateServerWithSizes(parseInt(serverId));
                }
            }
        }

        // Закрытие модального окна по клику вне его области
        const modal = document.getElementById("streams-modal");
        if (event.target === modal) {
            Modal.closeStreamsModal();
        }

        // Закрытие уведомления по клику на него
        const notification = document.getElementById("sync-feedback");
        if (
            event.target === notification ||
            (notification && notification.contains(event.target))
        ) {
            Notifications.hide();
        }
    });

    // Обработчики для кнопок стримов
    document.addEventListener("click", function (event) {
        if (event.target.matches(".stream button, .stream button *")) {
            const button = event.target.closest("button");

            // Обработка кнопки обновления стрима
            if (button && button.id.startsWith("btn-stream-")) {
                const streamId = button.id.replace("btn-stream-", "");
                if (window.API) {
                    API.updateStream(parseInt(streamId));
                }
            }

            // Обработка кнопки статистики стрима
            else if (button && button.id.startsWith("btn-stats-")) {
                const streamId = button.id.replace("btn-stats-", "");
                const streamElement = button.closest(".stream");
                const streamName =
                    streamElement?.querySelector(".stream-name")?.textContent ||
                    `Стрим ${streamId}`;

                if (window.StreamStats) {
                    StreamStats.showStats(parseInt(streamId), streamName);
                }
            }
        }
    });
}

// Функция инициализации приложения
function initializeApp() {
    try {
        // Проверка доступности критических модулей
        if (!window.Utils || !window.I18n || !window.API) {
            setTimeout(initializeApp, 100); // Повторить через 100ms
            return;
        }

        // Инициализация состояния серверов из данных в HTML
        initializeServersState();

        markServersWithManyStreams();

        // Настройка обработчиков событий
        setupEventListeners();

        if (AppGlobal.updateScrollHints) {
            AppGlobal.updateScrollHints();
        }

        // Форматируем числа файлов после загрузки
        if (AppGlobal.formatInitialFileCounts) {
            AppGlobal.formatInitialFileCounts();
        }

        // Настройка обработчика смены языка
        setupLanguageChangeHandler();
    } catch (error) {
        console.error("[App] Критическая ошибка при инициализации:", error);
        if (window.Notifications) {
            Notifications.showError("Ошибка инициализации приложения", 5000);
        }
    }
}

// Сделать доступным глобально
window.AppState = AppState;
window.AppGlobal = AppGlobal;
window.App = {
    initializeApp,
    initializeServersState,
    setupEventListeners,
    markServersWithManyStreams,
    updateInterfaceAfterLanguageChange,
};
