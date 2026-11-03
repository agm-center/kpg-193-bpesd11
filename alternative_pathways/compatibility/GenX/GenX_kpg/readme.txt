Generate KPG Run datasets from the supplied GenX results

Run from this GenX_kpg folder:

  python -m pip install -r ../requirements.txt
  python export_to_KPG.py

Inputs: ../GenX_basecase/inputs, ../GenX_basecase/results (DDP),
        and uc_initial_state.csv in this folder.
Output: ./kpg193_genx_base_2024/ ... ./kpg193_genx_base_2038/
Each output contains network .m/.mat files and 365/366 daily profiles.
Open the desired annual output folder in KPG Run.
Conversion uses Python and the saved results.

Replace previously generated annual folders:
  python export_to_KPG.py --overwrite

Generate only 2038:
  python export_to_KPG.py --years 2038

Convert a newly solved case (replace the timestamp placeholders):
  python export_to_KPG.py --inputs ../GenX_basecase_YYYYMMDD_HHMMSS_ffffff --results ../GenX_basecase_YYYYMMDD_HHMMSS_ffffff/results_YYYYMMDD_HHMMSS_sss --initial-state UPDATED_UC.csv --output ./kpg_YYYYMMDD_HHMMSS_ffffff

The supplied uc_initial_state.csv matches the supplied DDP solution. Changing
inputs or rerunning GenX can change the fleet and its required initial states.
Changed demand, renewable profiles or operating parameters can also require
new states even when capacities stay the same. Prepare and validate an updated
UC CSV before converting a changed case. This release reads that CSV; it does
not include a solver to generate new UC initial states automatically.

CSV columns: Year, Resource (unit name), Bus, Pmax_MW, Pmin_MW, Status (0/1),
Initial_P_MW, Inistate_h (positive = hours ON; negative = hours OFF).
The converter fills mpc.gen.Pg and the initial-duration/output fields of
mpc.genthermal in both .m and .mat. GEN_STATUS records equipment availability.
The supplied states were validated for January 1 without transmission
constraints, using Gurobi with a 5% MIP gap.
