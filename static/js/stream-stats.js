/**
 * static\js\stream-stats.js
 * Модуль для работы со статистикой и графиками стримов
 * Отображает историю изменений размеров стримов в виде графиков и статистики
 * Использует Chart.js для визуализации данных
 */

const StreamStats = {
    currentStreamId: null,
    currentStreamName: null,
    chart: null,
    escapeHandler: null,
    modalClickHandler: null,

    /**
     * Показывает модальное окно со статистикой стрима
     * @param {number} streamId - ID стрима
     * @param {string} streamName - Имя стрима
     */
    async showStats(streamId, streamName) {
        // Проверка поддержки Canvas
        if (!this.isCanvasSupported()) {
            Notifications.showError(
                I18n.t("notification.browserNotSupported"),
                4000
            );
            return;
        }

        this.currentStreamId = streamId;
        this.currentStreamName = streamName;

        // Обновляем заголовок модального окна
        const titleElement = document.getElementById("stats-modal-title");
        if (titleElement) {
            titleElement.textContent = I18n.t("stats.title", {
                stream: streamName,
            });
        }

        // Сбрасываем значения перед загрузкой
        this.resetStatsDisplay();

        // Показываем модальное окно
        this.openStatsModal();

        // Загружаем данные
        await this.loadStatsData();
    },

    /**
     * Проверяет поддержку Canvas
     * @returns {boolean}
     */
    isCanvasSupported() {
        const canvas = document.createElement("canvas");
        return !!(canvas.getContext && canvas.getContext("2d"));
    },

    /**
     * Сбрасывает отображение статистики перед загрузкой новых данных
     */
    resetStatsDisplay() {
        const elements = [
            "stats-current-size",
            "stats-max-size",
            "stats-min-size",
            "stats-avg-size",
            "stats-change",
            "stats-records-count",
        ];

        elements.forEach((id) => {
            const element = document.getElementById(id);
            if (element) {
                if (id === "stats-records-count") {
                    element.textContent = "0";
                } else {
                    element.textContent = I18n.t("stats.loading");
                }
            }
        });

        // Сбрасываем цвет изменения
        const changeElement = document.getElementById("stats-change");
        if (changeElement) {
            changeElement.style.color = "";
            changeElement.className = "stat-value";
        }

        // Очищаем график если он существует
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    },

    /**
     * Открывает модальное окно статистики
     */
    openStatsModal() {
        const modal = document.getElementById("stats-modal");
        if (modal) {
            modal.style.display = "flex";
            // Блокируем прокрутку body через класс
            document.body.classList.add("modal-open");
            this.addStatsModalHandlers();
            console.log(
                "[Stats] Модальное окно статистики открыто, прокрутка заблокирована"
            );
        }
    },

    /**
     * Закрывает модальное окно статистики
     */
    closeStatsModal() {
        const modal = document.getElementById("stats-modal");
        if (modal) {
            modal.style.display = "none";
            // Восстанавливаем прокрутку body
            document.body.classList.remove("modal-open");
            console.log(
                "[Stats] Модальное окно статистики закрыто, прокрутка восстановлена"
            );
        }

        this.removeStatsModalHandlers();

        // Уничтожаем график если он существует
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }

        this.currentStreamId = null;
        this.currentStreamName = null;
    },

    /**
     * Добавляет обработчики для модального окна статистики
     */
    addStatsModalHandlers() {
        // Обработчики кнопок
        const closeBtn = document.getElementById("stats-close-btn");
        const refreshBtn = document.getElementById("stats-refresh-btn");
        const periodSelect = document.getElementById("stats-period");

        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.closeStatsModal());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener("click", () => this.loadStatsData());
        }

        if (periodSelect) {
            periodSelect.addEventListener("change", () => this.loadStatsData());
        }

        // Обработчик клавиши Escape
        this.escapeHandler = (event) => {
            if (event.key === "Escape") {
                this.closeStatsModal();
            }
        };
        document.addEventListener("keydown", this.escapeHandler);

        // Закрытие по клику вне области
        this.modalClickHandler = (event) => {
            const modal = document.getElementById("stats-modal");
            if (event.target === modal) {
                this.closeStatsModal();
            }
        };

        const statsModal = document.getElementById("stats-modal");
        if (statsModal) {
            statsModal.addEventListener("click", this.modalClickHandler);
        }
    },

    /**
     * Удаляет обработчики модального окна статистики
     */
    removeStatsModalHandlers() {
        if (this.escapeHandler) {
            document.removeEventListener("keydown", this.escapeHandler);
            this.escapeHandler = null;
        }

        const modal = document.getElementById("stats-modal");
        if (modal && this.modalClickHandler) {
            modal.removeEventListener("click", this.modalClickHandler);
            this.modalClickHandler = null;
        }
    },

    /**
     * Загружает данные статистики с сервера
     */
    async loadStatsData() {
        if (!this.currentStreamId) return;

        const periodSelect = document.getElementById("stats-period");
        const refreshBtn = document.getElementById("stats-refresh-btn");

        if (!periodSelect || !refreshBtn) return;

        const period = periodSelect.value;

        // Показываем состояние загрузки
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = I18n.t("stats.loading");

        try {
            const response = await fetch(
                `/api/stream/${this.currentStreamId}/history?days=${period}`
            );

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                this.displayStats(data.history);
                this.renderChart(data.history);
            } else {
                throw new Error(data.error || I18n.t("notification.loadError"));
            }
        } catch (error) {
            console.error("[Stats] Ошибка загрузки статистики:", error);
            this.showNoData();
            Notifications.showError(
                I18n.t("notification.loadError") + ": " + error.message,
                4000
            );
        } finally {
            // Восстанавливаем кнопку
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = I18n.t("stats.refresh");
        }
    },

    /**
     * Отображает статистическую информацию
     * @param {Array} historyData - Данные истории
     */
    displayStats(historyData) {
        if (
            !historyData ||
            !Array.isArray(historyData) ||
            historyData.length === 0
        ) {
            this.showNoData();
            return;
        }

        try {
            // Сортируем данные по дате (от старых к новым)
            const sortedData = [...historyData].sort((a, b) => {
                const dateA = new Date(a.timestamp);
                const dateB = new Date(b.timestamp);
                return dateA - dateB;
            });

            // Рассчитываем статистику
            const sizes = sortedData.map((item) => item.size_bytes);
            const currentSize = sortedData[sortedData.length - 1].size_bytes;
            const maxSize = Math.max(...sizes);
            const minSize = Math.min(...sizes);
            const avgSize =
                sizes.reduce((sum, size) => sum + size, 0) / sizes.length;

            // Рассчитываем изменение
            const oldestSize = sortedData[0].size_bytes;
            const sizeChange = currentSize - oldestSize;
            const changePercent =
                oldestSize > 0
                    ? ((sizeChange / oldestSize) * 100).toFixed(1)
                    : "0.0";

            // Обновляем DOM
            this.updateStatElement(
                "stats-current-size",
                Utils.formatFileSize(currentSize)
            );
            this.updateStatElement(
                "stats-max-size",
                Utils.formatFileSize(maxSize)
            );
            this.updateStatElement(
                "stats-min-size",
                Utils.formatFileSize(minSize)
            );
            this.updateStatElement(
                "stats-avg-size",
                Utils.formatFileSize(avgSize)
            );
            this.updateStatElement(
                "stats-records-count",
                sortedData.length.toString()
            );

            // Отображаем изменение с цветом
            this.updateChangeElement(sizeChange, changePercent);
        } catch (error) {
            console.error("[Stats] Ошибка при расчете статистики:", error);
            this.showNoData();
        }
    },

    /**
     * Обновляет элемент статистики
     * @param {string} elementId - ID элемента
     * @param {string} value - Значение
     */
    updateStatElement(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    },

    /**
     * Обновляет элемент изменения размера
     * @param {number} sizeChange - Изменение размера
     * @param {string} changePercent - Процент изменения
     */
    updateChangeElement(sizeChange, changePercent) {
        const changeElement = document.getElementById("stats-change");
        if (!changeElement) return;

        const changeSign = sizeChange >= 0 ? "+" : "";
        changeElement.textContent = `${changeSign}${Utils.formatFileSize(
            sizeChange
        )} (${changeSign}${changePercent}%)`;

        // Устанавливаем цвет
        changeElement.classList.remove(
            "change-positive",
            "change-negative",
            "change-neutral"
        );

        if (sizeChange > 0) {
            changeElement.classList.add("change-positive");
        } else if (sizeChange < 0) {
            changeElement.classList.add("change-negative");
        } else {
            changeElement.classList.add("change-neutral");
        }
    },

    /**
     * Показывает сообщение об отсутствии данных
     */
    showNoData() {
        const noDataText = I18n.t("stats.noData");
        this.updateStatElement("stats-current-size", noDataText);
        this.updateStatElement("stats-max-size", noDataText);
        this.updateStatElement("stats-min-size", noDataText);
        this.updateStatElement("stats-avg-size", noDataText);
        this.updateStatElement("stats-change", noDataText);
        this.updateStatElement("stats-records-count", "0");

        // Очищаем график
        this.clearChartCanvas();
    },

    /**
     * Очищает canvas графика
     */
    clearChartCanvas() {
        const canvas = document.getElementById("size-chart");
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Отображаем сообщение об отсутствии данных
        ctx.font = "14px Arial";
        ctx.fillStyle = "#666";
        ctx.textAlign = "center";
        ctx.fillText(
            I18n.t("stats.noData"),
            canvas.width / 2,
            canvas.height / 2
        );
    },

    /**
     * Рендерит график изменения размера
     * @param {Array} historyData - Данные истории
     */
    renderChart(historyData) {
        const canvas = document.getElementById("size-chart");
        if (!canvas) return;

        // Уничтожаем предыдущий график
        if (this.chart) {
            this.chart.destroy();
        }

        if (
            !historyData ||
            !Array.isArray(historyData) ||
            historyData.length === 0
        ) {
            this.showNoData();
            return;
        }

        try {
            // Сортируем данные по дате (от старых к новым)
            const sortedData = [...historyData].sort((a, b) => {
                const dateA = new Date(a.timestamp);
                const dateB = new Date(b.timestamp);
                return dateA - dateB;
            });

            // Подготавливаем данные для графика
            const labels = sortedData.map((item) => {
                const date = new Date(item.timestamp);
                return date.toLocaleDateString("ru-RU", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                });
            });

            const data = sortedData.map((item) => item.size_bytes);

            // Создаем график с Chart.js
            this.chart = new Chart(canvas, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: I18n.t("stats.chartLabel"),
                            data: data,
                            borderColor: "#007acc",
                            backgroundColor: "rgba(0, 122, 204, 0.1)",
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: "#007acc",
                            pointBorderColor: "#ffffff",
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            mode: "index",
                            intersect: false,
                            backgroundColor: "rgba(0, 0, 0, 0.8)",
                            titleColor: "#ffffff",
                            bodyColor: "#ffffff",
                            borderColor: "#007acc",
                            borderWidth: 1,
                            callbacks: {
                                label: (context) => {
                                    return `${I18n.t(
                                        "stats.chartLabel"
                                    )}: ${Utils.formatFileSize(
                                        context.parsed.y
                                    )}`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: {
                                color: "rgba(0, 0, 0, 0.1)",
                            },
                            ticks: {
                                color: "#666",
                                maxRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 10,
                            },
                        },
                        y: {
                            beginAtZero: false,
                            grid: {
                                color: "rgba(0, 0, 0, 0.1)",
                            },
                            ticks: {
                                color: "#666",
                                callback: (value) =>
                                    Utils.formatFileSize(value),
                            },
                        },
                    },
                    interaction: {
                        intersect: false,
                        mode: "index",
                    },
                },
            });
        } catch (error) {
            console.error("[Stats] Ошибка при создании графика:", error);
            this.clearChartCanvas();
        }
    },
};

// Сделать доступным глобально
window.StreamStats = StreamStats;
