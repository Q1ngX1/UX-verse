import {routes, terrains} from "./routes.js";
import {configure, homeExtras, catalogExtras, detailExtras, collectionsPage, journalPage, plannerPage, guideExtras, installCompare, syncCompare} from "./explore.js";

const main = document.querySelector("#main");
const page = document.body.dataset.page;
const query = new URLSearchParams(window.location.search);
const issues = query.get("scenario") === "issues";
const saveKey = "waymark.saved.v1";
const nav = [["routes.html", "Routes"], ["collections.html", "Collections"], ["journal.html", "Journal"], ["guide.html", "Field guide"], ["saved.html", "Saved"], ["planner.html", "Day planner"], ["contact.html", "Contact"]];
const routeIndex = new Map(routes.map(route => [route.id, route]));

document.body.classList.toggle("issues", issues);

function link(file, values = {}, hash = "") {
  const params = new URLSearchParams(values);
  if (issues) params.set("scenario", "issues");
  return file + (params.size ? `?${params}` : "") + hash;
}

function loadSaved() {
  try {
    const ids = JSON.parse(localStorage.getItem(saveKey));
    return new Set(Array.isArray(ids) ? ids.filter(id => routeIndex.has(id)) : []);
  } catch {
    return new Set();
  }
}

const saved = loadSaved();

function layout() {
  const active = page === "detail" ? "routes" : page;
  const links = nav.filter(([file]) => !issues || file !== "saved.html").map(([file, label]) =>
    `<a href="${link(file)}"${file === `${active}.html` ? ' aria-current="page"' : ""}>${label}${file === "saved.html" ? ' <span data-count></span>' : ""}</a>`,
  ).join("");
  document.querySelector("#header").innerHTML = `
    <div class="wrap topbar">
      <a class="brand" href="${link("index.html")}"><span aria-hidden="true" class="mark"></span>waymark<span class="brand-dot">.</span></a>
      <button type="button" id="menu" class="button secondary menu" aria-expanded="false" aria-controls="primary">Menu</button>
      <nav id="primary" aria-label="Main navigation">${links}</nav>
    </div>`;
  document.querySelector("#footer").innerHTML = `
    <div class="wrap footer-inner">
      <div><a class="brand" href="${link("index.html")}"><span aria-hidden="true" class="mark"></span>waymark.</a>
      <p>A little closer to the outdoors.</p><p>Local UX-verse test site · Fictional routes and sample content</p></div>
      <nav aria-label="Footer">${nav.map(([file, label]) => `<a href="${link(file)}">${label}</a>`).join("")}</nav>
    </div>`;
  document.body.insertAdjacentHTML("beforeend", '<div class="notice" role="status" aria-live="polite"></div>');

  const menu = document.querySelector("#menu");
  const toggleMenu = open => menu.setAttribute("aria-expanded", String(open));
  menu.addEventListener("click", () => toggleMenu(menu.getAttribute("aria-expanded") === "false"));
  document.querySelector("#header").addEventListener("keydown", event => {
    if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
      toggleMenu(false);
      menu.focus();
    }
  });
  installCompare();
}

function saveButton(route, full = false) {
  return `<button type="button" class="button secondary ${full ? "save-wide" : "save"}" data-save="${route.id}"></button>`;
}

function syncSaved() {
  for (const button of document.querySelectorAll("[data-save]")) {
    const active = saved.has(button.dataset.save);
    const route = routeIndex.get(button.dataset.save);
    button.setAttribute("aria-pressed", String(active));
    button.setAttribute("aria-label", `${active ? "Remove" : "Save"} ${route.name}`);
    button.textContent = button.classList.contains("save-wide") ? (active ? "Saved" : "Save route") : (active ? "♥" : "♡");
  }
  for (const counter of document.querySelectorAll("[data-count]")) {
    counter.textContent = saved.size ? `(${saved.size})` : "";
  }
  syncCompare();
}

let noticeTimer;
function notify(text) {
  const notice = document.querySelector(".notice");
  clearTimeout(noticeTimer);
  notice.textContent = text;
  noticeTimer = setTimeout(() => { notice.textContent = ""; }, 2400);
}

