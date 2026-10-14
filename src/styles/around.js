export const around = `
    .around { padding: 0 16px 12px; }
    .around-stop + .around-stop { border-top: 1px solid var(--divider-color); }
    .around-stop { padding: 8px 0; }
    .around-stop-header { display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; }
    .around-stop-name { flex: 1; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .around-distance { font-size: 0.8em; color: var(--secondary-text-color); white-space: nowrap; }
    .around-departure { display: flex; align-items: center; gap: 10px; padding: 3px 0; }
    .around-departure .badge { margin-right: 0; }
    .around-destination { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .around-times { display: flex; gap: 4px; flex-shrink: 0; }
    .around-empty { font-size: 0.85em; font-style: italic; color: var(--secondary-text-color); }
    :host([compact]) .around { padding: 0 12px 8px; }
    :host([compact]) .around-stop { padding: 4px 0; }
    :host([compact]) .around-departure { padding: 1px 0; }
    :host([compact]) .around-times .time { padding: 2px 6px; }
`;
