import { describe, expect, it } from "vitest";
import {
    DEFAULT_CONFIG,
    matchesFilters,
    normalizeConfig,
    prepareDepartures,
} from "../../src/config.js";

const NOW = Date.parse("2026-08-04T14:00:00Z");

function departure(overrides) {
    return {
        line: "C1",
        direction: 1,
        expected_ts: new Date(NOW + 5 * 60000).toISOString(),
        ...overrides,
    };
}

describe("normalizeConfig", () => {
    it("applies the defaults for an empty config", () => {
        expect(normalizeConfig({})).toEqual({ ...DEFAULT_CONFIG, lines: [] });
    });

    it("wraps a scalar lines value into an array of strings", () => {
        expect(normalizeConfig({ lines: 2 }).lines).toEqual(["2"]);
        expect(normalizeConfig({ lines: "C1" }).lines).toEqual(["C1"]);
    });

    it("treats a missing lines value as no filter", () => {
        expect(normalizeConfig({ lines: null }).lines).toEqual([]);
    });

    it("rejects out-of-range integers", () => {
        expect(() => normalizeConfig({ direction: 3 })).toThrow(/direction/);
        expect(() => normalizeConfig({ walk_time: 61 })).toThrow(/walk_time/);
        expect(() => normalizeConfig({ max_lines: 0 })).toThrow(/max_lines/);
    });

    it("rejects wrongly typed values", () => {
        expect(() => normalizeConfig({ entity: 1 })).toThrow(/entity/);
        expect(() => normalizeConfig({ compact: "yes" })).toThrow(/compact/);
        expect(() => normalizeConfig({ lines: {} })).toThrow(/lines/);
    });
});

describe("matchesFilters", () => {
    const config = normalizeConfig({ lines: ["C1"], direction: 2 });

    it("compares line names case-insensitively", () => {
        expect(matchesFilters("c1", 2, config)).toBe(true);
        expect(matchesFilters("C2", 2, config)).toBe(false);
    });

    it("accepts the direction as a string or as a number", () => {
        expect(matchesFilters("C1", "2", config)).toBe(true);
        expect(matchesFilters("C1", 1, config)).toBe(false);
    });

    it("keeps everything when no filter is configured", () => {
        const open = normalizeConfig({});
        expect(matchesFilters("C1", 1, open)).toBe(true);
    });
});

describe("prepareDepartures", () => {
    const config = normalizeConfig({});

    it("humanizes the countdown from the raw timestamp", () => {
        const [item] = prepareDepartures([departure()], config, NOW);
        expect(item.time).toBe("5 mn");
        expect(item.minutes).toBe(5);
    });

    it("reports departures within the next minute as close", () => {
        const soon = departure({ expected_ts: new Date(NOW + 30000).toISOString() });
        expect(prepareDepartures([soon], config, NOW)[0].time).toBe("proche");
    });

    it("drops departures older than the stale cutoff", () => {
        const gone = departure({ expected_ts: new Date(NOW - 90000).toISOString() });
        expect(prepareDepartures([gone], config, NOW)).toEqual([]);
    });

    it("drops departures unreachable within the walk time", () => {
        const walking = normalizeConfig({ walk_time: 10 });
        expect(prepareDepartures([departure()], walking, NOW)).toEqual([]);
    });

    it("ignores unparseable timestamps", () => {
        expect(prepareDepartures([departure({ expected_ts: "nope" })], config, NOW)).toEqual(
            [],
        );
    });

    it("caps the list to max_lines in compact mode only", () => {
        const items = [departure(), departure(), departure()];
        const compact = normalizeConfig({ compact: true, max_lines: 2 });
        expect(prepareDepartures(items, compact, NOW)).toHaveLength(2);
        expect(prepareDepartures(items, normalizeConfig({ max_lines: 2 }), NOW)).toHaveLength(
            3,
        );
    });

    it("tolerates a missing departures list", () => {
        expect(prepareDepartures(undefined, config, NOW)).toEqual([]);
    });
});