function timeLabel(minutes) {
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
}

function card(route, returnFilters = "") {
  const terrain = terrains[route.terrain];
  const image = `<img src="${terrain.image}" alt="${terrain.alt}" style="object-position:${route.position}" loading="lazy">`;
  const data = returnFilters ? {id: route.id, from: returnFilters} : {id: route.id};
  const title = `<div class="card-title"><p class="eyebrow">${route.area}</p><h3>${route.name}</h3></div>`;
  return `<article class="card">
    ${issues ? image : ""}
    <a class="card-link" href="${link("route.html", data)}" aria-label="${route.name}">${issues ? "" : image}${title}</a>
    <span class="terrain-badge">${route.terrain}</span>
    <div class="card-body"><p>${route.teaser}</p><p class="stats"><span class="difficulty ${route.difficulty.toLowerCase()}">${route.difficulty}</span> · ${route.miles} mi · ${timeLabel(route.minutes)}</p><button type="button" class="compare-add" data-compare="${route.id}" aria-label="Compare ${route.name}" aria-pressed="false">Compare ${route.name}</button></div>
    ${saveButton(route)}
  </article>`;
}

function home() {
  main.innerHTML = `
    <section class="wrap hero">
      <div class="hero-copy"><p class="eyebrow"><span class="tiny-sun" aria-hidden="true">✳</span> A day outside, a little closer</p>
        <h1>Find a trail worth the morning.</h1>
        <p class="lede">Less screen time. More trail time. Discover thoughtful walks around the Bay Area, from ocean air to the quiet of the forest.</p>
        <form class="hero-search" action="routes.html" method="get">
          <label for="home-search">Find a route</label>
          <div><input id="home-search" type="search" name="q" placeholder="Try coast or redwoods">${issues ? '<input name="scenario" type="hidden" value="issues">' : ""}<button class="button" type="submit">Search</button></div>
        </form>
        <a class="text-link" href="${link("routes.html")}">Browse all routes</a>
        <div class="hero-footnote"><span aria-hidden="true">⌁</span> Somewhere good is closer than you think.</div>
      </div>
      <figure><img src="${terrains.Coast.image}" alt="${terrains.Coast.alt}" fetchpriority="high">
        <span class="photo-stamp">THE WEEKEND<br>IS CALLING</span><figcaption><span>This week’s little escape</span><a href="${link("route.html", {id: "cypress-headland"})}">Cypress Headland</a><span>Marin Coast · 4.8 mi · Moderate</span></figcaption>
      </figure>
    </section>
    <div class="trail-strip"><div class="wrap"><span>Go at your own pace</span><span>15 routes to wander</span><span>Coast, forest & city</span><span>Made for a day outside</span></div></div>
    <section class="wrap section">
      <div class="section-title"><div><h2>Explore by terrain</h2><p>Choose the scenery that suits your day.</p></div></div>
      <div class="terrain-list">${Object.entries(terrains).map(([name, info]) => `<a href="${link("routes.html", {terrain: name})}"><img src="${info.image}" alt="" loading="lazy"><span class="terrain-icon" aria-hidden="true">${{Coast:"≈",Forest:"♧",Urban:"⌂"}[name]}</span><strong>${name}</strong><span>${info.copy}</span><small>${routes.filter(route => route.terrain === name).length} routes to explore</small></a>`).join("")}</div>
    </section>
    <section class="wrap section"><div class="section-title"><h2>Featured routes</h2><a class="text-link" href="${link("routes.html")}">See all routes</a></div>
      <div class="grid">${routes.slice(0, 3).map(route => card(route)).join("")}</div>
    </section>`;
  homeExtras();
}

