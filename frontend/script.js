(function () {
    const COLORS = {
        OpenAI: "openai", Anthropic: "anthropic", DeepSeek: "deepseek",
        Google: "google", Mistral: "mistral", Meta: "meta", Qwen: "qwen"
    };

    const PLATFORM_LABELS = {
        openrouter: "OpenRouter",
        yunwu: "Yunwu 云雾"
    };

    let data = [];
    let sortKey = "input_price";
    let sortDir = "asc";
    let activeProvider = null;
    let activePlatform = null;

    const tbody = document.getElementById("table-body");
    const search = document.getElementById("search");
    const filtersEl = document.getElementById("filters");
    const platformFiltersEl = document.getElementById("platform-filters");
    const updatedEl = document.getElementById("updated");
    const refreshBtn = document.getElementById("refresh-btn");

    tbody.addEventListener("click", (event) => {
        const row = event.target.closest("tr[data-slug]");
        if (!row) return;
        const slug = row.dataset.slug;
        window.location.href = `/${slug}`;
    });

    async function load() {
        const pricesRes = await fetch("/api/prices");
        data = await pricesRes.json();

        if (data.length) {
            const orItems = data.filter(d => d.platform === "openrouter");
            const ywItems = data.filter(d => d.platform === "yunwu");
            let parts = [];
            if (orItems.length) {
                const src = orItems[0].source || "static";
                const cls = src === "live" ? "source-live" : "source-static";
                parts.push(`OpenRouter: ${new Date(orItems[0].updated_at).toLocaleString()} <span class="source-badge ${cls}">${src}</span>`);
            }
            if (ywItems.length && ywItems[0].updated_at) {
                const src = ywItems[0].source || "none";
                const cls = src === "live" ? "source-live" : "source-static";
                parts.push(`Yunwu: ${new Date(ywItems[0].updated_at).toLocaleString()} <span class="source-badge ${cls}">${src}</span>`);
            }
            updatedEl.innerHTML = "Last updated — " + parts.join(" &nbsp;|&nbsp; ");
        }

        // Platform filter buttons
        const platforms = [...new Set(data.map(d => d.platform))];
        platformFiltersEl.innerHTML = platforms.map(p =>
            `<button class="filter-btn platform-filter" data-platform="${p}">${PLATFORM_LABELS[p] || p}</button>`
        ).join("");
        platformFiltersEl.querySelectorAll(".platform-filter").forEach(btn => {
            btn.addEventListener("click", () => {
                const p = btn.dataset.platform;
                activePlatform = activePlatform === p ? null : p;
                platformFiltersEl.querySelectorAll(".platform-filter").forEach(b => b.classList.remove("active"));
                if (activePlatform) btn.classList.add("active");
                render();
            });
        });

        // Provider filter buttons
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

        render();
    }

    refreshBtn.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing...";
        try {
            await fetch("/api/refresh", { method: "POST" });
            await load();
            const resp = await fetch("/api/export");
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "llm_pricing.xlsx";
            a.click();
            URL.revokeObjectURL(url);
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.textContent = "Refresh";
        }
    });

    function filtered() {
        let d = data;
        if (activePlatform) d = d.filter(m => m.platform === activePlatform);
        if (activeProvider) d = d.filter(m => m.provider === activeProvider);
        const q = search.value.toLowerCase();
        if (q) d = d.filter(m =>
            m.provider.toLowerCase().includes(q) ||
            m.model.toLowerCase().includes(q) ||
            m.platform.toLowerCase().includes(q)
        );
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
        if (!n) return "-";
        if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
        return (n / 1000).toFixed(0) + "K";
    }

    function render() {
        const rows = filtered();
        tbody.innerHTML = rows.map(m => {
            const provCls = COLORS[m.provider] || "openai";
            const platCls = m.platform === "yunwu" ? "badge-yunwu" : "badge-openrouter";
            const platLabel = PLATFORM_LABELS[m.platform] || m.platform;
            return `<tr class="row-link" data-slug="${m.slug}">
                <td><span class="badge ${platCls}">${platLabel}</span></td>
                <td><span class="badge badge-${provCls}">${m.provider}</span></td>
                <td>${m.model}</td>
                <td class="price">${fmt(m.input_price)}</td>
                <td class="price">${fmt(m.output_price)}</td>
                <td>${fmtCtx(m.context_window)}</td>
            </tr>`;
        }).join("");
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

    load();
    setInterval(load, 10 * 60 * 1000);
})();
