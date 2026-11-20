// Michaelmas presentation mockup (first draft, 19 Nov 2026).
//   node scripts/make_slides.js        (needs pptxgenjs: npm install pptxgenjs)
// Figures come from scripts/slide_figures.py. Hui has since edited the deck by hand
// (outputs/slides/presentation_mockup_hui.pptx: new slide order and notes), so treat that
// file as the latest version and this script as the starting layout.
const path = require("path");
const pptxgen = require("pptxgenjs");

const FIG = path.join(__dirname, "..", "outputs", "slides") + "/";
const OUT = FIG + "presentation_mockup.pptx";

const DARK = "2D3142", MUTED = "6B7280", PURPLE = "A88BD4", DEEP = "4B2A8A", BLUE = "5B9BD5",
  GREEN = "7DC383", YELLOW = "F2C14E", GREY = "9AA0A6", TINT = "F4F2FA", LINE = "D9DCE1";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                 // 13.33 x 7.5 in
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };
pres.title = "Alternative-Fuel Fleet Transition: An Airline Network Perspective";
pres.author = "Hui Lin Chew";

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.9,
        fontSize: 30, bold: true, color: DARK, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: MUTED, align: "right" },
});
pres.defineSlideMaster({ title: "TITLE", background: { color: "FFFFFF" } });

// Picture that keeps its shape, centred in a box
function figure(slide, file, aspect, x, y, w, h) {
  let fw = w, fh = w / aspect;
  if (fh > h) { fh = h; fw = h * aspect; }
  slide.addImage({ path: FIG + file, x: x + (w - fw) / 2, y: y + (h - fh) / 2, w: fw, h: fh });
}
function caption(slide, text) {
  slide.addText(text, { x: 0.6, y: 6.85, w: 11.4, h: 0.35, fontSize: 11, color: MUTED, italic: true,
    margin: 0, isTextBox: true });
}
function content(section, title) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}

// ---------- 1. Title ----------
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
s.addText("How should an airline move its fleet from kerosene to hydrogen and LNG?", {
  x: 0.6, y: 1.6, w: 5.6, h: 2.6, fontSize: 36, bold: true, color: DARK, valign: "top", margin: 0, isTextBox: true });
s.addText("Alternative-Fuel Fleet Transition: An Airline Network Perspective", {
  x: 0.6, y: 4.4, w: 5.6, h: 0.6, fontSize: 16, color: DEEP, margin: 0, isTextBox: true });
s.addText([
  { text: "Hui Lin Chew", options: { bold: true, breakLine: true } },
  { text: "Supervisor: Dr Maria Vera-Morales · Whittle Laboratory", options: { breakLine: true } },
  { text: "Michaelmas 2026" },
], { x: 0.6, y: 5.3, w: 5.6, h: 1.1, fontSize: 14, color: MUTED, margin: 0, isTextBox: true });
figure(s, "1_ryanair_network.png", 1.396, 6.5, 0.6, 6.4, 6.3);
s.addText("Ryanair, 14 Sep 2022: 2,355 flights, 200 airports", { x: 6.5, y: 6.95, w: 6.4, h: 0.3,
  fontSize: 11, color: MUTED, italic: true, align: "center", margin: 0, isTextBox: true });
s.addNotes("Open with the question. The map is one real day of Ryanair, which the model now runs on.");

// ---------- 2. What am I trying to do ----------
s = content("Introduction", "What am I trying to do?");
const fuels = [["Kerosene", "today", GREY], ["LNG", "liquefied natural gas", GREEN], ["LH₂", "liquid hydrogen", BLUE]];
fuels.forEach(([name, sub, colour], i) => {
  const x = 1.4 + i * 3.9;
  s.addShape(pres.shapes.OVAL, { x, y: 1.9, w: 2.2, h: 2.2, fill: { color: colour }, line: { color: colour } });
  s.addText(name, { x, y: 1.9, w: 2.2, h: 2.2, fontSize: 26, bold: true, color: "FFFFFF", align: "center",
    valign: "middle", margin: 0, isTextBox: true });
  s.addText(sub, { x: x - 0.4, y: 4.25, w: 3.0, h: 0.4, fontSize: 14, color: MUTED, align: "center",
    margin: 0, isTextBox: true });
  if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.55, y: 2.75, w: 1.0, h: 0.5,
    fill: { color: LINE }, line: { color: LINE } });
});
s.addText("Which flights switch fuel, when, and what does it change for the airline?", {
  x: 0.6, y: 5.2, w: 12.1, h: 0.8, fontSize: 24, bold: true, color: DEEP, align: "center", margin: 0, isTextBox: true });
