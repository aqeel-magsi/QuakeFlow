#%%
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import tqdm
import os

# %%
'''
HypoDD can be downloaded from https://www.ldeo.columbia.edu/~felixw/hypoDD.html
Helpful compiling flags: FFLAGS = -O -I${INCLDIR} -mcmodel=large
'''
os.system("wget -O HYPODD_1.3.tar.gz http://www.ldeo.columbia.edu/~felixw/HYPODD/HYPODD_1.3.tar.gz")
os.system("tar -xf HYPODD_1.3.tar.gz")
os.system("ln -s $(which gfortran) f77")
os.system("ln -s $(which gfortran) g77")
os.environ['PATH'] += os.pathsep + os.getcwd()
os.system("make -C HYPODD/src")
PH2DT_CMD = "HYPODD/src/ph2dt/ph2dt ph2dt.inp"
HYPODD_CMD = "HYPODD/src/hypoDD/hypoDD hypoDD.inp"

# %%
''' 
The two test files can be downloaded using commands:
curl -O -J -L https://osf.io/aw53b/download
curl -O -J -L https://osf.io/y879e/download
curl -O -J -L https://osf.io/km97w/download
Details explained in Zhu et al. (2021) (https://arxiv.org/abs/2109.09008)
'''
# os.system("curl -O -J -L https://osf.io/aw53b/download")
# os.system("curl -O -J -L https://osf.io/y879e/download")
# os.system("curl -O -J -L https://osf.io/km97w/download")
os.system("python convert_stations.py")
picks = pd.read_csv('gamma_picks.csv', sep="\t")
events = pd.read_csv('gamma_catalog.csv', sep="\t")


# %%
if "file_index" in events.columns:
    events["match_id"] = events.apply(lambda x: f'{x["event_idx"]}_{x["file_index"]}', axis=1)
    picks["match_id"] = picks.apply(lambda x: f'{x["event_idx"]}_{x["file_index"]}', axis=1)
elif "file_idx" in events.columns:
    events["match_id"] = events.apply(lambda x: f'{x["event_idx"]}_{x["file_idx"]}', axis=1)
    picks["match_id"] = picks.apply(lambda x: f'{x["event_idx"]}_{x["file_idx"]}', axis=1)
else:
    events["match_id"] = events["event_idx"]
    picks["match_id"] = picks["event_idx"]
events.sort_values(by="time", inplace=True, ignore_index=True)

# %%
# MAXEVENT = len(events)
MAXEVENT = 1e4 ## segment by time
MAXEVENT = len(events) // ((len(events) - 1) // MAXEVENT + 1) + 1

# %% run hypoDD
def run_hypoDD(i, MAXEVENT):
    os.system(PH2DT_CMD)
    os.system(HYPODD_CMD)
    os.system(f"cp hypoDD.reloc hypoDD_{int(i//MAXEVENT):02d}.reloc")
    os.system(f"cp dt.ct dt_{int(i//MAXEVENT):02d}.ct")
    os.system(f"cp event.dat event_{int(i//MAXEVENT):02d}.dat")
    os.system(f"cp event.sel event_{int(i//MAXEVENT):02d}.sel")
    return f"hypoDD_{int(i//MAXEVENT):02d}.reloc"


# %% convert format
out_file = open("hypoDD.pha", "w")
hypoDD_catalogs = []

picks_by_event = picks.groupby("match_id").groups
for i in tqdm(range(len(events))):
    if i % MAXEVENT == MAXEVENT - 1:
        out_file.close()
        catalog = run_hypoDD(i, MAXEVENT)
        hypoDD_catalogs.append(catalog)
        out_file = open("hypoDD.pha", "w")

    event = events.iloc[i]
    event_time = datetime.strptime(event["time"], "%Y-%m-%dT%H:%M:%S.%f")
    lat = event["latitude"]
    lng = event["longitude"]
    dep = event["depth(m)"] / 1e3
    mag = event["magnitude"]
    EH = 0
    EZ = 0
    RMS = float(event["covariance"].split(",")[0])
    if RMS > 10:
        RMS = 0
    year, month, day, hour, min, sec = (
        event_time.year,
        event_time.month,
        event_time.day,
        event_time.hour,
        event_time.minute,
        float(event_time.strftime("%S.%f")),
    )
    event_line = f"# {year:4d} {month:2d} {day:2d} {hour:2d} {min:2d} {sec:5.2f}  {lat:7.4f} {lng:9.4f}   {dep:5.2f} {mag:5.2f} {EH:5.2f} {EZ:5.2f} {RMS:5.2f} {i+1:9d}\n"
    out_file.write(event_line)

    picks_idx = picks_by_event[event["match_id"]]
    for j in picks_idx:
        pick = picks.iloc[j]
        network_code, station_code, comp_code, channel_code = pick['id'].split('.')
        phase_type = pick['type'].upper()
        phase_weight = pick['prob']
        pick_time = (datetime.strptime(pick["timestamp"], "%Y-%m-%dT%H:%M:%S.%f") - event_time).total_seconds()
        # if pick_time <= 0:
        #     continue
        pick_line = f"{station_code:<5s}    {pick_time:8.3f}   {phase_weight:5.4f}   {phase_type}\n"
        out_file.write(pick_line)


out_file.close()
catalog = run_hypoDD(i, MAXEVENT)
hypoDD_catalogs.append(catalog)

# %% concatenate segmented catalogs
print(f"cat {' '.join(hypoDD_catalogs)} > hypoDD_catalog.txt")
os.system(f"cat {' '.join(hypoDD_catalogs)} > hypoDD_catalog.txt")