export const departures = `
    /* minmax(0, 1fr): without it the implicit column is sized on the widest
       tile, so a long destination next to two clocks pushes the rows past the
       card, which clips them. */
    .tiles { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; padding: 12px 16px; }
    .tiles + .tiles { padding-top: 0; }
    .tile-group { font-size: 0.68em; font-weight: 500; text-transform: uppercase; letter-spacing: 0.9px; color: var(--secondary-text-color); }
    .tile { display: flex; flex-direction: column; gap: 6px; background: var(--naolib-neutral); border-radius: var(--naolib-radius); padding: 10px 12px; }
    .tile-row { display: flex; align-items: center; gap: 10px; }
    .tile .badge { margin-right: 0; }
    .tile-text { flex: 1; min-width: 0; }
    .tile-mode { font-size: 0.72em; color: var(--secondary-text-color); }
    .dest { font-size: 1.1em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .times-container { display: flex; align-items: baseline; gap: 10px; margin-left: auto; }
    /* Strip under the departure: the clocks the countdown stands for, and the
       markers. Its tint carries the state so a delay reads without parsing. */
    .strip { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 8px; border-radius: 6px; background: var(--naolib-neutral-strong); font-size: 0.88em; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
    .strip.late { background: rgba(231, 76, 60, 0.16); }
    .strip.final { background: rgba(127, 127, 127, 0.26); }
    .clock { white-space: nowrap; }
    .clock.strong { font-weight: 700; color: var(--primary-text-color); }
    .clock.aimed { margin-right: 4px; text-decoration: line-through; opacity: 0.65; }
    .clock.late { color: var(--naolib-urgent); font-weight: 700; }
    .clock.early { color: var(--naolib-early); font-weight: 700; }
    .mark { font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
    :host([compact]) .tiles { gap: 6px; padding: 8px 16px; }
    :host([compact]) .tile { padding: 6px 10px; }
    :host([compact]) .strip { font-size: 0.8em; padding: 3px 8px; }
    :host([compact]) .mark { font-size: 0.8em; color: var(--secondary-text-color); }
`;
