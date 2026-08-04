import { esc } from "../html.js";
import { lineBadge, modeLabel } from "../lines.js";
import { departureMeta, message, timeClass } from "./shared.js";
import { ID_SCHEDULE_BTN } from "../constants.js";

// Clock and "last departure" sit under the countdown they describe: on the
// same line they would read like another departure.
function departureHtml(item, cssClass) {
    const meta = departureMeta(item);
    return `
        <div class="departure">
            <div class="${cssClass}">${esc(item.time)}</div>
            ${meta ? `<div class="departure-meta">${meta}</div>` : ""}
        </div>
    `;
}

function tileHtml(departure, timesHtml) {
    return `
        <div class="tile">
            ${lineBadge(departure.line)}
            <div class="tile-text">
                <div class="dest">${esc(departure.destination)}</div>
                <div class="tile-mode">${modeLabel(departure.type)}</div>
            </div>
            <div class="times-container">${timesHtml}</div>
        </div>
    `;
}

function groupedTiles(departures, direction, config) {
    const inDirection = departures.filter((item) => item.direction === direction);
    if (inDirection.length === 0) return message("Pas de départ");

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
            return tileHtml(group, timesHtml);
        })
        .join("");
}

function footerHtml(stopCode, config) {
    if (!stopCode || !config.show_timetable_button) return "";
    return `
        <div class="card-footer">
            <button type="button" class="button" id="${ID_SCHEDULE_BTN}">
                <ha-icon icon="mdi:clock-outline"></ha-icon>
                Voir tous les horaires
            </button>
        </div>
    `;
}

export function renderDepartures(departures, stopCode, config) {
    if (departures.length === 0) {
        return `${message("Aucun départ proche")}${footerHtml(stopCode, config)}`;
    }

    if (config.compact) {
        const tiles = departures
            .map((departure) =>
                tileHtml(departure, departureHtml(departure, timeClass(departure.minutes))),
            )
            .join("");
        return `<div class="tiles">${tiles}</div>${footerHtml(stopCode, config)}`;
    }

    const sections = [1, 2]
        .filter((direction) =>
            departures.some((item) => item.direction === direction),
        )
        .map(
            (direction) =>
                `<div class="tiles"><div class="tile-group">Direction ${direction}</div>${groupedTiles(departures, direction, config)}</div>`,
        )
        .join("");

    return `${sections}${footerHtml(stopCode, config)}`;
}
