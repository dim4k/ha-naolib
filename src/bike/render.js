import { esc } from "../html.js";
import { message } from "../render/shared.js";

// Availability colouring: red once the station is empty (or full, for docks),
// amber when it is nearly so.
function countClass(value, capacity) {
    if (typeof value !== "number") return "bike-count";
    if (value === 0) return "bike-count empty";
    if (capacity && value <= Math.max(1, Math.round(capacity * 0.15))) {
        return "bike-count low";
    }
    return "bike-count";
}

function statusHtml(data) {
    const notices = [];
    if (data.is_installed === false) notices.push("Station hors service");
    else {
        if (data.is_renting === false) notices.push("Location indisponible");
        if (data.is_returning === false)
            notices.push("Restitution indisponible");
    }
    if (!notices.length) return "";
    return `<div class="bike-status">${notices.map(esc).join(" · ")}</div>`;
}

function gaugeHtml(bikes, capacity) {
    if (!capacity || typeof bikes !== "number") return "";
    const ratio = Math.min(100, Math.round((bikes / capacity) * 100));
    return `
        <div class="bike-gauge" role="img" aria-label="${ratio}% de la capacité">
            <div class="bike-gauge-fill" style="width: ${ratio}%"></div>
        </div>
    `;
}

function counterHtml(label, value, capacity, icon) {
    const text = typeof value === "number" ? String(value) : "—";
    return `
        <div class="bike-counter">
            <ha-icon icon="${icon}"></ha-icon>
            <div class="${countClass(value, capacity)}">${text}</div>
            <div class="bike-label">${esc(label)}</div>
        </div>
    `;
}

function nearbyRowHtml(station, config) {
    const bikes = typeof station.bikes === "number" ? station.bikes : "—";
    const docks = typeof station.docks === "number" ? station.docks : "—";
    const closed = station.is_renting === false ? " closed" : "";
    const docksCell = config.show_docks
        ? `<div class="bike-nearby-docks">${docks} <span>pl.</span></div>`
        : "";
    return `
        <div class="bike-nearby-row${closed}">
            <div class="bike-nearby-name">${esc(station.name)}</div>
            <div class="bike-nearby-distance">${esc(String(station.distance))} m</div>
            <div class="bike-nearby-bikes">${bikes} <span>vélos</span></div>
            ${docksCell}
        </div>
    `;
}

function nearbyHtml(stations, config) {
    if (!stations.length) return "";
    return `
        <div class="bike-nearby">
            <div class="bike-nearby-title">Stations à proximité</div>
            ${stations.map((station) => nearbyRowHtml(station, config)).join("")}
        </div>
    `;
}

export function renderBikeStation(data, nearby, config) {
    if (!data.available) {
        return message("Station introuvable dans les données Naolib");
    }

    const counters = [
        counterHtml("vélos", data.bikes, data.capacity, "mdi:bike"),
    ];
    if (config.show_docks) {
        counters.push(
            counterHtml(
                "places",
                data.docks,
                data.capacity,
                "mdi:rhombus-outline",
            ),
        );
    }

    return `
        <div class="bike-main">
            <div class="bike-counters">${counters.join("")}</div>
            ${config.compact ? "" : gaugeHtml(data.bikes, data.capacity)}
            ${statusHtml(data)}
        </div>
        ${nearbyHtml(nearby, config)}
    `;
}
