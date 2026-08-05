import { describe, expect, it } from "vitest";
import { lineBadge, lineColors } from "../../src/lines.js";

describe("lineColors", () => {
    it("uses the colour the network declares", () => {
        // Line 26 is green, not the generic fallback blue.
        expect(lineColors("26")).toEqual({ bg: "#009640", text: "#ffffff" });
        expect(lineColors("1")).toEqual({ bg: "#00a754", text: "#ffffff" });
        expect(lineColors("C1")).toEqual({ bg: "#0bbbef", text: "#ffffff" });
    });

    it("takes the readable text colour from the feed", () => {
        expect(lineColors("4").text).toBe("#000000");
        expect(lineColors("C20").text).toBe("#000000");
        expect(lineColors("2").text).toBe("#ffffff");
    });

    it("covers the lettered and three-digit lines", () => {
        expect(lineColors("1B").bg).toBe("#00a754");
        expect(lineColors("TE1").bg).toBe("#502391");
        expect(lineColors("N1").bg).toBe("#2aaab6");
        expect(lineColors("118").bg).toBe("#a9162e");
    });

    it("ignores the case of the line number", () => {
        expect(lineColors("c3")).toEqual(lineColors("C3"));
    });

    it("falls back on the theme colour for an unknown line", () => {
        expect(lineColors("ZZ")).toEqual({
            bg: "var(--primary-color)",
            text: "#ffffff",
        });
    });
});

describe("lineBadge", () => {
    it("renders the colours inline", () => {
        const html = lineBadge("26");
        expect(html).toContain("background-color: #009640");
        expect(html).toContain("color: #ffffff");
        expect(html).toContain(">26<");
    });

    it("escapes the line number", () => {
        expect(lineBadge("<img>")).not.toContain("<img>");
    });
});
