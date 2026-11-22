import {mount} from "./app.js";

async function api(url, payload) {
  const response = await fetch(url, payload === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Requête invalide ou momentanément indisponible.");
  }
  return data;
}

function request(action, payload) {
  if (action === "catalog") {
    const {domain, ...query} = payload;
    return api("/catalog/" + encodeURIComponent(domain) + "?" + new URLSearchParams(query));
  }
  const routes = {taste: "/recommend/items", cross: "/cross-recommend", feed: "/recommend/feed", feedback: "/feedback"};
  return api(routes[action], payload);
}

const root = document.querySelector("[data-prisme]");
try {
  const metadata = await api("/domains");
  mount(root, {
    hero: "/assets/hero.webp",
    tiles: Array.from({length: 12}, (_, index) => "/assets/art-" + index + ".webp"),
  }, request, metadata);
} catch {
  const notice = root.querySelector('[data-role="notice"]');
  notice.textContent = "Le catalogue est indisponible. Recharge la page pour réessayer.";
  root.querySelector('[data-role="catalog"]').setAttribute("aria-busy", "false");
}
