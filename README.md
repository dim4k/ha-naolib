# 🚌 Tan Nantes - Home Assistant

A custom integration for Home Assistant that displays upcoming bus and tram departures for the **Tan (Nantes)** network at the stop closest to your location.

This integration includes a native **Custom Lovelace Card**, requiring no complex configuration.

![Tan Nantes Card](https://github.com/dim4k/ha-tan-nantes/blob/main/screenshot.png?raw=true)

## ✨ Features

-   **📍 Auto-detection:** Enter your GPS coordinates, and the integration automatically finds the nearest stop via the Tan API.
-   **⏱️ Real-time:** Displays real waiting times (API `tempsattente.json`).
-   **🎨 Included Card:** A visual Custom Card is automatically installed to display line badges and directions properly.
-   **🔔 Sensors:** Creates `sensor` entities that you can use in your own automations.

## 📥 Installation

### Via HACS (Recommended)

1.  Open HACS in Home Assistant.
2.  Go to **Integrations** > Menu (3 dots) > **Custom repositories**.
3.  Add the URL of this repository: `https://github.com/dim4k/ha-tan-nantes`.
4.  Category: **Integration**.
5.  Click **Download**.
6.  **Restart Home Assistant**.

### Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Tan Nantes**.
4.  Enter the **Latitude** and **Longitude** of your home (or desired location, ie : 47.218 / -1.553)
5.  The integration will find the nearest stop and create the entities.

## 📺 Dashboard Usage

To add the card to your dashboard, you can add it to your dashboard using the visual editor:

1.  In your dashboard, click **'Edit Dashboard'**.
2.  Click **'Add Card'** (or the '+' icon).
3.  Search for and select the **'Tan Nantes'** card.
4.  The card will appear with a sample entity ID (`sensor.tan_next_commerce`). In the code editor, **update the `entity:` field** with the name of the sensor created for your stop (e.g., `sensor.tan_next_gare_de_l_etat`).

## 📚 API

This integration relies on the **Tan Open Data API**.
You can find the official documentation here: [https://open.tan.fr/doc/openapi](https://open.tan.fr/doc/openapi)
