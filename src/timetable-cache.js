// The timetables a card fetched, one per day browsed. Days are counted from
// today, so an offset only means something on the day it was fetched: a
// dashboard left open overnight would otherwise keep showing yesterday's
// timetable as today's.
export class TimetableCache {
    constructor() {
        this._day = null;
        // Bumped whenever the cache is emptied: an answer still on its way
        // belongs to what was dropped.
        this._generation = 0;
        this._empty();
    }

    _empty() {
        this._timetables = new Map();
        this._expired = new Set();
        this._fetching = new Set();
    }

    // Forget everything: the stop changed.
    clear() {
        this._generation += 1;
        this._empty();
    }

    // Forget everything once the calendar day has changed since the last
    // call. Returns whether anything had to be dropped.
    rollover(now = new Date()) {
        const day = new Date(now).toDateString();
        if (this._day === day) return false;
        const stale = this._day !== null;
        this._day = day;
        if (stale) this.clear();
        return stale;
    }

    timetable(offset) {
        return this._timetables.get(offset) || {};
    }

    isFetched(offset) {
        return this._timetables.has(offset);
    }

    // Whether the day lies past the end of the embedded calendar.
    isExpired(offset) {
        return this._expired.has(offset);
    }

    // Start fetching a day, unless it is already known or on its way. Returns
    // the function settling the request: called with the answer, or with
    // nothing when the request failed. It returns false when the answer came
    // too late to be used.
    begin(offset) {
        if (this._timetables.has(offset) || this._fetching.has(offset)) return null;
        this._fetching.add(offset);
        const generation = this._generation;
        return (data) => {
            if (generation !== this._generation) return false;
            this._fetching.delete(offset);
            if (data !== undefined) {
                this._timetables.set(offset, data?.timetable || {});
                if (data?.expired) this._expired.add(offset);
            }
            return true;
        };
    }
}
