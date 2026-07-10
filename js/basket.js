/* =========================================================
   basket.js — "Количка за сравнение" / калкулатор за ремонт
   -----------------------------------------------------------
   Идея: при ремонт потребителят обикновено купува НЯКОЛКО вида
   продукти наведнъж (напр. плочки + лепило + фугомаса) и предпочита
   да поръча всичко от ЕДИН магазин, вместо да обикаля няколко сайта.
   Тук пазим избраните продукти + количества (в localStorage, за да
   оцелеят между презареждания и различни страници на сайта) и на
   basket.html смятаме за всеки магазин каква ще е ОБЩАТА цена, ако
   потребителят купи всичко оттам.

   Излага window.ArchiPariBasket = { getItems, getQty, addItem,
   removeItem, setQty, clear, count, subscribe, mountFloatingBar,
   renderAddButton }
   ========================================================= */

(function () {
  "use strict";

  const STORAGE_KEY = "archipari_basket_v1";
  const listeners = [];

  /* ---------- Съхранение (localStorage) ---------- */

  function readStorage() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function writeStorage(items) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      // localStorage може да липсва (частен режим и т.н.) — количката
      // просто няма да оцелее между презареждания, но сайтът не гърми.
    }
  }

  let items = readStorage(); // { productId: qty }

  function notify() {
    writeStorage(items);
    listeners.forEach(fn => {
      try { fn(items); } catch (e) { /* игнорираме грешка в слушател */ }
    });
    renderFloatingBar();
  }

  /* ---------- Публично API ---------- */

  function getItems() {
    return { ...items };
  }

  function getQty(productId) {
    return items[productId] || 0;
  }

  function setQty(productId, qty) {
    const n = Math.max(0, Math.floor(Number(qty) || 0));
    if (n <= 0) {
      delete items[productId];
    } else {
      items[productId] = n;
    }
    notify();
  }

  function addItem(productId, qty) {
    const add = Math.max(1, Math.floor(Number(qty) || 1));
    items[productId] = (items[productId] || 0) + add;
    notify();
  }

  function removeItem(productId) {
    delete items[productId];
    notify();
  }

  function clear() {
    items = {};
    notify();
  }

  function count() {
    return Object.values(items).reduce((sum, q) => sum + q, 0);
  }

  function subscribe(fn) {
    listeners.push(fn);
  }

  /* ---------- Плаващ бар "Количка" (на всички страници) ---------- */

  function ensureFloatingBarEl() {
    let bar = document.getElementById("archipariFloatingBasket");
    if (bar) return bar;

    bar = document.createElement("a");
    bar.id = "archipariFloatingBasket";
    bar.className = "floating-basket-bar";
    bar.href = "basket.html";
    document.body.appendChild(bar);
    return bar;
  }

  function renderFloatingBar() {
    const n = count();
    const bar = ensureFloatingBarEl();

    // На самата basket.html не показваме плаващия бар — потребителят вече е там.
    const onBasketPage = !!document.getElementById("basketPage");

    if (n === 0 || onBasketPage) {
      bar.classList.remove("visible");
      return;
    }

    bar.innerHTML = `
      <span class="floating-basket-icon">🧺</span>
      <span>В количката: <strong>${n}</strong> ${n === 1 ? "продукт" : "продукта"}</span>
      <span class="floating-basket-cta">Сравни обща цена →</span>`;
    bar.classList.add("visible");
  }

  /* ---------- Бутон "Добави в количката" за продуктова карта ---------- */

  /* Връща HTML низ за контролата — рендира се вътре в продуктова карта
     или на страницата за детайлно сравнение. Използва data-атрибути и
     делегиран event listener (вж. attachAddButtonHandlers), за да работи
     и след innerHTML презаписи (напр. при филтриране). */
  function addButtonHtml(productId) {
    const qty = getQty(productId);
    if (qty > 0) {
      return `
        <div class="add-to-basket-control in-basket" data-product-id="${productId}">
          <button type="button" class="qty-btn" data-action="dec" aria-label="Намали количеството">−</button>
          <span class="qty-value">${qty}</span>
          <button type="button" class="qty-btn" data-action="inc" aria-label="Увеличи количеството">+</button>
          <span class="in-basket-check">✓ В количката</span>
        </div>`;
    }
    return `
      <div class="add-to-basket-control" data-product-id="${productId}">
        <button type="button" class="add-to-basket-btn" data-action="add">+ Добави в количката</button>
      </div>`;
  }

  function refreshAddButtons(root) {
    (root || document).querySelectorAll(".add-to-basket-control[data-product-id]").forEach(el => {
      const pid = el.dataset.productId;
      el.outerHTML = addButtonHtml(pid);
    });
  }

  function attachAddButtonHandlers(root) {
    const scope = root || document;
    scope.addEventListener("click", e => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const control = btn.closest(".add-to-basket-control[data-product-id]");
      if (!control) return;

      const pid = control.dataset.productId;
      const action = btn.dataset.action;

      e.preventDefault();
      e.stopPropagation();

      if (action === "add") {
        addItem(pid, 1);
      } else if (action === "inc") {
        setQty(pid, getQty(pid) + 1);
      } else if (action === "dec") {
        setQty(pid, getQty(pid) - 1);
      }

      refreshAddButtons(scope);
    });
  }

  /* ---------- Инициализация ---------- */

  document.addEventListener("DOMContentLoaded", () => {
    renderFloatingBar();
    attachAddButtonHandlers(document);
  });

  window.ArchiPariBasket = {
    getItems,
    getQty,
    addItem,
    removeItem,
    setQty,
    clear,
    count,
    subscribe,
    addButtonHtml,
    refreshAddButtons
  };
})();
