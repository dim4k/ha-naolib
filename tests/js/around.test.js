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

    it("keeps the order and the next departures, dropping the gone ones", () => {
        const stops = prepareStops(STOPS, config, NOW);
        expect(stops.map((stop) => stop.name)).toEqual(["Commerce", "Bouffay"]);
        expect(stops[0].departures.map((d) => d.line)).toEqual(["1", "C2", "2"]);
        expect(stops[0].departures[0].seconds).toBe(120);
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
