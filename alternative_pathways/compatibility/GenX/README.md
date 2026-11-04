# GenX example

Run from this folder with Julia 1.12, GenX 0.4.5 and a Gurobi license:

```bash
python -m pip install -r requirements.txt
julia --project=. -e 'using Pkg; Pkg.instantiate()'
python export_to_GenX.py
# Use the new case folder printed above:
julia --project=. run_GenX.jl GenX_basecase_YYYYMMDD_HHMMSS_ffffff
```

Input generation creates a new timestamped case and accepts `--case-dir` for an empty destination. Each solve writes `results_<timestamp>/` inside its case. Running `run_GenX.jl` without a case argument uses the supplied `GenX_basecase` inputs. The supplied solution remains in `GenX_basecase/results/`.

| Setting | Example value |
|---|---|
| Horizon / solve | 2024–2038, annual stages; GenX DDP; WACC 6%; 1,300 KRW/USD |
| Representative days | Eight per year; maximum net demand and maximum within-day net-demand down-ramp included |
| Adequacy | Applied from 2026; thermal 100%, PV 14.3%, onshore/offshore wind 2.4%, hydro 21.2%, BESS 0%; RHS = (1 + reserve margin) × annual peak |
| Operating reserves | Hourly demand × (4,500 / 100,958); unmet reserves penalized at USD 2,000/MW per hour |
| Transmission | Fixed annual BPESD11 network, transport; 345/765 kV AC ratings × 0.7; 154 kV and HVDC unchanged |
| Dispatch | Continuous LP; zero minimum output; hourly ramps; linear full-load average generation costs; no UC |
| Investment timing | First eligible year = max(planned earliest year, 2024 + lead time); later investment enters service in the selected year; no minimum build size |
| Retirement | Planned retirement year; month is not represented in annual stages; voluntary early retirement allowed for existing thermal units |
| Storage | Six hours; 85% round-trip efficiency applied to charging; cyclic daily SOC; simultaneous charging/discharging allowed |
| Policies | Annual CO₂ caps applied; ELCC curves, curtailment caps and unallocated project pools are not applied |

Annual BPESD11 adequacy is added in `run_GenX.jl`. For KPG Run conversion commands and UC initial-state requirements, see [GenX_kpg/readme.txt](GenX_kpg/readme.txt).
