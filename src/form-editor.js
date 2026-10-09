// Both card editors are an ha-form driven by a schema: they only differ in
// their defaults, labels and fields, which subclasses provide.
export class NaolibFormEditor extends HTMLElement {
    static defaults = {};
    static labels = {};
    static helpers = {};

    buildSchema(_hass, _config) {
        return [];
    }

    // Hooks for the options whose form value differs from the stored one.
    toFormData(config) {
        return config;
    }

    fromFormData(config, value) {
        return { ...config, ...value };
    }

    setConfig(config) {
        this._config = { ...this.constructor.defaults, ...(config || {}) };
        this._render();
    }

    set hass(hass) {
        this._hass = hass;
        this._render();
    }

    _render() {
        if (!this._hass || !this._config) return;

        if (!this._form) {
            const { labels, helpers } = this.constructor;
            this._form = document.createElement("ha-form");
            this._form.computeLabel = (schema) => labels[schema.name] || schema.name;
            this._form.computeHelper = (schema) => helpers[schema.name] || "";
            this._form.addEventListener("value-changed", (ev) =>
                this._valueChanged(ev),
            );
            this.appendChild(this._form);
        }

        this._form.hass = this._hass;
        this._form.schema = this.buildSchema(this._hass, this._config);
        this._form.data = this.toFormData(this._config);
    }

    _valueChanged(ev) {
        ev.stopPropagation();
        this._config = this.fromFormData(this._config, ev.detail.value);
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: this._prune(this._config) },
                bubbles: true,
                composed: true,
            }),
        );
    }

    // Keep the stored configuration to what the user actually changed, so the
    // YAML editor stays readable.
    _prune(config) {
        const defaults = this.constructor.defaults;
        const out = {};
        for (const [key, value] of Object.entries(config)) {
            if (
                key in defaults &&
                JSON.stringify(value) === JSON.stringify(defaults[key])
            ) {
                continue;
            }
            out[key] = value;
        }
        return out;
    }
}
