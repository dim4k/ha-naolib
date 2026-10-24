import { describe, expect, it } from "vitest";
import {
    directionHeading,
    directionLabel,
    directionTermini,
} from "../../src/directions.js";

const schedules = {
    "C1|1": { ligne: { numLigne: "C1", direction: "François Mitterrand" } },
    "C1|2": { ligne: { numLigne: "C1", direction: "Gare de Chantenay" } },
    "2|1": { ligne: { numLigne: "2", direction: "Orvault Grand Val" } },
    "2|2": { ligne: { numLigne: "2", direction: "Trocardière" } },
};

describe("directionTermini", () => {
    it("names each direction after the termini of its lines", () => {
        const termini = directionTermini(schedules, []);
        expect(directionLabel(termini, 1)).toBe(
            "2 → Orvault Grand Val · C1 → François Mitterrand",
        );
        expect(directionLabel(termini, 2)).toBe(
            "2 → Trocardière · C1 → Gare de Chantenay",
        );
    });

    it("keeps only the lines the card shows", () => {
        const termini = directionTermini(schedules, [], ["C1"]);
        expect(directionLabel(termini, 1)).toBe("C1 → François Mitterrand");
    });

    it("falls back on the next departures without a timetable", () => {
        const departures = [
            { line: "C1", direction: 1, destination: "François Mitterrand" },
            { line: "C1", direction: 1, destination: "Le Cardo" },
            { line: "C3", direction: 1, destination: "François Mitterrand" },
        ];
        const termini = directionTermini(undefined, departures);
        expect(directionLabel(termini, 1)).toBe(
            "C1 → François Mitterrand / Le Cardo · C3 → François Mitterrand",
        );
    });

    it("groups the lines sharing a terminus", () => {
        const departures = [
            { line: "C3", direction: 2, destination: "Commerce" },
            { line: "C1", direction: 2, destination: "Commerce" },
        ];
        const termini = directionTermini({}, departures);
        expect(directionLabel(termini, 2)).toBe("C1, C3 → Commerce");
    });

    it("keeps the direction number when nothing is known", () => {
        expect(directionLabel(directionTermini({}, []), 2)).toBe("Direction 2");
    });
});

describe("directionHeading", () => {
    it("lists where the departures of a direction go", () => {
        const departures = [
            { line: "C1", direction: 1, destination: "François Mitterrand" },
            { line: "C3", direction: 1, destination: "Armor" },
            { line: "C3", direction: 1, destination: "Armor" },
            { line: "C1", direction: 2, destination: "Gare de Chantenay" },
        ];
        expect(directionHeading(departures, 1)).toBe(
            "Vers Armor · François Mitterrand",
        );
        expect(directionHeading(departures, 2)).toBe("Vers Gare de Chantenay");
    });

    it("keeps the direction number without a destination", () => {
        expect(directionHeading([{ direction: 1 }], 1)).toBe("Direction 1");
    });
});
