import { esc } from "../html.js";
import { matchesFilters } from "../config.js";
import { lineBadge } from "../lines.js";
import { message } from "./shared.js";
import {
    formatClock,
    formatDay,
    humanizeSeconds,
    passageDate,
    relativeDay,
    serviceHourKey,
} from "../time.js";
import {
    ATTR_DAY,
    ATTR_DIRECTION,
    ATTR_KEEP_SCROLL,
    ATTR_LINE,
    ID_BACK_BTN,
    MAX_DAY_OFFSET,
} from "../constants.js";

// `extra` lets the caller drop the line chips next to the title; the loading
// and error states render the bare header.
export function renderTimetableHeader(extra = "") {
    return `
        <div class="card-header schedule-header">
            <button type="button" class="icon-button" id="${ID_BACK_BTN}" aria-label="Retour aux prochains départs">
                <ha-icon icon="mdi:arrow-left"></ha-icon>
            </button>
            <span class="tt-title">Horaires</span>
            ${extra}
        </div>
    `;
}

// Turn the raw "{line}|{direction}" payload into one entry per line, each
// holding its directions. Both the line and the direction id are read from the
// key: the payload itself only carries the destination label.
export function groupSchedules(schedules, config) {
    const byLine = new Map();

    for (const key of Object.keys(schedules || {})) {
        const [line, direction] = key.split("|");
        if (!matchesFilters(line, direction, config)) continue;
        const data = schedules[key];
        if (!data) continue;

        if (!byLine.has(line)) byLine.set(line, { line, directions: [] });
        byLine.get(line).directions.push({
            key,
            line,
            direction: Number(direction),
            label: data.direction_label || `Sens ${direction}`,
            horaires: data.horaires || {},
        });
    }

    return [...byLine.values()]
        .sort((a, b) =>
            String(a.line).localeCompare(String(b.line), undefined, { numeric: true }),
        )
        .map((group) => ({
            ...group,
            directions: group.directions.sort((a, b) => a.direction - b.direction),
        }));
}

// The selection is remembered per card instance, but the payload can change
// under it (filters, new service day), so fall back to the first entry
// available rather than showing nothing.
export function resolveSelection(groups, selectedLine, directionByLine) {
    if (!groups.length) return null;
    const group = groups.find((item) => item.line === selectedLine) || groups[0];
    const wanted = directionByLine?.get(group.line);
    const entry =
        group.directions.find((item) => item.direction === wanted) ||
        group.directions[0];
    return { group, entry };
}

function theoreticalTimestamps(horaires, now) {
    const out = [];
    for (const hour of Object.keys(horaires || {})) {
        const hourValue = parseInt(hour, 10);
        if (Number.isNaN(hourValue)) continue;
        for (const minute of horaires[hour] || []) {
            const minuteValue = parseInt(minute, 10);
            if (Number.isNaN(minuteValue)) continue;
            out.push(passageDate(now, hourValue, minuteValue).getTime());
        }
    }
    return out.sort((a, b) => a - b);
}

function nextTimestamp(horaires, now) {
    return theoreticalTimestamps(horaires, now).find(
        (timestamp) => timestamp >= now,
    );
}

// First "HH:MM" of the service day, which starts mid-morning-after for the
// slots past midnight.
function firstSlot(horaires) {
    const hours = Object.keys(horaires || {}).sort(
        (a, b) => serviceHourKey(a) - serviceHourKey(b),
    );
    const hour = hours[0];
    if (hour === undefined) return "";
    const minutes = [...(horaires[hour] || [])].sort();
    if (!minutes.length) return "";
    return `${String(hour).padStart(2, "0")}:${minutes[0]}`;
}

function section(label, body) {
    return `<div class="tt-section"><div class="tt-label">${label}</div>${body}</div>`;
}

function emptyMessage(live) {
    return live ? "Aucun horaire aujourd'hui" : "Aucun horaire ce jour-l\u00e0";
}

function renderChips(groups, selectedLine) {
    const chips = groups
        .map((group) => {
            const selected = group.line === selectedLine;
            return `<button type="button" class="tt-chip${selected ? " selected" : ""}" ${ATTR_LINE}="${esc(group.line)}" aria-pressed="${selected}">${lineBadge(group.line)}</button>`;
        })
        .join("");
    return `<div class="tt-chips" role="group" aria-label="Lignes">${chips}</div>`;
}

// The terminus is announced as a destination, not as one end of an axis: the
// arrow and the "Direction" kicker sit before the label, and the opposite
// terminus is demoted to a swap button.
function renderDirection(group, entry) {
    const other =
        group.directions.find((item) => item.direction !== entry.direction) || null;
    const swap = other
        ? `<button type="button" class="tt-swap" ${ATTR_DIRECTION}="${other.direction}" aria-label="Voir la direction ${esc(other.label)}">
                <ha-icon icon="mdi:swap-horizontal"></ha-icon>
                <span>${esc(other.label)}</span>
            </button>`
        : "";

    return `
        <div class="tt-section tt-dir-section">
            <div class="tt-to">
                <ha-icon class="tt-to-arrow" icon="mdi:arrow-right"></ha-icon>
                <div class="tt-to-text">
                    <div class="tt-label">Direction</div>
                    <div class="tt-to-name">${esc(entry.label)}</div>
                </div>
                ${swap}
            </div>
        </div>
    `;
}

