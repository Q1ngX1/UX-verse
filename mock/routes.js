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

export const terrains = {
  Coast: {image: "assets/coast.webp", alt: "A trail above the Pacific Ocean", copy: "Bluffs, beaches, and open headlands."},
  Forest: {image: "assets/forest.webp", alt: "A shaded trail among coastal redwoods", copy: "Cool ravines and redwood canopies."},
  Urban: {image: "assets/city.webp", alt: "A paved path along the bay", copy: "Waterfront paths and neighborhood greenways."},
};
