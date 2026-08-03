import { normalizeConfig, prepareDepartures } from "./config.js";
import { NaolibCardEditor } from "./editor.js";
import { esc } from "./html.js";
import { renderDepartures } from "./render/departures.js";
import { renderTimetable, renderTimetableHeader } from "./render/timetable.js";
import { styles } from "./styles.js";

// Detect a Naolib sensor by its attributes rather than its entity_id,
// so the card keeps working even if the entity is renamed.
function isNaolibEntity(state) {
    return (
        !!state &&
        state.attributes.stop_code !== undefined &&
        Array.isArray(state.attributes.next_departures)
    );
}

function findNaolibEntity(hass) {
    return Object.keys(hass.states).find((entityId) =>
        isNaolibEntity(hass.states[entityId]),
    );
}

class NaolibCard extends HTMLElement {
    // `hass` can be set before `setConfig` (mobile reconnections), so the card
    // always carries a usable configuration.
    config = normalizeConfig({});

    static getStubConfig(hass) {
        return { entity: findNaolibEntity(hass) || "" };
    }

    static getConfigElement() {
        return document.createElement("naolib-card-editor");
    }

    setConfig(config) {
        this.config = normalizeConfig(config);
        this.toggleAttribute("compact", this.config.compact);
        // Options change what is rendered without the entity state changing,
        // so drop the memoized state to force a redraw.
        this._state = null;
        if (this.content && this._hass) this._updateFromHass(this._hass);
    }

    connectedCallback() {
        // Tick the displayed times down between coordinator refreshes, so
        // the countdown stays accurate (and reaches "proche" on time)
        // instead of aging until the next poll.
        if (this._ticker) return;
        this._ticker = setInterval(() => {
            if (this._showSchedule || !this._state || !this.content) return;
            try {
                this._render();
            } catch (err) {
                console.error("Naolib card: render failed", err);
            }
        }, 20000);
    }

    disconnectedCallback() {
        if (this._ticker) {
            clearInterval(this._ticker);
            this._ticker = null;
        }
    }

    set hass(hass) {
        // Keep a reference for the on-demand timetable WebSocket call.
        this._hass = hass;
        try {
            this._updateFromHass(hass);
        } catch (err) {
            // Never let an exception bubble up to Home Assistant, otherwise
            // the whole card is replaced by a generic "Configuration error".
            // This happens often on mobile where `hass` may be set before
            // `setConfig`, or during frequent reconnections.
            console.error("Naolib card error:", err);
            try {
                if (!this.content) this._initShadowDom();
                this._message(`Erreur : ${esc(err?.message || err)}`);
            } catch (renderErr) {
                // The fallback rendering must not throw either.
                console.error("Naolib card: cannot render error state", renderErr);
            }
        }
    }

    _message(html) {
        this.content.innerHTML = `<div class="no-bus">${html}</div>`;
    }

    _updateFromHass(hass) {
        if (!hass) return;

        const config = this.config;
        const entityId = config.entity || findNaolibEntity(hass);

        if (!this.content) this._initShadowDom();
        if (!entityId) {
            this._message(
                `Aucune entité Naolib trouvée. Ajoutez l'intégration via Paramètres &gt; Appareils et services.`,
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
                state.attributes.stop_label ||
                state.attributes.friendly_name,
        );

        if (!state.attributes.stop_code) {
            this._message("Entité non configurée (stop_code manquant)");
            return;
        }

        // Departures are rendered straight from the sensor attributes:
        // no WebSocket round-trip, so the card displays instantly and
        // survives flaky mobile connections. The WebSocket is only used
        // for the full timetable, on demand (see _fetchSchedules).
        this._render();
    }

    _fetchSchedules() {
        // Fetch the full timetable on demand, only when the schedule view
        // is opened. Guard against concurrent calls.
        if (this._fetching || !this._hass || !this._state) return;
        const stopCode = this._state.attributes.stop_code;
        if (!stopCode) return;

        this._fetching = true;
        this._hass
            .callWS({ type: "naolib/get_data", stop_code: stopCode })
            .then((data) => {
                this._schedules = data?.schedules || {};
                this._schedulesFetched = true;
                if (this._showSchedule) this._render();
            })
            .catch((err) => {
                console.error("Error fetching Naolib schedules:", err);
                if (this._showSchedule) {
                    this.content.innerHTML = `${renderTimetableHeader()}<div class="no-bus">Erreur de chargement des horaires : ${esc(err?.message || err)}</div>`;
                }
            })
            .finally(() => {
                this._fetching = false;
            });
    }

    _initShadowDom() {
        // attachShadow throws if a root is already attached, which happens
        // when a previous call failed after attaching but before filling it.
        if (!this.shadowRoot) this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
            <style>${styles}</style>
            <ha-card>
                <div class="card-header">
                    <ha-icon icon="mdi:bus-clock" class="icon"></ha-icon>
                    <span id="title">Arrêt Naolib</span>
                </div>
                <div id="content"></div>
            </ha-card>
        `;
        this.content = this.shadowRoot.getElementById("content");
        this.titleElement = this.shadowRoot.getElementById("title");

        this.content.addEventListener("click", (ev) => {
            if (ev.target.closest("#schedule-btn")) {
                this._showSchedule = true;
                this._render();
                this._fetchSchedules();
            } else if (ev.target.closest("#back-btn")) {
                this._showSchedule = false;
                this._render();
            }
        });
    }

    _updateTitle(name) {
        if (this.titleElement) this.titleElement.innerText = name || "Arrêt Naolib";
    }

    _render() {
        if (!this._state) {
            this._message("Chargement...");
            return;
        }

        const config = this.config;
        if (this._showSchedule) {
            this.content.innerHTML = renderTimetable(
                this._schedules || {},
                !!this._schedulesFetched,
                config,
            );
            return;
        }

        this.content.innerHTML = renderDepartures(
            prepareDepartures(this._state.attributes.next_departures, config),
            this._state.attributes.stop_code,
            config,
        );
    }

    getCardSize() {
        const departures = prepareDepartures(
            this._state?.attributes?.next_departures ?? [],
            this.config,
        );
        return 2 + Math.ceil(departures.length / (this.config.compact ? 1 : 2));
    }

    // Sizing for the sections view: the rendered height depends on how many
    // line/destination groups the feed returns and doubles when the timetable
    // is open, so only the card itself can measure it.
    getGridOptions() {
        return { columns: 12, min_columns: 6, rows: "auto" };
    }
}

// The loader retries with a fresh query string, so this module can be
// evaluated more than once per page: a second definition is not an error.
function define(tag, elementClass) {
    try {
        customElements.define(tag, elementClass);
    } catch (err) {
        if (!customElements.get(tag)) throw err;
    }
}

define("naolib-card", NaolibCard);
define("naolib-card-editor", NaolibCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "naolib-card")) {
    window.customCards.push({
        type: "naolib-card",
        name: "Naolib Nantes",
        preview: true,
        description: "Affiche les prochains départs (Bus/Tram) pour un arrêt donné.",
    });
}
