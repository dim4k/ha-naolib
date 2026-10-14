import { DEFAULT_AROUND_CONFIG, MAX_DEPARTURES, MAX_STOPS } from "./config.js";
import { aroundSources } from "../entities.js";
import { NaolibFormEditor } from "../form-editor.js";

const LABELS = {
    entity: "Entité suivie (personne, zone ou traceur)",
    title: "Titre",
    departures: "Départs affichés par arrêt",
    max_stops: "Nombre maximum d'arrêts",
    compact: "Mode compact",
};

const HELPERS = {
    entity: "Celle d'une entrée Naolib « autour de moi ».",
    title: "Laisser vide pour « Autour de … ».",
    max_stops: "Mettre à 0 pour afficher tous les arrêts de l'entrée.",
};

// Only the entities an "around me" entry follows have stops to show.
function buildSchema(hass, config) {
    const sources = aroundSources(hass);
    if (config.entity && !sources.includes(config.entity)) sources.push(config.entity);
    return [
        {
            name: "entity",
            required: true,
            selector: {
                entity: {
                    filter: [{ domain: ["person", "zone", "device_tracker"] }],
                    include_entities: sources,
                },
            },
        },
        { name: "title", selector: { text: {} } },
        {
            name: "",
            type: "grid",
            schema: [
                {
                    name: "departures",
                    selector: { number: { min: 1, max: MAX_DEPARTURES, mode: "box" } },
                },
                {
                    name: "max_stops",
                    selector: { number: { min: 0, max: MAX_STOPS, mode: "box" } },
                },
                { name: "compact", selector: { boolean: {} } },
            ],
        },
    ];
}

export class NaolibAroundCardEditor extends NaolibFormEditor {
    static defaults = DEFAULT_AROUND_CONFIG;
    static labels = LABELS;
    static helpers = HELPERS;

    buildSchema(hass, config) {
        return buildSchema(hass, config);
    }
}
