#!/usr/bin/env python3

from pathlib import Path
import argparse, calendar, math, os, re, shutil
import numpy as np
import pandas as pd
from scipy.io import loadmat, savemat
HERE=Path(__file__).resolve().parent
GENX=HERE.parent
RELEASE=Path(__file__).resolve().parents[4]
EXP=RELEASE/'alternative_pathways'
INITIAL=RELEASE/'kpg193_v2_0_2024'
BPESD11=RELEASE
# Capacity tolerance in MW (10 W).
EPS=1e-5

def csv(path):
    return pd.read_csv(path, encoding='utf-8-sig')

def matrix(text, name):
    m = re.search(r'mpc\.' + name + r'\s*=\s*\[(.*?)\];', text, re.S)
    if m is None:
        return np.zeros((0, 17 if name == 'dcline' else 0))
    rows = []
    for line in m[1].splitlines():
        body = line.split('%')[0].replace(';', ' ').strip()
        if body:
            rows.append([float(x) for x in body.split()])
    return np.array(rows, dtype=float)

def read_case(directory):
    path = next((directory/'network/m').glob('*.m'))
    text = path.read_text()
    return {k: matrix(text, k) for k in ('bus','branch','dcline','gen','gencost','genthermal')}

def scaled_cost(a, b, c, old, new):
    return a*old/new, b, c*new/old

def make_generator(resource, bus, tech, cap, pmin, ru, rd, ut, dt, startup,
                   a, b, c, co2, group, source_id=0, initial_on=0, initial_p=0,
                   initial_duration=-48, su=None, sd=None):
    return dict(resource=resource,bus=int(bus),technology=tech,capacity_MW=float(cap),
        pmin_MW=float(pmin),ramp_up_MW=float(ru),ramp_down_MW=float(rd),
        min_up_h=int(math.ceil(ut)),min_down_h=int(math.ceil(dt)),startup_KRW=float(startup),
        cost_a_KRW=float(a),cost_b_KRW=float(b),cost_c_KRW=float(c),
        co2_t_per_MWh=float(co2),commitment_group=group,source_gen_id=int(source_id),
        initial_on=int(initial_on),initial_p_MW=float(initial_p),initial_duration_h=int(initial_duration),
        startup_limit_MW=float(cap if su is None else su),shutdown_limit_MW=float(cap if sd is None else sd))



def frame(path):
    return pd.read_csv(path)


def save_csv(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format='%.12g')


def write_network(folder, mpc, types):
    name = folder.name
    for ext in ('m', 'mat'):
        (folder / 'network' / ext).mkdir(parents=True, exist_ok=True)
    savemat(folder / 'network/mat' / (name + '.mat'), {'mpc': mpc}, do_compression=True)
    with (folder / 'network/m' / (name + '.m')).open('w') as f:
        f.write(f"function mpc = {name}\n% KPG Run input. Planning-case transfer limits; costs in 1000 KRW.\nmpc.version = '2';\nmpc.baseMVA = 100;\n")
        for key, array in mpc.items():
            if key in ('version', 'baseMVA'):
                continue
            f.write(f'mpc.{key} = [\n')
            for i, row in enumerate(np.atleast_2d(array)):
                suffix = ' % ' + types[i] if key == 'gen' else ''
                f.write(' '.join(f'{v:.15g}' for v in row) + ';' + suffix + '\n')
            f.write('];\n')
        f.write('end\n')
    restored = loadmat(folder / 'network/mat' / (name + '.mat'), simplify_cells=True)['mpc']
    text = (folder / 'network/m' / (name + '.m')).read_text()
    for key, array in mpc.items():
        if key not in ('version', 'baseMVA'):
            assert np.allclose(np.atleast_2d(restored[key]), array, atol=1e-8)
            assert np.allclose(matrix(text, key), array, atol=1e-8)


