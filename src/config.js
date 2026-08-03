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

function invalid(message) {
    // Lovelace surfaces this message in the card editor.
    throw new Error(`naolib-card: ${message}`);
}

function asInteger(value, name, min, max) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < min || number > max) {
        invalid(`"${name}" doit être un entier entre ${min} et ${max}`);
    }
    return number;
}

function asBoolean(value, name) {
    if (typeof value !== "boolean") invalid(`"${name}" doit être vrai ou faux`);
    return value;
}

// Normalize and validate a user-provided card configuration. Anything the
// renderer reads afterwards is guaranteed to have the right type.
export function normalizeConfig(config) {
    if (config && typeof config !== "object") invalid("configuration invalide");
    const raw = { ...DEFAULT_CONFIG, ...(config || {}) };

    if (typeof raw.entity !== "string") invalid('"entity" doit être une entité');
    if (typeof raw.title !== "string") invalid('"title" doit être du texte');

    let lines = raw.lines;
    if (lines === null || lines === undefined) lines = [];
    if (typeof lines === "string" || typeof lines === "number") lines = [lines];
    if (!Array.isArray(lines)) invalid('"lines" doit être une liste de lignes');

    return {
        ...raw,
        lines: lines.map((line) => String(line)),
        direction: asInteger(raw.direction ?? 0, "direction", 0, 2),
        walk_time: asInteger(raw.walk_time ?? 0, "walk_time", 0, MAX_WALK_TIME),
        max_lines: asInteger(
            raw.max_lines ?? DEFAULT_CONFIG.max_lines,
            "max_lines",
            1,
            MAX_LINES_LIMIT,
        ),
        show_timetable_button: asBoolean(
            raw.show_timetable_button,
            "show_timetable_button",
        ),
        compact: asBoolean(raw.compact, "compact"),
    };
}

// Same output format as the backend _humanize().
function humanizeSeconds(delta) {
    if (delta <= 60) return "proche";
    const minutes = Math.floor(delta / 60);
    if (minutes < 60) return `${minutes} mn`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
}

// Shared by the departures and the timetable views so both honour the
// configured filters the same way.
export function matchesFilters(line, direction, config) {
    if (config.lines.length) {
        const wanted = String(line ?? "").toLowerCase();
        if (!config.lines.some((l) => String(l).toLowerCase() === wanted)) return false;
    }
    return !(config.direction && Number(direction) !== config.direction);
}

// Recompute the humanized times from the raw timestamps so the card ticks
// down between coordinator refreshes, and apply the configured filters.
// Departures more than 60 s in the past are dropped (mirrors the backend).
export function prepareDepartures(departures, config, now = Date.now()) {
    const earliest = now + config.walk_time * 60000;
    const out = [];

    for (const departure of departures || []) {
        if (!matchesFilters(departure.line, departure.direction, config)) continue;

        const timestamp = Date.parse(departure.expected_ts);
        if (Number.isNaN(timestamp)) continue;
        if (timestamp < earliest) continue;
        const delta = (timestamp - now) / 1000;
        if (delta < -60) continue;

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
