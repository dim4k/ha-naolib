import { NaolibBaseCard } from "../base-card.js";
import { aroundSensors, aroundSources, isAroundEntity } from "../entities.js";
import { TICK_MS } from "../constants.js";
import { normalizeAroundConfig, prepareStops } from "./config.js";
import { renderAround } from "./render.js";

// Lists the stops of an "around me" entry, nearest first, with their next
// departures. Unlike the other cards it shows several sensors: every
// nearby-stop sensor whose around_source is the configured entity.
export class NaolibAroundCard extends NaolibBaseCard {
    static normalizeConfig = normalizeAroundConfig;
    static acceptsEntity = isAroundEntity;
    static icon = "mdi:map-marker-radius";
    static defaultTitle = "Arrêts à proximité";
    static noEntityMessage =
        "Aucune entrée « autour de moi » trouvée. Ajoutez-en une via Paramètres &gt; Appareils et services.";
    static logLabel = "Naolib around card";

    static getConfigElement() {
        return document.createElement("naolib-around-card-editor");
    }

    static getStubConfig(hass) {
        return { entity: aroundSources(hass)[0] || "" };
    }

    connectedCallback() {
        // Count the departures down between two sensor updates.
        if (this._ticker) return;
        this._ticker = setInterval(() => {
            if (!this._sensors || !this.content) return;
            try {
                this._render();
            } catch (err) {
                console.error("Naolib around card: render failed", err);
            }
        }, TICK_MS);
    }

    disconnectedCallback() {
        clearInterval(this._ticker);
        this._ticker = null;
    }

    setConfig(config) {
        this._key = null;
        super.setConfig(config);
    }

    _updateFromHass(hass) {
        if (!hass) return;
        if (!this.content) this._initShadowDom();

        const source = this.config.entity || aroundSources(hass)[0];
        if (!source) {
            this._message(this.constructor.noEntityMessage);
            return;
        }

        const sensors = aroundSensors(hass, source);
        // Nothing to redraw while none of the sensors changed.
        const key = [source, ...sensors.map((s) => `${s.entity_id}@${s.last_updated}`)]
            .sort()
            .join("|");
        if (key === this._key) return;
        this._key = key;
        this._sensors = sensors;

        const name = hass.states[source]?.attributes?.friendly_name || source;
        this._updateTitle(this.config.title || `Autour de ${name}`);
        this._render();
    }

    _render() {
        if (!this._sensors.length) {
            this._message("Aucun arrêt à proximité pour le moment.");
            return;
        }
        this.content.innerHTML = renderAround(
            prepareStops(this._sensors, this.config),
            this.config,
        );
    }

    getCardSize() {
        const stops = prepareStops(this._sensors || [], this.config);
        return 1 + stops.reduce((size, stop) => size + 1 + stop.departures.length, 0);
    }
}
