(function () {
    const COLORS = {
        OpenAI: "openai", Anthropic: "anthropic", DeepSeek: "deepseek",
        Google: "google", Mistral: "mistral", Meta: "meta"
    };

    let data = [];
    let sortKey = "input_price";
    let sortDir = "asc";
    let activeProvider = null;

    const tbody = document.getElementById("table-body");
    const search = document.getElementById("search");
    const filtersEl = document.getElementById("filters");
    const updatedEl = document.getElementById("updated");

    // --- Data loading ---
    async function load() {
        const pricesRes = await fetch("/api/prices");
        data = await pricesRes.json();

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

        render();
    }

    // --- Table logic ---
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
            return `<tr>
                <td><span class="badge badge-${cls}">${m.provider}</span></td>
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
})();
