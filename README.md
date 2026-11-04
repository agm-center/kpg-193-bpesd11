## Citation

If you use the KPG 193 test system in your work, please cite:

```bibtex
@INPROCEEDINGS{11225382,
  author={Song, Geonho and Kim, Jip},
  booktitle={2025 IEEE Power & Energy Society General Meeting (PESGM)}, 
  title={KPG 193: A Synthetic Korean Power Grid Test System for Decarbonization Studies}, 
  year={2025},
  pages={1-5},
  doi={10.1109/PESGM52009.2025.11225382}
}
```

# KPG 193 — BPESD11 Test Grid Data

![License: ODbL](https://img.shields.io/badge/License-ODbL_1.0-blue.svg)
![Version: v2.0](https://img.shields.io/badge/Version-v2.0-green.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)

![KPG 193 BPESD11 network evolution from 2024 to 2038](kpg193_ver2_0_2024_2038_1s_w1600.gif)
*Network evolution of the KPG 193 BPESD11 test system from 2024 to 2038.*


## What is KPG 193 BPESD11?

### Reference Expansion Pathway (11th BPESD11)

KPG 193 BPESD11 extends the [KPG 193 test system](https://github.com/agm-center/kpg-testgrid) with Korean transmission grid scenarios from 2024 to 2038 based on Korea's 11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD11, 11차 전력수급기본계획). It provides yearly MATPOWER-compatible network snapshots, hourly time-series profiles, renewable capacity data, and expansion metadata.

The dataset reflects planned generation and transmission changes under Korea's **11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD11)**. Across the planning horizon, it includes 61 generator additions, 49 generator retirement records, 207 AC branch additions, and 7 DC line additions.

### Alternative Expansion Pathway

The **KPG 193-BPESD11** extension supports studies of alternative generation and storage expansion pathways. It adds bus-level thermal, renewable and storage candidates, retrofit options, location-dependent costs and planning parameters. Open source expansion tool-compatible (Currently supports GenX) inputs and conversion scripts connect expansion planning to operational analysis: optimize an alternative pathway in GenX, then convert the results back into annual KPG-format datasets compatible with **KPG Run**.

### KPG Platform

This dataset is part of the KPG Test System module within the KPG (Korean Power Grid) Platform. It remains compatible with **KPG Run** for optimal power flow and unit commitment simulations and **KPG View** for map‑based network and result visualization.

| Module | Description |
|--------|-------------|
| [**KPG Test System**](https://agm.kentech.ac.kr/docs/kpg-test-system/) (this repo) | Synthetic grid data — network, generators, demand, renewable, and commitment profiles |
| [**KPG Run**](https://agm.kentech.ac.kr/docs/kpg-run/user-interface/) | Desktop application for solving ED, UC, DC-OPF, and AC-OPF problems |
| [**KPG View**](https://agm.kentech.ac.kr/docs/kpg-view/overview/) | Interactive map-based visualization of grid networks and simulation results |


## Dataset Overview

### Reference Expansion Pathway (11th BPESD11)

| Component | Count / range |
|---|---|
| Buses | 193 |
| Conventional generators with positive capacity | 193–199 |
| Conventional generator records | 194–244 |
| AC branches | 382–565 |
| DC lines | 2–8 |
| Voltage levels | 154 / 345 / 765 kV |
| Renewable types | Solar / Wind / Hydro |
| Base year | 2024 |
| Planning horizon | 2024–2038 |
| Total years | 15 |
| Temporal resolution | Hourly, 8,760 h/year (8,784 h in leap years) |

### Alternative Expansion Pathway

| Component | Coverage |
|---|---|
| Generation candidates | LNG, Nuclear, Solar PV, Onshore Wind and Offshore Wind |
| Storage and retrofits | Six-hour BESS; hydrogen and ammonia retrofit options |
| Planning parameters | Retirements, emissions, reserve margins, land-cost multipliers and ELCC curves |
| Offshore wind profiles | Hourly profiles at 61 candidate buses |
| Platform compatibility | GenX Support, input conversion and KPG-format result export |

## Selective Download

Each scenario year is stored as a separate folder, such as `kpg193_v2_0_2038`. Use sparse checkout to download only the year folders you need.

```bash
git clone --filter=blob:none --sparse https://github.com/agm-center/kpg-testgrid-bpesd11.git
cd kpg-testgrid-bpesd11
git sparse-checkout set kpg193_v2_0_2024 kpg193_v2_0_2030 kpg193_v2_0_2038
```


For the complete GenX example, download `alternative_pathways/` and all annual folders from 2024 to 2038.

## Structure

```text
.
├── kpg193_v2_0_{year}/                  # Reference pathway, 2024–2038
│   ├── kpg193_ver2_0_{year}.png         # Network visualization
│   ├── network/
│   │   ├── m/KPG193_ver2_0_{year}.m
│   │   ├── mat/KPG193_ver2_0_{year}.mat
│   │   └── metadata/
│   │       ├── bus_metadata/bus_metadata_{year}.csv
│   │       ├── generator_metadata/generator_metadata_{year}.csv
│   │       └── expansion/
│   │           ├── gen_changes.csv
│   │           ├── line_changes.csv
│   │           └── dcline_changes.csv
│   ├── profile/
│   │   ├── demand/                     # demand_{day}.csv
│   │   ├── renewables/                 # renewables_{day}.csv, including offshore
│   │   └── commitment_decision/        # commitment_decision_{day}.csv
│   └── renewables_capacity/
│       ├── solar_generators.csv
│       ├── wind_generators.csv
│       └── hydro_generators.csv
└── alternative_pathways/               # Alternative pathway inputs and tools
    ├── candidates/                     # Generation, storage, retrofit and transmission
    ├── parameters/                     # Shared planning inputs
    └── compatibility/
        └── GenX/
            ├── Project.toml / Manifest.toml / requirements.txt
            ├── README.md               # Run commands and model settings
            ├── export_to_GenX.py        # Dataset → timestamped GenX case
            ├── run_GenX.jl              # Run the annual expansion example
            ├── GenX_basecase/          # Supplied inputs and solved DDP results
            │   ├── inputs/2024/ ... 2038/
            │   ├── settings/ metadata/
            │   └── results/results_p1/ ... results_p15/
            ├── GenX_basecase_{timestamp}/  # New cases generated locally
            │   ├── inputs/ settings/ metadata/
            │   └── results_{timestamp}/   # New DDP solution
            └── GenX_kpg/
                ├── export_to_KPG.py    # GenX results + saved UC states → KPG format
                ├── uc_initial_state.csv / readme.txt
                └── kpg193_genx_base_{year}/  # Generated locally; not distributed
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

Year-by-year generation and transmission expansion records based on Korea's 11th Basic Plan for Long-Term Electricity Supply and Demand (BPESD11).

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

`renewables_{day}.csv` provides normalized renewable generation ratios by bus. For solar, onshore wind and hydro, multiply each ratio by the corresponding installed capacity in `renewables_capacity/` to obtain available generation in MW.

| Column | Description |
|---|---|
| `hour` | Hour of day |
| `bus_id` | Bus ID |
| `pv_profile_ratio` | Solar ratio |
| `wind_profile_ratio` | Onshore wind ratio |
| `hydro_profile_ratio` | Hydro ratio |
| `offshore_profile_ratio` | Fixed-bottom offshore wind ratio; zero at buses without an offshore candidate |


The same offshore weather is used across 2024–2038: days 1–365 retain their source indices, and day 366 uses source day 59. Existing solar, wind and hydro profile values are retained.

### `profile/commitment_decision/`

`commitment_decision_{day}.csv` provides hourly on/off status values for conventional generators.

| Column | Description |
|---|---|
| `hour` | Hour of day |
| `gen_id` | Generator ID; matches `generator_metadata_{year}.csv` and the MATPOWER generator row |
| `status` | 1 = on, 0 = off |

### `renewables_capacity/`

Installed renewable capacity by bus for solar, wind, and hydro resources.

| Column | Description |
|---|---|
| `bus_id` | Bus ID |
| `gen_type` | Renewable type |
| `pmax_mw` | Installed capacity (MW) |
| `Pmin [MW]` | Minimum output |

### `alternative_pathways/candidates/`

Bus-level options for constructing alternative expansion pathways.

| File | Description |
|---|---|
| `thermal_candidates.csv` | BPESD11 and additional LNG/Nuclear candidates, with size limits, lead times, investment costs and operating parameters |
| `renewable_candidates.csv` | Solar PV, onshore wind and fixed-bottom offshore wind potential, costs and lead times by bus |
| `storage_candidates.csv` | BESS locations, power/energy limits, duration, efficiency and costs |
| `retrofit_candidates.csv` | Existing-generator hydrogen/ammonia conversion options, costs and emission factors |
| `transmission_candidates.csv` | Planned transmission projects, including endpoints, commissioning years, capacity, length, costs and electrical parameters |
| `unallocated_candidates.csv` | National BPESD11 project pools without a fixed site, with eligible technologies, years and capacity limits |

### Sources and transformations

| Data | Source | Applied values |
|---|---|---|
| Planned generation, retirements and transmission | [BPESD11](https://www.kpx.or.kr/boardDownload.es?bid=ATT&list_no=74420&seq=1) and the supplied annual KPG snapshots | 2024–2038 project schedules; national full-plan capacity of 268.1 GW in 2038 (p.54) |
| Generation investment and fixed O&M | [Moon et al. (2025)](https://doi.org/10.1016/j.esr.2025.101897), p.6, §§3.4.3–3.4.4 | 2023 OCC in USD/kW: LNG 1,154; Nuclear 3,050; PV 1,162; Onshore Wind 2,053; Offshore Wind 4,985. Annual changes: +1.62%, +2.55%, −2.8%, −1.8%, −2.3%, respectively. FOM in USD/(kW year): 42, 139, 24, 46, 105 |
| Thermal operating parameters | KPG generator cost curves and operating specifications | December-2024 fuel prices: LNG 82,687.26 and Nuclear 2,565.66 KRW/Gcal |
| Additional LNG / nuclear sites | Screening adapted from [GRIDCERF](https://doi.org/10.1038/s41597-023-02694-y) and [OR-SAGE](https://info.ornl.gov/sites/publications/files/Pub30613.pdf) | 149 LNG and 25 nuclear buses; slope ≤12%; nuclear population ≤500 persons/mi² and coast distance ≤5 km; contiguous area ≥1 km² LNG / 2.0234 km² nuclear |
| PV / onshore wind potential | EGIS 2025 land cover, VWorld and EcoBank protection layers, Copernicus GLO-90 terrain; project GIS screening | PV 36 MWdc/km²; onshore wind 3 MW/km²; protection and optional exclusion areas included |
| Offshore wind potential and profile | [GEBCO 2025](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid) and 2022 KMA LDAPS weather | Depth ≤50 m; 3 MW/km²; 61 candidate buses; wind at 93 m |
| BESS locations and costs | [KPX 2025 first ESS tender](https://new.kpx.or.kr/boardDownload.es?bid=0042&list_no=75204&seq=1); [ATB 2024 v3 workbook](https://data.openei.org/files/6006/2024_v3_Workbook.xlsx), Utility-Scale Battery Storage cells I111/I128; [U.S. CPI-U](https://www.bls.gov/regions/northeast/data/consumerpriceindex_us_table.htm) | 48 mapped buses; 6 h; 10–100 MW/unit; 5 units/bus; 85% round-trip efficiency. Moderate scenario, projection year 2024: OCC 3,457,647,638.46 KRW/MW; FOM 86,441,190.96 KRW/(MW year) |
| Lead times and technical lives | KPG_Expansion planning assumptions; [ATB 2024 technical lifetimes](https://atb.nlr.gov/electricity/2024/definitions) | Additional LNG 3.3333 y; Nuclear 7 y; PV 1.5 y; Wind 4 y; BESS 1 y; planned thermal candidates 0 y. Lives: LNG 30 y, Nuclear 60 y, RE 30 y, BESS 15 y |
| Hydrogen / ammonia retrofits | [Öberg et al. (2022), Table 3](https://doi.org/10.1016/j.ijhydene.2021.10.035); [BloombergNEF (2022), Appendix A p.20](https://assets.bbhub.io/professional/sites/24/BNEF-Japans-Costly-Ammonia-Coal-Co-Firing-Strategy_FINAL.pdf) | 100% hydrogen firing: 25% of LNG new-build OCC. Coal with 20% ammonia energy share: 11% of coal new-build OCC |
| Regional land costs | January-2025 assessed parcel prices, aggregated to KPG buses (`bus_land_prices.csv`, ALL4: forest, miscellaneous land, field and paddy) | Median bus price 27,206.963319 KRW/m²; investment shares: LNG 5%, Nuclear 1%, PV 20%, onshore wind 3.5%, offshore wind 0% |
| Direct CO₂ factors | Technology-average proxies retained from the DC study inputs | Coal / IGCC 0.8384; LNG 0.38; Nuclear 0 tCO₂/MWh |
| Policy parameters and peak demand | BPESD11 emissions / reserve-margin schedules; supplied annual demand; study curtailment assumption | CO₂: 145.9 Mt in 2030 and 83.1 Mt in 2038. Reserve margins: 20% through 2028, 21% in 2029–2032, 22% thereafter. Curtailment: 3% through 2034, 5% thereafter |
| Renewable capacity-credit curves | [Paik (2024), Table 1, Avg. column, p.71](https://doi.org/10.7836/kses.2024.44.4.067) | Penetration 5%, 10%, 15%, 20%, 30%; reference capacity 110,237 MW |

### `alternative_pathways/parameters/`

Shared inputs for planning studies and comparison with the reference pathway.

| File | Description |
|---|---|
| `bpesd11_planned_capacity.csv` | Full national planned installed/effective capacity mix, including unallocated projects; 2038 total installed capacity is 268.1 GW |
| `planned_retirements.csv` | Generator IDs and planned retirement years/months |
| `emission_factors.csv` | Direct operational CO₂ factors by fuel, in tCO₂/MWh |
| `policy_mandates.csv` | Annual emission caps, planning reserve margins, curtailment reference limits and full-year peak demand (`Peak_Load_MW`) |
| `cost_multipliers.csv` | Bus land-price multipliers, normalized to a median of 1 |
| `elcc_curves.csv` | Renewable capacity-credit curves by penetration level |

Demand uses the annual `profile/demand/` files. The GenX converter selects eight K-medoids representative days per year, including the maximum net-demand and maximum net-demand ramp-down days.

### `alternative_pathways/compatibility/GenX/`

The example optimizes annual investments over 2024–2038 and converts the results to KPG Run datasets. See the [GenX README](alternative_pathways/compatibility/GenX/README.md) for settings and [conversion instructions](alternative_pathways/compatibility/GenX/GenX_kpg/readme.txt) for UC initial-state requirements.

| File / folder | Description |
|---|---|
| `export_to_GenX.py` | Selects representative days and creates annual inputs in a new timestamped GenX case |
| `GenX_basecase/` | Supplied annual inputs, settings and solved DDP results |
| `run_GenX.jl` | Runs GenX DDP with annual BPESD11 adequacy; writes `results_<timestamp>/results_p1` through `results_p15` in the selected case |
| `GenX_kpg/export_to_KPG.py` | Converts solved capacities and saved UC initial states into annual KPG networks and profiles |
| `GenX_kpg/uc_initial_state.csv` | Saved January-1 UC initial states for the supplied DDP fleet, keyed by year and unit name |
| `GenX_kpg/readme.txt` | Short conversion instructions; annual output folders are generated here and omitted from the download |

To generate annual KPG datasets directly from the supplied solution, run from `alternative_pathways/compatibility/GenX/GenX_kpg/`:

```bash
python -m pip install -r ../requirements.txt
python export_to_KPG.py
```

To rebuild inputs and solve a changed planning case, run from `alternative_pathways/compatibility/GenX/`:

```bash
python -m pip install -r requirements.txt
julia --project=. -e 'using Pkg; Pkg.instantiate()'
python export_to_GenX.py
# Use the new case folder printed by export_to_GenX.py:
julia --project=. run_GenX.jl GenX_basecase_YYYYMMDD_HHMMSS_ffffff
```

## License

This dataset is released under the [Open Database License (ODbL 1.0)](http://opendatacommons.org/licenses/odbl/1.0/). GenX is installed separately under its upstream software license; Gurobi and KPG Run are not distributed with the dataset.
