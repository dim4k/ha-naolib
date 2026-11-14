import { describe, expect, it } from "vitest";
import { TimetableCache } from "../../src/timetable-cache.js";

const MONDAY = new Date(2026, 10, 16, 23, 59);
const TUESDAY = new Date(2026, 10, 17, 0, 1);
const ANSWER = { timetable: { "C3|1": { times: { "08": ["05"] } } } };

describe("TimetableCache", () => {
    it("knows nothing before a day is fetched", () => {
        const cache = new TimetableCache();
        expect(cache.isFetched(0)).toBe(false);
        expect(cache.isExpired(0)).toBe(false);
        expect(cache.timetable(0)).toEqual({});
    });

    it("stores the answer of a day", () => {
        const cache = new TimetableCache();
        const settle = cache.begin(0);
        expect(settle(ANSWER)).toBe(true);
        expect(cache.isFetched(0)).toBe(true);
        expect(cache.timetable(0)).toEqual(ANSWER.timetable);
        expect(cache.isFetched(1)).toBe(false);
    });

    it("keeps a day without service apart from a day not fetched", () => {
        const cache = new TimetableCache();
        cache.begin(0)({});
        expect(cache.isFetched(0)).toBe(true);
        expect(cache.timetable(0)).toEqual({});
    });

    it("remembers the days past the end of the calendar", () => {
        const cache = new TimetableCache();
        cache.begin(3)({ timetable: {}, expired: true });
        expect(cache.isExpired(3)).toBe(true);
        expect(cache.isExpired(0)).toBe(false);
    });

    it("fetches a day only once", () => {
        const cache = new TimetableCache();
        const settle = cache.begin(0);
        expect(cache.begin(0)).toBeNull();
        settle(ANSWER);
        expect(cache.begin(0)).toBeNull();
        expect(cache.begin(1)).not.toBeNull();
    });

    it("lets a failed day be fetched again", () => {
        const cache = new TimetableCache();
        expect(cache.begin(0)()).toBe(true);
        expect(cache.isFetched(0)).toBe(false);
        expect(cache.begin(0)).not.toBeNull();
    });

    it("keeps the timetables within the same day", () => {
        const cache = new TimetableCache();
        expect(cache.rollover(MONDAY)).toBe(false);
        cache.begin(0)(ANSWER);
        expect(cache.rollover(MONDAY)).toBe(false);
        expect(cache.isFetched(0)).toBe(true);
    });

    it("drops the timetables once the day has changed", () => {
        const cache = new TimetableCache();
        cache.rollover(MONDAY);
        cache.begin(0)(ANSWER);
        cache.begin(1)({ timetable: {}, expired: true });

        expect(cache.rollover(TUESDAY)).toBe(true);
        expect(cache.isFetched(0)).toBe(false);
        expect(cache.isExpired(1)).toBe(false);
        expect(cache.begin(0)).not.toBeNull();
        expect(cache.rollover(TUESDAY)).toBe(false);
    });

    it("ignores an answer that straddled midnight", () => {
        const cache = new TimetableCache();
        cache.rollover(MONDAY);
        const settle = cache.begin(0);
        cache.rollover(TUESDAY);

        expect(settle(ANSWER)).toBe(false);
        expect(cache.isFetched(0)).toBe(false);
        // The day can be asked for again right away.
        expect(cache.begin(0)).not.toBeNull();
    });

    it("ignores an answer for a stop that was replaced", () => {
        const cache = new TimetableCache();
        const settle = cache.begin(0);
        cache.clear();

        expect(settle(ANSWER)).toBe(false);
        expect(settle()).toBe(false);
        expect(cache.isFetched(0)).toBe(false);
    });
});