function catalog() {
  main.innerHTML = `
    <section class="wrap section"><h1>Find a route</h1><p class="lede">Search by name or area, or narrow the list by terrain and difficulty.</p>
      <form id="filters" class="filters">
        <label>Search routes<input name="q" type="search" placeholder="Search names, areas, or terrain"></label>
        <label>Terrain<select name="terrain"><option value="">All terrain</option>${Object.keys(terrains).map(key => `<option>${key}</option>`).join("")}</select></label>
        <label>Difficulty<select name="difficulty"><option value="">All difficulties</option><option>Easy</option><option>Moderate</option><option>Challenging</option></select></label>
        <label>Sort by<select name="sort"><option value="featured">Featured</option><option value="shortest">Shortest distance</option><option value="longest">Longest distance</option></select></label>
        <button type="button" id="clear-filters" class="button secondary">Clear filters</button>
      </form>
      <p id="result-count" class="stats" role="status"></p>
      <div id="results" class="grid"></div>
    </section>`;

  const form = document.querySelector("#filters");
  function update(changeURL) {
    const {q, terrain, difficulty, sort} = form.elements;
    const value = q.value.trim();
    const terms = value.toLowerCase().split(/\s+/);
    const matches = routes.filter(route => {
      const searchable = `${route.name} ${route.area} ${route.terrain} ${route.teaser} ${route.description}`.toLowerCase();
      return (!terrain.value || route.terrain === terrain.value)
        && (!difficulty.value || route.difficulty === difficulty.value)
        && terms.every(term => searchable.includes(term))
        && (!form.elements.duration?.value || route.minutes <= Number(form.elements.duration.value))
        && (!form.elements.facility?.value || route.facilities.includes(form.elements.facility.value));
    });
    if (sort.value === "shortest") matches.sort((a, b) => a.miles - b.miles);
    if (sort.value === "longest") matches.sort((a, b) => b.miles - a.miles);
    const filters = new URLSearchParams();
    if (value) filters.set("q", value);
    if (terrain.value) filters.set("terrain", terrain.value);
    if (difficulty.value) filters.set("difficulty", difficulty.value);
    if (sort.value !== "featured") filters.set("sort", sort.value);
    if (form.elements.duration?.value) filters.set("duration", form.elements.duration.value);
    if (form.elements.facility?.value) filters.set("facility", form.elements.facility.value);
    if (document.querySelector('[data-view="map"][aria-pressed="true"]')) filters.set("view", "map");
    if (changeURL) history.replaceState(null, "", link("routes.html", filters));
    document.querySelector("#result-count").textContent = `${matches.length} ${matches.length === 1 ? "route" : "routes"}`;
    document.querySelector("#results").innerHTML = matches.length
      ? matches.map(route => card(route, filters.toString())).join("")
      : '<div class="empty"><h2>No matching routes</h2><p>Try a broader search or clear a filter.</p></div>';
    syncSaved();
    document.dispatchEvent(new CustomEvent("waymark:results", {detail: {matches, filters: filters.toString()}}));
  }

  catalogExtras(form, () => update(true));
  for (const control of form.querySelectorAll("input, select")) {
    if (query.has(control.name)) control.value = query.get(control.name);
    if (control.name === "sort" && !control.value) control.value = "featured";
  }
  form.addEventListener("submit", event => { event.preventDefault(); update(true); });
  form.addEventListener("input", () => update(true));
  document.querySelector("#clear-filters").addEventListener("click", () => {
    const difficulty = form.elements.difficulty.value;
    form.reset();
    if (issues) form.elements.difficulty.value = difficulty;
    update(true);
  });
  update(false);
  window.addEventListener("popstate", () => {
    form.reset();
    const state = new URLSearchParams(location.search);
    for (const control of form.querySelectorAll("input, select")) if (state.has(control.name)) control.value = state.get(control.name);
    update(false);
  });
}

