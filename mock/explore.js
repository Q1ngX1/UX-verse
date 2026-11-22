import {routes, terrains} from "./routes.js";
import {collections, stories, packingItems} from "./content.js";

let app;
const index = new Map(routes.map(route => [route.id, route]));
const params = () => new URLSearchParams(location.search);
const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { app.notify("Changes are available for this visit, but this browser could not save them."); return false; } };
export function configure(context) { app = context; }

function collectionCard(collection) {
  return `<a class="collection-card" href="${app.link("collections.html", {id: collection.id})}"><img src="assets/${collection.image}.webp" alt="" loading="lazy"><div><span class="eyebrow">${collection.kicker}</span><h3>${collection.title}</h3><p>${collection.ids.length} handpicked routes</p></div></a>`;
}
function storyCard(story) {
  return `<article class="story-card"><a href="${app.link("journal.html", {id: story.id})}"><img src="assets/${story.image}.webp" alt="" loading="lazy"><div><p class="eyebrow">${story.category} <span>· ${story.read} min read</span></p><h3>${story.title}</h3><p>${story.intro}</p><span class="text-link">Read the story</span></div></a></article>`;
}

export function homeExtras() {
  app.main.insertAdjacentHTML("beforeend", `
    <section class="mood-section"><div class="wrap mood-layout"><div><p class="eyebrow">A little inspiration</p><h2>What kind of day<br>are you dreaming of?</h2><p>There’s no one way to get outside.<br>Find a walk that feels like you.</p></div><div class="mood-finder"><div class="pill-group" role="group" aria-label="Choose a mood">${["Find some shade", "Ocean air", "Car-free friendly"].map((mood, i) => `<button class="pill" type="button" data-mood="${mood}" aria-pressed="${i === 0}">${mood}</button>`).join("")}</div><p id="mood-copy"></p><a id="mood-result" class="button" href="${app.link("routes.html", {terrain:"Forest"})}">Find my escape</a><span class="micro">A change of scenery is a good place to start.</span></div></div></section>
    <section class="wrap section"><div class="section-title"><div><p class="eyebrow">Good days, thoughtfully gathered</p><h2>A collection for every mood.</h2></div><a class="text-link" href="${app.link("collections.html")}">Explore collections</a></div><div class="collection-grid">${collections.slice(0,3).map(collectionCard).join("")}</div></section>
    <section class="wrap section journal-section"><div class="section-title"><div><p class="eyebrow">The field journal</p><h2>Notes from the outside.</h2></div><a class="text-link" href="${app.link("journal.html")}">All stories</a></div><div class="grid">${stories.map(storyCard).join("")}</div></section>
    <section class="wrap invitation"><div class="invitation-symbol" aria-hidden="true">✳</div><div><p class="eyebrow">Make a little room for adventure</p><h2>Your next good day starts here.</h2><p>Save a few favorites. Pack the essentials. Leave the rest of the day open.</p></div><a class="button" href="${app.link("planner.html")}">Plan a day outside</a></section>`);
  const descriptions = {"Find some shade": ["Cool creek paths, dappled light, and a little quiet under the canopy.", "Forest"], "Ocean air": ["Open headlands, salty breezes, and room to watch the horizon.", "Coast"], "Car-free friendly": ["Waterfront paths and neighborhood greenways to reach at a slower pace.", "Urban"]};
  const choose = mood => {
    document.querySelector("#mood-copy").textContent = descriptions[mood][0];
    document.querySelector("#mood-result").href = app.link("routes.html", {terrain: descriptions[mood][1]});
    document.querySelectorAll("[data-mood]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.mood === mood)));
  };
  document.querySelectorAll("[data-mood]").forEach(button => button.addEventListener("click", () => choose(button.dataset.mood)));
  choose("Find some shade");
  trailFinder();
}

function trailFinder() {
  document.querySelector(".hero .text-link").insertAdjacentHTML("afterend", '<button type="button" class="finder-trigger quiet-button" id="open-finder">Help me choose a trail</button>');
  app.main.insertAdjacentHTML("beforeend", `<dialog id="trail-finder" aria-labelledby="finder-title"><form method="dialog" class="dialog-header"><p class="eyebrow">The little trail finder</p><button class="button secondary">Close trail finder</button></form><div id="finder-content"></div></dialog>`);
  const dialog = document.querySelector("#trail-finder");
  let step = 0;
  const answers = ["", "90", ""];
  const questions = [
    {title:"Where would you like to wander?", copy:"Start with a change of scenery.", options:[["", "Surprise me", "A little of everything"], ["Forest", "Under the trees", "Creek paths and quiet canopies"], ["Coast", "Beside the sea", "Open skies and ocean air"], ["Urban", "Around the neighborhood", "Waterfronts, gardens, and cafés"]]},
    {title:"How much time is yours?", copy:"Choose your walking time. Leave a little room for pauses.", options:[["60", "A small escape", "Up to 1 hour"], ["90", "A slow morning", "Up to 90 minutes"], ["150", "A little longer", "Up to 2.5 hours"], ["", "The day is wide open", "Any walking time"]]},
    {title:"What pace feels right?", copy:"There’s a good day outside for every kind of energy.", options:[["Easy", "Keep it gentle", "Shorter routes and smaller climbs"], ["Moderate", "A little adventure", "Some hills along the way"], ["Challenging", "Make it a challenge", "Longer climbs and uneven trails"], ["", "Show me everything", "I’ll choose as I go"]]},
  ];
  const content = document.querySelector("#finder-content");
  const render = () => {
    if(step===3) {
      const matches=routes.filter(route=>(!answers[0] || route.terrain===answers[0]) && (!answers[1] || route.minutes<=Number(answers[1])) && (!answers[2] || route.difficulty===answers[2]));
      content.innerHTML=`<p class="eyebrow">A little inspiration, just for you</p><h2 id="finder-title" tabindex="-1">${matches.length ? "Your kind of day is out there." : "Let’s leave a little more room."}</h2><p class="lede">${matches.length ? `${matches.length} ${matches.length===1 ? "route fits" : "routes fit"} your plans. Here are a few places to start.` : "No routes fit all three choices. Try more walking time or a different pace."}</p><div class="grid finder-results">${matches.slice(0,3).map(route=>app.card(route)).join("")}</div><div class="button-row"><button class="button secondary" type="button" data-finder-back>Change my answers</button>${matches.length ? `<a class="button" href="${app.link("routes.html", Object.fromEntries([["terrain",answers[0]],["duration",answers[1]],["difficulty",answers[2]]].filter(([,value])=>value)))}">View all matches</a>` : ""}</div>`;
      app.syncSaved();
    } else {
      const question=questions[step];
      content.innerHTML=`<p class="eyebrow">${step+1} of 3 · Your day, your way</p><h2 id="finder-title" tabindex="-1">${question.title}</h2><p class="lede">${question.copy}</p><form id="finder-form"><fieldset class="finder-options"><legend class="sr-only">${question.title}</legend>${question.options.map(([value,label,copy])=>`<label class="finder-option"><input type="radio" name="choice" value="${value}" ${answers[step]===value ? "checked" : ""}><span><strong>${label}</strong><small>${copy}</small></span></label>`).join("")}</fieldset><div class="button-row">${step>0 ? '<button class="button secondary" type="button" data-finder-back>Back</button>' : ""}<button class="button" type="submit">${step===2 ? "Find my trails" : "Continue"}</button></div></form>`;
      content.querySelector("#finder-form").addEventListener("submit",event=> { event.preventDefault(); answers[step]=new FormData(event.currentTarget).get("choice") ?? ""; step++; render(); content.querySelector("h2").focus(); });
      content.querySelectorAll("input").forEach(input=>input.addEventListener("change",()=> { answers[step]=input.value; }));
    }
    content.querySelector("[data-finder-back]")?.addEventListener("click",()=> { step--; render(); content.querySelector("h2").focus(); });
  };
  document.querySelector("#open-finder").addEventListener("click",()=> { step=0; render(); dialog.showModal(); });
}

// A deliberately schematic map: no third-party tiles, geolocation, or external requests.
function mapArtwork() {
  return `<svg class="map-art" viewBox="0 0 800 600" preserveAspectRatio="none" aria-hidden="true"><defs><pattern id="contours" width="90" height="85" patternUnits="userSpaceOnUse"><path d="M-20 40 Q25 -10 65 40 T155 40 M-20 58 Q25 8 65 58 T155 58" fill="none" stroke="#afbea4" stroke-width="1" opacity=".35"/></pattern></defs><rect width="800" height="600" fill="#e3e8d8"/><path d="M0 0H315Q270 90 360 145T380 290Q310 390 420 450L390 600H0Z" fill="#bfd4d5"/><path d="M410 0Q350 150 465 170T450 310Q380 390 510 480L570 600H660Q545 420 570 320T555 150L590 0Z" fill="#bfd4d5"/><rect width="800" height="600" fill="url(#contours)"/><path d="M130 0Q340 130 220 330T300 600M540 0Q600 210 650 320T730 600M50 380Q350 250 780 450" fill="none" stroke="#f8faf0" stroke-width="9"/><path d="M130 0Q340 130 220 330T300 600M540 0Q600 210 650 320T730 600M50 380Q350 250 780 450" fill="none" stroke="#d4c9b1" stroke-width="2"/><g fill="#52685d" font-size="17" font-family="system-ui"><text x="85" y="315" transform="rotate(-75 85 315)" letter-spacing="6">PACIFIC OCEAN</text><text x="270" y="75">NORTH BAY</text><text x="625" y="190">EAST BAY</text><text x="280" y="530">PENINSULA</text><text x="550" y="558">SOUTH BAY</text></g></svg>`;
}

export function catalogExtras(form, update) {
  form.insertAdjacentHTML("beforeend", `<label>Walking time<select name="duration" aria-label="Walking time"><option value="">Any duration</option><option value="60">Up to 1 hour</option><option value="90">Up to 90 minutes</option><option value="150">Up to 2.5 hours</option></select></label><label>Facilities<select name="facility" aria-label="Facilities"><option value="">Any facilities</option><option>Restrooms</option><option>Water</option><option>Transit</option></select></label>`);
  document.querySelector("#result-count").insertAdjacentHTML("beforebegin", `<div class="catalog-tools"><div class="pill-group" role="group" aria-label="Quick filters"><button class="pill" data-quick="all" type="button">All adventures</button><button class="pill" data-quick="short" type="button">Under an hour</button><button class="pill" data-quick="Forest" type="button">In the trees</button><button class="pill" data-quick="Coast" type="button">By the sea</button></div><div class="view-switch" role="group" aria-label="Route display"><button type="button" data-view="grid">Grid</button><button type="button" data-view="map">Map</button></div></div>`);
  document.querySelector("#results").insertAdjacentHTML("afterend", `<section id="map-view" class="map-layout" hidden aria-label="Route map"><div class="route-map">${mapArtwork()}<div id="map-pins"></div><span class="map-disclaimer">Illustrative map · Not for navigation</span></div><div id="map-preview" class="map-preview" aria-live="polite"></div></section>`);
  let map = params().get("view") === "map";
  let current = routes;
  let returnFilters = "";
  const preview = route => {
    document.querySelector("#map-preview").innerHTML = route ? `<p class="eyebrow">Explore this route</p>${app.card(route, returnFilters)}` : `<div class="empty"><h2>No routes on the map</h2><p>Try changing your filters.</p></div>`;
    document.querySelectorAll("[data-pin]").forEach(pin => pin.setAttribute("aria-pressed", String(pin.dataset.pin === route?.id)));
    app.syncSaved();
  };
  const render = () => {
    document.querySelector("#results").hidden = map;
    document.querySelector("#map-view").hidden = !map;
    document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String((button.dataset.view === "map") === map)));
    document.querySelectorAll("[data-quick]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.quick === "short" ? form.elements.duration.value === "60" : button.dataset.quick === "all" ? !form.elements.duration.value && !form.elements.terrain.value : form.elements.terrain.value === button.dataset.quick)));
    document.querySelector("#map-pins").innerHTML = current.map(route => `<button type="button" class="map-pin" style="left:${route.point[0]}%;top:${route.point[1]}%" data-pin="${route.id}" aria-label="Show ${route.name}" aria-pressed="false"><span aria-hidden="true">♧</span><span class="pin-label">${route.name}</span></button>`).join("");
    preview(current[0]);
  };
  document.addEventListener("waymark:results", event => { current = event.detail.matches; returnFilters = event.detail.filters; render(); });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => { map = button.dataset.view === "map"; render(); update(); }));
  document.querySelectorAll("[data-quick]").forEach(button => button.addEventListener("click", () => {
    form.elements.duration.value = button.dataset.quick === "short" ? "60" : "";
    form.elements.terrain.value = ["Forest", "Coast"].includes(button.dataset.quick) ? button.dataset.quick : "";
    update();
  }));
  document.querySelector("#map-pins").addEventListener("click", event => { const pin = event.target.closest("[data-pin]"); if (pin) preview(index.get(pin.dataset.pin)); });
  window.addEventListener("popstate", () => { map = params().get("view") === "map"; render(); });
  render();
}

