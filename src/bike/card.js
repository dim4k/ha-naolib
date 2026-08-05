import { normalizeBikeConfig, prepareNearby } from "./config.js";
import { renderBikeStation } from "./render.js";
import { findEntity, isBikeEntity } from "../entities.js";
import { esc } from "../html.js";
import { message } from "../render/shared.js";
import { styles } from "../styles/index.js";

function findBikeEntity(hass) {
    return findEntity(hass, isBikeEntity);
}

export class NaolibBikeCard extends HTMLElement {
    // `hass` can be set before `setConfig` (mobile reconnections), so the card
    // always carries a usable configuration.
    config = normalizeBikeConfig({});

    static getStubConfig(hass) {
        return { entity: findBikeEntity(hass) || "" };
    }

    static getConfigElement() {
        return document.createElement("naolib-bike-card-editor");
    }

    setConfig(config) {
        this.config = normalizeBikeConfig(config);
        this.toggleAttribute("compact", this.config.compact);
        // Options change what is rendered without the entity state changing,
        // so drop the memoized state to force a redraw.
        this._state = null;
        if (this.content && this._hass) this._updateFromHass(this._hass);
    }

    set hass(hass) {
        this._hass = hass;
        try {
            this._updateFromHass(hass);
        } catch (err) {
            // Never let an exception bubble up to Home Assistant, otherwise
            // the whole card is replaced by a generic "Configuration error".
            console.error("Naolib bike card error:", err);
            try {
                if (!this.content) this._initShadowDom();
                this._message(`Erreur : ${esc(err?.message || err)}`);
            } catch (renderErr) {
                console.error(
                    "Naolib bike card: cannot render error state",
                    renderErr,
                );
            }
        }
    }

    _message(html) {
        this.content.innerHTML = message(html);
    }

    _updateFromHass(hass) {
        if (!hass) return;

        const config = this.config;
        const entityId = config.entity || findBikeEntity(hass);

        if (!this.content) this._initShadowDom();
        if (!entityId) {
            this._message(
                `Aucune station vélo Naolib trouvée. Ajoutez-la via Paramètres &gt; Appareils et services.`,
            );
            return;
        }

        const state = hass.states[entityId];
        if (!state || !state.attributes) {
            this._message(`Entité introuvable : ${esc(entityId)}`);
            return;
        }

        // Nothing to redraw while the sensor has not been updated.
        if (
            this._state &&
            this._state.last_updated === state.last_updated &&
            this._state.entity_id === entityId
        ) {
            return;
        }

        this._state = state;
        this._updateTitle(
            config.title ||
                state.attributes.station_label ||
                state.attributes.friendly_name,
        );

        if (!state.attributes.station_id) {
            this._message("Entité non configurée (station_id manquant)");
            return;
        }

        this._render();
    }

    _initShadowDom() {
        // attachShadow throws if a root is already attached, which happens
        // when a previous call failed after attaching but before filling it.
        if (!this.shadowRoot) this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
            <style>${styles}</style>
            <ha-card>
                <div class="card-header">
                    <ha-icon icon="mdi:bike" class="icon"></ha-icon>
                    <span id="title">Station vélo Naolib</span>
                </div>
                <div id="content"></div>
            </ha-card>
        `;
        this.content = this.shadowRoot.getElementById("content");
        this.titleElement = this.shadowRoot.getElementById("title");
    }

    _updateTitle(name) {
        if (this.titleElement) {
            this.titleElement.innerText = name || "Station vélo Naolib";
        }
    }

    // The sensor attributes carry everything the card shows, so the whole
    // station and its neighbours render without any WebSocket round-trip.
    _stationData() {
        const attributes = this._state.attributes;
        return {
            available: this._state.state !== "unavailable",
            bikes: Number.isFinite(Number(this._state.state))
                ? Number(this._state.state)
                : null,
            docks: attributes.docks_available,
            capacity: attributes.capacity,
            is_installed: attributes.is_installed,
            is_renting: attributes.is_renting,
            is_returning: attributes.is_returning,
        };
    }

    _render() {
        if (!this._state) {
            this._message("Chargement...");
            return;
        }

        this.content.innerHTML = renderBikeStation(
            this._stationData(),
            prepareNearby(this._state.attributes.nearby_stations, this.config),
            this.config,
        );
    }

    getCardSize() {
        const nearby = prepareNearby(
            this._state?.attributes?.nearby_stations ?? [],
            this.config,
        );
        return 3 + nearby.length;
    }

    // Sizing for the sections view: the height depends on how many
    // neighbouring stations the config asks for, so only the card can measure it.
    getGridOptions() {
        return { columns: 12, min_columns: 6, rows: "auto" };
    }
}
