import { TICK_MS } from "./constants.js";
import { findEntity } from "./entities.js";
import { errorText, esc } from "./html.js";
import { message } from "./render/shared.js";
import { styles } from "./styles/index.js";

// Lifecycle shared by the departures and the bike cards: entity lookup,
// error containment, shadow DOM and title. Subclasses describe their entity
// through the static fields below and implement _render().
export class NaolibBaseCard extends HTMLElement {
    static normalizeConfig = (config) => config;
    // Predicate recognising the sensors this card can render.
    static acceptsEntity = () => false;
    // Attributes holding the configured identifier and its display label.
    static idAttribute = "";
    static labelAttribute = "";
    static icon = "";
    static defaultTitle = "";
    static noEntityMessage = "";
    static logLabel = "Naolib card";
    // Cards counting departures down redraw on a timer between two updates,
    // so the countdowns (and "proche") stay on time instead of aging.
    static ticks = false;

    // `hass` can be set before `setConfig` (mobile reconnections), so the card
    // always carries a usable configuration.
    config = this.constructor.normalizeConfig({});

    static getStubConfig(hass) {
        return { entity: findEntity(hass, this.acceptsEntity) || "" };
    }

    connectedCallback() {
        if (!this.constructor.ticks || this._ticker) return;
        this._ticker = setInterval(() => {
            if (!this._hasData() || !this.content) return;
            try {
                this._render();
            } catch (err) {
                console.error(`${this.constructor.logLabel}: render failed`, err);
            }
        }, TICK_MS);
    }

    disconnectedCallback() {
        clearInterval(this._ticker);
        this._ticker = null;
    }

    // Whether there is anything to draw yet.
    _hasData() {
        return Boolean(this._state);
    }

    setConfig(config) {
        this.config = this.constructor.normalizeConfig(config);
        this.toggleAttribute("compact", this.config.compact);
        // Options change what is rendered without the entity state changing,
        // so drop the memoized state to force a redraw.
        this._state = null;
        if (this.content && this._hass) this._updateFromHass(this._hass);
    }

    set hass(hass) {
        // Kept for the subclasses that call back into Home Assistant.
        this._hass = hass;
        try {
            this._updateFromHass(hass);
        } catch (err) {
            // Never let an exception bubble up to Home Assistant, otherwise
            // the whole card is replaced by a generic "Configuration error".
            // This happens often on mobile where `hass` may be set before
            // `setConfig`, or during frequent reconnections.
            console.error(`${this.constructor.logLabel} error:`, err);
            try {
                if (!this.content) this._initShadowDom();
                this._message(`Erreur : ${errorText(err)}`);
            } catch (renderErr) {
                // The fallback rendering must not throw either.
                console.error(
                    `${this.constructor.logLabel}: cannot render error state`,
                    renderErr,
                );
            }
        }
    }

    _message(html) {
        this.content.innerHTML = message(html);
    }

    // Called before a new state is adopted, with the one it replaces.
    _onStateChange(_previous, _state) {}

    _updateFromHass(hass) {
        if (!hass) return;

        const card = this.constructor;
        const entityId = this.config.entity || findEntity(hass, card.acceptsEntity);

        if (!this.content) this._initShadowDom();
        if (!entityId) {
            this._message(card.noEntityMessage);
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

        this._onStateChange(this._state, state);
        this._state = state;
        this._updateTitle(
            this.config.title ||
                state.attributes[card.labelAttribute] ||
                state.attributes.friendly_name,
        );

        if (!state.attributes[card.idAttribute]) {
            this._message(`Entité non configurée (${card.idAttribute} manquant)`);
            return;
        }

        this._render();
    }

    _initShadowDom() {
        const card = this.constructor;
        // attachShadow throws if a root is already attached, which happens
        // when a previous call failed after attaching but before filling it.
        if (!this.shadowRoot) this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
            <style>${styles}</style>
            <ha-card>
                <div class="card-header">
                    <ha-icon icon="${card.icon}" class="icon"></ha-icon>
                    <span id="title">${esc(card.defaultTitle)}</span>
                </div>
                <div id="content"></div>
            </ha-card>
        `;
        this.content = this.shadowRoot.getElementById("content");
        this.titleElement = this.shadowRoot.getElementById("title");
    }

    _updateTitle(name) {
        if (this.titleElement) {
            this.titleElement.innerText = name || this.constructor.defaultTitle;
        }
    }

    // Sizing for the sections view: the rendered height depends on the data
    // and on the options, so only the card itself can measure it.
    getGridOptions() {
        return { columns: 12, min_columns: 6, rows: "auto" };
    }
}
