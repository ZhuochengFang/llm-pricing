/**
 * 主页脚本 — LLM 定价仪表盘
 */
(function () {
    const COLORS = {
        OpenAI: "openai", Anthropic: "anthropic", DeepSeek: "deepseek",
        Google: "google", Mistral: "mistral", Meta: "meta", Qwen: "qwen",
        Grok: "grok", MiniMax: "minimax", ByteDance: "bytedance",
        Jimeng: "jimeng", Zhipu: "zhipu"
    };

    const PLATFORM_LABELS = {
        openrouter: "OpenRouter",
        yunwu: "Yunwu 云雾"
    };

    const TYPE_LABELS = {
        text: "文本模型",
        image: "图像模型",
        video: "视频模型"
    };

    let data = [];
    let sortKey = null;
    let sortDir = "asc";
    let activeProvider = null;
    let activePlatform = null;
    let activeType = null;

    const tbody = document.getElementById("table-body");
    const search = document.getElementById("search");
    const filtersEl = document.getElementById("filters");
    const platformFiltersEl = document.getElementById("platform-filters");
    const typeFiltersEl = document.getElementById("type-filters");
    const updatedEl = document.getElementById("updated");
    const refreshBtn = document.getElementById("refresh-btn");
    const resetProviderBtn = document.getElementById("reset-provider");

    tbody.addEventListener("click", (event) => {
        const row = event.target.closest("tr[data-slug]");
        if (!row) return;
        window.location.href = `/${row.dataset.slug}`;
    });

    function countBy(arr, key, value) {
        if (value === null) return arr.length;
        return arr.filter(d => d[key] === value || (key === "model_type" && !d[key] && value === "text")).length;
    }

    function buildFilterBtn(value, label, count, isActive, extraClass) {
        const cls = ["fbtn"];
        if (isActive) cls.push("fbtn-active");
        if (extraClass) cls.push(extraClass);
        if (count === 0) cls.push("fbtn-disabled");
        return `<button class="${cls.join(" ")}" data-value="${value ?? ""}">`
            + `<span class="fbtn-label">${label}</span>`
            + `<span class="fbtn-count">${count}</span>`
            + `</button>`;
    }

    function currentFiltered() {
        let d = data;
        if (activePlatform) d = d.filter(m => m.platform === activePlatform);
        if (activeType) d = d.filter(m => (m.model_type || "text") === activeType);
        if (activeProvider) d = d.filter(m => m.provider === activeProvider);
        return d;
    }

    function rebuildFilters() {
        // Platform filters — count with other filters applied (except platform)
        const platBase = data.filter(d =>
            (!activeProvider || d.provider === activeProvider) &&
            (!activeType || (d.model_type || "text") === activeType)
        );
        const platforms = [...new Set(data.map(d => d.platform))];
        platformFiltersEl.innerHTML =
            buildFilterBtn(null, "全部", platBase.length, !activePlatform) +
            platforms.map(p =>
                buildFilterBtn(p, PLATFORM_LABELS[p] || p,
                    platBase.filter(d => d.platform === p).length,
                    activePlatform === p)
            ).join("");

        // Provider filters — count with other filters applied (except provider)
        const provBase = data.filter(d =>
            (!activePlatform || d.platform === activePlatform) &&
            (!activeType || (d.model_type || "text") === activeType)
        );
        const providers = [...new Set(data.map(d => d.provider))];
        filtersEl.innerHTML =
            buildFilterBtn(null, "全部供应商", provBase.length, !activeProvider) +
            providers.map(p =>
                buildFilterBtn(p, p,
                    provBase.filter(d => d.provider === p).length,
                    activeProvider === p,
                    COLORS[p] ? `fbtn-prov-${COLORS[p]}` : "")
            ).join("");

        // Type filters — count with other filters applied (except type)
        const typeBase = data.filter(d =>
            (!activePlatform || d.platform === activePlatform) &&
            (!activeProvider || d.provider === activeProvider)
        );
        const types = [...new Set(data.map(d => d.model_type || "text"))];
        typeFiltersEl.innerHTML =
            buildFilterBtn(null, "全部类型", typeBase.length, !activeType) +
            types.map(t =>
                buildFilterBtn(t, TYPE_LABELS[t] || t,
                    typeBase.filter(d => (d.model_type || "text") === t).length,
                    activeType === t,
                    `fbtn-type-${t}`)
            ).join("");
    }

    function attachFilterEvents(container, getActive, setActive) {
        container.addEventListener("click", (e) => {
            const btn = e.target.closest(".fbtn");
            if (!btn || btn.classList.contains("fbtn-disabled")) return;
            const val = btn.dataset.value || null;
            setActive(val === getActive() ? null : val);
            rebuildFilters();
            render();
        });
    }

    attachFilterEvents(platformFiltersEl,
        () => activePlatform, v => activePlatform = v);
    attachFilterEvents(filtersEl,
        () => activeProvider, v => activeProvider = v);
    attachFilterEvents(typeFiltersEl,
        () => activeType, v => activeType = v);

    resetProviderBtn.addEventListener("click", () => {
        activeProvider = null;
        activePlatform = null;
        activeType = null;
        rebuildFilters();
        render();
    });

    async function load() {
        const pricesRes = await fetch("/api/prices");
        data = (await pricesRes.json()).map((d, i) => ({ ...d, _idx: i }));

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

        rebuildFilters();
        render();
    }

    refreshBtn.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing...";
        try {
            await fetch("/api/refresh", { method: "POST" });
            await load();
            const exportParams = new URLSearchParams();
            if (activeProvider) exportParams.set("provider", activeProvider);
            if (activePlatform) exportParams.set("platform", activePlatform);
            if (activeType) exportParams.set("model_type", activeType);
            const exportQuery = exportParams.toString();
            const resp = await fetch("/api/export" + (exportQuery ? "?" + exportQuery : ""));
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
        if (activeType) d = d.filter(m => (m.model_type || "text") === activeType);
        if (activeProvider) d = d.filter(m => m.provider === activeProvider);
        const q = search.value.toLowerCase();
        if (q) d = d.filter(m =>
            m.provider.toLowerCase().includes(q) ||
            m.model.toLowerCase().includes(q) ||
            m.platform.toLowerCase().includes(q)
        );
        if (sortKey) {
            d.sort((a, b) => {
                let va = a[sortKey], vb = b[sortKey];
                if (typeof va === "string") { va = va.toLowerCase(); vb = vb.toLowerCase(); }
                if (va < vb) return sortDir === "asc" ? -1 : 1;
                if (va > vb) return sortDir === "asc" ? 1 : -1;
                return 0;
            });
        } else {
            d.sort((a, b) => a._idx - b._idx);
        }
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
            const mtype = m.model_type || "text";
            const typeLabel = TYPE_LABELS[mtype] || mtype;
            const unreliable = mtype !== "text" && m.output_price === 0;
            const rowCls = unreliable ? "row-link row-unreliable" : "row-link";
            const refTag = unreliable ? ' <span class="price-ref">（仅供参考）</span>' : "";
            return `<tr class="${rowCls}" data-slug="${m.slug}">
                <td><span class="badge ${platCls}">${platLabel}</span></td>
                <td><span class="badge badge-${provCls}">${m.provider}</span></td>
                <td>${m.model}</td>
                <td><span class="badge badge-type-${mtype}">${typeLabel}</span></td>
                <td class="price">${fmt(m.input_price)}${refTag}</td>
                <td class="price">${fmt(m.output_price)}${refTag}</td>
                <td>${fmtCtx(m.context_window)}</td>
            </tr>`;
        }).join("");
    }

    document.querySelectorAll("th[data-sort]").forEach(th => {
        th.addEventListener("click", () => {
            const key = th.dataset.sort;
            if (sortKey === key) {
                if (sortDir === "asc") {
                    sortDir = "desc";
                } else {
                    sortKey = null;
                    sortDir = "asc";
                }
            } else {
                sortKey = key;
                sortDir = "asc";
            }
            document.querySelectorAll("th").forEach(t => t.classList.remove("asc", "desc"));
            if (sortKey) th.classList.add(sortDir);
            render();
        });
    });

    search.addEventListener("input", render);
    load();
    setInterval(load, 10 * 60 * 1000);
})();
