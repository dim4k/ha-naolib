// Naolib sensors are recognised by their attributes rather than by their
// entity_id, so a renamed entity keeps working. The cards and their editors
// share these predicates to stay in agreement about what they accept.

export function isDepartureEntity(state) {
    return (
        !!state &&
        state.attributes.stop_code !== undefined &&
        Array.isArray(state.attributes.next_departures)
    );
}

// Only the "bikes available" sensor carries the neighbouring stations, which
// is what the bike card renders; the docks sensor is not a valid target.
export function isBikeEntity(state) {
    return (
        !!state &&
        state.attributes.station_id !== undefined &&
        Array.isArray(state.attributes.nearby_stations)
    );
}

export function findEntity(hass, predicate) {
    return Object.keys(hass.states).find((entityId) =>
        predicate(hass.states[entityId]),
    );
}

export function matchingEntities(hass, predicate, current) {
    const ids = Object.keys(hass.states).filter((entityId) =>
        predicate(hass.states[entityId]),
    );
    // Keep the configured entity offered even while it is unavailable,
    // otherwise editing the card would silently clear it.
    if (current && !ids.includes(current)) ids.push(current);
    return ids;
}

// A nearby-stop sensor of an "around me" entry: a departures sensor that
// also names the entity it follows.
export function isAroundEntity(state) {
    return isDepartureEntity(state) && typeof state.attributes.around_source === "string";
}

// The entities followed by an "around me" entry, in a stable order.
export function aroundSources(hass) {
    const sources = new Set();
    for (const state of Object.values(hass?.states || {})) {
        if (isAroundEntity(state)) sources.add(state.attributes.around_source);
    }
    return [...sources].sort();
}

export function aroundSensors(hass, source) {
    return Object.values(hass?.states || {}).filter(
        (state) => isAroundEntity(state) && state.attributes.around_source === source,
    );
}
