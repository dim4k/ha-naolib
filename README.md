<p align="center">
  <img src="https://github.com/dim4k/ha-naolib/blob/main/custom_components/naolib/brand/icon.png?raw=true" width="96" alt="">
</p>

<h1 align="center">Naolib Nantes for Home Assistant</h1>

<p align="center">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-default-41BDF5.svg" alt="HACS Default"></a>
  <a href="https://github.com/dim4k/ha-naolib/releases"><img src="https://img.shields.io/github/v/release/dim4k/ha-naolib?include_prereleases" alt="Release"></a>
  <a href="https://github.com/dim4k/ha-naolib/actions/workflows/hassfest.yaml"><img src="https://github.com/dim4k/ha-naolib/actions/workflows/hassfest.yaml/badge.svg" alt="Hassfest"></a>
  <a href="https://github.com/dim4k/ha-naolib/actions/workflows/hacs.yaml"><img src="https://github.com/dim4k/ha-naolib/actions/workflows/hacs.yaml/badge.svg" alt="HACS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/dim4k/ha-naolib" alt="License"></a>
</p>

<p align="center">
  Real-time bus, tram and ferry departures for the <b>Naolib</b> network (Nantes, France),<br>
  plus the availability of its bike-sharing stations
</p>

![Naolib cards](https://github.com/dim4k/ha-naolib/blob/main/screenshot.png?raw=true)

<p align="center">
  <sub>Unofficial project, not affiliated with Semitan, Nantes Métropole, Okina or JCDecaux.</sub>
</p>

## Features

- **Real-time departures** from the official SIRI feed, with a ticking countdown, a delay
  indicator and the last departure of the day flagged per line.
- **Bike stations** (ex-Bicloo) with bikes and docks available, plus the neighbouring stations
  when yours is empty or full.
- **Full daily timetable** fetched on demand from the card, for today and the six days ahead.
- **Guided setup** from a searchable list or a map, and **sensor entities** carrying every
  upcoming departure for your automations.

## Installation

Requires Home Assistant 2025.2 or newer — nothing else, the integration ships its own cards.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dim4k&repository=ha-naolib&category=integration)

Search for **Naolib Nantes** in HACS, download it, then restart Home Assistant. For a manual
install, copy `custom_components/naolib` into `config/custom_components` and restart.

## Configuration

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=naolib)

Add the **Naolib** integration, choose what to track — **a stop** (bus, tram, ferry) or **a
bike station** — then pick it from the searchable list of the whole network, or on a map
around a location (your home coordinates are pre-filled, distances included).

Entities are created right away; repeat to follow several stops or stations. The refresh
interval (60 s by default, 30 to 600 s) is set from the **Configure** button. Deleting an
entry removes its device, entities and history; cards already added to a dashboard have to be
removed by hand.

## Dashboard cards

Both cards are registered by the integration, so they show up in the card picker, and every
option below is also available from their visual editor.

### Departures — `custom:naolib-card`

```yaml
type: custom:naolib-card
entity: sensor.<your_stop>_next_departures
```

Lists the two next departures per line and direction. The **Voir tous les horaires** button
opens the timetable view: pick a line, switch direction, and the whole day shows up as one
tile per hour, scrolled to the current one. That view is theoretical only.

| Option                  | Default | Description                                               |
| ----------------------- | ------- | --------------------------------------------------------- |
| `entity`                | —       | Sensor of the stop to display (required)                  |
| `title`                 | stop    | Override the card title                                   |
| `lines`                 | all     | Only keep these line numbers                              |
| `direction`             | `0`     | `0` both directions, `1` or `2` to keep only one          |
| `walk_time`             | `0`     | Minutes of walk: hides departures you can no longer catch |
| `max_lines`             | `6`     | Maximum rows per direction (per card when compact)        |
| `show_timetable_button` | `true`  | Show the full timetable button                            |
| `compact`               | `false` | One line per departure, without direction grouping        |

### Bike station — `custom:naolib-bike-card`

```yaml
type: custom:naolib-bike-card
entity: sensor.<your_station>_bikes_available
```

Shows the bikes and docks available, a gauge of how full the station is, a warning when
renting or returning is suspended, and the neighbouring stations with their distance.

