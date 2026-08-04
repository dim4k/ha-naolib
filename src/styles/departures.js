export const departures = `
    .tiles { display: grid; gap: 8px; padding: 12px 16px; }
    .tiles + .tiles { padding-top: 0; }
    .tile-group { font-size: 0.68em; font-weight: 500; text-transform: uppercase; letter-spacing: 0.9px; color: var(--secondary-text-color); }
    .tile { display: flex; align-items: center; gap: 10px; background: var(--naolib-neutral); border-radius: var(--naolib-radius); padding: 10px 12px; }
    .tile .badge { margin-right: 0; }
    .tile-text { flex: 1; min-width: 0; }
    .tile-mode { font-size: 0.72em; color: var(--secondary-text-color); }
    .dest { font-size: 1.05em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    /* Two-row grid so every marker lines up, whatever the height of
       the time above it. */
    .times-container { display: grid; grid-auto-flow: column; grid-template-rows: auto auto; column-gap: 10px; justify-items: end; align-items: center; }
    .departure { display: contents; }
    .departure > .time, .departure > .time-secondary { grid-row: 1; }
    .departure-meta { grid-row: 2; display: flex; align-items: center; gap: 4px; margin-top: 3px; }
    .clock { font-size: 0.72em; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap; padding: 2px 6px; border-radius: 10px; background: var(--naolib-neutral-strong); }
    .clock.aimed { background: none; padding: 2px 0; text-decoration: line-through; opacity: 0.7; }
    .clock.late, .clock.early { font-weight: 700; }
    .clock.late { background: rgba(231, 76, 60, 0.18); color: var(--naolib-urgent); }
    .clock.early { background: rgba(39, 174, 96, 0.18); color: var(--naolib-early); }
    .time-secondary { font-size: 0.9em; color: var(--secondary-text-color); font-weight: normal; padding: 4px 0; }
    :host([compact]) .tiles { gap: 6px; padding: 8px 16px; }
    :host([compact]) .tile { padding: 6px 10px; }
`;
