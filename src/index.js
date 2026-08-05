import { NaolibCard } from "./card.js";
import { NaolibBikeCard } from "./bike/card.js";
import { NaolibBikeCardEditor } from "./bike/editor.js";
import { NaolibCardEditor } from "./editor.js";

// The loader retries with a fresh query string, so this module can be
// evaluated more than once per page: a second definition is not an error.
function define(tag, elementClass) {
    try {
        customElements.define(tag, elementClass);
    } catch (err) {
        if (!customElements.get(tag)) throw err;
    }
}

define("naolib-card", NaolibCard);
define("naolib-card-editor", NaolibCardEditor);
define("naolib-bike-card", NaolibBikeCard);
define("naolib-bike-card-editor", NaolibBikeCardEditor);

const CARDS = [
    {
        type: "naolib-card",
        name: "Naolib Nantes",
        preview: true,
        description: "Affiche les prochains départs (Bus/Tram) pour un arrêt donné.",
    },
    {
        type: "naolib-bike-card",
        name: "Naolib Vélo",
        preview: true,
        description:
            "Affiche les vélos et places disponibles d'une station Naolib et de ses voisines.",
    },
];

window.customCards = window.customCards || [];
for (const card of CARDS) {
    if (!window.customCards.some((known) => known.type === card.type)) {
        window.customCards.push(card);
    }
}
