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

function invalid(message) {
    // Lovelace surfaces this message in the card editor.
    throw new Error(`naolib-bike-card: ${message}`);
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
export function normalizeBikeConfig(config) {
    if (config && typeof config !== "object") invalid("configuration invalide");
    const raw = { ...DEFAULT_BIKE_CONFIG, ...(config || {}) };

    if (typeof raw.entity !== "string") invalid('"entity" doit être une entité');
    if (typeof raw.title !== "string") invalid('"title" doit être du texte');

    return {
        ...raw,
        nearby_count: asInteger(
            raw.nearby_count ?? DEFAULT_BIKE_CONFIG.nearby_count,
            "nearby_count",
            0,
            MAX_NEARBY_COUNT,
        ),
        nearby_radius: asInteger(
            raw.nearby_radius ?? DEFAULT_BIKE_CONFIG.nearby_radius,
            "nearby_radius",
            0,
            MAX_NEARBY_RADIUS,
        ),
        show_docks: asBoolean(raw.show_docks, "show_docks"),
        compact: asBoolean(raw.compact, "compact"),
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