function detail() {
  const route = routeIndex.get(query.get("id"));
  if (!route) {
    main.innerHTML = `<section class="wrap section"><h1>Route not found</h1><p>Browse the directory to find another route.</p><a class="button" href="${link("routes.html")}">Find a route</a></section>`;
    return;
  }
  document.title = `${route.name} · Waymark`;
  const terrain = terrains[route.terrain];
  const returnFilters = new URLSearchParams(query.get("from") ?? "");
  const back = issues ? link("index.html") : link("routes.html", returnFilters);
  main.innerHTML = `
    <section class="wrap section">
      <nav class="crumb" aria-label="Breadcrumb"><a href="${back}">All routes</a><span aria-hidden="true">/</span><span>${route.name}</span></nav>
      <div class="section-title"><div><p class="eyebrow">${route.area} · ${route.terrain}</p><h1>${route.name}</h1><p class="lede">${route.teaser}</p></div>${saveButton(route, true)}</div>
      <div class="detail-top">
        <button type="button" id="photo-button" class="photo-button" aria-label="Enlarge route photo"><img src="${terrain.image}" alt="${terrain.alt}" style="object-position:${route.position}"><span>View photo</span></button>
        <aside class="route-facts" aria-label="Route at a glance"><h2>At a glance</h2>
          <dl><div><dt>Distance</dt><dd>${route.miles} mi</dd></div><div><dt>Difficulty</dt><dd>${route.difficulty}</dd></div>
          <div><dt>Typical time</dt><dd>${timeLabel(route.minutes)}</dd></div><div><dt>Elevation gain</dt><dd>${route.gain} ft</dd></div><div><dt>Route type</dt><dd>${route.shape}</dd></div></dl>
        </aside>
      </div>
      <div class="detail-sections">
        <div class="tabs" role="group" aria-label="Route information">
          <button type="button" data-tab="overview" aria-controls="route-panel">Overview</button><button type="button" data-tab="access" aria-controls="route-panel">Parking &amp; access</button><button type="button" data-tab="gear" aria-controls="route-panel">What to bring</button>
        </div>
        <div id="route-panel" aria-live="polite"></div>
      </div>
      <a class="text-link" href="${link("guide.html")}">Read the field guide</a>
    </section>
    <dialog id="photo" aria-label="Route photo"><form method="dialog"><button class="button secondary" autofocus>Close photo</button></form><img src="${terrain.image}" alt="${terrain.alt}"></dialog>
    ${issues ? `<aside class="mobile-callout"><strong>Keep this route handy</strong><p>Save it for your next day out.</p>${saveButton(route, true)}</aside>` : ""}`;
  const panel = document.querySelector("#route-panel");
  const tabs = document.querySelectorAll("[data-tab]");
  const details = {
    overview: `<h2>Route overview</h2><p>${route.description}</p><h3>Along the way</h3><ol>${route.stops.map(stop => `<li>${stop}</li>`).join("")}</ol>`,
    access: `<h2>Parking &amp; access</h2><p>${route.logistics}</p>`,
    gear: `<h2>What to bring</h2><p>${route.gear}</p>`,
  };
  function show(tab) {
    panel.innerHTML = details[tab];
    for (const button of tabs) button.setAttribute("aria-pressed", String(button.dataset.tab === tab));
  }
  for (const button of tabs) button.addEventListener("click", () => show(issues && button.dataset.tab === "access" ? "gear" : button.dataset.tab));
  document.querySelector("#photo-button").addEventListener("click", () => document.querySelector("#photo").showModal());
  show("overview");
  detailExtras(route);
}

function savedPage() {
  const collection = routes.filter(route => saved.has(route.id));
  main.innerHTML = `<section class="wrap section"><h1 tabindex="-1">Saved routes</h1><p class="lede">Keep a shortlist for your next day outside.</p>
    ${collection.length ? `<div class="saved-summary"><span>${collection.length} saved · ${collection.reduce((n, r) => n + r.miles, 0).toFixed(1)} miles of possibility</span><a class="button secondary" href="${link("planner.html")}">Build a day plan</a></div>` : ""}
    ${collection.length ? `<div class="grid">${collection.map(route => card(route)).join("")}</div>` : `<div class="empty"><h2>No routes saved yet</h2><p>Save a route from the directory or from its detail page.</p><a class="button" href="${link("routes.html")}">Browse routes</a></div>`}</section>`;
}

