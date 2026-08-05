import {
    DEFAULT_BIKE_CONFIG,
    MAX_NEARBY_COUNT,
    MAX_NEARBY_RADIUS,
} from "./config.js";
import { isBikeEntity, matchingEntities } from "../entities.js";

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

// Keep the stored configuration to what the user actually changed, so the
// YAML editor stays readable.
function prune(config) {
    const out = {};
    for (const [key, value] of Object.entries(config)) {
        if (key in DEFAULT_BIKE_CONFIG) {
            if (JSON.stringify(value) === JSON.stringify(DEFAULT_BIKE_CONFIG[key])) {
                continue;
            }
        }
        out[key] = value;
    }
    return out;
}

export class NaolibBikeCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = { ...DEFAULT_BIKE_CONFIG, ...(config || {}) };
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
        this._form.data = this._config;
    }

    _valueChanged(ev) {
        ev.stopPropagation();
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: prune(this._config) },
                bubbles: true,
                composed: true,
            }),
        );
    }
}
