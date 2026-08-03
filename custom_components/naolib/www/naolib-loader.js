// Home Assistant imports a custom card exactly once per page load and never
// retries, so a single transient failure leaves the dashboard stuck on
// "Configuration error" until a full reload. This module keeps retrying, and
// waits for the element registry to be final before defining anything.

const CARD_URL = new URL(import.meta.url);
CARD_URL.pathname = CARD_URL.pathname.replace(/[^/]*$/, "naolib-card.js");

const IMPORT_TIMEOUT_MS = 10000;
const APP_TIMEOUT_MS = 20000;

// Readable from the browser console to diagnose a card that stays in error.
const status = (window.naolibLoader = {
    loader: import.meta.url,
    state: "idle",
    attempts: 0,
    lastError: null,
});

let pending = false;

// The app bundle installs @webcomponents/scoped-custom-element-registry on its
// very first line, which swaps window.customElements for a registry whose
// lookup table ignores everything defined before it. Being an extra module, we
// race that bundle, and a card defined too early stays invisible to Lovelace
// for the whole life of the page. The <home-assistant> element can only be
// defined after the polyfill, so it marks the registry as final.
function whenRegistryIsFinal() {
    if (customElements.get("home-assistant")) return Promise.resolve();
    return Promise.race([
        customElements.whenDefined("home-assistant"),
        new Promise((resolve) => setTimeout(resolve, APP_TIMEOUT_MS)),
    ]);
}

// Lovelace resolves a custom card through customElements.get, so this is the
// only check that matters: an element it cannot see is an element that does
// not exist as far as the dashboard is concerned.
function isCardReady() {
    return !!customElements.get("naolib-card");
}

async function loadCard() {
    if (pending || isCardReady()) return;
    pending = true;
    status.state = "waiting-for-app";
    await whenRegistryIsFinal();
    status.state = "loading";

    const url = new URL(CARD_URL);
    if (status.attempts) {
        // A fresh query string forces a new module instance and bypasses both
        // the module map and any bad response cached by the service worker.
        url.searchParams.set("retry", String(status.attempts));
    }
    status.attempts += 1;

    try {
        // A dynamic import whose request is stalled or aborted stays pending
        // forever instead of rejecting, which would leave the card in error
        // for the whole life of the page.
        await Promise.race([
            import(url.href),
            new Promise((_resolve, reject) => {
                setTimeout(() => reject(new Error("import timed out")), IMPORT_TIMEOUT_MS);
            }),
        ]);
        // A resolved import is not enough: the module can evaluate without the
        // element ending up registered.
        if (!isCardReady()) {
            throw new Error("module evaluated but naolib-card is not registered");
        }
        status.state = "ready";
        status.lastError = null;
    } catch (err) {
        status.state = "failed";
        status.lastError = String(err);
        console.error("Naolib: card failed to load, retrying", err);
        setTimeout(loadCard, Math.min(30000, 500 * 2 ** status.attempts));
    } finally {
        pending = false;
    }
}

// Mobile browsers abort in-flight requests when the page is backgrounded, and
// the app is usually resumed before the network is back up.
window.addEventListener("online", loadCard);
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadCard();
});

loadCard();
