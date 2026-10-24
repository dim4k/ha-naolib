import { describe, expect, it } from "vitest";
import { normalizeAroundConfig, prepareStops } from "../../src/around/config.js";
import {
    noStopsMessage,
    notLocatedMessage,
    renderAround,
} from "../../src/around/render.js";
import { firstLocatable, isLocatable } from "../../src/entities.js";
import { aroundSuggestion } from "../../src/suggestions.js";

const NOW = Date.parse("2026-10-14T18:00:00+02:00");
const at = (minutes) => new Date(NOW + minutes * 60000).toISOString();

const STOPS = [
    {
        code: "S1",
        name: "Commerce",
        distance: 42,
        departures: [
            { line: "1", destination: "Mitterrand", expected_ts: at(-0.5) },
            { line: "1", destination: "Mitterrand", expected_ts: at(2) },
            { line: "C2", destination: "Gare Sud", expected_ts: at(5) },
            { line: "1", destination: "Mitterrand", expected_ts: at(7) },
            { line: "1", destination: "Mitterrand", expected_ts: at(15) },
            { line: "1", destination: "Mitterrand", expected_ts: at(25) },
            { line: "1", destination: "Jamet", expected_ts: at(4) },
            { line: "2", destination: "Orvault", expected_ts: at(9) },
            { line: "3", destination: "Neustrie", expected_ts: at(12) },
        ],
    },
    { code: "S2", name: "Bouffay", distance: 300, departures: [] },
];

const located = { attributes: { latitude: 47.2, longitude: -1.5 } };
const HASS = {
    states: {
        "device_tracker.phone": located,
        "person.me": located,
        "zone.home": located,
        "person.unknown": { attributes: {} },
        "sensor.gps": located,
    },
};

describe("normalizeAroundConfig", () => {
    it("fills the defaults", () => {
        expect(normalizeAroundConfig({ entity: "person.me" })).toMatchObject({
            entity: "person.me",
            radius: 500,
            max_stops: 5,
            departures: 3,
            compact: false,
        });
    });

    it("rejects out-of-range values", () => {
        expect(() => normalizeAroundConfig({ radius: 50 })).toThrow(/radius/);
        expect(() => normalizeAroundConfig({ max_stops: 0 })).toThrow(/max_stops/);
        expect(() => normalizeAroundConfig({ departures: 99 })).toThrow(/departures/);
    });
});

describe("prepareStops", () => {
    const config = normalizeAroundConfig({});

    it("groups the departures by line and terminus, soonest first", () => {
        const stops = prepareStops(STOPS, config, NOW);
        expect(stops.map((stop) => stop.name)).toEqual(["Commerce", "Bouffay"]);
        expect(
            stops[0].directions.map((d) => `${d.line} ${d.destination}`),
        ).toEqual(["1 Mitterrand", "1 Jamet", "C2 Gare Sud", "2 Orvault", "3 Neustrie"]);
        expect(stops[1].directions).toEqual([]);
    });

    it("keeps the next passages of each direction, dropping the gone ones", () => {
        const [stop] = prepareStops(STOPS, config, NOW);
        expect(stop.directions[0].seconds).toEqual([120, 420, 900]);
        const [two] = prepareStops(STOPS, normalizeAroundConfig({ departures: 2 }), NOW);
        expect(two.directions[0].seconds).toEqual([120, 420]);
    });

    it("copes with nothing", () => {
        expect(prepareStops(undefined, config, NOW)).toEqual([]);
    });
});

describe("rendering", () => {
    it("lists each stop with its distance and departures", () => {
        const html = renderAround(prepareStops(STOPS, normalizeAroundConfig({}), NOW));
        expect(html).toContain("Commerce");
        expect(html).toContain("42 m");
        expect(html).toContain("Gare Sud");
        expect(html).toContain("2 mn");
        expect(html).toContain("Aucun passage prévu");
    });

    it("puts the passages of a direction side by side, soonest first", () => {
        const html = renderAround(prepareStops(STOPS, normalizeAroundConfig({}), NOW));
        const row = html.slice(html.indexOf("Mitterrand"), html.indexOf("Jamet"));
        expect(row).toContain('class="around-times"');
        expect(row.indexOf("2 mn")).toBeLessThan(row.indexOf("7 mn"));
        expect(row.indexOf("7 mn")).toBeLessThan(row.indexOf("15 mn"));
        expect(row).not.toContain("25 mn");
    });

    it("explains an unknown position or no stop around", () => {
        expect(notLocatedMessage("<Paul>")).toContain("&lt;Paul&gt;");
        expect(noStopsMessage("Paul", 500)).toContain("500 m");
    });
});

describe("locatable entities", () => {
    it("accepts persons, zones and trackers with coordinates", () => {
        expect(isLocatable("device_tracker.phone", located)).toBe(true);
        expect(isLocatable("zone.home", located)).toBe(true);
        expect(isLocatable("person.unknown", HASS.states["person.unknown"])).toBe(false);
        expect(isLocatable("sensor.gps", located)).toBe(false);
    });

    it("prefers a person for a new card", () => {
        expect(firstLocatable(HASS)).toBe("person.me");
        expect(firstLocatable({ states: {} })).toBeUndefined();
    });

    it("suggests the card for a located entity only", () => {
        expect(aroundSuggestion(HASS, "device_tracker.phone")).toEqual([
            {
                label: "Arrêts à proximité",
                config: { type: "custom:naolib-around-card", entity: "device_tracker.phone" },
            },
        ]);
        expect(aroundSuggestion(HASS, "person.unknown")).toEqual([]);
        expect(aroundSuggestion(HASS, "sensor.gps")).toEqual([]);
    });
});
