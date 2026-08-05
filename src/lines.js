import { esc } from "./html.js";

// Official colours from the Nantes Métropole GTFS feed (routes.txt), which
// ships the text colour alongside the background: white is unreadable on the
// yellow and lime lines, and the network already says which to use.
const LINE_COLORS = {
    "1": { bg: "#00a754", text: "#ffffff" },
    "1B": { bg: "#00a754", text: "#ffffff" },
    "2": { bg: "#e30613", text: "#ffffff" },
    "3": { bg: "#2581c4", text: "#ffffff" },
    "4": { bg: "#ffcd1c", text: "#000000" },
    "5": { bg: "#0bbbef", text: "#ffffff" },
    "10": { bg: "#ffed00", text: "#000000" },
    "11": { bg: "#e8b975", text: "#000000" },
    "12": { bg: "#a1daf8", text: "#000000" },
    "23": { bg: "#0bbbef", text: "#ffffff" },
    "26": { bg: "#009640", text: "#ffffff" },
    "27": { bg: "#a1daf8", text: "#000000" },
    "28": { bg: "#a1daf8", text: "#000000" },
    "30": { bg: "#ffed00", text: "#000000" },
    "33": { bg: "#f5b5d3", text: "#000000" },
    "36": { bg: "#65c2c4", text: "#ffffff" },
    "38": { bg: "#009640", text: "#ffffff" },
    "40": { bg: "#ffed00", text: "#000000" },
    "42": { bg: "#c8d300", text: "#000000" },
    "47": { bg: "#bca3ce", text: "#ffffff" },
    "50": { bg: "#ffed00", text: "#000000" },
    "59": { bg: "#f5b5d3", text: "#000000" },
    "60": { bg: "#ffed00", text: "#000000" },
    "66": { bg: "#2581c4", text: "#ffffff" },
    "67": { bg: "#2581c4", text: "#ffffff" },
    "69": { bg: "#d39e46", text: "#ffffff" },
    "71": { bg: "#c8d300", text: "#000000" },
    "75": { bg: "#e8b975", text: "#000000" },
    "77": { bg: "#a1daf8", text: "#000000" },
    "78": { bg: "#f7a600", text: "#000000" },
    "79": { bg: "#f5b5d3", text: "#000000" },
    "80": { bg: "#ffed00", text: "#000000" },
    "81": { bg: "#65c2c4", text: "#ffffff" },
    "85": { bg: "#f5b5d3", text: "#000000" },
    "86": { bg: "#0bbbef", text: "#ffffff" },
    "87": { bg: "#f7a600", text: "#000000" },
    "88": { bg: "#a877b2", text: "#ffffff" },
    "89": { bg: "#76b82a", text: "#ffffff" },
    "91": { bg: "#009640", text: "#ffffff" },
    "93": { bg: "#65c2c4", text: "#ffffff" },
    "95": { bg: "#c8d300", text: "#000000" },
    "96": { bg: "#f7a600", text: "#000000" },
    "97": { bg: "#bca3ce", text: "#ffffff" },
    "98": { bg: "#f7a600", text: "#000000" },
    "118": { bg: "#a9162e", text: "#ffffff" },
    "142": { bg: "#a9162e", text: "#ffffff" },
    "C1": { bg: "#0bbbef", text: "#ffffff" },
    "C2": { bg: "#ee7402", text: "#ffffff" },
    "C3": { bg: "#f7a600", text: "#000000" },
    "C4": { bg: "#76b82a", text: "#ffffff" },
    "C6": { bg: "#a877b2", text: "#ffffff" },
    "C7": { bg: "#c8d300", text: "#000000" },
    "C8": { bg: "#c8d300", text: "#000000" },
    "C9": { bg: "#f5b5d3", text: "#000000" },
    "C20": { bg: "#ffed00", text: "#000000" },
    "E1": { bg: "#e30613", text: "#ffffff" },
    "E4": { bg: "#e30613", text: "#ffffff" },
    "E5": { bg: "#e30613", text: "#ffffff" },
    "E8": { bg: "#e30613", text: "#ffffff" },
    "N1": { bg: "#2aaab6", text: "#ffffff" },
    "N2": { bg: "#2aaab6", text: "#ffffff" },
    "N3": { bg: "#2aaab6", text: "#ffffff" },
    "NA": { bg: "#a1daf8", text: "#000000" },
    "TE1": { bg: "#502391", text: "#ffffff" },
    "TE2": { bg: "#2581c4", text: "#ffffff" },
};

const FALLBACK = { bg: "var(--primary-color)", text: "#ffffff" };

const MODE_LABELS = {
    1: "Tramway",
    2: "Busway",
    3: "Bus",
    4: "Navibus",
};

export function lineColors(line) {
    return LINE_COLORS[String(line).toUpperCase()] || FALLBACK;
}

export function lineBadge(line) {
    const { bg, text } = lineColors(line);
    return `<div class="badge" style="background-color: ${bg}; color: ${text};" title="Ligne ${esc(line)}">${esc(line)}</div>`;
}

export function modeLabel(type) {
    return MODE_LABELS[type] || "Bus";
}