const compared = new Set();
let compareOpener;
export function syncCompare() {
  document.querySelectorAll("[data-compare]").forEach(button => { button.setAttribute("aria-pressed", String(compared.has(button.dataset.compare))); });
  const bar = document.querySelector("#compare-bar");
  if (!bar) return;
  bar.hidden = !compared.size;
  document.body.classList.toggle("has-compare", !!compared.size);
  document.querySelector("#compare-count").textContent = `${compared.size} of 3 routes selected`;
  document.querySelector("#open-compare").disabled = compared.size < 2;
}
export function installCompare() {
  document.body.insertAdjacentHTML("beforeend", `<aside id="compare-bar" class="compare-bar" aria-label="Route comparison" hidden><span id="compare-count" role="status"></span><button type="button" id="open-compare" class="button">Compare routes</button><button type="button" id="clear-compare" class="quiet-button">Clear</button></aside><dialog id="compare-dialog" aria-labelledby="compare-title"><form method="dialog" class="dialog-header"><h2 id="compare-title">Find your kind of trail.</h2><button class="button secondary">Close comparison</button></form><div id="comparison"></div></dialog>`);
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-compare]");
    if (!button) return;
    const id = button.dataset.compare;
    if (compared.has(id)) compared.delete(id);
    else if (compared.size < 3) compared.add(id);
    else { app.notify("Compare up to 3 routes. Remove one to make room."); return; }
    syncCompare();
  });
  document.querySelector("#clear-compare").addEventListener("click", () => {
    compared.clear(); syncCompare(); document.querySelector("[data-compare]")?.focus();
  });
  const dialog = document.querySelector("#compare-dialog");
  document.querySelector("#open-compare").addEventListener("click", event => {
    compareOpener = event.currentTarget;
    const selected = [...compared].map(id => index.get(id));
    const rows = [["Distance", route => `${route.miles} mi`], ["Walking time", route => app.timeLabel(route.minutes)], ["Difficulty", route => route.difficulty], ["Elevation gain", route => `${route.gain} ft`], ["Terrain", route => route.terrain], ["Route type", route => route.shape], ["Facilities", route => route.facilities.join(", ") || "None listed"]];
    document.querySelector("#comparison").innerHTML = `<div class="table-scroll" tabindex="0" aria-label="Route comparison table"><table><caption>Side-by-side trail details · fictional routes</caption><thead><tr><th scope="col">Your next adventure</th>${selected.map(route => `<th scope="col"><img src="${terrains[route.terrain].image}" alt=""><a href="${app.link("route.html", {id:route.id})}">${route.name}</a></th>`).join("")}</tr></thead><tbody>${rows.map(([label, value]) => `<tr><th scope="row">${label}</th>${selected.map(route => `<td>${value(route)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    document.querySelector("#comparison").insertAdjacentHTML("beforeend", `<div class="mobile-comparisons"><p class="micro">Your trail comparison · Fictional routes</p>${selected.map(route=>`<article class="mobile-comparison-card"><img src="${terrains[route.terrain].image}" alt=""><h3><a href="${app.link("route.html",{id:route.id})}">${route.name}</a></h3><dl>${rows.map(([label,value])=>`<div><dt>${label}</dt><dd>${value(route)}</dd></div>`).join("")}</dl></article>`).join("")}</div>`);
    dialog.showModal();
  });
  dialog.addEventListener("close", () => compareOpener?.focus());
}

export function collectionsPage() {
  const collection = collections.find(item => item.id === params().get("id"));
  if (params().has("id") && !collection) return missing("Collection");
  if (collection) {
    document.title = `${collection.title} · Waymark`;
    app.main.innerHTML = `<section class="wrap section"><nav class="crumb" aria-label="Breadcrumb"><a href="${app.link("collections.html")}">All collections</a><span>/</span><span>${collection.title}</span></nav><div class="collection-hero"><img src="assets/${collection.image}.webp" alt=""><div><p class="eyebrow">${collection.kicker}</p><h1>${collection.title}</h1><p class="lede">${collection.description}</p><p class="micro">${collection.ids.length} routes · An editorial selection of fictional walks</p><a class="button" href="${app.link("planner.html", {collection:collection.id})}">Plan this collection</a></div></div><div class="section-title"><h2>Your next little escape</h2><span>${collection.ids.length} routes</span></div><div class="grid">${collection.ids.map(id => app.card(index.get(id))).join("")}</div></section><section class="wrap section"><div class="section-title"><h2>A different kind of day?</h2></div><div class="collection-grid">${collections.filter(item => item !== collection).map(collectionCard).join("")}</div></section>`;
  } else app.main.innerHTML = `<section class="wrap section"><div class="page-intro"><p class="eyebrow">Go where your mood takes you</p><h1>Good days, gathered.</h1><p class="lede">Not sure where to start? A few thoughtful collections to help you find your way outside.</p></div><div class="collection-grid collection-directory">${collections.map(collectionCard).join("")}</div></section><section class="wrap invitation"><div><h2>A day that’s entirely yours.</h2><p>Mix a favorite trail with a little time to wander.</p></div><a class="button" href="${app.link("planner.html")}">Open day planner</a></section>`;
}
function missing(kind) {
  app.main.innerHTML = `<section class="wrap section"><h1>${kind} not found</h1><p class="lede">There’s still plenty to explore.</p><a class="button" href="${app.link("index.html")}">Back to Waymark</a></section>`;
}
export function journalPage() {
  const story = stories.find(item => item.id === params().get("id"));
  if (params().has("id") && !story) return missing("Story");
  if (!story) {
    app.main.innerHTML = `<section class="wrap section"><div class="page-intro"><p class="eyebrow">The field journal</p><h1>A few notes from outside.</h1><p class="lede">Small rituals, practical ideas, and reasons to take the scenic route. Sample editorial stories from Waymark.</p></div><div class="pill-group journal-filters" role="group" aria-label="Story categories">${["All stories", ...new Set(stories.map(item => item.category))].map((category,i) => `<button type="button" class="pill" data-category="${category}" aria-pressed="${i===0}">${category}</button>`).join("")}</div><div class="grid" id="story-results">${stories.map(storyCard).join("")}</div><p id="story-count" class="micro" role="status">3 stories</p></section>`;
    document.querySelectorAll("[data-category]").forEach(button => button.addEventListener("click", () => {
      const matches = stories.filter(item => button.dataset.category === "All stories" || item.category === button.dataset.category);
      document.querySelector("#story-results").innerHTML = matches.map(storyCard).join("");
      document.querySelector("#story-count").textContent = `${matches.length} ${matches.length === 1 ? "story" : "stories"}`;
      document.querySelectorAll("[data-category]").forEach(control => control.setAttribute("aria-pressed", String(control === button)));
    }));
    return;
  }
  document.title = `${story.title} · Waymark`;
  app.main.innerHTML = `<article class="wrap section article"><nav class="crumb" aria-label="Breadcrumb"><a href="${app.link("journal.html")}">All stories</a><span>/</span><span>${story.category}</span></nav><header class="article-heading"><p class="eyebrow">${story.category} · ${story.read} min read</p><h1>${story.title}</h1><p class="lede">${story.intro}</p><p class="micro">From the Waymark editorial desk · Sample story</p></header><img class="article-cover" src="assets/${story.image}.webp" alt="${terrains[{forest:"Forest",coast:"Coast",city:"Urban"}[story.image]].alt}"><div class="article-layout"><aside class="article-toc"><p class="eyebrow">In this story</p>${story.sections.map(([title],i) => `<a href="#chapter-${i}">${title}</a>`).join("")}<button type="button" class="button secondary" id="copy-story">Copy story link</button></aside><div class="article-body">${story.sections.map(([title,copy],i) => `<section id="chapter-${i}"><h2>${title}</h2><p>${copy}</p></section>`).join("")}<blockquote>Leave a little room for the unexpected.</blockquote><a class="button" href="${app.link("collections.html", {id:story.collection})}">Explore the collection</a></div></div></article><section class="wrap section"><div class="section-title"><h2>Keep wandering.</h2></div><div class="grid">${stories.filter(item => item!==story).map(storyCard).join("")}</div></section>`;
  document.querySelector("#copy-story").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); app.notify("Story link copied."); } catch { app.notify("Copy the address from your browser to share this story."); }
  });
}

export function detailExtras(route) {
  const section = app.main.querySelector("section");
  section.insertAdjacentHTML("beforeend", `<div class="detail-extras"><section class="trail-profile panel"><div class="section-title"><div><p class="eyebrow">A feel for the trail</p><h2>The journey, at a glance.</h2></div><a class="button" href="${app.link("planner.html", {add:route.id})}">Add to day plan</a></div><svg class="elevation" viewBox="0 0 700 180" role="img" aria-label="Illustrative elevation profile for ${route.name}"><defs><linearGradient id="elevation-fill" x2="0" y2="1"><stop stop-color="#759774" stop-opacity=".45"/><stop offset="1" stop-color="#759774" stop-opacity="0"/></linearGradient></defs><path d="M0 140 Q70 135 115 100 T240 85 T350 35 T470 80 T590 110 T700 140 V180 H0Z" fill="url(#elevation-fill)"/><path d="M0 140 Q70 135 115 100 T240 85 T350 35 T470 80 T590 110 T700 140" stroke="#37634d" stroke-width="3" fill="none"/><path d="M0 170H700" stroke="#bcc9ba"/></svg><div class="profile-labels"><span>Start · 0 mi</span><span>${route.gain} ft total gain</span><span>Finish · ${route.miles} mi</span></div><p class="micro">Illustrative profile, not surveyed elevation or navigation data.</p><div class="waypoint-buttons" role="group" aria-label="Trail stops">${route.stops.map((stop,i) => `<button type="button" class="pill" data-stop="${i}" aria-pressed="${i===0}">${stop}</button>`).join("")}</div><p id="waypoint-note" role="status"></p></section><div class="detail-lower"><section class="panel"><p class="eyebrow">Before you set off</p><h2>Good to know.</h2><div class="amenities">${["Restrooms","Water","Transit"].map(item => `<span class="amenity ${route.facilities.includes(item) ? "available" : ""}">${route.facilities.includes(item) ? "✓" : "—"} ${item}${route.facilities.includes(item) ? "" : " not listed"}</span>`).join("")}</div><p>${route.gear}</p><p class="micro">Fictional route details. Check official sources before any real outing.</p><a class="text-link" href="${app.link("guide.html")}">More planning essentials</a></section><section class="panel"><p class="eyebrow">Your trail notes</p><h2>A small memory of the day.</h2><form id="trail-note-form" class="note-form"><label>Trail note<textarea name="note" rows="3" maxlength="400" placeholder="A favorite stop, a packing reminder…"></textarea></label><button class="button secondary" type="submit">Save trail note</button><p id="trail-note-status" role="status"></p></form><p class="micro">Private to this browser. No account needed.</p></section></div><section class="review-section"><div class="section-title"><div><p class="eyebrow">Community trailbook · demo entries</p><h2>Little notes from the trail.</h2></div><button type="button" class="button secondary" id="write-review">Add a demo review</button></div><div class="review-grid" id="reviews"></div><form id="review-form" class="panel review-form" hidden><h3>Share a sample trail review</h3><p>Demo only. Your review stays in this browser.</p><label>Display name<input name="name" required maxlength="40" autocomplete="off"></label><label>Your rating<select name="rating"><option value="5">5 — Loved it</option><option value="4">4 — A good day</option><option value="3">3 — It was okay</option><option value="2">2 — Could be better</option><option value="1">1 — Not for me</option></select></label><label>Your review<textarea name="review" required rows="3" maxlength="500"></textarea></label><div class="button-row"><button class="button" type="submit">Post demo review</button><button class="button secondary" id="cancel-review" type="button">Cancel</button></div></form><p id="review-status" role="status"></p></section></div>`);
  const chooseStop = i => {
    document.querySelector("#waypoint-note").textContent = `${route.stops[i]} · ${i===0 ? "Start your walk here." : i===route.stops.length-1 ? "A good spot to pause before the return." : "Take a moment to enjoy the view along the way."}`;
    document.querySelectorAll("[data-stop]").forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.stop)===i)));
  };
  document.querySelectorAll("[data-stop]").forEach(button => button.addEventListener("click", () => chooseStop(Number(button.dataset.stop))));
  chooseStop(0);
  const noteKey = `waymark.note.${route.id}.v1`;
  const noteForm = document.querySelector("#trail-note-form");
  const note = read(noteKey, "");
  noteForm.elements.note.value = typeof note === "string" ? note.slice(0,400) : "";
  noteForm.addEventListener("submit", event => {
    event.preventDefault();
    if (write(noteKey, noteForm.elements.note.value)) document.querySelector("#trail-note-status").textContent = "Trail note saved in this browser.";
  });
  const reviewKey = `waymark.reviews.${route.id}.v1`;
  const stored = read(reviewKey, []);
  const reviews = Array.isArray(stored) ? stored.filter(item => item && typeof item.name === "string" && typeof item.review === "string" && Number.isInteger(Number(item.rating)) && Number(item.rating)>=1 && Number(item.rating)<=5).slice(0,20) : [];
  const renderReviews = () => {
    document.querySelector("#reviews").innerHTML = `<article class="review-card"><p class="stars" aria-label="5 out of 5 stars">★★★★★</p><p>“A lovely change of pace. Leave some time to stop along the way.”</p><span>Alex · Sample review</span></article><article class="review-card"><p class="stars" aria-label="4 out of 5 stars">★★★★☆</p><p>“The access notes made it easy to choose the right walk for our morning.”</p><span>Sam · Sample review</span></article>${reviews.map(item => `<article class="review-card"><p class="stars" aria-label="${Number(item.rating)} out of 5 stars">${"★".repeat(Number(item.rating))}${"☆".repeat(5-Number(item.rating))}</p><p>${escape(item.review)}</p><span>${escape(item.name)} · Your demo review</span></article>`).join("")}`;
  };
  renderReviews();
  const form = document.querySelector("#review-form");
  const toggle = open => { form.hidden = !open; document.querySelector("#write-review").setAttribute("aria-expanded", String(open)); if(open) form.elements.name.focus(); else document.querySelector("#write-review").focus(); };
  document.querySelector("#write-review").setAttribute("aria-expanded", "false");
  document.querySelector("#write-review").addEventListener("click", () => toggle(form.hidden));
  document.querySelector("#cancel-review").addEventListener("click", () => toggle(false));
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!form.elements.name.value.trim() || !form.elements.review.value.trim()) { app.notify("Add a name and review before posting."); return; }
    reviews.unshift({name:form.elements.name.value.trim(), rating:Number(form.elements.rating.value), review:form.elements.review.value.trim()});
    reviews.splice(20);
    const persisted = write(reviewKey, reviews);
    renderReviews(); form.reset(); toggle(false);
    document.querySelector("#review-status").textContent = persisted ? "Your demo review was added and saved in this browser." : "Your demo review was added for this visit.";
  });
  app.main.insertAdjacentHTML("beforeend", `<section class="wrap section"><div class="section-title"><h2>More of this kind of day.</h2><a class="text-link" href="${app.link("routes.html", {terrain:route.terrain})}">Explore ${route.terrain.toLowerCase()} routes</a></div><div class="grid">${routes.filter(item => item.terrain===route.terrain && item.id!==route.id).slice(0,3).map(item => app.card(item)).join("")}</div></section>`);
}

export function guideExtras() {
  app.main.insertAdjacentHTML("beforeend", `<section class="wrap section"><div class="section-title"><div><p class="eyebrow">A little preparation</p><h2>Pack light. Think ahead.</h2><p>A reusable checklist for your next day outside.</p></div></div><div id="guide-packing" class="panel"></div><div class="guide-principles"><article><span aria-hidden="true">♧</span><h3>Leave it as you found it</h3><p>Stay on marked paths, carry out what you bring in, and give wildlife space.</p></article><article><span aria-hidden="true">☼</span><h3>Make room for the weather</h3><p>Check official conditions, plan for changing temperatures, and know when to turn around.</p></article><article><span aria-hidden="true">⌁</span><h3>Walk at your own pace</h3><p>Choose a route that fits the day you have. A short walk still counts.</p></article></div></section>`);
  packing(document.querySelector("#guide-packing"));
}
function packing(container) {
  const raw = read("waymark.packing.v1", []);
  const checked = new Set(Array.isArray(raw) ? raw.filter(item => packingItems.includes(item)) : []);
  container.innerHTML = `<div class="section-title"><h3>The essentials</h3><span data-pack-count role="status"></span></div><div class="packing-list">${packingItems.map((item,i) => `<label class="check-item"><input type="checkbox" data-pack="${i}" ${checked.has(item) ? "checked" : ""}><span>${item}</span></label>`).join("")}</div><progress max="${packingItems.length}" value="${checked.size}" aria-label="Packing progress"></progress><button type="button" class="quiet-button" data-reset-pack>Reset checklist</button>`;
  const refresh = () => {
    container.querySelector("[data-pack-count]").textContent = `${checked.size} of ${packingItems.length} packed`;
    container.querySelector("progress").value = checked.size;
  };
  container.addEventListener("change", event => {
    const input = event.target.closest("[data-pack]"); if (!input) return;
    const item = packingItems[Number(input.dataset.pack)];
    if (input.checked) checked.add(item); else checked.delete(item);
    write("waymark.packing.v1", [...checked]); refresh();
  });
  container.querySelector("[data-reset-pack]").addEventListener("click", () => { checked.clear(); container.querySelectorAll("input").forEach(input => { input.checked=false; }); write("waymark.packing.v1", []); refresh(); });
  refresh();
}

export function plannerPage() {
  const stored = read("waymark.plan.v1", {});
  const raw = stored && typeof stored === "object" ? stored : {};
  const plan = {ids:Array.isArray(raw.ids) ? [...new Set(raw.ids.filter(id => index.has(id)))].slice(0,8) : [], date:typeof raw.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw.date) ? raw.date : "", start:typeof raw.start === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(raw.start) ? raw.start : "09:00", notes:typeof raw.notes === "string" ? raw.notes.slice(0,1000) : ""};
  const add = params().get("add");
  const collection = collections.find(item => item.id === params().get("collection"));
  if (index.has(add) && !plan.ids.includes(add) && plan.ids.length<8) plan.ids.push(add);
  if (collection) plan.ids = [...new Set([...plan.ids, ...collection.ids])].slice(0,8);
  if (add || collection) { write("waymark.plan.v1", plan); history.replaceState(null,"",app.link("planner.html")); }
  app.main.innerHTML = `<section class="wrap section"><div class="page-intro"><p class="eyebrow">A day at your own pace</p><h1>A little plan. A lot of possibility.</h1><p class="lede">Gather your favorite routes, put them in order, and make a little room for the outdoors.</p><p class="micro">Fictional routes · Walking times exclude transport and breaks · Saved only in this browser</p></div><div class="planner-layout"><div><section class="panel"><div class="section-title"><h2>Your day outside</h2><span class="eyebrow">Make it yours</span></div><div class="plan-fields"><label>Adventure date<input type="date" id="plan-date"></label><label>Start time<input type="time" id="plan-start" required></label></div><form id="add-route-form" class="add-route-form"><label>Add a route<select id="plan-route" aria-label="Add a route">${routes.map(route => `<option value="${route.id}">${route.name} · ${route.miles} mi</option>`).join("")}</select></label><button class="button" type="submit">Add route</button></form><div id="plan-stops"></div><label class="plan-notes">Day notes<textarea id="plan-notes" maxlength="1000" rows="3" placeholder="Coffee stop, meeting point, things to remember…"></textarea></label><p id="plan-status" class="micro" role="status"></p></section><section id="planner-packing" class="panel"></section></div><aside class="plan-summary panel"><p class="eyebrow">Your day in the making</p><h2>A little overview.</h2><dl id="plan-totals"></dl><p class="micro">This planner doesn’t calculate travel between trailheads. Allow time for transit, food, and a few good pauses.</p><div class="summary-actions"><button class="button" type="button" id="download-plan">Download plan</button><button class="button secondary" type="button" id="print-plan">Print plan</button><button class="quiet-button" type="button" id="clear-plan">Clear routes</button></div><a class="text-link" href="${app.link("saved.html")}">Revisit your saved routes</a></aside></div></section><dialog id="clear-plan-dialog" aria-labelledby="clear-plan-title"><h2 id="clear-plan-title">Clear your planned routes?</h2><p>Your date, notes, and packing checklist will stay.</p><form method="dialog" class="button-row"><button class="button secondary" value="cancel">Keep routes</button><button class="button" value="clear">Clear routes</button></form></dialog>`;
  const date = document.querySelector("#plan-date"); const start = document.querySelector("#plan-start"); const notes = document.querySelector("#plan-notes");
  date.value=plan.date; start.value=plan.start; notes.value=plan.notes;
  const persist = () => { const okay=write("waymark.plan.v1", plan); document.querySelector("#plan-status").textContent = okay ? "Day plan saved in this browser." : "Day plan available for this visit."; };
  const clock = minutes => `${String(Math.floor(minutes/60)%24).padStart(2,"0")}:${String(minutes%60).padStart(2,"0")}${minutes>=1440 ? ` (+${Math.floor(minutes/1440)} day)` : ""}`;
  const render = () => {
    let elapsed = Number(plan.start.slice(0,2))*60 + Number(plan.start.slice(3));
    document.querySelector("#plan-stops").innerHTML = plan.ids.length ? `<ol class="itinerary">${plan.ids.map((id,i) => {
      const route=index.get(id); const begin=elapsed; elapsed+=route.minutes;
      return `<li><span class="itinerary-time">${clock(begin)}<small>${app.timeLabel(route.minutes)} walking</small></span><div class="itinerary-route"><span class="eyebrow">${route.terrain} · ${route.difficulty}</span><h3><a href="${app.link("route.html",{id})}">${route.name}</a></h3><p>${route.miles} mi · Finish ${clock(elapsed)}</p></div><div class="reorder"><button type="button" data-move="${i}" data-direction="-1" aria-label="Move ${route.name} earlier" ${i===0 ? "disabled" : ""}>↑</button><button type="button" data-move="${i}" data-direction="1" aria-label="Move ${route.name} later" ${i===plan.ids.length-1 ? "disabled" : ""}>↓</button><button type="button" data-remove="${id}" aria-label="Remove ${route.name} from plan">×</button></div></li>`;
    }).join("")}</ol>` : `<div class="empty"><span class="empty-symbol" aria-hidden="true">⌁</span><h3>The day is yours.</h3><p>Add a route above, or find inspiration in our collections.</p><a class="text-link" href="${app.link("collections.html")}">Explore collections</a></div>`;
    const selected=plan.ids.map(id=>index.get(id));
    document.querySelector("#plan-totals").innerHTML = `<div><dt>Routes</dt><dd>${selected.length} / 8</dd></div><div><dt>Total distance</dt><dd>${selected.reduce((n,r)=>n+r.miles,0).toFixed(1)} mi</dd></div><div><dt>Walking time</dt><dd>${app.timeLabel(selected.reduce((n,r)=>n+r.minutes,0))}</dd></div><div><dt>Elevation gain</dt><dd>${selected.reduce((n,r)=>n+r.gain,0).toLocaleString()} ft</dd></div>`;
    document.querySelectorAll("#plan-route option").forEach(option => { option.disabled=plan.ids.includes(option.value); });
    if (plan.ids.includes(document.querySelector("#plan-route").value)) document.querySelector("#plan-route").value=routes.find(route=>!plan.ids.includes(route.id))?.id ?? "";
    document.querySelector("#clear-plan").disabled=!plan.ids.length;
    document.querySelector("#download-plan").disabled=!plan.ids.length;
  };
  document.querySelector("#add-route-form").addEventListener("submit", event => {
    event.preventDefault(); const id=document.querySelector("#plan-route").value;
    if(plan.ids.length>=8) return app.notify("Keep your day manageable: plan up to 8 routes.");
    if(!index.has(id) || plan.ids.includes(id)) return;
    plan.ids.push(id); render(); persist(); app.notify(`${index.get(id).name} added to your day plan.`);
  });
  document.querySelector("#plan-stops").addEventListener("click", event => {
    const move=event.target.closest("[data-move]"); const remove=event.target.closest("[data-remove]");
    if(move) { const i=Number(move.dataset.move); const target=i+Number(move.dataset.direction); if(target<0 || target>=plan.ids.length) return; [plan.ids[i],plan.ids[target]]=[plan.ids[target],plan.ids[i]]; const id=plan.ids[target]; render(); persist(); document.querySelector(`[data-remove="${id}"]`)?.focus(); }
    if(remove) { const id=remove.dataset.remove; plan.ids=plan.ids.filter(item=>item!==id); render(); persist(); document.querySelector("#plan-route").focus(); app.notify(`${index.get(id).name} removed from your day plan.`); }
  });
  for(const input of [date,start,notes]) input.addEventListener("input", () => {
    if(input===start && !start.value) { start.setCustomValidity("Choose a start time."); return; }
    start.setCustomValidity(""); plan.date=date.value; plan.start=start.value || plan.start; plan.notes=notes.value; persist(); if(input===start) render();
  });
  start.addEventListener("blur", () => { if (!start.value) { start.value=plan.start; start.setCustomValidity(""); } });
  const dialog=document.querySelector("#clear-plan-dialog");
  document.querySelector("#clear-plan").addEventListener("click",()=>dialog.showModal());
  dialog.addEventListener("close",()=> { if(dialog.returnValue==="clear") { plan.ids=[]; render(); persist(); document.querySelector("#plan-route").focus(); } });
  document.querySelector("#print-plan").addEventListener("click",()=>window.print());
  document.querySelector("#download-plan").addEventListener("click",()=> {
    const body=["WAYMARK — A day outside", "Fictional routes. Walking times exclude transport and breaks.", `Date: ${plan.date || "Flexible"} | Start: ${plan.start}`, "", ...plan.ids.map((id,i)=> {const route=index.get(id); return `${i+1}. ${route.name} — ${route.miles} mi, ${app.timeLabel(route.minutes)}, ${route.gain} ft gain\n   ${route.logistics}`;}), "", `Notes: ${plan.notes}`, "", "PACKING LIST", ...packingItems.map((item,i)=>`[${document.querySelector(`[data-pack="${i}"]`)?.checked ? "x" : " "}] ${item}`)].join("\n");
    const url=URL.createObjectURL(new Blob([body],{type:"text/plain;charset=utf-8"})); const anchor=document.createElement("a"); anchor.href=url; anchor.download="waymark-day-plan.txt"; anchor.click(); setTimeout(()=>URL.revokeObjectURL(url),1000); app.notify("Day plan downloaded.");
  });
  packing(document.querySelector("#planner-packing")); render();
}
