export const base = `
    :host {
        font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        --naolib-radius: 10px;
        --naolib-urgent: #e74c3c;
        --naolib-warning: #f1c40f;
        --naolib-early: #27ae60;
        --naolib-neutral: rgba(127, 127, 127, 0.1);
        --naolib-neutral-strong: rgba(127, 127, 127, 0.18);
        --naolib-scroll-thumb: rgba(127, 127, 127, 0.35);
        --naolib-scroll-thumb-hover: rgba(127, 127, 127, 0.55);
    }
    ha-card { padding-bottom: 0; overflow: hidden; }
    .card-header { padding: 16px; font-weight: bold; font-size: 1.2em; display: flex; align-items: center; }
    .icon { margin-right: 10px; color: var(--primary-color); }
    .badge { font-weight: bold; padding: 4px 8px; border-radius: 6px; min-width: 25px; text-align: center; margin-right: 12px; font-size: 1.1em; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
    .no-bus { padding: 10px 16px; font-style: italic; color: var(--secondary-text-color); text-align: center; }
    .time { font-weight: bold; font-size: 1.1em; padding: 4px 8px; border-radius: 4px; white-space: nowrap; background: var(--naolib-neutral); color: var(--primary-text-color); }
    .urgent { background-color: rgba(231, 76, 60, 0.2); color: var(--naolib-urgent); }
    .warning { background-color: rgba(241, 196, 15, 0.2); color: var(--naolib-warning); }
    .button { display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--primary-color); font-weight: 500; padding: 6px 12px; border-radius: 4px; transition: background 0.2s; background: none; border: none; font-family: inherit; font-size: inherit; }
    .button:hover { background-color: rgba(var(--rgb-primary-color), 0.1); }
    .button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .button ha-icon { margin-right: 6px; --mdc-icon-size: 18px; }
    .icon-button { cursor: pointer; background: none; border: none; padding: 0; margin-right: 10px; color: var(--primary-color); display: inline-flex; }
    .icon-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .card-footer { padding: 8px 16px; text-align: center; border-top: 1px solid var(--divider-color); }
    :host([compact]) .card-header { padding: 12px 16px 4px; font-size: 1.05em; }
    :host([compact]) .badge { font-size: 0.95em; padding: 2px 6px; margin-right: 8px; }
    :host([compact]) .time { font-size: 1em; }
`;
