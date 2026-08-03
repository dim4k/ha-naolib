import { DEFAULT_CONFIG, MAX_LINES_LIMIT, MAX_WALK_TIME } from "./config.js";

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
                entity: { filter: [{ domain: "sensor", integration: "naolib" }] },
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
                    options: [
                        { value: "0", label: "Les deux" },
                        { value: "1", label: "Direction 1" },
                        { value: "2", label: "Direction 2" },
                    ],
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

// Keep the stored configuration to what the user actually changed, so the
// YAML editor stays readable.
function prune(config) {
    const out = {};
    for (const [key, value] of Object.entries(config)) {
        if (key in DEFAULT_CONFIG) {
            if (JSON.stringify(value) === JSON.stringify(DEFAULT_CONFIG[key])) continue;
        }
        out[key] = value;
    }
    return out;
}

export class NaolibCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = { ...DEFAULT_CONFIG, ...(config || {}) };
        this._render();
    }

    set hass(hass) {
        this._hass = hass;
        this._render();
    }

    _render() {
        if (!this._hass || !this._config) return;

        if (!this._form) {
            this._form = document.createElement("ha-form");
            this._form.computeLabel = (schema) => LABELS[schema.name] || schema.name;
            this._form.computeHelper = (schema) => HELPERS[schema.name] || "";
            this._form.addEventListener("value-changed", (ev) =>
                this._valueChanged(ev),
            );
            this.appendChild(this._form);
        }

        this._form.hass = this._hass;
        this._form.schema = buildSchema(this._hass, this._config);
        // The direction selector works with strings, the config with numbers.
        this._form.data = { ...this._config, direction: String(this._config.direction) };
    }

    _valueChanged(ev) {
        ev.stopPropagation();
        const value = ev.detail.value;
        this._config = {
            ...this._config,
            ...value,
            direction: Number(value.direction ?? 0),
        };
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: prune(this._config) },
                bubbles: true,
                composed: true,
            }),
        );
    }
}
