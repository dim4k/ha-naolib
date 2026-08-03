import { esc } from "../html.js";
import { matchesFilters } from "../config.js";
import { lineBadge } from "../lines.js";

export function renderTimetableHeader() {
    return `
        <div class="card-header schedule-header">
            <button type="button" class="icon-button" id="back-btn" aria-label="Retour aux prochains départs">
                <ha-icon icon="mdi:arrow-left"></ha-icon>
            </button>
            <span>Horaires</span>
        </div>
    `;
}

function hourRows(horaires) {
    if (!horaires) return "";
    // Departures come grouped by hour; sort them with the small hours after
    // midnight last.
    return Object.keys(horaires)
        .map((hour) => ({ hour, passages: horaires[hour] }))
        .sort((a, b) => {
            const hourA = parseInt(a.hour, 10);
            const hourB = parseInt(b.hour, 10);
            return (hourA < 4 ? hourA + 24 : hourA) - (hourB < 4 ? hourB + 24 : hourB);
        })
        .map(
            (entry) => `
                <div class="schedule-item">
                    <div class="schedule-hour">${esc(entry.hour)}</div>
                    <div class="schedule-min">${esc(entry.passages.join(" "))}</div>
                </div>
            `,
        )
        .join("");
}

export function renderTimetable(schedules, fetched, config) {
    // Group keys are "{line}|{direction}"; the payload itself only carries the
    // destination label, so the direction is read back from the key.
    const keys = Object.keys(schedules).filter((key) => {
        const [line, direction] = key.split("|");
        return matchesFilters(line, direction, config);
    });

    if (keys.length === 0) {
        // Distinguish "still loading" from "no service today" (e.g. Sunday or
        // holiday), which also returns an empty timetable.
        const message = fetched
            ? "Aucun horaire aujourd'hui"
            : "Chargement des horaires...";
        return `${renderTimetableHeader()}<div class="no-bus">${message}</div>`;
    }

    const listHtml = keys
        .sort((a, b) =>
            String(schedules[a].ligne.numLigne).localeCompare(
                String(schedules[b].ligne.numLigne),
                undefined,
                { numeric: true },
            ),
        )
        .map((key) => {
            const data = schedules[key];
            const line = data.ligne.numLigne;
            const direction = data.direction_label || `Sens ${data.ligne.direction}`;
            return `
                <div class="schedule-group">
                    <div class="schedule-line-header">
                        ${lineBadge(line)}
                        <div class="schedule-dest">Vers ${esc(direction)}</div>
                    </div>
                    <div class="schedule-grid">${hourRows(data.horaires)}</div>
                </div>
            `;
        })
        .join("");

    return `${renderTimetableHeader()}<div class="schedule-container">${listHtml}</div>`;
}
