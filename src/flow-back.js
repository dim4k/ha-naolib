// Config flow forms have no back button. Each Naolib form carries an optional
// "back" switch that the integration understands; this hides the switch and
// puts a "Retour" button next to "Valider" instead, which turns the switch on
// and submits the form, as a user would. If the markup changes, the switch
// stays visible and keeps working.

import { findAll, whileFlowDialogOpen } from "./flow-dialog.js";

const BACK_FIELD = "back";
const MARK = "naolibBack";

// The form field of the back switch on a Naolib step, if it has one.
export function backField(flowForm) {
    if (flowForm?.step?.handler !== "naolib") return null;
    const form = flowForm.shadowRoot?.querySelector("ha-form");
    const fields = form?.shadowRoot?.querySelectorAll("ha-selector") || [];
    return [...fields].find((field) => field.schema?.name === BACK_FIELD) || null;
}

function backButton(field, submit) {
    const button = document.createElement("ha-button");
    button.dataset[MARK] = "1";
    button.slot = "secondaryAction";
    button.setAttribute("appearance", "plain");
    button.textContent = "Retour";
    button.addEventListener("click", async () => {
        const toggle = findAll(field, "ha-switch")[0];
        if (!toggle) return;
        if (!toggle.checked) toggle.click();
        // Let the flow form store the new value before submitting it.
        await new Promise((resolve) => setTimeout(resolve));
        submit.click();
    });
    return button;
}

function update(app) {
    for (const dialog of findAll(app, "dialog-data-entry-flow")) {
        const footer = findAll(dialog, "ha-dialog-footer")[0];
        if (!footer) continue;
        const existing = footer.querySelector(`[data-naolib-back]`);
        const field = backField(findAll(dialog, "step-flow-form")[0]);
        const submit = footer.querySelector('[slot="primaryAction"]');

        if (!field || !submit) {
            existing?.remove();
            continue;
        }
        field.style.display = "none";
        // The button belongs to one step: rebuild it when the step changes.
        if (existing && existing.naolibField === field) continue;
        existing?.remove();
        const button = backButton(field, submit);
        button.naolibField = field;
        footer.appendChild(button);
    }
}

export function installBackButton() {
    whileFlowDialogOpen(update);
}
