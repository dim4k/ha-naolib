import { DEFAULT_CONFIG, MAX_LINES_LIMIT, MAX_WALK_TIME } from "./config.js";
import { directionLabel, directionTermini } from "./directions.js";
import { isDepartureEntity, matchingEntities } from "./entities.js";
import { NaolibFormEditor } from "./form-editor.js";

const LABELS = {
    entity: "Entité (arrêt Naolib)",
    title: "Titre",
    lines: "Lignes",
    direction: "Direction",
    walk_time: "Temps de marche (minutes)",
    max_lines: "Lignes affichées par direction",
    show_timetable_button: "Bouton « Voir tous les horaires »",
    compact: "Mode compact",
};

const HELPERS = {
    title: "Laisser vide pour utiliser le nom de l'arrêt.",
    lines: "Ne garder que ces lignes. Toutes les lignes si vide.",
    walk_time: "Masque les départs qui ne peuvent plus être atteints à pied.",
    max_lines:
        "Nombre maximum de lignes affichées dans chaque sens. "
        + "En mode compact, nombre maximum de départs affichés.",
    compact: "Une ligne par départ, sans regroupement par direction.",
};

// Timetables by stop code, fetched once per stop: they name the termini even
// when nothing runs right now.
const timetablesByStop = new Map();

// Each direction is named after the termini of the lines the card shows.
function directionOptions(hass, config) {
    const attributes = hass.states[config.entity]?.attributes;
    const termini = directionTermini(
        timetablesByStop.get(attributes?.stop_code),
        attributes?.next_departures,
        config.lines,
    );
    return [
        { value: "0", label: "Les deux" },
        { value: "1", label: directionLabel(termini, 1) },
        { value: "2", label: directionLabel(termini, 2) },
    ];
}

// The available lines are read from the selected entity, so the picker offers
// what actually passes at this stop instead of the whole network.
function lineOptions(hass, config) {
    const state = hass.states[config.entity];
    const departures = state?.attributes?.next_departures || [];
    const lines = new Set(
        departures.map((departure) => String(departure.line ?? "")).filter(Boolean),
    );
    for (const line of config.lines) lines.add(String(line));
    return [...lines]
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
        .map((line) => ({ value: line, label: line }));
}

function buildSchema(hass, config) {
    return [
        {
            name: "entity",
            required: true,
            selector: {
                entity: {
                    filter: [{ domain: "sensor", integration: "naolib" }],
                    // The integration also creates bike sensors, which this
                    // card cannot render.
                    include_entities: matchingEntities(
                        hass,
                        isDepartureEntity,
                        config.entity,
                    ),
                },
            },
        },
        { name: "title", selector: { text: {} } },
        {
            name: "lines",
            selector: {
                select: {
                    multiple: true,
                    custom_value: true,
                    options: lineOptions(hass, config),
                },
            },
        },
        {
            name: "direction",
            selector: {
                select: {
                    mode: "dropdown",
                    options: directionOptions(hass, config),
                },
            },
        },
        {
            name: "",
            type: "grid",
            schema: [
                {
                    name: "max_lines",
                    selector: {
                        number: { min: 1, max: MAX_LINES_LIMIT, mode: "box" },
                    },
                },
                {
                    name: "walk_time",
                    selector: {
                        number: {
                            min: 0,
                            max: MAX_WALK_TIME,
                            mode: "box",
                            unit_of_measurement: "min",
                        },
                    },
                },
                { name: "show_timetable_button", selector: { boolean: {} } },
                { name: "compact", selector: { boolean: {} } },
            ],
        },
    ];
}

export class NaolibCardEditor extends NaolibFormEditor {
    static defaults = DEFAULT_CONFIG;
    static labels = LABELS;
    static helpers = HELPERS;

    buildSchema(hass, config) {
        return buildSchema(hass, config);
    }

    // The direction selector works with strings, the config with numbers.
    toFormData(config) {
        return { ...config, direction: String(config.direction) };
    }

    fromFormData(config, value) {
        return { ...config, ...value, direction: Number(value.direction ?? 0) };
    }

    _render() {
        this._fetchTimetable();
        super._render();
    }

    // Fetch the stop's timetable once, then draw the form again with it.
    _fetchTimetable() {
        const stopCode = this._hass?.states[this._config?.entity]?.attributes
            ?.stop_code;
        if (!stopCode || timetablesByStop.has(stopCode)) return;
        timetablesByStop.set(stopCode, undefined);
        this._hass
            .callWS({ type: "naolib/get_data", stop_code: stopCode })
            .then((data) => {
                timetablesByStop.set(stopCode, data?.schedules || {});
                super._render();
            })
            .catch(() => {
                // The next departures still name the termini they serve.
            });
    }
}
