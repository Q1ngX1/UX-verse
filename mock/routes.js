// Fictional route data for the local test site.
export const routes = [
  {
    id: "cypress-headland", name: "Cypress Headland", area: "Marin Coast", terrain: "Coast", difficulty: "Moderate",
    miles: 4.8, minutes: 150, gain: 620, shape: "Loop", position: "50% 53%",
    teaser: "A ridge walk above the Pacific, with a sheltered overlook halfway around.",
    description: "Start on a wide gravel path that climbs through wind-shaped shrubs. Past the first saddle, the trail opens onto a long coastal ridge. The return leg descends through a protected gully before joining the original path.",
    logistics: "The signed trailhead starts at the west end of the gravel lot. The lot has 24 spaces. There is a restroom at the trailhead and no drinking water on the loop.",
    gear: "A wind shell, water, and shoes with good grip are useful here. The ridge is exposed and the lower trail can stay muddy after rain.",
    stops: ["West trailhead", "Cypress overlook", "Creek crossing"],
  },
  {
    id: "fern-creek", name: "Fern Creek Loop", area: "Santa Cruz Mountains", terrain: "Forest", difficulty: "Easy",
    miles: 2.7, minutes: 75, gain: 180, shape: "Loop", position: "50% 40%",
    teaser: "A shaded loop through redwoods with a low footbridge and a quiet creek bank.",
    description: "Follow Fern Creek upstream on an even dirt trail beneath the redwoods. Take the footbridge to the east bank for a gentle climb and a view down into the ravine. A short connector brings the path back to the picnic area.",
    logistics: "Parking is beside the picnic area. A restroom and two benches are available at the start. The footbridge is narrow, with a step at either end.",
    gear: "Bring a light layer for the cooler creek bottom. Shoes with grip help on damp roots and wooden bridge decking.",
    stops: ["Picnic area", "Lower footbridge", "Ravine viewpoint"],
  },
  {
    id: "harbor-walk", name: "East Harbor Walk", area: "East Bay", terrain: "Urban", difficulty: "Easy",
    miles: 3.2, minutes: 70, gain: 35, shape: "Out & back", position: "50% 55%",
    teaser: "An easy waterfront path, with benches, neighborhood cafés, and views across the bay.",
    description: "From the harbor plaza, stay on the paved shoreline path. The route passes a small marina and a planted promenade before reaching the public pier. Return along the water or stop in the neighborhood for lunch.",
    logistics: "The route begins two blocks from the transit stop. Accessible restrooms and a water fountain are on the plaza, and seating is available along the path.",
    gear: "Bring sun protection and a layer for the bay breeze. The path is paved and generally even.",
    stops: ["Harbor plaza", "Marina promenade", "Public pier"],
  },
  {
    id: "salt-point", name: "Salt Point Bluff", area: "Outer Coast", terrain: "Coast", difficulty: "Easy",
    miles: 2.1, minutes: 60, gain: 95, shape: "Out & back", position: "78% 48%",
    teaser: "A short, open bluff trail with a broad ocean view and very little climbing.",
    description: "A compacted dirt path follows the edge of a coastal meadow to a broad viewpoint. The bluff section is open to the wind. The viewpoint is the turnaround, with room to sit on the inland side of the trail.",
    logistics: "Use the south turnout at the start of the route. There are no restrooms or water stations. The viewpoint has an unpaved surface.",
    gear: "Pack a wind layer and water. Keep to the marked path through the meadow.",
    stops: ["South turnout", "Bluff meadow", "Ocean viewpoint"],
  },
  {
    id: "redwood-ridge", name: "Redwood Ridge", area: "Peninsula", terrain: "Forest", difficulty: "Challenging",
    miles: 7.4, minutes: 225, gain: 1450, shape: "Loop", position: "36% 62%",
    teaser: "A longer climb through redwoods, with a ridge-top clearing for a lunch break.",
    description: "Climb steadily from the creek to a spur on the ridge. A quiet stretch of singletrack links two clearings before the descent. The last mile returns through the same shaded valley.",
    logistics: "Limited parking is available at the lower gate. The upper trail has no water or restrooms. Allow extra time for the steep, uneven descent.",
    gear: "Carry water, a snack, and reliable footwear. Trekking poles can help on the steeper sections.",
    stops: ["Lower gate", "Ridge clearing", "Valley junction"],
  },
  {
    id: "canal-greenway", name: "Canal Greenway", area: "East Bay", terrain: "Urban", difficulty: "Moderate",
    miles: 5.6, minutes: 125, gain: 105, shape: "Out & back", position: "72% 55%",
    teaser: "A long, mostly flat greenway through gardens, footbridges, and residential blocks.",
    description: "Pick up the greenway beside the community garden and follow it past a series of footbridges. A short street crossing connects the two longest segments. The public garden at the far end makes a good turnaround.",
    logistics: "Start close to the neighborhood bus stop. Street parking is limited on weekend mornings. Drinking water is available in the garden at the far end.",
    gear: "Bring water and sun protection. A few exposed stretches have limited shade until late afternoon.",
    stops: ["Community garden", "Canal footbridge", "Public garden"],
  },
];

