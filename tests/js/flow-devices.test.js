import { describe, expect, it } from "vitest";
import { aroundStopDeviceIds } from "../../src/flow-devices.js";

const DEVICES = [
    { id: "d1", identifiers: [["naolib", "around_E1_FR_NAOLIB:StopPlace:1"]] },
    { id: "d2", identifiers: [["naolib", "around_E1_FR_NAOLIB:StopPlace:2"]] },
    { id: "d3", identifiers: [["naolib", "around_E2_FR_NAOLIB:StopPlace:3"]] },
    { id: "d4", identifiers: [["naolib", "FR_NAOLIB:StopPlace:4"]] },
    { id: "d5", identifiers: [["other", "around_E1_x"]] },
];

describe("aroundStopDeviceIds", () => {
    it("keeps the nearby stops of the entry only", () => {
        expect([...aroundStopDeviceIds(DEVICES, "E1")]).toEqual(["d1", "d2"]);
    });

    it("copes with missing data", () => {
        expect(aroundStopDeviceIds(undefined, "E1").size).toBe(0);
        expect(aroundStopDeviceIds([{ id: "x" }], "E1").size).toBe(0);
    });
});
