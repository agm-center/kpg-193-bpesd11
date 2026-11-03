#!/usr/bin/env python3

from pathlib import Path
import argparse, calendar, csv, datetime as dt, io, math, re, shutil, tempfile
import numpy as np
RELEASE = Path(__file__).resolve().parents[3]
EXP = RELEASE/'alternative_pathways'
CANDIDATE_FILES = {
    'thermal_candidates': 'thermal_candidates.csv',
    'RE_candidates': 'renewable_candidates.csv',
    'sto_candidates': 'storage_candidates.csv',
    'Retrofit_candidates': 'retrofit_candidates.csv',
    'tx_candidates': 'transmission_candidates.csv',
}
INITIAL = RELEASE/'kpg193_v2_0_2024'
MMBTU_PER_GCAL = 4.1868 / 1.05505585262
PEAK_CONTRIBUTIONS = dict(Nuclear=1., Coal=1., LNG=1., Solar=.143,
    Wind=.024, OffshoreWind=.024, Hydro=.212, BESS=0., Marine=0.,
    Bio=.459, FuelCell=.732, IGCC=1.,
    **{'Green-Hydrogen Firing':1., 'Coal-Ammonia Co-firing':1.})


def line_voltage_kv(native_rating_mw):
    # Published MW/circuit families (overhead/cable), including bundled lines.
    matches = {kv for unit, kv in [(452,154),(354,154),(1086,345),(953,345),(7290,765)]
               if 1 <= native_rating_mw/unit <= 16
               and math.isclose(native_rating_mw/unit, round(native_rating_mw/unit), abs_tol=1e-8)}
    if len(matches) != 1:
        raise ValueError(f'Unknown or ambiguous BPESD11 line rating: {native_rating_mw} MW')
    return matches.pop()


def apply_transmission_limits(network, metadata):
    assert len(network) == len(metadata)
    for line, source in zip(network, metadata):
        assert int(line['Network_Lines']) == int(source['Network_Lines'])
        lo, hi = float(source['Min_Flow_MW']), float(source['Max_Flow_MW'])
        assert lo <= 0 <= hi
        native = min(-lo, hi)
        kv = line_voltage_kv(native) if source['Kind'] == 'AC' else 0
        factor = 0.7 if kv in (345,765) else 1.0
        line['Line_Max_Flow_MW'] = native * factor
        line['Line_Max_Flow_Possible_MW'] = native * factor
        line['KPG_Native_Rating_MW'] = native
        line['KPG_Voltage_kV'] = kv
        line['KPG_Rating_Factor'] = factor