function guide() {
  const seasonal = issues ? "seasonal-access.html?scenario=issues" : link("guide.html", {}, "#seasonal");
  main.innerHTML = `<section class="wrap section guide"><div><h1>Field guide</h1><p class="lede">A few things to check before you choose a route and head out.</p>
    <h2>Plan your day</h2><p>Compare distance, elevation, and difficulty in the route directory. Each route page lists a typical time, the trailhead, and the facilities available at the start.</p>
    <p><a class="text-link" href="${seasonal}">Check seasonal access</a></p>
    <h2 id="seasonal">Seasonal access</h2><p>After wet weather, check the route’s access notes before leaving. Coastal paths may be exposed to strong wind, and shaded forest trails can stay muddy for longer.</p>
    <h2>Frequently asked questions</h2>
    <details><summary>What do the difficulty labels mean?</summary><p>Easy routes are shorter and climb less. Moderate routes may include sustained hills. Challenging routes combine longer distances, steeper climbs, or uneven terrain.</p></details>
    <details><summary>Where can I find parking information?</summary><p>Open a route and select Parking &amp; access to see trailhead, parking, restroom, and transit notes.</p></details>
    <details><summary>Where are my saved routes stored?</summary><p>Saved routes stay in this browser. Open Saved to see your shortlist.</p></details>
    <p><a class="text-link" href="${link("contact.html")}">Report a problem with a route</a></p></div>
    <aside class="guide-card"><img src="${terrains.Forest.image}" alt="${terrains.Forest.alt}" loading="lazy"><h2>Take the shaded route</h2><p>Redwood loops offer a cooler option on warm afternoons.</p><a class="text-link" href="${link("routes.html", {terrain: "Forest"})}">Find forest routes</a></aside>
    </section>`;
  guideExtras();
}

function contact() {
  main.innerHTML = `<section class="wrap section guide"><div><h1>Contact Waymark</h1><p class="lede">Report a route detail or tell us about an issue using the site.</p>
    <form id="contact-form" class="contact-form">
      <label>Your name<input name="name" autocomplete="name" required maxlength="80"></label>
      <label>Email<input name="email" type="email" autocomplete="email" required maxlength="160"></label>
      <label>Topic<select name="topic"><option>Route information</option><option>Website feedback</option><option>General question</option></select></label>
      <label>Message<textarea name="message" rows="5" required maxlength="800"></textarea></label>
      <button class="button" type="submit">Send message</button>
      <p class="feedback" id="feedback" role="status"></p>
    </form></div><aside class="guide-card contact-note"><h2>About this form</h2><p>This is a local demo. Use sample contact details. Messages are handled in your browser.</p><a class="text-link" href="${link("guide.html")}#seasonal">Check the field guide</a></aside></section>`;
  const form = document.querySelector("#contact-form");
  const feedback = document.querySelector("#feedback");
  const button = form.querySelector("button");
  form.addEventListener("submit", event => {
    event.preventDefault();
    button.disabled = true;
    button.textContent = "Sending…";
    feedback.textContent = "";
    setTimeout(() => {
      form.reset();
      button.textContent = "Send message";
      button.disabled = false;
      if (!issues) feedback.textContent = "Thanks. Your demo message was received.";
    }, 650);
  });
}

configure({main, link, card, timeLabel, syncSaved, notify});
layout();
({home, routes: catalog, detail, saved: savedPage, guide, contact, collections: collectionsPage, journal: journalPage, planner: plannerPage})[page]();
syncSaved();

main.addEventListener("click", event => {
  const button = event.target.closest("[data-save]");
  if (!button) return;
  const id = button.dataset.save;
  const route = routeIndex.get(id);
  const removing = saved.has(id);
  if (removing) saved.delete(id);
  else saved.add(id);
  try {
    localStorage.setItem(saveKey, JSON.stringify([...saved]));
  } catch {
    notify("This browser could not persist your shortlist.");
    syncSaved();
    return;
  }
  if (page === "saved") {
    savedPage();
    (main.querySelector("[data-save]") ?? main.querySelector("h1")).focus();
  }
  syncSaved();
  notify(`${route.name} ${removing ? "removed from your shortlist" : "saved"}.`);
});