def result_fleet(results, inputs, year):
    d = inputs / 'inputs' / str(year)
    mapping = frame(d / 'metadata/resource_mapping.csv').set_index('Resource')
    stage = list(frame(inputs / 'metadata/years.csv').Year).index(year) + 1
    path = results / f'results_p{stage}' / 'capacity.csv'
    cap = frame(path)
    cap = cap[cap.Resource != 'Total'].set_index('Resource')
    assert set(cap.index) == set(mapping.index)
    tc = frame(inputs / 'metadata/source_candidates/thermal_candidates.csv').set_index('Resource')
    retro = frame(inputs / 'metadata/source_candidates/Retrofit_candidates.csv').set_index('Resource')
    uc = frame(d / 'metadata/thermal_source_parameters.csv').set_index('Resource')
    thermal = frame(d / 'resources/Thermal.csv').set_index('Resource')
    stores = frame(d / 'resources/Storage.csv').set_index('Resource')
    fuel = frame(d / 'system/Fuels_data.csv')
    base = read_case(INITIAL)
    fx=float(frame(inputs/'metadata/model_settings.csv').iloc[0].KRW_per_USD)
    gens, re, storage, hydro = [], [], [], []
    expected = {}
    for resource, c in cap.iterrows():
        info = mapping.loc[resource]
        K = max(0., float(c.EndCap))
        assert c.EndCap >= -1e-3
        assert int(c.Zone) == int(info.Bus)
        if K <= EPS:
            continue
        expected[resource] = K
        if info.Kind in ('existing_thermal', 'candidate_thermal', 'retrofit'):
            u, t = uc.loc[resource], thermal.loc[resource]
            linear = fx * (t.Heat_Rate_MMBTU_per_MWh * fuel.iloc[1][t.Fuel] + t.Var_OM_Cost_per_MWh)
            co2 = t.Heat_Rate_MMBTU_per_MWh * fuel.iloc[0][t.Fuel]
            if info.Kind == 'candidate_thermal':
                spec = tc.loc[info.Source_ID]
                n = max(1, math.ceil((K - 1e-4) / spec.Max_Cap_MW))
                assert n <= spec.Max_units
                unit, host = K / n, 0
                if spec.Heat_Basis == 'capacity_normalized':
                    coeff = spec.Fuel_Cost * np.array([spec.Heat_quad / unit, spec.Heat_lin, spec.Heat_coeff * unit])
                else:
                    coeff = np.array(scaled_cost(spec.Fuel_Cost * spec.Heat_quad,
                        spec.Fuel_Cost * spec.Heat_lin, spec.Fuel_Cost * spec.Heat_coeff, spec.Max_Cap_MW, unit))
                sur, sdr = spec.Startup_Ramp_Fraction, spec.Shutdown_Ramp_Fraction
            else:
                host = int(info.Source_ID) if info.Kind == 'existing_thermal' else int(retro.loc[info.Source_ID].Gen_ID)
                g, gt = base['gen'][host - 1], base['genthermal'][host - 1]
                n, unit = 1, K
                coeff = np.array(scaled_cost(*(base['gencost'][host-1, 4:7] * 1000), g[8], K))
                sur, sdr = gt[7] / g[8], gt[8] / g[8]
            full = coeff[0] * unit + coeff[1] + coeff[2] / unit
            coeff *= linear / full if full else 1.
            for j in range(n):
                rid = resource if n == 1 else f'{resource}__{j+1}'
                row = make_generator(rid, info.Bus, info.Technology, unit,
                    u.Source_Pmin_Fraction*unit, u.Source_Ramp_Up_Per_Hour*unit,
                    u.Source_Ramp_Down_Per_Hour*unit, u.UT_hours, u.DT_hours,
                    u.Source_Startup_KRW_per_MW*unit, *coeff, co2,
                    f'HOST_{host}' if host else rid, host, 0, 0., -48, sur*unit, sdr*unit)
                row.update(cem_resource=resource)
                gens.append(row)
        elif info.Kind in ('existing_re', 'candidate_re'):
            re.append(dict(resource=resource, bus=int(info.Bus), technology=info.Technology, capacity_MW=K))
        elif info.Kind == 'candidate_bess':
            s = stores.loc[resource]
            charge = K if int(s.Model) == 1 else float(c.EndChargeCap)
            storage.append(dict(resource=resource, technology='BESS',
                bus=int(info.Bus), power_MW=K, charge_MW=charge, energy_MWh=float(c.EndEnergyCap),
                eff_up=s.Eff_Up, eff_down=s.Eff_Down))
        elif info.Kind == 'profile_hydro':
            hydro.append(dict(resource=resource, group_id=int(info.Source_ID), bus=int(info.Bus), capacity_MW=K))
        else:
            raise ValueError(info.Kind)
    net=frame(d/'metadata/network_mapping.csv')
    network=frame(d/'system/Network.csv')
    annual=read_case(RELEASE/f'kpg193_v2_0_{year}')
    m={k:v.copy() for k,v in base.items()}
    m['bus']=annual['bus'].copy()
    branch=[];dc=[]
    for (_,r),(_,limit) in zip(net.iterrows(),network.iterrows()):
        cap=float(limit.Line_Max_Flow_MW)
        assert int(r.Source_Year)==year
        source_row=int(r.Source_Row)-1
        if r.Kind=='AC':
            row=annual['branch'][source_row,:13].copy()
            assert np.allclose(row[:5],[r.FromBus,r.ToBus,r.r_pu,r.x_pu,r.b_pu])
            row[5:8]=cap;branch.append(row)
        else:
            row=annual['dcline'][source_row].copy()
            assert np.allclose(row[:2],[r.FromBus,r.ToBus])
            row[9:11]=[-cap,cap];dc.append(row)
    m['branch']=np.array(branch).reshape(-1,13)
    m['dcline']=np.array(dc).reshape(-1,17)
    return m, pd.DataFrame(gens), pd.DataFrame(re,columns=['resource','bus','technology','capacity_MW']), pd.DataFrame(storage,columns=['resource','technology','bus','power_MW','charge_MW','energy_MWh','eff_up','eff_down']), pd.DataFrame(hydro,columns=['resource','group_id','bus','capacity_MW']), expected


