import { normalizeConfig, prepareDepartures } from "./config.js";
import { NaolibCardEditor } from "./editor.js";
import { esc } from "./html.js";
import { renderDepartures } from "./render/departures.js";
import { renderTimetable, renderTimetableHeader } from "./render/timetable.js";
import { message } from "./render/shared.js";
import { styles } from "./styles/index.js";
import {
    ATTR_DAY,
    ATTR_DIRECTION,
    ATTR_KEEP_SCROLL,
    ATTR_LINE,
    ID_BACK_BTN,
    ID_SCHEDULE_BTN,
    MAX_DAY_OFFSET,
    TICK_MS,
} from "./constants.js";

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

    // Timetable view state, kept in memory only: the selected line, the
    // direction remembered for each line and the day being browsed.
    _selectedLine = null;
    _directionByLine = new Map();
    _dayOffset = 0;
    // Timetables are fetched and cached per day browsed.
    _schedulesByDay = new Map();
    _fetchedDays = new Set();
    _fetchingDays = new Set();

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
        // instead of aging until the next poll. The timetable view ticks too:
        // its clock and countdowns would drift otherwise.
        if (this._ticker) return;
        this._ticker = setInterval(() => {
            if (!this._state || !this.content) return;
            try {
                this._render();
            } catch (err) {
                console.error("Naolib card: render failed", err);
            }
        }, TICK_MS);
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
        this.content.innerHTML = message(html);
    }

    // Replacing innerHTML wholesale loses the scroll position of the timetable
    // containers, which the 20 s ticker would then reset on every pass.
    _setContent(html) {
        const saved = new Map();
        for (const node of this.content.querySelectorAll(`[${ATTR_KEEP_SCROLL}]`)) {
            saved.set(node.getAttribute(ATTR_KEEP_SCROLL), {
                top: node.scrollTop,
                left: node.scrollLeft,
            });
        }

        this.content.innerHTML = html;

        for (const node of this.content.querySelectorAll(`[${ATTR_KEEP_SCROLL}]`)) {
            const position = saved.get(node.getAttribute(ATTR_KEEP_SCROLL));
            if (position) {
                node.scrollTop = position.top;
                node.scrollLeft = position.left;
            }
        }

        if (this._scrollToCurrentHour) {
            // The grid is absent while the timetable is still loading; keep the
            // request pending until it can actually be honoured.
            this._scrollToCurrentHour = !this._scrollHoursToCurrent();
        }
    }

    _scrollHoursToCurrent() {
        const body = this.content.querySelector(".tt-hours");
        if (!body) return false;
        const cell = body.querySelector(".tt-cell.now");
        // Another day has no current hour: start from the first departure.
        body.scrollTop = cell ? Math.max(0, cell.offsetTop - 4) : 0;
        return true;
    }

    _resetScheduleState() {
        this._schedulesByDay = new Map();
        this._fetchedDays = new Set();
        this._selectedLine = null;
        this._directionByLine = new Map();
        this._dayOffset = 0;
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

        // A different stop invalidates the cached timetable and any selection
        // made against it.
        if (
            this._state &&
            (this._state.entity_id !== entityId ||
                this._state.attributes.stop_code !== state.attributes.stop_code)
        ) {
            this._resetScheduleState();
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

    _fetchSchedules(dayOffset) {
        // Fetch the full timetable on demand, only when the schedule view
        // is opened, and once per day browsed.
        if (!this._hass || !this._state) return;
        if (this._fetchedDays.has(dayOffset) || this._fetchingDays.has(dayOffset)) {
            return;
        }
        const stopCode = this._state.attributes.stop_code;
        if (!stopCode) return;

        this._fetchingDays.add(dayOffset);
        this._hass
            .callWS({
                type: "naolib/get_data",
                stop_code: stopCode,
                day_offset: dayOffset,
            })
            .then((data) => {
                this._schedulesByDay.set(dayOffset, data?.schedules || {});
                this._fetchedDays.add(dayOffset);
                if (this._showSchedule) this._render();
            })
            .catch((err) => {
                console.error("Error fetching Naolib schedules:", err);
                if (this._showSchedule) {
                    this.content.innerHTML = `${renderTimetableHeader()}${message(
                        `Erreur de chargement des horaires : ${esc(err?.message || err)}`,
                    )}`;
                }
            })
            .finally(() => {
                this._fetchingDays.delete(dayOffset);
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
            try {
                this._handleClick(ev);
            } catch (err) {
                console.error("Naolib card: interaction failed", err);
            }
        });
    }

    _handleClick(ev) {
        const target = ev.target;

        if (target.closest(`#${ID_SCHEDULE_BTN}`)) {
            this._showSchedule = true;
            this._dayOffset = 0;
            this._scrollToCurrentHour = true;
            this._render();
            this._fetchSchedules(0);
            return;
        }

        if (target.closest(`#${ID_BACK_BTN}`)) {
            this._showSchedule = false;
            this._render();
            return;
        }

        const chip = target.closest(`[${ATTR_LINE}]`);
        if (chip) {
            this._selectedLine = chip.getAttribute(ATTR_LINE);
            this._scrollToCurrentHour = true;
            this._render();
            return;
        }

        const day = target.closest(`[${ATTR_DAY}]`);
        if (day) {
            const offset = Number(day.getAttribute(ATTR_DAY));
            if (Number.isNaN(offset) || offset < 0 || offset > MAX_DAY_OFFSET) return;
            this._dayOffset = offset;
            this._scrollToCurrentHour = true;
            this._render();
            this._fetchSchedules(offset);
            return;
        }

        const direction = target.closest(`[${ATTR_DIRECTION}]`);
        if (direction) {
            // The rendered chip is the source of truth: the line may still be
            // the default one, never explicitly picked by the user.
            const line =
                this._selectedLine ??
                this.content.querySelector(".tt-chip.selected")?.getAttribute(ATTR_LINE);
            if (line === undefined || line === null) return;
            this._selectedLine = line;
            this._directionByLine.set(
                line,
                Number(direction.getAttribute(ATTR_DIRECTION)),
            );
            this._scrollToCurrentHour = true;
            this._render();
        }
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
            this._setContent(
                renderTimetable({
                    schedules: this._schedulesByDay.get(this._dayOffset) || {},
                    fetched: this._fetchedDays.has(this._dayOffset),
                    config,
                    selectedLine: this._selectedLine,
                    directionByLine: this._directionByLine,
                    dayOffset: this._dayOffset,
                }),
            );
            return;
        }

        this._setContent(
            renderDepartures(
                prepareDepartures(this._state.attributes.next_departures, config),
                this._state.attributes.stop_code,
                config,
            ),
        );
    }

    getCardSize() {
        // Header, chips, direction row and the scroll-capped hour grid.
        if (this._showSchedule) return 10;

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
