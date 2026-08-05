import { describe, expect, it } from "vitest";
import {
    findEntity,
    isBikeEntity,
    isDepartureEntity,
    matchingEntities,
} from "../../src/entities.js";

const HASS = {
    states: {
        "sensor.gare_next_departures": {
            attributes: { stop_code: "STOP1", next_departures: [] },
        },
        "sensor.republique_bikes_available": {
            attributes: { station_id: "12", nearby_stations: [] },
        },
        "sensor.republique_docks_available": {
            attributes: { station_id: "12", capacity: 26 },
        },
        "sensor.unrelated": { attributes: {} },
    },
};

describe("isDepartureEntity", () => {
    it("accepts a departures sensor", () => {
        expect(isDepartureEntity(HASS.states["sensor.gare_next_departures"])).toBe(
            true,
        );
    });

    it("rejects the bike sensors and anything else", () => {
        expect(
            isDepartureEntity(HASS.states["sensor.republique_bikes_available"]),
        ).toBe(false);
        expect(isDepartureEntity(HASS.states["sensor.unrelated"])).toBe(false);
        expect(isDepartureEntity(undefined)).toBe(false);
    });
});

describe("isBikeEntity", () => {
    it("accepts the bikes sensor, which carries the neighbours", () => {
        expect(isBikeEntity(HASS.states["sensor.republique_bikes_available"])).toBe(
            true,
        );
    });

    it("rejects the docks sensor, which the card cannot render", () => {
        expect(isBikeEntity(HASS.states["sensor.republique_docks_available"])).toBe(
            false,
        );
    });

    it("rejects a departures sensor", () => {
        expect(isBikeEntity(HASS.states["sensor.gare_next_departures"])).toBe(false);
    });
});

describe("matchingEntities", () => {
    it("lists only the entities the card accepts", () => {
        expect(matchingEntities(HASS, isBikeEntity)).toEqual([
            "sensor.republique_bikes_available",
        ]);
        expect(matchingEntities(HASS, isDepartureEntity)).toEqual([
            "sensor.gare_next_departures",
        ]);
    });

    it("keeps the configured entity even when it is unknown", () => {
        expect(matchingEntities(HASS, isBikeEntity, "sensor.gone")).toContain(
            "sensor.gone",
        );
    });

    it("does not duplicate the configured entity", () => {
        const ids = matchingEntities(
            HASS,
            isBikeEntity,
            "sensor.republique_bikes_available",
        );
        expect(ids).toHaveLength(1);
    });
});

describe("findEntity", () => {
    it("returns the first match, or undefined", () => {
        expect(findEntity(HASS, isDepartureEntity)).toBe(
            "sensor.gare_next_departures",
        );
        expect(findEntity({ states: {} }, isBikeEntity)).toBeUndefined();
    });
});
