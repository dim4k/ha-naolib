// Once an "around me" entry is created, Home Assistant lists its devices (one
// per nearby stop) with an area picker each. This adds a cross to each of
// them: it calls the regular device removal, which the integration turns into
// a lasting exclusion of that stop.
//
// It only reads public element properties (the step, its devices and the
// area picker's device). If the markup changes, the cross is simply not
// added; deleting the device from its page still works.

import { findAll, whileFlowDialogOpen } from "./flow-dialog.js";

const CREATE_ENTRY_STEP = "step-flow-create-entry";

// Ids of the devices that are nearby stops of this "around me" entry.
export function aroundStopDeviceIds(devices, entryId) {
    const prefix = `around_${entryId}_`;
    return new Set(
        (devices || [])
            .filter((device) =>
                (device.identifiers || []).some(
                    ([domain, id]) => domain === "naolib" && String(id).startsWith(prefix),
                ),
            )
            .map((device) => device.id),
    );
}

// Home Assistant reuses the rows when its device list changes (a removed
// stop, a renamed device), so a row is matched to its device again on every
// pass, and the button reads the row's device when clicked. The list itself
// follows the device registry: the row of a removed stop goes away on its own.
function removeButton(row, step, entryId) {
    const button = document.createElement("ha-icon-button");
    button.dataset.naolibRemove = "1";
    button.label = "Retirer cet arrêt";
    button.title = "Retirer cet arrêt";
    button.style.cssText = "position: absolute; top: 0; right: 0;";
    const icon = document.createElement("ha-icon");
    icon.icon = "mdi:close";
    button.appendChild(icon);
    button.addEventListener("click", async () => {
        const deviceId = row.querySelector("ha-area-picker")?.device;
        if (!deviceId) return;
        button.disabled = true;
        try {
            await step.hass.callWS({
                type: "config/device_registry/remove_config_entry",
                config_entry_id: entryId,
                device_id: deviceId,
            });
        } catch (err) {
            console.error("Naolib: cannot remove the stop", err);
            button.disabled = false;
        }
    });
    return button;
}

function decorate(step) {
    const entryId = step.step?.result?.entry_id;
    if (step.step?.handler !== "naolib" || !entryId || !step.shadowRoot) return;
    const ids = aroundStopDeviceIds(step.devices, entryId);

    for (const row of step.shadowRoot.querySelectorAll("div.device")) {
        const deviceId = row.querySelector("ha-area-picker")?.device;
        let button = row.querySelector(":scope > [data-naolib-remove]");
        if (!ids.has(deviceId)) {
            button?.remove();
            continue;
        }
        if (!button) {
            row.style.position = "relative";
            button = removeButton(row, step, entryId);
            row.appendChild(button);
        }
        // A reused row now shows another device: make its button usable again.
        if (button.naolibDevice !== deviceId) {
            button.naolibDevice = deviceId;
            button.disabled = false;
        }
    }
}

export function installDeviceRemoval() {
    whileFlowDialogOpen((app) => {
        for (const step of findAll(app, CREATE_ENTRY_STEP)) decorate(step);
    });
}
