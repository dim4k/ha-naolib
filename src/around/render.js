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

function departureHtml(departure) {
    return `
        <div class="around-departure">
            ${lineBadge(departure.line ?? "?")}
            <div class="around-destination">${esc(departure.destination)}</div>
            <div class="${timeClass(departure.seconds)}">${esc(humanizeSeconds(departure.seconds))}</div>
        </div>
    `;
}

function stopHtml(stop) {
    const distance = Number.isFinite(stop.distance)
        ? `<div class="around-distance">${esc(String(stop.distance))} m</div>`
        : "";
    const departures = stop.departures.length
        ? stop.departures.map(departureHtml).join("")
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

// Either no entry follows this entity, or no stop is in its radius (or it has
// no position yet): the card cannot tell them apart, so it names both.
export function noStopsMessage(name) {
    return `Aucun arrêt pour ${esc(name)}. Vérifiez qu'une entrée Naolib « autour de moi » suit cette entité (Paramètres &gt; Appareils et services) ; le rayon et le nombre d'arrêts s'y règlent.`;
}
