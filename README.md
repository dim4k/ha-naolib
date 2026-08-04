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
-   **Guided setup**: search a stop around a location on the map, or by typing part of its name.
-   **Full daily timetable** available from the card, fetched on demand, for today and the six days ahead.
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
then choose how to look for your stop:

-   **Around a location**: confirm the point to search around (your home coordinates are
    pre-filled) and pick your stop from the closest ones.
-   **By name**: type part of the stop name (`comme` finds `Commerce`; case and accents are
    ignored) and pick it from the matches.

The entities are created right away.

Repeat the process to follow several stops. The refresh interval, 60 seconds by default,
can be changed between 30 and 600 seconds from the **Configure** button of the integration.

### Removal

Go to **Settings** > **Devices & services** > **Naolib Nantes**, open the menu of the stop
you want to drop and choose **Delete**; its device, entities and history go with it.

To uninstall completely, remove every stop, then delete **Naolib Nantes** from HACS (or
delete `config/custom_components/naolib` for a manual install) and restart Home Assistant.
The card and its dashboard resource are removed with the integration; the cards left on
your dashboards have to be deleted by hand.

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
departure markers underneath. The **Voir tous les horaires** button opens the timetable view:
pick a line from the chips at the top, switch direction, and the whole day shows up as one
tile per hour, scrolled to the current one with the next passage highlighted. That view is
theoretical only — realtime belongs to the departures view above.

All options are available from the visual editor:

| Option                  | Default | Description                                             |
| ----------------------- | ------- | ------------------------------------------------------- |
| `entity`                | —       | Sensor of the stop to display (required)                 |
| `title`                 | stop    | Override the card title                                  |
| `lines`                 | all     | Only keep these line numbers                             |
| `direction`             | `0`     | `0` both directions, `1` or `2` to keep only one         |
| `walk_time`             | `0`     | Minutes of walk: hides departures you can no longer catch |
| `max_lines`             | `6`     | Maximum rows per direction (per card when compact)       |
| `show_timetable_button` | `true`  | Show the full timetable button                           |
| `compact`               | `false` | One line per departure, without direction grouping       |

## Action

`naolib.get_departures` returns the filtered departures of a stop, which is handy in
scripts and templates:

```yaml
action: naolib.get_departures
data:
    config_entry_id: <entry id of the stop>
    lines: ["1", "C3"]
    walk_time: 5
    limit: 3
response_variable: departures
```

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
    Nantes Métropole GTFS feed and refreshed monthly by a scheduled workflow. Timetables live
    in a compressed SQLite database, so only the stops you follow are ever read into memory.
-   **The card is a plain Web Component**, served by the integration itself and isolated in a
    shadow root.

## Data sources

Live departures come from the **Naolib / Okina SIRI** public endpoint, stops and timetables
from the **Nantes Métropole** open data GTFS feed. This project is not affiliated with
Semitan, Nantes Métropole or Okina.

## Development

The card sources live in `src/` and are bundled into `custom_components/naolib/www/` by
esbuild; the generated bundles are committed, so rebuild them before opening a pull request:

```bash
npm ci && npm run check   # eslint + vitest + build
pip install ruff -r requirements_test.txt
ruff check . && ruff format --check . && pytest
```

The integration targets the **silver** quality scale, which requires the Python modules to
stay fully covered:

```bash
pytest --cov=custom_components/naolib --cov-report=term-missing
```

The test suite runs against the Home Assistant package, which requires Python 3.13.2 or
newer.

## Contributing

Bug reports and suggestions are welcome in the
[issue tracker](https://github.com/dim4k/ha-naolib/issues). Please include your Home
Assistant version and, when relevant, the integration's diagnostics file.

## License

Released under the [MIT License](LICENSE).
