class TanNantesCard extends HTMLElement {
    static getStubConfig() {
        return { entity: "sensor.tan_next_commerce" };
    }

    setConfig(config) {
        if (!config.entity) throw new Error("You must define an entity");
        this.config = config;
    }

    set hass(hass) {
        const entityId = this.config.entity;
        const state = hass.states[entityId];

        if (!state || this._state === state) return;
        this._state = state;

        if (!this.content) this._initShadowDom();

        this._updateTitle(state.attributes.friendly_name);
        this._render();
    }

    _initShadowDom() {
        this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
            <style>${TanNantesCard.styles}</style>
            <ha-card>
                <div class="card-header">
                    <ha-icon icon="mdi:bus-clock" class="icon"></ha-icon>
                    <span id="title">Arrêt Tan</span>
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
            } else if (e.target.closest("#back-btn")) {
                this._showSchedule = false;
                this._render();
            }
        });
    }

    _updateTitle(name) {
        if (this.titleElement)
            this.titleElement.innerText = name || "Arrêt Tan";
    }

    _render() {
        const attrs = this._state.attributes;
        if (this._showSchedule) {
            this.content.innerHTML = this._renderSchedule(
                attrs.schedules || {}
            );
        } else {
            this.content.innerHTML = this._renderDepartures(
                attrs.next_departures || [],
                attrs.stop_code
            );
        }
    }

    _renderDepartures(departures, stopCode) {
        if (departures.length === 0) {
            return (
                `<div class="no-bus">Aucun départ proche</div>` +
                this._renderFooter(stopCode)
            );
        }

        return `
            <div class="direction-header">Direction 1</div>
            ${this._renderRows(departures, 1)}
            <div class="direction-header">Direction 2</div>
            ${this._renderRows(departures, 2)}
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
                groups[key] = { ...bus, times: [] };
            }
            groups[key].times.push(bus.time);
        });

        // Convert to array and sort by first time
        const sortedGroups = Object.values(groups).sort((a, b) => {
            return this._parseTime(a.times[0]) - this._parseTime(b.times[0]);
        });

        return sortedGroups
            .map((group) => {
                const time1 = group.times[0];
                const time2 = group.times[1]; // Only take the second one if exists

                const isWarning = /(^|\D)[23](mn|')/.test(time1);
                const isUrgent =
                    time1.includes("proche") || /(^|\D)1(mn|')/.test(time1);

                const trafficIcon = group.traffic_info
                    ? `<ha-icon icon="mdi:alert-circle" class="traffic-warning" title="${(
                          group.traffic_message || "Info trafic"
                      ).replace(/"/g, "&quot;")}"></ha-icon>`
                    : "";

                let timeHtml = `<div class="time ${
                    isUrgent ? "urgent" : isWarning ? "warning" : ""
                }">${time1}</div>`;
                if (time2) {
                    timeHtml += `<div class="time-secondary">${time2}</div>`;
                }

                return `
                <div class="row">
                    <ha-icon icon="${this._getIconForType(
                        group.type
                    )}" class="mode-icon"></ha-icon>
                    <div class="badge" style="background-color: ${this._getLineColor(
                        group.line
                    )};" title="Ligne ${group.line}">${group.line}</div>
                    <div class="dest">${group.destination}${trafficIcon}</div>
                    <div class="times-container">
                        ${timeHtml}
                    </div>
                </div>
            `;
            })
            .join("");
    }

    _parseTime(timeStr) {
        if (!timeStr) return 9999;
        if (timeStr.includes("proche")) return 0;
        const match = timeStr.match(/(\d+)(mn|h)/);
        if (!match) return 9999;
        let val = parseInt(match[1]);
        if (match[2] === "h") val *= 60;
        return val;
    }

    _renderSchedule(schedules) {
        if (Object.keys(schedules).length === 0) {
            return `
                ${this._renderScheduleHeader()}
                <div class="no-bus">Chargement des horaires...</div>
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
                    timesHtml = data.horaires
                        .map(
                            (h) => `
                    <div class="schedule-item">
                        <div class="schedule-hour">${h.heure}</div>
                        <div class="schedule-min">${h.passages.join(" ")}</div>
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
                        )}; margin-right: 10px;">${line}</div>
                        <div class="schedule-dest">Vers ${direction}</div>
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
            .traffic-warning { color: #f39c12; margin-left: 5px; vertical-align: middle; }
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
            .times-container { display: flex; align-items: center; }
            .time-secondary { font-size: 0.9em; color: var(--secondary-text-color); margin-left: 8px; font-weight: normal; }
            ha-card { padding-bottom: 0; overflow: hidden; }
        `;
    }
}

customElements.define("tan-nantes-card", TanNantesCard);

window.customCards = window.customCards || [];
window.customCards.push({
    type: "tan-nantes-card",
    name: "Tan Nantes",
    preview: true,
    description:
        "Affiche les prochains départs (Bus/Tram) pour un arrêt donné.",
});
