import { NaolibBaseCard } from "../base-card.js";
import { firstLocatable } from "../entities.js";
import { errorText, esc } from "../html.js";
import { LOADING } from "../render/shared.js";
import {
    SUBSCRIBE_RETRY_MS,
    canSubscribe,
    normalizeAroundConfig,
    prepareStops,
} from "./config.js";
import { noStopsMessage, notLocatedMessage, renderAround } from "./render.js";

// Lists the stops around a person, zone or device tracker, nearest first,
// with their next departures. The integration follows the entity and pushes
// the stops over a WebSocket subscription, so stops appear and disappear as
// the entity moves; no "around me" entry is needed.
export class NaolibAroundCard extends NaolibBaseCard {
    static normalizeConfig = normalizeAroundConfig;
    static icon = "mdi:map-marker-radius";
    static defaultTitle = "Arrêts à proximité";
    static noEntityMessage =
        "Choisissez une personne, une zone ou un traceur à suivre dans l'éditeur de la carte.";
    static logLabel = "Naolib around card";
    // Counts the departures down between two pushes from the integration.
    static ticks = true;

    static getConfigElement() {
        return document.createElement("naolib-around-card-editor");
    }

    static getStubConfig(hass) {
        return { entity: firstLocatable(hass) || "" };
    }

    connectedCallback() {
        super.connectedCallback();
        this._subscribe();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this._unsubscribe();
    }

    // The stops come from the subscription, not from an entity state.
    _hasData() {
        return Boolean(this._data);
    }

    _updateFromHass(hass) {
        if (!hass) return;
        if (!this.content) this._initShadowDom();

        const entity = this.config.entity;
        if (!entity) {
            this._unsubscribe();
            this._failure = null;
            this._message(this.constructor.noEntityMessage);
            return;
        }
        this._name = hass.states[entity]?.attributes?.friendly_name || entity;
        this._updateTitle(this.config.title || `Autour de ${this._name}`);
        this._subscribe();
        // A failure keeps its message up until the next attempt.
        if (!this._data && !this._failure) this._message(LOADING);
    }

    // One subscription per entity, radius and number of stops; a new
    // configuration replaces it.
    async _subscribe() {
        const { entity, radius, max_stops: maxStops } = this.config;
        if (!this._hass || !this.isConnected || !entity) return;
        const key = `${entity}|${radius}|${maxStops}`;
        if (this._subscriptionKey === key) return;
        // `hass` is set on every state change: a subscription that cannot
        // succeed (integration not loaded, invalid entity) would otherwise be
        // attempted again several times a second.
        if (!canSubscribe(this._failure, key)) return;

        this._unsubscribe();
        this._failure = null;
        this._subscriptionKey = key;
        this._data = null;
        try {
            const unsubscribe = await this._hass.connection.subscribeMessage(
                (data) => {
                    if (this._subscriptionKey !== key) return;
                    this._data = data;
                    this._render();
                },
                {
                    type: "naolib/around/subscribe",
                    entity_id: entity,
                    radius,
                    max_stops: maxStops,
                },
            );
            if (this._subscriptionKey === key) this._unsubscribeFn = unsubscribe;
            else unsubscribe();
        } catch (err) {
            if (this._subscriptionKey === key) {
                this._subscriptionKey = null;
                this._failure = { key, retryAt: Date.now() + SUBSCRIBE_RETRY_MS };
            }
            console.error("Naolib around card: subscription failed", err);
            if (this.content) {
                this._message(
                    `Impossible de suivre ${esc(this._name || entity)} : l'intégration Naolib est-elle installée avec au moins une entrée ? (${errorText(err)})`,
                );
            }
        }
    }

    _unsubscribe() {
        const unsubscribe = this._unsubscribeFn;
        this._unsubscribeFn = null;
        this._subscriptionKey = null;
        if (unsubscribe) {
            Promise.resolve(unsubscribe()).catch(() => {});
        }
    }

    _render() {
        if (!this._data) return;
        if (!this._data.located) {
            this._message(notLocatedMessage(this._name));
            return;
        }
        if (!this._data.stops.length) {
            this._message(noStopsMessage(this._name, this.config.radius));
            return;
        }
        this.content.innerHTML = renderAround(prepareStops(this._data.stops, this.config));
    }

    getCardSize() {
        const stops = prepareStops(this._data?.stops, this.config);
        return 1 + stops.reduce((size, stop) => size + 1 + stop.directions.length, 0);
    }
}
