/* =========================================================
   product.js — детайлно сравнение на един продукт
   Разчита на данните, вече заредени и изложени от script.js
   (window.ArchiPari), затова изчаква събитието
   "archipari:data-ready", преди да рендира каквото и да е.
   ========================================================= */
 
(function () {
  "use strict";
 
  function getParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }
 
  function renderMessage(container, text) {
    container.innerHTML = `<div class="empty-state">${text}</div>`;
  }
 
  function renderOfferCard(offer, storeId, isBest, product) {
    const img = offer.image || window.ArchiPari.FALLBACK_IMAGE;
    const label = offer.label || product.name;
    const storeName = window.ArchiPari.getStoreName(storeId);
 
    const priceBlock = `
      <div class="offer-detail-price">
        ${isBest ? '<span class="best-badge">Най-ниска цена</span>' : ""}
        <span class="price">${window.ArchiPari.formatEUR(offer.price)}</span>
      </div>`;
 
    const buyButton = offer.url
      ? `<a class="btn-primary offer-detail-link" href="${offer.url}" target="_blank" rel="noopener noreferrer">Виж в ${storeName}</a>`
      : "";
 
    return `
      <article class="offer-detail-card ${isBest ? "best" : ""}">
        <img class="offer-detail-thumb" src="${img}" alt="${label}" loading="lazy"
             onerror="this.onerror=null;this.src='${window.ArchiPari.FALLBACK_IMAGE}';">
        <div class="offer-detail-body">
          <div class="offer-detail-store">${storeName}</div>
          <div class="offer-detail-label">${label}</div>
          ${priceBlock}
          ${buyButton}
        </div>
      </article>`;
  }
 
  function render(product) {
    const container = document.getElementById("productDetailPage");
 
    const offersEntries = Object.entries(product.offers || {});
    if (offersEntries.length === 0) {
      renderMessage(container, "За този продукт все още няма нито една оферта.");
      return;
    }
 
    const sorted = offersEntries
      .map(([storeId, offer]) => ({ storeId, offer }))
      .sort((a, b) => a.offer.price - b.offer.price);
 
    const bestPrice = sorted[0].offer.price;
    const worstPrice = sorted[sorted.length - 1].offer.price;
    const savings = worstPrice - bestPrice;
 
    const matchNoteHtml = product.matchNote
      ? `<div class="match-note">⚠ ${product.matchNote}</div>`
      : "";
 
    const savingsHtml = savings > 0
      ? `<div class="savings-note">Спестявате до ${window.ArchiPari.formatEUR(savings)}, ако изберете най-евтината оферта.</div>`
      : "";
 
    const basketControlHtml = window.ArchiPariBasket
      ? window.ArchiPariBasket.addButtonHtml(product.id)
      : "";

    const cardsHtml = sorted.map(({ storeId, offer }) =>
      renderOfferCard(offer, storeId, offer.price === bestPrice, product)
    ).join("");
 
    container.innerHTML = `
      <div class="product-detail-header">
        <a class="back-link" href="index.html">← Обратно към всички материали</a>
        <h1>${product.name}</h1>
        <div class="product-meta">${product.category} · за ${product.unit}</div>
        ${matchNoteHtml}
        ${savingsHtml}
        <div class="product-detail-basket">${basketControlHtml}</div>
      </div>
      <div class="offer-detail-grid">${cardsHtml}</div>`;
  }
 
  function init() {
    const container = document.getElementById("productDetailPage");
    const DATA = window.ArchiPari.getData();
 
    if (!DATA) {
      renderMessage(container, "Възникна проблем при зареждане на данните. Опреснете страницата.");
      return;
    }
 
    const id = getParam("id");
    if (!id) {
      renderMessage(container, "Не е посочен продукт за сравнение. <a href=\"index.html\">Обратно към всички материали</a>");
      return;
    }
 
    const product = DATA.products.find(p => p.id === id);
    if (!product) {
      renderMessage(container, "Продуктът не беше намерен. <a href=\"index.html\">Обратно към всички материали</a>");
      return;
    }
 
    render(product);
  }
 
  // script.js хвърля "archipari:data-ready" веднага след като зареди
  // и изложи данните на window.ArchiPari — изчакваме точно това събитие,
  // вместо да презареждаме данните тук отново.
  document.addEventListener("archipari:data-ready", init);
})();