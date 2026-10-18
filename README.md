## Citation

If you use the KPG 193 test system in your work, please cite:

```bibtex
@article{song2024kpg,
  title={KPG 193: A Synthetic Korean Power Grid Test System for Decarbonization Studies},
  author={Song, Geonho and Kim, Jip},
  journal={arXiv preprint arXiv:2411.14756},
  year={2024}
}
```

# KPG 193 — BPESD-11 Test Grid Data

![License: ODbL](https://img.shields.io/badge/License-ODbL_1.0-blue.svg)
![Version: v2.0](https://img.shields.io/badge/Version-v2.0-green.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)

![KPG 193 BPESD-11 network evolution from 2024 to 2038](kpg193_ver2_0_2024_2038_1s_w1600.gif)
*Network evolution of the KPG 193 BPESD-11 test system from 2024 to 2038.*


## What is KPG 193 BPESD-11?

KPG 193 BPESD-11 extends the [KPG 193 test system](https://github.com/agm-center/kpg-testgrid) with Korean transmission grid scenarios from 2024 to 2038 based on Korea's 11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD-11, 11차 전력수급기본계획). It provides yearly MATPOWER-compatible network snapshots, hourly time-series profiles, renewable capacity data, and expansion metadata.

The dataset reflects planned generation and transmission changes under Korea's **11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD-11)**. Across the planning horizon, it includes 61 generator additions, 49 generator retirement records, 207 AC branch additions, and 7 DC line additions.

This dataset is part of the KPG Test System module within the KPG (Korean Power Grid) Platform. It remains compatible with **KPG Run** for power flow and unit commitment simulations and **KPG View** for map‑based network and result visualization.

| Module | Description |
|--------|-------------|
| [**KPG Test System**](https://agm.kentech.ac.kr/docs/kpg-test-system/) (this repo) | Synthetic grid data — network, generators, demand, renewable, and commitment profiles |
| [**KPG Run**](https://agm.kentech.ac.kr/docs/kpg-run/user-interface/) | Desktop application for solving ED, UC, DC-OPF, and AC-OPF problems |
| [**KPG View**](https://agm.kentech.ac.kr/docs/kpg-view/overview/) | Interactive map-based visualization of grid networks and simulation results |


## Dataset Overview

| Component | Count / range |
|---|---|
| Buses | 193 |
| Active conventional generators | 183–199 |
| Conventional generator records | 183–244 |
| AC branches | 358–565 |
| DC lines | 1–8 |
| Voltage levels | 154 / 345 / 765 kV |
| Renewable types | Solar / Wind / Hydro |
| Base year | 2025 |
| Planning horizon | 2024–2038 |
| Total years | 15 |
| Temporal resolution | Hourly, 8,760 h/year (8,784 h in leap years) |

## Selective Download

Each scenario year is stored as a separate folder, such as `kpg193_v2_0_2038`. Use sparse checkout to download only the year folders you need.

```bash
git clone --filter=blob:none --sparse https://github.com/agm-center/kpg-testgrid-bpesd11.git
cd kpg-testgrid-bpesd11
git sparse-checkout set kpg193_v2_0_2024 kpg193_v2_0_2030 kpg193_v2_0_2038
```


## Structure

```
kpg193_v2_0_{year}/                 (year: 2024–2038)
├── kpg193_ver2_0_{year}.png         # Network visualization
├── network/
│   ├── m/KPG193_ver2_0_{year}.m      # MATPOWER case file
│   ├── mat/KPG193_ver2_0_{year}.mat  # MATPOWER case file (binary)
│   └── metadata/
│       ├── bus_metadata/
│       │   └── bus_metadata_{year}.csv
│       ├── expansion/
│       │   ├── gen_changes.csv
│       │   ├── line_changes.csv
│       │   └── dcline_changes.csv
│       └── generator_metadata/
│           └── generator_metadata_{year}.csv
├── profile/
│   ├── demand/                      # demand_{day}.csv
│   ├── renewables/                  # renewables_{day}.csv
│   └── commitment_decision/         # commitment_decision_{day}.csv
└── renewables_capacity/
    ├── solar_generators.csv
    ├── wind_generators.csv
    └── hydro_generators.csv
```

Each profile directory contains one daily file per calendar day (365 files, or 366 files in leap years). Demand and renewable profile files contain 24 hours × 193 buses per day, while commitment files contain hourly on/off status values for conventional generators.

## Data Description

### `network/`

MATPOWER-compatible case files for each yearly 193-bus Korean transmission network scenario.

### `network/metadata/bus_metadata/`

`bus_metadata_{year}.csv` provides bus location and name metadata.

| Column | Description |
|---|---|
| `bus_id` | Bus ID |
| `Latitude`, `Longitude` | Geographic coordinates |
| `name_Korean`, `name_English` | Bus names in Korean and English |

### `network/metadata/expansion/`

Year-by-year generation and transmission expansion records based on Korea's 11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD-11).

**`gen_changes.csv`** — generator additions and retirements

| Column | Description |
|---|---|
| `project_id`, `source` | Plan ID and source |
| `name_kor`, `name_eng` | Plant name |
| `effective_year`, `effective_month` | Effective date |
| `action` | `add` or `retire` |
| `gen_type` | Fuel type |
| `bus` | Bus ID |
| `Pmax`, `Pmin` | Output limits (MW) |
| `ramp_10`, `ramp_30` | Ramp limits |

**`line_changes.csv`** — AC branch additions

| Column | Description |
|---|---|
| `project_id`, `source` | Plan ID and source |
| `effective_year`, `effective_month` | Effective date |
| `voltage_level` | Voltage class |
| `fbus`, `tbus` | From/to bus IDs |
| `r`, `x`, `b` | Branch parameters |
| `rateA` | Thermal limit (MVA) |

**`dcline_changes.csv`** — DC line additions

| Column | Description |
|---|---|
| `effective_year`, `effective_month` | Effective date |
| `voltage_level` | DC voltage class |
| `fbus`, `tbus` | From/to bus IDs |
| `Pmin`, `Pmax` | Flow limits (MW) |

### `network/metadata/generator_metadata/`

`generator_metadata_{year}.csv` provides cost and technical parameters for conventional generators.

| Column | Description |
|---|---|
| `gen_id`, `bus_id` | Generator and bus IDs |
| `plant_name_kor`, `unit_name` | Plant and unit name |
| `pmax_mw` | Maximum output (MW) |
| `gen_type` | Fuel type |
| `fuel_cost_krw_per_gcal` | Fuel cost |
| `heat_lhc_gcal_per_mwh` | Heat rate |
| `heat_nlhc_gcal_per_h` | No-load heat consumption |
| `gencost_a`, `gencost_b`, `gencost_c` | Cost coefficients |
| `final_cost_function_1000krw_per_h` | Cost function |

### `profile/demand/`

`demand_{day}.csv` provides hourly active and reactive demand by bus.

| Column | Description |
|---|---|
| `hour` | Hour of day |
| `bus_id` | Bus ID |
| `demandP` | Active demand (MW) |
| `demandQ` | Reactive demand (MVAr) |

### `profile/renewables/`

`renewables_{day}.csv` provides normalized renewable generation ratios by bus. Multiply each ratio by the installed capacity in `renewables_capacity/` to obtain generation in MW.

| Column | Description |
|---|---|
| `hour` | Hour of day |
| `bus_id` | Bus ID |
| `pv_profile_ratio` | Solar ratio |
| `wind_profile_ratio` | Wind ratio |
| `hydro_profile_ratio` | Hydro ratio |

### `profile/commitment_decision/`

`commitment_decision_{day}.csv` provides hourly on/off status values for conventional generators.

| Column | Description |
|---|---|
| `hour` | Hour of day |
| `generator_id` | Generator ID |
| `status` | 1 = on, 0 = off |

### `renewables_capacity/`

Installed renewable capacity by bus for solar, wind, and hydro resources.

| Column | Description |
|---|---|
| `bus_ID` | Bus ID |
| `Type` | Renewable type |
| `Pmax [MW]` | Installed capacity |
| `Pmin [MW]` | Minimum output |

## License

This dataset is released under the [Open Database License (ODbL 1.0)](http://opendatacommons.org/licenses/odbl/1.0/).
