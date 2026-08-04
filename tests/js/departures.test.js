import { describe, expect, it } from "vitest";
import { normalizeConfig, prepareDepartures } from "../../src/config.js";
import { renderDepartures } from "../../src/render/departures.js";

const NOW = new Date(2026, 7, 4, 14, 0).getTime();

function departure(overrides) {
    return {
        line: "C1",
        type: 2,
        destination: "Beaujoire",
        direction: 1,
        expected_ts: new Date(NOW + 5 * 60000).toISOString(),
        ...overrides,
    };
}

function render(items, config = normalizeConfig({}), stopCode = "COMM1") {
    return renderDepartures(prepareDepartures(items, config, NOW), stopCode, config);
}

describe("renderDepartures", () => {
    it("reports an empty feed and still offers the timetable", () => {
        const html = render([]);
        expect(html).toContain("Aucun départ proche");
        expect(html).toContain('id="schedule-btn"');
    });

    it("hides the timetable button when disabled or without a stop", () => {
        expect(
            render([departure()], normalizeConfig({ show_timetable_button: false })),
        ).not.toContain("schedule-btn");
        expect(render([departure()], normalizeConfig({}), "")).not.toContain(
            "schedule-btn",
        );
    });

    it("groups the departures of a line and destination on one tile", () => {
        const html = render([
            departure(),
            departure({ expected_ts: new Date(NOW + 12 * 60000).toISOString() }),
        ]);
        expect(html.match(/class="tile"/g)).toHaveLength(1);
        expect(html).toContain("5 mn");
        expect(html).toContain("12 mn");
    });

    it("renders a section per direction", () => {
        const html = render([departure(), departure({ direction: 2 })]);
        expect(html).toContain("Direction 1");
        expect(html).toContain("Direction 2");
    });

    it("colours the countdown by urgency", () => {
        const urgent = render([
            departure({ expected_ts: new Date(NOW + 30000).toISOString() }),
        ]);
        expect(urgent).toContain("time urgent");
        const warning = render([
            departure({ expected_ts: new Date(NOW + 3 * 60000).toISOString() }),
        ]);
        expect(warning).toContain("time warning");
    });

    it("shows the theoretical time struck through and the last-departure marker", () => {
        const html = render([departure({ delay_minutes: 4, is_last: true })]);
        expect(html).toContain('class="clock aimed">14:01<');
        expect(html).toContain('class="clock late"');
        expect(html).toContain("14:05");
        expect(html).toContain("dernier");
    });

    it("keeps a single clock for delays within the tolerance", () => {
        const html = render([departure({ delay_minutes: 1 })]);
        expect(html).toContain('class="clock">14:05<');
        expect(html).not.toContain("clock aimed");
    });

    it("drops the direction sections in compact mode", () => {
        const html = render(
            [departure(), departure({ direction: 2 })],
            normalizeConfig({ compact: true }),
        );
        expect(html).not.toContain("tile-group");
        expect(html.match(/class="tile"/g)).toHaveLength(2);
    });

    it("escapes the destination", () => {
        const html = render([departure({ destination: "<img src=x>" })]);
        expect(html).not.toContain("<img src=x>");
        expect(html).toContain("&lt;img src=x&gt;");
    });
});
