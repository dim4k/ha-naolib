import { MS_PER_MINUTE, STALE_SECONDS } from "./constants.js";
import { humanizeSeconds } from "./time.js";
import { configValidator } from "./validate.js";

export const DEFAULT_CONFIG = {
    entity: "",
    title: "",
    lines: [],
    direction: 0, // 0 = both directions
    walk_time: 0, // minutes needed to reach the stop
    max_lines: 6, // rows per direction, or per card when compact
    show_timetable_button: true,
    compact: false,
};

export const MAX_LINES_LIMIT = 30;
export const MAX_WALK_TIME = 60;

const check = configValidator("naolib-card");

// Normalize and validate a user-provided card configuration. Anything the
// renderer reads afterwards is guaranteed to have the right type.
export function normalizeConfig(config) {
    const raw = check.base(config, DEFAULT_CONFIG);

    let lines = raw.lines;
    if (lines === null || lines === undefined) lines = [];
    if (typeof lines === "string" || typeof lines === "number") lines = [lines];
    if (!Array.isArray(lines)) check.invalid('"lines" doit être une liste de lignes');

    return {
        ...raw,
        lines: lines.map((line) => String(line)),
        direction: check.integer(raw.direction ?? 0, "direction", 0, 2),
        walk_time: check.integer(raw.walk_time ?? 0, "walk_time", 0, MAX_WALK_TIME),
        max_lines: check.integer(
            raw.max_lines ?? DEFAULT_CONFIG.max_lines,
            "max_lines",
            1,
            MAX_LINES_LIMIT,
        ),
        show_timetable_button: check.boolean(
            raw.show_timetable_button,
            "show_timetable_button",
        ),
        compact: check.boolean(raw.compact, "compact"),
    };
}

// Shared by the departures and the timetable views so both honour the
// configured filters the same way. `direction` may come as a number (realtime
// feed) or as a string (timetable group key).
export function matchesFilters(line, direction, config) {
    if (config.lines.length) {
        const wanted = String(line ?? "").toLowerCase();
        if (!config.lines.some((l) => String(l).toLowerCase() === wanted)) return false;
    }
    if (!config.direction) return true;
    return Number(direction) === config.direction;
}

// Recompute the humanized times from the raw timestamps so the card ticks
// down between coordinator refreshes, and apply the configured filters.
// Departures more than 60 s in the past are dropped (mirrors the backend).
export function prepareDepartures(departures, config, now = Date.now()) {
    const earliest = now + config.walk_time * MS_PER_MINUTE;
    const out = [];

    for (const departure of departures || []) {
        if (!matchesFilters(departure.line, departure.direction, config)) continue;

        const timestamp = Date.parse(departure.expected_ts);
        if (Number.isNaN(timestamp)) continue;
        if (timestamp < earliest) continue;
        const delta = (timestamp - now) / 1000;
        if (delta < -STALE_SECONDS) continue;

        out.push({
            ...departure,
            time: humanizeSeconds(delta),
            // Kept numeric so the renderer never has to parse the label back.
            minutes: Math.max(0, Math.floor(delta / 60)),
        });
        // One departure is one row in compact mode; the grouped view caps the
        // rows it renders instead, so that no direction can starve the other.
        if (config.compact && out.length >= config.max_lines) break;
    }

    return out;
}
