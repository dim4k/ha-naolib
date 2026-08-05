import { base } from "./base.js";
import { bike } from "./bike.js";
import { departures } from "./departures.js";
import { timetable } from "./timetable.js";

export const styles = [base, departures, timetable, bike].join("\n");
