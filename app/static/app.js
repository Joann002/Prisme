const paths = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.7 8.3-2 5.4-5.4 2 2-5.4z"/>',
  shuffle: '<path d="M3 7h3c4 0 7 10 11 10h4m-3-3 3 3-3 3M3 17h3c4 0 7-10 11-10h4m-3-3 3 3-3 3"/>',
  columns: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M12 5v14"/>',
  shield: '<path d="M12 22s7-3.5 7-9.5V6l-7-3-7 3v6.5c0 6 7 9.5 7 9.5Z"/><path d="m9 12 2 2 4-4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  spark: '<path d="M12 3c0 6.2 2.8 9 9 9-6.2 0-9 2.8-9 9 0-6.2-2.8-9-9-9 6.2 0 9-2.8 9-9Z"/>',
  "arrow-down": '<path d="M12 4v15m-5-5 5 5 5-5"/>',
  "arrow-right": '<path d="M4 12h15m-5-5 5 5-5 5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  bookmark: '<path d="M6 5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16l-6-4-6 4Z"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
  film: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16m10-16v16M3 9h4m-4 6h4m10-6h4m-4 6h4"/>',
  book: '<path d="M12 6C8 3 4 4 3 5v14c3-2 6-2 9 0 3-2 6-2 9 0V5c-1-1-5-2-9 1Zm0 0v13"/>',
  game: '<path d="M8 7h8c3 0 4.5 2.2 5.4 6l.5 2.4c.6 3-2.4 4-4 2.5L15 15H9l-3 2.9c-1.6 1.5-4.6.5-4-2.5l.5-2.4c.9-3.8 2.5-6 5.5-6Zm.5 2v4m-2-2h4m5.5-1h.01m2.49 2h.01"/>',
  music: '<path d="M9 18V5l11-2v13M9 9l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="17" cy="16" rx="3" ry="2.5"/>',
  food: '<path d="M4 3v6a3 3 0 0 0 6 0V3M7 3v18m12 0V3c-3 2-4 5-4 9h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  up: '<path d="M7 10v11H3V10h4Zm0 1 5-8c2 0 3 2 2 6h5a2 2 0 0 1 2 2l-2 8a2 2 0 0 1-2 2H7"/>',
  down: '<path d="M7 14V3H3v11h4Zm0-1 5 8c2 0 3-2 2-6h5a2 2 0 0 0 2-2l-2-8a2 2 0 0 0-2-2H7"/>',
};

const domainOrder = ["movies", "books", "games", "music", "recipes"];
const views = {
  discover: ["Découvrir", "Explore le catalogue", "Choisis 3 à 5 favoris pour composer ta sélection."],
  cross: ["Entre les domaines", "Croise les domaines", "Pars de tes favoris dans un domaine et découvre des idées dans un autre."],
  compare: ["Comparer les modèles", "Compare les modèles", "Applique deux modèles à la même sélection et compare leurs résultats."],
};
const privacy = [
  "La démo ne demande ni compte, ni nom, ni adresse e-mail. Les profils du catalogue de démonstration sont synthétiques. Tes favoris restent dans cette session. Les résultats peuvent être mis en cache pendant cinq minutes.",
  "Chaque vote est compté par jour, domaine, élément et sens du vote, sans identifiant de profil. Les métriques servent à suivre les performances et la diversité des recommandations.",
  "Si un catalogue importé fournit des images externes, leurs hébergeurs peuvent recevoir les demandes d’images.",
];
const pageSize = 6;

function icon(name) {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (paths[name] || paths.grid) + '</svg>';
}

