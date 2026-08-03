// Detect a Naolib sensor by its attributes rather than its entity_id,
// so the card keeps working even if the entity is renamed.
function isNaolibEntity(state) {
    return (
        !!state &&
        state.attributes.stop_code !== undefined &&
        Array.isArray(state.attributes.next_departures)
    );
}

// Escape a value before interpolating it into innerHTML. The SIRI feed is
// an external data source: a destination or line name containing markup
// would otherwise be injected straight into the DOM.
function esc(value) {
    return String(value ?? "").replace(
        /[&<>"']/g,
        (c) =>
            ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            })[c]
    );
}

class NaolibCard extends HTMLElement {
    static getStubConfig(hass, entities, entitiesFallback) {
        // Try to find a Naolib sensor by its attributes (not its
        // entity_id), so detection keeps working regardless of naming.
        const entity = Object.keys(hass.states).find((eid) =>
            isNaolibEntity(hass.states[eid])
        );
        return {
            entity: entity || "",
        };
    }

    static getConfigElement() {
        return document.createElement("naolib-card-editor");
    }

    setConfig(config) {
        this.config = config || {};
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
                this.content.innerHTML = `<div class="no-bus">Erreur: ${esc(
                    err && err.message ? err.message : err
                )}</div>`;
            } catch (renderErr) {
                // The fallback rendering must not throw either.
                console.error("Naolib card: cannot render error state", renderErr);
            }
        }
    }

    _updateFromHass(hass) {
        if (!hass) return;

        // `setConfig` may not have run yet (e.g. on mobile reconnections),
        // so guard against a missing config object.
        let entityId = this.config ? this.config.entity : undefined;

        // Fallback: try to find an entity if none is configured
        if (!entityId) {
            const found = Object.keys(hass.states).find((eid) =>
                isNaolibEntity(hass.states[eid])
            );
            if (found) {
                entityId = found;
            }
        }

        if (!this.content) this._initShadowDom();
        if (!entityId) {
            this.content.innerHTML = `<div class="no-bus" style="padding: 16px;">No Naolib entities found. Please add the integration via Settings > Devices &amp; Services.</div>`;
            return;
        }

        const state = hass.states[entityId];

        if (!state || !state.attributes) {
            this.content.innerHTML = `<div class="no-bus">Entity not found: ${esc(
                entityId
            )}</div>`;
            return;
        }

        // Check if state changed to trigger a re-render
        if (
            this._state &&
            this._state.last_updated === state.last_updated &&
            this._state.entity_id === entityId
        )
            return;

        this._state = state;

        this._updateTitle(
            state.attributes.stop_label || state.attributes.friendly_name
        );

        if (!state.attributes.stop_code) {
            this.content.innerHTML = `<div class="no-bus">Entité non configurée (stop_code manquant)</div>`;
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
            .callWS({
                type: "naolib/get_data",
                stop_code: stopCode,
            })
            .then((data) => {
                this._schedules = (data && data.schedules) || {};
                this._schedulesFetched = true;
                if (this._showSchedule) this._render();
            })
            .catch((err) => {
                console.error("Error fetching Naolib schedules:", err);
                if (this._showSchedule) {
                    this.content.innerHTML =
                        this._renderScheduleHeader() +
                        `<div class="no-bus">Erreur de chargement des horaires: ${esc(
                            err && err.message ? err.message : err
                        )}</div>`;
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
            <style>${NaolibCard.styles}</style>
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

        // Event delegation
        this.content.addEventListener("click", (e) => {
            if (e.target.closest("#schedule-btn")) {
                this._showSchedule = true;
                this._render();
                this._fetchSchedules();
            } else if (e.target.closest("#back-btn")) {
                this._showSchedule = false;
                this._render();
            }
        });
    }

    _updateTitle(name) {
        if (this.titleElement)
            this.titleElement.innerText = name || "Arrêt Naolib";
    }

    _render() {
        if (!this._state) {
            this.content.innerHTML = `<div class="no-bus">Chargement...</div>`;
            return;
        }

        if (this._showSchedule) {
            this.content.innerHTML = this._renderSchedule(
                this._schedules || {},
                !!this._schedulesFetched
            );
        } else {
            this.content.innerHTML = this._renderDepartures(
                this._state.attributes.next_departures || [],
                this._state.attributes.stop_code
            );
        }
    }

    _renderDepartures(departures, stopCode) {
        departures = this._withLiveTimes(departures);
        if (departures.length === 0) {
            return (
                `<div class="no-bus">Aucun départ proche</div>` +
                this._renderFooter(stopCode)
            );
        }

        const hasDir1 = departures.some((p) => p.direction === 1 && p.time);
        const hasDir2 = departures.some((p) => p.direction === 2 && p.time);

        const dir1Html = hasDir1
            ? `<div class="direction-header">Direction 1</div>${this._renderRows(departures, 1)}`
            : "";
        const dir2Html = hasDir2
            ? `<div class="direction-header">Direction 2</div>${this._renderRows(departures, 2)}`
            : "";

        return `
            ${dir1Html}
            ${dir2Html}
            ${this._renderFooter(stopCode)}
        `;
    }

    _renderFooter(stopCode) {
        if (!stopCode) return "";
        return `
            <div class="card-footer">
                <div class="button" id="schedule-btn">
                    <ha-icon icon="mdi:clock-outline"></ha-icon>
                    Voir tous les horaires
                </div>
            </div>
        `;
    }

    _renderRows(departures, direction) {
        const busDirection = departures.filter(
            (p) => p.direction === direction && p.time
        );
        if (busDirection.length === 0)
            return `<div class="no-bus">Pas de départ</div>`;

        // Group by Line + Destination
        const groups = {};
        busDirection.forEach((bus) => {
            const key = `${bus.line}-${bus.destination}`;
            if (!groups[key]) {
                groups[key] = { ...bus, items: [] };
            }
            groups[key].items.push(bus);
        });

        // Convert to array and sort by first time
        const sortedGroups = Object.values(groups).sort((a, b) => {
            return (
                this._parseTime(a.items[0].time) -
                this._parseTime(b.items[0].time)
            );
        });

        return sortedGroups
            .map((group) => {
                const first = group.items[0];
                const second = group.items[1]; // Only take the second one if exists

                // "proche" or <=1 min => urgent (red), 2-3 min => warning (orange).
                const isProche = /proche/i.test(first.time);
                const minutes = this._parseTime(first.time);
                const isUrgent = isProche || minutes <= 1;
                const isWarning = !isUrgent && minutes <= 3;

                let timeHtml = this._departureHtml(
                    first,
                    `time ${isUrgent ? "urgent" : isWarning ? "warning" : ""}`
                );
                if (second) {
                    timeHtml += this._departureHtml(second, "time-secondary");
                }

                return `
                <div class="row">
                    <ha-icon icon="${this._getIconForType(
                        group.type
                    )}" class="mode-icon"></ha-icon>
                    <div class="badge" style="background-color: ${this._getLineColor(
                        group.line
                    )}; color: ${this._getLineTextColor(
                    group.line
                )};" title="Ligne ${esc(group.line)}">${esc(
                    group.line
                )}</div>
                    <div class="dest">${esc(group.destination)}</div>
                    <div class="times-container">
                        ${timeHtml}
                    </div>
                </div>
            `;
            })
            .join("");
    }

    // Delay and "last departure" sit under the time they describe: on the
    // same line they read like another departure.
    _departureHtml(item, timeClass) {
        const meta = `${this._delayBadge(item.delay_minutes)}${this._lastBadge(
            item.is_last
        )}`;
        return `
            <div class="departure">
                <div class="${timeClass}">${esc(item.time)}</div>
                ${meta ? `<div class="departure-meta">${meta}</div>` : ""}
            </div>
        `;
    }

    _parseTime(timeStr) {
        if (!timeStr) return 9999;
        if (timeStr.includes("proche")) return 0;
        const match = timeStr.match(/(\d+)\s*(mn|h)/);
        if (!match) return 9999;
        let val = parseInt(match[1]);
        if (match[2] === "h") val *= 60;
        return val;
    }

    // Recompute the humanized times from the raw timestamps, so the card
    // ticks down between coordinator refreshes. Departures more than 60 s
    // in the past are dropped (mirrors the backend filter).
    _withLiveTimes(departures) {
        const now = Date.now();
        const out = [];
        for (const d of departures) {
            if (!d.expected_ts) {
                out.push(d);
                continue;
            }
            const delta = (Date.parse(d.expected_ts) - now) / 1000;
            if (delta < -60) continue;
            out.push({ ...d, time: this._humanizeSeconds(delta) });
        }
        return out;
    }

    // Same output format as the backend _humanize().
    _humanizeSeconds(delta) {
        if (delta <= 60) return "proche";
        const minutes = Math.floor(delta / 60);
        if (minutes < 60) return `${minutes} mn`;
        const hours = Math.floor(minutes / 60);
        return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
    }

    // Delay vs the theoretical timetable (SIRI Aimed vs Expected).
    _delayBadge(delay) {
        if (typeof delay !== "number") return "";
        if (delay >= 2)
            return `<div class="time-meta late" title="Retard vs horaire théorique">+${delay} min</div>`;
        if (delay <= -2)
            return `<div class="time-meta early" title="Avance vs horaire théorique">${delay} min</div>`;
        return "";
    }

    // Last scheduled passage of the day (from the GTFS timetable; the
    // realtime feed does not expose it).
    _lastBadge(isLast) {
        if (!isLast) return "";
        return `<div class="time-meta last" title="Dernier passage prévu aujourd'hui">dernier</div>`;
    }

    _renderSchedule(schedules, fetched) {
        if (Object.keys(schedules).length === 0) {
            // Distinguish "still loading" from "no service today" (e.g.
            // Sunday or holiday), which also returns an empty timetable.
            return `
                ${this._renderScheduleHeader()}
                <div class="no-bus">${
                    fetched
                        ? "Aucun horaire aujourd'hui"
                        : "Chargement des horaires..."
                }</div>
            `;
        }

        const sortedKeys = Object.keys(schedules).sort((a, b) => {
            const lineA = schedules[a].ligne.numLigne;
            const lineB = schedules[b].ligne.numLigne;
            return lineA.localeCompare(lineB, undefined, { numeric: true });
        });

        const listHtml = sortedKeys
            .map((key) => {
                const data = schedules[key];
                const line = data.ligne.numLigne;
                const direction =
                    data.direction_label || `Sens ${data.ligne.direction}`;

                let timesHtml = "";
                if (data.horaires) {
                    // Departures come grouped by hour; sort them with the
                    // small hours after midnight last.
                    const horairesList = Object.keys(data.horaires)
                        .map((h) => ({ heure: h, passages: data.horaires[h] }))
                        .sort((a, b) => {
                            let hA = parseInt(a.heure);
                            let hB = parseInt(b.heure);
                            if (hA < 4) hA += 24;
                            if (hB < 4) hB += 24;
                            return hA - hB;
                        });

                    timesHtml = horairesList
                        .map(
                            (h) => `
                    <div class="schedule-item">
                        <div class="schedule-hour">${esc(h.heure)}</div>
                        <div class="schedule-min">${esc(
                            h.passages.join(" ")
                        )}</div>
                    </div>
                `
                        )
                        .join("");
                }

                return `
                <div class="schedule-group">
                    <div class="schedule-line-header">
                        <div class="badge" style="background-color: ${this._getLineColor(
                            line
                        )}; color: ${this._getLineTextColor(
                            line
                        )}; margin-right: 10px;">${esc(line)}</div>
                        <div class="schedule-dest">Vers ${esc(direction)}</div>
                    </div>
                    <div class="schedule-grid">${timesHtml}</div>
                </div>
            `;
            })
            .join("");

        return `
            ${this._renderScheduleHeader()}
            <div class="schedule-container">${listHtml}</div>
        `;
    }

    _renderScheduleHeader() {
        return `
            <div class="card-header schedule-header">
                <ha-icon icon="mdi:arrow-left" class="icon" id="back-btn"></ha-icon>
                <span>Horaires</span>
            </div>
        `;
    }

    _getLineColor(line) {
        const colors = {
            1: "#00A754",
            2: "#E30612",
            3: "#2481C3",
            4: "#FDC600",
            5: "#0BBBEF",
            C1: "#0BBBEF",
            C2: "#EE7402",
            C3: "#F7A600",
            C4: "#76B82A",
            C6: "#A877B2",
            C7: "#C8D300",
            C8: "#C8D300",
            C9: "#F5B5D3",
            C20: "#FFED00",
            NA: "#2ecc71",
        };
        return colors[line] || "var(--primary-color)";
    }

    _getLineTextColor(line) {
        // Dark text on light badge backgrounds (white is unreadable on
        // yellow/lime/pink lines, e.g. C20).
        const darkText = ["4", "C4", "C7", "C8", "C9", "C20"];
        return darkText.includes(String(line)) ? "#1a1a1a" : "#ffffff";
    }

    _getIconForType(type) {
        const icons = {
            1: "mdi:tram",
            2: "mdi:bus-articulated-front",
            3: "mdi:bus",
            4: "mdi:ferry",
        };
        return icons[type] || "mdi:bus";
    }

    getCardSize() {
        return 3;
    }

    static get styles() {
        return `
            :host { font-family: Roboto, sans-serif; }
            .card-header { padding: 16px; font-weight: bold; font-size: 1.2em; display: flex; align-items: center; }
            .schedule-header { border-bottom: 1px solid var(--divider-color); padding-bottom: 10px; margin-bottom: 10px; }
            .icon { margin-right: 10px; color: var(--primary-color); }
            #back-btn { cursor: pointer; }
            .direction-header { font-size: 0.85em; text-transform: uppercase; color: var(--secondary-text-color); margin: 10px 16px 5px; border-bottom: 1px solid var(--divider-color); padding-bottom: 4px; letter-spacing: 1px; }
            .row { display: flex; align-items: center; padding: 8px 16px; border-bottom: 1px solid rgba(127,127,127, 0.1); }
            .badge { background-color: var(--primary-color); color: white; font-weight: bold; padding: 4px 8px; border-radius: 6px; min-width: 25px; text-align: center; margin-right: 12px; font-size: 1.1em; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
            .mode-icon { color: var(--secondary-text-color); margin-right: 8px; --mdc-icon-size: 20px; }
            .dest { flex-grow: 1; font-size: 1.05em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-right: 10px; }
            .time { font-weight: bold; font-size: 1.1em; padding: 4px 8px; border-radius: 4px; white-space: nowrap; background: rgba(127,127,127,0.1); color: var(--primary-text-color); }
            .urgent { background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; }
            .warning { background-color: rgba(241, 196, 15, 0.2); color: #f1c40f; }
            .no-bus { padding: 10px 16px; font-style: italic; color: var(--secondary-text-color); text-align: center; }
            .card-footer { padding: 8px 16px; text-align: center; border-top: 1px solid var(--divider-color); }
            .button { display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--primary-color); font-weight: 500; padding: 6px 12px; border-radius: 4px; transition: background 0.2s; }
            .button:hover { background-color: rgba(var(--rgb-primary-color), 0.1); }
            .button ha-icon { margin-right: 6px; --mdc-icon-size: 18px; }
            .schedule-container { padding: 0 16px 16px; max-height: 400px; overflow-y: auto; }
            .schedule-group { margin-bottom: 20px; }
            .schedule-line-header { display: flex; align-items: center; margin-bottom: 8px; border-bottom: 1px solid rgba(127,127,127,0.1); padding-bottom: 4px; }
            .schedule-dest { font-weight: 500; font-size: 1.1em; }
            .schedule-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(60px, 1fr)); gap: 8px; }
            .schedule-item { background: rgba(127,127,127, 0.1); padding: 4px; border-radius: 4px; text-align: center; font-size: 0.9em; }
            .schedule-hour { font-weight: bold; color: var(--primary-color); }
            .schedule-min { color: var(--secondary-text-color); }
            /* Two-row grid so every marker lines up, whatever the height of
               the time above it. */
            .times-container { display: grid; grid-auto-flow: column; grid-template-rows: auto auto; column-gap: 10px; justify-items: end; align-items: center; }
            .departure { display: contents; }
            .departure > .time, .departure > .time-secondary { grid-row: 1; }
            .departure-meta { grid-row: 2; display: flex; gap: 4px; margin-top: 4px; }
            .time-secondary { font-size: 0.9em; color: var(--secondary-text-color); font-weight: normal; padding: 4px 0; }
            .time-meta { font-size: 0.65em; font-weight: 700; white-space: nowrap; padding: 2px 6px; border-radius: 10px; }
            .time-meta.late { background: rgba(231, 76, 60, 0.18); color: #e74c3c; }
            .time-meta.early { background: rgba(39, 174, 96, 0.18); color: #27ae60; }
            .time-meta.last { background: rgba(127,127,127,0.15); color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
            ha-card { padding-bottom: 0; overflow: hidden; }
        `;
    }
}

// The loader retries with a fresh query string, so this module can be
// evaluated more than once per page: a second definition is not an error.
try {
    customElements.define("naolib-card", NaolibCard);
} catch (err) {
    if (!customElements.get("naolib-card")) throw err;
}

class NaolibCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = config;
        if (this.content) {
            const picker = this.content.querySelector("ha-entity-picker");
            if (picker) picker.value = config.entity;
        }
    }

    set hass(hass) {
        this._hass = hass;
        if (!this.content) {
            this._init();
        }
    }

    _init() {
        this.content = document.createElement("div");
        this.content.innerHTML = `
            <div class="card-config">
                <ha-entity-picker
                    label="Entité (arrêt Naolib)"
                    domain-filter="sensor"
                    include-domains='["sensor"]'
                ></ha-entity-picker>
            </div>
        `;
        this.appendChild(this.content);

        const picker = this.content.querySelector("ha-entity-picker");
        picker.hass = this._hass;
        if (this._config) {
            picker.value = this._config.entity;
        }
        // Listen to both events: newer HA versions fire "change" on
        // pickers, older ones fire "value-changed".
        picker.addEventListener("change", this._valueChanged.bind(this));
        picker.addEventListener("value-changed", this._valueChanged.bind(this));
    }

    _valueChanged(ev) {
        if (!this._hass) return;
        const target = ev.target;
        if (this._config && this._config.entity === target.value) return;

        this._config = {
            ...this._config,
            entity: target.value,
        };

        const event = new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
        });
        this.dispatchEvent(event);
    }
}

try {
    customElements.define("naolib-card-editor", NaolibCardEditor);
} catch (err) {
    if (!customElements.get("naolib-card-editor")) throw err;
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "naolib-card")) {
    window.customCards.push({
        type: "naolib-card",
        name: "Naolib Nantes",
        preview: true,
        description:
            "Affiche les prochains départs (Bus/Tram) pour un arrêt donné.",
    });
}
