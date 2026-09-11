(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { index: null, product: null, query: "", character: "all", previousFocus: null };

  const escapeHTML = (value) => String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
  const normalized = (value) => String(value).normalize("NFKC").toLocaleLowerCase("ja");
  const megabytes = (bytes) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;

  function animationSource(item, explicit = false) {
    return reducedMotion && !explicit ? item.start_image : item.animation;
  }

  function apngImage(item, className = "", alt = "") {
    return `<img class="${className}" src="${escapeHTML(animationSource(item))}" data-apng data-animation="${escapeHTML(item.animation)}" data-static="${escapeHTML(item.start_image)}" alt="${escapeHTML(alt)}" width="320" height="270">`;
  }

  async function loadCatalog() {
    try {
      const indexResponse = await fetch("data/products/index.json");
      if (!indexResponse.ok) throw new Error(`商品一覧を取得できませんでした (${indexResponse.status})`);
      state.index = await indexResponse.json();
      const params = new URLSearchParams(location.search);
      const wanted = params.get("pack");
      const entry = state.index.products.find((item) => item.slug === wanted) || state.index.products[0];
      if (!entry) throw new Error("商品が登録されていません");
      await loadProduct(entry);
      renderPackSwitcher(entry.slug);
    } catch (error) {
      $("#productTitle").textContent = "読み込みに失敗しました";
      $("#productDescription").textContent = error.message;
      $("#stickerGrid").setAttribute("aria-busy", "false");
      console.error(error);
    }
  }

  async function loadProduct(entry) {
    const response = await fetch(entry.data);
    if (!response.ok) throw new Error(`商品データを取得できませんでした (${response.status})`);
    state.product = await response.json();
    state.character = "all";
    state.query = "";
    $("#searchInput").value = "";
    renderProduct();
  }

  function renderPackSwitcher(activeSlug) {
    const wrap = $("#packSwitcherWrap");
    const select = $("#packSwitcher");
    select.innerHTML = state.index.products.map((entry) => `<option value="${escapeHTML(entry.slug)}"${entry.slug === activeSlug ? " selected" : ""}>${escapeHTML(entry.title)}</option>`).join("");
    wrap.hidden = state.index.products.length < 2;
    select.onchange = async () => {
      const entry = state.index.products.find((item) => item.slug === select.value);
      if (!entry) return;
      const url = new URL(location.href);
      url.searchParams.set("pack", entry.slug);
      history.replaceState({}, "", url);
      await loadProduct(entry);
    };
  }

  function renderProduct() {
    const product = state.product;
    document.title = `${product.title}｜LINEスタンプ レビュー室`;
    $("#productTitle").textContent = product.title;
    $("#productDescription").textContent = product.description;
    $("#statusNote").textContent = product.status_note;
    const allQaPassed = product.qa.every((check) => check.status === "PASS");
    $("#heroFacts").innerHTML = `
      <span><strong>${escapeHTML(product.item_count)}</strong>個すべて</span>
      <span><strong>QA</strong>${allQaPassed ? "全項目 PASS" : "要確認"}</span>
      <span><strong>LINE</strong>未申請</span>`;
    renderHero();
    renderDownloads();
    renderFilters();
    renderCards();
    renderPreview();
    renderReviewSheets();
    renderQA();
  }

  function renderHero() {
    const product = state.product;
    const featured = product.featured_item_ids.map((id) => product.items.find((item) => item.id === id)).filter(Boolean);
    const mainFallback = featured[featured.length - 1];
    const mainSrc = reducedMotion && mainFallback ? mainFallback.start_image : product.assets.main;
    const floats = featured.map((item) => apngImage(item, "hero-float", `${item.text} のアニメーション`)).join("");
    $("#heroStage").innerHTML = `<img class="hero-main" src="${escapeHTML(mainSrc)}" data-apng data-animation="${escapeHTML(product.assets.main)}" data-static="${escapeHTML(mainFallback?.start_image || product.assets.tab)}" alt="${escapeHTML(product.title)} メイン画像" width="240" height="240">${floats}`;
  }

  function renderDownloads() {
    const { line_upload: line, complete_delivery: complete } = state.product.downloads;
    $("#downloadRow").innerHTML = `
      <a class="download-button" href="${escapeHTML(line.url)}" download>${escapeHTML(line.label)} <small>${escapeHTML(megabytes(line.bytes))}</small></a>
      <a class="secondary-download" href="${escapeHTML(complete.url)}">${escapeHTML(complete.label)} <small>${escapeHTML(megabytes(complete.bytes))}</small></a>`;
    $("#downloadFootnote").textContent = complete.availability_note;
  }

  function renderFilters() {
    const labels = new Map([["all", "すべて"]]);
    state.product.items.forEach((item) => {
      if (!labels.has(item.character)) labels.set(item.character, item.character_label);
    });
    $("#filterChips").innerHTML = [...labels].map(([value, label]) => `<button type="button" data-character="${escapeHTML(value)}" aria-pressed="${value === state.character}">${escapeHTML(label)}</button>`).join("");
  }

  function visibleItems() {
    const query = normalized(state.query.trim());
    return state.product.items.filter((item) => {
      const characterMatches = state.character === "all" || item.character === state.character;
      const haystack = normalized([item.text, item.intended_use, item.character, item.character_label, item.start, item.end].join(" "));
      return characterMatches && (!query || haystack.includes(query));
    });
  }

  function renderCards() {
    const items = visibleItems();
    const grid = $("#stickerGrid");
    grid.innerHTML = items.map((item) => `
      <article class="sticker-card" data-item-id="${escapeHTML(item.id)}">
        <button class="card-open" type="button" aria-label="${escapeHTML(item.text)} の詳細を見る" data-open-id="${escapeHTML(item.id)}">
          <div class="card-visual sticker-stage">
            <span class="card-number">${escapeHTML(item.id)}</span>
            ${apngImage(item, "", `${item.text} — ${item.character_label}`)}
            <span class="card-zoom">タップで詳しく</span>
          </div>
          <div class="card-copy">
            <span class="character-tag">${escapeHTML(item.character_label)}</span>
            <h3>${escapeHTML(item.text)}</h3>
            <p class="card-use">${escapeHTML(item.intended_use)}</p>
          </div>
        </button>
      </article>`).join("");
    grid.setAttribute("aria-busy", "false");
    $("#resultCount").textContent = `${items.length} / ${state.product.items.length}点`;
    $("#emptyState").hidden = items.length !== 0;
  }

  function renderPreview() {
    const video = $("#previewVideo");
    video.src = state.product.assets.preview_video;
    video.poster = state.product.assets.contact_sheet;
  }

  function renderReviewSheets() {
    const product = state.product;
    const sheets = [
      [product.assets.contact_sheet, "全16点一覧", "文字と全体バランス"],
      [product.assets.start_end_sheet, "START → END", "動きの前後差"],
      [product.assets.character_sheet, "キャラクター正本", "こむぎ・すみれ・みるく"]
    ];
    $("#reviewGrid").innerHTML = sheets.map(([src, title, note]) => `<a class="review-card" href="${escapeHTML(src)}"><img src="${escapeHTML(src)}" alt="${escapeHTML(title)}" loading="lazy"><span class="review-card-copy"><h3>${escapeHTML(title)}</h3><span>${escapeHTML(note)} ↗</span></span></a>`).join("");
  }

  function renderQA() {
    $("#qaGrid").innerHTML = state.product.qa.map((check) => `<a class="qa-card" href="${escapeHTML(check.source)}"><span class="qa-status">${escapeHTML(check.status)}</span><span><h3>${escapeHTML(check.label)}</h3><p>${escapeHTML(check.detail)}</p></span><span class="qa-arrow" aria-hidden="true">↗</span></a>`).join("");
  }

  function replayImages(root = document) {
    const token = Date.now();
    root.querySelectorAll("img[data-apng]").forEach((image, index) => {
      const source = image.dataset.animation;
      image.src = "data:image/gif;base64,R0lGODlhAQABAAAAACw=";
      window.setTimeout(() => { image.src = `${source}?replay=${token}-${index}`; }, 18);
    });
  }

  function openDialog(itemId, trigger) {
    const item = state.product.items.find((candidate) => candidate.id === itemId);
    if (!item) return;
    state.previousFocus = trigger;
    $("#dialogNumber").textContent = `STICKER ${item.id}`;
    $("#dialogTitle").textContent = item.text;
    $("#dialogCharacter").textContent = item.character_label;
    $("#dialogUse").textContent = item.intended_use;
    const animation = $("#dialogAnimation");
    animation.src = animationSource(item);
    animation.dataset.animation = item.animation;
    animation.dataset.static = item.start_image;
    animation.dataset.apng = "";
    animation.alt = `${item.text} のアニメーション`;
    $("#dialogStart").src = item.start_image;
    $("#dialogStart").alt = `${item.text} の開始フレーム`;
    $("#dialogEnd").src = item.end_image;
    $("#dialogEnd").alt = `${item.text} の終了フレーム`;
    $("#dialogStartText").textContent = item.start;
    $("#dialogEndText").textContent = item.end;
    $("#dialogMotionMeta").textContent = `${item.frames}フレーム × ${item.frame_ms}ms / ${item.loops}ループ`;
    const download = $("#dialogDownload");
    download.href = item.animation;
    download.download = `${item.id}.png`;
    const dialog = $("#stickerDialog");
    dialog.showModal();
    document.body.style.overflow = "hidden";
  }

  function closeDialog() {
    const dialog = $("#stickerDialog");
    if (dialog.open) dialog.close();
  }

  document.addEventListener("click", (event) => {
    const openButton = event.target.closest("[data-open-id]");
    if (openButton) openDialog(openButton.dataset.openId, openButton);

    const filter = event.target.closest("[data-character]");
    if (filter) {
      state.character = filter.dataset.character;
      $("#filterChips").querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button === filter)));
      renderCards();
    }

    const background = event.target.closest("[data-bg]");
    if (background) {
      document.body.dataset.stageBg = background.dataset.bg;
      $("#backgroundToggle").querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button === background)));
    }
  });

  $("#searchInput").addEventListener("input", (event) => { state.query = event.target.value; renderCards(); });
  $("#replayAll").addEventListener("click", () => replayImages());
  $("#dialogReplay").addEventListener("click", () => replayImages($("#stickerDialog")));
  $("#dialogClose").addEventListener("click", closeDialog);
  $("#stickerDialog").addEventListener("close", () => {
    document.body.style.overflow = "";
    state.previousFocus?.focus();
  });
  $("#stickerDialog").addEventListener("click", (event) => {
    const dialog = event.currentTarget;
    const rect = $(".dialog-card", dialog).getBoundingClientRect();
    const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
    if (outside) closeDialog();
  });

  loadCatalog();
})();
