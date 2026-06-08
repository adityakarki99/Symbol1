const state = {
  symbols: [],
  categories: [],
  tags: [],
  query: "",
  category: "",
  tag: "",
  sort: "name-asc",
};

const els = {
  loading: document.getElementById("loading"),
  grid: document.getElementById("symbol-grid"),
  empty: document.getElementById("empty-state"),
  search: document.getElementById("search"),
  sort: document.getElementById("sort"),
  categoryList: document.getElementById("category-list"),
  tagCloud: document.getElementById("tag-cloud"),
  viewTitle: document.getElementById("view-title"),
  resultCount: document.getElementById("result-count"),
  totalCount: document.getElementById("total-count"),
  dialog: document.getElementById("detail-dialog"),
  closeDetail: document.getElementById("close-detail"),
  sidebar: document.getElementById("sidebar"),
  sidebarToggle: document.getElementById("sidebar-toggle"),
};

async function loadData() {
  const [symbols, categories, tags] = await Promise.all([
    fetch("./data/symbols.json").then((r) => r.json()),
    fetch("./data/categories.json").then((r) => r.json()),
    fetch("./data/tags.json").then((r) => r.json()),
  ]);
  state.symbols = symbols;
  state.categories = categories.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  state.tags = tags.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function renderCategories() {
  els.totalCount.textContent = `(${state.symbols.length})`;
  els.categoryList.innerHTML = state.categories
    .map(
      (cat) => `
      <button class="category-btn" data-category="${escapeHtml(cat.name)}">
        <span>${escapeHtml(cat.name)}</span>
        <span>${cat.count}</span>
      </button>`
    )
    .join("");
}

function renderTags() {
  const topTags = state.tags.slice(0, 24);
  els.tagCloud.innerHTML = topTags
    .map(
      (tag) => `
      <button class="tag-btn" data-tag="${escapeHtml(tag.name)}">${escapeHtml(tag.name)}</button>`
    )
    .join("");
}

function getFilteredSymbols() {
  const q = state.query.trim().toLowerCase();
  let results = state.symbols;

  if (state.category) {
    results = results.filter((s) => s.categories.includes(state.category) || s.culture === state.category);
  }

  if (state.tag) {
    results = results.filter((s) => s.tags.includes(state.tag));
  }

  if (q) {
    results = results.filter((s) => {
      const haystack = [
        s.name,
        s.culture,
        s.region,
        s.description,
        s.general_info,
        ...(s.tags || []),
        ...(s.categories || []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }

  results = [...results];
  if (state.sort === "name-asc") results.sort((a, b) => a.name.localeCompare(b.name));
  if (state.sort === "name-desc") results.sort((a, b) => b.name.localeCompare(a.name));
  if (state.sort === "culture-asc") {
    results.sort((a, b) => (a.culture || "").localeCompare(b.culture || "") || a.name.localeCompare(b.name));
  }

  return results;
}

function renderGrid() {
  const results = getFilteredSymbols();
  const titleParts = [];
  if (state.category) titleParts.push(state.category);
  if (state.tag) titleParts.push(`#${state.tag}`);
  els.viewTitle.textContent = titleParts.length ? titleParts.join(" · ") : "All Symbols";
  els.resultCount.textContent = `${results.length} symbol${results.length === 1 ? "" : "s"}`;

  if (!results.length) {
    els.grid.innerHTML = "";
    els.empty.classList.remove("hidden");
    return;
  }

  els.empty.classList.add("hidden");
  els.grid.innerHTML = results
    .map(
      (symbol) => `
      <article class="symbol-card" data-id="${escapeHtml(symbol.id)}" tabindex="0">
        <img src="${escapeHtml(symbol.image_url || "")}" alt="${escapeHtml(symbol.name)}" loading="lazy" onerror="this.style.visibility='hidden'" />
        <div>
          <h3>${escapeHtml(symbol.name)}</h3>
          <p>${escapeHtml(symbol.culture || symbol.categories[0] || "Symbol")}</p>
        </div>
      </article>`
    )
    .join("");
}

function openDetail(symbolId) {
  const symbol = state.symbols.find((s) => s.id === symbolId);
  if (!symbol) return;

  document.getElementById("detail-name").textContent = symbol.name;
  document.getElementById("detail-culture").textContent = symbol.culture || symbol.categories.join(", ");
  document.getElementById("detail-description").textContent = symbol.description || "No description available.";
  document.getElementById("detail-general").textContent = symbol.general_info || "";
  document.getElementById("detail-source").href = symbol.url;

  const image = document.getElementById("detail-image");
  image.src = symbol.image_url || "";
  image.alt = symbol.name;

  const generalSection = document.getElementById("general-section");
  if (symbol.general_info) generalSection.classList.remove("hidden");
  else generalSection.classList.add("hidden");

  document.getElementById("detail-tags").innerHTML = (symbol.tags || [])
    .slice(0, 12)
    .map((tag) => `<span>${escapeHtml(tag)}</span>`)
    .join("");

  els.dialog.showModal();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setActiveButtons() {
  document.querySelectorAll(".filter-btn, .category-btn").forEach((btn) => {
    const cat = btn.dataset.category ?? "";
    btn.classList.toggle("active", cat === state.category);
  });
  document.querySelectorAll(".tag-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tag === state.tag);
  });
}

function bindEvents() {
  let searchTimer;
  els.search.addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = event.target.value;
      renderGrid();
    }, 180);
  });

  els.sort.addEventListener("change", (event) => {
    state.sort = event.target.value;
    renderGrid();
  });

  document.querySelector(".filter-btn[data-category='']").addEventListener("click", () => {
    state.category = "";
    state.tag = "";
    setActiveButtons();
    renderGrid();
    els.sidebar.classList.remove("open");
  });

  els.categoryList.addEventListener("click", (event) => {
    const btn = event.target.closest(".category-btn");
    if (!btn) return;
    state.category = btn.dataset.category;
    state.tag = "";
    setActiveButtons();
    renderGrid();
    els.sidebar.classList.remove("open");
  });

  els.tagCloud.addEventListener("click", (event) => {
    const btn = event.target.closest(".tag-btn");
    if (!btn) return;
    state.tag = state.tag === btn.dataset.tag ? "" : btn.dataset.tag;
    setActiveButtons();
    renderGrid();
    els.sidebar.classList.remove("open");
  });

  els.grid.addEventListener("click", (event) => {
    const card = event.target.closest(".symbol-card");
    if (!card) return;
    openDetail(card.dataset.id);
  });

  els.grid.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const card = event.target.closest(".symbol-card");
    if (!card) return;
    event.preventDefault();
    openDetail(card.dataset.id);
  });

  els.closeDetail.addEventListener("click", () => els.dialog.close());
  els.dialog.addEventListener("click", (event) => {
    const rect = els.dialog.querySelector(".detail-inner").getBoundingClientRect();
    const inside =
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom;
    if (!inside) els.dialog.close();
  });

  els.sidebarToggle.addEventListener("click", () => {
    els.sidebar.classList.toggle("open");
  });
}

async function init() {
  try {
    await loadData();
    renderCategories();
    renderTags();
    bindEvents();
    renderGrid();
  } catch (error) {
    els.loading.innerHTML = `<p>Failed to load symbol data: ${escapeHtml(error.message)}</p>`;
    return;
  }
  els.loading.classList.add("hidden");
}

init();
