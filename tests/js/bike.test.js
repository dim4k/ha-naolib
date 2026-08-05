import { describe, expect, it } from "vitest";
import {
    DEFAULT_BIKE_CONFIG,
    normalizeBikeConfig,
    prepareNearby,
} from "../../src/bike/config.js";
import { renderBikeStation } from "../../src/bike/render.js";

function station(overrides) {
    return {
        station_id: "2",
        name: "COMMERCE",
        distance: 200,
        bikes: 5,
        docks: 10,
        capacity: 15,
        is_renting: true,
        is_returning: true,
        ...overrides,
    };
}

describe("normalizeBikeConfig", () => {
    it("applies the defaults for an empty config", () => {
        expect(normalizeBikeConfig({})).toEqual(DEFAULT_BIKE_CONFIG);
    });

    it("rejects out-of-range integers", () => {
        expect(() => normalizeBikeConfig({ nearby_count: 11 })).toThrow(
            /nearby_count/,
        );
        expect(() => normalizeBikeConfig({ nearby_radius: -1 })).toThrow(
            /nearby_radius/,
        );
    });

    it("rejects wrongly typed values", () => {
        expect(() => normalizeBikeConfig({ entity: 1 })).toThrow(/entity/);
        expect(() => normalizeBikeConfig({ show_docks: "yes" })).toThrow(/show_docks/);
        expect(() => normalizeBikeConfig({ compact: 1 })).toThrow(/compact/);
    });
});

describe("prepareNearby", () => {
    const config = normalizeBikeConfig({ nearby_count: 2, nearby_radius: 300 });

    it("drops the stations beyond the radius", () => {
        const kept = prepareNearby(
            [station({ distance: 100 }), station({ distance: 400 })],
            config,
        );
        expect(kept).toHaveLength(1);
        expect(kept[0].distance).toBe(100);
    });

    it("caps the list to the configured count", () => {
        const kept = prepareNearby(
            [
                station({ distance: 100 }),
                station({ distance: 150 }),
                station({ distance: 200 }),
            ],
            config,
        );
        expect(kept).toHaveLength(2);
    });

    it("returns nothing when the neighbours are disabled", () => {
        const disabled = normalizeBikeConfig({ nearby_count: 0 });
        expect(prepareNearby([station()], disabled)).toEqual([]);
    });

    it("tolerates a missing list", () => {
        expect(prepareNearby(undefined, config)).toEqual([]);
    });
});

describe("renderBikeStation", () => {
    const config = normalizeBikeConfig({});

    it("reports a station missing from the snapshot", () => {
        const html = renderBikeStation({ available: false }, [], config);
        expect(html).toMatch(/introuvable/);
    });

    it("shows the counters and the neighbours", () => {
        const html = renderBikeStation(
            {
                available: true,
                bikes: 7,
                docks: 8,
                capacity: 15,
                is_installed: true,
                is_renting: true,
                is_returning: true,
            },
            [station({ name: "PRÉFECTURE", distance: 120 })],
            config,
        );
        expect(html).toMatch(/>7</);
        expect(html).toMatch(/>8</);
        expect(html).toMatch(/PRÉFECTURE/);
        expect(html).toMatch(/120 m/);
    });

    it("flags a station that cannot be rented from", () => {
        const html = renderBikeStation(
            {
                available: true,
                bikes: 0,
                docks: 15,
                capacity: 15,
                is_installed: true,
                is_renting: false,
                is_returning: true,
            },
            [],
            config,
        );
        expect(html).toMatch(/Location indisponible/);
        expect(html).toMatch(/bike-count empty/);
    });

    it("escapes the station names", () => {
        const html = renderBikeStation(
            { available: true, bikes: 1, docks: 1, capacity: 2 },
            [station({ name: "<img src=x onerror=alert(1)>" })],
            config,
        );
        expect(html).not.toMatch(/<img/);
    });

    it("hides the docks when they are turned off", () => {
        const withoutDocks = normalizeBikeConfig({ show_docks: false });
        const html = renderBikeStation(
            { available: true, bikes: 3, docks: 9, capacity: 12 },
            [station()],
            withoutDocks,
        );
        expect(html).not.toMatch(/places/);
        expect(html).not.toMatch(/pl\./);
    });
});
