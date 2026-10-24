import { configValidator } from "../validate.js";

export const DEFAULT_BIKE_CONFIG = {
    entity: "",
    title: "",
    nearby_count: 3, // neighbouring stations listed
    nearby_radius: 500, // meters
    show_docks: true,
    compact: false,
};

export const MAX_NEARBY_COUNT = 10;
export const MAX_NEARBY_RADIUS = 1000;

const check = configValidator("naolib-bike-card");

// Normalize and validate a user-provided card configuration. Anything the
// renderer reads afterwards is guaranteed to have the right type.
export function normalizeBikeConfig(config) {
    const raw = check.base(config, DEFAULT_BIKE_CONFIG);

    return {
        ...raw,
        nearby_count: check.integer(raw.nearby_count, "nearby_count", 0, MAX_NEARBY_COUNT),
        nearby_radius: check.integer(
            raw.nearby_radius,
            "nearby_radius",
            0,
            MAX_NEARBY_RADIUS,
        ),
        show_docks: check.boolean(raw.show_docks, "show_docks"),
        compact: check.boolean(raw.compact, "compact"),
    };
}

// The backend caps the list generously (10 stations within 1 km); the card
// narrows it down to what the user asked for.
export function prepareNearby(stations, config) {
    if (!config.nearby_count) return [];
    return (stations || [])
        .filter((station) => Number(station.distance) <= config.nearby_radius)
        .slice(0, config.nearby_count);
}
