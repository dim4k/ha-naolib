import {
    DEFAULT_AROUND_CONFIG,
    MAX_DEPARTURES,
    MAX_RADIUS,
    MAX_STOPS,
    MIN_RADIUS,
} from "./config.js";
import { NaolibFormEditor } from "../form-editor.js";

const LABELS = {
    entity: "Entité suivie (personne, zone ou traceur)",
    title: "Titre",
    radius: "Rayon (mètres)",
    max_stops: "Nombre maximum d'arrêts",
    departures: "Départs affichés par arrêt",
    compact: "Mode compact",
};

const HELPERS = {
    entity: "Elle doit avoir des coordonnées GPS ; les arrêts suivent ses déplacements.",
    title: "Laisser vide pour « Autour de … ».",
};

function buildSchema() {
    return [
        {
            name: "entity",
            required: true,
            selector: {
                entity: { filter: [{ domain: ["person", "zone", "device_tracker"] }] },
            },
        },
        { name: "title", selector: { text: {} } },
        {
            name: "",
            type: "grid",
            schema: [
                {
                    name: "radius",
                    selector: {
                        number: {
                            min: MIN_RADIUS,
                            max: MAX_RADIUS,
                            step: 50,
                            mode: "box",
                            unit_of_measurement: "m",
                        },
                    },
                },
                {
                    name: "max_stops",
                    selector: { number: { min: 1, max: MAX_STOPS, mode: "box" } },
                },
                {
                    name: "departures",
                    selector: { number: { min: 1, max: MAX_DEPARTURES, mode: "box" } },
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

    buildSchema() {
        return buildSchema();
    }
}
