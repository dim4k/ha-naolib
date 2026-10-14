import { describe, expect, it } from "vitest";
import {
    isPositionStep,
    withZoneLocation,
    zoneLocation,
} from "../../src/flow-zone.js";

const HASS = {
    states: {
        "zone.home": { attributes: { latitude: 47.21, longitude: -1.55 } },
        "zone.broken": { attributes: {} },
    },
};

describe("isPositionStep", () => {
    it("accepts the Naolib position pages only", () => {
        expect(isPositionStep({ handler: "naolib", step_id: "by_location" })).toBe(
            true,
        );
        expect(
            isPositionStep({ handler: "naolib", step_id: "bike_by_location" }),
        ).toBe(true);
        expect(isPositionStep({ handler: "naolib", step_id: "select_stop" })).toBe(
            false,
        );
        expect(isPositionStep({ handler: "other", step_id: "by_location" })).toBe(
            false,
        );
        expect(isPositionStep(undefined)).toBe(false);
    });
});

describe("zoneLocation", () => {
    it("reads the centre of a zone", () => {
        expect(zoneLocation(HASS, "zone.home")).toEqual({
            latitude: 47.21,
            longitude: -1.55,
        });
    });

    it("returns null without coordinates", () => {
        expect(zoneLocation(HASS, "zone.broken")).toBeNull();
        expect(zoneLocation(HASS, "zone.unknown")).toBeNull();
    });
});

describe("withZoneLocation", () => {
    it("moves the marker onto the zone", () => {
        const value = { zone: "zone.home", location: { latitude: 0, longitude: 0 } };
        expect(withZoneLocation(HASS, value, "zone.home")).toEqual({
            zone: "zone.home",
            location: { latitude: 47.21, longitude: -1.55 },
        });
    });

    it("leaves the value alone when the zone cannot be placed", () => {
        expect(withZoneLocation(HASS, { zone: "" }, "")).toBeNull();
        expect(withZoneLocation(HASS, { zone: "zone.broken" }, "zone.broken")).toBeNull();
        expect(withZoneLocation(HASS, null, "zone.home")).toBeNull();
    });
});
