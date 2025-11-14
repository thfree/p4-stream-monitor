/**
 * static\js\i18n.js
 * Масштабируемая система интернационализации (i18n)
 * Управляет загрузкой переводов, переключением языков и динамическим обновлением интерфейса
 * Поддерживает плейсхолдеры и вложенные структуры переводов
 */

const I18n = {
    currentLang: "ru",
    availableLanguages: {},
    translations: {},

    /**
     * Инициализация системы i18n
     */
    async init() {
        await this.loadAvailableLanguages();
        await this.detectAndLoadLanguage();
        this.setupLanguageSwitcher();
    },

    /**
     * Загружает список доступных языков
     */
    async loadAvailableLanguages() {
        try {
            this.availableLanguages = {
                ru: {
                    name: "Русский",
                    code: "RU",
                    flag: "🇷🇺",
                    file: "ru.json",
                },
                en: {
                    name: "English",
                    code: "EN",
                    flag: "🇺🇸",
                    file: "en.json",
                },
            };
        } catch (error) {
            console.error("[I18n] Error loading available languages:", error);
        }
    },

    /**
     * Определяет и загружает язык
     */
    async detectAndLoadLanguage() {
        const savedLang = localStorage.getItem("preferredLanguage");
        if (savedLang && this.availableLanguages[savedLang]) {
            this.currentLang = savedLang;
        } else {
            const browserLang = this.getBrowserLanguage();
            if (this.availableLanguages[browserLang]) {
                this.currentLang = browserLang;
            }
        }

        await this.loadLanguage(this.currentLang);
    },

    /**
     * Определяет язык браузера
     */
    getBrowserLanguage() {
        const browserLang = (
            navigator.language ||
            navigator.userLanguage ||
            "ru"
        ).split("-")[0];
        return browserLang;
    },

    /**
     * Загружает переводы для конкретного языка
     */
    async loadLanguage(langCode) {
        try {
            if (!this.availableLanguages[langCode]) {
                langCode = "ru";
            }

            const response = await fetch(`/static/locales/${langCode}.json`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            this.translations[langCode] = await response.json();
            this.currentLang = langCode;

            this.applyTranslations();
            this.updateLanguageSwitcher();
        } catch (error) {
            console.error(`[I18n] Error loading language ${langCode}:`, error);
            if (langCode !== "ru") {
                await this.loadLanguage("ru");
            }
        }
    },

    /**
     * Применяет переводы ко всем элементам страницы
     */
    applyTranslations() {
        const langData = this.getFlatTranslations();

        // Устанавливаем атрибут lang для html элемента
        document.documentElement.lang = this.currentLang;

        // Обновляем все элементы с переводами
        this.updateTranslatedElements();

        // Обновляем модальные окна
        this.updateModals();
    },

    /**
     * Преобразует вложенные объекты в плоскую структуру
     */
    getFlatTranslations() {
        const flat = {};

        const flatten = (obj, prefix = "") => {
            for (const key in obj) {
                if (typeof obj[key] === "object") {
                    flatten(obj[key], prefix + key + ".");
                } else {
                    flat[prefix + key] = obj[key];
                }
            }
        };

        if (this.translations[this.currentLang]) {
            flatten(this.translations[this.currentLang]);
        }

        return flat;
    },

    /**
     * Получает перевод по ключу с заменой плейсхолдеров
     */
    getTranslation(key, data = {}) {
        const flatTranslations = this.getFlatTranslations();
        let text = flatTranslations[key] || key;

        text = text.replace(/{(\w+)}/g, (match, placeholder) => {
            return data[placeholder] !== undefined ? data[placeholder] : match;
        });

        return text;
    },

    /**
     * Настраивает переключатель языков
     */
    setupLanguageSwitcher() {
        this.renderLanguageSwitcher();

        document.addEventListener("click", (e) => {
            if (e.target.closest("#language-switcher")) {
                this.toggleLanguageDropdown();
            } else if (e.target.closest(".language-option")) {
                const langCode =
                    e.target.closest(".language-option").dataset.lang;
                this.switchLanguage(langCode);
            } else {
                this.hideLanguageDropdown();
            }
        });
    },

    /**
     * Рендерит переключатель языков
     */
    renderLanguageSwitcher() {
        const currentLang = this.availableLanguages[this.currentLang];
        const switcherHTML = `
            <div class="language-switcher-container">
                <button id="language-switcher" class="btn-language" title="${this.t(
                    "language.change"
                )}">
                    ${currentLang.code}
                </button>
                <div class="language-dropdown" id="language-dropdown">
                    ${Object.entries(this.availableLanguages)
                        .map(
                            ([code, lang]) => `
                            <div class="language-option ${
                                code === this.currentLang ? "active" : ""
                            }" 
                                data-lang="${code}">
                                ${lang.flag} ${lang.name} (${lang.code})
                            </div>
                        `
                        )
                        .join("")}
                </div>
            </div>
        `;

        const container = document.querySelector(".language-switcher");
        if (container) {
            container.innerHTML = switcherHTML;
        }
    },

    /**
     * Переключает язык
     */
    async switchLanguage(langCode) {
        if (
            this.availableLanguages[langCode] &&
            langCode !== this.currentLang
        ) {
            const oldLang = this.currentLang;

            await this.loadLanguage(langCode);
            localStorage.setItem("preferredLanguage", langCode);
            this.hideLanguageDropdown();

            // Принудительно обновляем ВСЕ переведенные элементы
            this.applyTranslations();

            // Специальное обновление для динамических кнопок
            if (
                typeof ServerToggler !== "undefined" &&
                ServerToggler.updateToggleAllButton
            ) {
                ServerToggler.updateToggleAllButton();
            }

            // Обновляем поиск если есть активный запрос
            if (
                typeof StreamSearch !== "undefined" &&
                StreamSearch.getCurrentQuery
            ) {
                const currentQuery = StreamSearch.getCurrentQuery();
                if (currentQuery) {
                    StreamSearch.performSearch(currentQuery);
                }
            }

            // Отправляем кастомное событие для других модулей
            document.dispatchEvent(
                new CustomEvent("languageChanged", {
                    detail: { oldLang, newLang: langCode },
                })
            );
        }
    },

    /**
     * Обновляет интерфейс после смены языка
     */
    updateInterfaceAfterLanguageChange() {
        // Обновляем кнопку "свернуть/развернуть все"
        const toggleAllBtn = document.getElementById("btn-toggle-all");
        if (toggleAllBtn) {
            // Вызываем метод обновления кнопки из ServerToggler
            if (
                typeof ServerToggler !== "undefined" &&
                ServerToggler.updateToggleAllButton
            ) {
                ServerToggler.updateToggleAllButton();
            }
        }

        // Обновляем информацию о поиске если есть активный поиск
        const searchInput = document.getElementById("stream-search");
        if (searchInput && searchInput.value) {
            if (
                typeof StreamSearch !== "undefined" &&
                StreamSearch.performSearch
            ) {
                StreamSearch.performSearch(searchInput.value);
            }
        }

        // Обновляем подсказки прокрутки
        if (typeof updateScrollHints === "function") {
            updateScrollHints();
        }

        // Показываем уведомление о смене языка
        if (typeof Notifications !== "undefined") {
            Notifications.showInfo(
                this.t("notification.languageChanged", {
                    language: this.t(`language.${this.currentLang}`),
                }),
                2000
            );
        }
    },

    /**
     * Обновляет все переведенные элементы на странице
     */
    updateTranslatedElements() {
        // Текстовые элементы
        document.querySelectorAll("[data-i18n]").forEach((element) => {
            const key = element.getAttribute("data-i18n");
            const translation = this.getTranslation(key, element.dataset);
            if (translation && element.innerHTML !== translation) {
                element.innerHTML = translation;
            }
        });

        // Атрибуты title
        document.querySelectorAll("[data-i18n-title]").forEach((element) => {
            const key = element.getAttribute("data-i18n-title");
            const translation = this.getTranslation(key, element.dataset);
            if (translation && element.title !== translation) {
                element.title = translation;
            }
        });

        // Placeholders
        document
            .querySelectorAll("[data-i18n-placeholder]")
            .forEach((element) => {
                const key = element.getAttribute("data-i18n-placeholder");
                const translation = this.getTranslation(key, element.dataset);
                if (translation && element.placeholder !== translation) {
                    element.placeholder = translation;
                }
            });

        // Обновляем элементы с количеством файлов
        document
            .querySelectorAll(".file-count[data-original-count]")
            .forEach((element) => {
                const originalCount = element.getAttribute(
                    "data-original-count"
                );
                if (originalCount) {
                    const numericCount = parseInt(originalCount);
                    if (!isNaN(numericCount)) {
                        const formattedCount =
                            Utils.formatLargeNumber(numericCount);
                        const filesText = this.t("stream.files");
                        const formattedExactCount =
                            numericCount.toLocaleString();

                        // Обновляем содержимое
                        element.innerHTML = `• ${formattedCount} ${filesText}`;
                        element.title = formattedExactCount;
                        element.setAttribute(
                            "data-formatted-count",
                            formattedCount
                        );
                    }
                }
            });
    },

    /**
     * Обновляет тексты в модальных окнах
     */
    updateModals() {
        // Обновляем модальное окно списка стримов
        const modalButtons = document.querySelectorAll(
            "#streams-modal [data-i18n]"
        );
        modalButtons.forEach((element) => {
            const key = element.getAttribute("data-i18n");
            const translation = this.getTranslation(key, element.dataset);
            if (translation && element.textContent !== translation) {
                element.textContent = translation;
            }
        });

        // Обновляем модальное окно статистики
        const statsButtons = document.querySelectorAll(
            "#stats-modal [data-i18n]"
        );
        statsButtons.forEach((element) => {
            const key = element.getAttribute("data-i18n");
            const translation = this.getTranslation(key, element.dataset);
            if (translation && element.textContent !== translation) {
                element.textContent = translation;
            }
        });

        // Обновляем заголовки модальных окон
        this.updateModalContent();
        this.updateStatsModal();
    },

    /**
     * Обновляет содержимое модального окна списка стримов
     */
    updateModalContent() {
        // Обновляем заголовок модального окна
        const modalTitle = document.getElementById("modal-title");
        if (modalTitle && Modal.currentServerId) {
            const serverElement = document.getElementById(
                `server-${Modal.currentServerId}`
            );
            const serverName =
                serverElement?.dataset.serverName ||
                `Сервер ${Modal.currentServerId}`;
            const streamList = document.getElementById("stream-list");
            const count = streamList ? streamList.children.length : 0;

            modalTitle.textContent = this.t("modal.streamsTitle", {
                server: serverName,
                count: count,
            });
        }
    },

    /**
     * Обновляет модальное окно статистики
     */
    updateStatsModal() {
        // Обновляем заголовок если есть активный стрим
        if (
            typeof StreamStats !== "undefined" &&
            StreamStats.currentStreamName
        ) {
            const statsTitle = document.getElementById("stats-modal-title");
            if (statsTitle) {
                statsTitle.textContent = this.t("stats.title", {
                    stream: StreamStats.currentStreamName,
                });
            }
        }

        // Обновляем ВСЕ элементы в модальном окне статистики
        const statsModal = document.getElementById("stats-modal");
        if (statsModal) {
            // Обновляем текстовые элементы
            statsModal.querySelectorAll("[data-i18n]").forEach((element) => {
                const key = element.getAttribute("data-i18n");
                const translation = this.getTranslation(key, element.dataset);
                if (translation && element.textContent !== translation) {
                    element.textContent = translation;
                }
            });

            // Обновляем кнопку "Обновить"
            const refreshBtn = document.getElementById("stats-refresh-btn");
            if (refreshBtn && refreshBtn.textContent.includes("Обновить")) {
                refreshBtn.innerHTML = this.t("stats.refresh");
            }

            // Обновляем placeholder'ы
            statsModal
                .querySelectorAll("[data-i18n-placeholder]")
                .forEach((element) => {
                    const key = element.getAttribute("data-i18n-placeholder");
                    const translation = this.getTranslation(
                        key,
                        element.dataset
                    );
                    if (translation && element.placeholder !== translation) {
                        element.placeholder = translation;
                    }
                });
        }
    },

    /**
     * Показывает/скрывает выпадающий список языков
     */
    toggleLanguageDropdown() {
        const dropdown = document.getElementById("language-dropdown");
        if (dropdown) {
            dropdown.classList.toggle("show");
        }
    },

    hideLanguageDropdown() {
        const dropdown = document.getElementById("language-dropdown");
        if (dropdown) {
            dropdown.classList.remove("show");
        }
    },

    /**
     * Обновляет переключатель языков
     */
    updateLanguageSwitcher() {
        this.renderLanguageSwitcher();
    },

    /**
     * Получает перевод (публичный метод)
     */
    t(key, data = {}) {
        return this.getTranslation(key, data);
    },

    /**
     * Возвращает список доступных языков
     */
    getAvailableLanguages() {
        return this.availableLanguages;
    },

    /**
     * Возвращает текущий язык
     */
    getCurrentLanguage() {
        return this.currentLang;
    },
};

// Сделать доступным глобально
window.I18n = I18n;
