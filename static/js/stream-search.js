/**
 * static\js\stream-search.js
 * Модуль поиска и фильтрации стримов
 * Обеспечивает поиск по имени стрима с отложенным выполнением
 * Фильтрует серверы и стримы, показывает информацию о результатах
 */

const StreamSearch = {
    currentQuery: "",
    searchTimeout: null,

    /**
     * Инициализация системы поиска
     */
    init() {
        const searchInput = document.getElementById("stream-search");
        const clearButton = document.getElementById("btn-clear-search");

        if (!searchInput) {
            console.warn("[Search] Поле поиска не найдено");
            return;
        }

        // Обработчик ввода текста
        searchInput.addEventListener("input", (e) => {
            this.handleSearch(e.target.value);
        });

        // Обработчик очистки
        clearButton.addEventListener("click", () => {
            this.clearSearch();
        });

        // Обработчик клавиши Escape
        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                this.clearSearch();
                searchInput.blur();
            }
        });
    },

    /**
     * Обработка поискового запроса
     * @param {string} query - Поисковый запрос
     */
    handleSearch(query) {
        // Очищаем предыдущий таймер
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        // Устанавливаем новый таймер для отложенного поиска
        this.searchTimeout = setTimeout(() => {
            this.performSearch(query.trim());
        }, 300);
    },

    /**
     * Выполнение поиска
     * @param {string} query - Поисковый запрос
     */
    performSearch(query) {
        this.currentQuery = query;

        const searchInfo = document.getElementById("search-results-info");
        const clearButton = document.getElementById("btn-clear-search");

        // Показываем/скрываем кнопку очистки
        if (query.length > 0) {
            clearButton.style.display = "flex";
        } else {
            clearButton.style.display = "none";
        }

        if (query.length === 0) {
            this.showAll();
            this.hideSearchInfo();
            return;
        }

        const searchTerm = query.toLowerCase();
        let totalMatches = 0;
        let serversWithMatches = 0;

        // Поиск по всем стримам
        const allStreams = document.querySelectorAll(".stream");
        allStreams.forEach((stream) => {
            const streamName = stream
                .querySelector(".stream-name")
                .textContent.toLowerCase();
            const isMatch = streamName.includes(searchTerm);

            if (isMatch) {
                stream.classList.remove("hidden-by-search");
                totalMatches++;
            } else {
                stream.classList.add("hidden-by-search");
            }
        });

        // Обработка серверов
        const allServers = document.querySelectorAll(".server");
        allServers.forEach((server) => {
            const serverStreams = server.querySelectorAll(
                ".stream:not(.hidden-by-search)"
            );
            const hasVisibleStreams = serverStreams.length > 0;

            if (hasVisibleStreams) {
                server.classList.remove("hidden-by-search");
                serversWithMatches++;

                // Автоматически разворачиваем серверы с результатами
                ServerToggler.expandServer(server.dataset.serverId);
            } else {
                server.classList.add("hidden-by-search");
            }
        });

        // Показываем информацию о результатах
        this.showSearchInfo(totalMatches, serversWithMatches, query);

        // Обновляем подсказки прокрутки после фильтрации
        setTimeout(() => {
            if (window.AppGlobal && window.AppGlobal.updateScrollHints) {
                window.AppGlobal.updateScrollHints();
            }
        }, 100);
    },

    /**
     * Показывает информацию о результатах поиска
     * @param {number} streamMatches - Количество найденных стримов
     * @param {number} serverMatches - Количество серверов с совпадениями
     * @param {string} query - Поисковый запрос
     */
    showSearchInfo(streamMatches, serverMatches, query) {
        const searchInfo = document.getElementById("search-results-info");

        if (streamMatches === 0) {
            searchInfo.innerHTML = I18n.t("search.noResults", {
                query: this.escapeHtml(query),
            });
            searchInfo.classList.add("show");
        } else {
            searchInfo.innerHTML =
                I18n.t("search.results", {
                    count: streamMatches,
                    servers: serverMatches,
                }) +
                `<button onclick="StreamSearch.clearSearch()">${I18n.t(
                    "search.clear"
                )}</button>`;
            searchInfo.classList.add("show");
        }
    },

    /**
     * Скрывает информацию о результатах поиска
     */
    hideSearchInfo() {
        const searchInfo = document.getElementById("search-results-info");
        if (searchInfo) {
            searchInfo.classList.remove("show");
            searchInfo.innerHTML = "";
        }
    },

    /**
     * Показывает все элементы (очищает поиск)
     */
    showAll() {
        const allElements = document.querySelectorAll(".server, .stream");
        allElements.forEach((element) => {
            element.classList.remove("hidden-by-search");
        });

        this.hideSearchInfo();
        document.getElementById("btn-clear-search").style.display = "none";
    },

    /**
     * Очищает поиск и показывает все элементы
     */
    clearSearch() {
        const searchInput = document.getElementById("stream-search");
        searchInput.value = "";
        this.currentQuery = "";

        this.showAll();
        searchInput.focus();
    },

    /**
     * Экранирует HTML для безопасного отображения
     * @param {string} text - Текст для экранирования
     * @returns {string} Экранированный текст
     */
    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Возвращает текущий поисковый запрос
     * @returns {string} Текущий запрос
     */
    getCurrentQuery() {
        return this.currentQuery;
    },
};

// Сделать доступным глобально
window.StreamSearch = StreamSearch;
