/**
 * static\js\main.js
 * Основной файл инициализации приложения
 * Управляет загрузкой зависимостей и последовательной инициализацией всех модулей
 * Обеспечивает корректный порядок инициализации и обработку ошибок
 */

class AppInitializer {
    static dependencies = {
        Utils: "/static/js/utils.js",
        I18n: "/static/js/i18n.js",
        Notifications: "/static/js/notifications.js",
        ScrollHelper: "/static/js/scroll-helper.js",
        ServerToggler: "/static/js/server-toggler.js",
        StreamSearch: "/static/js/stream-search.js",
        StreamStats: "/static/js/stream-stats.js",
        API: "/static/js/api.js",
        App: "/static/js/app.js",
    };

    static loadedModules = new Set();

    static async initialize() {
        console.log("Инициализация Perforce Stream Monitor...");

        try {
            // Загружаем все зависимости по порядку
            await this.loadDependencies();

            // Инициализируем i18n первой
            if (window.I18n && typeof window.I18n.init === "function") {
                await window.I18n.init();
            }

            // Инициализируем основные компоненты
            this.initializeAppComponents();

            // Проверяем доступность всех модулей
            this.verifyModules();
        } catch (error) {
            console.error("Ошибка инициализации:", error);
            this.showError("Ошибка загрузки приложения: " + error.message);
        }
    }

    static initializeAppComponents() {
        // Порядок инициализации компонентов
        const initSequence = [
            {
                module: window.ScrollHelper,
                name: "ScrollHelper",
                method: "init",
                optional: false,
            },
            {
                module: window.StreamSearch,
                name: "StreamSearch",
                method: "init",
                optional: false,
            },
            {
                module: window.ServerToggler,
                name: "ServerToggler",
                method: "updateToggleAllButton",
                optional: true,
            },
        ];

        initSequence.forEach(({ module, name, method, optional }) => {
            if (module && typeof module[method] === "function") {
                try {
                    module[method]();
                    this.loadedModules.add(name);
                } catch (error) {
                    console.error(`Ошибка инициализации ${name}:`, error);
                    if (!optional) {
                        throw error;
                    }
                }
            } else {
                console.warn(`${name} не доступен для инициализации`);
                if (!optional) {
                    throw new Error(`Обязательный модуль ${name} не доступен`);
                }
            }
        });

        // Инициализация App если он существует
        if (window.App && typeof window.App.initializeApp === "function") {
            try {
                window.App.initializeApp();
                this.loadedModules.add("App");
            } catch (error) {
                console.error("Ошибка инициализации App:", error);
            }
        }

        // Инициализация AppState если он существует
        if (window.AppState) {
            this.loadedModules.add("AppState");
        }

        // Инициализация AppGlobal если он существует
        if (window.AppGlobal) {
            this.loadedModules.add("AppGlobal");

            // Вызываем функции инициализации из AppGlobal
            if (
                typeof window.AppGlobal.formatInitialFileCounts === "function"
            ) {
                window.AppGlobal.formatInitialFileCounts();
            }
            if (typeof window.AppGlobal.updateScrollHints === "function") {
                window.AppGlobal.updateScrollHints();
            }
        }
    }

    static async loadDependencies() {
        const loadOrder = [
            "Utils", // Базовые утилиты
            "I18n", // Локализация (зависит от Utils)
            "Notifications", // Уведомления (зависит от I18n)
            "ScrollHelper", // Прокрутка
            "ServerToggler", // Управление серверами
            "StreamSearch", // Поиск
            "StreamStats", // Статистика (зависит от Utils, I18n)
            "API", // API (зависит от Utils, Notifications, I18n)
            "App", // Основное приложение (зависит от всех)
        ];

        for (const depName of loadOrder) {
            await this.loadScript(depName);
        }
    }

    static loadScript(depName) {
        return new Promise((resolve, reject) => {
            // Проверяем, не загружен ли уже модуль
            if (window[depName]) {
                this.loadedModules.add(depName);
                resolve();
                return;
            }

            const script = document.createElement("script");
            script.src = this.dependencies[depName];
            script.setAttribute("data-module", depName);

            script.onload = () => {
                // Даем время на выполнение скрипта
                setTimeout(() => {
                    if (window[depName]) {
                        this.loadedModules.add(depName);
                    } else {
                        console.warn(
                            `${depName} не найден в window после загрузки`
                        );
                    }
                    resolve();
                }, 100);
            };

            script.onerror = (error) => {
                console.error(`Ошибка загрузки ${depName}:`, error);
                reject(new Error(`Не удалось загрузить ${depName}`));
            };

            document.head.appendChild(script);
        });
    }

    static verifyModules() {
        const requiredModules = [
            "Utils",
            "I18n",
            "Notifications",
            "ScrollHelper",
            "ServerToggler",
            "StreamSearch",
            "API",
        ];

        const optionalModules = ["StreamStats", "App", "AppState", "AppGlobal"];

        const missingRequired = requiredModules.filter((mod) => !window[mod]);
        const missingOptional = optionalModules.filter((mod) => !window[mod]);

        if (missingRequired.length > 0) {
            throw new Error(
                `Отсутствуют обязательные модули: ${missingRequired.join(", ")}`
            );
        }

        if (missingOptional.length > 0) {
            console.warn(
                `Отсутствуют опциональные модули: ${missingOptional.join(", ")}`
            );
        }
    }

    static showError(message) {
        console.error("Критическая ошибка:", message);

        // Можно добавить отображение ошибки в интерфейсе
        const errorDiv = document.createElement("div");
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #dc3545;
            color: white;
            padding: 15px;
            border-radius: 5px;
            z-index: 10000;
            max-width: 400px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        `;
        errorDiv.innerHTML = `
            <strong>Ошибка загрузки</strong>
            <p style="margin: 5px 0; font-size: 14px;">${message}</p>
            <button onclick="this.parentElement.remove()" style="background: white; color: #dc3545; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">Закрыть</button>
        `;
        document.body.appendChild(errorDiv);
    }
}

// Запускаем инициализацию 
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        AppInitializer.initialize();
    });
} else {
    AppInitializer.initialize();
}