// On another day there is no "next" passage to count down to, so the banner
// announces the first departure of the service day instead.
function renderNext(horaires, now, next, live) {
    if (live) {
        if (next === undefined) return "";
        const relative = humanizeSeconds((next - now) / 1000);
        return `
            <div class="tt-section tt-next-section">
                <div class="tt-next">
                    <span class="tt-label">Prochain</span>
                    <span class="tt-next-time">${formatClock(new Date(next))}</span>
                    <span class="tt-next-rel">${relative === "proche" ? "proche" : `dans ${relative}`}</span>
                </div>
            </div>
        `;
    }

    const first = firstSlot(horaires);
    if (!first) return "";
    return `
        <div class="tt-section tt-next-section">
            <div class="tt-next">
                <span class="tt-label">Premier départ</span>
                <span class="tt-next-time">${first}</span>
            </div>
        </div>
    `;
}

function renderDays(dayOffset, now) {
    const date = new Date(now);
    date.setDate(date.getDate() + dayOffset);
    const nav = (offset, label, iconName, disabled) =>
        `<button type="button" class="tt-day-nav" ${ATTR_DAY}="${offset}" aria-label="${label}"${disabled ? " disabled" : ""}><ha-icon icon="mdi:chevron-${iconName}"></ha-icon></button>`;

    return `
        <div class="tt-section tt-day-section">
            <div class="tt-label">Jour</div>
            <div class="tt-day">
                ${nav(dayOffset - 1, "Jour précédent", "left", dayOffset <= 0)}
                <div class="tt-day-text">
                    <div class="tt-day-date">${esc(formatDay(date))}</div>
                    <div class="tt-day-rel">${esc(relativeDay(dayOffset))}</div>
                </div>
                ${nav(dayOffset + 1, "Jour suivant", "right", dayOffset >= MAX_DAY_OFFSET)}
            </div>
        </div>
    `;
}

// Minutes already gone stay visible but dimmed: they give the frequency of the
// line at a glance, which is what the whole view is for. Nothing is dimmed on
// another day, where "already gone" means nothing.
function renderHours(horaires, now, next, live) {
    const hours = Object.keys(horaires || {}).sort(
        (a, b) => serviceHourKey(a) - serviceHourKey(b),
    );
    if (!hours.length) return message(emptyMessage(live));

    // Follow the next passage rather than the wall clock: once the last minute
    // of an hour is gone, the block worth highlighting is the next one.
    const currentHourKey = live
        ? serviceHourKey(new Date(next ?? now).getHours())
        : null;

    const cells = hours
        .map((hour) => {
            const key = serviceHourKey(hour);
            const state =
                currentHourKey === null
                    ? ""
                    : key === currentHourKey
                      ? "now"
                      : key < currentHourKey
                        ? "past"
                        : "";
            const minutes = (horaires[hour] || [])
                .map((minute) => {
                    const timestamp = passageDate(
                        now,
                        parseInt(hour, 10),
                        parseInt(minute, 10),
                    ).getTime();
                    const modifier = !live
                        ? ""
                        : timestamp === next
                          ? " next"
                          : timestamp < now
                            ? " past"
                            : "";
                    return `<span class="tt-min${modifier}">${esc(minute)}</span>`;
                })
                .join("");
            return `
                <div class="tt-cell ${state}">
                    <div class="tt-cell-hour">${esc(hour)}<small>h</small></div>
                    <div class="tt-mins">${minutes}</div>
                </div>
            `;
        })
        .join("");

    return section(
        "Horaires du jour",
        `<div class="tt-hours" ${ATTR_KEEP_SCROLL}="hours"><div class="tt-grid">${cells}</div></div>`,
    );
}
export function renderTimetable({
    schedules,
    fetched,
    config,
    selectedLine,
    directionByLine,
    dayOffset = 0,
    now = Date.now(),
}) {
    const groups = groupSchedules(schedules, config);
    const live = dayOffset === 0;

    if (!groups.length) {
        // Distinguish "still loading" from "no service that day" (e.g. Sunday
        // or holiday), which also returns an empty timetable. The day stepper
        // stays rendered, otherwise a day without service is a dead end.
        return [
            renderTimetableHeader(),
            renderDays(dayOffset, now),
            message(
                fetched
                    ? emptyMessage(live)
                    : "Chargement des horaires...",
            ),
        ].join("");
    }

    const { group, entry } = resolveSelection(groups, selectedLine, directionByLine);
    const next = live ? nextTimestamp(entry.horaires, now) : undefined;

    return [
        renderTimetableHeader(renderChips(groups, group.line)),
        renderDirection(group, entry),
        renderNext(entry.horaires, now, next, live),
        renderDays(dayOffset, now),
        renderHours(entry.horaires, now, next, live),
    ].join("");
}
