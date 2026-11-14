import { NaolibBaseCard } from "./base-card.js";
import { normalizeConfig, prepareDepartures } from "./config.js";
import { isDepartureEntity } from "./entities.js";
import { errorText } from "./html.js";
import { renderDepartures } from "./render/departures.js";
import { renderTimetable, renderTimetableHeader } from "./render/timetable.js";
import { LOADING, message } from "./render/shared.js";
import { TimetableCache } from "./timetable-cache.js";
import {
    ATTR_DAY,
    ATTR_DIRECTION,
    ATTR_KEEP_SCROLL,
    ATTR_LINE,
    ID_BACK_BTN,
    ID_SCHEDULE_BTN,
    MAX_DAY_OFFSET,
} from "./constants.js";

export class NaolibCard extends NaolibBaseCard {
    // A Naolib sensor is detected by its attributes rather than its
    // entity_id, so the card keeps working even if the entity is renamed.
    static normalizeConfig = normalizeConfig;
    static acceptsEntity = isDepartureEntity;
    static idAttribute = "stop_code";
    static labelAttribute = "stop_label";
    static icon = "mdi:bus-clock";
    static defaultTitle = "Arrêt Naolib";
    static noEntityMessage =
        "Aucune entité Naolib trouvée. Ajoutez l'intégration via Paramètres &gt; Appareils et services.";
    static logLabel = "Naolib card";
    // The timetable view ticks too: its clock and countdowns would drift.
    static ticks = true;

    // Timetable view state, kept in memory only: the selected line, the
    // direction remembered for each line and the day being browsed.
    _selectedLine = null;
    _directionByLine = new Map();
    _dayOffset = 0;
    // Timetables are fetched and cached per day browsed.
    _timetables = new TimetableCache();

    static getConfigElement() {
        return document.createElement("naolib-card-editor");
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
        this._timetables.clear();
        this._selectedLine = null;
        this._directionByLine = new Map();
        this._dayOffset = 0;
    }

    // A different stop invalidates the cached timetable and any selection
    // made against it.
    _onStateChange(previous, state) {
        if (
            previous &&
            (previous.entity_id !== state.entity_id ||
                previous.attributes.stop_code !== state.attributes.stop_code)
        ) {
            this._resetScheduleState();
        }
    }

    _fetchSchedules(dayOffset) {
        // Fetch the full timetable on demand, only when the schedule view
        // is opened, and once per day browsed.
        if (!this._hass || !this._state) return;
        const stopCode = this._state.attributes.stop_code;
        if (!stopCode) return;
        const settle = this._timetables.begin(dayOffset);
        if (!settle) return;

        this._hass
            .callWS({
                type: "naolib/timetable",
                stop_code: stopCode,
                day_offset: dayOffset,
            })
            .then((data) => {
                // An answer for a stop or a day since dropped is ignored.
                if (settle(data ?? {}) && this._showSchedule) this._render();
            })
            .catch((err) => {
                console.error("Error fetching Naolib schedules:", err);
                if (settle() && this._showSchedule) {
                    this.content.innerHTML = `${renderTimetableHeader()}${message(
                        `Erreur de chargement des horaires : ${errorText(err)}`,
                    )}`;
                }
            });
    }

    _initShadowDom() {
        super._initShadowDom();
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

    _render() {
        if (!this._state) {
            this._message(LOADING);
            return;
        }

        const config = this.config;
        if (this._showSchedule) {
            // Past midnight "today" is another day: fetch it again.
            if (this._timetables.rollover()) this._fetchSchedules(this._dayOffset);
            this._setContent(
                renderTimetable({
                    schedules: this._timetables.timetable(this._dayOffset),
                    fetched: this._timetables.isFetched(this._dayOffset),
                    expired: this._timetables.isExpired(this._dayOffset),
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
}