| Option          | Default | Description                                        |
| --------------- | ------- | -------------------------------------------------- |
| `entity`        | —       | “Bikes available” sensor of the station (required) |
| `title`         | station | Override the card title                            |
| `nearby_count`  | `3`     | Neighbouring stations listed, `0` to hide them     |
| `nearby_radius` | `500`   | Only list the stations within this many meters     |
| `show_docks`    | `true`  | Show the free docks next to the bikes              |
| `compact`       | `false` | Hide the fill gauge                                |

## Entities

**A stop** creates one sensor whose state is the timestamp of the very next departure
(`device_class: timestamp`). Its `next_departures` attribute holds the ordered list of
upcoming departures, each with `line`, `type` (`1` tram, `2` busway, `3` bus, `4` ferry),
`destination`, `direction`, `time` (`proche`, `4 mn`…), `expected_ts`, `delay_minutes` and
`is_last`. `stop_code` and `stop_label` identify the stop.

**A bike station** creates two sensors, **Bikes available** and **Docks available**. The first
carries the station details:

| Attribute         | Description                                                    |
| ----------------- | -------------------------------------------------------------- |
| `station_id`      | Station identifier on the network                              |
| `station_label`   | Station name as shown in the UI                                |
| `address`         | Street address of the station                                  |
| `capacity`        | Total number of docks                                          |
| `docks_available` | Free docks, mirrored from the second sensor                    |
| `is_renting`      | `false` when no bike can be taken out                          |
| `is_returning`    | `false` when no bike can be given back                         |
| `last_reported`   | Operator timestamp. Unreliable, so it is not shown on the card |
| `nearby_stations` | Neighbouring stations with their distance and counters         |

## Automations

The `naolib.get_departures` action returns the filtered departures of a stop:

```yaml
action: naolib.get_departures
data:
    config_entry_id: <entry id of the stop>
    lines: ["1", "C3"]
    walk_time: 5
    limit: 3
response_variable: departures
```

The `next_departures` attribute works just as well in a template trigger, without any call.

## How it works

- **One request for the whole network.** A single SIRI `StopMonitoring` call returns every
  monitored stop, so watching ten stops costs no more than watching one. The bike feed works
  the same way: one GBFS poll serves every station, which is also what makes the
  "nearby stations" list free.
- **Timetables stay out of the database.** The daily schedule is served over WebSocket when
  the card asks for it, grouped by hour, and never stored as a state. The stop index and the
  timetables are generated from the Nantes Métropole GTFS feed and refreshed monthly by a
  scheduled workflow, then shipped as a compressed SQLite database.
- **The cards are plain Web Components**, served by the integration itself and isolated in a
  shadow root.

## Data sources

Live departures come from the **Naolib / Okina SIRI** public endpoint, stops and timetables
from the **Nantes Métropole** open data GTFS feed, and the bike stations from the **Naolib
GBFS 3.0** feed operated by JCDecaux, referenced on
[transport.data.gouv.fr](https://transport.data.gouv.fr/datasets/offre-et-temps-reel-du-service-velos-en-libre-service-naolib-de-nantes-metropole-au-format-gbfs).

## Development

The card sources live in `src/` and are bundled into `custom_components/naolib/www/` by
esbuild; the generated bundles are committed, so rebuild them before opening a pull request.
The integration targets the **silver** quality scale, which requires the Python modules to
stay fully covered. The test suite needs Python 3.13.2 or newer.

```bash
npm ci && npm run check   # eslint + vitest + build
pip install ruff -r requirements_test.txt
ruff check . && ruff format --check . && pytest --cov=custom_components/naolib
```

A Compose file ships both runners if you would rather not install the toolchains — any other
command can be passed through, and dependencies are cached in named volumes:

```bash
docker compose run --rm python   # ruff check + ruff format --check + pytest
docker compose run --rm node     # eslint + vitest + build
```

## Contributing

Bug reports and suggestions are welcome in the
[issue tracker](https://github.com/dim4k/ha-naolib/issues). Please include your Home
Assistant version and, when relevant, the integration's diagnostics file.

## License

Released under the [MIT License](LICENSE).
