import { aroundSources, isBikeEntity, isDepartureEntity } from "./entities.js";

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

// The "around me" card belongs to the entity an entry follows.
export function aroundSuggestion(hass, entityId) {
    return aroundSources(hass).includes(entityId)
        ? [
              {
                  label: "Arrêts à proximité",
                  config: { type: "custom:naolib-around-card", entity: entityId },
              },
          ]
        : [];
}
