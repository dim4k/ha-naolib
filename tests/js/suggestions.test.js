import { describe, expect, it } from "vitest";
import { bikeSuggestion, departureSuggestion } from "../../src/suggestions.js";

const HASS = {
    states: {
        "sensor.gare_next_departures": {
            attributes: { stop_code: "STOP1", next_departures: [] },
        },
        "sensor.republique_bikes_available": {
            attributes: { station_id: "12", nearby_stations: [] },
        },
        "sensor.unrelated": { attributes: {} },
    },
};

describe("departureSuggestion", () => {
    it("suggests the departures card for a departures sensor", () => {
        expect(departureSuggestion(HASS, "sensor.gare_next_departures")).toEqual([
            {
                label: "Prochains départs",
                config: {
                    type: "custom:naolib-card",
                    entity: "sensor.gare_next_departures",
                },
            },
        ]);
    });

    it("suggests nothing for other entities", () => {
        expect(departureSuggestion(HASS, "sensor.republique_bikes_available")).toEqual(
            [],
        );
        expect(departureSuggestion(HASS, "sensor.unknown")).toEqual([]);
    });
});

describe("bikeSuggestion", () => {
    it("suggests the bike card for the bikes sensor", () => {
        expect(bikeSuggestion(HASS, "sensor.republique_bikes_available")).toEqual([
            {
                label: "Station vélo",
                config: {
                    type: "custom:naolib-bike-card",
                    entity: "sensor.republique_bikes_available",
                },
            },
        ]);
    });

    it("suggests nothing for other entities", () => {
        expect(bikeSuggestion(HASS, "sensor.gare_next_departures")).toEqual([]);
        expect(bikeSuggestion(HASS, "sensor.unrelated")).toEqual([]);
    });
});
