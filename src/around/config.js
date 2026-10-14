import { configValidator } from "../validate.js";

export const DEFAULT_AROUND_CONFIG = {
    entity: "", // the person, zone or device tracker to follow
    title: "",
    radius: 500, // meters
    max_stops: 5,
    departures: 3, // per line and terminus
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

// The stops pushed by the integration (nearest first). The departures of a
// stop are grouped by line and terminus, soonest first, each with its next
// passages counted down from `now`. Departures already gone are dropped, like
// the departures card does: the stream refreshes less often than the card
// ticks.
export function prepareStops(stops, config, now = Date.now()) {
    return (stops || []).map((stop) => {
        const directions = new Map();
        for (const departure of stop.departures || []) {
            const seconds = (Date.parse(departure.expected_ts) - now) / 1000;
            if (!Number.isFinite(seconds) || seconds < 0) continue;
            const key = `${departure.line}|${departure.destination}`;
            if (!directions.has(key)) {
                directions.set(key, {
                    line: departure.line,
                    destination: departure.destination,
                    seconds: [],
                });
            }
            directions.get(key).seconds.push(seconds);
        }
        return {
            name: stop.name || "",
            distance: Number(stop.distance),
            directions: [...directions.values()]
                .map((direction) => ({
                    ...direction,
                    seconds: direction.seconds
                        .sort((a, b) => a - b)
                        .slice(0, config.departures),
                }))
                .sort((a, b) => a.seconds[0] - b.seconds[0]),
        };
    });
}
