import { esc } from "./html.js";

const LINE_COLORS = {
    1: "#00A754",
    2: "#E30612",
    3: "#2481C3",
    4: "#FDC600",
    5: "#0BBBEF",
    C1: "#0BBBEF",
    C2: "#EE7402",
    C3: "#F7A600",
    C4: "#76B82A",
    C6: "#A877B2",
    C7: "#C8D300",
    C8: "#C8D300",
    C9: "#F5B5D3",
    C20: "#FFED00",
    NA: "#2ecc71",
};

// Dark text on light badge backgrounds (white is unreadable on
// yellow/lime/pink lines, e.g. C20).
const DARK_TEXT_LINES = ["4", "C4", "C7", "C8", "C9", "C20"];

const MODE_ICONS = {
    1: "mdi:tram",
    2: "mdi:bus-articulated-front",
    3: "mdi:bus",
    4: "mdi:ferry",
};

export function lineBadge(line) {
    const background = LINE_COLORS[line] || "var(--primary-color)";
    const color = DARK_TEXT_LINES.includes(String(line)) ? "#1a1a1a" : "#ffffff";
    return `<div class="badge" style="background-color: ${background}; color: ${color};" title="Ligne ${esc(line)}">${esc(line)}</div>`;
}

export function modeIcon(type) {
    return MODE_ICONS[type] || "mdi:bus";
}
