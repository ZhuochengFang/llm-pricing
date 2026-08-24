/**
 * 历史价格页面脚本
 *
 * 功能：
 * - 通过 URL slug（如 /gpt-4o）或查询参数（?provider=...&model=...）确定目标模型
 * - 从 /api/history 加载价格历史数据
 * - 使用 Chart.js 绘制多平台价格趋势折线图
 * - 每 10 分钟自动刷新图表
 */
(function () {
    const PLATFORM_LABELS = { official: "Official", openrouter: "OpenRouter", yunwu: "Yunwu", moyu: "Moyu" };
    const titleEl = document.getElementById("model-title");
    const statusEl = document.getElementById("status");
    const canvas = document.getElementById("history-chart");
    let chartInstance = null;

    // 从 URL 路径或查询参数中提取模型信息
    const pathSlug = window.location.pathname.replace(/^\/+/, "").split("/")[0];
    const params = new URLSearchParams(window.location.search);
    const providerParam = params.get("provider");
    const modelParam = params.get("model");

    const slug = pathSlug && pathSlug !== "history" ? pathSlug : null;
    let provider = providerParam ? decodeURIComponent(providerParam) : null;
    let model = modelParam ? decodeURIComponent(modelParam) : null;

    function roundToMinute(ts) {
        // 将时间戳对齐到分钟，用于跨平台数据时间轴合并
        var d = new Date(ts);
        d.setSeconds(0, 0);
        return d.getTime();
    }

    async function loadHistory() {
        // 加载历史数据并渲染 Chart.js 折线图
        let historyByPlatform = {};

        if (slug) {
            const resp = await fetch(`/api/history/${encodeURIComponent(slug)}`);
            if (!resp.ok) {
                statusEl.textContent = "Unknown model slug.";
                return;
            }
            const payload = await resp.json();
            provider = payload.provider;
            model = payload.model;
            historyByPlatform = payload.history || {};
            titleEl.textContent = `${provider} / ${model}`;
        } else if (provider && model) {
            titleEl.textContent = `${provider} / ${model}`;
            const resp = await fetch(
                `/api/history?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            historyByPlatform = await resp.json();
        } else {
            statusEl.textContent = "Missing model information.";
            return;
        }

        const platforms = Object.keys(historyByPlatform).filter(
            p => historyByPlatform[p] && historyByPlatform[p].length
        );
        if (!platforms.length) {
            statusEl.textContent = "No auto-refresh history yet. Check back after the next refresh.";
            return;
        }

        const multiPlatform = platforms.length > 1;

        // 合并所有平台的时间戳，对齐到分钟以便生成统一的 X 轴
        const timelineSet = new Set();
        for (const plat of platforms) {
            for (const p of historyByPlatform[plat]) {
                timelineSet.add(roundToMinute(p.timestamp));
            }
        }
        const timeline = [...timelineSet].sort((a, b) => a - b);

        const labels = timeline.map(t => new Date(t).toLocaleString(undefined, {
            month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"
        }));

        // 每个平台的线条颜色：输入价格 / 输出价格
        const COLORS = {
            official:   { input: "#22c55e", output: "#eab308" },
            openrouter: { input: "#3b82f6", output: "#ef4444" },
            yunwu:      { input: "#a855f7", output: "#06b6d4" },
            moyu:       { input: "#f97316", output: "#fb923c" },
        };
        const datasets = [];

        for (const plat of platforms) {
            const points = historyByPlatform[plat];
            const byMinute = {};
            for (const p of points) byMinute[roundToMinute(p.timestamp)] = p;

            const inputData = timeline.map(t => byMinute[t] ? byMinute[t].input_price : null);
            const outputData = timeline.map(t => byMinute[t] ? byMinute[t].output_price : null);

            const colors = COLORS[plat] || COLORS.openrouter;
            const prefix = multiPlatform ? (PLATFORM_LABELS[plat] || plat) + " " : "";

            datasets.push({
                label: prefix + "Input $/1M",
                data: inputData,
                borderColor: colors.input,
                backgroundColor: colors.input + "33",
                tension: 0.2,
                pointRadius: 3,
                spanGaps: true,
                borderDash: multiPlatform && plat !== platforms[0] ? [6, 3] : [],
            });
            datasets.push({
                label: prefix + "Output $/1M",
                data: outputData,
                borderColor: colors.output,
                backgroundColor: colors.output + "33",
                tension: 0.2,
                pointRadius: 3,
                spanGaps: true,
                borderDash: multiPlatform && plat !== platforms[0] ? [6, 3] : [],
            });
        }

        Chart.defaults.color = "#e1e4e8";
        Chart.defaults.borderColor = "#30363d";

        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas, {
            type: "line",
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        ticks: {
                            callback: value => `$${Number(value).toFixed(2)}`
                        }
                    }
                }
            }
        });

        const latestTs = Math.max(...timeline);
        statusEl.textContent = `Latest update: ${new Date(latestTs).toLocaleString()}`;
    }

    // 页面加载时获取历史数据，之后每 10 分钟自动刷新
    loadHistory().catch(() => {
        statusEl.textContent = "Failed to load history.";
    });
    setInterval(() => {
        loadHistory().catch(() => {
            statusEl.textContent = "Failed to load history.";
        });
    }, 10 * 60 * 1000);
})();