s.addNotes("Heilmeier 1: airlines must cut CO2; new aircraft burn LNG or hydrogen. I want to know which of an airline's flights should switch, at what carbon price, and what that does to how the airline runs.");

// ---------- 3. How is it done today, what is new ----------
s = content("Introduction", "How is it done today, and what is missing?");
const views = [
  ["Aircraft and airports", "Hydrogen and LNG aircraft designs; fuel supply and refuelling at airports",
   "Rompokos; Proesmans; FlyZero; Hoelzen; Mangold; Al-Timimi; Sanford", TINT, DARK, MUTED],
  ["One airline, one year", "Which routes or flights new aircraft should fly, for a fixed fleet",
   "Kamat; Justin; Wu; Sirtori; Akinola", TINT, DARK, MUTED],
  ["Whole industry, year by year", "Fleets retire and are replaced to 2050, as averages per route",
   "Dray (AIM); Rau; Peter; Raab", TINT, DARK, MUTED],
  ["One airline, year by year", "Real timetable and turns, fuel at each airport, as the fleet turns over",
   "This project", PURPLE, "FFFFFF", "FFFFFF"],
];
views.forEach(([head, body, refs, fill, text, refColour], i) => {
  const x = 0.6 + i * 3.08;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.7, w: 2.85, h: 3.6, rectRadius: 0.12,
    fill: { color: fill }, line: { color: fill } });
  s.addText(head, { x: x + 0.25, y: 1.9, w: 2.35, h: 0.9, fontSize: 19, bold: true, color: text, valign: "top", margin: 0, isTextBox: true });
  s.addText(body, { x: x + 0.25, y: 2.9, w: 2.35, h: 1.5, fontSize: 15, color: text, valign: "top", margin: 0, isTextBox: true });
  s.addText(refs, { x: x + 0.25, y: 4.45, w: 2.35, h: 0.7, fontSize: 11, italic: true, color: refColour, valign: "bottom", margin: 0, isTextBox: true });
});
s.addText("Existing work: snapshots of one airline, or fleet change as industry averages", { x: 0.6, y: 5.5, w: 8.95, h: 0.4,
  fontSize: 14, color: MUTED, align: "center", margin: 0, isTextBox: true });
s.addText("The gap", { x: 9.84, y: 5.5, w: 2.85, h: 0.4, fontSize: 14, bold: true, color: DEEP, align: "center", margin: 0, isTextBox: true });
s.addNotes("Heilmeier 2 and 3. Airline-level studies (Kamat: American Airlines; Wu: hydrogen with carbon tax; Sirtori: hydrogen sub-fleet, no flight sequence or times) look at one year. Fleet-turnover models (Dray's AIM, Rau, Peter) go year by year but work on route averages, with no timetable, turns or fuel at each airport. New here: both at once, one airline's real timetable, year by year.");

// ---------- 4. The project in three parts ----------
pres.addSection({ title: "Method" });
s = content("Method", "The project in three parts");
const parts = [
  ["1  Data", "Real airline timetables, airports, aircraft and fuels", BLUE, "Done: Ryanair, Sep 2022"],
  ["2  Optimiser", "Which aircraft and fuel flies each flight, and when it leaves", GREEN, "Done: fuels, turns, re-timing"],
  ["3  Fleet over time", "Buying and retiring aircraft year by year", YELLOW, "Lent and Easter"],
];
parts.forEach(([head, body, colour, status], i) => {
  const x = 0.6 + i * 4.15;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.9, w: 3.6, h: 2.8, rectRadius: 0.12,
    fill: { color: colour }, line: { color: colour } });
  s.addText(head, { x: x + 0.3, y: 2.15, w: 3.0, h: 0.6, fontSize: 24, bold: true, color: DARK, margin: 0, isTextBox: true });
  s.addText(body, { x: x + 0.3, y: 2.9, w: 3.0, h: 1.6, fontSize: 16, color: DARK, valign: "top", margin: 0, isTextBox: true });
  s.addText(status, { x, y: 4.85, w: 3.6, h: 0.4, fontSize: 14, italic: true, color: MUTED, align: "center", margin: 0, isTextBox: true });
  if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 3.7, y: 3.1, w: 0.35, h: 0.4,
    fill: { color: LINE }, line: { color: LINE } });
});
s.addText("This term: parts 1 and 2", { x: 0.6, y: 5.7, w: 12.1, h: 0.5, fontSize: 20, bold: true, color: DEEP,
  align: "center", margin: 0, isTextBox: true });
