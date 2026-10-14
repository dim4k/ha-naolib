import { describe, expect, it } from "vitest";
import { normalizeAroundConfig, prepareStops } from "../../src/around/config.js";
import { renderAround } from "../../src/around/render.js";
import { aroundSensors, aroundSources } from "../../src/entities.js";
import { aroundSuggestion } from "../../src/suggestions.js";

const NOW = Date.parse("2026-10-14T18:00:00+02:00");
const at = (minutes) => new Date(NOW + minutes * 60000).toISOString();

function sensor(entityId, name, distance, departures, source = "person.me") {
    return {
        entity_id: entityId,
        last_updated: "x",
        attributes: {
            stop_code: entityId,
            stop_label: name,
            around_source: source,
            distance,
            next_departures: departures,
        },
    };
}

const FAR = sensor("sensor.bouffay", "Bouffay", 300, [
    { line: "C3", destination: "Hôtel Dieu", expected_ts: at(4) },
]);
const NEAR = sensor("sensor.commerce", "Commerce", 42, [
    { line: "1", destination: "Mitterrand", expected_ts: at(-5) },
    { line: "1", destination: "Mitterrand", expected_ts: at(2) },
    { line: "C2", destination: "Gare Sud", expected_ts: at(5) },
    { line: "2", destination: "Orvault", expected_ts: at(9) },
    { line: "3", destination: "Neustrie", expected_ts: at(12) },
]);
const OTHER = sensor("sensor.ailleurs", "Ailleurs", 10, [], "person.other");
const HASS = {
    states: {
        "sensor.bouffay": FAR,
        "sensor.commerce": NEAR,
        "sensor.ailleurs": OTHER,
        "sensor.fixed": { attributes: { stop_code: "X", next_departures: [] } },
    },
};

describe("normalizeAroundConfig", () => {
    it("fills the defaults", () => {
        expect(normalizeAroundConfig({ entity: "person.me" })).toMatchObject({
            entity: "person.me",
            departures: 3,
            max_stops: 0,
            compact: false,
        });
    });

    it("rejects out-of-range values", () => {
        expect(() => normalizeAroundConfig({ departures: 0 })).toThrow(/departures/);
        expect(() => normalizeAroundConfig({ max_stops: 99 })).toThrow(/max_stops/);
    });
});

describe("prepareStops", () => {
    const config = normalizeAroundConfig({});

    it("sorts by distance and keeps the next departures", () => {
        const stops = prepareStops([FAR, NEAR], config, NOW);
        expect(stops.map((stop) => stop.name)).toEqual(["Commerce", "Bouffay"]);
        expect(stops[0].departures.map((d) => d.line)).toEqual(["1", "C2", "2"]);
        expect(stops[0].departures[0].seconds).toBe(120);
    });

    it("drops the departures already gone", () => {
        const gone = sensor("sensor.parti", "Parti", 1, [
            { line: "1", destination: "Passé", expected_ts: at(-0.5) },
            { line: "1", destination: "Futur", expected_ts: at(1) },
        ]);
        const [stop] = prepareStops([gone], config, NOW);
        expect(stop.departures.map((d) => d.destination)).toEqual(["Futur"]);
    });

    it("caps the number of stops", () => {
        const stops = prepareStops([FAR, NEAR], { ...config, max_stops: 1 }, NOW);
        expect(stops).toHaveLength(1);
    });
});

describe("renderAround", () => {
    it("lists each stop with its distance and departures", () => {
        const html = renderAround(prepareStops([NEAR], normalizeAroundConfig({}), NOW));
        expect(html).toContain("Commerce");
        expect(html).toContain("42 m");
        expect(html).toContain("Gare Sud");
        expect(html).toContain("2 mn");
    });

    it("says when a stop has nothing coming", () => {
        const empty = sensor("sensor.vide", "Vide", 5, []);
        expect(renderAround(prepareStops([empty], normalizeAroundConfig({}), NOW))).toContain(
            "Aucun passage prévu",
        );
    });
});

describe("around sources", () => {
    it("finds the followed entities and their sensors", () => {
        expect(aroundSources(HASS)).toEqual(["person.me", "person.other"]);
        expect(aroundSensors(HASS, "person.me").map((s) => s.entity_id).sort()).toEqual([
            "sensor.bouffay",
            "sensor.commerce",
        ]);
    });

    it("suggests the card for a followed entity only", () => {
        expect(aroundSuggestion(HASS, "person.me")).toEqual([
            {
                label: "Arrêts à proximité",
                config: { type: "custom:naolib-around-card", entity: "person.me" },
            },
        ]);
        expect(aroundSuggestion(HASS, "person.nobody")).toEqual([]);
    });
});
