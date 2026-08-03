# Naolib Nantes for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz)
[![Release](https://img.shields.io/github/v/release/dim4k/ha-naolib?include_prereleases)](https://github.com/dim4k/ha-naolib/releases)
[![Hassfest](https://github.com/dim4k/ha-naolib/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/dim4k/ha-naolib/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/dim4k/ha-naolib/actions/workflows/hacs.yaml/badge.svg)](https://github.com/dim4k/ha-naolib/actions/workflows/hacs.yaml)
[![License](https://img.shields.io/github/license/dim4k/ha-naolib)](LICENSE)

Real-time bus and tram departures for the **Naolib** network (Nantes, France), with a
dashboard card included. Pick a stop near you during setup, add the card, and you are done:
no YAML, no API key, no external dependency.

![Naolib card](https://github.com/dim4k/ha-naolib/blob/main/screenshot.png?raw=true)

## Features

-   **Real-time departures** from the official SIRI feed, with a countdown that keeps ticking between refreshes.
-   **Delay indicator** comparing the expected time to the theoretical timetable.
-   **Last departure of the day** flagged per line and direction, from the embedded timetable.
-   **Guided setup**: enter a location, pick your stop from the closest ones.
-   **Full daily timetable** available from the card, fetched on demand.
-   **Sensor entities** exposing every upcoming departure for your own automations.

## Requirements

Home Assistant 2025.2 or newer. Nothing else: the integration ships its own card and needs
no account, token or extra download.

## Installation

### HACS (recommended)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dim4k&repository=ha-naolib&category=integration)

1.  In HACS, open the menu (three dots) and choose **Custom repositories**.
2.  Add `https://github.com/dim4k/ha-naolib` with the **Integration** category.
3.  Download **Naolib Nantes**, then restart Home Assistant.

### Manual

Copy `custom_components/naolib` into your `config/custom_components` folder, then restart
Home Assistant.

## Configuration

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=naolib)

Go to **Settings** > **Devices & services** > **Add integration**, search for **Naolib**,
then confirm the location to search around (your home coordinates are pre-filled) and pick
your stop from the nearby ones. The entities are created right away.

Repeat the process to follow several stops. The refresh interval, 60 seconds by default,
can be changed between 30 and 600 seconds from the **Configure** button of the integration.

## Dashboard card

The card is registered by the integration, so it shows up in the card picker as **Naolib
Nantes**: edit your dashboard, click **Add card**, search for **Naolib** and select the
entity of the stop to display.

The YAML equivalent is:

```yaml
type: custom:naolib-card
entity: sensor.<your_stop>_next_departures
```

The card lists the two next departures per line and direction, with the delay and last
departure markers underneath. The **Voir tous les horaires** button opens the full timetable
for the day.

## Entities

Each stop creates one sensor whose state is the timestamp of the very next departure
(`device_class: timestamp`), so relative time formatting works out of the box.

| Attribute         | Description                          |
| ----------------- | ------------------------------------ |
| `stop_code`       | Stop identifier on the network       |
| `stop_label`      | Stop name as shown in the UI         |
| `next_departures` | Ordered list of upcoming departures  |

Every departure holds `line`, `type` (`bus` or `tram`), `destination`, `direction`, `time`
(human readable, such as `proche` or `4 mn`), `expected_ts` (ISO timestamp), `delay_minutes`
and `is_last`.

```yaml
automation:
    - alias: "Leave for the tram"
      triggers:
          - trigger: template
            value_template: >
                {{ state_attr('sensor.commerce_next_departures', 'next_departures')
                   | selectattr('line', 'eq', '1')
                   | selectattr('time', 'eq', '5 mn')
                   | list | count > 0 }}
      actions:
          - action: notify.mobile_app
            data:
                message: "Tram 1 in 5 minutes."
```

## How it works

-   **One request for the whole network.** A single SIRI `StopMonitoring` call returns every
    monitored stop, so watching ten stops costs no more than watching one.
-   **Timetables stay out of the database.** The daily schedule is served over WebSocket when
    the card asks for it, grouped by hour to keep the payload small, and never stored as a
    state.
-   **Offline data is embedded.** The stop index and the timetables are generated from the
    Nantes Métropole GTFS feed and refreshed monthly by a scheduled workflow.
-   **The card is a plain Web Component**, served by the integration itself and isolated in a
    shadow root.

## Data sources

Live departures come from the **Naolib / Okina SIRI** public endpoint, stops and timetables
from the **Nantes Métropole** open data GTFS feed. This project is not affiliated with
Semitan, Nantes Métropole or Okina.

## Contributing

Bug reports and suggestions are welcome in the
[issue tracker](https://github.com/dim4k/ha-naolib/issues). Please include your Home
Assistant version and, when relevant, the integration's diagnostics file.

## License

Released under the [MIT License](LICENSE).
