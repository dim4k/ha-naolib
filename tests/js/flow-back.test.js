import { describe, expect, it } from "vitest";
import { backField } from "../../src/flow-back.js";

function flowForm(handler, names) {
    const fields = names.map((name) => ({ schema: { name } }));
    return {
        step: { handler },
        shadowRoot: {
            querySelector: () => ({ shadowRoot: { querySelectorAll: () => fields } }),
        },
    };
}

describe("backField", () => {
    it("finds the back switch of a Naolib step", () => {
        expect(backField(flowForm("naolib", ["zone", "back"]))).toEqual({
            schema: { name: "back" },
        });
    });

    it("ignores other integrations and steps without the switch", () => {
        expect(backField(flowForm("other", ["back"]))).toBeNull();
        expect(backField(flowForm("naolib", ["zone"]))).toBeNull();
        expect(backField(undefined)).toBeNull();
    });
});
