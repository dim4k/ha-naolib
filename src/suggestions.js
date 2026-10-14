import { isBikeEntity, isDepartureEntity } from "./entities.js";

// Home Assistant's card picker can browse by entity: community cards that
// implement `getEntitySuggestion` are then offered for the picked entity, in
// the "Community" section next to the built-in suggestions.
function suggest(predicate, type, label) {
    return (hass, entityId) =>
        predicate(hass.states[entityId])
            ? [{ label, config: { type: `custom:${type}`, entity: entityId } }]
            : [];
}

export const departureSuggestion = suggest(
    isDepartureEntity,
    "naolib-card",
    "Prochains départs",
);

export const bikeSuggestion = suggest(isBikeEntity, "naolib-bike-card", "Station vélo");
