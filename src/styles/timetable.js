export const timetable = `
    .schedule-header { padding-bottom: 10px; margin-bottom: 12px; gap: 8px; flex-wrap: wrap; }
    .tt-title { flex: 0 1 auto; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .schedule-header .tt-chips { flex: 1 1 auto; min-width: 0; justify-content: flex-end; }

    .tt-section { padding: 0 16px; margin-bottom: 16px; }
    .tt-section:last-child { margin-bottom: 0; padding-bottom: 16px; }
    /* The separators frame the "next passage" banner, as in the mock-up. */
    .tt-dir-section { padding-bottom: 12px; margin-bottom: 0; border-bottom: 1px solid var(--divider-color); }
    .tt-next-section { padding: 10px 16px; margin-bottom: 14px; border-bottom: 1px solid var(--divider-color); }
    .tt-label { font-size: 0.68em; font-weight: 500; text-transform: uppercase; letter-spacing: 0.9px; color: var(--secondary-text-color); margin-bottom: 6px; }

    .tt-chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .tt-chip { display: inline-flex; flex: 0 0 auto; cursor: pointer; background: none; border: none; padding: 3px; border-radius: var(--naolib-radius); opacity: 0.5; filter: grayscale(0.55); transition: opacity 0.15s, filter 0.15s; }
    .tt-chip .badge { margin-right: 0; }
    .tt-chip:hover { opacity: 0.85; filter: none; }
    /* Inset ring rather than an outline: it stays inside the button box, so it
       is never clipped when compact mode shrinks the badge. */
    .tt-chip.selected { opacity: 1; filter: none; box-shadow: inset 0 0 0 2px var(--primary-color); }
    .tt-chip:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }

    .tt-to { display: flex; align-items: center; gap: 10px; background: rgba(var(--rgb-primary-color), 0.1); border: 1px solid rgba(var(--rgb-primary-color), 0.35); border-radius: var(--naolib-radius); padding: 8px 10px; }
    .tt-to-arrow { color: var(--primary-color); --mdc-icon-size: 20px; flex: none; }
    .tt-to-text { flex: 1; min-width: 0; }
    .tt-to-text .tt-label { margin-bottom: 0; }
    .tt-to-name { font-weight: 600; color: var(--primary-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tt-swap { display: inline-flex; align-items: center; gap: 4px; max-width: 45%; cursor: pointer; border: none; background: none; padding: 5px 6px; border-radius: 8px; font-family: inherit; font-size: 0.78em; color: var(--secondary-text-color); transition: background 0.15s, color 0.15s; }
    .tt-swap span { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tt-swap ha-icon { --mdc-icon-size: 16px; flex: none; }
    .tt-swap:hover { background: rgba(var(--rgb-primary-color), 0.12); color: var(--primary-color); }
    .tt-swap:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }

    .tt-next { display: flex; align-items: baseline; gap: 8px; }
    .tt-next .tt-label { margin-bottom: 0; }
    .tt-next-time { font-size: 1.25em; font-weight: 700; color: var(--primary-color); font-variant-numeric: tabular-nums; }
    .tt-next-rel { font-size: 0.85em; color: var(--secondary-text-color); }

    .tt-day-section { margin-bottom: 12px; }
    .tt-day { display: flex; align-items: center; gap: 8px; background: var(--naolib-neutral); border-radius: var(--naolib-radius); padding: 4px; }
    .tt-day-nav { display: inline-flex; cursor: pointer; border: none; background: none; color: var(--primary-color); border-radius: 8px; padding: 5px; transition: background 0.15s; }
    .tt-day-nav:hover:not([disabled]) { background: rgba(var(--rgb-primary-color), 0.12); }
    .tt-day-nav[disabled] { color: var(--secondary-text-color); opacity: 0.4; cursor: default; }
    .tt-day-nav:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    .tt-day-text { flex: 1; min-width: 0; text-align: center; }
    .tt-day-date { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tt-day-rel { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.6px; color: var(--secondary-text-color); }

    /* Both syntaxes on purpose: Chromium 121+ and Firefox honour the standard
       properties, older Chromium falls back to the -webkit- pseudo-elements. */
    /* The negative margin compensates the padding, which keeps the grid aligned
       with the other sections while leaving room for the "now" ring and the
       last row at full scroll. */
    .tt-hours { max-height: 380px; overflow-y: auto; overscroll-behavior: contain; position: relative; margin: 0 -4px; padding: 4px 12px 6px 4px; scrollbar-width: thin; scrollbar-color: var(--naolib-scroll-thumb) transparent; }
    .tt-hours::-webkit-scrollbar { width: 8px; }
    .tt-hours::-webkit-scrollbar-track { background: transparent; }
    .tt-hours::-webkit-scrollbar-thumb { background: var(--naolib-scroll-thumb); border: 2px solid transparent; background-clip: content-box; border-radius: 4px; }
    .tt-hours::-webkit-scrollbar-thumb:hover { background: var(--naolib-scroll-thumb-hover); background-clip: content-box; }
    .tt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); gap: 8px; }
    .tt-cell { background: var(--naolib-neutral); border: 1px solid transparent; border-radius: var(--naolib-radius); padding: 6px 8px 8px; }
    .tt-cell.past { opacity: 0.42; }
    /* Inset ring rather than an outer glow: it stays inside the cell box, so
       the scroll container never clips it. */
    .tt-cell.now { background: rgba(var(--rgb-primary-color), 0.1); border-color: var(--primary-color); box-shadow: inset 0 0 0 2px rgba(var(--rgb-primary-color), 0.25); }
    .tt-cell-hour { font-size: 1.05em; font-weight: 700; color: var(--primary-color); font-variant-numeric: tabular-nums; padding-bottom: 4px; margin-bottom: 4px; border-bottom: 1px solid rgba(var(--rgb-primary-color), 0.2); }
    .tt-cell-hour small { font-size: 0.7em; font-weight: 400; opacity: 0.7; }
    .tt-mins { display: flex; flex-wrap: wrap; gap: 2px 6px; }
    .tt-min { min-width: 1.5em; text-align: center; font-size: 0.9em; font-variant-numeric: tabular-nums; color: var(--primary-text-color); }
    .tt-min.past { color: var(--secondary-text-color); opacity: 0.55; }
    .tt-min.next { background: var(--primary-color); color: #fff; font-weight: 700; border-radius: 5px; padding: 0 3px; margin: 0 -3px; }

    :host([compact]) .tt-hours { max-height: 260px; }
    :host([compact]) .tt-cell { padding: 4px 6px 6px; }
    :host([compact]) .tt-min { font-size: 0.85em; }
`;