function escape(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function imageIndex(item) {
  if (item.domaine === "recipes") return 4;
  if (item.domaine === "music") return 5;
  if (/fantasy|nature|mythologie/i.test(item.tags.join(" "))) return 2;
  if (/cyberpunk|andro|simulation/i.test(item.tags.join(" "))) return 3;
  if (/désert|space opera|dune/i.test(item.tags.join(" ") + item.titre)) return 0;
  if (/rêves|illusion|simulation/i.test(item.tags.join(" "))) return 7;
  if (/paris|romance/i.test(item.tags.join(" "))) return 8;
  if (/espace|astronautes|temps/i.test(item.tags.join(" "))) {
    return /temps/i.test(item.tags.join(" ")) ? 6 : 9;
  }
  if (/mystère|enquête/i.test(item.tags.join(" "))) return 10;
  if (item.domaine === "books") return 11;
  return 1;
}

function imageSource(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

export function mount(root, assets, request, metadata) {
  const find = (name) => root.querySelector('[data-role="' + name + '"]');
  const search = root.querySelector('input[type="search"]');
  const submit = root.querySelector('[data-action="recommend"]');
  const domainList = [...metadata].sort((a, b) => {
    const order = (x) => domainOrder.includes(x) ? domainOrder.indexOf(x) : domainOrder.length;
    return order(a.slug) - order(b.slug);
  });
  const domainMap = new Map(domainList.map((row) => [row.slug, row]));
  const state = {
    view: "discover",
    domain: domainList[0].slug,
    target: domainList[1]?.slug || "",
    modelA: "",
    modelB: "",
    picked: new Map(),
    items: [],
    total: 0,
    votes: new Map(),
    waitingVotes: new Set(),
    catalogJob: 0,
    recJob: 0,
    result: null,
    busy: false,
  };

  root.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = icon(node.dataset.icon);
  });
  root.style.setProperty("--hero-art", 'url("' + assets.hero + '")');
  find("domain-count").textContent = domainList.length + (domainList.length === 1 ? " domaine" : " domaines");
  find("source").textContent = domainList.every((row) => row.demo)
    ? "Données de démonstration" : "Catalogues et données importés";
  if (domainList.length < 2) root.querySelectorAll('[data-view="cross"]').forEach((node) => { node.hidden = true; });

  const domain = () => domainMap.get(state.domain);

  function allowedModels() {
    const models = domain().models;
    if (!models.some((model) => model.id === state.modelA)) state.modelA = domain().default_model;
    if (!models.some((model) => model.id === state.modelB) || state.modelA === state.modelB) {
      state.modelB = models.find((model) => model.id === "tfidf" && model.id !== state.modelA)?.id
        || models.find((model) => model.id !== state.modelA)?.id || state.modelA;
    }
  }

  function seeds() {
    if (!state.picked.has(state.domain)) state.picked.set(state.domain, new Map());
    return state.picked.get(state.domain);
  }

  function poster(item, label, clickable = true) {
    const art = assets.tiles[imageIndex(item)];
    const url = imageSource(item.image);
    const image = url ? '<img alt="" loading="lazy" referrerpolicy="no-referrer" src="' + escape(url) + '">' : "";
    const style = ' style="background-image:url(' + escape(art) + ')"';
    return clickable
      ? '<button type="button" class="poster" aria-label="' + escape(label) + '" data-action="detail" data-id="' +
          escape(item.item_id) + '"' + style + '>' + image + '</button>'
      : '<div class="poster"' + style + '>' + image + '</div>';
  }

  function tags(item) {
    return '<div class="tags">' + item.tags.slice(0, 4).map((tag) =>
      '<span class="tag">' + escape(tag) + '</span>').join("") + '</div>';
  }

  function paintDomains() {
    find("domains").innerHTML = domainList.map((row) =>
      '<button class="domain" type="button" data-domain="' + escape(row.slug) + '" aria-pressed="' +
      (row.slug === state.domain) + '">' + icon(row.icon) + escape(row.label) + '</button>'
    ).join("");
  }

  function paintCatalog() {
    const picked = seeds();
    const grid = find("catalog");
    grid.innerHTML = state.items.length ? state.items.map((item) => {
      const selected = picked.has(item.item_id);
      const subtitle = [item.year, item.tags[0]].filter(Boolean).join(" · ");
      return '<article class="tile' + (selected ? ' selected' : '') + '">' +
        poster(item, "À propos de " + item.titre) +
        '<button type="button" class="icon-button tile-add" data-action="toggle" data-id="' +
        escape(item.item_id) + '" aria-pressed="' + selected + '" aria-label="' +
        escape((selected ? "Retirer " : "Ajouter ") + item.titre) + '">' +
        icon(selected ? "check" : "plus") + '</button><div class="tile-info">' +
        '<button type="button" class="tile-name" data-action="detail" data-id="' +
        escape(item.item_id) + '">' + escape(item.titre) + '</button><p>' +
        escape(subtitle) + '</p></div></article>';
    }).join("") : '<p class="empty">Aucun élément trouvé.</p>';
    find("catalog-count").textContent = state.total + (state.total === 1 ? " élément" : " éléments");
    find("load-area").innerHTML = state.items.length < state.total
      ? '<button class="button" type="button" data-action="more">Afficher plus</button>' : "";
  }

  function paintSelection() {
    const picked = seeds();
    find("selection-count").textContent = picked.size + " / 5";
    find("progress").innerHTML = Array.from({length: 5}, (_, index) =>
      '<span class="' + (index < picked.size ? "filled" : "") + '"></span>').join("");
    find("seeds").innerHTML = picked.size ? [...picked.values()].map((item) =>
      '<div class="seed"><span>' + escape(item.titre) +
      '</span><button type="button" class="icon-button" data-action="remove" data-id="' +
      escape(item.item_id) + '" aria-label="' + escape("Retirer " + item.titre) + '">' + icon("x") +
      '</button></div>'
    ).join("") : '<div class="selection-empty">' + icon("plus") + '<span>Ajoute un premier favori.</span></div>';
    submit.disabled = picked.size < 3 || state.busy ||
      (state.view === "compare" && state.modelA === state.modelB);
    const label = { discover: "Voir mes recommandations", cross: "Explorer le domaine cible", compare: "Comparer les modèles" };
    find("submit-label").textContent = state.busy ? "Calcul en cours…" : label[state.view];
  }

  function select(label, name, rows, selected) {
    return '<label>' + label + '<select data-setting="' + name + '">' + rows.map((item) =>
      '<option value="' + escape(item.id) + '"' + (item.id === selected ? ' selected' : '') + '>' +
      escape(item.label) + '</option>').join("") + '</select></label>';
  }

  function paintOptions() {
    if (state.view === "cross") {
      const targets = domainList.filter((row) => row.slug !== state.domain);
      if (!targets.some((row) => row.slug === state.target)) state.target = targets[0]?.slug || "";
      find("options").innerHTML = select("Domaine cible", "target", targets.map((row) => ({
        id: row.slug, label: row.label,
      })), state.target);
    } else if (state.view === "compare") {
      allowedModels();
      find("options").innerHTML = select("Premier modèle", "modelA", domain().models, state.modelA) +
        select("Deuxième modèle", "modelB", domain().models, state.modelB);
    } else {
      find("options").innerHTML = "";
    }
  }

  function resetResults() {
    state.recJob += 1;
    state.busy = false;
    state.result = null;
    find("results").hidden = true;
    find("notice").textContent = "";
  }

  async function loadCatalog(append = false) {
    const job = ++state.catalogJob;
    const grid = find("catalog");
    grid.setAttribute("aria-busy", "true");
    if (!append) {
      grid.innerHTML = '<p class="loading">Chargement des éléments…</p>';
      find("catalog-count").textContent = "";
      find("load-area").innerHTML = "";
    } else {
      const more = find("load-area").querySelector("button");
      if (more) more.disabled = true;
    }
    try {
      const result = await request("catalog", {
        domain: state.domain, q: search.value.trim(), offset: append ? state.items.length : 0, limit: pageSize,
      });
      if (job !== state.catalogJob) return;
      state.items = append ? [...state.items, ...result.items] : result.items;
      state.total = result.total;
      paintCatalog();
    } catch (error) {
      if (job !== state.catalogJob) return;
      grid.innerHTML = '<p class="empty">' + escape(error.message) + '</p>';
      find("load-area").innerHTML = '<button class="button" type="button" data-action="retry">Réessayer</button>';
    } finally {
      if (job === state.catalogJob) grid.setAttribute("aria-busy", "false");
    }
  }

  function showView(view, scroll = true) {
    if (!views[view]) return;
    state.view = view;
    resetResults();
    root.querySelectorAll(".nav-item[data-view]").forEach((button) => {
      if (button.dataset.view === view) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    const [context, title, copy] = views[view];
    find("context").textContent = context;
    root.querySelector("#view-title").textContent = title;
    find("view-description").textContent = copy;
    find("hero").hidden = view !== "discover";
    paintOptions();
    paintSelection();
    if (scroll) root.scrollIntoView({block: "start"});
  }

  function changeDomain(slug) {
    if (!domainMap.has(slug) || slug === state.domain) return;
    state.domain = slug;
    search.value = "";
    search.placeholder = "Rechercher · " + domain().label;
    resetResults();
    paintDomains();
    paintOptions();
    paintSelection();
    loadCatalog();
    root.querySelector('[data-domain="' + slug + '"]').focus();
  }

  function toggleItem(item, control) {
    if (!item) return;
    const picked = seeds();
    if (picked.has(item.item_id)) picked.delete(item.item_id);
    else if (picked.size < 5) picked.set(item.item_id, item);
    else {
      find("notice").textContent = "Tu peux sélectionner jusqu’à cinq éléments.";
      return;
    }
    resetResults();
    paintSelection();
    paintCatalog();
    if (control) {
      const target = [...root.querySelectorAll('[data-action="toggle"]')].find(
        (node) => node.dataset.id === item.item_id
      );
      if (target) target.focus({preventScroll: true});
      else submit.focus({preventScroll: true});
    }
  }

  function resultsGrid(data, key) {
    if (!data.recommendations.length) return '<p class="empty">Aucune recommandation disponible.</p>';
    return '<div class="result-grid">' + data.recommendations.map((item, index) => {
      const vote = state.votes.get(item.domaine + ":" + item.item_id);
      const pending = state.waitingVotes.has(item.domaine + ":" + item.item_id);
      return '<article class="result-card"><span class="result-label">' + (index + 1) + '</span>' +
        poster(item, "", false) + '<div class="result-body"><button type="button" class="tile-name" ' +
        'data-action="result-detail" data-result="' + key + '" data-id="' + escape(item.item_id) + '">' +
        escape(item.titre) + '</button>' + tags(item) + '<p>' + escape(item.explanation) +
        '</p><div class="vote-row">' + ["up", "down"].map((value) =>
          '<button type="button" class="icon-button" data-action="vote" data-vote="' + value +
          '" data-result="' + key + '" data-id="' + escape(item.item_id) + '" aria-label="' +
          escape(value === "up" ? "Suggestion utile" : "Suggestion peu utile") + '" aria-pressed="' +
          (value === vote) + '"' + (vote || pending ? ' disabled' : '') + '>' + icon(value) + '</button>'
        ).join("") + (vote ? '<span class="vote-status">Vote enregistré</span>' : '') + '</div></div></article>';
    }).join("") + '</div>';
  }

  function paintResults() {
    const target = find("results");
    if (!state.result) return;
    const {heading, description, lists} = state.result;
    target.hidden = false;
    const header = '<header class="results-header"><h2>' + escape(heading) +
      '</h2><p>' + escape(description) + '</p></header>';
    if (lists.length === 2) {
      target.innerHTML = header + '<div class="comparison">' + lists.map((data, key) =>
        '<section class="comparison-pane"><h3>' + escape(domain().models.find(
          (model) => model.id === data.model
        )?.label || data.model) + '</h3>' + resultsGrid(data, key) + '</section>'
      ).join("") + '</div>';
    } else {
      target.innerHTML = header + resultsGrid(lists[0], 0);
    }
  }

  async function computeRecommendations() {
    if (submit.disabled) return;
    const job = ++state.recJob;
    state.busy = true;
    find("notice").textContent = "";
    find("results").hidden = true;
    paintSelection();
    const liked = [...seeds().keys()];
    const taste = (model) => request("taste", {domain: state.domain, model, liked, k: 10});
    try {
      if (state.view === "compare") {
        const lists = await Promise.all([taste(state.modelA), taste(state.modelB)]);
        if (job !== state.recJob) return;
        state.result = {heading: "Résultats côte à côte", lists,
          description: "Même catalogue, mêmes favoris et jusqu’à 10 résultats par modèle."};
      } else if (state.view === "cross") {
        const list = await request("cross", {
          source_domain: state.domain, target_domain: state.target, liked, k: 10,
        });
        if (job !== state.recJob) return;
        state.result = {heading: domain().label + " → " + domainMap.get(list.domain).label,
          lists: [list], description: "Des suggestions dans ton domaine cible à partir de tes favoris."};
      } else {
        const list = await taste(domain().default_model);
        if (job !== state.recJob) return;
        state.result = {heading: "Tes recommandations", lists: [list],
          description: list.recommendations.length + " suggestions dans le catalogue " + domain().label.toLowerCase() + "."};
      }
      paintResults();
      find("results").scrollIntoView({block: "start"});
    } catch (error) {
      if (job === state.recJob) find("notice").textContent = error.message;
    } finally {
      if (job === state.recJob) {
        state.busy = false;
        paintSelection();
      }
    }
  }

  function dialog(html) {
    find("dialog-content").innerHTML = html;
    if (!find("dialog").open) find("dialog").showModal();
  }

  function details(item, pickable) {
    if (!item) return;
    const action = pickable
      ? '<button class="button primary" type="button" data-action="dialog-toggle" data-id="' +
        escape(item.item_id) + '">' + icon(seeds().has(item.item_id) ? "check" : "plus") +
        (seeds().has(item.item_id) ? "Retirer de ma sélection" : "Ajouter à ma sélection") + '</button>'
      : "";
    dialog('<h2>' + escape(item.titre) + '</h2>' + tags(item) +
      (item.description ? '<p>' + escape(item.description) + '</p>' : '') +
      (item.explanation ? '<p>' + escape(item.explanation) + '</p>' : '') + action);
  }

  function resultItem(control) {
    return state.result?.lists[Number(control.dataset.result)]?.recommendations.find(
      (item) => item.item_id === control.dataset.id
    );
  }

  async function castVote(control) {
    const item = resultItem(control);
    const vote = control.dataset.vote;
    if (!item) return;
    const key = item.domaine + ":" + item.item_id;
    if (state.votes.has(key) || state.waitingVotes.has(key)) return;
    state.waitingVotes.add(key);
    paintResults();
    try {
      await request("feedback", {domain: item.domaine, item_id: item.item_id, vote});
      state.votes.set(key, vote);
    } catch (error) {
      find("notice").textContent = error.message;
    } finally {
      state.waitingVotes.delete(key);
      paintResults();
    }
  }

  root.addEventListener("click", (event) => {
    const control = event.target.closest("button");
    if (!control || !root.contains(control)) return;
    if (control.dataset.view) return showView(control.dataset.view);
    if (control.dataset.domain) return changeDomain(control.dataset.domain);
    const {action, id} = control.dataset;
    const item = state.items.find((entry) => entry.item_id === id) || seeds().get(id);
    switch (action) {
      case "explore": root.querySelector("#catalogue").scrollIntoView({block: "start"}); break;
      case "more": loadCatalog(true); break;
      case "retry": loadCatalog(); break;
      case "toggle":
      case "remove": toggleItem(item, control); break;
      case "recommend": computeRecommendations(); break;
      case "detail": details(item, true); break;
      case "result-detail": details(resultItem(control), false); break;
      case "dialog-toggle":
        find("dialog").close();
        toggleItem(item, control);
        break;
      case "close": find("dialog").close(); break;
      case "privacy": dialog("<h2>Confidentialité</h2>" + privacy.map((p) => "<p>" + p + "</p>").join(""));
        break;
      case "vote": castVote(control); break;
      default: break;
    }
  });
  root.addEventListener("change", (event) => {
    const setting = event.target.dataset.setting;
    if (!setting) return;
    state[setting] = event.target.value;
    resetResults();
    paintSelection();
  });
  let searchTimer;
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadCatalog(), 170);
  });
  root.addEventListener("error", (event) => {
    if (event.target.tagName === "IMG") event.target.hidden = true;
  }, true);

  paintDomains();
  showView("discover", false);
  loadCatalog();
}
