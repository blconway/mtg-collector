(() => {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────────

  const state = {
    groupBy: "set_name",
    selectedGroup: null,   // null = show all
    selectedCardUid: null,
    viewMode: "list",      // "list" or "grid"
    sort: "name",
    sortDir: "asc",
    search: "",
    page: 1,
  };

  // ── DOM refs ───────────────────────────────────────────────────────────────

  const $layout = document.getElementById("collection-layout");
  const $groupBySelect = document.getElementById("group-by-select");
  const $sidebarTree = document.getElementById("sidebar-tree");
  const $listSearch = document.getElementById("list-search");
  const $listSort = document.getElementById("list-sort");
  const $viewToggle = document.getElementById("view-toggle");
  const $globalSearch = document.getElementById("global-search");
  const $globalResults = document.getElementById("global-search-results");
  const $listContent = document.getElementById("list-content");
  const $listPagination = document.getElementById("list-pagination");
  const $detailPane = document.getElementById("detail-pane");
  const $modal = document.getElementById("card-modal");
  const $modalContent = document.getElementById("modal-content");
  const $resizeV = document.getElementById("resize-v");
  const $resizeH = document.getElementById("resize-h");

  // ── API helpers ────────────────────────────────────────────────────────────

  async function api(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
  }

  async function fetchGroups() {
    return api(`/api/groups?group_by=${encodeURIComponent(state.groupBy)}`);
  }

  async function fetchCards() {
    const params = new URLSearchParams();
    if (state.groupBy && state.selectedGroup !== null) {
      params.set("group_by", state.groupBy);
      params.set("group_value", state.selectedGroup);
    }
    if (state.search) params.set("q", state.search);
    params.set("sort", state.sort);
    params.set("sort_dir", state.sortDir);
    params.set("page", state.page);
    return api(`/api/cards?${params}`);
  }

  async function fetchCardDetail(uid) {
    return api(`/api/cards/${encodeURIComponent(uid)}`);
  }

  // ── Collection stats ────────────────────────────────────────────────────────

  async function loadStats() {
    try {
      const data = await api("/api/collection/stats");
      document.getElementById("stat-total-cards").textContent = data.total_cards.toLocaleString();
      document.getElementById("stat-unique-cards").textContent = data.unique_cards.toLocaleString();

      const val = parseFloat(data.total_value);
      document.getElementById("stat-total-value").textContent =
        val > 0 ? `$${val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "$0.00";

      const updatedEl = document.getElementById("stat-price-updated");
      if (data.price_updated_at) {
        const d = new Date(data.price_updated_at);
        updatedEl.textContent = `Prices: ${d.toLocaleDateString()}`;
      } else {
        updatedEl.textContent = "Prices: never updated";
      }
    } catch { /* ignore */ }
  }

  async function refreshPrices() {
    const btn = document.getElementById("refresh-prices-btn");
    btn.disabled = true;
    btn.textContent = "Refreshing...";

    try {
      const resp = await fetch("/api/prices/refresh", { method: "POST" });
      const data = await resp.json();
      if (data.ok) {
        btn.textContent = "Running...";
        // Poll for completion by checking stats periodically
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
          pollCount++;
          await loadStats();
          if (pollCount > 60) { // Stop after 5 minutes
            clearInterval(pollInterval);
            btn.disabled = false;
            btn.textContent = "Refresh Prices";
          }
        }, 5000);

        // Also update button after a reasonable time
        setTimeout(() => {
          clearInterval(pollInterval);
          btn.disabled = false;
          btn.textContent = "Refresh Prices";
          loadStats();
        }, 30000);
      }
    } catch {
      btn.disabled = false;
      btn.textContent = "Refresh Prices";
      alert("Failed to start price refresh");
    }
  }

  // ── Deduplicate ─────────────────────────────────────────────────────────────

  async function deduplicateCards() {
    if (!confirm("Merge duplicate cards that share the same printing, condition, finish, and language?\n\nQuantities will be combined.")) return;

    const btn = document.getElementById("dedupe-btn");
    btn.disabled = true;
    btn.textContent = "Merging...";

    try {
      const resp = await fetch("/api/collection/deduplicate", { method: "POST" });
      const data = await resp.json();
      btn.disabled = false;
      btn.textContent = "Deduplicate";

      if (data.ok) {
        if (data.removed_entries > 0) {
          alert(`Merged ${data.merged_groups} groups, removed ${data.removed_entries} duplicate entries.`);
          state.selectedCardUid = null;
          $detailPane.innerHTML = '<div class="detail-empty">Select a card to view details</div>';
          await refreshAll();
        } else {
          alert("No duplicates found.");
        }
      }
    } catch {
      btn.disabled = false;
      btn.textContent = "Deduplicate";
      alert("Failed to deduplicate");
    }
  }

  // ── Sidebar ────────────────────────────────────────────────────────────────

  async function loadSidebar() {
    $sidebarTree.innerHTML = '<div class="sidebar-loading">Loading...</div>';
    try {
      const data = await fetchGroups();
      renderSidebar(data);
    } catch {
      $sidebarTree.innerHTML = '<div class="sidebar-loading">Failed to load groups</div>';
    }
  }

  function renderSidebar(data) {
    const ul = document.createElement("ul");
    ul.className = "group-list";

    // "All" item
    const allLi = document.createElement("li");
    allLi.className = "group-item" + (state.selectedGroup === null ? " active" : "");
    allLi.innerHTML = `<span>All</span><span class="group-count">${data.total}</span>`;
    allLi.addEventListener("click", () => {
      state.selectedGroup = null;
      state.page = 1;
      refreshList();
      markActiveGroup();
    });
    ul.appendChild(allLi);

    for (const g of data.groups) {
      const li = document.createElement("li");
      li.className = "group-item" + (state.selectedGroup === g.value ? " active" : "");
      li.dataset.value = g.value;
      const label = document.createElement("span");
      label.textContent = g.label;
      label.style.overflow = "hidden";
      label.style.textOverflow = "ellipsis";
      const count = document.createElement("span");
      count.className = "group-count";
      count.textContent = g.count;
      li.appendChild(label);
      li.appendChild(count);
      li.addEventListener("click", () => {
        state.selectedGroup = g.value;
        state.page = 1;
        refreshList();
        markActiveGroup();
      });
      ul.appendChild(li);
    }

    $sidebarTree.innerHTML = "";
    $sidebarTree.appendChild(ul);
  }

  function markActiveGroup() {
    const items = $sidebarTree.querySelectorAll(".group-item");
    items.forEach((li, i) => {
      if (i === 0) {
        li.classList.toggle("active", state.selectedGroup === null);
      } else {
        li.classList.toggle("active", li.dataset.value === String(state.selectedGroup));
      }
    });
  }

  // ── Card list ──────────────────────────────────────────────────────────────

  async function loadList() {
    $listContent.innerHTML = '<div class="empty-state">Loading...</div>';
    try {
      const data = await fetchCards();
      if (state.viewMode === "grid") {
        renderGrid(data);
      } else {
        renderList(data);
      }
      renderPagination(data);
    } catch {
      $listContent.innerHTML = '<div class="empty-state">Failed to load cards</div>';
    }
  }

  function renderList(data) {
    if (!data.cards.length) {
      $listContent.innerHTML = '<div class="empty-state">No cards found</div>';
      return;
    }

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const sortCols = [
      { key: null, label: "", cls: "thumb-cell" },
      { key: "name", label: "Name" },
      { key: "set", label: "Set" },
      { key: "rarity", label: "Rarity" },
      { key: "condition", label: "Condition" },
      { key: "quantity", label: "Qty" },
      { key: "value", label: "Price" },
    ];
    const headRow = document.createElement("tr");
    for (const col of sortCols) {
      const th = document.createElement("th");
      if (col.cls) th.className = col.cls;
      if (col.key) {
        th.className = (th.className ? th.className + " " : "") + "sortable";
        if (state.sort === col.key) {
          th.classList.add("sorted");
          th.dataset.dir = state.sortDir;
        }
        th.textContent = col.label;
        th.addEventListener("click", () => {
          if (state.sort === col.key) {
            state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
          } else {
            state.sort = col.key;
            state.sortDir = "asc";
          }
          if ($listSort) $listSort.value = state.sort;
          state.page = 1;
          loadList();
        });
      }
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const card of data.cards) {
      const tr = document.createElement("tr");
      tr.dataset.uid = card.uid;
      if (card.uid === state.selectedCardUid) tr.className = "active";

      const imgSrc = card.image_url || "";
      const price = card.current_price && card.current_price !== "0.00"
        ? `$${card.current_price}`
        : "";

      tr.innerHTML = `
        <td class="thumb-cell">${imgSrc ? `<img src="${esc(imgSrc)}" alt="" loading="lazy">` : ""}</td>
        <td>${esc(card.name)}</td>
        <td class="muted">${esc(card.set_code || "")}</td>
        <td class="muted">${esc((card.rarity || "").charAt(0).toUpperCase() + (card.rarity || "").slice(1))}</td>
        <td><span class="condition-badge condition-${card.condition}">${esc(card.condition_label)}</span></td>
        <td>${card.quantity}</td>
        <td class="price">${price}</td>
      `;

      tr.addEventListener("click", () => selectCard(card.uid));
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);

    $listContent.innerHTML = "";
    $listContent.appendChild(table);
  }

  function renderGrid(data) {
    if (!data.cards.length) {
      $listContent.innerHTML = '<div class="empty-state">No cards found</div>';
      return;
    }

    const grid = document.createElement("div");
    grid.className = "card-grid";

    for (const card of data.cards) {
      const item = document.createElement("div");
      item.className = "card-grid-item" + (card.uid === state.selectedCardUid ? " active" : "");
      item.dataset.uid = card.uid;

      if (card.image_url) {
        item.innerHTML = `<img src="${esc(card.image_url)}" alt="${esc(card.name)}" loading="lazy">
          <div class="grid-label">${esc(card.name)}</div>`;
      } else {
        item.innerHTML = `<div style="aspect-ratio:488/680;background:var(--bg);display:flex;align-items:center;justify-content:center;font-size:0.75rem;color:var(--muted);padding:0.5rem;text-align:center">${esc(card.name)}</div>`;
      }

      item.addEventListener("click", () => selectCard(card.uid));
      grid.appendChild(item);
    }

    $listContent.innerHTML = "";
    $listContent.appendChild(grid);
  }

  function renderPagination(data) {
    if (data.pages <= 1) {
      $listPagination.innerHTML = `<span>${data.total} card${data.total !== 1 ? "s" : ""}</span><span></span>`;
      return;
    }

    $listPagination.innerHTML = `
      <span>Page ${data.page} of ${data.pages} (${data.total} cards)</span>
      <span>
        <button class="button button-sm" ${data.page <= 1 ? "disabled" : ""} id="page-prev">Prev</button>
        <button class="button button-sm" ${data.page >= data.pages ? "disabled" : ""} id="page-next">Next</button>
      </span>
    `;

    const prevBtn = document.getElementById("page-prev");
    const nextBtn = document.getElementById("page-next");
    if (prevBtn) prevBtn.addEventListener("click", () => { state.page--; loadList(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { state.page++; loadList(); });
  }

  async function selectCard(uid) {
    state.selectedCardUid = uid;

    // Mark active in list
    $listContent.querySelectorAll("[data-uid]").forEach(el => {
      el.classList.toggle("active", el.dataset.uid === uid);
    });

    // Load detail
    $detailPane.innerHTML = '<div class="detail-empty">Loading...</div>';
    try {
      const card = await fetchCardDetail(uid);
      renderDetail(card);
    } catch {
      $detailPane.innerHTML = '<div class="detail-empty">Failed to load card details</div>';
    }
  }

  // ── Detail panel ───────────────────────────────────────────────────────────

  function renderDetail(card) {
    const price = card.current_price && card.current_price !== "0.00" ? `$${card.current_price}` : "N/A";
    const totalVal = card.total_value && card.total_value !== "0.00" ? `$${card.total_value}` : "N/A";
    const purchasePrice = card.purchase_price && card.purchase_price !== "0.00" ? `$${card.purchase_price}` : "N/A";

    const locationParts = [card.binder, card.box, card.row, card.slot].filter(Boolean);
    const location = locationParts.length ? locationParts.join(" / ") : "Not specified";

    let tagsHtml = "";
    if (card.tag_list && card.tag_list.length) {
      tagsHtml = `<div class="detail-tags">
        <div class="detail-field-label">Tags</div>
        <div class="tag-row">${card.tag_list.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      </div>`;
    }

    let notesHtml = "";
    if (card.notes) {
      notesHtml = `<div class="detail-notes">
        <div class="detail-field-label">Notes</div>
        <div class="detail-notes-text">${esc(card.notes)}</div>
      </div>`;
    }

    let oracleHtml = "";
    if (card.oracle_text) {
      oracleHtml = `<div class="detail-oracle">
        <div class="detail-field-label">Oracle Text</div>
        <div class="detail-oracle-text">${esc(card.oracle_text)}</div>
      </div>`;
    }

    let scryfallLink = "";
    if (card.scryfall_uri) {
      scryfallLink = `<a href="${esc(card.scryfall_uri)}" target="_blank" rel="noreferrer" class="link-small">Scryfall ↗</a>`;
    }

    $detailPane.innerHTML = `
      <div class="detail-content">
        <div class="detail-image">
          ${card.image_url ? `<img src="${esc(card.image_url)}" alt="${esc(card.name)}">` : ""}
          ${scryfallLink ? `<div style="margin-top:0.5rem">${scryfallLink}</div>` : ""}
        </div>
        <div class="detail-meta">
          <div class="detail-header">
            <div>
              <h2 class="detail-name">${esc(card.name)}</h2>
              <p class="detail-set">${esc(card.set_name)}${card.collector_number ? ` · #${esc(card.collector_number)}` : ""}</p>
            </div>
            <div class="detail-actions">
              <button class="button button-sm" id="detail-edit-btn">Edit</button>
              <button class="button button-sm link-danger" id="detail-delete-btn" style="border-color:var(--error);color:var(--error)">Delete</button>
            </div>
          </div>
          <div class="detail-fields">
            <div class="detail-field">
              <div class="detail-field-label">Type</div>
              <div class="detail-field-value">${esc(card.type_line || "N/A")}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Mana Cost</div>
              <div class="detail-field-value">${esc(card.mana_cost || "N/A")}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Rarity</div>
              <div class="detail-field-value">${esc((card.rarity || "N/A").charAt(0).toUpperCase() + (card.rarity || "").slice(1))}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Color</div>
              <div class="detail-field-value">${esc(card.color_identity || "Colorless")}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Condition</div>
              <div class="detail-field-value"><span class="condition-badge condition-${card.condition}">${esc(card.condition_label)}</span></div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Finish</div>
              <div class="detail-field-value">${esc((card.finish || "").charAt(0).toUpperCase() + (card.finish || "").slice(1))}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Language</div>
              <div class="detail-field-value">${esc(card.language || "English")}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Quantity</div>
              <div class="detail-field-value">${card.quantity}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Market Price</div>
              <div class="detail-field-value price">${price}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Total Value</div>
              <div class="detail-field-value price">${totalVal}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Purchase Price</div>
              <div class="detail-field-value">${purchasePrice}</div>
            </div>
            <div class="detail-field">
              <div class="detail-field-label">Location</div>
              <div class="detail-field-value">${esc(location)}</div>
            </div>
            ${oracleHtml}
            ${tagsHtml}
            ${notesHtml}
          </div>
        </div>
      </div>
    `;

    // Bind detail actions
    document.getElementById("detail-edit-btn").addEventListener("click", () => openEditModal(card.uid));
    document.getElementById("detail-delete-btn").addEventListener("click", () => deleteCard(card.uid, card.name));
  }

  // ── Global search (add card) ───────────────────────────────────────────────

  function initGlobalSearch() {
    let timer = null;

    $globalSearch.addEventListener("input", () => {
      clearTimeout(timer);
      const q = $globalSearch.value.trim();
      if (q.length < 2) { $globalResults.hidden = true; return; }
      timer = setTimeout(async () => {
        try {
          const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
          const data = await resp.json();
          renderGlobalResults(data.results || []);
        } catch { $globalResults.hidden = true; }
      }, 250);
    });

    $globalSearch.addEventListener("blur", () => {
      setTimeout(() => { $globalResults.hidden = true; }, 200);
    });

    $globalSearch.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        $globalResults.hidden = true;
        $globalSearch.blur();
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const first = $globalResults.querySelector("li");
        if (first) first.click();
      }
    });

    function renderGlobalResults(results) {
      $globalResults.innerHTML = "";
      if (!results.length) { $globalResults.hidden = true; return; }
      for (const r of results.slice(0, 8)) {
        const li = document.createElement("li");
        const nameSpan = document.createElement("span");
        nameSpan.className = "gs-name";
        nameSpan.textContent = r.name;
        li.appendChild(nameSpan);
        if (r.owned > 0) {
          const badge = document.createElement("span");
          badge.className = "gs-owned";
          badge.textContent = `×${r.owned} owned`;
          li.appendChild(badge);
        }
        li.addEventListener("mousedown", (e) => {
          e.preventDefault();
          $globalSearch.value = "";
          $globalResults.hidden = true;
          openAddModal(r.name);
        });
        $globalResults.appendChild(li);
      }
      $globalResults.hidden = false;
    }
  }

  // ── Modal ──────────────────────────────────────────────────────────────────

  async function openAddModal(cardName) {
    try {
      const resp = await fetch("/api/card-form");
      const html = await resp.text();
      $modalContent.innerHTML = html;
      $modal.classList.add("open");
      bindModalEvents();
      initModalLookup(cardName);
    } catch {
      alert("Failed to load form");
    }
  }

  async function openEditModal(uid) {
    try {
      const resp = await fetch(`/api/card-form/${encodeURIComponent(uid)}`);
      const html = await resp.text();
      $modalContent.innerHTML = html;
      $modal.classList.add("open");
      bindModalEvents();
    } catch {
      alert("Failed to load form");
    }
  }

  function closeModal() {
    $modal.classList.remove("open");
    $modalContent.innerHTML = "";
  }

  function bindModalEvents() {
    const closeBtn = document.getElementById("modal-close-btn");
    const cancelBtn = document.getElementById("modal-cancel-btn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    const form = document.getElementById("modal-card-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const formData = new URLSearchParams(new FormData(form));
        try {
          const resp = await fetch(form.action, {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              "X-Requested-With": "XMLHttpRequest",
            },
            body: formData,
          });
          const data = await resp.json();
          if (data.ok) {
            closeModal();
            await refreshAll();
            if (data.card) {
              selectCard(data.card.uid);
            }
          } else {
            alert((data.errors || ["Unknown error"]).join("\n"));
          }
        } catch {
          alert("Failed to save card");
        }
      });
    }
  }

  function initModalLookup(prefilledName) {
    const searchInput = document.getElementById("modal-scryfall-search");
    if (!searchInput) return;

    const autocompleteList = document.getElementById("modal-autocomplete-list");
    const printSelectWrap = document.getElementById("modal-print-select-wrap");
    const printSelect = document.getElementById("modal-print-select");
    const lookupStatus = document.getElementById("modal-lookup-status");
    const formSection = document.getElementById("modal-card-form-section");
    const previewRow = document.getElementById("modal-card-preview-row");

    const fields = {
      name: document.getElementById("modal-f-name"),
      set_name: document.getElementById("modal-f-set-name"),
      set_code: document.getElementById("modal-f-set-code"),
      collector_number: document.getElementById("modal-f-collector-number"),
      scryfall_id: document.getElementById("modal-f-scryfall-id"),
      oracle_id: document.getElementById("modal-f-oracle-id"),
      type_line: document.getElementById("modal-f-type-line"),
      mana_cost: document.getElementById("modal-f-mana-cost"),
      oracle_text: document.getElementById("modal-f-oracle-text"),
      rarity: document.getElementById("modal-f-rarity"),
      color_identity: document.getElementById("modal-f-color-identity"),
      image_url: document.getElementById("modal-f-image-url"),
      scryfall_uri: document.getElementById("modal-f-scryfall-uri"),
      market_price: document.getElementById("modal-f-market-price"),
      foil_price: document.getElementById("modal-f-foil-price"),
    };

    let debounceTimer = null;

    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const q = searchInput.value.trim();
      if (q.length < 2) { autocompleteList.hidden = true; return; }
      debounceTimer = setTimeout(async () => {
        try {
          const resp = await fetch(`/api/autocomplete?q=${encodeURIComponent(q)}`);
          const data = await resp.json();
          renderAutoList(data.results || []);
        } catch { autocompleteList.hidden = true; }
      }, 250);
    });

    function renderAutoList(results) {
      autocompleteList.innerHTML = "";
      if (!results.length) { autocompleteList.hidden = true; return; }
      for (const name of results.slice(0, 8)) {
        const li = document.createElement("li");
        li.textContent = name;
        li.addEventListener("mousedown", (e) => { e.preventDefault(); pickName(name); });
        autocompleteList.appendChild(li);
      }
      autocompleteList.hidden = false;
    }

    searchInput.addEventListener("blur", () => {
      setTimeout(() => { autocompleteList.hidden = true; }, 150);
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const first = autocompleteList.querySelector("li");
        if (first) pickName(first.textContent);
      }
    });

    async function pickName(name) {
      searchInput.value = name;
      autocompleteList.hidden = true;
      lookupStatus.textContent = "Loading printings...";
      lookupStatus.hidden = false;
      printSelectWrap.hidden = true;
      formSection.hidden = true;

      try {
        const resp = await fetch(`/api/prints?name=${encodeURIComponent(name)}`);
        const data = await resp.json();
        const prints = data.results || [];
        if (!prints.length) { lookupStatus.textContent = "No printings found."; return; }
        renderPrints(prints);
        lookupStatus.hidden = true;
      } catch { lookupStatus.textContent = "Failed to load printings."; }
    }

    function renderPrints(prints) {
      printSelect.innerHTML = '<option value="">Select printing...</option>';
      for (const p of prints) {
        const opt = document.createElement("option");
        opt.value = p.scryfall_id;
        opt.textContent = `${p.set_name} (${p.set_code}) · #${p.collector_number} · ${p.rarity}${p.market_price ? " · $" + p.market_price : ""}`;
        opt.dataset.card = JSON.stringify(p);
        printSelect.appendChild(opt);
      }
      printSelectWrap.hidden = false;
      printSelect.focus();
    }

    printSelect.addEventListener("change", () => {
      const opt = printSelect.selectedOptions[0];
      if (!opt || !opt.dataset.card) { formSection.hidden = true; return; }
      const card = JSON.parse(opt.dataset.card);
      fillModalForm(card);
    });

    function fillModalForm(card) {
      for (const [key, el] of Object.entries(fields)) {
        if (el) el.value = card[key] || "";
      }

      const img = document.getElementById("modal-card-preview-img");
      if (img) { img.src = card.image_url || ""; img.alt = card.name || ""; }
      const nameEl = document.getElementById("modal-preview-name");
      if (nameEl) nameEl.textContent = card.name || "";
      const setEl = document.getElementById("modal-preview-set");
      if (setEl) setEl.textContent = `${card.set_name}${card.collector_number ? " · #" + card.collector_number : ""}`;
      const typeEl = document.getElementById("modal-preview-type");
      if (typeEl) typeEl.textContent = card.type_line || "";

      const scryfallLink = document.getElementById("modal-preview-scryfall-link");
      if (scryfallLink && card.scryfall_uri) {
        scryfallLink.href = card.scryfall_uri;
        scryfallLink.hidden = false;
      }

      const finishSelect = document.getElementById("modal-f-finish");
      if (finishSelect) {
        finishSelect.value = (card.foil_price && !card.market_price) ? "foil" : "nonfoil";
      }

      if (previewRow) previewRow.hidden = false;
      formSection.hidden = false;
    }

    if (prefilledName) {
      pickName(prefilledName);
    } else {
      setTimeout(() => searchInput.focus(), 100);
    }
  }

  // ── Changelog modal ────────────────────────────────────────────────────────

  async function openChangelog() {
    $modalContent.innerHTML = `
      <div class="modal-header">
        <h3>Changelog</h3>
        <button type="button" class="modal-close" id="modal-close-btn">&times;</button>
      </div>
      <div class="changelog-list" id="changelog-list">
        <div class="muted small" style="padding:1rem;text-align:center">Loading...</div>
      </div>
    `;
    $modal.classList.add("open");
    document.getElementById("modal-close-btn").addEventListener("click", closeModal);
    await loadChangelog();
  }

  async function loadChangelog() {
    const listEl = document.getElementById("changelog-list");
    try {
      const data = await api("/api/changelog");
      const entries = data.entries || [];

      if (!entries.length) {
        listEl.innerHTML = '<div class="muted small" style="padding:1rem;text-align:center">No changelog entries yet</div>';
        return;
      }

      listEl.innerHTML = "";
      for (const entry of entries) {
        const div = document.createElement("div");
        div.className = "changelog-entry";

        const date = new Date(entry.created_at);
        const dateStr = date.toLocaleDateString() + " " + date.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
        const canUndo = entry.action === "add" || entry.action === "import" || entry.action === "delete";

        div.innerHTML = `
          <div class="changelog-info">
            <div class="changelog-desc">
              <span class="changelog-action-badge ${esc(entry.action)}">${esc(entry.action)}</span>
              ${esc(entry.description)}
            </div>
            <div class="changelog-date">${esc(dateStr)}</div>
          </div>
          ${canUndo ? `<button class="button button-sm changelog-undo-btn" data-uid="${esc(entry.uid)}">Undo</button>` : ""}
        `;
        listEl.appendChild(div);
      }

      listEl.querySelectorAll(".changelog-undo-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          if (!confirm("Undo this action?")) return;
          btn.disabled = true;
          btn.textContent = "Undoing...";
          try {
            const resp = await fetch(`/api/changelog/${encodeURIComponent(btn.dataset.uid)}/undo`, { method: "POST" });
            const result = await resp.json();
            if (result.ok) {
              await loadChangelog();
              refreshAll();
            } else {
              alert((result.errors || ["Undo failed"]).join("\n"));
              btn.disabled = false;
              btn.textContent = "Undo";
            }
          } catch {
            alert("Failed to undo");
            btn.disabled = false;
            btn.textContent = "Undo";
          }
        });
      });
    } catch {
      listEl.innerHTML = '<div class="muted small" style="padding:1rem;text-align:center">Failed to load changelog</div>';
    }
  }

  // ── Delete all ─────────────────────────────────────────────────────────────

  function openDeleteAll() {
    $modalContent.innerHTML = `
      <div class="modal-header">
        <h3>Delete All Cards</h3>
        <button type="button" class="modal-close" id="modal-close-btn">&times;</button>
      </div>
      <p style="color:var(--error);font-size:0.9rem">
        This will permanently delete every card in your collection. This cannot be undone.
      </p>
      <p class="muted small">Type <strong>delete-all</strong> to confirm:</p>
      <input type="text" id="delete-all-input" class="delete-all-input" placeholder="delete-all" autocomplete="off">
      <div class="form-submit-row">
        <button class="button" id="delete-all-confirm-btn" style="background:var(--error);border-color:var(--error);color:#fff" disabled>Delete All Cards</button>
        <button class="button button-secondary" id="delete-all-cancel-btn">Cancel</button>
      </div>
    `;
    $modal.classList.add("open");

    document.getElementById("modal-close-btn").addEventListener("click", closeModal);
    document.getElementById("delete-all-cancel-btn").addEventListener("click", closeModal);

    const input = document.getElementById("delete-all-input");
    const confirmBtn = document.getElementById("delete-all-confirm-btn");

    input.addEventListener("input", () => {
      confirmBtn.disabled = input.value.trim() !== "delete-all";
    });

    confirmBtn.addEventListener("click", async () => {
      confirmBtn.disabled = true;
      confirmBtn.textContent = "Deleting...";
      try {
        const resp = await fetch("/api/collection/delete-all", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmation: input.value.trim() }),
        });
        const data = await resp.json();
        if (data.ok) {
          closeModal();
          state.selectedCardUid = null;
          $detailPane.innerHTML = '<div class="detail-empty">Select a card to view details</div>';
          await refreshAll();
        } else {
          alert((data.errors || ["Delete failed"]).join("\n"));
          confirmBtn.disabled = false;
          confirmBtn.textContent = "Delete All Cards";
        }
      } catch {
        alert("Failed to delete");
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Delete All Cards";
      }
    });

    setTimeout(() => input.focus(), 100);
  }

  // ── Import modal ───────────────────────────────────────────────────────────

  let importResolvedCards = [];

  async function openImportModal() {
    try {
      const resp = await fetch("/api/import-form");
      const html = await resp.text();
      $modalContent.innerHTML = html;
      $modal.classList.add("open");
      bindImportEvents();
    } catch {
      alert("Failed to load import form");
    }
  }

  function bindImportEvents() {
    const closeBtn = document.getElementById("modal-close-btn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);

    // Tab switching
    const tabs = document.querySelectorAll(".import-tab");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        tabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        document.querySelectorAll(".import-tab-content").forEach(c => c.classList.remove("active"));
        const target = document.getElementById(`import-tab-${tab.dataset.tab}`);
        if (target) target.classList.add("active");
      });
    });

    // Parse text list
    const parseTextBtn = document.getElementById("import-parse-text-btn");
    if (parseTextBtn) {
      parseTextBtn.addEventListener("click", async () => {
        const content = document.getElementById("import-text-input").value;
        if (!content.trim()) return;
        await parseImport("text", content);
      });
    }

    // CSV file upload
    const csvFile = document.getElementById("import-csv-file");
    if (csvFile) {
      csvFile.addEventListener("change", async () => {
        const file = csvFile.files[0];
        if (!file) return;
        const content = await file.text();
        await parseImport("csv", content);
      });
    }

    // Precon / Set search
    const preconSearch = document.getElementById("precon-search");
    if (preconSearch) {
      let preconTimer = null;
      preconSearch.addEventListener("input", () => {
        clearTimeout(preconTimer);
        const q = preconSearch.value.trim();
        if (q.length < 2) {
          document.getElementById("precon-results").innerHTML = "";
          return;
        }
        preconTimer = setTimeout(() => runPreconSearch(q), 300);
      });

      // Also re-search when radio changes
      document.querySelectorAll('input[name="precon-type"]').forEach(radio => {
        radio.addEventListener("change", () => {
          const q = preconSearch.value.trim();
          if (q.length >= 2) runPreconSearch(q);
        });
      });
    }
  }

  function getPreconSearchType() {
    const radio = document.querySelector('input[name="precon-type"]:checked');
    return radio ? radio.value : "decks";
  }

  async function runPreconSearch(query) {
    const type = getPreconSearchType();
    if (type === "decks") {
      await searchDecks(query);
    } else {
      await searchSets(query);
    }
  }

  async function searchDecks(query) {
    const resultsEl = document.getElementById("precon-results");
    resultsEl.innerHTML = '<div class="muted small">Searching decks...</div>';

    try {
      const resp = await fetch(`/api/decks/search?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      const decks = data.results || [];

      if (!decks.length) {
        resultsEl.innerHTML = '<div class="muted small">No decks found</div>';
        return;
      }

      resultsEl.innerHTML = "";
      for (const d of decks) {
        const item = document.createElement("div");
        item.className = "precon-result-item";

        item.innerHTML = `
          <div class="precon-result-info">
            <strong>${esc(d.name)}</strong>
            <span class="muted small">${esc(d.code)} · ${esc(d.type)}${d.releaseDate ? ` · ${esc(d.releaseDate)}` : ""}</span>
          </div>
          <button class="button button-sm button-accent precon-load-btn" data-filename="${esc(d.fileName)}">Load</button>
        `;
        resultsEl.appendChild(item);
      }

      resultsEl.querySelectorAll(".precon-load-btn").forEach(btn => {
        btn.addEventListener("click", () => loadDeck(btn.dataset.filename));
      });
    } catch {
      resultsEl.innerHTML = '<div class="muted small">Search failed</div>';
    }
  }

  async function searchSets(query) {
    const resultsEl = document.getElementById("precon-results");
    resultsEl.innerHTML = '<div class="muted small">Searching sets...</div>';

    try {
      const resp = await fetch(`/api/sets/search?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      const sets = data.results || [];

      if (!sets.length) {
        resultsEl.innerHTML = '<div class="muted small">No sets found</div>';
        return;
      }

      resultsEl.innerHTML = "";
      for (const s of sets) {
        const item = document.createElement("div");
        item.className = "precon-result-item";

        const typeLabel = s.set_type.replace(/_/g, " ");
        item.innerHTML = `
          <div class="precon-result-info">
            <strong>${esc(s.name)}</strong>
            <span class="muted small">${esc(s.code.toUpperCase())} · ${esc(typeLabel)} · ${s.card_count} cards${s.released_at ? ` · ${esc(s.released_at)}` : ""}</span>
          </div>
          <button class="button button-sm button-accent precon-load-btn" data-code="${esc(s.code)}">Load</button>
        `;
        resultsEl.appendChild(item);
      }

      resultsEl.querySelectorAll(".precon-load-btn").forEach(btn => {
        btn.addEventListener("click", () => loadPreconSet(btn.dataset.code));
      });
    } catch {
      resultsEl.innerHTML = '<div class="muted small">Search failed</div>';
    }
  }

  async function loadDeck(fileName) {
    const progress = document.getElementById("import-progress");
    const progressText = document.getElementById("import-progress-text");
    const preview = document.getElementById("import-preview");
    const result = document.getElementById("import-result");

    progress.hidden = false;
    progressText.textContent = "Loading deck from MTGJSON and resolving cards on Scryfall...";
    preview.hidden = true;
    result.hidden = true;

    try {
      const resp = await fetch(`/api/decks/${encodeURIComponent(fileName)}/cards`);
      const data = await resp.json();

      progress.hidden = true;

      if (!data.ok || !data.cards.length) {
        alert("No cards found in this deck.");
        return;
      }

      importResolvedCards = data.cards;
      renderImportPreview(data.cards, data.warnings || []);
    } catch {
      progress.hidden = true;
      alert("Failed to load deck");
    }
  }

  async function loadPreconSet(setCode) {
    const progress = document.getElementById("import-progress");
    const progressText = document.getElementById("import-progress-text");
    const preview = document.getElementById("import-preview");
    const result = document.getElementById("import-result");

    progress.hidden = false;
    progressText.textContent = `Loading cards from set ${setCode.toUpperCase()}...`;
    preview.hidden = true;
    result.hidden = true;

    try {
      const resp = await fetch(`/api/sets/${encodeURIComponent(setCode)}/cards`);
      const data = await resp.json();

      progress.hidden = true;

      if (!data.ok || !data.cards.length) {
        alert("No cards found in this set.");
        return;
      }

      importResolvedCards = data.cards;
      renderImportPreview(data.cards, []);
    } catch {
      progress.hidden = true;
      alert("Failed to load set cards");
    }
  }

  async function parseImport(format, content) {
    const progress = document.getElementById("import-progress");
    const preview = document.getElementById("import-preview");
    const result = document.getElementById("import-result");

    progress.hidden = false;
    preview.hidden = true;
    result.hidden = true;

    try {
      const formData = new FormData();
      formData.append("format", format);
      formData.append("content", content);

      const resp = await fetch("/api/import/parse", { method: "POST", body: formData });
      const data = await resp.json();

      progress.hidden = true;

      if (!data.ok) {
        alert((data.errors || ["Parse failed"]).join("\n"));
        return;
      }

      importResolvedCards = data.cards;
      renderImportPreview(data.cards, data.warnings);
    } catch {
      progress.hidden = true;
      alert("Failed to parse import");
    }
  }

  function renderImportPreview(cards, warnings) {
    const preview = document.getElementById("import-preview");
    const warningsEl = document.getElementById("import-warnings");
    const body = document.getElementById("import-preview-body");
    const countEl = document.getElementById("import-preview-count");

    // Warnings
    if (warnings && warnings.length) {
      warningsEl.innerHTML = warnings.map(w =>
        `<div class="import-warning">${esc(w)}</div>`
      ).join("");
    } else {
      warningsEl.innerHTML = "";
    }

    // Count
    const totalQty = cards.reduce((sum, c) => sum + c.quantity, 0);
    countEl.textContent = `${cards.length} unique cards, ${totalQty} total`;

    // Table rows
    body.innerHTML = "";
    cards.forEach((card, idx) => {
      const tr = document.createElement("tr");
      if (!card.matched) tr.classList.add("import-unmatched");

      const price = card.market_price ? `$${card.market_price}` : "";
      const statusIcon = card.matched
        ? '<span style="color:var(--success)">&#10003;</span>'
        : '<span style="color:var(--warning)">?</span>';

      tr.innerHTML = `
        <td>${statusIcon}</td>
        <td>${esc(card.name)}</td>
        <td class="muted">${esc(card.set_code || card.set_name || "")}</td>
        <td>${card.quantity}</td>
        <td class="muted">${esc(card.condition || "near_mint")}</td>
        <td class="muted">${esc(card.finish || "nonfoil")}</td>
        <td class="price">${price}</td>
        <td><button class="link-button link-danger import-remove-btn" data-idx="${idx}">&times;</button></td>
      `;
      body.appendChild(tr);
    });

    // Remove buttons
    body.querySelectorAll(".import-remove-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        importResolvedCards.splice(idx, 1);
        renderImportPreview(importResolvedCards, []);
      });
    });

    // Commit button
    const commitBtn = document.getElementById("import-commit-btn");
    commitBtn.onclick = () => commitImport();

    preview.hidden = false;
  }

  async function commitImport() {
    if (!importResolvedCards.length) return;

    const commitBtn = document.getElementById("import-commit-btn");
    commitBtn.disabled = true;
    commitBtn.textContent = "Importing...";

    try {
      const resp = await fetch("/api/import/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards: importResolvedCards }),
      });
      const data = await resp.json();

      if (data.ok) {
        document.getElementById("import-preview").hidden = true;
        const result = document.getElementById("import-result");
        const totalQty = importResolvedCards.reduce((sum, c) => sum + (c.quantity || 1), 0);
        let msg = `Successfully imported ${totalQty} card${totalQty !== 1 ? "s" : ""}`;
        if (data.created || data.merged) {
          const parts = [];
          if (data.created) parts.push(`${data.created} new`);
          if (data.merged) parts.push(`${data.merged} merged with existing`);
          msg += ` (${parts.join(", ")})`;
        }
        msg += ".";
        result.querySelector(".import-result-message").textContent = msg;
        result.hidden = false;

        const doneBtn = document.getElementById("import-done-btn");
        doneBtn.onclick = () => {
          closeModal();
          refreshAll();
        };
      } else {
        alert((data.errors || ["Import failed"]).join("\n"));
        commitBtn.disabled = false;
        commitBtn.textContent = "Import All";
      }
    } catch {
      alert("Failed to import cards");
      commitBtn.disabled = false;
      commitBtn.textContent = "Import All";
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────────────

  async function deleteCard(uid, name) {
    if (!confirm(`Delete ${name}?`)) return;
    try {
      const resp = await fetch(`/cards/${encodeURIComponent(uid)}/delete`, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await resp.json();
      if (data.ok) {
        state.selectedCardUid = null;
        $detailPane.innerHTML = '<div class="detail-empty">Select a card to view details</div>';
        await refreshAll();
      }
    } catch {
      alert("Failed to delete card");
    }
  }

  // ── Resize handles ─────────────────────────────────────────────────────────

  function initResize() {
    // Restore saved positions
    const savedSidebar = localStorage.getItem("mtg-sidebar-width");
    const savedListRatio = localStorage.getItem("mtg-list-ratio");

    if (savedSidebar) {
      $layout.style.setProperty("--sidebar-width", savedSidebar + "px");
    }
    if (savedListRatio) {
      const ratio = parseFloat(savedListRatio);
      $layout.querySelector(".right-panes").style.setProperty("--list-height", `${ratio}fr`);
      $layout.querySelector(".right-panes").style.setProperty("--detail-height", `${1 - ratio}fr`);
    }

    // Vertical resize (sidebar width)
    initDragHandle($resizeV, "col", (delta) => {
      const currentWidth = $layout.querySelector(".group-sidebar").getBoundingClientRect().width;
      const newWidth = Math.max(150, Math.min(500, currentWidth + delta));
      $layout.style.setProperty("--sidebar-width", newWidth + "px");
      localStorage.setItem("mtg-sidebar-width", newWidth);
    });

    // Horizontal resize (list/detail split)
    initDragHandle($resizeH, "row", (delta) => {
      const rightPanes = $layout.querySelector(".right-panes");
      const totalHeight = rightPanes.getBoundingClientRect().height;
      const listPane = document.getElementById("list-pane");
      const currentListHeight = listPane.getBoundingClientRect().height;
      const newRatio = Math.max(0.15, Math.min(0.85, (currentListHeight + delta) / totalHeight));
      rightPanes.style.setProperty("--list-height", `${newRatio}fr`);
      rightPanes.style.setProperty("--detail-height", `${1 - newRatio}fr`);
      localStorage.setItem("mtg-list-ratio", newRatio);
    });
  }

  function initDragHandle(handle, direction, onMove) {
    let startPos = 0;

    function onMouseDown(e) {
      e.preventDefault();
      startPos = direction === "col" ? e.clientX : e.clientY;
      handle.classList.add("dragging");
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    }

    function onMouseMove(e) {
      const currentPos = direction === "col" ? e.clientX : e.clientY;
      const delta = currentPos - startPos;
      startPos = currentPos;
      onMove(delta);
    }

    function onMouseUp() {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    }

    handle.addEventListener("mousedown", onMouseDown);
  }

  // ── Keyboard navigation ────────────────────────────────────────────────────

  function initKeyboard() {
    document.addEventListener("keydown", (e) => {
      // Don't handle if typing in an input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if ($modal.classList.contains("open")) return;

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        navigateList(e.key === "ArrowDown" ? 1 : -1);
      }
    });
  }

  function navigateList(direction) {
    const rows = $listContent.querySelectorAll("[data-uid]");
    if (!rows.length) return;

    let currentIndex = -1;
    rows.forEach((el, i) => {
      if (el.dataset.uid === state.selectedCardUid) currentIndex = i;
    });

    let newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = 0;
    if (newIndex >= rows.length) newIndex = rows.length - 1;

    const uid = rows[newIndex].dataset.uid;
    selectCard(uid);

    // Scroll into view
    rows[newIndex].scrollIntoView({ block: "nearest" });
  }

  // ── Utility ────────────────────────────────────────────────────────────────

  function esc(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Refresh helpers ────────────────────────────────────────────────────────

  async function refreshList() {
    await loadList();
  }

  async function refreshAll() {
    await Promise.all([loadStats(), loadSidebar(), loadList()]);
  }

  // ── Event bindings & init ──────────────────────────────────────────────────

  function init() {
    // Group by change
    $groupBySelect.addEventListener("change", () => {
      state.groupBy = $groupBySelect.value;
      state.selectedGroup = null;
      state.page = 1;
      loadSidebar();
      loadList();
    });

    // Search with debounce
    let searchTimer = null;
    $listSearch.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        state.search = $listSearch.value.trim();
        state.page = 1;
        loadList();
      }, 300);
    });

    // Sort
    $listSort.addEventListener("change", () => {
      state.sort = $listSort.value;
      state.sortDir = "asc";
      state.page = 1;
      loadList();
    });

    // View toggle
    $viewToggle.addEventListener("click", () => {
      state.viewMode = state.viewMode === "list" ? "grid" : "list";
      $viewToggle.textContent = state.viewMode === "list" ? "Grid" : "List";
      loadList();
    });

    // Refresh prices
    document.getElementById("refresh-prices-btn").addEventListener("click", refreshPrices);

    // Tools menu
    const toolsBtn = document.getElementById("tools-menu-btn");
    const toolsMenu = document.getElementById("tools-menu");
    toolsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toolsMenu.hidden = !toolsMenu.hidden;
    });
    document.addEventListener("click", () => { toolsMenu.hidden = true; });
    toolsMenu.addEventListener("click", (e) => e.stopPropagation());

    document.getElementById("refresh-prices-btn").addEventListener("click", () => {
      toolsMenu.hidden = true;
      refreshPrices();
    });
    document.getElementById("dedupe-btn").addEventListener("click", () => {
      toolsMenu.hidden = true;
      deduplicateCards();
    });
    document.getElementById("changelog-btn").addEventListener("click", () => {
      toolsMenu.hidden = true;
      openChangelog();
    });
    document.getElementById("delete-all-btn").addEventListener("click", () => {
      toolsMenu.hidden = true;
      openDeleteAll();
    });

    // Import
    document.getElementById("import-btn").addEventListener("click", openImportModal);

    // Global search (add card)
    initGlobalSearch();

    // Close modal on overlay click
    $modal.addEventListener("click", (e) => {
      if (e.target === $modal) closeModal();
    });

    // Escape to close modal
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $modal.classList.contains("open")) closeModal();
    });

    initResize();
    initKeyboard();

    // Initial load
    loadStats();
    loadSidebar();
    loadList();
  }

  init();
})();
