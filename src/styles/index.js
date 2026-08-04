import { base } from "./base.js";
import { departures } from "./departures.js";
import { timetable } from "./timetable.js";

export const styles = [base, departures, timetable].join("\n");
