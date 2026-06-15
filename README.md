# 🚌 Naolib Nantes - Home Assistant

A custom integration for Home Assistant that displays upcoming bus and tram departures for the **Naolib (Nantes)** network at the stop closest to your location.

This integration includes a native **Custom Lovelace Card**, requiring no complex configuration.

![Naolib Card](https://github.com/dim4k/ha-naolib/blob/main/screenshot.png?raw=true)

## ✨ Features

-   **📍 Auto-detection:** Enter your GPS coordinates, and the integration automatically finds the nearest stop.
-   **⏱️ Real-time:** Displays real waiting times (Naolib real-time SIRI API).
-   **🎨 Included Card:** A visual Custom Card is automatically installed to display line badges and directions properly.
-   **📅 Schedules:** View full daily schedules directly within the card.
-   **🔔 Sensors:** Creates `sensor` entities that you can use in your own automations.

## 📥 Installation

### Via HACS (Recommended)

1.  Open HACS in Home Assistant.
2.  Go to **Integrations** > Menu (3 dots) > **Custom repositories**.
3.  Add the URL of this repository: `https://github.com/dim4k/ha-naolib`.
4.  Category: **Integration**.
5.  Click **Download**.
6.  **Restart Home Assistant**.

### Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration**.
3.  Search for **Naolib**.
4.  Enter the **Latitude** and **Longitude** of your home (or desired location, ie : 47.218 / -1.553)
5.  The integration will find the nearest stop and create the entities.

## 📺 Dashboard Usage

To add the card to your dashboard, you can use the visual editor:

1.  In your dashboard, click **'Edit Dashboard'**.
2.  Click **'Add Card'** (or the '+' icon).
3.  Search for and select the **'Naolib'** card.
4.  The visual editor will appear. Select your entity from the dropdown list.
5.  Click **Save**.

You can also view the full schedule for the day by clicking on the "Voir tous les horaires" button at the bottom of the card.

## 🛠️ Technical Details

-   **WebSocket Architecture**: Heavy data (schedules) is fetched on-demand via WebSocket to keep Home Assistant's database light and fast.
-   **Optimized Data**: Schedule data is compressed before transfer to minimize network usage.
-   **Native Web Component**: The card is built as a standalone Web Component with Shadow DOM for style isolation.

## 📚 API

This integration relies on the **Naolib real-time SIRI API** (Okina) for live departures, and on the **Nantes Métropole open data** GTFS feed for the embedded stop index and timetables.
