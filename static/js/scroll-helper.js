/**
 * static\js\scroll-helper.js
 * Вспомогательные функции для работы с прокруткой страницы
 * Обеспечивает плавную прокрутку, отслеживание позиции и управление кнопкой "вверх"
 * Сохраняет и восстанавливает позицию прокрутки между перезагрузками
 */

const ScrollHelper = {
    isInitialized: false,
    scrollPosition: 0,

    /**
     * Инициализация системы прокрутки
     */
    init() {
        if (this.isInitialized) {
            console.warn("[ScrollHelper] Уже инициализирован");
            return;
        }

        // Восстанавливаем позицию прокрутки из sessionStorage, если есть
        this.restoreScrollPosition();

        // Сохраняем позицию прокрутки при разгрузке страницы
        window.addEventListener("beforeunload", () => {
            this.saveScrollPosition();
        });

        // Отслеживаем изменения позиции прокрутки
        window.addEventListener("scroll", () => {
            this.trackScrollPosition();
            this.toggleScrollToTopButton();
        });

        this.isInitialized = true;
    },

    /**
     * Плавно прокручивает страницу к указанному элементу
     * @param {string} elementId - ID целевого элемента
     * @param {number} offset - Смещение в пикселях (опционально)
     */
    scrollToElement(elementId, offset = 0) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`[ScrollHelper] Элемент с ID ${elementId} не найден`);
            return;
        }

        const elementRect = element.getBoundingClientRect();
        const absoluteElementTop = elementRect.top + window.pageYOffset;
        const scrollPosition = absoluteElementTop + offset;

        window.scrollTo({
            top: scrollPosition,
            behavior: "smooth",
        });
    },

    /**
     * Прокручивает страницу к началу
     */
    scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    },

    /**
     * Прокручивает страницу к концу
     */
    scrollToBottom() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: "smooth",
        });
    },

    /**
     * Сохраняет текущую позицию прокрутки в sessionStorage
     */
    saveScrollPosition() {
        this.scrollPosition =
            window.pageYOffset || document.documentElement.scrollTop;
        sessionStorage.setItem(
            "scrollPosition",
            this.scrollPosition.toString()
        );
    },

    /**
     * Восстанавливает позицию прокрутки из sessionStorage
     */
    restoreScrollPosition() {
        const savedPosition = sessionStorage.getItem("scrollPosition");
        if (savedPosition) {
            const position = parseInt(savedPosition, 10);

            window.scrollTo({
                top: position,
                behavior: "auto",
            });

            // Очищаем сохраненную позицию после восстановления
            sessionStorage.removeItem("scrollPosition");
        }
    },

    /**
     * Отслеживает и сохраняет текущую позицию прокрутки
     */
    trackScrollPosition() {
        const currentPosition =
            window.pageYOffset || document.documentElement.scrollTop;

        // Сохраняем только если позиция изменилась значительно
        if (Math.abs(currentPosition - this.scrollPosition) > 100) {
            this.scrollPosition = currentPosition;
        }
    },

    /**
     * Возвращает текущую позицию прокрутки
     * @returns {number} Текущая позиция в пикселях
     */
    getCurrentPosition() {
        return this.scrollPosition;
    },

    /**
     * Проверяет, находится ли элемент в области видимости
     * @param {string} elementId - ID элемента для проверки
     * @returns {boolean} true если элемент видим
     */
    isElementVisible(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return false;

        const rect = element.getBoundingClientRect();
        const windowHeight =
            window.innerHeight || document.documentElement.clientHeight;
        const windowWidth =
            window.innerWidth || document.documentElement.clientWidth;

        const isVisible =
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= windowHeight &&
            rect.right <= windowWidth;

        return isVisible;
    },

    /**
     * Показывает/скрывает кнопку прокрутки вверх в зависимости от позиции
     */
    toggleScrollToTopButton() {
        const scrollButton = document.getElementById("scrollToTop");
        if (!scrollButton) return;

        const scrollY =
            window.pageYOffset || document.documentElement.scrollTop;

        if (scrollY > 300) {
            scrollButton.classList.add("show");
        } else {
            scrollButton.classList.remove("show");
        }
    },
};

// Сделать доступным глобально
window.ScrollHelper = ScrollHelper;