def prepare_case(folder, year, fleet, initial_states, overwrite=False):
    m, gens, re, storage, hydro, expected = fleet
    allgens = gens.to_dict('records')
    thermal_count = len(allgens)
    storage_rows = []
    for s in storage.itertuples():
        assert abs(s.eff_down - 1.) < 1e-9, 'KPG storage reader supports charge losses only'
        assert s.energy_MWh > 0 and s.charge_MW > 0
        gid = len(allgens) + 1
        allgens.append(make_generator(s.resource, s.bus, s.technology, s.power_MW, 0.,
            s.power_MW, s.power_MW, 1, 1, 0, 0, 0, 0, 0, s.resource,
            initial_on=0, initial_p=0., initial_duration=-48, su=s.power_MW, sd=s.power_MW))
        storage_rows.append(dict(generator_id=gid, resource=s.resource, technology=s.technology,
            soc_min_mwh=0, soc_max_mwh=s.energy_MWh, soc_init_mwh=.5*s.energy_MWh,
            pump_eff=s.eff_up, pump_pmax_mw=s.charge_MW, pump_pmin_mw=0, terminal_equal=True))
    states = initial_states[initial_states.Year == year].set_index('Resource', verify_integrity=True)
    names = [g['resource'] for g in allgens]
    if set(states.index) != set(names):
        raise ValueError(f'{year}: saved UC states do not match this fleet; supply matching --initial-state CSV')
    for g in allgens:
        s = states.loc[g['resource']]
        if not np.allclose([s.Bus, s.Pmax_MW, s.Pmin_MW],
                [g['bus'], g['capacity_MW'], g['pmin_MW']], rtol=0, atol=1e-5):
            raise ValueError(f"{year} {g['resource']}: saved UC fleet parameters differ")
        duration, power = float(s.Inistate_h), float(s.Initial_P_MW)
        if not (np.isfinite([duration, power]).all() and duration != 0 and duration.is_integer()
                and s.Status in (0, 1) and int(s.Status) == int(duration > 0)):
            raise ValueError(f"{year} {g['resource']}: invalid saved UC state")
        if (duration > 0 and not g['pmin_MW']-1e-6 <= power <= g['capacity_MW']+1e-6
                or duration < 0 and abs(power) > 1e-6):
            raise ValueError(f"{year} {g['resource']}: saved initial output is outside its operating limits")
        g.update(initial_on=int(s.Status), initial_p_MW=power, initial_duration_h=int(duration))
    if folder.exists():
        if not overwrite:
            raise FileExistsError(f'{folder}: use --overwrite to replace this annual export')
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    gs, costs, gt, meta = [], [], [], []
    for i, g in enumerate(allgens, 1):
        k = g['capacity_MW']
        row = np.zeros(21)
        row[[0,3,4,5,6,7,8,9,17,18,19]] = [g['bus'], .5*k, -.5*k, 1, 100, 1, k,
            g['pmin_MW'], g['ramp_up_MW']/6, g['ramp_down_MW']/2, k/2]
        row[1] = g['initial_p_MW']
        gs.append(row)
        costs.append([2, g['startup_KRW']/1000, 0, 3, g['cost_a_KRW']/1000,
                      g['cost_b_KRW']/1000, g['cost_c_KRW']/1000])
        ut, dt = max(1, math.ceil(g['min_up_h'])), max(1, math.ceil(g['min_down_h']))
        gt.append([3, ut, dt, g['initial_duration_h'], g['initial_p_MW'], g['ramp_up_MW'], g['ramp_down_MW'],
            g['startup_limit_MW'], g['shutdown_limit_MW'], *([g['startup_KRW']/1000]*3),3,6,12])
        meta.append(dict(gen_id=i, bus_id=g['bus'], gen_type=g['technology'],
            plant_name_kor=g['resource'], unit_name=g['resource'], pmax_mw=k,
            resource=g.get('cem_resource',g['resource']), commitment_group=g['commitment_group'],
            original_gen_id=g.get('source_gen_id',0), co2_t_per_MWh=g['co2_t_per_MWh']))
    mpc = {k:np.atleast_2d(m[k]).copy() for k in ('bus','branch','dcline')}
    mpc['dclinecost'] = np.tile([2.,0.,0.,2.,0.,0.],(len(mpc['dcline']),1))
    mpc.update(version='2', baseMVA=100., gen=np.array(gs), gencost=np.array(costs), genthermal=np.array(gt))
    types = [g['technology'] for g in allgens]
    write_network(folder, mpc, types)
    save_csv(pd.DataFrame(meta),folder / f'network/metadata/generator_metadata/generator_metadata_{year}.csv')
    if storage_rows:
        save_csv(pd.DataFrame(storage_rows), folder / 'network/metadata/psh_metadata/storage_units.csv')
    busmeta = RELEASE/f'kpg193_v2_0_{year}/network/metadata/bus_metadata/bus_metadata_{year}.csv'
    save_csv(frame(busmeta),folder / f'network/metadata/bus_metadata/bus_metadata_{year}.csv')
    actual = gens.groupby('cem_resource').capacity_MW.sum().to_dict()
    for table, col in [(re,'capacity_MW'),(storage,'power_MW'),(hydro,'capacity_MW')]:
        for r in table.itertuples():
            actual[r.resource] = getattr(r,col)
    residual = max(abs(actual.get(k,0.)-v) for k,v in expected.items())
    assert residual < 1e-3, residual
    assert not (set(actual) - set(expected))
    ties=[]
    for _, group in pd.DataFrame(meta[:thermal_count]).groupby('commitment_group'):
        ids=list(group.gen_id)
        for g in ids[1:]:
            for h in range(1,25):
                for gi, c in [(ids[0],1),(g,-1)]:
                    ties.append(dict(constraint_id=f'host_{ids[0]}_{g}',hour=h,generator_id=gi,
                        variable='u',coefficient=c,sense='=',rhs=0,rhs_unit='dimensionless'))
    if ties:
        save_csv(pd.DataFrame(ties),folder / 'profile/constraints/linear_constraints.csv')
    capacities={}
    for tech, prefix in [('Solar','solar'),('Wind','wind'),('OffshoreWind','offshore')]:
        capacities[tech]=re[re.technology==tech].groupby('bus').capacity_MW.sum().reindex(range(1,194),fill_value=0).to_numpy()
    capacities['Hydro']=hydro.groupby('bus').capacity_MW.sum().reindex(range(1,194),fill_value=0).to_numpy()
    for prefix, values in [('solar',capacities['Solar']),('wind',capacities['Wind']+capacities['OffshoreWind']),('hydro',capacities['Hydro'])]:
        save_csv(pd.DataFrame({'bus_ID':range(1,194),'Pmax [MW]':values}), folder / f'renewables_capacity/{prefix}_generators_{year}.csv')
    return capacities