s.addNotes("Whole project: clean real data, an optimiser that assigns aircraft and fuels, then a fleet model that moves year by year. This term covers the first two.");

// ---------- 5. What the code does ----------
s = content("Method", "What the model does today");
const steps = [
  ["Inputs", "timetable\nairports and fuels sold\naircraft\nfuel prices", TINT],
  ["Can it fly?", "range\nfuel at the airport\nenough seats\nturn time", "DCE9F6"],
  ["Costs", "fuel and carbon\ncrew, maintenance\nowning the aircraft", "DCE9F6"],
  ["Optimiser", "cheapest way to\nfly every flight", "DFF0DC"],
  ["Outputs", "fuel mix\nCO₂ and cost\neach aircraft's day", "FCEFC9"],
];
steps.forEach(([head, body, fill], i) => {
  const x = 0.6 + i * 2.5;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.9, w: 2.1, h: 2.8, rectRadius: 0.1,
    fill: { color: fill }, line: { color: fill } });
  s.addText(head, { x: x + 0.15, y: 2.1, w: 1.8, h: 0.5, fontSize: 18, bold: true, color: DARK, align: "center", margin: 0, isTextBox: true });
  s.addText(body, { x: x + 0.15, y: 2.8, w: 1.8, h: 1.7, fontSize: 14, color: DARK, align: "center", valign: "top", margin: 0, isTextBox: true });
  if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.13, y: 3.12, w: 0.34, h: 0.36,
    fill: { color: LINE }, line: { color: LINE } });
});
s.addText("Python · PuLP + HiGHS solver · about 2,400 real flights solved in seconds", {
  x: 0.6, y: 5.2, w: 12.1, h: 0.4, fontSize: 14, color: MUTED, align: "center", margin: 0, isTextBox: true });
s.addNotes("One pass per scenario. Feasibility removes options (out of range, no fuel, curfew); costs price the rest; the optimiser chooses.");

// ---------- 6. Time-space network + MILP ----------
s = content("Method", "Flights and aircraft as a network");
figure(s, "6_time_space_network.png", 2.133, 0.6, 1.5, 7.4, 4.9);
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.3, y: 1.6, w: 4.4, h: 4.7, rectRadius: 0.1,
  fill: { color: TINT }, line: { color: TINT } });
