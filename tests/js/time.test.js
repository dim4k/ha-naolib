import { describe, expect, it } from "vitest";
import {
    formatClock,
    humanizeSeconds,
    passageDate,
    serviceDay,
    serviceHourKey,
} from "../../src/time.js";

describe("humanizeSeconds", () => {
    it("collapses the first minute into a single label", () => {
        expect(humanizeSeconds(0)).toBe("proche");
        expect(humanizeSeconds(60)).toBe("proche");
    });

    it("counts in minutes below an hour", () => {
        expect(humanizeSeconds(61)).toBe("1 mn");
        expect(humanizeSeconds(3599)).toBe("59 mn");
    });

    it("switches to hours and pads the minutes", () => {
        expect(humanizeSeconds(3600)).toBe("1h00");
        expect(humanizeSeconds(3600 + 5 * 60)).toBe("1h05");
    });
});

describe("serviceHourKey", () => {
    it("pushes the hours after midnight to the end of the service day", () => {
        expect(serviceHourKey("05")).toBe(5);
        expect(serviceHourKey("23")).toBe(23);
        expect(serviceHourKey("00")).toBe(24);
        expect(serviceHourKey("03")).toBe(27);
        expect(serviceHourKey("04")).toBe(4);
    });
});

describe("formatClock", () => {
    it("pads both fields", () => {
        expect(formatClock(new Date(2026, 7, 4, 9, 5))).toBe("09:05");
    });
});

describe("passageDate", () => {
    it("keeps daytime slots on the current day", () => {
        const now = new Date(2026, 7, 4, 14, 0).getTime();
        expect(passageDate(now, 15, 30)).toEqual(new Date(2026, 7, 4, 15, 30));
    });

    it("moves the slots after midnight to the next day", () => {
        const now = new Date(2026, 7, 4, 23, 0).getTime();
        expect(passageDate(now, 1, 10)).toEqual(new Date(2026, 7, 5, 1, 10));
    });

    it("keeps them on the current day when it is already the small hours", () => {
        const now = new Date(2026, 7, 5, 1, 0).getTime();
        expect(passageDate(now, 1, 10)).toEqual(new Date(2026, 7, 5, 1, 10));
    });

    it("puts the daytime slots on the day before, seen from the small hours", () => {
        const now = new Date(2026, 7, 5, 1, 0).getTime();
        expect(passageDate(now, 22, 30)).toEqual(new Date(2026, 7, 4, 22, 30));
        expect(passageDate(now, 4, 0)).toEqual(new Date(2026, 7, 4, 4, 0));
    });
});

describe("serviceDay", () => {
    const day = (date) => [date.getFullYear(), date.getMonth(), date.getDate()];

    it("is the calendar day from the cutoff on", () => {
        expect(day(serviceDay(new Date(2026, 7, 5, 4, 0)))).toEqual([2026, 7, 5]);
        expect(day(serviceDay(new Date(2026, 7, 5, 23, 59)))).toEqual([2026, 7, 5]);
    });

    it("is the day before in the small hours", () => {
        expect(day(serviceDay(new Date(2026, 7, 5, 0, 0)))).toEqual([2026, 7, 4]);
        expect(day(serviceDay(new Date(2026, 7, 5, 3, 59)))).toEqual([2026, 7, 4]);
        expect(day(serviceDay(new Date(2026, 7, 1, 2, 0)))).toEqual([2026, 6, 31]);
    });

    it("leaves its argument untouched", () => {
        const now = new Date(2026, 7, 5, 1, 0);
        serviceDay(now);
        expect(now).toEqual(new Date(2026, 7, 5, 1, 0));
    });
});
