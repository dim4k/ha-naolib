export const bike = `
    .bike-main { padding: 4px 16px 16px; }
    .bike-counters { display: flex; gap: 12px; }
    .bike-counter { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 12px 8px; border-radius: var(--naolib-radius); background: var(--naolib-neutral); }
    .bike-counter ha-icon { color: var(--primary-color); --mdc-icon-size: 22px; }
    .bike-count { font-size: 2em; font-weight: bold; line-height: 1.1; color: var(--primary-text-color); }
    .bike-count.low { color: var(--naolib-warning); }
    .bike-count.empty { color: var(--naolib-urgent); }
    .bike-label { font-size: 0.8em; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
    .bike-gauge { margin-top: 12px; height: 6px; border-radius: 3px; background: var(--naolib-neutral-strong); overflow: hidden; }
    .bike-gauge-fill { height: 100%; background: var(--primary-color); transition: width 0.3s; }
    .bike-status { margin-top: 10px; padding: 6px 10px; border-radius: 6px; text-align: center; font-size: 0.85em; font-weight: 500; background: rgba(231, 76, 60, 0.15); color: var(--naolib-urgent); }
    .bike-nearby { border-top: 1px solid var(--divider-color); padding: 8px 16px 12px; }
    .bike-nearby-title { font-size: 0.75em; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--secondary-text-color); margin-bottom: 4px; }
    .bike-nearby-row { display: flex; align-items: baseline; gap: 8px; padding: 6px 0; }
    .bike-nearby-row + .bike-nearby-row { border-top: 1px solid var(--naolib-neutral); }
    .bike-nearby-row.closed { opacity: 0.5; }
    .bike-nearby-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .bike-nearby-distance { font-size: 0.8em; color: var(--secondary-text-color); white-space: nowrap; }
    .bike-nearby-bikes, .bike-nearby-docks { font-weight: bold; white-space: nowrap; min-width: 56px; text-align: right; }
    .bike-nearby-bikes span, .bike-nearby-docks span { font-weight: normal; font-size: 0.75em; color: var(--secondary-text-color); }
    :host([compact]) .bike-main { padding: 0 12px 12px; }
    :host([compact]) .bike-counter { padding: 8px 6px; }
    :host([compact]) .bike-count { font-size: 1.5em; }
`;
