// Escape a value before interpolating it into innerHTML. The SIRI feed is
// an external data source: a destination or line name containing markup
// would otherwise be injected straight into the DOM.
export function esc(value) {
    return String(value ?? "").replace(
        /[&<>"']/g,
        (c) =>
            ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            })[c],
    );
}

// What an error says about itself, ready to interpolate.
export function errorText(err) {
    return esc(err?.message || err?.code || err);
}
