// Config flow forms cannot update one field from another. On the Naolib
// "search around a location" page, this moves the map marker onto the zone
// as soon as one is picked, so the zone and the map can share one page.
//
// It relies as little as possible on Home Assistant internals: the
// step-flow-form's public `step` and `hass`, the `schema` of the ha-form
// fields, and rewriting the form's value-changed event before the flow form
// stores it. If the frontend changes, the page keeps working, only the
// marker stops following; the backend then falls back on the zone when the
// marker was left at home.

const POSITION_STEPS = new Set(["by_location", "bike_by_location"]);
const ZONE_FIELD = "zone";

export function isPositionStep(step) {
    return step?.handler === "naolib" && POSITION_STEPS.has(step.step_id);
}

export function zoneLocation(hass, zoneId) {
    const attributes = hass?.states?.[zoneId]?.attributes;
    const latitude = attributes?.latitude;
    const longitude = attributes?.longitude;
    if (typeof latitude !== "number" || typeof longitude !== "number") return null;
    return { latitude, longitude };
}

// The form value with the marker moved onto the zone, or null to leave it.
export function withZoneLocation(hass, value, zoneId) {
    if (!zoneId || !value || typeof value !== "object") return null;
    const location = zoneLocation(hass, zoneId);
    if (!location) return null;
    return { ...value, location: { ...(value.location || {}), ...location } };
}

// ha-form fires its own value-changed right after the one of the field that
// changed, synchronously: the zone picked in between is remembered here.
const pickedZone = new WeakMap();

function onValueChanged(event) {
    const path = event.composedPath();
    const formIndex = path.findIndex((el) => el?.localName === "ha-form");
    if (formIndex < 0) return;
    const flow = path.find((el) => el?.localName === "step-flow-form");
    if (!flow || !isPositionStep(flow.step)) return;
    const form = path[formIndex];

    if (formIndex > 0) {
        const field = path
            .slice(0, formIndex)
            .find((el) => typeof el?.schema?.name === "string");
        if (field?.schema.name === ZONE_FIELD) {
            pickedZone.set(form, event.detail?.value);
        }
        return;
    }

    if (!pickedZone.has(form)) return;
    const zoneId = pickedZone.get(form);
    pickedZone.delete(form);
    const value = withZoneLocation(flow.hass, event.detail?.value, zoneId);
    if (value) event.detail.value = value;
}

let installed = false;

export function installZoneFollower(target = document) {
    if (installed) return;
    installed = true;
    // Capture phase, so the event is rewritten before the flow form sees it.
    target.addEventListener("value-changed", onValueChanged, true);
}