// All locations and conditions are illustrative, not navigation or live access data.
routes.push(
  {id: "golden-meadow", name: "Golden Meadow Trail", area: "North Bay", terrain: "Coast", difficulty: "Moderate", miles: 4.2, minutes: 115, gain: 410, shape: "Loop", position: "20% 65%", teaser: "Golden grasses, a gentle ridgeline, and a picnic spot facing the sea.", description: "Climb the meadow path to a grassy saddle, then follow the inland ridge to the old fence line. The return winds through a quiet hollow with distant ocean views.", logistics: "Park at the meadow gate lot. A picnic table is available at the entrance; carry all the water you need.", gear: "Bring a hat, drinking water, and a wind layer for the saddle.", stops: ["Meadow gate", "Grassy saddle", "Old fence line"]},
  {id: "oak-hollow", name: "Oak Hollow Ramble", area: "East Bay", terrain: "Forest", difficulty: "Easy", miles: 1.8, minutes: 50, gain: 90, shape: "Loop", position: "15% 80%", teaser: "An unhurried wander under oak branches, with room for a long picnic.", description: "An easy dirt path follows the edge of a leafy hollow. Stay left at the bench junction to reach the picnic clearing before looping back through the trees.", logistics: "Use the small lot at Hollow Lane. There are picnic tables and a restroom near the entrance.", gear: "A small picnic, water, and comfortable shoes are all you need for this short loop.", stops: ["Hollow Lane", "Bench junction", "Picnic clearing"]},
  {id: "lighthouse-spur", name: "Lighthouse Spur", area: "Outer Coast", terrain: "Coast", difficulty: "Moderate", miles: 3.8, minutes: 100, gain: 350, shape: "Out & back", position: "88% 30%", teaser: "Follow the headland to a lighthouse silhouette on the horizon.", description: "Walk the open headland path past two sheltered coves. A final climb reaches the lighthouse viewpoint; return by the same trail.", logistics: "Start at the headland visitor lot. Restrooms are at the start, but there is no drinking water along the spur.", gear: "Pack wind protection and water. Fog can make the return feel much cooler.", stops: ["Visitor lot", "Cove lookout", "Lighthouse viewpoint"]},
  {id: "bay-gardens", name: "Bay Gardens Promenade", area: "South Bay", terrain: "Urban", difficulty: "Easy", miles: 2.4, minutes: 55, gain: 20, shape: "Loop", position: "25% 50%", teaser: "Waterside gardens and wide paved paths for a slower kind of morning.", description: "Connect the garden terraces with the waterside promenade. The level paved route passes a café courtyard and a small public sculpture garden.", logistics: "The garden entrance is beside the tram stop. Accessible restrooms, drinking water, and benches are available in the courtyard.", gear: "Take sun protection and a reusable bottle. A light layer is useful by the water.", stops: ["Garden entrance", "Café courtyard", "Sculpture garden"]},
  {id: "misty-canyon", name: "Misty Canyon Path", area: "Peninsula", terrain: "Forest", difficulty: "Moderate", miles: 4.6, minutes: 140, gain: 670, shape: "Out & back", position: "80% 30%", teaser: "A cool canyon walk beside mossy rocks and a seasonal stream.", description: "The trail enters the canyon on a gentle grade before becoming narrower near the stream. At the stone terrace, pause for a snack and return the way you came.", logistics: "Use the canyon entrance pullout. There are no facilities; the last section has steps and uneven stones.", gear: "Choose shoes with grip and carry a light layer for the canyon shade.", stops: ["Canyon entrance", "Mossy crossing", "Stone terrace"]},
  {id: "summit-traverse", name: "Highland Summit Traverse", area: "North Bay", terrain: "Coast", difficulty: "Challenging", miles: 8.6, minutes: 285, gain: 1820, shape: "Loop", position: "10% 35%", teaser: "An all-morning ridge adventure with wide views and a rewarding climb.", description: "A sustained climb reaches the first ridge. Follow the undulating traverse to the summit cairn, then descend the inland switchbacks to the original trailhead.", logistics: "Park at Highland trailhead. A restroom is at the start. The route is exposed and has no water refill points.", gear: "Carry plenty of water, lunch, a warm layer, and sturdy footwear.", stops: ["Highland trailhead", "Ridge junction", "Summit cairn"]},
  {id: "willow-lake", name: "Willow Lake Circuit", area: "East Bay", terrain: "Forest", difficulty: "Easy", miles: 3.1, minutes: 85, gain: 140, shape: "Loop", position: "60% 75%", teaser: "A lakeside circuit with birdwatching corners and willow shade.", description: "Follow the wide path clockwise around the lake. Boardwalks connect the softer sections on the northern shore, and a bird hide offers a quiet midway stop.", logistics: "Park beside the lakeside kiosk. Restrooms and drinking water are near the picnic lawn. Boardwalks can be slippery after rain.", gear: "Bring binoculars, water, and shoes with grip for the boardwalk.", stops: ["Lakeside kiosk", "North boardwalk", "Bird hide"]},
  {id: "ferry-point", name: "Ferry Point Stroll", area: "East Bay", terrain: "Urban", difficulty: "Easy", miles: 1.5, minutes: 40, gain: 15, shape: "Out & back", position: "80% 70%", teaser: "A pocket-sized escape between the ferry landing and the old pier.", description: "From the ferry landing, follow the level promenade to the old pier. Watch the boats from a bench before returning past the waterfront cafés.", logistics: "Begin at the ferry landing. Accessible restrooms and drinking water are beside the transit plaza.", gear: "A wind layer is useful on the pier. The paved promenade has plenty of benches.", stops: ["Ferry landing", "Waterfront cafés", "Old pier"]},
  {id: "pine-switchbacks", name: "Pine Switchback Trail", area: "Santa Cruz Mountains", terrain: "Forest", difficulty: "Challenging", miles: 6.3, minutes: 210, gain: 1260, shape: "Loop", position: "30% 20%", teaser: "A steady climb through pines to a quiet ridge above the canopy.", description: "Climb a sequence of shaded switchbacks to Pine Ridge. The return follows a narrow old logging track before rejoining the trail beside the lower creek.", logistics: "Use the lower creek lot. No facilities are available on the route, and the ridge track is narrow.", gear: "Bring water, snacks, and grippy shoes. Walking poles may help on the descent.", stops: ["Lower creek lot", "Pine Ridge", "Old logging track"]},
);

