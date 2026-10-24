import { URGENT_MINUTES, WARNING_MINUTES } from "../constants.js";

export const LOADING = "Chargement...";

export function message(html) {
    return `<div class="message">${html}</div>`;
}

// Countdown colouring, from the whole minutes left.
export function timeClass(minutes) {
    if (minutes <= URGENT_MINUTES) return "time urgent";
    if (minutes <= WARNING_MINUTES) return "time warning";
    return "time";
}
