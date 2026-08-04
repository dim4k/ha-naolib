// DOM ids matched by the delegated click handler in card.js.
export const ID_SCHEDULE_BTN = "schedule-btn";
export const ID_BACK_BTN = "back-btn";

// Data attributes carried by the timetable line chips and direction buttons.
export const ATTR_LINE = "data-line";
export const ATTR_DIRECTION = "data-direction";
export const ATTR_DAY = "data-day";

// How far ahead the timetable can be browsed (mirrors the backend).
export const MAX_DAY_OFFSET = 6;

// Marks a scrollable container whose position must survive a full re-render.
export const ATTR_KEEP_SCROLL = "data-keep-scroll";

export const MS_PER_MINUTE = 60000;

// Countdown refresh between coordinator polls.
export const TICK_MS = 20000;

// Departure countdown colouring thresholds, in minutes.
export const URGENT_MINUTES = 1;
export const WARNING_MINUTES = 3;

// Minimum delay/advance vs the theoretical timetable worth showing.
export const DELAY_TOLERANCE_MINUTES = 2;

// Departures older than this are dropped (mirrors the backend).
export const STALE_SECONDS = 60;

// Hours below this belong to the tail of the previous service day.
export const SERVICE_DAY_CUTOFF_HOUR = 4;
