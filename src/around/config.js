import { configValidator } from "../validate.js";

export const DEFAULT_AROUND_CONFIG = {
    entity: "", // the person, zone or device tracker to follow
    title: "",
    radius: 500, // meters
    max_stops: 5,
    departures: 3, // per stop
    compact: false,
};

export const MIN_RADIUS = 100;
export const MAX_RADIUS = 3000;
export const MAX_STOPS = 15;
export const MAX_DEPARTURES = 10;

const check = configValidator("naolib-around-card");

export function normalizeAroundConfig(config) {
    const raw = check.base(config, DEFAULT_AROUND_CONFIG);
    return {
        ...raw,
        radius: check.integer(raw.radius, "radius", MIN_RADIUS, MAX_RADIUS),
        max_stops: check.integer(raw.max_stops, "max_stops", 1, MAX_STOPS),
        departures: check.integer(raw.departures, "departures", 1, MAX_DEPARTURES),
        compact: check.boolean(raw.compact, "compact"),
    };
}

// The stops pushed by the integration (nearest first), each with its next
// departures counted down from `now`. Departures already gone are dropped,
// like the departures card does: the stream refreshes less often than the
// card ticks.
export function prepareStops(stops, config, now = Date.now()) {
    return (stops || []).map((stop) => ({
        name: stop.name || "",
        distance: Number(stop.distance),
        departures: (stop.departures || [])
            .map((departure) => ({
                line: departure.line,
                destination: departure.destination,
                seconds: (Date.parse(departure.expected_ts) - now) / 1000,
            }))
            .filter((departure) => Number.isFinite(departure.seconds))
            .filter((departure) => departure.seconds >= 0)
            .slice(0, config.departures),
    }));
}
