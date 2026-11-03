# %% 1. Settings
import Pkg
Pkg.activate(@__DIR__)
using GenX, Gurobi, JuMP, CSV, DataFrames, Dates

CASE = isempty(ARGS) ? joinpath(@__DIR__, "GenX_basecase") : abspath(only(ARGS))
OUT = joinpath(CASE, "results_" * Dates.format(now(), "yyyymmdd_HHMMSS_sss"))
ispath(OUT) && error("Result directory already exists: $OUT")
years = CSV.read(joinpath(CASE, "metadata/years.csv"), DataFrame).Year
setup = GenX.configure_settings(joinpath(CASE, "settings/genx_settings.yml"),
    joinpath(CASE, "settings/output_settings.yml"))
setup["MultiStageSettingsDict"] = GenX.configure_settings_multistage(
    joinpath(CASE, "settings/multi_stage_settings.yml"))
stages = setup["MultiStageSettingsDict"]
scale = setup["ParameterScale"] == 1 ? 1000.0 : 1.0
optimizer = GenX.configure_solver(joinpath(CASE, "settings"), Gurobi.Optimizer;
    solver_name = "gurobi")

# %% 2. Annual GenX models + BPESD11 adequacy
inputs, models = Dict(), Dict()
for p in eachindex(years)
    stages["CurStage"] = p
    directory = joinpath(CASE, "inputs", string(years[p]))
    inputs[p] = GenX.load_inputs(setup, directory)
    inputs[p] = GenX.configure_multi_stage_inputs(inputs[p], stages, setup["NetworkExpansion"])
    GenX.compute_cumulative_min_retirements!(inputs, p)
    model = GenX.generate_model(setup, inputs[p], optimizer)

    policy = first(CSV.read(joinpath(directory, "metadata/KPG_policy.csv"), DataFrame))
    factors = CSV.read(joinpath(directory,
        "resources/policy_assignments/Resource_capacity_reserve_margin.csv"), DataFrame)
    alpha = Dict(String(r.Resource) => r.Derating_factor_1 for r in eachrow(factors))
    if policy.Apply_Adequacy == 1
        @constraint(model, cBPESD_RA,
            sum(alpha[name] * model[:eTotalCap][g] for (g, name) in enumerate(inputs[p]["RESOURCE_NAMES"])) >=
            (1 + policy.Reserve_Margin) * policy.Peak_Load_MW / scale)
    end
    models[p] = model
end

# %% 3. Native DDP and results
mkdir(OUT)
println("Results: ", OUT)
models, stats, inputs = GenX.run_ddp(OUT, models, setup, inputs)
for p in eachindex(years)
    stages["CurStage"] = p
    stage_out = joinpath(OUT, "results_p$p")
    GenX.write_outputs(models[p], stage_out, setup, inputs[p])
    summary = joinpath(stage_out, "system_summary.yml")
    if isfile(summary)
        lines = filter(line -> !startswith(strip(line), "JULIA_STDLIB:"), readlines(summary))
        write(summary, join(lines, "\n") * "\n")
    end
end
GenX.write_multi_stage_outputs(stats, OUT, setup, inputs)
