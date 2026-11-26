/* PyAegean Local Greek Visual Corpus Browser — Vanilla ES6 Client */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const state = {
    catalog: null,
    doc: null,
    tokensById: new Map(),
    orderedTokenIds: [],
    selectedTokenId: null,
    wordCache: new Map(),
    lemmaHighlight: null,
    customTranslation: null,
    showInterlinear: true,
    showTranslation: true,
    showPosColors: false,
    showSyntax: false,
    showScansion: false,
    greekFontRem: 1.38,
    worksOffset: 0,
    worksLimit: 40,
    currentParams: {
      target: "John 1:1-18",
      doc: 0,
      edition: "nestle1904",
      numbering: "lxx",
      offset: 0,
      limit: 500,
    },
  };

  function esc(val) {
    return String(val ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  let toastTimer = null;
  function showToast(msg, ms = 3200) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), ms);
  }

  async function apiGet(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  async function apiPost(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  // ── Theme & Layout Controls ──────────────────────────────────────────────

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("aegean-browser-theme", theme); } catch (_) {}
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(cur === "dark" ? "light" : "dark");
  }

  function applyFontSize() {
    document.documentElement.style.setProperty("--greek-size", `${state.greekFontRem.toFixed(2)}rem`);
  }

  function syncReadingClasses() {
    const sheet = $("#reading-sheet");
    sheet.classList.toggle("interlinear-on", state.showInterlinear);
    sheet.classList.toggle("pos-colors-on", state.showPosColors);
    $("#toggle-interlinear").classList.toggle("active", state.showInterlinear);
    $("#toggle-translation").classList.toggle("active", state.showTranslation);
    $("#toggle-pos-colors").classList.toggle("active", state.showPosColors);
    $("#toggle-syntax").classList.toggle("active", state.showSyntax);
    $("#toggle-scansion").classList.toggle("active", state.showScansion);
    $("#pos-legend").classList.toggle("hidden", !state.showPosColors);
    $("#syntax-drawer").classList.toggle("hidden", !state.showSyntax);
    $("#scansion-drawer").classList.toggle("hidden", !state.showScansion);
    renderTranslationVisibility();
  }

  function renderTranslationVisibility() {
    const banner = $("#translation-banner");
    const doc = state.doc;
    if (!doc) return;
    const custom = state.customTranslation;
    const tr = doc.translation || {};
    const hasVerseTrans = doc.blocks.some((b) => b.translation);
    $$(".verse-translation").forEach((el) => {
      el.classList.toggle("hidden", !state.showTranslation);
    });

    if (!state.showTranslation) {
      banner.classList.add("hidden");
      return;
    }

    if (custom) {
      banner.innerHTML = `<div class="translation-banner-label">Custom Parallel Translation</div><p class="translation-banner-text">${esc(custom).replace(/\n/g, "<br/>")}</p>`;
      banner.classList.remove("hidden");
    } else if (tr.available && tr.document_text && !hasVerseTrans) {
      banner.innerHTML = `<div class="translation-banner-label">Parallel Translation · ${esc(tr.source)} (${esc(tr.license)})</div><p class="translation-banner-text">${esc(tr.document_text).replace(/\n/g, "<br/>")}</p>`;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }

  // ── Engine Status & Live Configuration ───────────────────────────────────

  function renderEngineIndicator(eng) {
    if (!eng) return;
    const dot = $("#engine-dot");
    const lbl = $("#engine-label");
    if (eng.neural_active) {
      dot.classList.add("neural");
      const provs = (eng.backend_info && eng.backend_info.active_providers) || [];
      const dev = provs.includes("CUDAExecutionProvider") ? "CUDA" : "CPU";
      const rr = eng.oov_reranker !== "off" ? ` + ${eng.oov_reranker}` : "";
      lbl.textContent = `Neural (${dev}${rr})`;
    } else if (eng.treebank_active) {
      dot.classList.remove("neural");
      lbl.textContent = "Treebank (AGDT)";
    } else {
      dot.classList.remove("neural");
      lbl.textContent = "Offline Baseline";
    }
    renderEnginePopover(eng);
  }

  function renderEnginePopover(eng) {
    const body = $("#engine-body");
    const provs = (eng.backend_info && (eng.backend_info.active_providers || eng.backend_info.available_providers)) || [];
    body.innerHTML = `
      <div class="toggle-row">
        <div>
          <strong>Neural Pipeline (grc-joint-v3)</strong>
          <div class="muted-meta">${eng.neural_installed ? "Full UPOS, XPOS, UFeats, lemma & UD trees" : "Install pyaegean[neural] to enable"}</div>
        </div>
        <input id="eng-neural" type="checkbox" ${eng.neural_active ? "checked" : ""} ${eng.neural_installed ? "" : "disabled"} />
      </div>
      <div class="toggle-row">
        <div>
          <strong>OOV Lemma Reranker</strong>
          <div class="muted-meta">Stage 1B domain-robust OOV recovery</div>
        </div>
        <select id="eng-reranker" class="toolbar-select" ${eng.neural_installed ? "" : "disabled"}>
          <option value="off" ${eng.oov_reranker === "off" ? "selected" : ""}>Off</option>
          <option value="unique" ${eng.oov_reranker === "unique" ? "selected" : ""}>Deterministic</option>
          <option value="weighted" ${eng.oov_reranker === "weighted" ? "selected" : ""}>Weighted (bundled)</option>
        </select>
      </div>
      <div class="toggle-row">
        <div>
          <strong>Schema-2 Calibrated Confidence</strong>
          <div class="muted-meta">Expose calibrated probabilities per token</div>
        </div>
        <input id="eng-cal" type="checkbox" ${eng.calibration_active ? "checked" : ""} />
      </div>
      <div class="toggle-row">
        <div>
          <strong>Documentary Reconciliation</strong>
          <div class="muted-meta">PapyGreek coordinator & OOV levers</div>
        </div>
        <input id="eng-doc" type="checkbox" ${eng.documentary_reconciliation ? "checked" : ""} ${eng.neural_installed ? "" : "disabled"} />
      </div>
      <div class="toggle-row">
        <div>
          <strong>AGDT Treebank Lexicon</strong>
          <div class="muted-meta">Gold classical forms for offline mode</div>
        </div>
        <input id="eng-tb" type="checkbox" ${eng.treebank_active ? "checked" : ""} />
      </div>
      <div class="muted-meta">Providers: <code>${esc(provs.join(", ") || "offline pure-Python")}</code></div>
      <div class="muted-meta">Active lexica: <code>${esc((eng.active_lexica || []).join(", ") || "Dodson / Strong's")}</code></div>
      <button id="btn-apply-engine" type="button" class="btn-primary">Apply &amp; Re-analyze Text</button>
    `;

    $("#btn-apply-engine").addEventListener("click", async () => {
      const btn = $("#btn-apply-engine");
      btn.disabled = true;
      btn.textContent = "Updating engine…";
      try {
        const payload = {
          neural: $("#eng-neural").checked,
          oov_reranker: $("#eng-reranker").value,
          calibration: $("#eng-cal").checked,
          documentary_reconciliation: $("#eng-doc").checked,
          treebank: $("#eng-tb").checked,
        };
        const updated = await apiPost("/api/engine", payload);
        renderEngineIndicator(updated);
        state.wordCache.clear();
        $("#engine-popover").classList.add("hidden");
        showToast("NLP engine updated — re-analyzing passage…");
        await reloadCurrentDocument();
      } catch (err) {
        showToast(`Engine error: ${err.message}`, 5000);
      } finally {
        btn.disabled = false;
        btn.textContent = "Apply & Re-analyze Text";
      }
    });
  }

  // ── Left Navigator Rendering ─────────────────────────────────────────────

  function renderCatalog(cat) {
    state.catalog = cat;
    $("#version-badge").textContent = `v${cat.version}`;
    renderEngineIndicator(cat.engine);

    // Featured list
    const feat = $("#featured-list");
    feat.innerHTML = cat.featured
      .map(
        (f, i) => `
        <button class="nav-item" type="button" data-featured="${i}">
          <div class="nav-item-title">
            <span>${esc(f.label)}</span>
            <span class="tag-badge ok">${esc(f.badge.split("·")[0].trim())}</span>
          </div>
          <div class="nav-item-sub">${esc(f.blurb)}</div>
        </button>`
      )
      .join("");
    feat.querySelectorAll("[data-featured]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const f = cat.featured[Number(btn.dataset.featured)];
        openTarget(f.target, { doc: f.doc_index || 0 });
      });
    });

    // Corpora list
    renderCorporaList("");

    // Bible selectors
    const ntSel = $("#nt-book-select");
    ntSel.innerHTML = cat.nt_books
      .map((b) => `<option value="${esc(b.name)}" ${b.name === "John" ? "selected" : ""}>${esc(b.name)}</option>`)
      .join("");
    const edOpts = cat.nt_editions
      .map((e) => `<option value="${esc(e.id)}" ${e.id === "nestle1904" ? "selected" : ""}>${esc(e.id)} — ${esc(e.name.slice(0, 28))}</option>`)
      .join("");
    $("#nt-edition-select").innerHTML = edOpts;
    $("#edition-switcher").innerHTML = cat.nt_editions
      .map((e) => `<option value="${esc(e.id)}">${esc(e.id)}</option>`)
      .join("");

    const lxxSel = $("#lxx-book-select");
    lxxSel.innerHTML = cat.lxx_books
      .map((b) => `<option value="${esc(b.name)}" ${b.name === "Gen" ? "selected" : ""}>${esc(b.name)} — ${esc(b.title)}</option>`)
      .join("");

    // Collections filter dropdown
    const colSel = $("#works-collection-select");
    colSel.innerHTML =
      `<option value="">All 8 Collections (3,844 works)</option>` +
      cat.collections
        .map((c) => `<option value="${esc(c.id)}">${esc(c.title || c.id)} (${c.works})</option>`)
        .join("");
  }

  function renderCorporaList(filterText) {
    if (!state.catalog) return;
    const q = (filterText || "").trim().toLowerCase();
    const list = state.catalog.corpora.filter(
      (c) => !q || c.id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q) || c.category.toLowerCase().includes(q)
    );
    $("#corpora-count").textContent = `${list.length} Greek corpora`;
    const wrap = $("#corpora-list");
    wrap.innerHTML = list
      .map(
        (c) => `
        <button class="nav-item" type="button" data-corpus="${esc(c.id)}">
          <div class="nav-item-title">
            <span>${esc(c.id)}</span>
            <span class="tag-badge ${c.cached ? "ok" : ""}">${c.bundled ? "bundled" : c.cached ? "cached" : esc(c.size_hint || "fetch")}</span>
          </div>
          <div class="nav-item-sub">${esc(c.blurb || c.title)}</div>
        </button>`
      )
      .join("");
    wrap.querySelectorAll("[data-corpus]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.dataset.corpus;
        if (cid === "nt") openTarget("John 1:1-18");
        else if (cid === "lxx") openTarget("Gen 1:1-5");
        else openTarget(cid, { doc: 0 });
      });
    });
  }

  async function loadWorksPage() {
    const col = $("#works-collection-select").value;
    const q = $("#works-search-input").value.trim();
    const params = new URLSearchParams({
      limit: String(state.worksLimit),
      offset: String(state.worksOffset),
    });
    if (col) params.set("collection", col);
    if (q) params.set("q", q);
    $("#works-meta").textContent = "Searching catalog…";
    try {
      const data = await apiGet(`/api/collections?${params}`);
      $("#works-meta").textContent = `${data.total.toLocaleString()} matching works (showing ${data.offset + 1}–${Math.min(data.offset + data.works.length, data.total)})`;
      $("#btn-works-prev").disabled = data.offset <= 0;
      $("#btn-works-next").disabled = data.offset + data.works.length >= data.total;
      const wrap = $("#works-list");
      wrap.innerHTML = data.works
        .map(
          (w) => `
          <button class="nav-item" type="button" data-work="${esc(w.work_id)}">
            <div class="nav-item-title">
              <span>${esc(w.author || "Unknown")}</span>
              <span class="tag-badge">${esc(w.period || w.collection)}</span>
            </div>
            <div class="nav-item-sub">${esc(w.title)} · <span class="mono">${esc(w.work_id)}</span> (${Number(w.tokens || 0).toLocaleString()} tok)</div>
          </button>`
        )
        .join("");
      wrap.querySelectorAll("[data-work]").forEach((btn) => {
        btn.addEventListener("click", () => openTarget(btn.dataset.work, { doc: 0 }));
      });
    } catch (err) {
      $("#works-meta").textContent = err.message;
    }
  }

  async function runSearch(e) {
    if (e) e.preventDefault();
    const q = $("#search-query-input").value.trim();
    const target = $("#search-target-select").value;
    if (!q) return;
    $("#search-meta").textContent = "Searching…";
    try {
      const data = await apiGet(`/api/search?q=${encodeURIComponent(q)}&target=${encodeURIComponent(target)}&limit=35&offline=true`);
      $("#search-meta").textContent = `${data.count} hit${data.count === 1 ? "" : "s"} in ${data.target}`;
      const wrap = $("#search-results");
      if (!data.hits.length) {
        wrap.innerHTML = `<div class="muted-meta">No cached matches found. Try fetching the corpus in Library or searching Bible (NT + LXX).</div>`;
        return;
      }
      wrap.innerHTML = data.hits
        .map(
          (h, idx) => `
          <button class="nav-item" type="button" data-hit="${idx}">
            <div class="nav-item-title">
              <span>${esc(h.ref || h.doc_id || h.source)}</span>
              <span class="tag-badge indigo">${esc(h.source)}</span>
            </div>
            <div class="nav-item-sub greek-inline">${esc((h.snippet || h.text || "").slice(0, 140))}</div>
          </button>`
        )
        .join("");
      wrap.querySelectorAll("[data-hit]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const hit = data.hits[Number(btn.dataset.hit)];
          openTarget(hit.open_target || target);
        });
      });
    } catch (err) {
      $("#search-meta").textContent = err.message;
    }
  }

  let cachedLibrary = null;
  async function loadLibrary() {
    $("#library-summary").textContent = "Checking local cache…";
    try {
      cachedLibrary = await apiGet("/api/library");
      const s = cachedLibrary.summary || {};
      $("#library-summary").textContent = `${s.downloaded || 0} installed · ${s.bundled || 0} bundled · ${s.available || 0} available`;
      renderLibraryItems($("#library-filter").value);
    } catch (err) {
      $("#library-summary").textContent = err.message;
    }
  }

  function renderLibraryItems(filterText) {
    if (!cachedLibrary) return;
    const q = (filterText || "").trim().toLowerCase();
    const items = (cachedLibrary.items || []).filter(
      (it) => !q || it.id.toLowerCase().includes(q) || it.title.toLowerCase().includes(q) || it.category.toLowerCase().includes(q)
    );
    const wrap = $("#library-list");
    wrap.innerHTML = items
      .slice(0, 80)
      .map(
        (it) => `
        <div class="nav-item">
          <div class="nav-item-title">
            <span>${esc(it.id)}</span>
            <span class="tag-badge ${it.status === "downloaded" || it.status === "bundled" ? "ok" : ""}">${esc(it.status)}</span>
          </div>
          <div class="nav-item-sub">${esc(it.title)} · ${esc(it.size_hint || "")}</div>
          ${
            it.status === "available"
              ? `<div style="margin-top:6px"><button type="button" class="btn-subtle btn-sm" data-fetch-ds="${esc(it.id)}">Download</button></div>`
              : ""
          }
        </div>`
      )
      .join("");
    wrap.querySelectorAll("[data-fetch-ds]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ds = btn.dataset.fetchDs;
        btn.disabled = true;
        btn.textContent = "Downloading…";
        try {
          const out = await apiPost("/api/library/fetch", { dataset: ds });
          cachedLibrary = out.library;
          renderLibraryItems($("#library-filter").value);
          showToast(`Installed ${ds}`);
          const cat = await apiGet("/api/catalog");
          renderCatalog(cat);
        } catch (err) {
          showToast(`Download failed: ${err.message}`, 5000);
          btn.disabled = false;
          btn.textContent = "Download";
        }
      });
    });
  }

  // ── Document Loading & Reading Canvas Rendering ──────────────────────────

  async function openTarget(target, opts = {}) {
    const params = {
      target: target || state.currentParams.target,
      doc: opts.doc ?? 0,
      edition: opts.edition ?? state.currentParams.edition ?? "nestle1904",
      numbering: opts.numbering ?? "lxx",
      offset: opts.offset ?? 0,
      limit: opts.limit ?? 500,
    };
    state.currentParams = params;
    state.customTranslation = null;
    state.lemmaHighlight = null;
    $("#lemma-filter-pill").classList.add("hidden");
    $("#quick-jump-input").value = params.target;
    $("#doc-title").textContent = `Loading ${params.target}…`;
    $("#text-canvas").innerHTML = `<div class="empty-state"><p class="muted-meta">Loading and analyzing Greek text…</p></div>`;

    const qs = new URLSearchParams({
      target: params.target,
      doc: String(params.doc),
      edition: params.edition,
      numbering: params.numbering,
      offset: String(params.offset),
      limit: String(params.limit),
    });
    try {
      const data = await apiGet(`/api/open?${qs}`);
      renderDocument(data);
    } catch (err) {
      $("#doc-title").textContent = "Could not load text";
      $("#doc-subtitle").textContent = "";
      $("#text-canvas").innerHTML = `<div class="empty-state"><p><strong>${esc(err.message)}</strong></p><p class="muted-meta">Check that the passage reference is valid or download the corpus from the Library tab.</p></div>`;
      showToast(err.message, 5000);
    }
  }

  async function reloadCurrentDocument() {
    if (state.doc && state.doc.target === "scratchpad" && state.doc.context && state.doc.context.input_unicode) {
      const data = await apiPost("/api/analyze-text", {
        text: state.doc.context.input_unicode,
        translation: state.customTranslation || (state.doc.translation && state.doc.translation.document_text) || "",
        title: state.doc.title,
      });
      renderDocument(data);
      return;
    }
    await openTarget(state.currentParams.target, state.currentParams);
  }

  function renderDocument(doc) {
    state.doc = doc;
    state.tokensById.clear();
    state.orderedTokenIds = [];
    state.selectedTokenId = null;

    $("#doc-title").textContent = doc.title;
    $("#doc-subtitle").textContent = doc.subtitle;
    renderEngineIndicator(doc.engine);

    // Document switcher (for multi-doc corpora)
    const docSel = $("#doc-switcher");
    if (doc.documents && doc.documents.length > 1) {
      docSel.innerHTML = doc.documents
        .map((d) => `<option value="${d.index}" ${d.index === doc.doc_index ? "selected" : ""}>${esc(d.name)} (${d.tokens})</option>`)
        .join("");
      docSel.classList.remove("hidden");
    } else {
      docSel.classList.add("hidden");
    }

    // Edition switcher (for NT)
    const edSel = $("#edition-switcher");
    if (doc.context && doc.context.testament === "nt") {
      edSel.value = doc.context.edition || "nestle1904";
      edSel.classList.remove("hidden");
    } else {
      edSel.classList.add("hidden");
    }

    // Token pagination (for very long works like Chrysostom homilies)
    const pag = doc.pagination || {};
    const pager = $("#token-pager");
    if ((pag.total_tokens || 0) > (pag.limit || 500)) {
      const start = (pag.offset || 0) + 1;
      const end = (pag.offset || 0) + (pag.returned_tokens || 0);
      $("#page-indicator").textContent = `${start}–${end} / ${pag.total_tokens.toLocaleString()} tok`;
      $("#btn-page-prev").disabled = (pag.offset || 0) <= 0;
      $("#btn-page-next").disabled = !pag.has_more;
      pager.classList.remove("hidden");
    } else {
      pager.classList.add("hidden");
    }

    // Render blocks & interactive word tokens
    const canvas = $("#text-canvas");
    canvas.innerHTML = "";
    const frag = document.createDocumentFragment();

    for (const blk of doc.blocks || []) {
      const section = document.createElement("section");
      section.className = "verse-block";

      if (blk.ref) {
        const hdr = document.createElement("div");
        hdr.className = "verse-header";
        hdr.innerHTML = `<span class="verse-ref">${esc(blk.ref)}</span>${
          blk.mt_ref ? `<span class="tag-badge indigo">${esc(blk.mt_ref)}</span>` : ""
        }`;
        section.appendChild(hdr);
      }

      const flow = document.createElement("div");
      flow.className = "token-flow";
      for (const tok of blk.tokens || []) {
        state.tokensById.set(tok.id, tok);
        state.orderedTokenIds.push(tok.id);

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tok";
        btn.dataset.tid = String(tok.id);
        btn.dataset.upos = tok.upos || "";
        btn.dataset.lemmaFolded = tok.lemma_folded || "";

        const surf = document.createElement("span");
        surf.className = "tok-surface";
        surf.textContent = tok.text;
        btn.appendChild(surf);

        const il = document.createElement("span");
        il.className = "tok-interlinear";
        il.innerHTML = `
          <span class="tok-lemma">${esc(tok.lemma || "")}</span>
          <span class="tok-meta-mini">${esc(tok.upos || "")}${tok.strongs ? ` · ${esc(tok.strongs)}` : ""}</span>
          ${tok.gloss ? `<span class="tok-gloss">${esc(tok.gloss)}</span>` : ""}
        `;
        btn.appendChild(il);

        btn.addEventListener("mouseenter", (ev) => onTokenHover(tok.id, ev));
        btn.addEventListener("mousemove", (ev) => moveTooltip(ev));
        btn.addEventListener("mouseleave", () => clearTokenHover());
        btn.addEventListener("click", () => selectToken(tok.id));

        flow.appendChild(btn);
      }
      section.appendChild(flow);

      if (blk.translation) {
        const trP = document.createElement("p");
        trP.className = "verse-translation";
        trP.textContent = blk.translation;
        section.appendChild(trP);
      }
      frag.appendChild(section);
    }
    canvas.appendChild(frag);

    // Provenance footer
    const prov = doc.provenance || {};
    const provParts = [prov.source, prov.license].filter(Boolean);
    $("#provenance-footer").innerHTML = provParts.length
      ? `Source: ${esc(provParts.join(" · "))}${prov.url ? ` · <a href="${esc(prov.url)}" target="_blank" rel="noopener noreferrer">origin</a>` : ""}`
      : "";

    syncReadingClasses();
    renderContextTab(doc);
    renderStatsTab(doc);
    if (state.showScansion) runScansion();

    // Auto-select the first word so the parallel inspector is immediately alive and useful!
    if (state.orderedTokenIds.length > 0) {
      selectToken(state.orderedTokenIds[0], { scroll: false });
    } else {
      renderSyntaxSvg(null);
    }
  }

  // ── Hover Highlighting, Syntactic Relations & Micro-Tooltip ──────────────

  function getDependentIds(tokId) {
    const deps = [];
    for (const [id, t] of state.tokensById.entries()) {
      if (t.head_global === tokId && id !== tokId) deps.push(id);
    }
    return deps;
  }

  function onTokenHover(tokId, ev) {
    clearTokenHover();
    const tok = state.tokensById.get(tokId);
    if (!tok) return;
    const el = document.querySelector(`.tok[data-tid="${tokId}"]`);
    if (el) el.classList.add("is-hovered");

    // Highlight syntactic head and dependents
    if (tok.head_global !== null && tok.head_global !== undefined) {
      const hEl = document.querySelector(`.tok[data-tid="${tok.head_global}"]`);
      if (hEl) hEl.classList.add("is-head");
    }
    for (const did of getDependentIds(tokId)) {
      const dEl = document.querySelector(`.tok[data-tid="${did}"]`);
      if (dEl) dEl.classList.add("is-dependent");
    }

    // Show crisp hover micro-tooltip
    const tt = $("#word-tooltip");
    const relStr = tok.relation ? ` · ${tok.relation}` : "";
    const strStr = tok.strongs ? ` · ${tok.strongs}` : "";
    tt.innerHTML = `
      <div class="tt-head">${esc(tok.text)} → ${esc(tok.lemma || tok.text)}</div>
      <div class="tt-sub">${esc(tok.upos || "")}${esc(relStr)}${esc(strStr)}${tok.gloss ? ` — “${esc(tok.gloss)}”` : ""}</div>
    `;
    tt.classList.remove("hidden");
    moveTooltip(ev);
  }

  function moveTooltip(ev) {
    const tt = $("#word-tooltip");
    if (tt.classList.contains("hidden")) return;
    const pad = 14;
    const w = tt.offsetWidth || 220;
    const h = tt.offsetHeight || 54;
    let x = ev.clientX + pad;
    let y = ev.clientY + pad;
    if (x + w > window.innerWidth - 10) x = ev.clientX - w - pad;
    if (y + h > window.innerHeight - 10) y = ev.clientY - h - pad;
    tt.style.left = `${Math.max(8, x)}px`;
    tt.style.top = `${Math.max(8, y)}px`;
  }

  function clearTokenHover() {
    $$(".tok.is-hovered, .tok.is-head, .tok.is-dependent").forEach((el) => {
      el.classList.remove("is-hovered", "is-head", "is-dependent");
    });
    $("#word-tooltip").classList.add("hidden");
  }

  // ── Word Selection & Parallel Inspector (Grammar + Lexicon) ──────────────

  async function selectToken(tokId, opts = { scroll: false }) {
    const tok = state.tokensById.get(tokId);
    if (!tok) return;
    state.selectedTokenId = tokId;

    $$(".tok.is-selected").forEach((el) => el.classList.remove("is-selected"));
    const el = document.querySelector(`.tok[data-tid="${tokId}"]`);
    if (el) {
      el.classList.add("is-selected");
      if (opts.scroll) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // Update SVG dependency tree for this word's sentence
    const sent = state.doc && state.doc.sentences ? state.doc.sentences[tok.sentence_index] : null;
    renderSyntaxSvg(sent, tokId);

    // Immediate render from token payload while deep /api/word enriches
    renderGrammarTab(tok, null, sent);

    const cacheKey = `${tok.text}|${tok.lemma}|${tok.strongs}|${sent ? sent.text : ""}`;
    if (state.wordCache.has(cacheKey)) {
      const detail = state.wordCache.get(cacheKey);
      renderGrammarTab(tok, detail, sent);
      renderLexiconTab(tok, detail);
      return;
    }

    $("#insp-pane-lexicon").innerHTML = `<div class="empty-state"><p class="muted-meta">Looking up lexica &amp; Strong's for <span class="greek-inline">${esc(tok.lemma || tok.text)}</span>…</p></div>`;

    const qs = new URLSearchParams({
      surface: tok.text,
      lemma: tok.lemma || "",
      upos: tok.upos || "",
      xpos: tok.xpos || "",
      feats: tok.feats || "",
      robinson: tok.robinson || "",
      strongs: tok.strongs || "",
      sentence: sent ? sent.text : "",
      book: (state.doc && state.doc.context && state.doc.context.book) || "",
    });
    try {
      const detail = await apiGet(`/api/word?${qs}`);
      state.wordCache.set(cacheKey, detail);
      if (state.selectedTokenId === tokId) {
        renderGrammarTab(tok, detail, sent);
        renderLexiconTab(tok, detail);
      }
    } catch (err) {
      $("#insp-pane-lexicon").innerHTML = `<div class="empty-state"><p class="muted-meta">${esc(err.message)}</p></div>`;
    }
  }

  function renderGrammarTab(tok, detail, sent) {
    const pane = $("#insp-pane-grammar");
    const headTok = tok.head_global !== null && tok.head_global !== undefined ? state.tokensById.get(tok.head_global) : null;
    const depToks = getDependentIds(tok.id).map((id) => state.tokensById.get(id)).filter(Boolean);

    const xposRows = Object.entries(tok.xpos_decoded || {});
    const robRows = Object.entries(tok.robinson_decoded || {});
    const featPairs = (tok.feats || "")
      .split("|")
      .filter((s) => s.includes("="))
      .map((s) => s.split("="));

    const morphItems = [];
    if (xposRows.length) {
      for (const [k, v] of xposRows) morphItems.push([k, v]);
    } else if (robRows.length) {
      for (const [k, v] of robRows) morphItems.push([k, v]);
    }
    if (featPairs.length) {
      for (const [k, v] of featPairs) {
        if (!morphItems.some(([mk]) => mk.toLowerCase() === k.toLowerCase())) morphItems.push([k, v]);
      }
    }

    const confPos = tok.confidence_pos != null ? `POS ${(tok.confidence_pos * 100).toFixed(1)}%` : "";
    const confLem = tok.confidence_lemma != null ? `Lemma ${(tok.confidence_lemma * 100).toFixed(1)}%` : "";

    pane.innerHTML = `
      <div class="word-hero">
        <div class="word-hero-top">
          <span class="word-hero-surface">${esc(tok.text)}</span>
          <span class="tag-badge accent">${esc(tok.upos || "—")}</span>
        </div>
        <div class="word-hero-lemma">
          Lemma: <strong>${esc(tok.lemma || tok.text)}</strong>
          ${detail && detail.betacode ? `<span class="muted-meta mono"> (${esc(detail.betacode)})</span>` : ""}
        </div>
        ${tok.gloss ? `<div class="word-hero-gloss">“${esc(tok.gloss)}”</div>` : ""}
        <div class="badge-row">
          ${tok.strongs ? `<span class="tag-badge indigo">${esc(tok.strongs)}</span>` : ""}
          ${tok.relation ? `<span class="tag-badge">${esc(tok.relation)}</span>` : ""}
          ${tok.lemma_source ? `<span class="tag-badge">${esc(tok.lemma_source)}</span>` : ""}
          ${confPos ? `<span class="tag-badge ok">${esc(confPos)}</span>` : ""}
          ${confLem ? `<span class="tag-badge ok">${esc(confLem)}</span>` : ""}
        </div>
        <div style="margin-top:8px">
          <button type="button" class="btn-subtle btn-sm" id="btn-highlight-lemma">Highlight all occurrences</button>
          <button type="button" class="btn-subtle btn-sm" id="btn-jump-lexicon">Open Dictionary →</button>
        </div>
      </div>

      <div class="insp-card">
        <h3>Grammatical Tagging &amp; Morphology</h3>
        <div class="kv-grid">
          <div class="kv-key">UPOS</div><div class="kv-val mono">${esc(tok.upos || "—")}</div>
          ${tok.xpos ? `<div class="kv-key">AGDT XPOS</div><div class="kv-val mono">${esc(tok.xpos)}</div>` : ""}
          ${tok.robinson ? `<div class="kv-key">Robinson</div><div class="kv-val mono">${esc(tok.robinson)}</div>` : ""}
          ${tok.feats ? `<div class="kv-key">UD Feats</div><div class="kv-val mono">${esc(tok.feats)}</div>` : ""}
          ${morphItems.map(([k, v]) => `<div class="kv-key">${esc(k)}</div><div class="kv-val">${esc(v)}</div>`).join("")}
        </div>
      </div>

      <div class="insp-card">
        <h3>Syntactic Parsing</h3>
        ${
          tok.relation || headTok || depToks.length
            ? `
          <div class="kv-grid">
            <div class="kv-key">Relation</div><div class="kv-val mono">${esc(tok.relation || "—")}</div>
            <div class="kv-key">Syntactic Head</div>
            <div class="kv-val">
              ${
                headTok
                  ? `<button type="button" class="link-chip" data-jump-tid="${headTok.id}"><span class="greek-inline">${esc(headTok.text)}</span> (${esc(headTok.upos)})</button>`
                  : tok.head_sent === 0 && tok.relation
                  ? `<span class="tag-badge accent">ROOT</span>`
                  : "—"
              }
            </div>
            <div class="kv-key">Dependents</div>
            <div class="kv-val">
              ${
                depToks.length
                  ? depToks
                      .map((d) => `<button type="button" class="link-chip" data-jump-tid="${d.id}"><span class="greek-inline">${esc(d.text)}</span> <span class="mono">${esc(d.relation)}</span></button>`)
                      .join("")
                  : `<span class="muted-meta">None</span>`
              }
            </div>
          </div>`
            : `<p class="muted-meta" style="margin:0">Enable <strong>Neural Pipeline</strong> in the Engine menu for full UD dependency trees, XPOS, and syntactic arcs.</p>`
        }
      </div>

      ${
        detail
          ? `
      <div class="insp-card">
        <h3>Phonology, Syllables &amp; Accentuation</h3>
        <div class="kv-grid">
          <div class="kv-key">Syllables</div><div class="kv-val greek-inline">${esc((detail.syllables || []).join(" · ") || "—")}</div>
          <div class="kv-key">Accent</div><div class="kv-val">${esc(detail.accent && detail.accent.classification ? `${detail.accent.classification} (${detail.accent.accent_type || ""})` : "—")}</div>
          <div class="kv-key">Attic IPA</div><div class="kv-val mono">${esc(detail.ipa && detail.ipa.attic ? `/${detail.ipa.attic}/` : "—")}</div>
          <div class="kv-key">Koine IPA</div><div class="kv-val mono">${esc(detail.ipa && detail.ipa.koine ? `/${detail.ipa.koine}/` : "—")}</div>
        </div>
      </div>

      ${
        detail.morph_candidates && detail.morph_candidates.length
          ? `<div class="insp-card">
              <h3>Rule-Based Morphological Analyses</h3>
              ${detail.morph_candidates
                .slice(0, 6)
                .map((m) => `<div class="edition-diff-box"><strong class="greek-inline">${esc(m.lemma)}</strong> · <span class="mono">${esc(m.pos || "")}</span> ${esc([m.tense, m.mood, m.voice, m.person, m.case, m.number, m.gender].filter(Boolean).join(" "))}</div>`)
                .join("")}
            </div>`
          : ""
      }

      ${
        detail.paradigm_forms && detail.paradigm_forms.length
          ? `<div class="insp-card">
              <h3>Related Paradigm Forms</h3>
              <div class="badge-row">${detail.paradigm_forms.map((f) => `<span class="tag-badge greek-inline">${esc(f)}</span>`).join("")}</div>
            </div>`
          : ""
      }

      ${
        detail.explanation
          ? `<div class="insp-card">
              <h3>Pipeline Decision Trace</h3>
              <div class="kv-grid">
                <div class="kv-key">Lemma Route</div><div class="kv-val mono">${esc(detail.explanation.lemma_source || "—")}</div>
                <div class="kv-key">Review Flag</div><div class="kv-val">${detail.explanation.needs_review ? "Needs review" : "Verified / standard"}</div>
                ${detail.explanation.note ? `<div class="kv-key">Note</div><div class="kv-val">${esc(detail.explanation.note)}</div>` : ""}
              </div>
            </div>`
          : ""
      }`
          : ""
      }
    `;

    pane.querySelectorAll("[data-jump-tid]").forEach((btn) => {
      btn.addEventListener("click", () => selectToken(Number(btn.dataset.jumpTid), { scroll: true }));
    });
    const hlBtn = $("#btn-highlight-lemma");
    if (hlBtn) {
      hlBtn.addEventListener("click", () => highlightLemmaInDoc(tok.lemma_folded, tok.lemma || tok.text));
    }
    const lexBtn = $("#btn-jump-lexicon");
    if (lexBtn) {
      lexBtn.addEventListener("click", () => switchInspectorTab("lexicon"));
    }
  }

  function renderRootTreeHtml(node) {
    if (!node) return "";
    const children = (node.roots || []).map((c) => renderRootTreeHtml(c)).join("");
    return `
      <div class="root-node">
        <button type="button" class="root-btn" data-drill-word="${esc(node.lemma || "")}" data-drill-strongs="${esc(node.strongs || "")}">${esc(node.lemma || node.strongs)}</button>
        <span class="tag-badge indigo">${esc(node.strongs || "")}</span>
        <span>${esc(node.gloss || "")}</span>
        ${children ? `<div class="root-tree">${children}</div>` : ""}
      </div>`;
  }

  function renderLexiconTab(tok, detail) {
    const pane = $("#insp-pane-lexicon");
    const st = detail.strongs;
    const ws = detail.word_study;
    const activeSet = new Set(detail.active_lexica || []);

    pane.innerHTML = `
      <div class="word-hero">
        <div class="word-hero-top">
          <span class="word-hero-surface">${esc(detail.lemma || tok.lemma || tok.text)}</span>
          ${st ? `<span class="tag-badge indigo">${esc(st.strongs)}</span>` : ""}
        </div>
        ${st && st.translit ? `<div class="muted-meta">${esc(st.translit)} · ${esc(st.morph || "")} · ${esc(st.source || "")}</div>` : ""}
        ${st && st.gloss ? `<div class="word-hero-gloss">${esc(st.gloss)}</div>` : ""}
      </div>

      ${
        st
          ? `<div class="insp-card">
              <h3>Strong's Greek Lexicon</h3>
              <p style="margin:0 0 8px;font-size:0.84rem;line-height:1.55">${esc(st.definition || st.strongs_def || st.gloss)}</p>
              ${st.derivation ? `<div class="muted-meta"><strong>Derivation:</strong> ${esc(st.derivation)}</div>` : ""}
              ${st.kjv_def ? `<div class="muted-meta" style="margin-top:4px"><strong>KJV Usage:</strong> ${esc(st.kjv_def)}</div>` : ""}
              ${
                st.hebrew && st.hebrew.length
                  ? `<div class="badge-row" style="margin-top:6px"><span class="muted-meta">LXX / Hebrew eq.:</span>${st.hebrew.slice(0, 8).map((h) => `<span class="tag-badge">${esc(h)}</span>`).join("")}</div>`
                  : ""
              }
              ${
                detail.roots && detail.roots.roots && detail.roots.roots.length
                  ? `<div style="margin-top:10px"><div class="section-label">Etymological Root Tree (click to inspect)</div>${renderRootTreeHtml(detail.roots)}</div>`
                  : ""
              }
            </div>`
          : `<div class="insp-card"><h3>Strong's Lexicon</h3><p class="muted-meta" style="margin:0">No Strong's entry matched this lemma. Activate LSJ or Extended Strong's below for broader classical &amp; patristic coverage.</p></div>`
      }

      <div class="insp-card">
        <h3>Hosted Greek Dictionaries</h3>
        ${
          detail.lexicon_entries && detail.lexicon_entries.length
            ? detail.lexicon_entries
                .map(
                  (e) => `
                  <div class="edition-diff-box">
                    <div class="nav-item-title">
                      <span class="greek-inline">${esc(e.headword)}</span>
                      <span class="tag-badge ok">${esc(e.lexicon)}</span>
                    </div>
                    <div style="margin-top:4px">${esc(e.body || e.gloss)}</div>
                  </div>`
                )
                .join("")
            : `<p class="muted-meta" style="margin:0 0 8px">Activate any PyAegean hosted lexicon below to see full classical, Homeric, or Koine entries inline:</p>`
        }
        <div class="badge-row">
          <button type="button" class="link-chip" data-activate-lex="strongs">Extended Strong's (11k)</button>
          ${(detail.available_lexica || [])
            .filter((l) => l.hosted)
            .map(
              (l) => `<button type="button" class="link-chip" data-activate-lex="${esc(l.id)}">${activeSet.has(l.id) ? "✓ " : "+ "}${esc(l.id)} (${esc(l.scope)})</button>`
            )
            .join("")}
        </div>
      </div>

      ${
        ws && (ws.total_occurrences > 0 || ws.lxx_total > 0)
          ? `<div class="insp-card">
              <h3>Biblical Concordance &amp; Word Study</h3>
              <div class="badge-row" style="margin-bottom:8px">
                <span class="tag-badge indigo">NT: ${ws.total_occurrences} (${esc(ws.scope || "")})</span>
                <span class="tag-badge ok">LXX: ${ws.lxx_total}</span>
              </div>
              ${renderMiniBars(ws.by_book || {})}
              ${
                ws.sample_occurrences && ws.sample_occurrences.length
                  ? `<div style="margin-top:8px">
                      <div class="section-label">Sample Occurrences</div>
                      ${ws.sample_occurrences
                        .slice(0, 4)
                        .map(
                          (o) => `<button type="button" class="nav-item" style="margin-bottom:4px" data-open-ref="nt:${esc(o.book)} ${esc(o.ref.split(".").slice(1).join(":"))}">
                            <div class="nav-item-title"><span>${esc(o.ref)}</span><span class="tag-badge">${esc(o.morph || "")}</span></div>
                            <div class="nav-item-sub greek-inline">${esc((o.text || "").slice(0, 95))}</div>
                          </button>`
                        )
                        .join("")}
                    </div>`
                  : ""
              }
            </div>`
          : ""
      }

      <div class="insp-card">
        <h3>External Scholarly Lexica</h3>
        <div>
          ${(detail.external_links || [])
            .map((lk) => `<a class="link-chip" href="${esc(lk.url)}" target="_blank" rel="noopener noreferrer">${esc(lk.label)} ↗</a>`)
            .join("")}
        </div>
      </div>
    `;

    // Wire clickable etymology root drilling
    pane.querySelectorAll("[data-drill-word]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const w = btn.dataset.drillWord;
        const sid = btn.dataset.drillStrongs;
        showToast(`Inspecting root ${w || sid}…`);
        try {
          const d = await apiGet(`/api/word?surface=${encodeURIComponent(w || sid)}&strongs=${encodeURIComponent(sid)}`);
          renderLexiconTab({ text: w, lemma: d.lemma, strongs: sid }, d);
        } catch (err) {
          showToast(err.message, 4000);
        }
      });
    });

    // Wire hosted dictionary activation buttons
    pane.querySelectorAll("[data-activate-lex]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const lid = btn.dataset.activateLex;
        btn.disabled = true;
        btn.textContent = `Loading ${lid}…`;
        try {
          const res = await apiPost("/api/lexicon/activate", { id: lid });
          renderEngineIndicator(res.engine);
          state.wordCache.clear();
          showToast(`Activated ${lid} dictionary!`);
          if (state.selectedTokenId !== null) await selectToken(state.selectedTokenId);
        } catch (err) {
          showToast(`Lexicon error: ${err.message}`, 5000);
          btn.disabled = false;
          btn.textContent = `+ ${lid}`;
        }
      });
    });

    pane.querySelectorAll("[data-open-ref]").forEach((btn) => {
      btn.addEventListener("click", () => openTarget(btn.dataset.openRef));
    });
  }

  function renderMiniBars(countMap) {
    const entries = Object.entries(countMap || {}).slice(0, 8);
    if (!entries.length) return "";
    const maxVal = Math.max(...entries.map(([, v]) => Number(v) || 1), 1);
    return entries
      .map(
        ([k, v]) => `
        <div class="bar-row">
          <span class="mono">${esc(k)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.round((Number(v) / maxVal) * 100)}%"></div></div>
          <span class="mono" style="text-align:right">${v}</span>
        </div>`
      )
      .join("");
  }

  // ── Context Tab (Biblical Commentaries / Collations / Witnesses OR Classical Related) ─

  function renderContextTab(doc) {
    const body = $("#context-body");
    const ctx = doc.context || {};

    if (ctx.is_biblical) {
      const book = ctx.book || "John";
      const refStr = ctx.ref || "1.1-5";
      const comms = ctx.related_commentaries || [];

      body.innerHTML = `
        ${
          ctx.testament === "nt"
            ? `<div class="insp-card">
                <h3>Multi-Edition Collation &amp; Early Witnesses</h3>
                <p class="muted-meta" style="margin:0 0 8px">Compare ${esc(book)} ${esc(refStr)} across Nestle 1904, SBLGNT, SRGNT, Byzantine Majority, TR, and 2nd–5th c. uncials &amp; papyri (ℵ, A, B, P45, P66, P75).</p>
                <div class="badge-row">
                  <button type="button" class="btn-subtle btn-sm" id="btn-compare-editions">Compare NT Editions</button>
                  <button type="button" class="btn-subtle btn-sm" id="btn-compare-witnesses">Inspect Manuscripts</button>
                </div>
                <div id="biblical-collation-out" style="margin-top:10px"></div>
              </div>`
            : ""
        }

        <div class="insp-card">
          <h3>Linked Patristic Commentaries (${comms.length})</h3>
          ${
            comms.length
              ? comms
                  .slice(0, 20)
                  .map(
                    (c) => `
                    <div class="edition-diff-box">
                      <div class="nav-item-title">
                        <span>${esc(c.author)}</span>
                        <span class="tag-badge ${c.kind === "chrysostom" ? "accent" : "indigo"}">${esc(c.kind)}</span>
                      </div>
                      <div class="nav-item-sub">${esc(c.title)}</div>
                      <div class="badge-row" style="margin-top:6px">
                        <button type="button" class="btn-subtle btn-sm" data-comm-excerpt="${esc(c.work_id)}">Preview Greek Excerpt</button>
                        ${
                          String(c.work_id).startsWith("ogc") || String(c.work_id).startsWith("PG")
                            ? `<button type="button" class="btn-subtle btn-sm" data-open-comm="${esc(c.work_id)}">Open Full Work</button>`
                            : ""
                        }
                      </div>
                      <div id="excerpt-${esc(c.work_id.replace(/[^a-zA-Z0-9_-]/g, "_"))}" class="hidden"></div>
                    </div>`
                  )
                  .join("")
              : `<p class="muted-meta" style="margin:0">No indexed commentaries directly linked to ${esc(book)}.</p>`
          }
        </div>
      `;

      const edBtn = $("#btn-compare-editions");
      if (edBtn) {
        edBtn.addEventListener("click", async () => {
          const out = $("#biblical-collation-out");
          out.innerHTML = `<div class="muted-meta">Collating Greek NT editions…</div>`;
          try {
            const cmp = await apiGet(`/api/bible/editions?book=${encodeURIComponent(book)}&ref=${encodeURIComponent(refStr)}`);
            const verses = cmp.verses || [];
            out.innerHTML =
              `<div class="muted-meta" style="margin-bottom:6px">Editions: <code>${esc((cmp.editions || []).join(", "))}</code> · ${cmp.variant_count || 0} word variant(s)</div>` +
              verses
                .slice(0, 12)
                .map((v) => {
                  const vlist = (v.variants || [])
                    .map((w) => `<div class="mono" style="margin-top:3px">pos ${w.position}: ${Object.entries(w.readings || {}).map(([ek, ev]) => `${esc(ek)}=<span class="greek-inline">${esc(ev)}</span>`).join(" | ")}</div>`)
                    .join("");
                  return `<div class="edition-diff-box"><strong>${esc(v.ref)}</strong> ${v.identical ? `<span class="tag-badge ok">identical</span>` : `<span class="tag-badge accent">${(v.variants || []).length} variant(s)</span>`}${vlist}</div>`;
                })
                .join("");
          } catch (err) {
            out.innerHTML = `<div class="muted-meta">${esc(err.message)}</div>`;
          }
        });
      }

      const witBtn = $("#btn-compare-witnesses");
      if (witBtn) {
        witBtn.addEventListener("click", async () => {
          const out = $("#biblical-collation-out");
          out.innerHTML = `<div class="muted-meta">Loading 2nd–5th c. manuscript witnesses…</div>`;
          try {
            const data = await apiGet(`/api/bible/witnesses?book=${encodeURIComponent(book)}&ref=${encodeURIComponent(refStr)}`);
            out.innerHTML = (data.verses || [])
              .slice(0, 6)
              .map(
                (v) => `
                <div class="edition-diff-box">
                  <strong>${esc(v.ref)}</strong>
                  ${(v.witnesses || [])
                    .slice(0, 6)
                    .map((w) => `<div style="margin-top:4px"><span class="tag-badge indigo">${esc(w.siglum)}</span> <span class="greek-inline">${esc((w.text || "").slice(0, 110))}</span></div>`)
                    .join("")}
                </div>`
              )
              .join("");
          } catch (err) {
            out.innerHTML = `<div class="muted-meta">${esc(err.message)}</div>`;
          }
        });
      }

      body.querySelectorAll("[data-comm-excerpt]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const wid = btn.dataset.commExcerpt;
          const slot = $(`#excerpt-${wid.replace(/[^a-zA-Z0-9_-]/g, "_")}`);
          slot.classList.remove("hidden");
          slot.innerHTML = `<div class="muted-meta" style="margin-top:6px">Loading Greek commentary excerpt…</div>`;
          const activeTok = state.selectedTokenId !== null ? state.tokensById.get(state.selectedTokenId) : null;
          const qTerm = activeTok && activeTok.lemma ? activeTok.lemma : "";
          try {
            const res = await apiGet(
              `/api/bible/commentary-excerpt?book=${encodeURIComponent(book)}&work_id=${encodeURIComponent(wid)}&q=${encodeURIComponent(qTerm)}&limit=3`
            );
            const exs = res.excerpts || [];
            if (!exs.length) {
              slot.innerHTML = `<div class="muted-meta" style="margin-top:6px">No excerpt matched for this query.</div>`;
              return;
            }
            slot.innerHTML = exs
              .map((ex) => `<div class="commentary-excerpt"><div class="muted-meta">${esc(ex.citation || ex.work_id)}</div>${esc(ex.text || "")}</div>`)
              .join("");
          } catch (err) {
            slot.innerHTML = `<div class="muted-meta" style="margin-top:6px">${esc(err.message)}</div>`;
          }
        });
      });

      body.querySelectorAll("[data-open-comm]").forEach((btn) => {
        btn.addEventListener("click", () => openTarget(btn.dataset.openComm));
      });
    } else {
      // Classical / Patristic / Epigraphic / Literary Context
      const wm = ctx.work_meta;
      const related = ctx.related_works || [];
      body.innerHTML = `
        <div class="insp-card">
          <h3>Document Metadata &amp; Classical Tools</h3>
          <div class="kv-grid">
            <div class="kv-key">Document ID</div><div class="kv-val mono">${esc(doc.doc_id)}</div>
            ${ctx.period ? `<div class="kv-key">Period</div><div class="kv-val">${esc(ctx.period)}</div>` : ""}
            ${ctx.site ? `<div class="kv-key">Findspot</div><div class="kv-val">${esc(ctx.site)}</div>` : ""}
            ${wm && wm.author ? `<div class="kv-key">Author</div><div class="kv-val">${esc(wm.author)}</div>` : ""}
            ${wm && wm.tlg ? `<div class="kv-key">TLG ID</div><div class="kv-val mono">${esc(wm.tlg)}</div>` : ""}
            ${wm && wm.license ? `<div class="kv-key">License</div><div class="kv-val">${esc(wm.license)}</div>` : ""}
            ${wm && wm.source ? `<div class="kv-key">Edition Source</div><div class="kv-val">${esc(wm.source)} (${esc(wm.correction || "")})</div>` : ""}
          </div>
          <div class="badge-row" style="margin-top:10px">
            <button type="button" class="btn-subtle btn-sm" id="btn-ctx-scan">Scan Meter on Page</button>
            <button type="button" class="btn-subtle btn-sm" id="btn-ctx-scholia">Open Homer Scholia</button>
          </div>
        </div>

        <div class="insp-card">
          <h3>Related Greek Works (${related.length})</h3>
          ${
            related.length
              ? related
                  .map(
                    (w) => `
                    <button type="button" class="nav-item" style="margin-bottom:5px" data-open-rel="${esc(w.work_id)}">
                      <div class="nav-item-title">
                        <span>${esc(w.author || "")}</span>
                        <span class="tag-badge">${esc(w.period || w.collection)}</span>
                      </div>
                      <div class="nav-item-sub">${esc(w.title)} · <span class="mono">${esc(w.work_id)}</span></div>
                    </button>`
                  )
                  .join("")
              : `<p class="muted-meta" style="margin:0">Explore 3,844 ancient, classical, patristic, and Byzantine Greek works in the <strong>3,844 Works</strong> tab on the left.</p>`
          }
        </div>
      `;

      const scanBtn = $("#btn-ctx-scan");
      if (scanBtn) {
        scanBtn.addEventListener("click", () => {
          state.showScansion = true;
          syncReadingClasses();
          runScansion();
        });
      }
      const schBtn = $("#btn-ctx-scholia");
      if (schBtn) {
        schBtn.addEventListener("click", () => openTarget("homer-scholia"));
      }
      body.querySelectorAll("[data-open-rel]").forEach((btn) => {
        btn.addEventListener("click", () => openTarget(btn.dataset.openRel));
      });
    }
  }

  // ── Document Stats & Clickable Lemma Frequency Table ─────────────────────

  function renderStatsTab(doc) {
    const st = doc.stats || {};
    const body = $("#stats-body");
    body.innerHTML = `
      <div class="insp-card">
        <h3>Passage Lexical Profile</h3>
        <div class="kv-grid">
          <div class="kv-key">Tokens</div><div class="kv-val mono">${(st.tokens || 0).toLocaleString()}</div>
          <div class="kv-key">Unique Lemmas</div><div class="kv-val mono">${(st.unique_lemmas || 0).toLocaleString()}</div>
          <div class="kv-key">Hapax Legomena</div><div class="kv-val mono">${(st.hapax_count || 0).toLocaleString()}</div>
          <div class="kv-key">Sentences</div><div class="kv-val mono">${(st.sentences || 0).toLocaleString()}</div>
        </div>
      </div>

      <div class="insp-card">
        <h3>Part-of-Speech Distribution</h3>
        ${renderMiniBars(st.pos_counts || {})}
      </div>

      <div class="insp-card">
        <h3>Lemma Frequency (Click to Highlight in Text)</h3>
        <div>
          ${(st.top_lemmas || [])
            .map(
              (item) => `
              <button type="button" class="freq-row" data-hl-folded="${esc(item.folded)}" data-hl-label="${esc(item.lemma)}">
                <span><strong class="greek-inline">${esc(item.lemma)}</strong> <span class="muted-meta">${esc(item.gloss || "")}</span></span>
                <span class="badge-row" style="margin:0"><span class="tag-badge">${esc(item.upos)}</span><span class="tag-badge indigo">${item.count}×</span></span>
              </button>`
            )
            .join("")}
        </div>
      </div>
    `;

    body.querySelectorAll("[data-hl-folded]").forEach((btn) => {
      btn.addEventListener("click", () => {
        highlightLemmaInDoc(btn.dataset.hlFolded, btn.dataset.hlLabel);
      });
    });
  }

  function highlightLemmaInDoc(folded, displayLabel) {
    state.lemmaHighlight = folded;
    $$(".tok.is-same-lemma").forEach((el) => el.classList.remove("is-same-lemma"));
    let firstEl = null;
    let count = 0;
    $$(".tok").forEach((el) => {
      if (el.dataset.lemmaFolded === folded) {
        el.classList.add("is-same-lemma");
        if (!firstEl) firstEl = el;
        count += 1;
      }
    });
    $("#lemma-filter-text").textContent = `${displayLabel} (${count}×)`;
    $("#lemma-filter-pill").classList.remove("hidden");
    if (firstEl) firstEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearLemmaHighlight() {
    state.lemmaHighlight = null;
    $$(".tok.is-same-lemma").forEach((el) => el.classList.remove("is-same-lemma"));
    $("#lemma-filter-pill").classList.add("hidden");
  }

  // ── Inline SVG Dependency Tree Renderer ──────────────────────────────────

  function renderSyntaxSvg(sent, activeTokId) {
    const wrap = $("#syntax-svg-wrap");
    if (!sent || !sent.tokens || !sent.tokens.length) {
      wrap.innerHTML = `<div class="muted-meta">Select a word to view its sentence dependency tree.</div>`;
      return;
    }
    $("#syntax-sentence-label").textContent = `Sentence ${sent.index + 1}${sent.ref ? ` (${sent.ref})` : ""} — ${sent.tokens.length} tokens`;
    if (!sent.has_dependencies) {
      wrap.innerHTML = `<div class="muted-meta">No dependency arcs on this sentence yet. Enable <strong>Neural Pipeline (grc-joint-v3)</strong> in the Engine menu for full UD parsing.</div>`;
      return;
    }

    const toks = sent.tokens;
    const colW = 84;
    const padX = 28;
    const width = Math.max(420, toks.length * colW + padX * 2);
    const maxSpan = Math.max(
      1,
      ...toks.map((t) => (t.head > 0 ? Math.abs(t.head - t.index) : 1))
    );
    const arcAreaH = Math.min(130, 38 + maxSpan * 14);
    const baselineY = arcAreaH + 14;
    const height = baselineY + 46;

    const xOf = (idx1) => padX + (idx1 - 1) * colW + colW / 2;

    let arcsSvg = "";
    for (const t of toks) {
      const xDep = xOf(t.index);
      const isFocused = t.id === activeTokId || (t.head > 0 && toks[t.head - 1] && toks[t.head - 1].id === activeTokId);
      const stroke = isFocused ? "var(--accent)" : "var(--indigo)";
      const opacity = activeTokId != null && !isFocused ? "0.42" : "0.92";

      if (t.head === 0) {
        arcsSvg += `
          <line x1="${xDep}" y1="12" x2="${xDep}" y2="${baselineY - 6}" stroke="${stroke}" stroke-width="${isFocused ? 2.2 : 1.4}" opacity="${opacity}" />
          <text x="${xDep}" y="10" text-anchor="middle" font-size="10" font-family="var(--font-mono)" fill="${stroke}">${esc(t.relation || "root")}</text>
        `;
      } else if (t.head > 0 && t.head <= toks.length) {
        const xHead = xOf(t.head);
        const span = Math.abs(t.head - t.index);
        const h = Math.min(arcAreaH - 12, 22 + span * 13);
        const midX = (xHead + xDep) / 2;
        const ctrlY = baselineY - h;
        arcsSvg += `
          <path d="M ${xHead} ${baselineY - 4} Q ${midX} ${ctrlY} ${xDep} ${baselineY - 4}" fill="none" stroke="${stroke}" stroke-width="${isFocused ? 2.2 : 1.35}" opacity="${opacity}" />
          <text x="${midX}" y="${ctrlY + h * 0.42}" text-anchor="middle" font-size="10" font-family="var(--font-mono)" fill="${stroke}" opacity="${opacity}">${esc(t.relation)}</text>
        `;
      }
    }

    let wordsSvg = "";
    for (const t of toks) {
      const x = xOf(t.index);
      const isSel = t.id === activeTokId;
      wordsSvg += `
        <g class="svg-tok" data-svg-tid="${t.id}" style="cursor:pointer">
          <text x="${x}" y="${baselineY + 16}" text-anchor="middle" font-size="14" font-family="var(--font-greek)" font-weight="${isSel ? "700" : "400"}" fill="${isSel ? "var(--accent)" : "var(--ink-primary)"}">${esc(t.text.slice(0, 11))}</text>
          <text x="${x}" y="${baselineY + 32}" text-anchor="middle" font-size="10" font-family="var(--font-mono)" fill="var(--ink-muted)">${esc(t.upos)}</text>
        </g>
      `;
    }

    wrap.innerHTML = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Dependency parse tree">${arcsSvg}${wordsSvg}</svg>`;
    wrap.querySelectorAll("[data-svg-tid]").forEach((g) => {
      g.addEventListener("click", () => selectToken(Number(g.dataset.svgTid), { scroll: true }));
    });
  }

  // ── Metrical Scansion ────────────────────────────────────────────────────

  async function runScansion() {
    if (!state.doc) return;
    const meter = $("#scansion-meter-select").value;
    const lines = (state.doc.blocks || [])
      .map((b) => (b.tokens || []).map((t) => t.text).join(" "))
      .filter(Boolean)
      .slice(0, 20);
    const out = $("#scansion-results");
    out.innerHTML = `<div class="muted-meta">Scanning ${lines.length} line(s) as ${esc(meter)}…</div>`;
    try {
      const data = await apiPost("/api/scan", { lines, meter });
      out.innerHTML = (data.results || [])
        .map(
          (r) => `
          <div class="scansion-line-row">
            <div class="scansion-greek">${esc(r.line)}</div>
            ${
              r.error
                ? `<div class="muted-meta">${esc(r.error)}</div>`
                : `<div class="scansion-pattern">${esc(r.pattern)}${r.caesura ? ` · <span class="muted-meta">caesura: ${esc(r.caesura)}</span>` : ""}</div>
                   <div class="scansion-feet">${(r.feet || []).map((f) => `<span class="foot-chip">${esc(f.syllables.join("·"))} <span class="muted-meta">${esc(f.name)}</span></span>`).join("")}</div>`
            }
          </div>`
        )
        .join("");
    } catch (err) {
      out.innerHTML = `<div class="muted-meta">${esc(err.message)}</div>`;
    }
  }

  // ── Export Download ──────────────────────────────────────────────────────

  async function triggerExport(fmt) {
    if (!state.doc) return;
    try {
      const res = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format: fmt,
          title: state.doc.title,
          blocks: state.doc.blocks,
          sentences: state.doc.sentences,
        }),
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const disp = res.headers.get("Content-Disposition") || "";
      const match = disp.match(/filename="([^"]+)"/);
      const fname = match ? match[1] : `passage.${fmt}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fname;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1500);
      showToast(`Exported ${fname}`);
    } catch (err) {
      showToast(err.message, 4000);
    }
  }

  // ── Tabs & Event Wiring ──────────────────────────────────────────────────

  function switchNavTab(tabId) {
    $$(".nav-tab").forEach((b) => {
      const active = b.dataset.nav === tabId;
      b.classList.toggle("active", active);
      b.setAttribute("aria-selected", String(active));
    });
    $$(".nav-pane").forEach((p) => p.classList.toggle("active", p.id === `nav-pane-${tabId}`));
    if (tabId === "works" && !$("#works-list").children.length) loadWorksPage();
    if (tabId === "library" && !cachedLibrary) loadLibrary();
  }

  function switchInspectorTab(tabId) {
    $$(".insp-tab").forEach((b) => {
      const active = b.dataset.insp === tabId;
      b.classList.toggle("active", active);
      b.setAttribute("aria-selected", String(active));
    });
    $$(".insp-pane").forEach((p) => p.classList.toggle("active", p.id === `insp-pane-${tabId}`));
  }

  function bindEvents() {
    // Sidebar & Inspector tabs
    $$(".nav-tab").forEach((b) => b.addEventListener("click", () => switchNavTab(b.dataset.nav)));
    $$(".insp-tab").forEach((b) => b.addEventListener("click", () => switchInspectorTab(b.dataset.insp)));

    // Collapse toggles
    $("#btn-toggle-sidebar").addEventListener("click", () => $("#workspace").classList.toggle("sidebar-collapsed"));
    $("#btn-toggle-inspector").addEventListener("click", () => $("#workspace").classList.toggle("inspector-collapsed"));
    $("#btn-theme").addEventListener("click", toggleTheme);

    // Quick jump bar
    $("#quick-jump-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const val = $("#quick-jump-input").value.trim();
      if (val) openTarget(val, { doc: 0 });
    });

    // Corpora filter
    $("#corpora-filter").addEventListener("input", (e) => renderCorporaList(e.target.value));

    // Bible pane
    $("#btn-open-nt").addEventListener("click", () => {
      const bk = $("#nt-book-select").value;
      const ref = $("#nt-ref-input").value.trim();
      const ed = $("#nt-edition-select").value;
      openTarget(`nt:${bk}${ref ? " " + ref : ""}`, { edition: ed });
    });
    $("#btn-open-lxx").addEventListener("click", () => {
      const bk = $("#lxx-book-select").value;
      const ref = $("#lxx-ref-input").value.trim();
      const num = $("#lxx-num-select").value;
      openTarget(`lxx:${bk}${ref ? " " + ref : ""}`, { numbering: num });
    });

    const updatePsalm = async () => {
      const n = Number($("#psalm-num-input").value || 23);
      const dir = $("#psalm-dir-select").value;
      try {
        const res = await apiGet(`/api/bible/psalm?number=${n}&direction=${dir}`);
        const label = dir === "mt_to_lxx" ? `MT Psalm ${n} → LXX Psalm ${res.mapped.join(", ")}` : `LXX Psalm ${n} → MT Psalm ${res.mapped.join(", ")}`;
        $("#psalm-result").textContent = label;
      } catch (err) {
        $("#psalm-result").textContent = err.message;
      }
    };
    $("#psalm-num-input").addEventListener("input", updatePsalm);
    $("#psalm-dir-select").addEventListener("change", updatePsalm);

    // 3,844 works catalog
    let worksTimer = null;
    $("#works-collection-select").addEventListener("change", () => {
      state.worksOffset = 0;
      loadWorksPage();
    });
    $("#works-search-input").addEventListener("input", () => {
      clearTimeout(worksTimer);
      worksTimer = setTimeout(() => {
        state.worksOffset = 0;
        loadWorksPage();
      }, 180);
    });
    $("#btn-works-prev").addEventListener("click", () => {
      state.worksOffset = Math.max(0, state.worksOffset - state.worksLimit);
      loadWorksPage();
    });
    $("#btn-works-next").addEventListener("click", () => {
      state.worksOffset += state.worksLimit;
      loadWorksPage();
    });

    // Search & Library
    $("#search-form").addEventListener("submit", runSearch);
    $("#btn-refresh-library").addEventListener("click", loadLibrary);
    $("#library-filter").addEventListener("input", (e) => renderLibraryItems(e.target.value));

    // Document toolbar controls
    $("#doc-switcher").addEventListener("change", (e) => {
      openTarget(state.currentParams.target, { ...state.currentParams, doc: Number(e.target.value), offset: 0 });
    });
    $("#edition-switcher").addEventListener("change", (e) => {
      openTarget(state.currentParams.target, { ...state.currentParams, edition: e.target.value, offset: 0 });
    });
    $("#btn-page-prev").addEventListener("click", () => {
      const nextOff = Math.max(0, (state.currentParams.offset || 0) - (state.currentParams.limit || 500));
      openTarget(state.currentParams.target, { ...state.currentParams, offset: nextOff });
    });
    $("#btn-page-next").addEventListener("click", () => {
      const nextOff = (state.currentParams.offset || 0) + (state.currentParams.limit || 500);
      openTarget(state.currentParams.target, { ...state.currentParams, offset: nextOff });
    });

    // Reading toggles
    $("#toggle-interlinear").addEventListener("click", () => {
      state.showInterlinear = !state.showInterlinear;
      syncReadingClasses();
    });
    $("#toggle-translation").addEventListener("click", () => {
      state.showTranslation = !state.showTranslation;
      syncReadingClasses();
    });
    $("#toggle-pos-colors").addEventListener("click", () => {
      state.showPosColors = !state.showPosColors;
      syncReadingClasses();
    });
    $("#toggle-syntax").addEventListener("click", () => {
      state.showSyntax = !state.showSyntax;
      syncReadingClasses();
      if (state.showSyntax && state.selectedTokenId !== null) {
        const tok = state.tokensById.get(state.selectedTokenId);
        if (tok && state.doc) renderSyntaxSvg(state.doc.sentences[tok.sentence_index], tok.id);
      }
    });
    $("#toggle-scansion").addEventListener("click", () => {
      state.showScansion = !state.showScansion;
      syncReadingClasses();
      if (state.showScansion) runScansion();
    });
    $("#btn-rescan").addEventListener("click", runScansion);
    $("#scansion-meter-select").addEventListener("change", runScansion);
    $("#btn-clear-lemma-filter").addEventListener("click", clearLemmaHighlight);

    $("#btn-font-dec").addEventListener("click", () => {
      state.greekFontRem = Math.max(1.05, state.greekFontRem - 0.12);
      applyFontSize();
    });
    $("#btn-font-inc").addEventListener("click", () => {
      state.greekFontRem = Math.min(2.1, state.greekFontRem + 0.12);
      applyFontSize();
    });

    // Engine & Export popovers
    $("#btn-engine").addEventListener("click", () => $("#engine-popover").classList.toggle("hidden"));
    $("#btn-close-engine").addEventListener("click", () => $("#engine-popover").classList.add("hidden"));

    $("#btn-export").addEventListener("click", () => $("#export-menu").classList.toggle("hidden"));
    $$("[data-export]").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#export-menu").classList.add("hidden");
        triggerExport(btn.dataset.export);
      });
    });

    // Scratchpad Modal
    $("#btn-sandbox").addEventListener("click", () => $("#sandbox-modal").classList.remove("hidden"));
    $("#btn-close-sandbox").addEventListener("click", () => $("#sandbox-modal").classList.add("hidden"));
    $("#btn-sandbox-sample").addEventListener("click", () => {
      $("#sandbox-text").value = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος\nοὐλομένην, ἣ μυρίʼ Ἀχαιοῖς ἄλγεʼ ἔθηκε.";
      $("#sandbox-betacode").checked = false;
      $("#sandbox-translation").value = "Sing, goddess, the wrath of Achilles, son of Peleus—the destructive wrath that laid countless woes upon the Achaeans.";
    });
    $("#sandbox-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const data = await apiPost("/api/analyze-text", {
          text: $("#sandbox-text").value,
          betacode: $("#sandbox-betacode").checked,
          translation: $("#sandbox-translation").value,
          title: "Custom Greek Passage",
        });
        $("#sandbox-modal").classList.add("hidden");
        renderDocument(data);
        showToast("Analyzed custom passage");
      } catch (err) {
        showToast(err.message, 4500);
      }
    });

    // Custom Translation Modal
    $("#btn-custom-trans").addEventListener("click", () => {
      $("#custom-trans-input").value = state.customTranslation || "";
      $("#trans-modal").classList.remove("hidden");
    });
    $("#btn-close-trans").addEventListener("click", () => $("#trans-modal").classList.add("hidden"));
    $("#btn-clear-custom-trans").addEventListener("click", () => {
      state.customTranslation = null;
      $("#trans-modal").classList.add("hidden");
      renderTranslationVisibility();
    });
    $("#trans-form").addEventListener("submit", (e) => {
      e.preventDefault();
      state.customTranslation = $("#custom-trans-input").value.trim() || null;
      state.showTranslation = true;
      $("#trans-modal").classList.add("hidden");
      syncReadingClasses();
    });

    // Keyboard shortcuts (non-intrusive when typing in inputs/textareas)
    document.addEventListener("keydown", (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        if (e.key === "Escape") document.activeElement.blur();
        return;
      }
      if (e.key === "Escape") {
        $("#engine-popover").classList.add("hidden");
        $("#export-menu").classList.add("hidden");
        $("#sandbox-modal").classList.add("hidden");
        $("#trans-modal").classList.add("hidden");
      } else if (e.key === "i") {
        state.showInterlinear = !state.showInterlinear;
        syncReadingClasses();
      } else if (e.key === "t") {
        state.showTranslation = !state.showTranslation;
        syncReadingClasses();
      } else if (e.key === "d") {
        toggleTheme();
      } else if (e.key === "/") {
        e.preventDefault();
        $("#quick-jump-input").focus();
      } else if (e.key === "ArrowRight" && state.orderedTokenIds.length) {
        e.preventDefault();
        const pos = state.orderedTokenIds.indexOf(state.selectedTokenId);
        const next = state.orderedTokenIds[Math.min(state.orderedTokenIds.length - 1, pos + 1)];
        selectToken(next, { scroll: true });
      } else if (e.key === "ArrowLeft" && state.orderedTokenIds.length) {
        e.preventDefault();
        const pos = state.orderedTokenIds.indexOf(state.selectedTokenId);
        const prev = state.orderedTokenIds[Math.max(0, pos - 1)];
        selectToken(prev, { scroll: true });
      }
    });
  }

  // ── Boot Sequence ────────────────────────────────────────────────────────

  async function init() {
    try {
      const savedTheme = localStorage.getItem("aegean-browser-theme");
      if (savedTheme === "dark" || savedTheme === "light") applyTheme(savedTheme);
    } catch (_) {}
    applyFontSize();
    bindEvents();
    syncReadingClasses();

    try {
      const [cfg, cat] = await Promise.all([apiGet("/api/config"), apiGet("/api/catalog")]);
      renderCatalog(cat);
      await openTarget(cfg.initial_target || "John 1:1-18", {
        doc: cfg.initial_doc_index || 0,
        edition: cfg.initial_edition || "nestle1904",
      });
    } catch (err) {
      $("#doc-title").textContent = "Startup Error";
      $("#text-canvas").innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`;
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
