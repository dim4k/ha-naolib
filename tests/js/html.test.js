import { describe, expect, it } from "vitest";
import { esc } from "../../src/html.js";

describe("esc", () => {
    it("escapes every character that could break out of markup", () => {
        expect(esc(`<a href="x">&'`)).toBe(
            "&lt;a href=&quot;x&quot;&gt;&amp;&#39;",
        );
    });

    it("renders nullish values as an empty string", () => {
        expect(esc(null)).toBe("");
        expect(esc(undefined)).toBe("");
    });

    it("stringifies non-string values", () => {
        expect(esc(42)).toBe("42");
    });
});
