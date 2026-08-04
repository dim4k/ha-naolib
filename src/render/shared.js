import {
    DELAY_TOLERANCE_MINUTES,
    URGENT_MINUTES,
    WARNING_MINUTES,
} from "../constants.js";
import { formatClock } from "../time.js";

export function message(html) {
    return `<div class="no-bus">${html}</div>`;
}

export function timeClass(minutes) {
    if (minutes <= URGENT_MINUTES) return "time urgent";
    if (minutes <= WARNING_MINUTES) return "time warning";
    return "time";
}

// Departure clock, and the theoretical one struck through next to it when the
// vehicle drifts from the timetable (SIRI Aimed vs Expected). Showing both
// times says how late the bus is *and* when it actually leaves.
function clockHtml(expected, delay) {
    const real = formatClock(new Date(expected));
    if (typeof delay !== "number" || Math.abs(delay) < DELAY_TOLERANCE_MINUTES) {
        return `<span class="clock">${real}</span>`;
    }
    const aimed = formatClock(new Date(expected - delay * 60000));
    const state = delay > 0 ? "late" : "early";
    const title =
        delay > 0
            ? `${delay} min de retard sur l'horaire théorique`
            : `${-delay} min d'avance sur l'horaire théorique`;
    return `<span class="clock aimed">${aimed}</span><span class="clock ${state}" title="${title}">${real}</span>`;
}

// Second line of a departure: "dernier" marker (from the GTFS timetable, the
// realtime feed does not expose it) then the clock.
export function departureMeta(item) {
    const expected = Date.parse(item.expected_ts);
    if (Number.isNaN(expected)) return "";
    const last = item.is_last
        ? `<span class="time-meta last" title="Dernier passage prévu aujourd'hui">dernier</span>`
        : "";
    return `${last}${clockHtml(expected, item.delay_minutes)}`;
}
