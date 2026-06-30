#!/usr/bin/env python3
import ctypes, os, random, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
SO_PATH = "/home/xephyr/astro/src/astro_calc/libastro-calc.so"
lib = ctypes.CDLL(SO_PATH)
BODIES = [(0, "10", "Sun"), (1, "301", "Moon"), (2, "199", "Mercury"), (3, "299", "Venus"), (4, "499", "Mars"), (5, "599", "Jupiter"), (6, "699", "Saturn")]
lib.ac_init.argtypes = [ctypes.c_char_p]; lib.ac_init.restype = ctypes.c_int
lib.ac_calc_bodies.argtypes = [ctypes.c_double, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_void_p]
lib.ac_calc_bodies.restype = ctypes.c_int
lib.ac_date_to_jd.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_double]
lib.ac_date_to_jd.restype = ctypes.c_double
EPHE_PATH = b"/home/xephyr/dev/astrolog/ast78src/ephem/"
lib.ac_init(EPHE_PATH)
class AcBody(ctypes.Structure):
    _fields_ = [("body_id", ctypes.c_int),("name", ctypes.c_char*32),("longitude", ctypes.c_double),("latitude", ctypes.c_double),("distance", ctypes.c_double),("speed", ctypes.c_double),("retrograde", ctypes.c_int),("sign", ctypes.c_int),("sign_degree", ctypes.c_double),("house", ctypes.c_int)]
ARCSEC_LIMIT = 1.0; DEGREE_LIMIT = ARCSEC_LIMIT/3600.0
random.seed(42)
dates=[]
for _ in range(10):
    dates.append((random.randint(1900,2099), random.randint(1,12), random.randint(1,28), random.randint(0,23), random.randint(0,59), random.randint(0,59)))
BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
def query_jpl(jpl_cmd, year, month, day, hour, minute, second):
    dt = datetime(year, month, day, hour, minute, second)
    start_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    stop_str = (dt + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    params = {"format":"text","COMMAND":f"'{jpl_cmd}'","OBJ_DATA":"'NO'","MAKE_EPHEM":"'YES'","EPHEM_TYPE":"'OBSERVER'","CENTER":"'500@399'","START_TIME":f"'{start_str}'","STOP_TIME":f"'{stop_str}'","STEP_SIZE":"'1m'","QUANTITIES":"'31'"}
    qs = "&".join(f"{k}={urllib.parse.quote(v, safe='')}" for k,v in params.items())
    url = f"{BASE_URL}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, f"HTTP error: {e}"
    soe = data.find("$$SOE"); eoe = data.find("$$EOE")
    if soe==-1 or eoe==-1: return None, "No ephemeris data block"
    for line in data[soe:eoe].splitlines():
        line=line.strip()
        if not line or line.startswith("$$"): continue
        parts=line.split()
        if len(parts)>=3:
            try: return float(parts[-2]), None
            except ValueError: continue
    return None, "Could not parse numeric longitude"
print("="*70); print("JPL HORIZONS Validation Gate"); print("="*70)
print(f"Testing {len(dates)} random dates (1900-2100)")
print(f"Bodies: {', '.join(b[2] for b in BODIES)}")
print(f"PASS threshold: < {ARCSEC_LIMIT} arc-sec ({DEGREE_LIMIT:.6f} degrees)")
print()
all_pass=True; results=[]
for idx, (year,month,day,hour,minute,second) in enumerate(dates,1):
    jd_ut = lib.ac_date_to_jd(year, month, day, hour, minute, second, 0.0)
    body_ids_arr = (ctypes.c_int*len(BODIES))(*[b[0] for b in BODIES])
    out_bodies = (AcBody*len(BODIES))()
    lib.ac_calc_bodies(jd_ut, body_ids_arr, len(BODIES), out_bodies)
    for b_idx, (our_id, jpl_cmd, name) in enumerate(BODIES):
        se_lon = out_bodies[b_idx].longitude
        jpl_lon, err = query_jpl(jpl_cmd, year, month, day, hour, minute, second)
        if jpl_lon is None:
            print(f"Date {idx}: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d} | {name}: JPL ERROR: {err}")
            all_pass=False; results.append((idx,name,se_lon,None,None,False)); continue
        diff = abs(se_lon - jpl_lon)
        while diff > 180.0: diff = 360.0 - diff
        diff_arcsec = diff*3600.0; passed = diff < DEGREE_LIMIT
        if not passed: all_pass=False
        results.append((idx,name,se_lon,jpl_lon,diff_arcsec,passed))
        status = "PASS" if passed else "FAIL"
        print(f"Date {idx}: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d} | {name:8s} SE={se_lon:10.6f} JPL={jpl_lon:10.6f} diff={diff_arcsec:8.4f}arcsec [{status}]")
        time.sleep(0.3)
print(); print("="*70); print("Summary"); print("="*70)
passed_count = sum(1 for r in results if r[5]); total_count=len(results)
print(f"Passed: {passed_count}/{total_count}")
print("OVERALL: PASS" if all_pass else "OVERALL: FAIL")
