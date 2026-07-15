(function () {
    const titleEl = document.getElementById("model-title");
    const statusEl = document.getElementById("status");
    const canvas = document.getElementById("history-chart");
    let chartInstance = null;

    const pathSlug = window.location.pathname.replace(/^\/+/, "").split("/")[0];
    const params = new URLSearchParams(window.location.search);
    const providerParam = params.get("provider");
    const modelParam = params.get("model");

    const slug = pathSlug && pathSlug !== "history" ? pathSlug : null;
    let provider = providerParam ? decodeURIComponent(providerParam) : null;
    let model = modelParam ? decodeURIComponent(modelParam) : null;

    async function loadHistory() {
        let points = [];
        if (slug) {
            const resp = await fetch(`/api/history/${encodeURIComponent(slug)}`);
            if (!resp.ok) {
                statusEl.textContent = "Unknown model slug.";
                return;
            }
            const payload = await resp.json();
            provider = payload.provider;
            model = payload.model;
            points = payload.history || [];
            titleEl.textContent = `${provider} / ${model}`;
        } else if (provider && model) {
            titleEl.textContent = `${provider} / ${model}`;
            const resp = await fetch(
                `/api/history?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
            );
            points = await resp.json();
        } else {
            statusEl.textContent = "Missing model information.";
            return;
        }

        if (!points.length) {
            statusEl.textContent = "No auto-refresh history yet. Check back after the next refresh.";
            return;
        }

        const labels = points.map(p => new Date(p.timestamp).toLocaleString(undefined, {
            month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"
        }));
        const inputSeries = points.map(p => p.input_price);
        const outputSeries = points.map(p => p.output_price);

        Chart.defaults.color = "#e1e4e8";
        Chart.defaults.borderColor = "#30363d";

        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Input $/1M",
                        data: inputSeries,
                        borderColor: "#58a6ff",
                        backgroundColor: "rgba(88, 166, 255, 0.2)",
                        tension: 0.2,
                        pointRadius: 3
                    },
                    {
                        label: "Output $/1M",
                        data: outputSeries,
                        borderColor: "#f97316",
                        backgroundColor: "rgba(249, 115, 22, 0.2)",
                        tension: 0.2,
                        pointRadius: 3
                    }
                ]
            },
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

        const latest = points[points.length - 1];
        statusEl.textContent = `Latest update: ${new Date(latest.timestamp).toLocaleString()}`;
    }

    loadHistory().catch(() => {
        statusEl.textContent = "Failed to load history.";
    });
    setInterval(() => {
        loadHistory().catch(() => {
            statusEl.textContent = "Failed to load history.";
        });
    }, 10 * 60 * 1000);
})();
