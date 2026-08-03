export const styles = `
    :host { font-family: Roboto, sans-serif; }
    .card-header { padding: 16px; font-weight: bold; font-size: 1.2em; display: flex; align-items: center; }
    .schedule-header { border-bottom: 1px solid var(--divider-color); padding-bottom: 10px; margin-bottom: 10px; }
    .icon { margin-right: 10px; color: var(--primary-color); }
    .direction-header { font-size: 0.85em; text-transform: uppercase; color: var(--secondary-text-color); margin: 10px 16px 5px; border-bottom: 1px solid var(--divider-color); padding-bottom: 4px; letter-spacing: 1px; }
    .row { display: flex; align-items: center; padding: 8px 16px; border-bottom: 1px solid rgba(127,127,127, 0.1); }
    .badge { background-color: var(--primary-color); color: white; font-weight: bold; padding: 4px 8px; border-radius: 6px; min-width: 25px; text-align: center; margin-right: 12px; font-size: 1.1em; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
    .mode-icon { color: var(--secondary-text-color); margin-right: 8px; --mdc-icon-size: 20px; }
    .dest { flex-grow: 1; font-size: 1.05em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-right: 10px; }
    .time { font-weight: bold; font-size: 1.1em; padding: 4px 8px; border-radius: 4px; white-space: nowrap; background: rgba(127,127,127,0.1); color: var(--primary-text-color); }
    .urgent { background-color: rgba(231, 76, 60, 0.2); color: #e74c3c; }
    .warning { background-color: rgba(241, 196, 15, 0.2); color: #f1c40f; }
    .no-bus { padding: 10px 16px; font-style: italic; color: var(--secondary-text-color); text-align: center; }
    .card-footer { padding: 8px 16px; text-align: center; border-top: 1px solid var(--divider-color); }
    .button { display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--primary-color); font-weight: 500; padding: 6px 12px; border-radius: 4px; transition: background 0.2s; background: none; border: none; font-family: inherit; font-size: inherit; }
    .button:hover { background-color: rgba(var(--rgb-primary-color), 0.1); }
    .button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .button ha-icon { margin-right: 6px; --mdc-icon-size: 18px; }
    .icon-button { cursor: pointer; background: none; border: none; padding: 0; margin-right: 10px; color: var(--primary-color); display: inline-flex; }
    .icon-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .schedule-container { padding: 0 16px 16px; max-height: 400px; overflow-y: auto; }
    .schedule-group { margin-bottom: 20px; }
    .schedule-line-header { display: flex; align-items: center; margin-bottom: 8px; border-bottom: 1px solid rgba(127,127,127,0.1); padding-bottom: 4px; }
    .schedule-line-header .badge { margin-right: 10px; }
    .schedule-dest { font-weight: 500; font-size: 1.1em; }
    .schedule-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(60px, 1fr)); gap: 8px; }
    .schedule-item { background: rgba(127,127,127, 0.1); padding: 4px; border-radius: 4px; text-align: center; font-size: 0.9em; }
    .schedule-hour { font-weight: bold; color: var(--primary-color); }
    .schedule-min { color: var(--secondary-text-color); }
    /* Two-row grid so every marker lines up, whatever the height of
       the time above it. */
    .times-container { display: grid; grid-auto-flow: column; grid-template-rows: auto auto; column-gap: 10px; justify-items: end; align-items: center; }
    .departure { display: contents; }
    .departure > .time, .departure > .time-secondary { grid-row: 1; }
    .departure-meta { grid-row: 2; display: flex; gap: 4px; margin-top: 4px; }
    .time-secondary { font-size: 0.9em; color: var(--secondary-text-color); font-weight: normal; padding: 4px 0; }
    .time-meta { font-size: 0.65em; font-weight: 700; white-space: nowrap; padding: 2px 6px; border-radius: 10px; }
    .time-meta.late { background: rgba(231, 76, 60, 0.18); color: #e74c3c; }
    .time-meta.early { background: rgba(39, 174, 96, 0.18); color: #27ae60; }
    .time-meta.last { background: rgba(127,127,127,0.15); color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
    /* Compact mode: one line per departure, no grouping. */
    :host([compact]) .card-header { padding: 12px 16px 4px; font-size: 1.05em; }
    :host([compact]) .row { padding: 4px 16px; }
    :host([compact]) .badge { font-size: 0.95em; padding: 2px 6px; margin-right: 8px; }
    :host([compact]) .time { font-size: 1em; }
    ha-card { padding-bottom: 0; overflow: hidden; }
`;
