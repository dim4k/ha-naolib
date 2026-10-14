import { URGENT_MINUTES, WARNING_MINUTES } from "../constants.js";
import { esc } from "../html.js";
import { lineBadge } from "../lines.js";
import { humanizeSeconds } from "../time.js";

function timeClass(seconds) {
    const minutes = seconds / 60;
    if (minutes <= URGENT_MINUTES) return "time urgent";
    if (minutes <= WARNING_MINUTES) return "time warning";
    return "time";
}

// One row per line and terminus, its next passages side by side, the
// soonest on the left.
function directionHtml(direction) {
    const times = direction.seconds
        .map(
            (seconds) =>
                `<div class="${timeClass(seconds)}">${esc(humanizeSeconds(seconds))}</div>`,
        )
        .join("");
    return `
        <div class="around-departure">
            ${lineBadge(direction.line ?? "?")}
            <div class="around-destination">${esc(direction.destination)}</div>
            <div class="around-times">${times}</div>
        </div>
    `;
}

function stopHtml(stop) {
    const distance = Number.isFinite(stop.distance)
        ? `<div class="around-distance">${esc(String(stop.distance))} m</div>`
        : "";
    const departures = stop.directions.length
        ? stop.directions.map(directionHtml).join("")
        : `<div class="around-empty">Aucun passage prévu</div>`;
    return `
        <div class="around-stop">
            <div class="around-stop-header">
                <div class="around-stop-name">${esc(stop.name)}</div>
                ${distance}
            </div>
            ${departures}
        </div>
    `;
}

export function renderAround(stops) {
    return `<div class="around">${stops.map(stopHtml).join("")}</div>`;
}

export function notLocatedMessage(name) {
    return `La position de ${esc(name)} est inconnue : il faut une personne, une zone ou un traceur avec des coordonnées GPS.`;
}

export function noStopsMessage(name, radius) {
    return `Aucun arrêt dans un rayon de ${esc(String(radius))} m autour de ${esc(name)}.`;
}
