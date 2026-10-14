// Shared by the config flow helpers: while Home Assistant's config flow
// dialog is open, call each registered helper a few times per second with
// the app element, so it can adjust what the current step shows.

const FLOW_DIALOG = "dialog-data-entry-flow";
const POLL_MS = 300;
// Stop watching if no dialog shows up this soon after the trigger.
const APPEAR_MS = 3000;
const MAX_POLL_MS = 10 * 60 * 1000;

export function findAll(root, localName, found = []) {
    if (!root) return found;
    if (root.localName === localName) found.push(root);
    if (root.shadowRoot) findAll(root.shadowRoot, localName, found);
    for (const child of root.children || []) findAll(child, localName, found);
    return found;
}

const helpers = new Set();
let polling = null;
let listening = false;

// The dialog element stays in the page once closed, but only renders its
// ha-dialog while open.
function isOpen(app) {
    return findAll(app, FLOW_DIALOG).some((dialog) =>
        dialog.shadowRoot?.querySelector("ha-dialog"),
    );
}

function poll() {
    if (polling) return;
    const started = Date.now();
    let seen = false;
    polling = setInterval(() => {
        const app = document.querySelector("home-assistant");
        const open = isOpen(app);
        seen ||= open;
        const elapsed = Date.now() - started;
        if (
            (seen && !open) ||
            (!seen && elapsed > APPEAR_MS) ||
            elapsed > MAX_POLL_MS
        ) {
            clearInterval(polling);
            polling = null;
            return;
        }
        for (const helper of helpers) {
            try {
                helper(app);
            } catch (err) {
                console.error("Naolib: config flow helper failed", err);
            }
        }
    }, POLL_MS);
}

export function whileFlowDialogOpen(helper) {
    helpers.add(helper);
    if (listening) return;
    listening = true;
    window.addEventListener(
        "show-dialog",
        (event) => {
            if (event.detail?.dialogTag === FLOW_DIALOG) poll();
        },
        true,
    );
    // A direct link (e.g. ".../add?domain=naolib") opens the dialog while the
    // page loads, before this module runs: check once right away.
    poll();
}
