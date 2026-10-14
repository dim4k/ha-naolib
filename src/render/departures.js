import { esc } from "../html.js";
import { directionHeading } from "../directions.js";
import { lineBadge, modeLabel } from "../lines.js";
import { message } from "./shared.js";
import { formatClock } from "../time.js";
import {
    DELAY_TOLERANCE_MINUTES,
    ID_SCHEDULE_BTN,
    MS_PER_MINUTE,
    URGENT_MINUTES,
    WARNING_MINUTES,
} from "../constants.js";

function timeClass(minutes) {
    if (minutes <= URGENT_MINUTES) return "time urgent";
    if (minutes <= WARNING_MINUTES) return "time warning";
    return "time";
}

// Departure clock, and the theoretical one struck through next to it when the
// vehicle drifts from the timetable (SIRI Aimed vs Expected). Showing both
// times says how late the bus is *and* when it actually leaves.
function clocksHtml(item) {
    const expected = Date.parse(item.expected_ts);
    if (Number.isNaN(expected)) return "";
    const real = formatClock(new Date(expected));
    const delay = item.delay_minutes;
    if (
        typeof delay !== "number" ||
        Math.abs(delay) < DELAY_TOLERANCE_MINUTES
    ) {
        return `<span class="clock strong">${real}</span>`;
    }
    const aimed = formatClock(new Date(expected - delay * MS_PER_MINUTE));
    const state = delay > 0 ? "late" : "early";
    const title =
        delay > 0
            ? `${delay} min de retard sur l'horaire théorique`
            : `${-delay} min d'avance sur l'horaire théorique`;
    return `<span class="clock aimed">${aimed}</span><span class="clock strong ${state}" title="${title}">${real}</span>`;
}

function isLate(item) {
    return (
        typeof item.delay_minutes === "number" &&
        item.delay_minutes >= DELAY_TOLERANCE_MINUTES
    );
}

function tileRow(departure, timesHtml) {
    return `
        <div class="tile-row">
            ${lineBadge(departure.line)}
            <div class="tile-text">
                <div class="dest">${esc(departure.destination)}</div>
                <div class="tile-mode">${modeLabel(departure.type)}</div>
            </div>
            <div class="times-container">${timesHtml}</div>
        </div>
    `;
}

// The following departure only gets its real clock: a second struck-through
// time would drown the one that matters.
function nextClock(item) {
    const expected = Date.parse(item.expected_ts);
    if (Number.isNaN(expected)) return "";
    const clock = formatClock(new Date(expected));
    return `<span class="clock${isLate(item) ? " late" : ""}">${clock}</span>`;
}

// Second line of a tile: the clocks the countdown stands for, the departure
// after it, and the "last of the day" marker. Tinted so a delay or a last
// departure reads without being parsed.
function stripHtml(first, second) {
    const last = Boolean(first.is_last || second?.is_last);
    const state = isLate(first) ? " late" : last ? " final" : "";
    const next = second
        ? ` · puis ${esc(second.time)} (${nextClock(second)})`
        : "";
    return `
        <div class="strip${state}">
            <span>${clocksHtml(first)}${next}</span>
            ${last ? `<span class="mark" title="Dernier passage prévu aujourd'hui">dernier</span>` : ""}
        </div>
    `;
}

function tileHtml(first, second) {
    const countdown = `<div class="${timeClass(first.minutes)}">${esc(first.time)}</div>`;
    return `
        <div class="tile">
            ${tileRow(first, countdown)}
            ${stripHtml(first, second)}
        </div>
    `;
}

// Compact mode trades the clocks for density: one row per departure, the
// exact time left to the tooltip.
function compactTileHtml(departure) {
    const expected = Date.parse(departure.expected_ts);
    const title = Number.isNaN(expected)
        ? ""
        : ` title="${formatClock(new Date(expected))}"`;
    const mark = departure.is_last ? `<span class="mark">dernier</span>` : "";
    const countdown = `<div class="${timeClass(departure.minutes)}"${title}>${esc(departure.time)}</div>`;
    return `<div class="tile">${tileRow(departure, `${mark}${countdown}`)}</div>`;
}

function groupedTiles(departures, direction, config) {
    const inDirection = departures.filter(
        (item) => item.direction === direction,
    );
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
        .map((group) => tileHtml(group.items[0], group.items[1]))
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
        const tiles = departures.map(compactTileHtml).join("");
        return `<div class="tiles">${tiles}</div>${footerHtml(stopCode, config)}`;
    }

    const sections = [1, 2]
        .filter((direction) =>
            departures.some((item) => item.direction === direction),
        )
        .map(
            (direction) =>
                `<div class="tiles"><div class="tile-group">${esc(directionHeading(departures, direction))}</div>${groupedTiles(departures, direction, config)}</div>`,
        )
        .join("");

    return `${sections}${footerHtml(stopCode, config)}`;
}
