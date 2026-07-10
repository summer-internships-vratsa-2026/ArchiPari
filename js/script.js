/* =========================================================
   СтройЦени — основна логика на сайта
   - Зарежда данните за цени (data/products.json, с fallback
     към вградения js/data.js, за да работи и без локален сървър)
   - Търсене, филтриране по категория, магазини и сортиране
   - Проста обработка на контактната форма (front-end demo)
   ========================================================= */
 
(function () {
  "use strict";
 
  let DATA = null;
  const state = {
    query: "",
    category: "all",
    sort: "name-asc",
    activeStores: new Set()
  };
 
  /* ---------- Зареждане на данни ---------- */
 
  async function loadData() {
    try {
      const res = await fetch("data/products.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
    } catch (err) {
      // Ако страницата е отворена директно като файл (file://) fetch ще се провали
      // заради CORS — тогава ползваме вградените данни от js/data.js.
      if (window.STROYTSENI_DATA) {
        DATA = window.STROYTSENI_DATA;
      } else {
        console.error("Неуспешно зареждане на данните за цени:", err);
      }
    }
    if (DATA) normalizeData();
  }
 
  /* Прави данните "сигурни" за рендериране, дори ако products.json
     идва от стар формат (prices) или някой продукт има непълни данни.
     Без това една-единствена лоша офертата гърми целия сайт. */
  function normalizeData() {
    if (!Array.isArray(DATA.products)) {
      DATA.products = [];
      return;
    }
    DATA.products.forEach(p => {
      if (!p.offers || typeof p.offers !== "object") {
        if (p.prices && typeof p.prices === "object") {
          // Стар формат -> преобразуваме на място (само в паметта на браузъра;
          // реалният файл се мигрира трайно при следващо пускане на run_all.py).
          p.offers = {};
          Object.entries(p.prices).forEach(([storeId, price]) => {
            p.offers[storeId] = { price, image: null, url: null };
          });
        } else {
          p.offers = {};
        }
      }
    });
  }
 
  function formatEUR(value) {
  return value.toFixed(2).replace(".", ",") + " €";
}
 
  function formatDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString("bg-BG", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit"
      });
    } catch (e) {
      return iso;
    }
  }
 
  /* ---------- Изграждане на филтрите ---------- */
 
  function buildCategoryOptions() {
    const select = document.getElementById("categoryFilter");
    if (!select || !DATA) return;
    DATA.categories.forEach(cat => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      select.appendChild(opt);
    });
  }
 
  function buildStoreToggles() {
    const wrap = document.getElementById("storeToggles");
    if (!wrap || !DATA) return;
    DATA.stores.forEach(store => {
      state.activeStores.add(store.id);
 
      const label = document.createElement("label");
      label.className = "store-chip active";
      label.dataset.storeId = store.id;
 
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.addEventListener("change", () => {
        if (input.checked) {
          state.activeStores.add(store.id);
          label.classList.add("active");
        } else {
          state.activeStores.delete(store.id);
          label.classList.remove("active");
        }
        render();
      });
 
      label.appendChild(input);
      label.appendChild(document.createTextNode(store.name));
      wrap.appendChild(label);
    });
  }
 
  /* ---------- Логика за филтриране / сортиране ---------- */
 
  function getStoreName(id) {
    const s = DATA.stores.find(s => s.id === id);
    return s ? s.name : id;
  }
 
  function getFilteredProducts() {
    const q = state.query.trim().toLowerCase();
 
    let list = DATA.products.filter(p => {
      const matchesQuery = !q || p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
      const matchesCategory = state.category === "all" || p.category === state.category;
      return matchesQuery && matchesCategory;
    });
 
    // Пресмятаме минимална цена сред активните магазини за всеки продукт
    list = list.map(p => {
      const visiblePrices = Object.entries(p.offers)
        .filter(([storeId]) => state.activeStores.has(storeId))
        .map(([storeId, offer]) => ({
          storeId,
          price: offer.price,
          image: offer.image || null,
          url: offer.url || null
        }));
 
      const minPrice = visiblePrices.length
        ? Math.min(...visiblePrices.map(v => v.price))
        : null;
 
      return { ...p, _visiblePrices: visiblePrices, _minPrice: minPrice };
    }).filter(p => p._visiblePrices.length > 0);
 
    if (state.sort === "price-asc") {
      list.sort((a, b) => (a._minPrice ?? Infinity) - (b._minPrice ?? Infinity));
    } else if (state.sort === "price-desc") {
      list.sort((a, b) => (b._minPrice ?? -Infinity) - (a._minPrice ?? -Infinity));
    } else {
      list.sort((a, b) => a.name.localeCompare(b.name, "bg"));
    }
 
    return list;
  }
 
  /* ---------- Рендиране ---------- */
 
  const FALLBACK_IMAGE = "https://placehold.co/300x300/E9E7E2/8B8F94?text=%D0%9D%D1%8F%D0%BC%D0%B0+%D1%81%D0%BD%D0%B8%D0%BC%D0%BA%D0%B0";
 
  function renderProductCard(p) {
    const sortedPrices = [...p._visiblePrices].sort((a, b) => a.price - b.price);
    const best = sortedPrices[0];
    const worst = sortedPrices[sortedPrices.length - 1];
    const savings = worst && best ? (worst.price - best.price) : 0;
 
    const rows = sortedPrices.map(v => {
      const isBest = v.storeId === best.storeId;
      const img = v.image || FALLBACK_IMAGE;
      const rowInner = `
          <img class="offer-thumb" src="${img}" alt="${p.name} — снимка от ${getStoreName(v.storeId)}" loading="lazy"
               onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}';">
          <span class="store-name">${getStoreName(v.storeId)}${isBest ? '<span class="best-badge">Най-ниска</span>' : ""}</span>
          <span class="price">${formatEUR(v.price)}</span>`;
 
      return v.url
        ? `<li class="price-row ${isBest ? "best" : ""}">
             <a class="price-row-link" href="${v.url}" target="_blank" rel="noopener noreferrer">${rowInner}</a>
           </li>`
        : `<li class="price-row ${isBest ? "best" : ""}">${rowInner}</li>`;
    }).join("");
 
    const savingsNote = savings > 0
      ? `<div class="savings-note">Спестявате до ${formatEUR(savings)} спрямо най-скъпата оферта.</div>`
      : "";
 
    const noteDiffProduct = sortedPrices.length > 1
      ? `<div class="offer-disclaimer">Снимките са тези, показани от всеки магазин — продуктите може леко да се различават.</div>`
      : "";
 
    const basketControlHtml = window.ArchiPariBasket
      ? window.ArchiPariBasket.addButtonHtml(p.id)
      : "";

    return `
      <article class="product-card">
        <h3>${p.name}</h3>
        <div class="product-meta">${p.category} · за ${p.unit}</div>
        <ul class="price-list">${rows}</ul>
        ${savingsNote}
        ${noteDiffProduct}
        <div class="product-card-actions">
          <a class="details-link" href="product.html?id=${encodeURIComponent(p.id)}">Пълно сравнение и снимки →</a>
          ${basketControlHtml}
        </div>
      </article>`;
  }
 
  function render() {
    const container = document.getElementById("productsContainer");
    const resultCount = document.getElementById("resultCount");
    if (!container || !DATA) return;
 
    const filtered = getFilteredProducts();
 
    if (resultCount) {
      resultCount.textContent = `${filtered.length} ${filtered.length === 1 ? "резултат" : "резултата"}`;
    }
 
    if (filtered.length === 0) {
      container.innerHTML = `<div class="empty-state">Няма намерени материали. Опитайте с друга дума за търсене или филтър.</div>`;
      return;
    }
 
    // Групираме по категория, за да покажем заглавия на секциите
    const byCategory = {};
    filtered.forEach(p => {
      if (!byCategory[p.category]) byCategory[p.category] = [];
      byCategory[p.category].push(p);
    });
 
    let html = "";
    Object.keys(byCategory).forEach(cat => {
      html += `<h2 class="category-heading">${cat}</h2>`;
      html += `<div class="product-grid">${byCategory[cat].map(renderProductCard).join("")}</div>`;
    });
 
    container.innerHTML = html;
  }
 
  /* ---------- Инициализация на началната страница ---------- */
 
  function initHomePage() {
    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");
    const categoryFilter = document.getElementById("categoryFilter");
    const sortFilter = document.getElementById("sortFilter");
    const lastUpdatedEl = document.getElementById("lastUpdated");
 
    if (!searchInput) return; // не сме на началната страница
 
    buildCategoryOptions();
    buildStoreToggles();
 
    if (lastUpdatedEl && DATA.lastUpdated) {
      lastUpdatedEl.textContent = formatDate(DATA.lastUpdated);
    }
 
    let debounceTimer;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.query = searchInput.value;
        render();
      }, 200);
    });
 
    searchBtn.addEventListener("click", () => {
      state.query = searchInput.value;
      render();
    });
 
    searchInput.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        state.query = searchInput.value;
        render();
      }
    });
 
    categoryFilter.addEventListener("change", () => {
      state.category = categoryFilter.value;
      render();
    });
 
    sortFilter.addEventListener("change", () => {
      state.sort = sortFilter.value;
      render();
    });
 
    render();
  }
 
  /* ---------- Контактна форма (demo, без реален бекенд) ---------- */
 
  function initContactForm() {
    const form = document.getElementById("contactForm");
    const status = document.getElementById("formStatus");
    if (!form) return;
 
    form.addEventListener("submit", e => {
      e.preventDefault();
      // ЗАБЕЛЕЖКА: това е само демонстрация на front-end.
      // За реално изпращане на съобщения свържете формата с бекенд
      // endpoint (напр. собствен сървър, Formspree, EmailJS и др.)
      status.textContent = "Благодарим ви! Съобщението беше записано (демо режим — свържете формата с реален сървър, за да получавате имейли).";
      status.className = "form-status show ok";
      form.reset();
    });
  }
 
  /* ---------- Мобилно меню ---------- */
 
  function initNavToggle() {
    const toggle = document.getElementById("navToggle");
    const nav = document.getElementById("mainNav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }
 
  /* ---------- Старт ---------- */
 
  document.addEventListener("DOMContentLoaded", async () => {
    initNavToggle();
    initContactForm();
    await loadData();
 
    // Излагаме данните и няколко помощни функции глобално, за да може
    // product.js (страницата за детайлно сравнение) да ги ползва повторно,
    // без да дублира логиката за зареждане/нормализиране на данните.
   window.ArchiPari = {
    getData: () => DATA,
    formatEUR,
    formatDate,
    getStoreName,
    FALLBACK_IMAGE
  };
    document.dispatchEvent(new CustomEvent("archipari:data-ready"));
 
    if (DATA) {
      initHomePage();
    } else {
      const container = document.getElementById("productsContainer");
      if (container) {
        container.innerHTML = `<div class="empty-state">Възникна проблем при зареждане на цените. Опреснете страницата.</div>`;
      }
    }
  });
})();