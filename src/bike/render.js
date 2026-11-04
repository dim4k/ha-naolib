import { RANGE_URGENT_KM, RANGE_WARNING_KM } from "../constants.js";
import { esc } from "../html.js";
import { message } from "../render/shared.js";

// How many bike ranges are listed under the counters before "+N".
export const MAX_RANGE_CHIPS = 8;

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

// Range colouring, with the same red and amber as the counters.
function rangeLevel(km) {
    if (typeof km !== "number") return "";
    if (km <= RANGE_URGENT_KM) return " empty";
    if (km <= RANGE_WARNING_KM) return " low";
    return "";
}

// What the station's operator publishes. JCDecaux counts docks; Voi spots are
// painted on the ground, have none, and list every bike with its range.
export function stationFeatures(data, config) {
    return {
        docks: config.show_docks && typeof data.docks === "number",
        range: Array.isArray(data.vehicles),
    };
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

function counterHtml(label, value, className, icon) {
    const text = typeof value === "number" ? String(value) : "—";
    return `
        <div class="bike-counter">
            <ha-icon icon="${icon}"></ha-icon>
            <div class="${className}">${text}</div>
            <div class="bike-label">${esc(label)}</div>
        </div>
    `;
}

function rangeChipHtml(vehicle) {
    if (vehicle.disabled) {
        return `<span class="bike-range disabled" title="Vélo hors service">HS</span>`;
    }
    const km = typeof vehicle.range_km === "number" ? vehicle.range_km : "?";
    return `<span class="bike-range${rangeLevel(vehicle.range_km)}">${esc(String(km))} km</span>`;
}

// The range left in each bike parked at the spot, best first.
function rangesHtml(vehicles) {
    if (!vehicles.length) return "";
    const shown = vehicles.slice(0, MAX_RANGE_CHIPS);
    const hidden = vehicles.length - shown.length;
    const more = hidden > 0 ? `<span class="bike-range more">+${hidden}</span>` : "";
    return `
        <div class="bike-ranges" aria-label="Autonomie des vélos">
            ${shown.map(rangeChipHtml).join("")}${more}
        </div>
    `;
}

function appLinkHtml(url) {
    if (typeof url !== "string" || !url) return "";
    return `<a class="bike-app" href="${esc(url)}" rel="noopener">Ouvrir l'application</a>`;
}

function nearbyRowHtml(station, features) {
    const bikes = typeof station.bikes === "number" ? station.bikes : "—";
    const closed = station.is_renting === false ? " closed" : "";
    let extra = "";
    if (features.docks) {
        const docks = typeof station.docks === "number" ? station.docks : "—";
        extra = `<div class="bike-nearby-docks">${docks} <span>pl.</span></div>`;
    } else if (features.range) {
        const km =
            typeof station.best_range_km === "number" ? station.best_range_km : "—";
        extra = `<div class="bike-nearby-range">${km} <span>km</span></div>`;
    }
    return `
        <div class="bike-nearby-row${closed}">
            <div class="bike-nearby-name">${esc(station.name)}</div>
            <div class="bike-nearby-distance">${esc(String(station.distance))} m</div>
            <div class="bike-nearby-bikes">${bikes} <span>vélos</span></div>
            ${extra}
        </div>
    `;
}

function nearbyHtml(stations, features) {
    if (!stations.length) return "";
    return `
        <div class="bike-nearby">
            <div class="bike-nearby-title">Stations à proximité</div>
            ${stations.map((station) => nearbyRowHtml(station, features)).join("")}
        </div>
    `;
}

export function renderBikeStation(data, nearby, config) {
    if (!data.available) {
        return message("Station introuvable dans les données Naolib");
    }

    const features = stationFeatures(data, config);
    const counters = [
        counterHtml(
            "vélos",
            data.bikes,
            countClass(data.bikes, data.capacity),
            "mdi:bike",
        ),
    ];
    if (features.docks) {
        counters.push(
            counterHtml(
                "places",
                data.docks,
                countClass(data.docks, data.capacity),
                "mdi:rhombus-outline",
            ),
        );
    }
    if (features.range) {
        counters.push(
            counterHtml(
                "km max",
                data.best_range_km,
                `bike-count${rangeLevel(data.best_range_km)}`,
                "mdi:battery-charging-high",
            ),
        );
    }

    const details = config.compact
        ? ""
        : `${gaugeHtml(data.bikes, data.capacity)}${
              features.range ? rangesHtml(data.vehicles) : ""
          }${appLinkHtml(data.app_url)}`;

    return `
        <div class="bike-main">
            <div class="bike-counters">${counters.join("")}</div>
            ${details}
            ${statusHtml(data)}
        </div>
        ${nearbyHtml(nearby, features)}
    `;
}
