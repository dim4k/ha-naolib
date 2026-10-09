import {
    DEFAULT_BIKE_CONFIG,
    MAX_NEARBY_COUNT,
    MAX_NEARBY_RADIUS,
} from "./config.js";
import { isBikeEntity, matchingEntities } from "../entities.js";
import { NaolibFormEditor } from "../form-editor.js";

const LABELS = {
    entity: "Entité (station vélo Naolib)",
    title: "Titre",
    nearby_count: "Stations à proximité affichées",
    nearby_radius: "Rayon de recherche (mètres)",
    show_docks: "Afficher les places disponibles",
    compact: "Mode compact",
};

const HELPERS = {
    title: "Laisser vide pour utiliser le nom de la station.",
    nearby_count: "Mettre à 0 pour masquer les stations voisines.",
    nearby_radius: "Les stations plus éloignées ne sont pas proposées.",
    compact: "Masque la jauge de remplissage.",
};

// Only the "bikes available" sensor carries the nearby stations, so the picker
// filters on that attribute rather than on the entity id.
function buildSchema(hass, config) {
    return [
        {
            name: "entity",
            required: true,
            selector: {
                entity: {
                    filter: [{ domain: "sensor", integration: "naolib" }],
                    include_entities: matchingEntities(
                        hass,
                        isBikeEntity,
                        config.entity,
                    ),
                },
            },
        },
        { name: "title", selector: { text: {} } },
        {
            name: "",
            type: "grid",
            schema: [
                {
                    name: "nearby_count",
                    selector: {
                        number: { min: 0, max: MAX_NEARBY_COUNT, mode: "box" },
                    },
                },
                {
                    name: "nearby_radius",
                    selector: {
                        number: {
                            min: 0,
                            max: MAX_NEARBY_RADIUS,
                            step: 50,
                            mode: "box",
                            unit_of_measurement: "m",
                        },
                    },
                },
                { name: "show_docks", selector: { boolean: {} } },
                { name: "compact", selector: { boolean: {} } },
            ],
        },
    ];
}

export class NaolibBikeCardEditor extends NaolibFormEditor {
    static defaults = DEFAULT_BIKE_CONFIG;
    static labels = LABELS;
    static helpers = HELPERS;

    buildSchema(hass, config) {
        return buildSchema(hass, config);
    }
}
