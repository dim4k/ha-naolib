import { describe, expect, it } from "vitest";
import { normalizeConfig } from "../../src/config.js";
import {
    groupSchedules,
    renderTimetable,
    resolveSelection,
} from "../../src/render/timetable.js";

const NOW = new Date(2026, 7, 4, 14, 0).getTime();

const SCHEDULES = {
    "C1|1": {
        ligne: { numLigne: "C1", direction: "Beaujoire" },
        direction_label: "Beaujoire",
        horaires: { 14: ["05", "35"], 15: ["05"], 13: ["05"] },
    },
    "C1|2": {
        ligne: { numLigne: "C1", direction: "François Mitterrand" },
        direction_label: "François Mitterrand",
        horaires: { 14: ["10"] },
    },
    "2|1": {
        ligne: { numLigne: "2", direction: "Orvault" },
        direction_label: "Orvault",
        horaires: { 14: ["20"] },
    },
};

const OPEN = normalizeConfig({});

describe("groupSchedules", () => {
    it("groups the directions under their line and sorts lines numerically", () => {
        const groups = groupSchedules(SCHEDULES, OPEN);
        expect(groups.map((group) => group.line)).toEqual(["2", "C1"]);
        expect(groups[1].directions.map((entry) => entry.direction)).toEqual([1, 2]);
        expect(groups[1].directions[0].label).toBe("Beaujoire");
    });

    it("applies the configured line and direction filters", () => {
        const config = normalizeConfig({ lines: ["C1"], direction: 2 });
        const groups = groupSchedules(SCHEDULES, config);
        expect(groups).toHaveLength(1);
        expect(groups[0].directions.map((entry) => entry.direction)).toEqual([2]);
    });

    it("falls back to a generic label when the destination is missing", () => {
        const groups = groupSchedules(
            { "5|1": { direction_label: "", horaires: {} } },
            OPEN,
        );
        expect(groups[0].directions[0].label).toBe("Sens 1");
    });

    it("tolerates an empty payload", () => {
        expect(groupSchedules(undefined, OPEN)).toEqual([]);
    });
});

describe("resolveSelection", () => {
    const groups = groupSchedules(SCHEDULES, OPEN);

    it("defaults to the first line and its first direction", () => {
        const { group, entry } = resolveSelection(groups, null, new Map());
        expect(group.line).toBe("2");
        expect(entry.direction).toBe(1);
    });

    it("honours the direction remembered for the selected line", () => {
        const memory = new Map([["C1", 2]]);
        const { entry } = resolveSelection(groups, "C1", memory);
        expect(entry.label).toBe("François Mitterrand");
    });

    it("falls back to the first line when the selection disappeared", () => {
        const { group } = resolveSelection(groups, "99", new Map());
        expect(group.line).toBe("2");
    });

    it("returns nothing when there is no line at all", () => {
        expect(resolveSelection([], null, new Map())).toBeNull();
    });
});

function render(overrides) {
    return renderTimetable({
        schedules: SCHEDULES,
        fetched: true,
        config: OPEN,
        selectedLine: null,
        directionByLine: new Map(),
        now: NOW,
        ...overrides,
    });
}

describe("renderTimetable", () => {
    it("distinguishes loading from an empty service day", () => {
        expect(render({ schedules: {}, fetched: false })).toContain(
            "Chargement des horaires",
        );
        expect(render({ schedules: {}, fetched: true })).toContain(
            "Aucun horaire aujourd'hui",
        );
    });

    it("renders one chip per line and marks the selected one", () => {
        const html = render({ selectedLine: "C1" });
        expect(html.match(/class="tt-chip[ "]/g)).toHaveLength(2);
        expect(html).toContain('class="tt-chip selected" data-line="C1"');
    });

    it("names the selected destination and offers the opposite one", () => {
        const html = render({ selectedLine: "C1" });
        expect(html).toContain('class="tt-to-name">Beaujoire<');
        expect(html).toContain('data-direction="2"');
        expect(html).toContain("Fran\u00e7ois Mitterrand");
        expect(html).toContain("mdi:swap-horizontal");
    });

    it("swaps towards the direction that is not selected", () => {
        const html = render({
            selectedLine: "C1",
            directionByLine: new Map([["C1", 2]]),
        });
        expect(html).toContain('class="tt-to-name">Fran\u00e7ois Mitterrand<');
        expect(html).toContain('data-direction="1"');
    });

    it("drops the swap button when the line has a single direction", () => {
        const html = render({ selectedLine: "2" });
        expect(html).not.toContain("data-direction=");
        expect(html).toContain('class="tt-to-name">Orvault<');
    });

    it("always labels the direction and announces the next passage", () => {
        const html = render({ selectedLine: "C1" });
        expect(html).toContain("Direction");
        expect(html).toContain('class="tt-next-time">14:05<');
        expect(html).toContain("dans 5 mn");
    });

    it("shows the whole day right away", () => {
        const html = render({ selectedLine: "C1" });
        expect(html).toContain("tt-grid");
        expect(html.match(/class="tt-cell [a-z]*"/g)).toHaveLength(3);
    });

    it("marks the past, current and upcoming hours", () => {
        const html = render({ selectedLine: "C1" });
        expect(html).toContain('class="tt-cell past"');
        expect(html).toContain('class="tt-cell now"');
        expect(html).toContain('class="tt-cell "');
    });

    it("highlights the next passage and dims the ones already gone", () => {
        const html = render({ selectedLine: "C1" });
        expect(html).toContain('class="tt-min next">05<');
        expect(html).toContain('class="tt-min past">05<');
    });

    it("reports a direction without any slot", () => {
        const html = render({
            schedules: { "9|1": { direction_label: "Nulle part", horaires: {} } },
        });
        expect(html).toContain("Aucun horaire aujourd'hui");
    });

    it("escapes the destination labels", () => {
        const html = render({
            schedules: {
                "9|1": { direction_label: "<script>", horaires: {} },
            },
        });
        expect(html).not.toContain("<script>");
        expect(html).toContain("&lt;script&gt;");
    });

    it("steps through the days and names the selected date", () => {
        const today = render({ selectedLine: "C1" });
        expect(today).toContain('data-day="1"');
        expect(today).toContain("Mardi 4 ao\u00fbt");
        expect(today).toContain("Aujourd&#39;hui");
        // The first day cannot go back, the last one cannot go further.
        expect(today).toContain('data-day="-1" aria-label="Jour pr\u00e9c\u00e9dent" disabled');
        expect(render({ selectedLine: "C1", dayOffset: 6 })).toContain(
            'data-day="7" aria-label="Jour suivant" disabled',
        );
    });

    it("announces the first departure and dims nothing on another day", () => {
        const html = render({ selectedLine: "C1", dayOffset: 1 });
        expect(html).toContain("Mercredi 5 ao\u00fbt");
        expect(html).toContain("Demain");
        expect(html).toContain("Premier d\u00e9part");
        expect(html).toContain('class="tt-next-time">13:05<');
        expect(html).not.toContain("tt-cell past");
        expect(html).not.toContain("tt-min next");
    });

    it("keeps the day stepper on a day without any service", () => {
        const html = render({ schedules: {}, fetched: true, dayOffset: 2 });
        expect(html).toContain("Aucun horaire ce jour-l\u00e0");
        expect(html).toContain("Apr\u00e8s-demain");
        expect(html).toContain('data-day="1"');
    });
});
