// The network numbers the two ways of each line 1 and 2: name them after
// their terminus instead, per line, since direction 1 of one line has nothing
// to do with direction 1 of another.

const byLine = (a, b) => a.localeCompare(b, undefined, { numeric: true });

// Collect the terminus of each line, per direction, from the stop's timetable
// (keyed "line|direction") and from its next departures, which also cover a
// day without timetable. `lines` keeps only the lines the card shows.
export function directionTermini(schedules, departures, lines = []) {
    const wanted = new Set(lines.map(String));
    const termini = { 1: new Map(), 2: new Map() };
    const add = (line, direction, destination) => {
        line = String(line ?? "");
        destination = String(destination ?? "").trim();
        const byDirection = termini[Number(direction)];
        if (!line || !destination || !byDirection) return;
        if (wanted.size && !wanted.has(line)) return;
        if (!byDirection.has(line)) byDirection.set(line, new Set());
        byDirection.get(line).add(destination);
    };

    for (const [key, group] of Object.entries(schedules || {})) {
        const [line, direction] = key.split("|");
        add(group?.ligne?.numLigne || line, direction, group?.ligne?.direction);
    }
    for (const departure of departures || []) {
        add(departure.line, departure.direction, departure.destination);
    }
    return termini;
}

// "C1 → François Mitterrand · 2 → Orvault Grand Val", lines sharing a
// terminus grouped, or the bare direction number when nothing is known.
export function directionLabel(termini, direction) {
    const lines = termini[direction];
    if (!lines?.size) return `Direction ${direction}`;
    const linesByTerminus = new Map();
    for (const line of [...lines.keys()].sort(byLine)) {
        const terminus = [...lines.get(line)].sort().join(" / ");
        if (!linesByTerminus.has(terminus)) linesByTerminus.set(terminus, []);
        linesByTerminus.get(terminus).push(line);
    }
    return [...linesByTerminus]
        .map(([terminus, names]) => `${names.join(", ")} → ${terminus}`)
        .join(" · ");
}

// Heading of a direction in the card: where its departures go.
export function directionHeading(departures, direction) {
    const destinations = new Set(
        (departures || [])
            .filter((item) => item.direction === direction && item.destination)
            .map((item) => String(item.destination).trim()),
    );
    if (!destinations.size) return `Direction ${direction}`;
    return `Vers ${[...destinations].sort().join(" · ")}`;
}
