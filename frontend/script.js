/**
 * 主页脚本 — LLM 定价仪表盘
 *
 * 功能：
 * - 从 /api/prices 加载定价数据并渲染可排序、可筛选的表格
 * - 支持按平台、供应商筛选和关键词搜索
 * - 点击列头可按该列排序（升序→降序→恢复默认排序）
 * - 点击行跳转到该模型的价格历史页面
 * - Refresh 按钮触发手动刷新并自动下载 Excel 文件
 * - 每 10 分钟自动刷新数据
 */
(function () {
    // 供应商名 → CSS 类名后缀（用于徽章颜色）
    const COLORS = {
        OpenAI: "openai", Anthropic: "anthropic", DeepSeek: "deepseek",
        Google: "google", Mistral: "mistral", Meta: "meta", Qwen: "qwen"
    };

    // 平台标识 → 显示名称
    const PLATFORM_LABELS = {
        openrouter: "OpenRouter",
        yunwu: "Yunwu 云雾"
    };

    let data = [];
    let sortKey = null;    // 当前排序列，null 表示使用后端默认排序
    let sortDir = "asc";   // 排序方向：asc / desc
    let activeProvider = null;   // 当前选中的供应商筛选
    let activePlatform = null;   // 当前选中的平台筛选

    const tbody = document.getElementById("table-body");
    const search = document.getElementById("search");
    const filtersEl = document.getElementById("filters");
    const platformFiltersEl = document.getElementById("platform-filters");
    const updatedEl = document.getElementById("updated");
    const refreshBtn = document.getElementById("refresh-btn");

    // 点击表格行跳转到该模型的价格历史页面
    tbody.addEventListener("click", (event) => {
        const row = event.target.closest("tr[data-slug]");
        if (!row) return;
        const slug = row.dataset.slug;
        window.location.href = `/${slug}`;
    });

    async function load() {
        // 加载定价数据，附加 _idx 保留后端排序顺序
        const pricesRes = await fetch("/api/prices");
        data = (await pricesRes.json()).map((d, i) => ({ ...d, _idx: i }));

        // 更新页面底部的"最后更新时间"显示
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

        // 生成平台筛选按钮
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

        // 生成供应商筛选按钮
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

    // Refresh 按钮：手动刷新价格并下载 Excel
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
        // 应用平台、供应商、搜索筛选，然后按当前排序规则排序
        let d = data;
        if (activePlatform) d = d.filter(m => m.platform === activePlatform);
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

    function fmt(n) { return "$" + n.toFixed(2); }  // 格式化价格
    function fmtCtx(n) {  // 格式化上下文窗口大小
        if (!n) return "-";
        if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
        return (n / 1000).toFixed(0) + "K";
    }

    function render() {
        // 渲染表格：生成带平台/供应商徽章的行
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

    // 列头点击排序：升序 → 降序 → 恢复默认排序
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

    search.addEventListener("input", render);  // 搜索框实时筛选

    load();  // 页面加载时立即获取数据
    setInterval(load, 10 * 60 * 1000);  // 每 10 分钟自动刷新
})();
