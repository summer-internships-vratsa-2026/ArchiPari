/* =========================================================
   basket-page.js — логика специфично за basket.html
   Смята за всеки магазин: обща сума за избраните продукти,
   колко от тях реално се продават там, и кой магазин излиза
   най-изгоден, АКО потребителят купи всичко от едно място.
   ========================================================= */

(function () {
  "use strict";

  function renderEmptyState(container) {
    container.innerHTML = `
      <div class="empty-state basket-empty">
        Количката е празна.<br>
        Разгледай <a href="index.html#products">материалите</a> и добави продукти,
        за да сравниш къде общата сума излиза най-евтино.
      </div>`;
  }

  function renderItemsList(container, products, DATA) {
    const rows = products.map(({ product, qty }) => {
      const prices = Object.values(product.offers || {}).map(o => o.price);
      const fromPrice = prices.length ? Math.min(...prices) : null;
      const fromText = fromPrice !== null
        ? `от ${window.ArchiPari.formatEUR(fromPrice)} / ${product.unit}`
        : "няма налична цена";

      return `
        <li class="basket-item-row" data-product-id="${product.id}">
          <div class="basket-item-info">
            <a href="product.html?id=${encodeURIComponent(product.id)}" class="basket-item-name">${product.name}</a>
            <span class="basket-item-meta">${product.category} · ${fromText}</span>
          </div>
          <div class="basket-item-qty">
            <button type="button" class="qty-btn" data-action="dec" aria-label="Намали количеството">−</button>
            <input type="number" min="1" step="1" class="qty-input" value="${qty}" aria-label="Количество">
            <button type="button" class="qty-btn" data-action="inc" aria-label="Увеличи количеството">+</button>
          </div>
          <button type="button" class="basket-remove-btn" data-action="remove" aria-label="Премахни от количката">✕</button>
        </li>`;
    }).join("");

    container.innerHTML = `<ul class="basket-items-list">${rows}</ul>`;

    // Делегирани listener-и за +/-, ръчно въведено количество, и премахване.
    container.querySelectorAll(".basket-item-row").forEach(row => {
      const pid = row.dataset.productId;
      const input = row.querySelector(".qty-input");

      row.querySelector('[data-action="inc"]').addEventListener("click", () => {
        window.ArchiPariBasket.setQty(pid, window.ArchiPariBasket.getQty(pid) + 1);
      });
      row.querySelector('[data-action="dec"]').addEventListener("click", () => {
        window.ArchiPariBasket.setQty(pid, window.ArchiPariBasket.getQty(pid) - 1);
      });
      row.querySelector('[data-action="remove"]').addEventListener("click", () => {
        window.ArchiPariBasket.removeItem(pid);
      });
      input.addEventListener("change", () => {
        window.ArchiPariBasket.setQty(pid, input.value);
      });
    });
  }

  function renderStoreTotals(container, products, DATA) {
    const totalItemsNeeded = products.length;

    // За всеки магазин смятаме: сума на наличните продукти * количество,
    // и колко от избраните продукти изобщо се продават там.
    const storeResults = DATA.stores.map(store => {
      let total = 0;
      let availableCount = 0;
      const missing = [];

      products.forEach(({ product, qty }) => {
        const offer = product.offers && product.offers[store.id];
        if (offer && typeof offer.price === "number") {
          total += offer.price * qty;
          availableCount += 1;
        } else {
          missing.push(product.name);
        }
      });

      return {
        store,
        total,
        availableCount,
        missing,
        isComplete: availableCount === totalItemsNeeded
      };
    }).filter(r => r.availableCount > 0); // скриваме магазини без нито един от продуктите

    if (storeResults.length === 0) {
      container.innerHTML = `<div class="empty-state">Нито един магазин не предлага избраните продукти.</div>`;
      return;
    }

    // Подреждаме: първо магазините с ВСИЧКИ продукти (сортирани по цена),
    // после тези с частично покритие (също по цена) — купуването на
    // всичко от едно място обикновено е приоритетът на потребителя.
    storeResults.sort((a, b) => {
      if (a.isComplete !== b.isComplete) return a.isComplete ? -1 : 1;
      return a.total - b.total;
    });

    const bestComplete = storeResults.find(r => r.isComplete);

    const cardsHtml = storeResults.map(r => {
      const isBest = bestComplete && r.store.id === bestComplete.store.id;
      const coverageNote = r.isComplete
        ? `<span class="store-total-coverage complete">Всички ${totalItemsNeeded} продукта налични</span>`
        : `<span class="store-total-coverage partial">${r.availableCount} от ${totalItemsNeeded} продукта налични</span>`;

      const missingNote = r.missing.length
        ? `<div class="store-total-missing">Липсва: ${r.missing.join(", ")}</div>`
        : "";

      return `
        <article class="store-total-card ${isBest ? "best" : ""} ${r.isComplete ? "" : "incomplete"}">
          ${isBest ? '<span class="best-badge">Най-изгодно общо</span>' : ""}
          <h3>${r.store.name}</h3>
          ${coverageNote}
          <div class="store-total-price">${window.ArchiPari.formatEUR(r.total)}</div>
          ${missingNote}
          <a class="btn-primary" href="${r.store.url}" target="_blank" rel="noopener noreferrer">Отвори ${r.store.name} →</a>
        </article>`;
    }).join("");

    const introNote = bestComplete
      ? `<p class="basket-summary-note">Ако купиш всички <strong>${totalItemsNeeded}</strong> продукта от <strong>${bestComplete.store.name}</strong>, общата сума е <strong>${window.ArchiPari.formatEUR(bestComplete.total)}</strong> — най-изгодно е да поръчаш всичко оттам наведнъж.</p>`
      : `<p class="basket-summary-note">Нито един магазин не предлага всички избрани продукти едновременно — виж по-долу кой магазин покрива най-много от тях.</p>`;

    container.innerHTML = introNote + `<div class="store-totals-grid">${cardsHtml}</div>`;
  }

  function render() {
    const page = document.getElementById("basketPage");
    if (!page) return;

    const itemsListEl = document.getElementById("basketItemsList");
    const totalsEl = document.getElementById("basketStoreTotals");
    const DATA = window.ArchiPari.getData();
    const basketItems = window.ArchiPariBasket.getItems();
    const productIds = Object.keys(basketItems);

    if (productIds.length === 0) {
      renderEmptyState(page.querySelector(".basket-main"));
      itemsListEl.innerHTML = "";
      totalsEl.innerHTML = "";
      document.getElementById("basketClearBtn").style.display = "none";
      return;
    }

    document.getElementById("basketClearBtn").style.display = "";

    const products = productIds
      .map(id => ({ product: DATA.products.find(p => p.id === id), qty: basketItems[id] }))
      .filter(x => x.product); // ако продукт е бил премахнат от каталога междувременно

    renderItemsList(itemsListEl, products, DATA);
    renderStoreTotals(totalsEl, products, DATA);
  }

  function init() {
    const page = document.getElementById("basketPage");
    if (!page) return; // не сме на basket.html

    render();
    window.ArchiPariBasket.subscribe(render);

    const clearBtn = document.getElementById("basketClearBtn");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (window.confirm("Да изчистя ли цялата количка?")) {
          window.ArchiPariBasket.clear();
        }
      });
    }
  }

  document.addEventListener("archipari:data-ready", init);
})();
