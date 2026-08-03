import { esc } from "../html.js";
import { lineBadge, modeIcon } from "../lines.js";

// Delay vs the theoretical timetable (SIRI Aimed vs Expected).
function delayBadge(delay) {
    if (typeof delay !== "number") return "";
    if (delay >= 2) {
        return `<div class="time-meta late" title="Retard vs horaire théorique">+${delay} min</div>`;
    }
    if (delay <= -2) {
        return `<div class="time-meta early" title="Avance vs horaire théorique">${delay} min</div>`;
    }
    return "";
}

// Last scheduled passage of the day (from the GTFS timetable; the realtime
// feed does not expose it).
function lastBadge(isLast) {
    if (!isLast) return "";
    return `<div class="time-meta last" title="Dernier passage prévu aujourd'hui">dernier</div>`;
}

function timeClass(minutes) {
    // <=1 min => urgent (red), 2-3 min => warning (orange).
    if (minutes <= 1) return "time urgent";
    if (minutes <= 3) return "time warning";
    return "time";
}

// Delay and "last departure" sit under the time they describe: on the same
// line they read like another departure.
function departureHtml(item, cssClass) {
    const meta = `${delayBadge(item.delay_minutes)}${lastBadge(item.is_last)}`;
    return `
        <div class="departure">
            <div class="${cssClass}">${esc(item.time)}</div>
            ${meta ? `<div class="departure-meta">${meta}</div>` : ""}
        </div>
    `;
}

function rowHtml(departure, timesHtml) {
    return `
        <div class="row">
            <ha-icon icon="${modeIcon(departure.type)}" class="mode-icon"></ha-icon>
            ${lineBadge(departure.line)}
            <div class="dest">${esc(departure.destination)}</div>
            <div class="times-container">${timesHtml}</div>
        </div>
    `;
}

function groupedRows(departures, direction, config) {
    const inDirection = departures.filter((item) => item.direction === direction);
    if (inDirection.length === 0) return `<div class="no-bus">Pas de départ</div>`;

    const groups = {};
    for (const departure of inDirection) {
        const key = `${departure.line}-${departure.destination}`;
        if (!groups[key]) groups[key] = { ...departure, items: [] };
        groups[key].items.push(departure);
    }

    return Object.values(groups)
        .sort((a, b) => a.items[0].minutes - b.items[0].minutes)
        .slice(0, config.max_lines)
        .map((group) => {
            const [first, second] = group.items;
            let timesHtml = departureHtml(first, timeClass(first.minutes));
            if (second) timesHtml += departureHtml(second, "time-secondary");
            return rowHtml(group, timesHtml);
        })
        .join("");
}

function footerHtml(stopCode, config) {
    if (!stopCode || !config.show_timetable_button) return "";
    return `
        <div class="card-footer">
            <button type="button" class="button" id="schedule-btn">
                <ha-icon icon="mdi:clock-outline"></ha-icon>
                Voir tous les horaires
            </button>
        </div>
    `;
}

export function renderDepartures(departures, stopCode, config) {
    if (departures.length === 0) {
        return `<div class="no-bus">Aucun départ proche</div>${footerHtml(stopCode, config)}`;
    }

    if (config.compact) {
        const rows = departures
            .map((departure) =>
                rowHtml(departure, departureHtml(departure, timeClass(departure.minutes))),
            )
            .join("");
        return `${rows}${footerHtml(stopCode, config)}`;
    }

    const sections = [1, 2]
        .filter((direction) =>
            departures.some((item) => item.direction === direction),
        )
        .map(
            (direction) =>
                `<div class="direction-header">Direction ${direction}</div>${groupedRows(departures, direction, config)}`,
        )
        .join("");

    return `${sections}${footerHtml(stopCode, config)}`;
}