s.addText([
  { text: "Choose which aircraft type flies each flight", options: { bold: true, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "minimise   Σ cost × flights + Σ ownership × aircraft", options: { breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "such that", options: { italic: true, breakLine: true } },
  { text: "every flight is flown once", options: { bullet: true, breakLine: true } },
  { text: "aircraft in = aircraft out, at every airport and time", options: { bullet: true, breakLine: true } },
  { text: "aircraft used ≤ fleet", options: { bullet: true, breakLine: true } },
  { text: "nights at a base", options: { bullet: true } },
], { x: 8.55, y: 1.85, w: 3.95, h: 4.2, fontSize: 15, color: DARK, valign: "top", margin: 0,
  paraSpaceAfter: 4, isTextBox: true });
caption(s, "Fleet assignment on a time-space network (Hane et al. 1995); a mixed-integer linear program");
s.addNotes("Each airport is a timeline. Flights are arcs between timelines, aircraft wait along them. A type that can't fly a flight has no arc, so range, fuel and seats need no extra constraints.");

// ---------- 7. Validation ----------
pres.addSection({ title: "Results" });
s = content("Results", "Given Ryanair's flights, the model needs the same aircraft");
figure(s, "1_ryanair_network.png", 1.396, 0.6, 1.4, 5.3, 4.6);
figure(s, "backup_aircraft_per_base.png", 1.016, 6.1, 1.4, 4.0, 4.6);
const stats = [
  ["406 → 402", "aircraft needed, Ryanair → model (1 day)"],
  ["231 → 231", "over 4 days"],
  ["100%", "same next flight as Ryanair wherever only one aircraft was on the ground"],
];
stats.forEach(([big, small], i) => {
  const y = 1.6 + i * 1.5;
  s.addText(big, { x: 10.35, y, w: 2.4, h: 0.6, fontSize: 30, bold: true, color: DEEP, margin: 0, isTextBox: true });
  s.addText(small, { x: 10.35, y: y + 0.6, w: 2.4, h: 0.8, fontSize: 13, color: DARK, valign: "top", margin: 0, isTextBox: true });
});
caption(s, "OpenSky flight data, 14–17 Sep 2022 · 1 day: 406 of ~500 Ryanair aircraft (81%) whose whole day was tracked · each dot one base");
s.addNotes("Left: the real network we fed in. Middle: aircraft based at each airport, Ryanair vs model; every base sits on the line. 406 vs 402 aircraft for one day, an exact 231 vs 231 over four days. Where only one aircraft was on the ground the choice is forced, and the model makes the same one every time.");

// ---------- 8. Fuel mix ----------
s = content("Results", "At 200 $/t, LNG and LH₂ take 30% of flights");
figure(s, "8_fuel_mix.png", 2.212, 0.6, 1.5, 7.6, 4.9);
figure(s, "8_routes_by_fuel.png", 0.936, 8.5, 1.4, 4.2, 5.2);
caption(s, "5-airport test network · LH₂ at LHR, MAD · LNG at LHR, MAD, CDG · LH₂ 2.5 $/kg (2050) · map at 200 $/t");
s.addNotes("LNG first from 25 $/t; LH2 from 200 $/t on Madrid–London, the longest route with hydrogen at both ends. Kerosene keeps 70%: routes touching Dublin or Amsterdam have no new fuel to fly home on.");

// ---------- 9. Turnaround ----------
s = content("Results", "Longer refuelling locks new fuels out of a tight timetable");
figure(s, "9_retiming.png", 2.82, 0.6, 1.5, 12.1, 4.6);
caption(s, "Tight low-cost timetable (25-min turns) · 200 $/t · LH₂ at LHR, MAD · LNG at LHR, MAD, CDG");
s.addNotes("Same fuel airports as the last slide, but on a tight low-cost timetable. Only about 10% of flights have new fuel at both ends. If hydrogen and LNG can't refuel with passengers aboard (Al-Timimi's safety zone), turns get about 12 minutes longer and even those 10% are shut out. Letting departures move 20 minutes later lets them back in; at 60 minutes aircraft can be rearranged so 19% switch. On the looser out-and-back timetable the rule makes no difference.");

// ---------- 10. Who cares ----------
pres.addSection({ title: "Conclusions" });
s = content("Conclusions", "Who cares?");
const who = [
  ["Airlines", "Which aircraft to buy, and for which routes"],
  ["Airports", "Where new fuel is needed first"],
  ["Policymakers", "What carbon price makes the switch happen"],
];
who.forEach(([head, body], i) => {
  const y = 1.8 + i * 1.35;
  s.addShape(pres.shapes.OVAL, { x: 0.8, y, w: 0.9, h: 0.9, fill: { color: [BLUE, GREEN, YELLOW][i] },
    line: { color: [BLUE, GREEN, YELLOW][i] } });
  s.addText(head, { x: 2.0, y: y + 0.02, w: 4.5, h: 0.45, fontSize: 20, bold: true, color: DARK, margin: 0, isTextBox: true });
  s.addText(body, { x: 2.0, y: y + 0.47, w: 4.5, h: 0.4, fontSize: 16, color: MUTED, margin: 0, isTextBox: true });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.0, y: 1.8, w: 5.7, h: 3.9, rectRadius: 0.1,
  fill: { color: TINT }, line: { color: TINT } });
s.addText([
  { text: "So far", options: { bold: true, fontSize: 20, color: DEEP, breakLine: true } },
  { text: "The model reproduces how Ryanair uses its aircraft", options: { bullet: true, breakLine: true } },
  { text: "New fuels win first on long routes with fuel at both ends", options: { bullet: true, breakLine: true } },
  { text: "Turnaround rules can matter as much as fuel price", options: { bullet: true } },
], { x: 7.3, y: 2.05, w: 5.1, h: 3.4, fontSize: 17, color: DARK, valign: "top", margin: 0, paraSpaceAfter: 10, isTextBox: true });
s.addNotes("Heilmeier 4.");

// ---------- 11. Plan ----------
s = content("Conclusions", "Plan to the end of the year");
const months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];
const x0 = 4.6, mw = 0.9, top = 1.7, rowH = 0.6;
months.forEach((m, i) => {
  s.addText(m, { x: x0 + i * mw, y: top, w: mw, h: 0.35, fontSize: 13, color: MUTED, align: "center", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.LINE, { x: x0 + i * mw, y: top + 0.4, w: 0, h: 7 * rowH + 0.1, line: { color: LINE, width: 0.75 } });
});
s.addShape(pres.shapes.LINE, { x: x0 + 9 * mw, y: top + 0.4, w: 0, h: 7 * rowH + 0.1, line: { color: LINE, width: 0.75 } });
const tasks = [
  ["Network model, fuels, turnarounds", 0, 2.5],
  ["Ryanair data and validation", 1.5, 1.1],
  ["Industry input (Emirates), newer data", 2.5, 1.2],
  ["Fuels on the Ryanair network", 3.2, 1.6],
  ["Model plans the timetable for a given fleet", 3.8, 2.2],
  ["Fleet over time (year by year)", 5.0, 2.6],
  ["Write-up", 7.0, 1.8],
];
tasks.forEach(([name, start, len], r) => {
  const y = top + 0.55 + r * rowH;
  s.addText(name, { x: 0.6, y, w: 3.8, h: 0.4, fontSize: 14, color: DARK, align: "right", valign: "middle", margin: 0, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x0 + start * mw, y: y + 0.05, w: len * mw, h: 0.3, rectRadius: 0.05,
    fill: { color: BLUE }, line: { color: BLUE } });
});
[[1.6, "today"], [3.4, "TMR (week 0)"]].forEach(([at, label]) => {
  s.addShape(pres.shapes.LINE, { x: x0 + at * mw, y: top + 0.4, w: 0, h: 7 * rowH + 0.1,
    line: { color: DARK, width: 1.25, dashType: "dash" } });
  s.addText(label, { x: x0 + at * mw - 0.8, y: top + 0.55 + 7 * rowH, w: 1.6, h: 0.35, fontSize: 12,
    color: DARK, align: "center", margin: 0, isTextBox: true });
});
s.addNotes("Christmas: meet Anil (Emirates) on how airlines plan; pull 2025 data. Lent: fuels on the Ryanair network, then fleet in, schedule out. Easter: fleet over time.");

// ---------- Backup ----------
pres.addSection({ title: "Backup" });
s = content("Backup", "Backup: cost of cutting CO₂");
figure(s, "backup_cost_vs_co2.png", 1.52, 0.6, 1.5, 7.6, 5.0);
s.addText("Each point is one carbon price. Cost of flying excludes the carbon charge itself.", {
  x: 8.6, y: 2.5, w: 4.1, h: 1.5, fontSize: 16, color: DARK, valign: "top", margin: 0, isTextBox: true });
caption(s, "Same test network and assumptions as the fuel-mix slide");

s = content("Backup", "Backup: aircraft per base, Ryanair vs model");
figure(s, "backup_aircraft_per_base.png", 1.016, 0.6, 1.4, 5.4, 5.3);
s.addText([
  { text: "How the Ryanair data was cleaned", options: { bold: true, breakLine: true } },
  { text: "Missing airports from where the aircraft was seen", options: { bullet: true, breakLine: true } },
  { text: "An aircraft lands where it next takes off (99% agreement)", options: { bullet: true, breakLine: true } },
  { text: "Gate times = tracked times + climb and taxi", options: { bullet: true, breakLine: true } },
  { text: "Only aircraft whose whole day is known", options: { bullet: true, breakLine: true } },
  { text: "189 seats × 94% load factor; 25-min turns", options: { bullet: true } },
], { x: 6.6, y: 1.8, w: 6.1, h: 4.4, fontSize: 16, color: DARK, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true });

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT));