const points = [[26,43],[42,77],[71,37],[17,22],[49,61],[77,49],[30,30],[74,61],[22,56],[62,83],[46,51],[36,20],[69,53],[84,42],[51,86]];
for (const [i, route] of routes.entries()) {
  route.point = points[i];
  route.facilities = ["Restrooms", "Water", "Transit"].filter((facility) => {
    const text = route.logistics.toLowerCase();
    if (facility === "Transit") return /transit|tram|ferry|bus stop/.test(text);
    if (facility === "Water") return /drinking water|water fountain/.test(text) && !/no drinking|no water/.test(text);
    return /restroom/.test(text) && !/no restrooms|no water or restrooms/.test(text);
  });
  route.tags = [route.minutes <= 90 ? "Short escape" : "Slow adventure", route.terrain === "Forest" ? "Find some shade" : route.terrain === "Coast" ? "Ocean air" : "Car-free friendly"];
}

export const terrains = {
  Coast: {image: "assets/coast.webp", alt: "A trail above the Pacific Ocean", copy: "Bluffs, beaches, and open headlands."},
  Forest: {image: "assets/forest.webp", alt: "A shaded trail among coastal redwoods", copy: "Cool ravines and redwood canopies."},
  Urban: {image: "assets/city.webp", alt: "A paved path along the bay", copy: "Waterfront paths and neighborhood greenways."},
};
