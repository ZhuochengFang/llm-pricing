(function () {
    const COLORS = {
        OpenAI: "openai", Anthropic: "anthropic", DeepSeek: "deepseek",
        Google: "google", Mistral: "mistral", Meta: "meta"
    };

    const HEX_COLORS = {
        OpenAI: "#10a37f", Anthropic: "#d97706", DeepSeek: "#6366f1",
        Google: "#4285f4", Mistral: "#f97316", Meta: "#0668e1"
    };

    let data = [];
    let historyData = [];
    let sevenDayData = [];
    let sortKey = "input_price";
    let sortDir = "asc";
    let activeProvider = null;

    const tbody = document.getElementById("table-body");
    const search = document.getElementById("search");
    const filtersEl = document.getElementById("filters");
    const updatedEl = document.getElementById("updated");
    const refreshBtn = document.getElementById("refresh-btn");

    // Chart state
    let historyChart = null;
    let compareChart = null;
    let selectedModels = new Set();
    let historyPriceType = "input_price";
    let chartsInitialized = { history: false, compare: false, sevenDay: false };

    // --- Tab switching ---
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById(btn.dataset.tab).classList.add("active");

            if (btn.dataset.tab === "tab-7day" && !chartsInitialized.sevenDay && sevenDayData.length) {
                initSevenDayCharts();
            }
            if (btn.dataset.tab === "tab-history" && !chartsInitialized.history && historyData.length) {
                initHistoryChart();
            }
            if (btn.dataset.tab === "tab-compare" && !chartsInitialized.compare && data.length) {
                initCompareChart();
            }
        });
    });

    // --- Chart.js global dark theme ---
    function setChartDefaults() {
        Chart.defaults.color = "#8b949e";
        Chart.defaults.borderColor = "#21262d";
        Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    }

    // --- Data loading ---
    async function load() {
        const [pricesRes, historyRes, sevenDayRes] = await Promise.all([
            fetch("/api/prices"),
            fetch("/api/price-history"),
            fetch("/api/prices-7day")
        ]);
        data = await pricesRes.json();
        historyData = await historyRes.json();
        sevenDayData = await sevenDayRes.json();

        if (data.length) {
            updatedEl.textContent = "Last updated: " + new Date(data[0].updated_at).toLocaleString();
        }
        const providers = [...new Set(data.map(d => d.provider))];
        filtersEl.innerHTML = providers.map(p =>
            `<button class="filter-btn" data-provider="${p}">${p}</button>`
        ).join("");
        filtersEl.querySelectorAll(".filter-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const p = btn.dataset.provider;
                activeProvider = activeProvider === p ? null : p;
                filtersEl.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
                if (activeProvider) btn.classList.add("active");
                render();
            });
        });

        buildModelChips();
        buildSevenDayChips();
        setChartDefaults();
        render();
    }

    // --- Table logic (unchanged) ---
    function filtered() {
        let d = data;
        if (activeProvider) d = d.filter(m => m.provider === activeProvider);
        const q = search.value.toLowerCase();
        if (q) d = d.filter(m => m.provider.toLowerCase().includes(q) || m.model.toLowerCase().includes(q));
        d.sort((a, b) => {
            let va = a[sortKey], vb = b[sortKey];
            if (typeof va === "string") { va = va.toLowerCase(); vb = vb.toLowerCase(); }
            if (va < vb) return sortDir === "asc" ? -1 : 1;
            if (va > vb) return sortDir === "asc" ? 1 : -1;
            return 0;
        });
        return d;
    }

    function fmt(n) { return "$" + n.toFixed(2); }
    function fmtCtx(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
        return (n / 1000).toFixed(0) + "K";
    }

    function render() {
        const rows = filtered();
        tbody.innerHTML = rows.map(m => {
            const cls = COLORS[m.provider] || "openai";
            return `<tr data-provider="${m.provider}" data-model="${m.model}">
                <td><span class="badge badge-${cls}">${m.provider}</span></td>
                <td>${m.model}</td>
                <td class="price">${fmt(m.input_price)}</td>
                <td class="price">${fmt(m.output_price)}</td>
                <td>${fmtCtx(m.context_window)}</td>
            </tr>`;
        }).join("");

        // Attach row click handlers for modal
        tbody.querySelectorAll("tr").forEach(tr => {
            tr.addEventListener("click", () => {
                openModal(tr.dataset.provider, tr.dataset.model);
            });
        });

        // Update comparison chart if visible
        if (chartsInitialized.compare) updateCompareChart();
    }

    document.querySelectorAll("th[data-sort]").forEach(th => {
        th.addEventListener("click", () => {
            const key = th.dataset.sort;
            if (sortKey === key) sortDir = sortDir === "asc" ? "desc" : "asc";
            else { sortKey = key; sortDir = "asc"; }
            document.querySelectorAll("th").forEach(t => t.classList.remove("asc", "desc"));
            th.classList.add(sortDir);
            render();
        });
    });

    search.addEventListener("input", render);

    // --- Model chips for history tab ---
    function buildModelChips() {
        const container = document.getElementById("model-chips");
        // Default: select first 3 models
        const defaults = historyData.slice(0, 3);
        defaults.forEach(m => selectedModels.add(m.provider + ":" + m.model));

        container.innerHTML = historyData.map(m => {
            const key = m.provider + ":" + m.model;
            const color = HEX_COLORS[m.provider] || "#58a6ff";
            const isActive = selectedModels.has(key);
            return `<button class="model-chip${isActive ? " active" : ""}" data-key="${key}"
                style="${isActive ? "background:" + color + ";border-color:" + color : ""}">${m.model}</button>`;
        }).join("");

        container.querySelectorAll(".model-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const key = chip.dataset.key;
                const color = HEX_COLORS[key.split(":")[0]] || "#58a6ff";
                if (selectedModels.has(key)) {
                    selectedModels.delete(key);
                    chip.classList.remove("active");
                    chip.style.background = "";
                    chip.style.borderColor = "";
                } else {
                    selectedModels.add(key);
                    chip.classList.add("active");
                    chip.style.background = color;
                    chip.style.borderColor = color;
                }
                if (chartsInitialized.history) updateHistoryChart();
            });
        });

        // Select All / Clear All
        document.getElementById("select-all-chips").addEventListener("click", () => {
            historyData.forEach(m => selectedModels.add(m.provider + ":" + m.model));
            container.querySelectorAll(".model-chip").forEach(chip => {
                const color = HEX_COLORS[chip.dataset.key.split(":")[0]] || "#58a6ff";
                chip.classList.add("active");
                chip.style.background = color;
                chip.style.borderColor = color;
            });
            if (chartsInitialized.history) updateHistoryChart();
        });
        document.getElementById("clear-all-chips").addEventListener("click", () => {
            selectedModels.clear();
            container.querySelectorAll(".model-chip").forEach(chip => {
                chip.classList.remove("active");
                chip.style.background = "";
                chip.style.borderColor = "";
            });
            if (chartsInitialized.history) updateHistoryChart();
        });

        // Price type toggle
        document.querySelectorAll(".toggle-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                historyPriceType = btn.dataset.type;
                if (chartsInitialized.history) updateHistoryChart();
            });
        });
    }

    // --- Price History Chart (stepped line) ---
    function initHistoryChart() {
        const ctx = document.getElementById("history-chart").getContext("2d");
        historyChart = new Chart(ctx, {
            type: "line",
            data: { datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "nearest", intersect: false },
                scales: {
                    x: {
                        type: "time",
                        time: { unit: "month", tooltipFormat: "MMM yyyy" },
                        title: { display: true, text: "Date" },
                        grid: { color: "#21262d" }
                    },
                    y: {
                        title: { display: true, text: "Price ($/1M tokens)" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ctx.dataset.label + ": $" + ctx.parsed.y.toFixed(2)
                        }
                    }
                }
            }
        });
        chartsInitialized.history = true;
        updateHistoryChart();
    }

    function updateHistoryChart() {
        const datasets = [];
        const isBoth = historyPriceType === "both";

        for (const entry of historyData) {
            const key = entry.provider + ":" + entry.model;
            if (!selectedModels.has(key)) continue;

            const color = HEX_COLORS[entry.provider] || "#58a6ff";
            const priceKeys = isBoth ? ["input_price", "output_price"] : [historyPriceType];

            for (const priceKey of priceKeys) {
                const isOutput = priceKey === "output_price";
                const points = entry.history.map(h => ({
                    x: h.date,
                    y: h[priceKey]
                }));

                // Extend last price to today for visual continuity
                if (points.length) {
                    points.push({ x: new Date().toISOString().slice(0, 10), y: points[points.length - 1].y });
                }

                datasets.push({
                    label: isBoth ? entry.model + (isOutput ? " (out)" : " (in)") : entry.model,
                    data: points,
                    borderColor: color,
                    backgroundColor: color + "33",
                    stepped: "before",
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 2,
                    borderDash: isOutput && isBoth ? [5, 3] : [],
                    fill: false
                });
            }
        }

        historyChart.data.datasets = datasets;
        historyChart.options.scales.y.title.text = isBoth ? "Price ($/1M tokens)"
            : (historyPriceType === "input_price" ? "Input" : "Output") + " Price ($/1M tokens)";
        historyChart.update();
        updatePriceChangeSummary();
    }

    // --- Comparison Chart (horizontal bar) ---
    function initCompareChart() {
        const ctx = document.getElementById("compare-chart").getContext("2d");
        compareChart = new Chart(ctx, {
            type: "bar",
            data: { labels: [], datasets: [] },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: "Price ($/1M tokens)" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    },
                    y: {
                        grid: { color: "#21262d" }
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ctx.dataset.label + ": $" + ctx.parsed.x.toFixed(2)
                        }
                    }
                }
            }
        });
        chartsInitialized.compare = true;
        updateCompareChart();
    }

    function updateCompareChart() {
        const rows = filtered();
        // Sort by input price ascending for chart readability
        const sorted = [...rows].sort((a, b) => a.input_price - b.input_price);
        const labels = sorted.map(m => m.model);
        const bgColors = sorted.map(m => HEX_COLORS[m.provider] || "#58a6ff");

        compareChart.data.labels = labels;
        compareChart.data.datasets = [
            {
                label: "Input $/1M",
                data: sorted.map(m => m.input_price),
                backgroundColor: bgColors.map(c => c + "cc"),
                borderColor: bgColors,
                borderWidth: 1
            },
            {
                label: "Output $/1M",
                data: sorted.map(m => m.output_price),
                backgroundColor: bgColors.map(c => c + "55"),
                borderColor: bgColors,
                borderWidth: 1
            }
        ];
        // Adjust height for number of models
        const canvas = document.getElementById("compare-chart");
        const minH = Math.max(400, sorted.length * 40);
        canvas.parentElement.style.height = minH + "px";
        compareChart.resize();
        compareChart.update();
    }

    // --- Price Change Summary ---
    function updatePriceChangeSummary() {
        const container = document.getElementById("price-change-summary");
        const priceKey = historyPriceType === "both" ? "input_price" : historyPriceType;
        const cards = [];

        for (const entry of historyData) {
            const key = entry.provider + ":" + entry.model;
            if (!selectedModels.has(key)) continue;
            if (entry.history.length < 2) continue;

            const oldest = entry.history[0];
            const newest = entry.history[entry.history.length - 1];
            const oldP = oldest[priceKey];
            const newP = newest[priceKey];
            const pctChange = oldP === 0 ? 0 : ((newP - oldP) / oldP) * 100;
            const dir = pctChange < -0.5 ? "down" : pctChange > 0.5 ? "up" : "flat";
            const sign = pctChange > 0 ? "+" : "";

            cards.push(`<div class="change-card">
                <span class="model-name">${entry.model}</span>
                <span class="change-value ${dir}">${sign}${pctChange.toFixed(1)}%</span>
                <span class="change-detail">$${oldP.toFixed(2)} → $${newP.toFixed(2)}</span>
            </div>`);
        }

        container.innerHTML = cards.length ? cards.join("") : "";
    }

    // --- Compare sub-tab switching ---
    let scatterChart = null;
    let providerChart = null;
    let ratioChart = null;

    document.querySelectorAll(".compare-sub-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".compare-sub-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".compare-view").forEach(v => v.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("compare-" + btn.dataset.view).classList.add("active");

            // Lazy-init sub-charts
            if (btn.dataset.view === "scatter" && !scatterChart && data.length) initScatterChart();
            if (btn.dataset.view === "provider" && !providerChart && data.length) initProviderChart();
            if (btn.dataset.view === "ratio" && !ratioChart && data.length) initRatioChart();
        });
    });

    // --- Scatter Plot ---
    function initScatterChart() {
        const ctx = document.getElementById("scatter-chart").getContext("2d");
        const rows = filtered();
        const pointData = rows.map(m => ({
            x: m.input_price,
            y: m.output_price,
            label: m.model,
            provider: m.provider
        }));

        // Group by provider for legend
        const providers = [...new Set(rows.map(m => m.provider))];
        const datasets = providers.map(p => ({
            label: p,
            data: pointData.filter(d => d.provider === p).map(d => ({ x: d.x, y: d.y })),
            backgroundColor: (HEX_COLORS[p] || "#58a6ff") + "cc",
            borderColor: HEX_COLORS[p] || "#58a6ff",
            pointRadius: 6,
            pointHoverRadius: 9,
            // Store labels for tooltip
            modelLabels: pointData.filter(d => d.provider === p).map(d => d.label)
        }));

        scatterChart = new Chart(ctx, {
            type: "scatter",
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: "Input Price ($/1M tokens)" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    },
                    y: {
                        title: { display: true, text: "Output Price ($/1M tokens)" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const ds = ctx.dataset;
                                const name = ds.modelLabels ? ds.modelLabels[ctx.dataIndex] : "";
                                return name + ": $" + ctx.parsed.x.toFixed(2) + " in / $" + ctx.parsed.y.toFixed(2) + " out";
                            }
                        }
                    }
                }
            }
        });
    }

    // --- By Provider grouped bar chart ---
    function initProviderChart() {
        const ctx = document.getElementById("provider-chart").getContext("2d");
        const rows = filtered();

        // Compute averages per provider
        const provMap = {};
        for (const m of rows) {
            if (!provMap[m.provider]) provMap[m.provider] = { sumIn: 0, sumOut: 0, count: 0 };
            provMap[m.provider].sumIn += m.input_price;
            provMap[m.provider].sumOut += m.output_price;
            provMap[m.provider].count++;
        }
        const providers = Object.keys(provMap).sort();
        const avgIn = providers.map(p => provMap[p].sumIn / provMap[p].count);
        const avgOut = providers.map(p => provMap[p].sumOut / provMap[p].count);
        const bgColors = providers.map(p => HEX_COLORS[p] || "#58a6ff");

        providerChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: providers,
                datasets: [
                    {
                        label: "Avg Input $/1M",
                        data: avgIn,
                        backgroundColor: bgColors.map(c => c + "cc"),
                        borderColor: bgColors,
                        borderWidth: 1
                    },
                    {
                        label: "Avg Output $/1M",
                        data: avgOut,
                        backgroundColor: bgColors.map(c => c + "55"),
                        borderColor: bgColors,
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { grid: { color: "#21262d" } },
                    y: {
                        title: { display: true, text: "Avg Price ($/1M tokens)" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: { position: "top", labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ctx.dataset.label + ": $" + ctx.parsed.y.toFixed(2)
                        }
                    }
                }
            }
        });
    }

    // --- I/O Ratio chart ---
    function initRatioChart() {
        const ctx = document.getElementById("ratio-chart").getContext("2d");
        const rows = filtered().filter(m => m.input_price > 0);
        const withRatio = rows.map(m => ({
            model: m.model,
            provider: m.provider,
            ratio: m.output_price / m.input_price
        })).sort((a, b) => a.ratio - b.ratio);

        const labels = withRatio.map(m => m.model);
        const bgColors = withRatio.map(m => (HEX_COLORS[m.provider] || "#58a6ff") + "cc");
        const borderColors = withRatio.map(m => HEX_COLORS[m.provider] || "#58a6ff");

        ratioChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Output / Input Ratio",
                    data: withRatio.map(m => m.ratio),
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: "Output / Input Price Ratio" },
                        grid: { color: "#21262d" },
                        beginAtZero: true
                    },
                    y: { grid: { color: "#21262d" } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => "Ratio: " + ctx.parsed.x.toFixed(2) + "x"
                        }
                    }
                }
            }
        });

        // Adjust height
        const canvas = document.getElementById("ratio-chart");
        const minH = Math.max(400, withRatio.length * 35);
        canvas.parentElement.style.height = minH + "px";
        ratioChart.resize();
    }

    // --- 7-Day Trend Charts ---
    let sevenDayCharts = [];
    let selectedModels7day = new Set();
    let sevenDayPriceType = "input_price";

    function buildSevenDayChips() {
        const container = document.getElementById("model-chips-7day");
        // Default: select all models
        sevenDayData.forEach(m => selectedModels7day.add(m.provider + ":" + m.model));

        container.innerHTML = sevenDayData.map(m => {
            const key = m.provider + ":" + m.model;
            const color = HEX_COLORS[m.provider] || "#58a6ff";
            return `<button class="model-chip active" data-key="${key}"
                style="background:${color};border-color:${color}">${m.model}</button>`;
        }).join("");

        container.querySelectorAll(".model-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const key = chip.dataset.key;
                const color = HEX_COLORS[key.split(":")[0]] || "#58a6ff";
                if (selectedModels7day.has(key)) {
                    selectedModels7day.delete(key);
                    chip.classList.remove("active");
                    chip.style.background = "";
                    chip.style.borderColor = "";
                } else {
                    selectedModels7day.add(key);
                    chip.classList.add("active");
                    chip.style.background = color;
                    chip.style.borderColor = color;
                }
                if (chartsInitialized.sevenDay) renderSevenDayGrid();
            });
        });

        document.getElementById("select-all-7day").addEventListener("click", () => {
            sevenDayData.forEach(m => selectedModels7day.add(m.provider + ":" + m.model));
            container.querySelectorAll(".model-chip").forEach(chip => {
                const color = HEX_COLORS[chip.dataset.key.split(":")[0]] || "#58a6ff";
                chip.classList.add("active");
                chip.style.background = color;
                chip.style.borderColor = color;
            });
            if (chartsInitialized.sevenDay) renderSevenDayGrid();
        });

        document.getElementById("clear-all-7day").addEventListener("click", () => {
            selectedModels7day.clear();
            container.querySelectorAll(".model-chip").forEach(chip => {
                chip.classList.remove("active");
                chip.style.background = "";
                chip.style.borderColor = "";
            });
            if (chartsInitialized.sevenDay) renderSevenDayGrid();
        });

        document.querySelectorAll("[data-type-7day]").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("[data-type-7day]").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                sevenDayPriceType = btn.dataset.type7day;
                if (chartsInitialized.sevenDay) renderSevenDayGrid();
            });
        });
    }

    function initSevenDayCharts() {
        chartsInitialized.sevenDay = true;
        renderSevenDayGrid();
    }

    function renderSevenDayGrid() {
        const grid = document.getElementById("seven-day-grid");
        // Destroy old charts
        sevenDayCharts.forEach(c => c.destroy());
        sevenDayCharts = [];

        const selected = sevenDayData.filter(m => selectedModels7day.has(m.provider + ":" + m.model));
        if (!selected.length) {
            grid.innerHTML = '<p style="color:#8b949e;text-align:center;padding:2rem;">Select models above to view 7-day trends.</p>';
            return;
        }

        grid.innerHTML = selected.map((m, i) => {
            const latest = m.daily_prices[m.daily_prices.length - 1];
            const priceVal = latest ? latest[sevenDayPriceType] : 0;
            const priceLabel = sevenDayPriceType === "input_price" ? "Input" : "Output";
            return `<div class="seven-day-card">
                <div class="seven-day-card-header">
                    <span class="model-label"><span class="badge badge-${COLORS[m.provider] || "openai"}">${m.provider}</span> ${m.model}</span>
                    <span class="price-label">${priceLabel}: $${priceVal.toFixed(2)}/1M</span>
                </div>
                <canvas id="seven-day-chart-${i}"></canvas>
            </div>`;
        }).join("");

        selected.forEach((m, i) => {
            const ctx = document.getElementById("seven-day-chart-" + i).getContext("2d");
            const color = HEX_COLORS[m.provider] || "#58a6ff";
            const prices = m.daily_prices.map(d => d[sevenDayPriceType]);
            const labels = m.daily_prices.map(d => d.date);

            // Calculate min/max for tighter y-axis
            const minP = Math.min(...prices);
            const maxP = Math.max(...prices);
            const padding = (maxP - minP) * 0.2 || maxP * 0.1 || 0.1;

            const chart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        data: prices,
                        borderColor: color,
                        backgroundColor: color + "22",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        pointBackgroundColor: color,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => items[0].label,
                                label: (ctx) => "$" + ctx.parsed.y.toFixed(2) + " / 1M tokens"
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: "#21262d" },
                            ticks: { maxTicksLimit: 7, font: { size: 10 } }
                        },
                        y: {
                            grid: { color: "#21262d" },
                            min: Math.max(0, minP - padding),
                            max: maxP + padding,
                            ticks: {
                                callback: (v) => "$" + v.toFixed(2),
                                font: { size: 10 }
                            }
                        }
                    }
                }
            });
            sevenDayCharts.push(chart);
        });
    }

    // --- Refresh data ---
    async function refreshData() {
        refreshBtn.classList.add("loading");
        refreshBtn.querySelector(".refresh-label").textContent = "Refreshing...";
        try {
            const [pricesRes, historyRes, sevenDayRes] = await Promise.all([
                fetch("/api/prices"),
                fetch("/api/price-history"),
                fetch("/api/prices-7day")
            ]);
            data = await pricesRes.json();
            historyData = await historyRes.json();
            sevenDayData = await sevenDayRes.json();

            if (data.length) {
                updatedEl.textContent = "Last updated: " + new Date().toLocaleString();
            }

            // Destroy existing charts
            if (historyChart) { historyChart.destroy(); historyChart = null; }
            if (compareChart) { compareChart.destroy(); compareChart = null; }
            if (scatterChart) { scatterChart.destroy(); scatterChart = null; }
            if (providerChart) { providerChart.destroy(); providerChart = null; }
            if (ratioChart) { ratioChart.destroy(); ratioChart = null; }
            sevenDayCharts.forEach(c => c.destroy());
            sevenDayCharts = [];

            chartsInitialized = { history: false, compare: false, sevenDay: false };

            // Rebuild UI
            selectedModels.clear();
            selectedModels7day.clear();
            buildModelChips();
            buildSevenDayChips();
            render();

            // Re-init charts for the active tab
            const activeTab = document.querySelector(".tab-btn.active");
            if (activeTab) {
                if (activeTab.dataset.tab === "tab-7day" && sevenDayData.length) initSevenDayCharts();
                if (activeTab.dataset.tab === "tab-history" && historyData.length) initHistoryChart();
                if (activeTab.dataset.tab === "tab-compare" && data.length) initCompareChart();
            }
        } catch (e) {
            console.error("Refresh failed:", e);
            updatedEl.textContent = "Refresh failed. Please try again.";
        } finally {
            refreshBtn.classList.remove("loading");
            refreshBtn.querySelector(".refresh-label").textContent = "Refresh Prices";
        }
    }

    refreshBtn.addEventListener("click", refreshData);

    // --- Row-click modal for 7-day price chart ---
    const modalOverlay = document.getElementById("modal-overlay");
    const modalTitle = document.getElementById("modal-title");
    const modalClose = document.getElementById("modal-close");
    let modalChart = null;
    let modalPriceType = "input_price";
    let modalProvider = null;
    let modalModel = null;

    function openModal(provider, model) {
        modalProvider = provider;
        modalModel = model;
        modalPriceType = "input_price";

        // Reset toggle buttons
        document.querySelectorAll("[data-modal-type]").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.modalType === "input_price");
        });

        const color = HEX_COLORS[provider] || "#58a6ff";
        modalTitle.innerHTML = `<span class="badge badge-${COLORS[provider] || "openai"}">${provider}</span> ${model} — 7-Day Price`;
        modalOverlay.classList.add("active");
        renderModalChart();
    }

    function renderModalChart() {
        const entry = sevenDayData.find(m => m.provider === modalProvider && m.model === modalModel);
        if (!entry) return;

        if (modalChart) { modalChart.destroy(); modalChart = null; }

        const ctx = document.getElementById("modal-chart").getContext("2d");
        const color = HEX_COLORS[modalProvider] || "#58a6ff";
        const isBoth = modalPriceType === "both";
        const datasets = [];

        const priceKeys = isBoth ? ["input_price", "output_price"] : [modalPriceType];
        let allPrices = [];

        for (const priceKey of priceKeys) {
            const isOutput = priceKey === "output_price";
            const prices = entry.daily_prices.map(d => d[priceKey]);
            allPrices = allPrices.concat(prices);

            datasets.push({
                label: isBoth ? (isOutput ? "Output $/1M" : "Input $/1M") : (priceKey === "input_price" ? "Input $/1M" : "Output $/1M"),
                data: prices,
                borderColor: isOutput && isBoth ? color + "99" : color,
                backgroundColor: color + "22",
                fill: !isBoth,
                tension: 0.35,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: isOutput && isBoth ? color + "99" : color,
                borderWidth: 2,
                borderDash: isOutput && isBoth ? [5, 3] : []
            });
        }

        const labels = entry.daily_prices.map(d => d.date);
        const minP = Math.min(...allPrices);
        const maxP = Math.max(...allPrices);
        const padding = (maxP - minP) * 0.2 || maxP * 0.1 || 0.1;

        modalChart = new Chart(ctx, {
            type: "line",
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: isBoth, position: "top", labels: { usePointStyle: true, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => (ctx.dataset.label || "") + ": $" + ctx.parsed.y.toFixed(2)
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: "#21262d" },
                        ticks: { font: { size: 11 } }
                    },
                    y: {
                        grid: { color: "#21262d" },
                        min: Math.max(0, minP - padding),
                        max: maxP + padding,
                        ticks: {
                            callback: (v) => "$" + v.toFixed(2),
                            font: { size: 11 }
                        }
                    }
                }
            }
        });
    }

    function closeModal() {
        modalOverlay.classList.remove("active");
        if (modalChart) { modalChart.destroy(); modalChart = null; }
    }

    modalClose.addEventListener("click", closeModal);
    modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) closeModal();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modalOverlay.classList.contains("active")) closeModal();
    });

    document.querySelectorAll("[data-modal-type]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-modal-type]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            modalPriceType = btn.dataset.modalType;
            renderModalChart();
        });
    });

    load();
})();