def read_csv(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def f(row, key, default=0):
    return float(row.get(key) or default)


def matrix(text, name):
    content = re.search(r'mpc\.' + name + r'\s*=\s*\[(.*?)\];', text, re.S).group(1)
    return np.array([[float(v) for v in line.split('%')[0].replace(';',' ').split()]
                     for line in content.splitlines() if line.split('%')[0].replace(';',' ').strip()])


def crf(life, rate):
    return 1/life if rate == 0 else rate/(1-(1+rate)**(-life))


def key(prefix, original):
    return prefix + '_' + re.sub('[^A-Za-z0-9_]+', '_', str(original))


def export_year_snapshots(ROOT,args):
    years = [int(y) for y in args.years.split(',')]
    assert years == sorted(set(years)) and set(years) <= set(range(2024,2039))
    assert args.krw_per_usd > 0 and args.wacc >= 0
    fx = args.krw_per_usd
    inputs = {n: read_csv(EXP/('candidates' if n.endswith('_candidates') else 'parameters')/
        CANDIDATE_FILES.get(n,n.lower()+'.csv')) for n in [
        'thermal_candidates','RE_candidates','sto_candidates','Retrofit_candidates',
        'Planned_Retirements','Emission_Factors','cost_multipliers','policy_mandates']}
    meta = read_csv(INITIAL/'network/metadata/generator_metadata/generator_metadata_2024.csv')
    text = next((INITIAL/'network/m').glob('*.m')).read_text()
    gen,cost,uc = [matrix(text,n) for n in ['gen','gencost','genthermal']]
    assert len(gen)==len(meta)==len(uc)
    retire = {int(r['gen_id']):int(r['Retirement_Year']) for r in inputs['Planned_Retirements']}
    factors = {r['gen_type']:f(r,'CO2_t_per_MWh') for r in inputs['Emission_Factors']}
    emission = {int(r['gen_id']):factors['IGCC' if 'IGCC' in r['plant_name_kor'] else r['gen_type']] for r in meta}
    land = {int(r['bus_id']):f(r,'Cost_Multiplier') for r in inputs['cost_multipliers']}
    policy = {int(r['year']):r for r in inputs['policy_mandates']}
    reps = read_csv(args.representative_results/'representative_days.csv')
    existing_re = {}
    for tech, file in [('Solar','solar'),('Wind','wind')]:
        for r in read_csv(INITIAL/f'renewables_capacity/{file}_generators.csv'):
            existing_re[int(r['bus_id']),tech] = f(r,'pmax_mw')
    for year in years:
        peak = float(policy[year]['Peak_Load_MW'])
        assert math.isfinite(peak) and peak > 0, f'Invalid annual peak for {year}'
        annual = RELEASE/f'kpg193_v2_0_{year}'
        annual_text = next((annual/'network/m').glob('*.m')).read_text()
        branch,dc = [matrix(annual_text,n) for n in ['branch','dcline']]
        for change in read_csv(annual/'network/metadata/expansion/line_changes.csv'):
            assert line_voltage_kv(f(change,'rateA')) == int(change['voltage_level'])
        profiles = {}
        selected = [r for r in reps if int(r['year'])==year]
        for rp in selected:
            day=int(rp['source_day'])
            renew=read_csv(annual/f'profile/renewables/renewables_{day}.csv')
            profiles[day]={}
            for tech,column in [('Solar','pv_profile_ratio'),('Wind','wind_profile_ratio'),('Hydro','hydro_profile_ratio')]:
                a=np.full((24,193),np.nan)
                for row in renew:a[int(row['hour'])-1,int(row['bus_id'])-1]=float(row[column])
                assert np.isfinite(a).all() and a.min()>=0
                profiles[day][tech]=a
        folder = ROOT/'cases'/f'kpg193_{year}'
        for sub in ['resources/policy_assignments','system','policies','metadata']:
            (folder/sub).mkdir(parents=True, exist_ok=True)
        resources = {n:[] for n in ['Thermal','Vre','Storage','Hydro']}
        mappings, fuels, technical = [], {'None':(0.,0.)}, []
        heat_by_gen = {}
        original_op = {}
        resource_aux = {}
        retrofit_hosts = {int(r['gen_id']) for r in inputs['Retrofit_candidates']
            if year >= max(f(r,'Earliest_Year'),2024+f(r,'Lead_Time'))
            and year < retire.get(int(r['gen_id']),9999) and f(r,'Max_Cap_MW') > 0}

        def common(name,bus,kind,technology,source,source_id,existing=0.,maxcap=0.,new=0):
            r = dict(Resource=name, Zone=int(bus), New_Build=new, Can_Retire=0,
                Existing_Cap_MW=existing, Max_Cap_MW=maxcap, Min_Cap_MW=0,
                Inv_Cost_per_MWyr=0., Fixed_OM_Cost_per_MWyr=0., Var_OM_Cost_per_MWh=0.,
                Heat_Rate_MMBTU_per_MWh=0., Fuel='None', Reg_Max=0.,Rsv_Max=0.,
                Reg_Cost=0.,Rsv_Cost=0.,region=f'KPG_B{int(bus):03d}',cluster=1)
            mappings.append(dict(Resource=name,Bus=int(bus),Kind=kind,Technology=technology,
                                 Source_File=source,Source_ID=source_id))
            resource_aux[name] = dict(kind=kind,technology=technology,bus=int(bus))
            return r

        def fuel(r,heat_gcal,price_krw,co2):
            heat = heat_gcal * MMBTU_PER_GCAL
            assert heat > 0 and price_krw > 0
            fuel_key = 'F_' + r['Resource']
            r.update(Heat_Rate_MMBTU_per_MWh=heat,Fuel=fuel_key)
            fuels[fuel_key] = (co2/heat,price_krw/fx/MMBTU_PER_GCAL)
            assert math.isclose(heat*fuels[fuel_key][0],co2,abs_tol=1e-12)
            return heat

        def investment(r,source,life,land_share=0):
            occ = f(source,'Inv_Cost_per_MW')*(1+f(source,'Annual_Cost_Change_rates'))**(year-2024)
            adjusted = occ*(1-land_share+land_share*land[r['Zone']])
            r['Inv_Cost_per_MWyr'] = adjusted/fx*crf(life,args.wacc)
            r['Fixed_OM_Cost_per_MWyr'] = f(source,'FOM_per_MWyr',f(source,'Incremental_FOM_per_MWyr'))/fx

        def thermal_fields(r,pmax,pmin,rampup,rampdn,start,ut,down):
            r.update(Model=2,Cap_Size=pmax,Start_Cost_per_MW=start/fx,Start_Fuel_MMBTU_per_MW=0.,
                     Up_Time=ut,Down_Time=down,Ramp_Up_Percentage=min(1.,rampup),
                     Ramp_Dn_Percentage=min(1.,rampdn),Min_Power=0.,Can_Retrofit=0,Retrofit=0,
                     Retrofit_Id='none',Retrofit_Efficiency=1.)
            technical.append(dict(Resource=r['Resource'],Source_Pmin_Fraction=pmin,
                Source_Ramp_Up_Per_Hour=rampup,Source_Ramp_Down_Per_Hour=rampdn,
                Source_Startup_KRW_per_MW=start,UT_hours=ut,DT_hours=down))

        for i,m in enumerate(meta):
            gid=i+1;K=gen[i,8];bus=int(gen[i,0]);end=retire.get(gid,9999)
            if K<=0:continue
            assert int(m['gen_id'])==gid and int(m['bus_id'])==bus
            op=1000*(cost[i,4]*K+cost[i,5]+cost[i,6]/K)
            price=f(m,'fuel_cost_krw_per_gcal'); heat_by_gen[gid]=op/price;original_op[gid]=op
            r=common(f'EXIST_TH_{gid:03d}',bus,'existing_thermal',m['gen_type'],
                     'bpesd2024:mpc.gen/gencost/genthermal',gid,existing=K if year<end else 0,maxcap=K)
            thermal_fields(r,K,gen[i,9]/K,uc[i,5]/K,uc[i,6]/K,1000*uc[i,10]/K,uc[i,1],uc[i,2])
            if gid in retrofit_hosts:
                r.update(Can_Retire=1,Can_Retrofit=1,Retrofit_Id=f'HOST_{gid:03d}')
            fuel(r,heat_by_gen[gid],price,emission[gid]);resources['Thermal'].append(r)

        for s in inputs['thermal_candidates']:
            name=key('CAN_TH',s['Resource']);K=f(s,'Max_Cap_MW');tech=s['Resource'].split('*')[1]
            available=year>=max(f(s,'Earliest_Year'),2024+f(s,'Lead_Time'))
            r=common(name,int(s['bus_id']),'candidate_thermal',tech,'thermal_candidates.csv',s['Resource'],
                     maxcap=f(s,'Max_units')*K if available else 0,new=1)
            thermal_fields(r,K,f(s,'Pmin'),f(s,'Ramprate'),f(s,'Ramprate'),f(s,'Startup_Cost'),f(s,'UT'),f(s,'DT'))
            heat=(f(s,'Heat_quad')*K+f(s,'Heat_lin')+f(s,'Heat_coeff')/K if s['Heat_Basis']=='absolute_MW'
                  else f(s,'Heat_quad')+f(s,'Heat_lin')+f(s,'Heat_coeff'))
            fuel(r,heat,f(s,'fuel_cost_krw_per_gcal'),f(s,'CO2_t_per_MWh'))
            investment(r,s,f(s,'Life_time'),f(s,'Land_Cost_Ratio'));resources['Thermal'].append(r)

        for s in inputs['Retrofit_candidates']:
            gid=int(s['gen_id']);end=retire.get(gid,9999);K=f(s,'Max_Cap_MW')
            available=year>=max(f(s,'Earliest_Year'),2024+f(s,'Lead_Time')) and year<end
            r=common(f'RETRO_G{gid:03d}',int(s['bus_id']),'retrofit',s['Retrofit_Fuel'],
                     'Retrofit_candidates.csv',s['Resource'],maxcap=K if available else 0,new=1)
            thermal_fields(r,K,f(s,'Pmin'),f(s,'Ramprate'),f(s,'Ramprate'),f(s,'Startup_Cost'),f(s,'UT'),f(s,'DT'))
            r.update(Retrofit=int(available),
                     Retrofit_Id=f'HOST_{gid:03d}' if available else 'none',Retrofit_Efficiency=1.)
            price=f(meta[gid-1],'fuel_cost_krw_per_gcal')*f(s,'Op_Cost_Multiplier')
            fuel(r,f(s,'Op_Cost_per_MWh')/price,price,f(s,'CO2_t_per_MWh'))
            retirement_step=next((y for y in years if y>=end),end)
            life=min(30,max(1,retirement_step-year));investment(r,s,life)
            assert math.isclose(r['Heat_Rate_MMBTU_per_MWh']*fuels[r['Fuel']][1]*fx,
                                f(s,'Op_Cost_per_MWh'),rel_tol=1e-8)
            resources['Thermal'].append(r)

        for s in inputs['RE_candidates']:
            if s['gen_type'] not in ('Solar','Wind'): continue
            bus=int(s['bus_id']);tech=s['gen_type'];oldcap=existing_re[bus,tech]
            r=common(f'EXIST_{tech}_B{bus:03d}',bus,'existing_re',tech,'bpesd2024:renewables_capacity',
                     f'{tech}:{bus}',existing=oldcap,maxcap=oldcap)
            r['Num_VRE_Bins']=1;resources['Vre'].append(r)
            available=year>=2024+f(s,'Lead_Time')
            r=common(key('CAN_RE',s['Resource']),bus,'candidate_re',tech,'RE_candidates.csv',s['Resource'],
                     maxcap=max(0,f(s,'Max_Cap_MW')-oldcap) if available else 0,new=1)
            r['Num_VRE_Bins']=1;investment(r,s,f(s,'Life_time'),f(s,'Land_Cost_Ratio'));resources['Vre'].append(r)

        def storage_fields(r,energy,charge,eff,model=2):
            # SOC is measured as deliverable electrical energy.
            r.update(Model=model,Existing_Cap_MWh=energy,Max_Cap_MWh=energy,Min_Cap_MWh=0,
                Existing_Charge_Cap_MW=charge,Max_Charge_Cap_MW=charge,Min_Charge_Cap_MW=0,
                Inv_Cost_per_MWhyr=0.,Fixed_OM_Cost_per_MWhyr=0.,
                Inv_Cost_Charge_per_MWyr=0.,Fixed_OM_Cost_Charge_per_MWyr=0.,
                Var_OM_Cost_per_MWh_In=0.,Self_Disch=0.,Eff_Up=eff,Eff_Down=1.,
                Min_Duration=0.,Max_Duration=0.,LDS=0)

        for s in inputs['sto_candidates']:
            available=year>=max(f(s,'Earliest_Year'),2024+f(s,'Lead_Time'))
            cap=f(s,'Max_units')*f(s,'Max_Cap_MW') if available else 0
            r=common(key('CAN_ST',s['Resource']),int(s['bus_id']),'candidate_bess','BESS',
                     'sto_candidates.csv',s['Resource'],maxcap=cap,new=1)
            storage_fields(r,0,0,f(s,'Roundtrip_Efficiency'))
            duration=f(s,'Duration_hours',6.)
            r.update(Max_Cap_MWh=duration*cap,Max_Charge_Cap_MW=cap,Min_Duration=duration,Max_Duration=duration,
                     Var_OM_Cost_per_MWh=f(s,'VOM_per_MWh')/fx)
            investment(r,s,f(s,'Life_time'));resources['Storage'].append(r)
        for h in read_csv(INITIAL/'renewables_capacity/hydro_generators.csv'):
            bus=int(h['bus_id']);K=f(h,'pmax_mw')
            if K<=0:continue
            r=common(f'HYDRO_B{bus:03d}',bus,'profile_hydro','Hydro',
                     'bpesd2024:hydro_generators.csv',bus,existing=K,maxcap=K)
            r['Num_VRE_Bins']=1;resources['Vre'].append(r)
        for kind,rows in resources.items():
            fields=None if rows else ['Resource','Zone','New_Build','Can_Retire','Existing_Cap_MW','Max_Cap_MW','Hydro_Energy_to_Power_Ratio']
            write_csv(folder/'resources'/f'{kind}.csv',rows,fields)
        all_res=[r for rows in resources.values() for r in rows]
        assert len({r['Resource'] for r in all_res})==len(all_res)
        write_csv(folder/'metadata/resource_mapping.csv',mappings)
        write_csv(folder/'metadata/thermal_source_parameters.csv',technical)

        network=[];network_meta=[]
        def line(name,start,end,rating,lower,upper,kind,source_row,x=0.,rr=0.,bb=0.):
            lid=len(network)+1
            network.append(dict(Network_zones=f'z{lid}' if lid<=193 else '',Network_Lines=lid,
                Start_Zone=int(start),End_Zone=int(end),Line_Max_Flow_MW=rating,
                Line_Loss_Percentage=0.,Line_Max_Reinforcement_MW=0.,Line_Reinforcement_Cost_per_MWyr=0.,
                transmission_path_name=name))
            network_meta.append(dict(Network_Lines=lid,Name=name,Kind=kind,FromBus=int(start),ToBus=int(end),
                Min_Flow_MW=lower,Max_Flow_MW=upper,x_pu=x,r_pu=rr,b_pu=bb,Source_Year=year,Source_Row=source_row))
        for i,b in enumerate(branch):
            if b[10]:line(f'AC_BPESD_{year}_{i+1}',b[0],b[1],b[5],-b[5],b[5],'AC',i+1,b[3],b[2],b[4])
        for i,d in enumerate(dc):
            if d[2]:line(f'DC_BPESD_{year}_{i+1}',d[0],d[1],max(abs(d[9]),abs(d[10])),d[9],d[10],'DC',i+1)
        write_csv(folder/'system/Network.csv',network);write_csv(folder/'metadata/network_mapping.csv',network_meta)

        selected=[r for r in reps if int(r['year'])==year]
        assert len(selected)==8
        demand_rows=[];variability_rows=[]
        for j,rp in enumerate(selected):
            day=int(rp['source_day'])
            native_load=read_csv(EXP.parent/f'kpg193_v2_0_{year}/profile/demand/demand_{day}.csv')
            native_demand=np.full((24,193),np.nan)
            for record in native_load:
                native_demand[int(record['hour'])-1,int(record['bus_id'])-1]=float(record['demandP'])
            assert np.isfinite(native_demand).all() and native_demand.min()>=0
            for h in range(24):
                t=j*24+h+1
                dr=dict(Voll=2600000/fx if t==1 else '',Demand_Segment=1 if t==1 else '',
                    Cost_of_Demand_Curtailment_per_MW=1 if t==1 else '',Max_Demand_Curtailment=1 if t==1 else '',
                    Rep_Periods=8 if t==1 else '',Timesteps_per_Rep_Period=24 if t==1 else '',
                    Sub_Weights=f(selected[t-1],'weight')*24 if t<=8 else '',Time_Index=t)
                dr.update({f'Demand_MW_z{b+1}':native_demand[h,b] for b in range(193)})
                demand_rows.append(dr)
                vr={'Time_Index':t}
                for s in all_res:
                    name=s['Resource'];aux=resource_aux[name]
                    if aux['kind'] in ('existing_re','candidate_re','profile_hydro'):
                        value=profiles[day][aux['technology']][h,aux['bus']-1]
                    else:value=1.
                    vr[name]=value
                variability_rows.append(vr)
        write_csv(folder/'system/Demand_data.csv',demand_rows)
        write_csv(folder/'system/Generators_variability.csv',variability_rows)
        fuel_rows=[dict(Time_Index=0,**{name:v[0] for name,v in fuels.items()})]
        fuel_rows += [dict(Time_Index=t,**{name:v[1] for name,v in fuels.items()}) for t in range(1,193)]
        write_csv(folder/'system/Fuels_data.csv',fuel_rows)
        write_csv(folder/'policies/CO2_cap.csv',[dict(Network_zones=f'z{b}',CO_2_Cap_Zone_1=1,
            CO_2_Max_Mtons_1=f(policy[year],'CO2_Emission_Cap_t_per_yr')/1e6 if b==1 else 0.) for b in range(1,194)])
        write_csv(folder/'metadata/KPG_policy.csv',[dict(Year=year,
            Peak_Load_MW=peak,Reserve_Margin=f(policy[year],'Planning_Reserve_Margin'),
            Apply_Adequacy=int(year>=2026),Curtailment_Max_Rate=f(policy[year],'RE_Curtailment_Max_Rate'),
            Hydro_Credit=.212,BESS_Credit=0.)])
        assert math.isclose(sum(f(r,'weight') for r in selected),365+calendar.isleap(year),abs_tol=1e-6)

def read(path):
    return read_csv(Path(path))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def number(row, field, default=0.0):
    return float(row.get(field) or default)


def build_case(args, snapshot_root):
    CASE=args.case_dir.resolve()
    YEARS=list(map(int,args.years.split(',')))
    assert YEARS==sorted(set(YEARS)) and YEARS[0]==2024 and YEARS[-1]<=2038
    LENGTHS=[b-a for a,b in zip(YEARS,YEARS[1:])]+[1]
    FX=args.krw_per_usd; RATE=args.wacc
    export_year_snapshots(snapshot_root,args)
    sources = {}
    for file in ['thermal_candidates', 'RE_candidates', 'sto_candidates', 'Retrofit_candidates']:
        sources[file] = {r['Resource']: r for r in read(EXP/'candidates'/CANDIDATE_FILES[file])}
    retire = {int(r['gen_id']): int(r['Retirement_Year'])
              for r in read(EXP/'parameters/planned_retirements.csv')}
    land = {int(r['bus_id']): number(r, 'Cost_Multiplier')
            for r in read(EXP/'parameters/cost_multipliers.csv')}
    policy = {int(r['year']): r for r in read(EXP/'parameters/policy_mandates.csv')}
    reps = read(args.representative_results/'representative_days.csv')
    first = snapshot_root/'cases/kpg193_2024'
    base_thermal = {r['Resource']: r for r in read(first/'resources/Thermal.csv')}
    alpha = PEAK_CONTRIBUTIONS
    peak2024 = number(read(first/'metadata/KPG_policy.csv')[0], 'Peak_Load_MW')
    reserve_fraction = 4500.0/peak2024
    offshore = [r for r in sources['RE_candidates'].values() if r['gen_type'] == 'OffshoreWind']
    (CASE/'metadata').mkdir(parents=True, exist_ok=True)
    write(CASE/'metadata/model_settings.csv',[dict(KRW_per_USD=FX,WACC=RATE)])
    write(CASE/'metadata/years.csv', [dict(Stage=i+1, Year=y, Length=LENGTHS[i]) for i, y in enumerate(YEARS)])

    if (CASE/'inputs').exists():
        raise FileExistsError(f'{CASE}: choose a new case directory')
    for stage, year in enumerate(YEARS, 1):
        src = snapshot_root/f'cases/kpg193_{year}'
        dst = CASE/f'inputs/{year}'
        for sub in ['resources', 'system', 'policies', 'metadata']:
            shutil.copytree(src/sub, dst/sub, dirs_exist_ok=True)
        mappings = read(dst/'metadata/resource_mapping.csv')
        tables = {name: read(dst/f'resources/{name}.csv') for name in ['Thermal', 'Vre', 'Storage', 'Hydro']}
        profile = read(dst/'system/Generators_variability.csv')
        chosen = [r for r in reps if int(r['year']) == year]
        offshore_values = []
        for r in chosen:
            day = int(r['source_day'])
            data = read(RELEASE/f'kpg193_v2_0_{year}/profile/renewables/renewables_{day}.csv')
            eligible_buses = {int(s['bus_id']) for s in offshore}
            offshore_values.append({(int(v['bus_id']), int(v['hour'])): number(v, 'offshore_profile_ratio')
                                    for v in data if int(v['bus_id']) in eligible_buses})
        for s in offshore:
            name = key('CAN_RE', s['Resource'])
            row = dict(tables['Vre'][0])
            bus = int(s['bus_id'])
            lead = number(s, 'Lead_Time')
            cost = number(s, 'Inv_Cost_per_MW') * (1+number(s, 'Annual_Cost_Change_rates'))**(year-2024)
            cost *= 1-number(s, 'Land_Cost_Ratio')+number(s, 'Land_Cost_Ratio')*land[bus]
            row.update(Resource=name, Zone=bus, New_Build=1, Can_Retire=0,
                       Existing_Cap_MW=0, Max_Cap_MW=number(s, 'Max_Cap_MW') if year >= 2024+lead else 0,
                       Min_Cap_MW=0, Inv_Cost_per_MWyr=cost/FX*crf(number(s, 'Life_time'), RATE),
                       Fixed_OM_Cost_per_MWyr=number(s, 'FOM_per_MWyr')/FX,
                       region=f'KPG_B{bus:03d}', cluster=1)
            tables['Vre'].append(row)
            mappings.append(dict(Resource=name, Bus=bus, Kind='candidate_re', Technology='OffshoreWind',
                                 Source_File='RE_candidates.csv', Source_ID=s['Resource']))
            for t, r in enumerate(profile):
                r[name] = offshore_values[t//24][bus, t%24+1]
        mapping = {r['Resource']: r for r in mappings}
        multi, deratings = [], []
        for category, rows in tables.items():
            for r in rows:
                m = mapping[r['Resource']]
                kind, tech = m['Kind'], m['Technology']
                life, earliest, retire_year, min_retire = 100, 2024, 9999, 0.0
                if kind == 'existing_thermal':
                    gid = int(m['Source_ID'])
                    r['Existing_Cap_MW'] = number(base_thermal[r['Resource']], 'Existing_Cap_MW')
                    r['Max_Cap_MW'] = r['Existing_Cap_MW']
                    r['Can_Retire'] = 1
                    retire_year = retire.get(gid, 9999)
                    prev = YEARS[stage-2] if stage > 1 else -9999
                    if prev < retire_year <= year:
                        min_retire = r['Existing_Cap_MW']
                elif kind.startswith('candidate') or kind == 'retrofit':
                    source = sources[Path(m['Source_File']).stem][m['Source_ID']]
                    life = number(source, 'Life_time', 30)
                    earliest = max(number(source, 'Earliest_Year', 2024), 2024+number(source, 'Lead_Time'))
                    if kind == 'retrofit':
                        retire_year = retire.get(int(source['gen_id']), 9999)
                        life = 100
                        r['Can_Retire'] = 1
                        if year >= retire_year:
                            r['Max_Cap_MW'] = 1e-7
                    r['New_Build'] = int(year >= earliest and year < retire_year)
                if category == 'Thermal':
                    r['Rsv_Max'] = min(1, number(r, 'Ramp_Up_Percentage'))
                elif category == 'Storage':
                    r['Rsv_Max'] = 1
                    if kind == 'candidate_bess':
                        r['Model'] = 1
                r['Reg_Max'] = 0
                retirement_step = next((y for y in YEARS if y>=retire_year),retire_year)
                recovery = min(30, max(1, retirement_step-year)) if kind=='retrofit' else life
                multi.append(dict(Resource=r['Resource'], Lifetime=life, Capital_Recovery_Period=recovery,
                                  WACC=RATE, Min_Retired_Cap_MW=min_retire,
                                  Min_Retired_Energy_Cap_MW=0, Min_Retired_Charge_Cap_MW=0,
                                  Contribute_Min_Retirement=1))
                deratings.append(dict(Resource=r['Resource'], Derating_factor_1=alpha[tech]))
            if rows:write(dst/f'resources/{category}.csv', rows)
        write(dst/'resources/Resource_multistage_data.csv', multi)
        write(dst/'resources/policy_assignments/Resource_capacity_reserve_margin.csv', deratings)
        write(dst/'metadata/resource_mapping.csv', mappings)
        write(dst/'system/Generators_variability.csv', profile)
        nm = read(dst/'metadata/network_mapping.csv')
        net = read(dst/'system/Network.csv')
        apply_transmission_limits(net, nm)
        for n in net:
            n['DerateCapRes_1'] = 0
            n['CapRes_Excl_1'] = 0
        write(dst/'system/Network.csv', net)
        write(dst/'system/Operational_reserves.csv', [dict(Reg_Req_Percent_Demand=0, Reg_Req_Percent_VRE=0,
             Rsv_Req_Percent_Demand=reserve_fraction, Rsv_Req_Percent_VRE=0,
             Unmet_Rsv_Penalty_Dollar_per_MW=2600000/FX, Dynamic_Contingency=0, Static_Contingency_MW=0)])
        write(dst/'policies/Capacity_reserve_margin.csv', [dict(Network_zones=f'z{b}',
              CapRes_1=number(policy[year], 'Planning_Reserve_Margin') if year>=2026 else 0) for b in range(1,194)])
        print(f'Prepared native stage {stage}: {year}, {len(mappings)} resources', flush=True)

    source_dir=CASE/'metadata/source_candidates'
    source_columns = {
        'thermal_candidates': {'bus_id':'Bus', 'fuel_cost_krw_per_gcal':'Fuel_Cost'},
        'RE_candidates': {'bus_id':'Bus', 'gen_type':'Technology'},
        'sto_candidates': {'bus_id':'Bus'},
        'Retrofit_candidates': {'bus_id':'Bus', 'gen_id':'Gen_ID'},
        'tx_candidates': {'fbus':'FromBus', 'tbus':'ToBus', 'length_km':'Length_km',
                          'r_pu':'r', 'x_pu':'x', 'b_pu':'b'},
    }
    for name in ('thermal_candidates','RE_candidates','sto_candidates','Retrofit_candidates','tx_candidates'):
        columns = source_columns[name]
        write(source_dir/(name+'.csv'),[{columns.get(k,k):v for k,v in row.items()}
            for row in read(EXP/'candidates'/CANDIDATE_FILES[name])])
    settings = CASE/'settings'
    settings.mkdir(exist_ok=True)
    (settings/'genx_settings.yml').write_text('''Solver: Gurobi
NetworkExpansion: 0
DC_OPF: 0
Trans_Loss_Segments: 0
OperationalReserves: 1
EnergyShareRequirement: 0
CapacityReserveMargin: 0
CO2Cap: 1
MinCapReq: 0
MaxCapReq: 0
ParameterScale: 1
UCommit: 2
TimeDomainReduction: 0
MultiStage: 1
StorageVirtualDischarge: 0
VirtualChargeDischargeCost: 0
WriteShadowPrices: 0
WriteOutputs: full
OverwriteResults: 1
EnableJuMPDirectModel: false
EnableJuMPStringNames: false
''')
    (settings/'multi_stage_settings.yml').write_text(f'''NumStages: {len(YEARS)}
StageLengths: {LENGTHS}
WACC: {RATE}
ConvergenceTolerance: 1.0e-7
Myopic: 0
WriteIntermittentOutputs: 0
''')
    (settings/'gurobi_settings.yml').write_text('''Threads: 4
Method: -1
PreDual: -1
Crossover: 1
Feasib_Tol: 1.0e-8
Optimal_Tol: 1.0e-8
BarConvTol: 1.0e-9
NumericFocus: 1
SoftMemLimit: 170
TimeLimit: 7200
''')
    (CASE/'Run.jl').unlink(missing_ok=True)
    print('Native case:', CASE)


def constrained_medoids(distances, forced, net, starts, seed=504980811):
    from scipy.optimize import minimize
    rng = np.random.default_rng(seed)
    n = len(distances)
    pool = np.setdiff1d(np.arange(n), forced)
    best = None
    for attempt in range(starts):
        medoids = np.r_[forced, rng.choice(pool, 8-len(forced), replace=False)]
        previous = None
        for iteration in range(1000):
            labels = np.argmin(distances[:, medoids], axis=1)
            labels[medoids] = np.arange(8)
            if previous is not None and np.array_equal(labels, previous):
                break
            previous = labels.copy()
            for cluster in range(len(forced), 8):
                members = np.where(labels == cluster)[0]
                medoids[cluster] = members[np.argmin(distances[np.ix_(members, members)].sum(axis=1))]
        else:
            raise RuntimeError('K-medoids failed to converge')
        score = float(distances[np.arange(n), medoids[labels]].sum())
        if best is None or score < best[0]:
            best = score, medoids.copy(), labels.copy()
    score, medoids, labels = best
    counts = np.bincount(labels, minlength=8).astype(float)
    daily = net.sum(axis=1)/1000
    scale = max(abs(daily.sum()), 1.)
    A = np.vstack([counts/n, counts*daily[medoids]/scale])
    target = np.array([1., daily.sum()/scale])
    fit = minimize(lambda x: np.square(x-1).sum(), np.ones(8), jac=lambda x: 2*(x-1),
        method='SLSQP', bounds=list(zip(1/counts, n/counts)),
        constraints=[dict(type='eq', fun=lambda x: A@x-target, jac=lambda x: A)],
        options=dict(ftol=1e-12, maxiter=2000))
    assert fit.success, fit.message
    weights = counts*fit.x
    assert abs(weights.sum()-n) < 1e-6
    assert np.isclose(weights@daily[medoids], daily.sum(), rtol=1e-8, atol=1e-6)
    return medoids, counts, weights, score


def select_representatives(args):
    import pandas as pd
    from scipy.spatial.distance import cdist
    reps, summary = [], []
    index = pd.MultiIndex.from_product([range(1, 25), range(1, 194)], names=['hour', 'bus_id'])
    for year in map(int, args.years.split(',')):
        directory = RELEASE/f'kpg193_v2_0_{year}'
        n = 365 + calendar.isleap(year)
        caps = {}
        for tech in ('solar', 'wind'):
            table = pd.read_csv(directory/f'renewables_capacity/{tech}_generators.csv').sort_values('bus_id')
            assert list(table.bus_id) == list(range(1, 194))
            caps[tech] = table['pmax_mw'].to_numpy(float)
            assert np.isfinite(caps[tech]).all() and (caps[tech] >= 0).all() and caps[tech].sum() > 0
        load, solar, wind = [], [], []
        for day in range(1, n+1):
            arrays = []
            for kind, stem, columns in [('demand', 'demand', ['demandP']),
                    ('renewables', 'renewables', ['pv_profile_ratio', 'wind_profile_ratio'])]:
                table = pd.read_csv(directory/f'profile/{kind}/{stem}_{day}.csv')
                assert len(table) == len(index) and not table.duplicated(['hour', 'bus_id']).any()
                values = table.set_index(['hour', 'bus_id']).reindex(index)[columns].to_numpy(float)
                assert np.isfinite(values).all() and (values >= 0).all()
                arrays.append(values.reshape(24, 193, len(columns)))
            load.append(arrays[0][:, :, 0].sum(axis=1))
            solar.append(arrays[1][:, :, 0]@caps['solar'])
            wind.append(arrays[1][:, :, 1]@caps['wind'])
        load, solar, wind = map(np.asarray, (load, solar, wind))
        net = load-solar-wind
        peak = int(np.argmax(net.max(axis=1)))
        down = int(np.argmax((-np.diff(net, axis=1)).max(axis=1)))
        forced = list(dict.fromkeys([peak, down]))
        arrays = [load, wind/caps['wind'].sum(), solar/caps['solar'].sum()]
        assert all(a.std() > 0 for a in arrays)
        features = np.concatenate([(a-a.mean())/a.std() for a in arrays], axis=1)
        distance = cdist(features, features, metric='sqeuclidean')/72
        medoids, counts, weights, score = constrained_medoids(distance, forced, net, args.rep_starts)
        for i, day in enumerate(medoids):
            reason = 'max_net_load' if day == peak else 'max_ramp_down' if day == down else 'kmedoid'
            reps.append(dict(year=year, scenario=i+1,
                date=str(dt.date(year, 1, 1)+dt.timedelta(days=int(day))), source_day=int(day)+1,
                weight=weights[i], cluster_days=int(counts[i]), reason=reason))
        summary.append(dict(year=year, calendar_days=n, starts=args.rep_starts, seed=504980811,
            max_net_day=peak+1, max_down_ramp_day=down+1, distance=score,
            annual_net_GWh=net.sum()/1000, weighted_net_GWh=weights@net[medoids].sum(axis=1)/1000,
            annual_peak_MW=load.max(), forecast_solar_MW=caps['solar'].sum(), forecast_wind_MW=caps['wind'].sum()))
        print('Selected representative days:', year, flush=True)
    write_csv(args.representative_results/'representative_days.csv', reps)
    write_csv(args.representative_results/'representative_summary.csv', summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-dir',type=Path,help='New case directory; default: GenX_basecase_<timestamp>')
    parser.add_argument('--years',default=','.join(map(str,range(2024,2039))))
    parser.add_argument('--rep-starts',type=int,default=100,help='Deterministic K-medoids starts')
    parser.add_argument('--krw-per-usd',type=float,default=1300.)
    parser.add_argument('--wacc',type=float,default=.06)
    args=parser.parse_args()
    years = list(map(int, args.years.split(',')))
    assert years == sorted(set(years)) and years[0] == 2024 and set(years) <= set(range(2024, 2039))
    assert args.rep_starts > 0 and args.krw_per_usd > 0 and args.wacc >= 0
    if args.case_dir is None:
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        args.case_dir = Path(__file__).parent/f'GenX_basecase_{stamp}'
    args.case_dir = args.case_dir.resolve()
    if args.case_dir.exists() and any(args.case_dir.iterdir()):
        parser.error(f'{args.case_dir} is not empty; choose a new --case-dir')
    args.case_dir.mkdir(parents=True, exist_ok=True)
    args.representative_results = args.case_dir/'metadata'
    print('New case:', args.case_dir, flush=True)
    select_representatives(args)
    with tempfile.TemporaryDirectory(prefix='kpg_genx_') as directory:
        build_case(args,Path(directory))

if __name__=='__main__':
    main()
