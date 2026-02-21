(function () {
  const page = document.body?.dataset?.page || "";
  const ls = window.localStorage;
  const isFileProtocol = window.location.protocol === "file:";
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const defaultApiBase = isFileProtocol ? "http://localhost:5001" : "";

  function normalizeApiBase(base) {
    return (base || "").replace(/\/+$/, "");
  }

  function getApiBase() {
    const stored = normalizeApiBase(ls.getItem("investai_api_base") || "");
    if (!isLocalHost && (stored.includes("localhost") || stored.includes("127.0.0.1"))) {
      ls.removeItem("investai_api_base");
      return defaultApiBase;
    }
    return stored || defaultApiBase;
  }

  function setApiBase(base) {
    ls.setItem("investai_api_base", normalizeApiBase(base));
  }

  async function api(path, options = {}) {
    const res = await fetch(`${getApiBase()}${path}`, options);
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const body = ct.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) {
      const detail = body && body.error ? body.error : `${res.status}`;
      throw new Error(detail);
    }
    return body;
  }

  function scoreClass(score) {
    if (score >= 76) return "score-good";
    if (score >= 56) return "score-mid";
    return "score-bad";
  }

  function fmtMoney(v) {
    const n = Number(v || 0);
    if (!n) return "-";
    if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    return `$${n.toFixed(0)}`;
  }

  function getStoredMode() {
    return ls.getItem("investai_webmcp_mode") || "backend";
  }

  function addLog(msg, color) {
    const logs = document.getElementById("console-logs");
    if (!logs) return;
    const line = document.createElement("div");
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    if (color) line.style.color = color;
    logs.appendChild(line);
    logs.scrollTop = logs.scrollHeight;
  }

  function getWebMcp() {
    const nativeMcp = window.navigator.modelContext || window.mcp;
    if (nativeMcp) return nativeMcp;
    return {
      isSimulated: true,
      async registerTool() {},
      async executeTool(name, params) {
        await new Promise((r) => setTimeout(r, 350));
        if (name === "analyze_financials") return { score: 72, market_cap: 12000000000, source: "sim" };
        if (name === "check_founders") return { score: 78, reliability: 78, past_exits: 2, source: "sim" };
        if (name === "get_social_sentiment") return { score: 69, sentiment: "BULLISH", intensity: 69, source: "sim" };
        return { ok: true, params };
      },
    };
  }

  async function registerWebMcpTools() {
    const mcp = getWebMcp();
    try {
      if (typeof mcp.registerTool !== "function") return;
      await mcp.registerTool({
        name: "analyze_financials",
        description: "Analyze financial profile for an entity",
        parameters: { type: "object", properties: { entity: { type: "string" } }, required: ["entity"] },
        execute: async ({ entity }) => {
          if (getStoredMode() === "simulation") return { score: 74, market_cap: 9300000000, source: "webmcp-sim" };
          const r = await api(`/api/analyze?entity=${encodeURIComponent(entity)}&demo_mode=false`);
          return r.financials || {};
        },
      });
      await mcp.registerTool({
        name: "check_founders",
        description: "Check founder reliability and red flags",
        parameters: { type: "object", properties: { entity: { type: "string" } }, required: ["entity"] },
        execute: async ({ entity }) => {
          if (getStoredMode() === "simulation") return { reliability: 82, score: 82, source: "webmcp-sim" };
          const r = await api(`/api/analyze?entity=${encodeURIComponent(entity)}&demo_mode=false`);
          return r.founders || {};
        },
      });
      await mcp.registerTool({
        name: "get_social_sentiment",
        description: "Get social sentiment from Reddit/Twitter proxies",
        parameters: { type: "object", properties: { entity: { type: "string" } }, required: ["entity"] },
        execute: async ({ entity }) => {
          if (getStoredMode() === "simulation") return { sentiment: "NEUTRAL", score: 61, source: "webmcp-sim" };
          const r = await api(`/api/analyze?entity=${encodeURIComponent(entity)}&demo_mode=false`);
          return r.social || {};
        },
      });
      addLog("WebMCP tools enregistrés.");
    } catch (err) {
      addLog(`WebMCP registration error: ${err.message}`, "#ffcc00");
    }
  }

  async function runAnalyze(entity) {
    const settings = await api("/api/settings").catch(() => ({ demo_mode: false }));
    const demoMode = !!settings.demo_mode;
    return api(`/api/analyze?entity=${encodeURIComponent(entity)}&demo_mode=${demoMode ? "true" : "false"}`);
  }

  async function initSearch() {
    const input = document.getElementById("entity-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const watchBtn = document.getElementById("watch-btn");
    const verdictBox = document.getElementById("verdict-box");

    addLog("Système prêt. Backend: " + getApiBase());
    await registerWebMcpTools();

    async function analyzeAction() {
      const entity = (input.value || "").trim();
      if (!entity) return alert("Entre une entité.");
      analyzeBtn.disabled = true;
      addLog(`Start research for ${entity}`);
      try {
        const mcp = getWebMcp();
        if (getStoredMode() === "simulation") {
          addLog("Mode WebMCP simulation.");
          const f = await mcp.executeTool("analyze_financials", { entity });
          const fd = await mcp.executeTool("check_founders", { entity });
          const s = await mcp.executeTool("get_social_sentiment", { entity });
          const score = Math.round(((f.score || 0) + (fd.score || fd.reliability || 0) + (s.score || s.intensity || 0)) / 3);
          renderVerdict({
            entity,
            score,
            verdict: score >= 76 ? "INVESTIR" : score >= 56 ? "OBSERVER" : "FUIR",
            reason: "Simulation WebMCP active.",
            financials: f,
            founders: fd,
            social: s,
          });
        } else {
          const result = await runAnalyze(entity);
          addLog("Financial analysis done.");
          addLog("Founder analysis done.");
          addLog("Social sentiment done.");
          addLog(`Verdict: ${result.verdict} (${result.score})`, result.score >= 76 ? "#00ff88" : "#ffcc00");
          renderVerdict(result);
        }
      } catch (err) {
        addLog(`Erreur: ${err.message}`, "#ff5f6d");
      } finally {
        analyzeBtn.disabled = false;
      }
    }

    function renderVerdict(result) {
      verdictBox.classList.remove("hidden");
      document.getElementById("v-entity").textContent = result.entity || "-";
      document.getElementById("v-score").textContent = `${result.score ?? "--"}%`;
      document.getElementById("v-decision").textContent = result.verdict || "-";
      document.getElementById("v-reason").textContent = result.reason || "-";
      document.getElementById("m-fin").textContent = `${result.financials?.score ?? "-"} / 100`;
      document.getElementById("m-fnd").textContent = `${result.founders?.score ?? result.founders?.reliability ?? "-"} / 100`;
      document.getElementById("m-soc").textContent = `${result.social?.score ?? "-"} / 100`;
      const reportLink = document.getElementById("open-report-link");
      reportLink.href = `./report.html?entity=${encodeURIComponent(result.entity || "")}`;
    }

    analyzeBtn?.addEventListener("click", analyzeAction);
    input?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") analyzeAction();
    });
    watchBtn?.addEventListener("click", async () => {
      const entity = (input.value || "").trim();
      if (!entity) return;
      try {
        await api("/api/watchlist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ entity }),
        });
        addLog(`Watchlist: ${entity} ajouté`, "#7ef5b8");
      } catch (err) {
        addLog(`Watchlist error: ${err.message}`, "#ff5f6d");
      }
    });
  }

  async function initDashboard() {
    const grid = document.getElementById("portfolio-grid");
    const status = document.getElementById("dashboard-status");

    async function refresh() {
      status.textContent = "Mise à jour...";
      try {
        const data = await api("/api/portfolio");
        const items = data.items || [];
        grid.innerHTML = "";
        if (!items.length) {
          grid.innerHTML = '<p class="hint">Aucune entité analysée pour le moment.</p>';
          status.textContent = "Aucune donnée.";
          return;
        }
        items.forEach((it) => {
          const el = document.createElement("article");
          el.className = "entity-card";
          el.innerHTML = `
            <h3>${it.entity || "-"}</h3>
            <p class="hint">${new Date(it.timestamp || Date.now()).toLocaleString()}</p>
            <span class="score-pill ${scoreClass(it.score || 0)}">${it.score || 0}%</span>
            <p>${it.verdict || "-"}</p>
            <a class="btn" href="./report.html?entity=${encodeURIComponent(it.entity || "")}">Deep Dive</a>
          `;
          grid.appendChild(el);
        });
        status.textContent = `Mis à jour à ${new Date().toLocaleTimeString()}`;
      } catch (err) {
        status.textContent = `Erreur: ${err.message}`;
      }
    }

    document.getElementById("refresh-dashboard-btn")?.addEventListener("click", refresh);
    await refresh();
    setInterval(refresh, 60000);
  }

  function drawSentimentChart(score) {
    const canvas = document.getElementById("sentiment-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#03110a";
    ctx.fillRect(0, 0, w, h);

    const points = 24;
    const values = Array.from({ length: points }, (_, i) => {
      const drift = (Math.sin(i / 2.8) + 1) * 12;
      const noise = ((i * 17) % 13) - 6;
      return Math.max(8, Math.min(98, score + drift + noise - 15));
    });

    ctx.strokeStyle = "rgba(0,255,136,0.2)";
    ctx.lineWidth = 1;
    for (let y = 20; y <= h - 20; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    ctx.strokeStyle = "#00ff88";
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = (i / (points - 1)) * (w - 20) + 10;
      const y = h - ((v / 100) * (h - 20) + 10);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  async function initReport() {
    const params = new URLSearchParams(window.location.search);
    const entity = (params.get("entity") || "").trim();
    const runBtn = document.getElementById("run-report-analysis-btn");
    const exportBtn = document.getElementById("export-pdf-btn");
    const title = document.getElementById("report-title");

    async function loadResult() {
      if (!entity) {
        document.getElementById("report-subtitle").textContent = "Ajoute ?entity=XYZ dans l'URL ou lance une analyse.";
        return;
      }
      title.innerHTML = `Rapport <span>${entity}</span>`;
      let item = null;
      const portfolio = await api("/api/portfolio").catch(() => ({ items: [] }));
      item = (portfolio.items || []).find((x) => String(x.entity || "").toLowerCase() === entity.toLowerCase());
      if (!item) item = await runAnalyze(entity);
      renderReport(item);
    }

    function renderReport(r) {
      document.getElementById("rf-score").textContent = `${r.financials?.score ?? "-"} / 100`;
      document.getElementById("rf-market-cap").textContent = fmtMoney(r.financials?.market_cap);
      document.getElementById("rf-revenue").textContent = fmtMoney(r.financials?.revenue_estimate);
      document.getElementById("rf-burn").textContent = fmtMoney(r.financials?.burn_rate);
      document.getElementById("rf-7d").textContent = `${Number(r.financials?.price_change_7d || 0).toFixed(2)}%`;

      document.getElementById("rfd-name").textContent = r.founders?.name || "-";
      document.getElementById("rfd-reliability").textContent = `${r.founders?.reliability ?? "-"}%`;
      document.getElementById("rfd-exits").textContent = `${r.founders?.past_exits ?? "-"}`;
      document.getElementById("rfd-flags").textContent = r.founders?.red_flags || "-";

      document.getElementById("rs-label").textContent = r.social?.sentiment || "-";
      document.getElementById("rs-intensity").textContent = `${r.social?.intensity ?? "-"} / 100`;
      document.getElementById("rs-ratio").textContent = `${Math.round((r.social?.bullish_ratio || 0) * 100)}%`;
      document.getElementById("rs-top-post").textContent = r.social?.top_post || "-";

      document.getElementById("rv-score").textContent = `${r.score ?? "--"}%`;
      document.getElementById("rv-verdict").textContent = r.verdict || "-";
      document.getElementById("rv-reason").textContent = r.reason || "-";

      drawSentimentChart(Number(r.social?.score || 50));
    }

    runBtn?.addEventListener("click", async () => {
      if (!entity) return;
      const r = await runAnalyze(entity);
      renderReport(r);
    });
    exportBtn?.addEventListener("click", () => window.print());
    await loadResult();
  }

  async function initSettings() {
    const apiBaseInput = document.getElementById("api-base");
    const demoToggle = document.getElementById("demo-mode-toggle");
    const webmcpSimToggle = document.getElementById("webmcp-sim-toggle");
    const status = document.getElementById("settings-status");

    function setStatus(text, ok = true) {
      status.textContent = text;
      status.style.color = ok ? "#7ef5b8" : "#ff5f6d";
    }

    apiBaseInput.value = getApiBase();
    webmcpSimToggle.checked = getStoredMode() === "simulation";

    try {
      const cfg = await api("/api/settings");
      document.getElementById("coingecko-api-key").value = cfg.coingecko_api_key || "";
      document.getElementById("reddit-client-id").value = cfg.reddit_client_id || "";
      document.getElementById("reddit-client-secret").value = cfg.reddit_client_secret || "";
      document.getElementById("reddit-user-agent").value = cfg.reddit_user_agent || "InvestAI/1.0";
      document.getElementById("telegram-bot-token").value = cfg.telegram_bot_token || "";
      document.getElementById("telegram-chat-id").value = cfg.telegram_chat_id || "";
      demoToggle.checked = !!cfg.demo_mode;
    } catch (err) {
      setStatus(`Lecture settings impossible: ${err.message}`, false);
    }

    document.getElementById("save-settings-btn")?.addEventListener("click", async () => {
      try {
        setApiBase(apiBaseInput.value || defaultApiBase);
        const payload = {
          demo_mode: demoToggle.checked,
          coingecko_api_key: document.getElementById("coingecko-api-key").value,
          reddit_client_id: document.getElementById("reddit-client-id").value,
          reddit_client_secret: document.getElementById("reddit-client-secret").value,
          reddit_user_agent: document.getElementById("reddit-user-agent").value,
          telegram_bot_token: document.getElementById("telegram-bot-token").value,
          telegram_chat_id: document.getElementById("telegram-chat-id").value,
        };
        ls.setItem("investai_webmcp_mode", webmcpSimToggle.checked ? "simulation" : "backend");
        await api("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setStatus("Paramètres sauvegardés.");
      } catch (err) {
        setStatus(`Erreur sauvegarde: ${err.message}`, false);
      }
    });

    document.getElementById("test-telegram-btn")?.addEventListener("click", async () => {
      try {
        const body = {
          telegram_bot_token: document.getElementById("telegram-bot-token").value,
          telegram_chat_id: document.getElementById("telegram-chat-id").value,
        };
        const res = await api("/api/test-telegram", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (res.ok) setStatus("Message Telegram de test envoyé.");
        else setStatus("Telegram inactif ou échec d'envoi.", false);
      } catch (err) {
        setStatus(`Erreur Telegram: ${err.message}`, false);
      }
    });
  }

  if (page === "search") initSearch();
  if (page === "dashboard") initDashboard();
  if (page === "report") initReport();
  if (page === "settings") initSettings();
})();