def generate_profiles(entries, days):
    for day in days:
        order=pd.MultiIndex.from_product([range(1,194),range(1,25)],names=['bus_id','hour'])
        demand_cache={}; weather_cache={}
        for e in entries:
            folder, year, capacities=e['folder'],e['year'],e['capacities']
            if day > (366 if calendar.isleap(year) else 365): continue
            weather_key=(year,day)
            if weather_key not in weather_cache:
                path=BPESD11/f'kpg193_v2_0_{year}/profile/renewables/renewables_{day}.csv'
                profile=frame(path).set_index(['bus_id','hour']).reindex(order)
                assert profile[['pv_profile_ratio','wind_profile_ratio','hydro_profile_ratio']].notna().all().all()
                weather_cache[weather_key]=profile
            base=offshore=weather_cache[weather_key]
            if year not in demand_cache:
                source=BPESD11 / f'kpg193_v2_0_{year}/profile/demand/demand_{day}.csv'
                dd=frame(source)
                assert len(dd)==193*24 and not dd.duplicated(['bus_id','hour']).any()
                assert np.isfinite(dd[['demandP','demandQ']]).all().all()
                demand_cache[year]=(source,dd)
            source,dd=demand_cache[year]
            target=folder / f'profile/demand/demand_{day}.csv'
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                shutil.copyfile(source,target)
            for directory,stem in [('network/metadata/psh_metadata','storage_units'),
                                   ('profile/constraints','linear_constraints')]:
                common=folder / directory / (stem+'.csv')
                daily=folder / directory / f'{stem}_{day}.csv'
                if common.exists() and not daily.exists():
                    os.link(common,daily)
            on,off=capacities['Wind'],capacities['OffshoreWind']
            active=np.repeat(off>EPS,24)
            op=offshore.offshore_profile_ratio.to_numpy(float)
            assert np.isfinite(op[active]).all(), (year,day,'missing installed offshore profile')
            op=np.nan_to_num(op,nan=0.)
            onw,offw=np.repeat(on,24),np.repeat(off,24)
            available=onw*base.wind_profile_ratio.to_numpy()+offw*op
            blended=np.divide(available,onw+offw,out=np.zeros(len(base)),where=onw+offw>EPS)
            residual=np.max(np.abs(blended*(onw+offw)-available))
            assert residual<1e-7
            data=base.reset_index()[['hour','bus_id','pv_profile_ratio','wind_profile_ratio','hydro_profile_ratio']].copy()
            data['wind_profile_ratio']=blended
            data['onshore_profile_ratio']=base.wind_profile_ratio.to_numpy()
            data['offshore_profile_ratio']=op
            save_csv(data,folder / f'profile/renewables/renewables_{day}.csv')
        if day==1 or day%30==0:
            print('Chronological profiles:',day,flush=True)




def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,default=GENX/'GenX_basecase')
    p.add_argument('--results',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--initial-state',type=Path,default=HERE/'uc_initial_state.csv')
    p.add_argument('--years',type=int,nargs='+')
    p.add_argument('--days',type=int,default=366)
    p.add_argument('--overwrite',action='store_true')
    args=p.parse_args(argv)
    assert 1<=args.days<=366
    results=(args.results or args.inputs/'results').resolve()
    out=(args.output or HERE).resolve()
    initial_states=frame(args.initial_state)
    out.mkdir(parents=True,exist_ok=True)
    entries=[]
    years=frame(args.inputs/'metadata/years.csv')
    for row in years.itertuples():
        if args.years and row.Year not in args.years: continue
        folder=out/f'kpg193_genx_base_{row.Year}'
        capacity=prepare_case(folder,int(row.Year),result_fleet(results,args.inputs,int(row.Year)),initial_states,args.overwrite)
        entries.append(dict(year=int(row.Year),folder=folder,capacities=capacity))
    assert entries,'No selected years exist in the solution'
    generate_profiles(entries,range(1,args.days+1))
    print('KPG export complete:',out,flush=True)

if __name__=='__main__':
    main()
