import { NaolibBaseCard } from "../base-card.js";
import { normalizeBikeConfig, prepareNearby } from "./config.js";
import { renderBikeStation } from "./render.js";
import { isBikeEntity } from "../entities.js";

export class NaolibBikeCard extends NaolibBaseCard {
    static normalizeConfig = normalizeBikeConfig;
    static acceptsEntity = isBikeEntity;
    static idAttribute = "station_id";
    static labelAttribute = "station_label";
    static icon = "mdi:bike";
    static defaultTitle = "Station vélo Naolib";
    static noEntityMessage =
        "Aucune station vélo Naolib trouvée. Ajoutez-la via Paramètres &gt; Appareils et services.";
    static logLabel = "Naolib bike card";

    static getConfigElement() {
        return document.createElement("naolib-bike-card-editor");
    }

    // The sensor attributes carry everything the card shows, so the whole
    // station and its neighbours render without any WebSocket round-trip.
    _stationData() {
        const attributes = this._state.attributes;
        return {
            available: this._state.state !== "unavailable",
            bikes: Number.isFinite(Number(this._state.state))
                ? Number(this._state.state)
                : null,
            docks: attributes.docks_available,
            capacity: attributes.capacity,
            is_installed: attributes.is_installed,
            is_renting: attributes.is_renting,
            is_returning: attributes.is_returning,
        };
    }

    _render() {
        if (!this._state) {
            this._message("Chargement...");
            return;
        }

        this.content.innerHTML = renderBikeStation(
            this._stationData(),
            prepareNearby(this._state.attributes.nearby_stations, this.config),
            this.config,
        );
    }

    getCardSize() {
        const nearby = prepareNearby(
            this._state?.attributes?.nearby_stations ?? [],
            this.config,
        );
        return 3 + nearby.length;
    }
}
