import { configValidator } from "../validate.js";

export const DEFAULT_AROUND_CONFIG = {
    entity: "", // the person, zone or device tracker an "around me" entry follows
    title: "",
    departures: 3, // per stop
    max_stops: 0, // 0 = every stop the entry exposes
    compact: false,
};

export const MAX_DEPARTURES = 10;
export const MAX_STOPS = 15;

const check = configValidator("naolib-around-card");

export function normalizeAroundConfig(config) {
    const raw = check.base(config, DEFAULT_AROUND_CONFIG);
    return {
        ...raw,
        departures: check.integer(raw.departures, "departures", 1, MAX_DEPARTURES),
        max_stops: check.integer(raw.max_stops, "max_stops", 0, MAX_STOPS),
        compact: check.boolean(raw.compact, "compact"),
    };
}

// What the card shows: the stops nearest first, each with its next
// departures counted down from `now`; departures gone for more than a
// minute are dropped (the sensor refreshes less often than the card ticks).
export function prepareStops(sensors, config, now = Date.now()) {
    const stops = sensors
        .map((state) => {
            const attributes = state.attributes;
            const departures = (attributes.next_departures || [])
                .map((departure) => ({
                    line: departure.line,
                    destination: departure.destination,
                    seconds: (Date.parse(departure.expected_ts) - now) / 1000,
                }))
                .filter((departure) => Number.isFinite(departure.seconds))
                .filter((departure) => departure.seconds >= -60)
                .slice(0, config.departures);
            return {
                entityId: state.entity_id,
                name: attributes.stop_label || attributes.friendly_name || "",
                distance: Number(attributes.distance),
                departures,
            };
        })
        .sort((a, b) => (a.distance || 0) - (b.distance || 0));
    return config.max_stops ? stops.slice(0, config.max_stops) : stops;
}
