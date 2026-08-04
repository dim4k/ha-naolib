import { SERVICE_DAY_CUTOFF_HOUR } from "./constants.js";

// Same output format as the backend _humanize().
export function humanizeSeconds(delta) {
    if (delta <= 60) return "proche";
    const minutes = Math.floor(delta / 60);
    if (minutes < 60) return `${minutes} mn`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
}

// Sort key placing the small hours after midnight at the end of the day.
export function serviceHourKey(hour) {
    const value = parseInt(hour, 10);
    return value < SERVICE_DAY_CUTOFF_HOUR ? value + 24 : value;
}

export function formatClock(date) {
    return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

const DAY_FORMAT = new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
});

export function formatDay(date) {
    const label = DAY_FORMAT.format(date);
    return label.charAt(0).toUpperCase() + label.slice(1);
}

export function relativeDay(offset) {
    if (offset === 0) return "Aujourd'hui";
    if (offset === 1) return "Demain";
    if (offset === 2) return "Apr\u00e8s-demain";
    return `Dans ${offset} jours`;
}

// Resolve an "HH:MM" timetable slot to an absolute date. Slots before the
// service-day cutoff belong to the next calendar day, unless the current time
// is itself in those small hours.
export function passageDate(now, hour, minute) {
    const reference = new Date(now);
    const date = new Date(now);
    date.setHours(hour, minute, 0, 0);
    if (
        hour < SERVICE_DAY_CUTOFF_HOUR &&
        reference.getHours() >= SERVICE_DAY_CUTOFF_HOUR
    ) {
        date.setDate(date.getDate() + 1);
    }
    return date;
}
