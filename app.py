# -*- coding: utf-8 -*-
"""
Smart Irrigation Network Design & Cost AI Agent  (v9 - Unified Hardened Engine)
Real map boundary + exclusions | FAO-56 Penman-Monteith | Hazen-Williams pipe sizing |
Hydraulic scheduling (RAW/depletion) | Sectors & valves | Currency + VAT | DXF deliverables.
Run:  streamlit run app.py
PRELIMINARY DESIGN TOOL - results must be verified by a licensed irrigation engineer before construction.
"""
import io, math, re, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests, streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Smart Irrigation AI", page_icon="💧", layout="wide")

try:
    import folium
    from folium.plugins import Draw, Geocoder
    from streamlit_folium import st_folium
    from shapely.geometry import Polygon, LineString
    from shapely.ops import unary_union
    from pyproj import Transformer
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError as _e:
    st.error("Missing library: %s. Install: pip install streamlit streamlit-folium folium shapely pyproj ezdxf "
             "deep-translator matplotlib pandas numpy requests" % _e)
    st.stop()
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

BRAND = "walid.sal.abd9911"
DISCLAIMER = ("⚠️ PRELIMINARY ENGINEERING TOOL - not for construction without a final topographic survey, "
              "pump curves and sign-off by a licensed irrigation engineer.")


def L(s):
    return s


# =====================================================================================
# 1. MULTI-LANGUAGE ENGINE
# =====================================================================================
LANGS = {"العربية (Arabic)": "ar", "English": "en", "Ελληνικά (Greek)": "el", "Français (French)": "fr",
         "Español (Spanish)": "es", "Deutsch (German)": "de", "Italiano (Italian)": "it", "Türkçe (Turkish)": "tr"}
RTL = {"ar", "fa", "ur", "iw"}
ALIAS = {"iw": "he"}


@st.cache_resource
def _tstore():
    return {"cache": {}, "blocked_until": 0.0}


def _batch(texts, lang):
    texts = list(texts)
    if lang == "en" or GoogleTranslator is None:
        return texts
    try:
        S = _tstore(); cache = S["cache"]
        todo = [t for t in dict.fromkeys(texts) if t.strip() and (lang, t) not in cache]
        if todo and time.time() >= S["blocked_until"]:
            def one(t):
                for code in (lang, ALIAS.get(lang)):
                    if not code:
                        continue
                    try:
                        r = GoogleTranslator(source="en", target=code).translate(t[:4900])
                        if r:
                            return t, r
                    except Exception:
                        pass
                return t, None
            with ThreadPoolExecutor(12) as ex:
                results = list(ex.map(one, todo))
            ok = sum(1 for _, r in results if r)
            for t, r in results:
                if r:
                    cache[(lang, t)] = r
            if len(todo) >= 5 and ok == 0:
                S["blocked_until"] = time.time() + 60
        return [_tstore()["cache"].get((lang, t), t) for t in texts]
    except Exception:
        return texts


try:
    _SRC = Path(__file__).read_text(encoding="utf-8")
except Exception:
    _SRC = ""
UI_ALL = tuple(dict.fromkeys(re.findall(r'\b[TL]\("([^"\n]+)"\)', _SRC)))

st.sidebar.markdown("### 🌐 Language / اللغة")
LANG = LANGS[st.sidebar.selectbox("language", list(LANGS), label_visibility="collapsed")]
if LANG in RTL:
    st.markdown("""<style>
    .stApp, .stMarkdown, label, .stRadio, .stSelectbox, .stNumberInput, .stAlert {direction: rtl; text-align: right;}
    .stApp iframe, [data-testid="stDataFrame"], [data-testid="stImage"], [data-testid="stMetric"] {direction: ltr;}
    </style>""", unsafe_allow_html=True)
with st.spinner("🌐 ..."):
    _UI = dict(zip(UI_ALL, _batch(UI_ALL, LANG)))

def T(s):
    return _UI.get(s) or _batch((s,), LANG)[0]


def tr_md(text):
    pat = re.compile(r'^(\s*(?:#+\s+|[-*]\s+|\d+\.\s+)?)(.*)$')
    ms = [pat.match(l) for l in text.split("\n")]
    out = _batch([m.group(2) for m in ms], LANG)
    return "\n".join(m.group(1) + o for m, o in zip(ms, out))


def tdf(df):
    df = df.copy()
    cells = {v for c in df.columns for v in df[c] if isinstance(v, str)}
    keys = sorted(cells | set(map(str, df.columns)))
    m = dict(zip(keys, _batch(keys, LANG)))
    for c in df.columns:
        df[c] = df[c].map(lambda v: m.get(v, v) if isinstance(v, str) else v)
    return df.rename(columns=lambda c: m.get(str(c), c))


# =====================================================================================
# 2. ENGINEERING DATA
# =====================================================================================
SOILS = {"sandy": L("Sandy"), "clay": L("Clayey"), "loam": L("Loamy"), "rocky": L("Rocky")}
INFIL = {"sandy": 30, "loam": 15, "clay": 6, "rocky": 10}                       # basic intake rate, mm/h
TAW = {"sandy": 100.0, "loam": 160.0, "clay": 200.0, "rocky": 130.0}           # total available water, mm/m
ZR = {"turf": 0.30, "shrub": 0.40, "tree": 1.00, "veg": 0.45, "orchard": 1.00, "field": 0.60}  # root depth, m
P_ALLOW = 0.50                                                                # readily-available depletion fraction
CLASSES = {"land": L("Landscape & Ornamentals"), "prod": L("Production Fields & Orchards")}
CROPS = {
    "land": {L("Lawn / turf grass"): (0.85, "turf", 0.4, 0.4),
             L("Ornamental shrubs & flowers"): (0.55, "shrub", 1.0, 0.5),
             L("Landscape trees & palms"): (0.60, "tree", 4.0, 1.0)},
    "prod": {L("Vegetables"): (1.05, "veg", 1.5, 0.3), L("Olive orchard"): (0.70, "orchard", 6.0, 1.0),
             L("Citrus orchard"): (0.70, "orchard", 6.0, 1.0), L("Date palms"): (0.95, "orchard", 8.0, 1.0),
             L("Vineyard"): (0.70, "orchard", 3.0, 1.0),
             L("Field crops (wheat, maize, alfalfa)"): (1.05, "field", 1.5, 0.3)}}
WATER = {"well": L("Existing well"), "surface": L("Surface water / canal"),
         "scratch": L("Design water source from scratch")}
POWER = {"grid": L("Grid electricity"), "diesel": L("Diesel generator"), "solar": L("Solar energy system")}
DRIPQ = {"turf": 1.6, "shrub": 2.0, "tree": 4.0, "veg": 1.6, "orchard": 4.0, "field": 1.6}  # emitter flow, L/h
SYS = {
    "popup": dict(name="Pop-up sprinklers", Ea=.75, q=900, Hop=30, sp=(10, 10), pe=7.0,
                  look="Heads hide below the lawn when off; even, soft coverage; best for turf, but wind drift lowers efficiency."),
    "sprinkler": dict(name="Solid-set sprinklers", Ea=.72, q=1500, Hop=40, sp=(15, 15), pe=11.0,
                      look="Risers are visible above the crop; cools the crop; sensitive to wind."),
    "drip": dict(name="Surface drip irrigation", Ea=.90, Hop=10, pe=0.10,
                 look="Almost invisible and quiet; no wind drift; water goes only to the roots."),
    "sdi": dict(name="Subsurface drip irrigation (SDI)", Ea=.93, Hop=12, pe=0.14, inst=1.25,
                look="Fully hidden underground: clean surface, minimum evaporation, protected from damage."),
    "pivot": dict(name="Center pivot", Ea=.85, Hop=35, pe=0,
                  look="Automated, very low labour; best for large, open and gently sloping fields.")}
PIPE_PRICE = {16: .35, 20: .5, 25: .8, 32: 1.2, 40: 1.8, 50: 2.6, 63: 4, 75: 5.5, 90: 7.5, 110: 11, 125: 14,
              140: 17, 160: 22, 200: 34, 250: 52, 315: 80}                        # USD/m, PE/PVC PN10
LAT_DRIP, LAT_SPR = [16, 20, 25, 32, 40, 50], [32, 40, 50, 63, 75, 90]
MAINS = [32, 40, 50, 63, 75, 90, 110, 125, 140, 160, 200, 250, 315]
MOTORS = [.37, .55, .75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200]
DXF_EMITTER_LIMIT = 40000
MAX_LATERALS = 20000
DRIP_ID = {16: 13.6, 20: 16.4, 25: 20.4, 32: 26.0}                            # ACTUAL dripline ID, mm
PE_IDF = 0.886                                                                  # ID = 0.886 x OD (PE100 PN10)
HF_SAFETY = 1.20
EFF_RAIN = 0.70
CAPEX_LO, CAPEX_HI = 0.85, 1.35
CURRENCIES = {"USD": (1.0, 0.0), "EUR": (0.92, 24.0), "EGP": (48.0, 14.0),
              "SAR": (3.75, 15.0), "AED": (3.67, 5.0)}
V_MAX_MAIN, V_MAX_LAT = 1.5, 2.0


# =====================================================================================
# 3. CLIMATE: FAO-56 PENMAN-MONTEITH, TERRAIN (cached)
# =====================================================================================
def fao56_et0(tmax, tmin, rs, u10, lat, elev, doy):
    """Daily reference ET0 (mm/day), FAO-56 eq. 6. Vectorised."""
    tmean = (tmax + tmin) / 2
    u2 = u10 * 4.87 / np.log(67.8 * 10 - 5.42)
    Pk = 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26
    gamma = 0.000665 * Pk
    es = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))
    e_s, e_a = (es(tmax) + es(tmin)) / 2, es(tmin)
    delta = 4098 * es(tmean) / (tmean + 237.3) ** 2
    phi = math.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    Ra = (24 * 60 / np.pi) * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
    Rso = np.maximum((0.75 + 2e-5 * elev) * Ra, 0.1)
    Rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * np.sqrt(e_a)) \
        * (1.35 * np.clip(rs / Rso, 0.3, 1.0) - 0.35)
    Rn = 0.77 * rs - Rnl
    et0 = (0.408 * delta * Rn + gamma * 900 / (tmean + 273) * u2 * (e_s - e_a)) / (delta + gamma * (1 + 0.34 * u2))
    return np.maximum(et0, 0), u2


@st.cache_data(show_spinner=False, ttl=86400)
def get_climate(lat, lon):
    base = "temperature_2m_max,temperature_2m_min,shortwave_radiation_sum,wind_speed_10m_max,precipitation_sum"
    end = dt.date.today() - dt.timedelta(days=7)
    for daily in (base + ",et0_fao_evapotranspiration", base):
        try:
            r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=25, params=dict(
                latitude=lat, longitude=lon, start_date=str(end - dt.timedelta(days=364)), end_date=str(end),
                daily=daily, wind_speed_unit="ms", timezone="auto"))
            r.raise_for_status()
            js = r.json()
            d = pd.DataFrame(js["daily"]).dropna(subset=base.split(","))
            if d.empty:
                continue
            elev = float(js.get("elevation", 0) or 0)
            t = pd.to_datetime(d["time"])
            u10 = 0.55 * d["wind_speed_10m_max"].values
            et0, u2 = fao56_et0(d["temperature_2m_max"].values, d["temperature_2m_min"].values,
                                d["shortwave_radiation_sum"].values, u10, lat, elev, t.dt.dayofyear.values)
            monthly = pd.Series(et0).groupby(t.dt.month.values).mean().reindex(range(1, 13))
            et0_m = list(monthly.fillna(float(monthly.mean())))
            rain_m = list(d["precipitation_sum"].groupby(t.dt.month.values).sum().reindex(range(1, 13), fill_value=0.0))
            xc = None
            if "et0_fao_evapotranspiration" in d:
                xc = float(d["et0_fao_evapotranspiration"].groupby(t.dt.month.values).mean().max())
            return dict(ok=True, et0_peak=float(monthly.max()), peak_month=int(monthly.idxmax()),
                        et0_ann=float(et0.sum()), rain=float(d["precipitation_sum"].sum()),
                        wind2=float(np.mean(u2)), elev=elev, xcheck=xc, et0_m=et0_m, rain_m=rain_m)
        except Exception:
            continue
    pk = max(3.0, 8 - 0.06 * abs(lat))
    return dict(ok=False, et0_peak=pk, peak_month=7, et0_ann=pk * 0.6 * 365, rain=300.0, wind2=2.0,
                elev=0.0, xcheck=None, et0_m=None, rain_m=None)


@st.cache_data(show_spinner=False, ttl=86400)
def get_relief(lat, lon, span):
    try:
        dl, dn = span / 2 / 110540, span / 2 / (111320 * math.cos(math.radians(lat)))
        la, lo = [lat, lat + dl, lat - dl, lat, lat], [lon, lon, lon, lon + dn, lon - dn]
        r = requests.get("https://api.open-meteo.com/v1/elevation", timeout=15,
                         params=dict(latitude=",".join(map(str, la)), longitude=",".join(map(str, lo))))
        el = r.json()["elevation"]
        rel = max(el) - min(el)
        return float(rel), float(min(100.0, rel / span * 100))
    except Exception:
        return 0.02 * span, 2.0


def utm_of(lon, lat):
    ep = (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1
    return Transformer.from_crs(4326, ep, always_xy=True), "EPSG:%d" % ep


# =====================================================================================
# 4. HYDRAULIC ENGINE
# =====================================================================================
def hw(Q, D, Lm, C=140, id_mm=None):
    """Hazen-Williams head loss (m). Q in m3/h, D nominal mm, L in m."""
    if Q <= 0 or Lm <= 0:
        return 0.0
    d = (id_mm if id_mm is not None else 0.9 * D) / 1000
    return 10.67 * Lm * (Q / 3600) ** 1.852 / (C ** 1.852 * d ** 4.87)


def vel(Q, D):
    return (Q / 3600) / (math.pi / 4 * (0.9 * D / 1000) ** 2)


def pick(Q, fn, opts, vmax, hmax):
    for D in opts:
        if vel(Q, D) <= vmax and fn(D) <= hmax:
            return D
    return opts[-1]


def chr_F(N):
    return 1 / 2.852 + 1 / (2 * N) + math.sqrt(0.852) / (6 * N * N)


def n_em(Ls, em, sk):
    return max(1, len(np.arange(0, Ls + 1e-6, em) if sk in ("popup", "sprinkler") else np.arange(em / 2, Ls, em)))


def make_layout(P, sk, row, em):
    net = P["net"]
    minx, miny, maxx, maxy = net.bounds
    cx = net.centroid.x
    src = min(P["boundary"].exterior.coords, key=lambda p: (p[0] - minx) + (p[1] - miny))[:2]
    lay = dict(src=src, laterals=[], pivots=[], mains=[], sub=None, row=row, em=em, cx=cx, n=1, zone_y=[])
    if sk == "pivot":
        n = max(1, math.ceil(P["A_net"] / 400000))
        R = math.sqrt(P["A_net"] / n / math.pi)
        for i in range(n):
            c = (minx + (maxx - minx) * (i + .5) / n, net.centroid.y)
            lay["pivots"].append((c[0], c[1], R))
            lay["mains"].append(LineString([src, c]))
        return lay
    ys = np.arange(miny + row / 2, maxy, row)
    if len(ys) == 0:
        ys = [net.centroid.y]
    if len(ys) > MAX_LATERALS:
        raise ValueError("Too many laterals (%d): area too large for the selected spacing." % len(ys))
    for y in ys:
        g = net.intersection(LineString([(minx - 1, y), (maxx + 1, y)]))
        for s in ([g] if g.geom_type == "LineString" else list(getattr(g, "geoms", []))):
            if s.geom_type == "LineString" and s.length >= 1:
                lay["laterals"].append(dict(line=s, y=float(y), zone=0))
    if not lay["laterals"]:
        raise ValueError("Net area is too small / narrow for the selected spacing.")
    lay["sub"] = LineString([(cx, miny), (cx, maxy)])
    lay["mains"] = [LineString([src, (cx, miny)])]
    return lay


def design(P, sk):
    """Full hydraulic + cost design for ONE system type. Returns result dict."""
    sy, cat, A, W = SYS[sk], P["cat"], P["A_net"], []
    Ea = sy["Ea"]
    if sk in ("popup", "sprinkler", "pivot"):
        if P["wind2"] > 3.0:
            Ea -= 0.07
            W.append("High mean wind (%.1f m/s at 2 m): sprinkler efficiency reduced by 7 %%." % P["wind2"])
        if P["soil"] == "sandy":
            Ea -= 0.03
    gross = P["etc"] / Ea
    if sk in ("popup", "sprinkler"):
        row, em = sy["sp"]; q = sy["q"]
    elif sk == "pivot":
        row = em = q = None
    else:
        row, em = (0.4, 0.4) if cat == "turf" else (P["row"], P["em"]); q = DRIPQ[cat]
    Hop = sy["Hop"]
    lay = make_layout(P, sk, row, em)
    nlat, Qs, maxh = len(lay["laterals"]), P["Qs"], P["maxh"]
    if sk == "pivot":
        n = len(lay["pivots"]); rate = gross / 20.0; t = 20.0
        Qp = A * rate / 1000 / n
        if P["water"] != "scratch" and Qp > Qs:
            Qp = Qs; rate = Qp * n * 1000 / A; t = gross / rate
        hours = t
    else:
        rate = q / (row * em); t = gross / rate
        Qfull = A * rate / 1000
        if P["water"] == "scratch":
            n = max(1, int(maxh // t))
        else:
            n = max(1, math.ceil(Qfull / Qs))
        n_hours = max(1, math.ceil(nlat * t / maxh))
        n = max(n, min(n_hours, nlat))
        n = min(n, nlat); Qp = Qfull / n; hours = n * t
        if sk in ("popup", "sprinkler") and rate > INFIL[P["soil"]]:
            W.append("Application rate %.1f mm/h exceeds soil intake rate %d mm/h: run-off risk, use cycle-and-soak."
                     % (rate, INFIL[P["soil"]]))
    if hours > maxh:
        W.append("Required pumping time %.1f h/day exceeds the available window of %.1f h: increase daily hours, "
                 "reduce net area, split the field or accept deficit irrigation." % (hours, maxh))
    if P["slope"] > 8 and sk in ("popup", "sprinkler", "drip"):
        W.append("Slope %.1f %%: use pressure-compensating emitters and run laterals along contours." % P["slope"])
    ptable = []
    lat_id = lambda D: DRIP_ID.get(D, PE_IDF * D) if sk in ("drip", "sdi") else PE_IDF * D
    lens = []
    if sk == "pivot":
        Rm = lay["pivots"][0][2]
        Lmain = max(10.0, max(m.length for m in lay["mains"]))
        Dmain = pick(Qp, lambda D: hw(Qp, D, Lmain), MAINS, V_MAX_MAIN, max(2.0, .15 * Hop))
        hf_lat = 0.55 * hw(Qp, 168 / 0.9, Rm, C=130); hf_sub = 0.0; hf_main = hw(Qp, Dmain, Lmain)
        Dlat = Dsub = None; Lmax = Rm; Nmax = 1; lens = []; Nem = 0
        pipes = [("Main pipe PE/PVC", Dmain, sum(max(10.0, m.length) for m in lay["mains"]))]
        ptable = [("Main", Dmain, Lmain, Qp, vel(Qp, Dmain), hf_main),
                  ("Pivot span (168 mm ID)", 168, Rm, Qp, vel(Qp, 168 / 0.9), hf_lat)]
        lay["n"] = n; Lsub = 0.0
    else:
        lens = [s["line"].length for s in lay["laterals"]]
        Lmax = max(lens); Nmax = n_em(Lmax, em, sk); Qlat = Nmax * q / 1000
        opts = LAT_SPR if sk in ("popup", "sprinkler") else (LAT_DRIP if sk == "drip" else [16, 20, 25])
        F = chr_F(Nmax)
        Dlat = pick(Qlat, lambda D: F * hw(Qlat, D, Lmax, id_mm=lat_id(D)), opts, V_MAX_LAT, 0.10 * Hop)
        hf_lat = F * hw(Qlat, Dlat, Lmax, id_mm=lat_id(Dlat))
        miny, maxy = lay["sub"].coords[0][1], lay["sub"].coords[1][1]
        bands = np.array_split(np.arange(nlat), n)
        zstart = [lay["laterals"][b[0]]["y"] for b in bands]
        Lto, Lband = max(0.0, zstart[-1] - miny), max(1.0, maxy - zstart[-1])
        fsub = lambda D: hw(Qp, D, Lto) + 0.4 * hw(Qp, D, Lband)
        Dsub = pick(Qp, fsub, MAINS, V_MAX_MAIN, 0.10 * Hop)
        hf_sub = fsub(Dsub)
        Lsub = lay["sub"].length
        Lmain = max(10.0, lay["mains"][0].length)
        Dmain = pick(Qp, lambda D: hw(Qp, D, Lmain), MAINS, V_MAX_MAIN, max(2.0, .15 * Hop))
        hf_main = hw(Qp, Dmain, Lmain)
        Nem = sum(n_em(l, em, sk) for l in lens)
        pipes = [("Lateral PE (%s)" % ("sprinkler line" if q > 100 else "dripline"), Dlat, sum(lens)),
                 ("Submain PE/PVC", Dsub, Lsub), ("Main pipe PE/PVC", Dmain, Lmain)]
        ptable = [("Lateral (longest)", Dlat, Lmax, Qlat, vel(Qlat, Dlat), hf_lat),
                  ("Submain (farthest zone)", Dsub, Lsub, Qp, vel(Qp, Dsub), hf_sub),
                  ("Main", Dmain, Lmain, Qp, vel(Qp, Dmain), hf_main)]
        lay["zone_y"] = zstart; lay["n"] = n
        for zi, b in enumerate(bands):
            for i in b:
                lay["laterals"][i]["zone"] = zi
    if hf_lat / Hop > 0.20:
        W.append("Lateral friction loss alone is %.0f %% of operating pressure (>20 %%): split laterals, use "
                 "pressure-compensating emitters or a bigger dripline." % (100 * hf_lat / Hop))
    if (hf_lat + hf_sub) / Hop > 0.20:
        W.append("Lateral+submain friction is %.0f %% of operating pressure (>20 %%): pressure uniformity at risk."
                 % (100 * (hf_lat + hf_sub) / Hop))
    if sk != "pivot" and vel(Qp, Dmain) > V_MAX_MAIN:
        W.append("Main-pipe velocity %.2f m/s exceeds the %.1f m/s limit: consider a larger main."
                 % (vel(Qp, Dmain), V_MAX_MAIN))
    if Nem > DXF_EMITTER_LIMIT:
        W.append("Emitters (%d) exceed %d: individual points are NOT plotted in the DXF (memory safety)."
                 % (Nem, DXF_EMITTER_LIMIT))
    elev = 0.5 * P["relief"]
    fric = hf_lat + hf_sub + hf_main
    minor = 0.10 * fric
    TDH = Hop + HF_SAFETY * fric + minor + 5.0 + P["lift"] + elev
    Psh = Qp * TDH / (367 * 0.65)
    motor = next((m for m in MOTORS if m >= 1.15 * Psh), MOTORS[-1]); Pin = Psh / 0.90
    months = P.get("season") or list(range(1, 13))
    et0_m = P.get("et0_m") or [P["et0_ann"] / 12.0] * 12
    rain_m = P.get("rain_m") or [P["rain"] / 12.0] * 12
    net_mm = sum(max(0.0, P["kc"] * et0_m[m - 1] - EFF_RAIN * rain_m[m - 1]) for m in months) * 30.42
    Vann = net_mm / Ea * A / 1000
    kwh = Pin * Vann / Qp
    liters = Psh * 0.28 * Vann / Qp
    e_cost = kwh * P["pe"] if P["power"] == "grid" else (liters * P["pd"] if P["power"] == "diesel" else 0.0)
    k = P["pidx"]; rows = []

    def add(name, qty, unit, uc):
        rows.append((name, round(float(qty), 1), unit, round(uc * k, 2), round(qty * uc * k)))

    for nm, D, Lm in pipes:
        add("%s D%d mm" % (nm, D), Lm, "m", PIPE_PRICE[D] * (sy.get("inst", 1.0) if "Lateral" in nm else 1.0))
    if sk == "pivot":
        add("Center-pivot machine (%d unit)" % n, n, "ea", 6000 + 1500 * A / 1e4 / n)
    else:
        add("Emitters / sprinkler heads", Nem, "ea", sy["pe"])
        add("Zone valves (%d zones)" % n, n, "ea", 150)
    add("Fittings, valves & air release (10 % of pipe)", 1, "lot", 0.10 * sum(r[4] for r in rows) / k)
    add("Controller & wiring", 1, "lot", 600 + 25 * n)
    add("Filtration%s (%.0f m3/h)" % (" & fertigation" if P["prod"] else "", Qp), 1, "lot", 35 * Qp + (1500 if P["prod"] else 0))
    add("Pump + motor %.1f kW (%.0f m3/h @ %.0f m)" % (motor, Qp, TDH), 1, "set", 400 + 240 * motor)
    add("Trenching & backfill (main + submain)", pipes[-1][2] + (pipes[-2][2] if sk != "pivot" else 0), "m", 4)
    if P["power"] == "grid":
        add("Grid connection, transformer & panel", 1, "lot", 2000 + 60 * motor)
    elif P["power"] == "diesel":
        add("Diesel generator %.0f kVA" % (1.5 * motor), 1, "set", 350 * 1.5 * motor + 800)
    else:
        kwp = 1.3 * Pin
        add("Solar PV array %.1f kWp" % kwp, kwp, "kWp", P["pv"])
        add("Solar pump inverter / VFD", 1, "set", 150 * motor + 300)
    if P["water"] == "scratch":
        depth = P["lift"] + 30
        add("Borehole drilling + casing (%.0f m)" % depth, depth, "m", P["bh"])
        add("Borehole development & test pumping", 1, "lot", 2000)
    elif P["water"] == "surface":
        add("Intake structure & screen", 1, "lot", 1500)
    else:
        add("Well head connection", 1, "lot", 500)
    mat = sum(r[4] for r in rows)
    inst = mat * P["labor"] / 100
    cont = (mat + inst) * P["cont"] / 100
    capex = mat + inst + cont
    opex = dict(energy=e_cost, maint=0.03 * mat, labor=max(300.0, 60 * A / 1e4), water=Vann * P["pw"])
    opex_t = sum(opex.values())
    r_, N_ = P["disc"] / 100, P["life"]
    tco = capex + opex_t * ((1 - (1 + r_) ** -N_) / r_ if r_ > 0 else N_)
    return dict(sk=sk, name=sy["name"], Ea=Ea, gross=gross, Vday=gross * A / 1000, rate=rate, t=t, n=n, Qp=Qp,
                hours=hours, Hop=Hop, Dlat=Dlat, Dsub=Dsub, Dmain=Dmain, Lmax=Lmax, Nmax=Nmax,
                Lmain=sum(m.length for m in lay["mains"]), Lsub=Lsub, Llat=sum(lens), hf_lat=hf_lat, hf_sub=hf_sub,
                hf_main=hf_main, minor=minor, TDH=TDH, Psh=Psh, motor=motor, Pin=Pin, Nem=Nem, Vann=Vann,
                kwh=kwh, liters=liters, rows=rows, mat=mat, inst=inst, cont=cont, capex=capex, opex=opex,
                opex_t=opex_t, tco=tco, W=W, lay=lay, q=q, row=row, em=em, ptable=ptable,
                lat_id=(None if sk == "pivot" else lat_id(Dlat)),
                capex_lo=capex * CAPEX_LO, capex_hi=capex * CAPEX_HI)


def recommend(P):
    cat, A, wind, soil = P["cat"], P["A_net"], P["wind2"], P["soil"]
    c = list(dict(turf=["popup", "sdi"], shrub=["drip", "sdi"], tree=["drip", "sdi"],
                  veg=["drip", "sdi", "sprinkler"], orchard=["drip", "sdi", "sprinkler"],
                  field=["pivot", "sprinkler", "drip"])[cat])
    why = []
    if soil == "rocky":
        c = [x for x in c if x not in ("sdi", "pivot")]
        why.append("Rocky soil: buried laterals and pivot wheel tracks are not practical.")
    if cat == "field" and "pivot" in c and (A < 100000 or P["slope"] > 12):
        c.remove("pivot"); why.append("Center pivot needs >= 10 ha net area and slope <= 12 %.")
    rec = c[0]
    if wind > 3.0 and rec in ("popup", "sprinkler", "pivot"):
        dr = [x for x in c if x in ("drip", "sdi")]
        if dr and (wind > 4.5 or rec != "pivot"):
            rec = dr[0]
            why.append("Mean wind %.1f m/s at 2 m: wind drift makes sprinklers inefficient, drip selected." % wind)
    if soil == "sandy" and rec in ("popup", "sprinkler") and "sdi" in c:
        why.append("Sandy soil drains fast: frequent, short cycles are recommended.")
    if not why:
        why.append("Best technical match for the crop type, net area (%.2f ha), soil and wind." % (A / 1e4))
    return rec, c, why


# =====================================================================================
# 5. IRRIGATION SCHEDULING (soil-water depletion, RAW)
# =====================================================================================
def schedule_info(P, R):
    """Depletion-based scheduling: interval between events, events/day, per-event hours, daily timetable."""
    RAW = P_ALLOW * TAW[P["soil"]] * ZR[P["cat"]]                      # readily available water, mm
    evpd = P["etc"] / RAW if RAW > 0 else 1.0                          # events per day
    t_event = R["t"] / evpd                                          # hours per irrigation event
    interval = 1 if evpd >= 1 else max(1, min(30, int(round(1.0 / evpd))))
    n = R["n"]
    start_h = P.get("start_h", 22.0)
    rows = []
    acc = start_h
    for i in range(n):
        s_h, e_h = acc % 24.0, (acc + R["t"]) % 24.0
        rows.append(dict(zone=i + 1, valve="V%d" % (i + 1), Qp=R["Qp"], hours=R["t"],
                         start="%02d:%02d" % (int(s_h), int(round((s_h % 1) * 60))),
                         end="%02d:%02d" % (int(e_h), int(round((e_h % 1) * 60)))))
        acc += R["t"]
    return dict(RAW=RAW, evpd=evpd, t_event=t_event, interval=interval, rows=rows,
                fits=R["hours"] <= P["maxh"] + 1e-9)


# =====================================================================================
# 6. DXF GENERATOR
# =====================================================================================
def emitter_points(lay, sk, em):
    pts = []
    for s in lay["laterals"]:
        Ls = s["line"].length
        ds = np.arange(0, Ls + 1e-6, em) if sk in ("popup", "sprinkler") else np.arange(em / 2, Ls, em)
        for d in (ds if len(ds) else [Ls / 2]):
            p = s["line"].interpolate(float(d)); pts.append((p.x, p.y))
    return pts


def build_dxf(P, R, SCHED, CUR, FX, VAT):
    lay, sk = R["lay"], R["sk"]
    doc = ezdxf.new("R2010"); doc.units = 6; msp = doc.modelspace()
    layers = [("BOUNDARY", 3), ("EXCLUSION", 1), ("MAIN", 5), ("SUBMAIN", 4), ("EMITTER", 6), ("VALVE", 30),
              ("PUMP_SOURCE", 1), ("TEXT", 7), ("PIVOT", 2), ("WARNING", 1), ("TITLE_BLOCK", 7)]
    for ln, lc in layers:
        doc.layers.add(ln, color=lc)
    minx, miny, maxx, maxy = P["boundary"].bounds
    h = max(maxx - minx, maxy - miny, 10) / 90

    def txt(s, x, y, layer="TEXT", hh=None):
        msp.add_text(s, height=hh or h, dxfattribs={"layer": layer}).set_placement((x, y))

    msp.add_lwpolyline(list(P["boundary"].exterior.coords), close=True, dxfattribs={"layer": "BOUNDARY"})
    for e in P["excl_polys"]:
        msp.add_lwpolyline(list(e.exterior.coords), close=True, dxfattribs={"layer": "EXCLUSION"})
    for m in lay["mains"]:
        msp.add_lwpolyline(list(m.coords), dxfattribs={"layer": "MAIN", "const_width": h / 6})
    mid = lay["mains"][0].interpolate(0.5, normalized=True)
    txt("MAIN D%d mm L=%.0f m" % (R["Dmain"], R["Lmain"]), mid.x + h, mid.y, "MAIN")
    warn_y = miny - 8 * h
    if sk == "pivot":
        for i, (x, y, r) in enumerate(lay["pivots"]):
            msp.add_circle((x, y), r, dxfattribs={"layer": "PIVOT"})
            msp.add_line((x, y), (x + r, y), dxfattribs={"layer": "PIVOT"})
            txt("PIVOT %d  R=%.0f m" % (i + 1, r), x, y + h, "PIVOT")
    else:
        sub = lay["sub"]
        msp.add_lwpolyline(list(sub.coords), dxfattribs={"layer": "SUBMAIN", "const_width": h / 8})
        txt("SUBMAIN D%d mm" % R["Dsub"], lay["cx"] + h, sub.coords[0][1] + h * 3, "SUBMAIN")
        for zi in range(lay["n"]):
            ln = "LATERAL_Z%d" % (zi + 1)
            if ln not in doc.layers:
                doc.layers.add(ln, color=2 + zi % 6)
            vy, vx = lay["zone_y"][zi], lay["cx"]
            msp.add_lwpolyline([(vx - h / 2, vy - h / 2), (vx + h / 2, vy - h / 2), (vx + h / 2, vy + h / 2),
                                (vx - h / 2, vy + h / 2)], close=True, dxfattribs={"layer": "VALVE"})
            txt("V%d" % (zi + 1), vx + h, vy, "VALVE")
        for s in lay["laterals"]:
            msp.add_lwpolyline(list(s["line"].coords), dxfattribs={"layer": "LATERAL_Z%d" % (s["zone"] + 1)})
        txt("LATERAL D%d mm, emitter spacing %.2f m, row spacing %.2f m, q=%.1f L/h"
            % (R["Dlat"], R["em"], R["row"], R["q"]), minx, miny - 6 * h)
        if R["Nem"] <= DXF_EMITTER_LIMIT:
            for x, y in emitter_points(lay, sk, R["em"]):
                if sk in ("popup", "sprinkler"):
                    msp.add_circle((x, y), 0.5, dxfattribs={"layer": "EMITTER"})
                else:
                    msp.add_point((x, y), dxfattribs={"layer": "EMITTER"})
        else:
            txt("WARNING: %d emitters exceed the %d plotting limit - points NOT drawn (memory safety)."
                % (R["Nem"], DXF_EMITTER_LIMIT), minx, warn_y, "WARNING")
    sx, sy_ = lay["src"]
    msp.add_circle((sx, sy_), 1.25 * h, dxfattribs={"layer": "PUMP_SOURCE"})
    txt("PUMP / SOURCE  %.0f m3/h @ %.0f m, %.1f kW" % (R["Qp"], R["TDH"], R["motor"]), sx + h, sy_ - h, "PUMP_SOURCE")
    for i, s in enumerate(["SMART IRRIGATION DESIGN - %s" % R["name"],
                           "CRS: %s (UTM, metres) | Gross %.0f m2 | Net %.0f m2" % (P["epsg"], P["A_gross"], P["A_net"]),
                           "Zones: %d | Q=%.1f m3/h | TDH=%.1f m | PRELIMINARY - verify before construction"
                           % (R["n"], R["Qp"], R["TDH"])]):
        txt(s, minx, miny - (10 + 2 * i) * h)
    # ---- title block with schedule ----
    tb_w = 110; rows_show = min(R["n"], 30)
    tb_h = 92 + 4.2 * rows_show
    tb_x, tb_y = maxx + 12, maxy
    msp.add_lwpolyline([(tb_x, tb_y), (tb_x + tb_w, tb_y), (tb_x + tb_w, tb_y - tb_h), (tb_x, tb_y - tb_h)],
                       close=True, dxfattribs={"layer": "TITLE_BLOCK"})
    bh = 3.4
    head = ["IRRIGATION SCHEDULE & SECTORS", "Brand: %s" % BRAND,
            "Pump: %.1f m3/h | TDH %.1f m | Motor %.1f kW" % (R["Qp"], R["TDH"], R["motor"]),
            "Interval: every %d d | Events/day: %.2f | Event duration: %.2f h" % (SCHED["interval"], SCHED["evpd"], SCHED["t_event"]),
            "Daily window: %.1f h (fits: %s)" % (R["hours"], "YES" if SCHED["fits"] else "NO - SPLIT/EXTEND"),
            "CAPEX: %s | +VAT(%.0f%%): %s" % (fmt_cur(R["capex"], CUR, FX), VAT, fmt_cur(R["capex"] * FX and R["capex"] * (1 + VAT / 100), CUR, FX))]
    ycur = tb_y - 4
    for i, s in enumerate(head):
        txt(s, tb_x + 3, ycur, "TITLE_BLOCK", hh=bh * (1.5 if i == 0 else 1.0))
        ycur -= bh * 1.7
    txt("ZONE | FLOW m3/h | RUN h/day | START - END", tb_x + 3, ycur, "TITLE_BLOCK", hh=bh); ycur -= bh * 1.4
    for r in SCHED["rows"][:rows_show]:
        txt("%s | %.1f | %.2f | %s - %s" % (r["valve"], r["Qp"], r["hours"], r["start"], r["end"]),
            tb_x + 3, ycur, "TITLE_BLOCK", hh=bh * 0.85)
        ycur -= bh * 1.15
    txt(DISCLAIMER[:120], tb_x + 3, ycur - 2, "WARNING", hh=bh * 0.8)
    buf = io.StringIO(); doc.write(buf)
    return buf.getvalue().encode("utf-8")


# =====================================================================================
# 7. REPORTS
# =====================================================================================
def fmt_cur(x, cur, fx):
    return "{:,.0f} {}".format(x * fx, cur)


def money(x):
    return "{:,.0f}".format(x)


def make_reports(P, R, ALT, why, SCHED, CUR, FX, VAT):
    A = P["A_net"]
    saving = max(0, 100 * (1 - 0.55 / R["Ea"]))
    eng = ["# Technical report: hydraulic design",
           "## 1. Site and climate",
           "- Gross area %.0f m2; excluded area %.0f m2; net cultivated area A_net = %.0f m2 (%.2f ha)."
           % (P["A_gross"], P["A_excl"], A, A / 1e4),
           "- Peak-month ET0 (FAO-56 Penman-Monteith) = %.2f mm/day; wind at 2 m = %.1f m/s; slope = %.1f %%."
           % (P["et0"], P["wind2"], P["slope"]),
           "- Kc = %.2f -> ETc = %.2f mm/day. Application efficiency Ea = %.0f %%; gross requirement = %.2f mm/day = %.1f m3/day."
           % (P["kc"], P["etc"], 100 * R["Ea"], R["gross"], R["Vday"]),
           "## 2. Selected system: %s" % R["name"]] + ["- " + w for w in why] + [
           "- Application rate %.2f mm/h; %d zone(s) in sequence, %.1f h per zone per day, %.1f h/day total."
           % (R["rate"], R["n"], R["t"], R["hours"]),
           "- Design flow per zone Q = %.1f m3/h (%.2f L/s); operating pressure %.0f m (%.1f bar)."
           % (R["Qp"], R["Qp"] / 3.6, R["Hop"], R["Hop"] / 10.2),
           "## 3. Irrigation scheduling (soil-water balance)",
           "- Readily available water RAW = %.0f mm (soil TAW %d mm/m x rooting depth %.2f m x p = %.2f)."
           % (SCHED["RAW"], TAW[P["soil"]], ZR[P["cat"]], P_ALLOW),
           "- Irrigation interval: every %d day(s); %.2f event(s)/day; %.2f h per event; daily window needed = %.1f h / available %.1f h: %s."
           % (SCHED["interval"], SCHED["evpd"], SCHED["t_event"], R["hours"], P["maxh"],
              "FITS" if SCHED["fits"] else "DOES NOT FIT - split zones or extend the window"),
           "## 4. Pipe network (Hazen-Williams, C = 140)"]
    if R["sk"] == "pivot":
        eng.append("- Main: D%d mm, %.0f m, head loss %.2f m. Pivot span loss %.2f m."
                   % (R["Dmain"], R["Lmain"], R["hf_main"], R["hf_lat"]))
    else:
        lid = R.get("lat_id")
        eng += ["- Laterals: D%d mm%s, longest %.0f m with %d emitters, Christiansen friction %.2f m."
                % (R["Dlat"], "" if not lid else " (dripline ID %.1f mm)" % lid, R["Lmax"], R["Nmax"], R["hf_lat"]),
                "- Submain: D%d mm, %.0f m, head loss to farthest zone %.2f m." % (R["Dsub"], R["Lsub"], R["hf_sub"]),
                "- Main: D%d mm, %.0f m, head loss %.2f m (velocity limit %.1f m/s)."
                % (R["Dmain"], R["Lmain"], R["hf_main"], V_MAX_MAIN)]
    eng += ["- Total emitters / heads: %d; total lateral length %.0f m." % (R["Nem"], R["Llat"]),
            "## 5. Pump and energy",
            "- TDH = %.1f m (operating %.0f + friction %.1f x %.2f safety + minor %.1f + filter 5 + static lift %.0f + terrain %.1f)."
            % (R["TDH"], R["Hop"], R["hf_lat"] + R["hf_sub"] + R["hf_main"], HF_SAFETY, R["minor"], P["lift"], 0.5 * P["relief"]),
            "- Pump duty %.1f m3/h @ %.1f m; shaft %.1f kW; motor %.1f kW; input %.1f kW." % (R["Qp"], R["TDH"], R["Psh"], R["motor"], R["Pin"]),
            "- Annual water %.0f m3; annual energy %.0f kWh%s." % (R["Vann"], R["kwh"],
              " (%.0f L diesel)" % R["liters"] if P["power"] == "diesel" else ""),
            "## 6. Warnings and assumptions"] + (["- " + w for w in R["W"]] or ["- No critical warnings."]) + [
            "- Assumptions: dripline ID %.1f mm for D%d lateral (verify with the manufacturer datasheet); friction x %.2f safety; "
            "growing season = month(s) %s; effective rainfall coefficient %.2f." % (lid or 0, R["Dlat"], HF_SAFETY,
              ",".join(map(str, P.get("season") or range(1, 13))), EFF_RAIN),
            "- Preliminary straight-lateral layout; the final design needs a topographic survey and pump curves."]
    cli = ["# Your irrigation project in simple words",
           "- We recommend: %s." % R["name"],
           "- %s" % SYS[R["sk"]]["look"],
           "- Your plants need about %.0f cubic metres of water per day in the hottest season." % R["Vday"],
           "- Compared with traditional flood irrigation this system can save about %.0f %% of the water." % saving,
           "- Total water use is about %.0f cubic metres per year." % R["Vann"],
           "- Estimated investment: %s on average - realistic band %s to %s (budget at the high end). "
           "Yearly running cost: about %s." % (fmt_cur(R["capex"], CUR, FX), fmt_cur(R["capex_lo"], CUR, FX),
                                               fmt_cur(R["capex_hi"], CUR, FX), fmt_cur(R["opex_t"], CUR, FX)),
           "- The land is watered automatically in %d section(s) by a controller, every %d day(s)." % (R["n"], SCHED["interval"])]
    best = min(ALT.values(), key=lambda r: r["tco"]); cheap = min(ALT.values(), key=lambda r: r["capex"])
    eco = ["# Economic report: first cost versus long-term efficiency",
           "- Life-cycle cost = CAPEX + present value of yearly running costs over %d years at %.1f %% discount." % (P["life"], P["disc"]),
           "- CAPEX band for the recommended system: %s optimistic - %s base - %s pessimistic (all excluding VAT; add %.0f %% VAT -> %s)."
           % (fmt_cur(R["capex_lo"], CUR, FX), fmt_cur(R["capex"], CUR, FX), fmt_cur(R["capex_hi"], CUR, FX),
              VAT, fmt_cur(R["capex"] * (1 + VAT / 100), CUR, FX)),
           "- Lowest first cost: %s (%s)." % (cheap["name"], fmt_cur(cheap["capex"], CUR, FX)),
           "- Lowest life-cycle cost: %s (%s)." % (best["name"], fmt_cur(best["tco"], CUR, FX))]
    if best["sk"] != cheap["sk"] and cheap["opex_t"] > best["opex_t"]:
        eco.append("- The extra investment pays back in about %.1f years through lower running costs."
                   % max(0, (best["capex"] - cheap["capex"]) / (cheap["opex_t"] - best["opex_t"])))
    eco.append("- Technical recommendation: %s." % R["name"])
    return "\n".join(eng), "\n".join(cli), "\n".join(eco)


# =====================================================================================
# 8. PLOTS
# =====================================================================================
def _fill(ax, g, **kw):
    for p in (g.geoms if g.geom_type.startswith("Multi") else [g]):
        if p.is_empty:
            continue
        ax.fill(*p.exterior.xy, **kw)
        for i in p.interiors:
            ax.fill(*i.xy, color="white")


def plot_boundary(G):
    fig, ax = plt.subplots(figsize=(5, 4))
    _fill(ax, G["boundary"], color="#cfe8cf", ec="green", lw=2)
    for e in G["excl_polys"]:
        _fill(ax, e, color="#f4b6b6", ec="red")
    ax.set_aspect("equal"); ax.ticklabel_format(useOffset=False, style="plain"); ax.tick_params(labelsize=6)
    return fig


def plot_layout(P, R):
    fig, ax = plt.subplots(figsize=(7, 6)); lay = R["lay"]
    _fill(ax, P["boundary"], color="#cfe8cf", ec="green", lw=2)
    for e in P["excl_polys"]:
        _fill(ax, e, color="#f4b6b6", ec="red")
    cols = plt.cm.tab10.colors
    for s in lay["laterals"]:
        ax.plot(*s["line"].xy, color=cols[s["zone"] % 10], lw=.5)
    if lay["sub"] is not None:
        ax.plot(*lay["sub"].xy, color="blue", lw=2)
    for m in lay["mains"]:
        ax.plot(*m.xy, color="navy", lw=3)
    for x, y, r in lay["pivots"]:
        ax.add_patch(plt.Circle((x, y), r, fill=False, ec="orange", lw=2))
    for vy in lay.get("zone_y", []):
        ax.plot(lay["cx"], vy, "s", color="purple", ms=5)
    ax.plot(*lay["src"], "ro", ms=9); ax.set_aspect("equal"); ax.set_xlabel("E (m)"); ax.set_ylabel("N (m)")
    ax.ticklabel_format(useOffset=False, style="plain"); ax.tick_params(labelsize=7)
    return fig


# =====================================================================================
# 9. USER INTERFACE
# =====================================================================================
def polys_from(drawings):
    out = []
    for f in drawings or []:
        g = (f or {}).get("geometry", {})
        if g.get("type") == "Polygon" and g.get("coordinates"):
            out.append([tuple(c[:2]) for c in g["coordinates"][0]])
    return out


def largest(g):
    return max(g.geoms, key=lambda x: x.area) if g.geom_type.startswith("Multi") else g


GPS_JS = """
<script>
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    function(p){
      var u = new URL(window.parent.location.href);
      u.searchParams.set('lat', p.coords.latitude.toFixed(5));
      u.searchParams.set('lon', p.coords.longitude.toFixed(5));
      window.parent.location.href = u.toString();
    },
    function(e){ window.parent.location.search += '&gpserr=1'; },
    {enableHighAccuracy: true, timeout: 12000, maximumAge: 60000});
}
</script>
"""

ss = st.session_state
ss.setdefault("center", (30.0, 31.2)); ss.setdefault("ver", 0); ss.setdefault("excl", [])
ss.setdefault("boundary", None); ss.setdefault("res", None)

st.title("💧 " + T("Smart Irrigation Network Design & Cost AI Agent"))
st.caption(T("Free preliminary design tool: FAO-56 Penman-Monteith, Hazen-Williams, scheduling, sectors & DXF output."))

# ---- sidebar economics ----
with st.sidebar.expander("💰 " + T("Economics & currency"), expanded=False):
    CUR = st.selectbox(T("Currency"), list(CURRENCIES.keys()), index=0)
    fx = st.number_input(T("Exchange rate (local per USD)"), 0.01, 10000.0, float(CURRENCIES[CUR][0]), 0.01)
    vat = st.number_input(T("VAT (%)"), 0.0, 30.0, float(CURRENCIES[CUR][1]), 0.5)
    price_e = st.number_input(T("Electricity price (USD/kWh)"), 0.0, 5.0, 0.10, 0.01)
    price_d = st.number_input(T("Diesel price (USD/L)"), 0.0, 5.0, 0.80, 0.05)
    price_w = st.number_input(T("Water price (USD/m3)"), 0.0, 10.0, 0.0, 0.05)
    pv_cost = st.number_input(T("Solar PV cost (USD/kWp)"), 100.0, 3000.0, 700.0, 50.0)
    bh_cost = st.number_input(T("Borehole cost (USD/m)"), 10.0, 500.0, 70.0, 5.0)
    labor = st.number_input(T("Installation labour (% of materials)"), 0.0, 100.0, 20.0, 1.0)
    cont = st.number_input(T("Contingency (%)"), 0.0, 50.0, 10.0, 1.0)
    disc = st.number_input(T("Discount rate (%)"), 0.0, 30.0, 8.0, 0.5)
    life = st.number_input(T("Project life (years)"), 3, 40, 10, 1)
    pidx = st.number_input(T("Local price index (1.0 = reference)"), 0.2, 5.0, 1.0, 0.05)

# ---------------- 9.1 MAP ----------------
st.header("🗺️ 1. " + T("Satellite map & boundary drawing"))
st.info(T("Use the polygon or rectangle tool on the map, then press the matching button below. "
          "Draw the land first (button 1), then the areas to cut out (button 2)."))
c1, c2, c3 = st.columns([2, 2, 1])
lat_in = c1.number_input(T("Latitude"), -85.0, 85.0, float(ss["center"][0]), 0.0001, format="%.5f")
lon_in = c2.number_input(T("Longitude"), -180.0, 180.0, float(ss["center"][1]), 0.0001, format="%.5f")
if c3.button("📍 " + T("Go to location"), use_container_width=True):
    ss["center"] = (lat_in, lon_in); ss["ver"] += 1; st.rerun()
if st.button("📡 " + T("Use my current GPS location")):
    ss["gps_pending"] = True
if ss.get("gps_pending"):
    qp = st.query_params
    if "gpserr" in qp:
        ss["gps_pending"] = False; qp.clear(); st.rerun()
    elif qp.get("lat"):
        try:
            ss["center"] = (float(qp["lat"]), float(qp["lon"])); ss["gps_pending"] = False
            qp.clear(); ss["ver"] += 1; st.rerun()
        except Exception:
            ss["gps_pending"] = False; qp.clear(); st.rerun()
    else:
        components.html(GPS_JS, height=0)
        st.info(T("Waiting for GPS - allow location access in the browser (requires HTTPS)."))

m = folium.Map(location=ss["center"], zoom_start=16, tiles=None, max_zoom=19)
folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                 attr="Esri World Imagery", name="Satellite (Esri)", max_zoom=19).add_to(m)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
Draw(export=False, position="topleft", edit_options={"edit": True, "remove": True},
     draw_options={"polygon": {"shapeOptions": {"color": "#00e000"}},
                   "rectangle": {"shapeOptions": {"color": "#00e000"}},
                   "polyline": False, "circle": False, "marker": False, "circlemarker": False}).add_to(m)
try:
    Geocoder(collapsed=True, add_marker=False).add_to(m)
except Exception:
    pass
folium.LayerControl().add_to(m)
try:
    out = st_folium(m, key="map%d" % ss["ver"], height=520, returned_objects=["all_drawings"], use_container_width=True)
except TypeError:
    out = st_folium(m, key="map%db" % ss["ver"], height=520, returned_objects=["all_drawings"])
except Exception as e:
    out = None; st.error("Map component error: %s" % e)
polys = polys_from(out.get("all_drawings") if out else None)
st.caption("%s: %d" % (T("Polygons currently drawn"), len(polys)))

b1, b2, b3 = st.columns(3)
if b1.button("🟢 1. " + T("Define Effective Land Boundary"), use_container_width=True):
    if polys:
        ss["boundary"] = polys[0]; ss["excl"] = []; ss["res"] = None; st.success(T("Boundary saved."))
    else:
        st.warning(T("Draw a polygon on the map first."))
if b2.button("🔴 2. " + T("Exclude Non-Cultivated Areas"), use_container_width=True):
    if not ss["boundary"]:
        st.warning(T("Define the land boundary first."))
    elif len(polys) < 2:
        st.warning(T("Draw the areas to cut out (buildings, roads, rocks) after the boundary, then press again."))
    else:
        ss["excl"] = polys[1:]; ss["res"] = None; st.success(T("Exclusions saved."))
if b3.button("🧹 3. " + T("Clear / Edit Boundary"), use_container_width=True):
    ss["boundary"] = None; ss["excl"] = []; ss["res"] = None; ss["ver"] += 1; st.rerun()

with st.expander("⌨️ " + T("Fallback: create a rectangular boundary by dimensions (if the map does not load)")):
    f1, f2 = st.columns(2)
    rw = f1.number_input(T("Width (m)"), 5.0, 20000.0, 100.0, 5.0)
    rl = f2.number_input(T("Length (m)"), 5.0, 20000.0, 150.0, 5.0)
    if st.button(T("Create rectangle at the latitude/longitude above")):
        fwd0, epsg0 = utm_of(lon_in, lat_in)
        ep0 = int(epsg0.split(":")[1])
        inv0 = Transformer.from_crs(ep0, 4326, always_xy=True)
        x0, y0 = fwd0.transform(lon_in, lat_in)
        ss["boundary"] = [inv0.transform(x0 + dx, y0 + dy) for dx, dy in
                          [(-rw / 2, -rl / 2), (rw / 2, -rl / 2), (rw / 2, rl / 2), (-rw / 2, rl / 2), (-rw / 2, -rl / 2)]]
        ss["excl"] = []; ss["res"] = None; st.success(T("Boundary saved."))

# ---------------- geometry -> areas ----------------
G = None
if ss["boundary"]:
    try:
        b = ss["boundary"]
        lon0, lat0 = float(np.mean([p[0] for p in b])), float(np.mean([p[1] for p in b]))
        fwd, epsg_s = utm_of(lon0, lat0)
        bp = largest(Polygon([fwd.transform(*p) for p in b]).buffer(0))
        ex = []
        for e in ss["excl"]:
            ep_ = largest(Polygon([fwd.transform(*p) for p in e]).buffer(0)).intersection(bp)
            if not ep_.is_empty and ep_.geom_type in ("Polygon", "MultiPolygon"):
                ex.append(largest(ep_))
        exu = unary_union(ex) if ex else None
        net = bp.difference(exu).buffer(0) if exu else bp
        G = dict(boundary=bp, excl_polys=ex, net=net, A_gross=bp.area, A_excl=bp.area - net.area, A_net=net.area,
                 lat=lat0, lon=lon0, epsg=epsg_s)
        k1, k2, k3 = st.columns(3)
        k1.metric(T("Total land area"), "%s m² (%.2f ha)" % (money(bp.area), bp.area / 1e4))
        k2.metric(T("Excluded area"), "%s m²" % money(G["A_excl"]))
        k3.metric(T("Net cultivated area (A_net)"), "%s m² (%.2f ha)" % (money(net.area), net.area / 1e4))
        fig = plot_boundary(G); st.pyplot(fig); plt.close(fig)
    except Exception as e:
        G = None; st.error("%s: %s" % (T("Invalid boundary"), e))

# ---------------- 9.2 WIZARD ----------------
st.header("🧭 2. " + T("Project inputs wizard"))
w1, w2 = st.columns(2)
cls = w1.radio(T("Project classification"), list(CLASSES), format_func=lambda k: T(CLASSES[k]))
crop = w1.selectbox(T("Crop / plant type"), list(CROPS[cls]), format_func=T)
soil = w1.selectbox(T("Soil type"), list(SOILS), format_func=lambda k: T(SOILS[k]))
water = w2.selectbox(T("Water source"), list(WATER), format_func=lambda k: T(WATER[k]))
power = w2.selectbox(T("Power & energy source"), list(POWER), format_func=lambda k: T(POWER[k]))
Qs = w2.number_input(T("Available source flow (m3/h)"), 1.0, 5000.0, 30.0, 1.0, disabled=(water == "scratch"))
lift = w2.number_input(T("Static lift: water level to pump (m)"), 0.0, 400.0, 40.0 if water != "surface" else 5.0, 1.0)
with st.expander("🌡️ " + T("Manual climate & slope overrides (0 = automatic)")):
    o1, o2, o3 = st.columns(3)
    ov_et0 = o1.number_input(T("Peak ET0 (mm/day)"), 0.0, 15.0, 0.0, 0.1)
    ov_wind = o2.number_input(T("Mean wind at 2 m (m/s)"), 0.0, 15.0, 0.0, 0.1)
    ov_slope = o3.number_input(T("Slope (%)"), 0.0, 60.0, 0.0, 0.5)

s1, s2, s3, s4 = st.columns(4)
sm1 = s1.selectbox(T("Growing season: start month"), list(range(1, 13)), index=3)
sm2 = s2.selectbox(T("Growing season: end month"), list(range(1, 13)), index=8)
maxh = s3.number_input(T("Daily operation window (h)"), 4.0, 24.0, 20.0, 0.5)
start_t = s4.time_input(T("Daily start time"), value=dt.time(22, 0))
season_m = list(range(sm1, sm2 + 1)) if sm2 >= sm1 else list(range(sm1, 13)) + list(range(1, sm2 + 1))
st.caption(T("Annual water & energy are summed month-by-month over these months (FAO-56 balance, 70 % effective rainfall). "
             "Zones run sequentially within the daily window."))

if st.button("🚀 " + T("Run AI design engine"), type="primary", use_container_width=True):
    if not G:
        st.error(T("Define the land boundary first."))
    elif G["A_net"] < 20:
        st.error(T("Net area is too small."))
    else:
        try:
            with st.spinner(T("Fetching climate & terrain, designing the network...")):
                clim = get_climate(round(G["lat"], 3), round(G["lon"], 3))
                minx, miny, maxx, maxy = G["boundary"].bounds
                ext = max(maxx - minx, maxy - miny, 50.0)
                relief, slope = get_relief(round(G["lat"], 4), round(G["lon"], 4), ext)
                if ov_slope:
                    slope = ov_slope; relief = slope / 100 * ext
                kc, cat, row, em = CROPS[cls][crop]
                et0 = ov_et0 or clim["et0_peak"]
                P = dict(G, cat=cat, kc=kc, row=row, em=em, soil=soil, water=water, power=power, Qs=Qs, lift=lift,
                         prod=(cls == "prod"), et0=et0, etc=kc * et0,
                         et0_ann=clim["et0_ann"] if not ov_et0 else ov_et0 * 0.6 * 365,
                         rain=clim["rain"], wind2=ov_wind or clim["wind2"], relief=relief, slope=slope,
                         clim_ok=clim["ok"], xcheck=clim.get("xcheck"), pe=price_e, pd=price_d, pw=price_w,
                         pv=pv_cost, bh=bh_cost, labor=labor, cont=cont, disc=disc, life=life, pidx=pidx,
                         season=season_m, et0_m=clim.get("et0_m"), rain_m=clim.get("rain_m"),
                         maxh=maxh, start_h=start_t.hour + start_t.minute / 60.0)
                rec, cands, why = recommend(P)
                ALT = {}
                for kx in cands:
                    try:
                        ALT[kx] = design(P, kx)
                    except Exception:
                        if kx == rec:
                            raise
                R = ALT[rec]
                SCHED = schedule_info(P, R)
                eng, cli, eco = make_reports(P, R, ALT, why, SCHED, CUR, fx, vat)
                ss["res"] = dict(P=P, R=R, ALT=ALT, SCHED=SCHED, eng=eng, cli=cli, eco=eco,
                                 dxf=build_dxf(P, R, SCHED, CUR, fx, vat), CUR=CUR, fx=fx, vat=vat)
        except Exception as e:
            ss["res"] = None; st.error("%s: %s" % (T("Design failed"), e))

# ---------------- 9.3 RESULTS ----------------
res = ss.get("res")
if res:
    P, R, ALT, SCHED = res["P"], res["R"], res["ALT"], res["SCHED"]
    CUR, fx, vat = res["CUR"], res["fx"], res["vat"]
    st.header("📊 3. " + T("Results & deliverables"))
    if not P["clim_ok"]:
        st.warning(T("Climate service unreachable: ET0 was estimated from latitude. Use the manual overrides for accuracy."))
    k = st.columns(5)
    k[0].metric("ET0 peak", "%.2f mm/d" % P["et0"], None if not P["xcheck"] else "Open-Meteo: %.2f" % P["xcheck"], delta_color="off")
    k[1].metric("ETc", "%.2f mm/d" % P["etc"]); k[2].metric(T("Flow per zone (m³/h)"), "%.1f" % R["Qp"])
    k[3].metric("TDH", "%.1f m" % R["TDH"]); k[4].metric(T("Pump motor (kW)"), "%.1f" % R["motor"])
    st.success("✅ " + T("Recommended system") + ": **" + tr_md(R["name"]) + "**")
    for w in R["W"]:
        st.warning(tr_md(w))
    tabs = st.tabs(["🗺️ " + T("Layout"), "💵 " + T("Cost report"), "⏰ " + T("Irrigation schedule"),
                    "📘 " + T("Engineer report"), "🏡 " + T("Client report"), "⚖️ " + T("Economic report"), "📐 " + T("DXF")])
    with tabs[0]:
        fig = plot_layout(P, R); st.pyplot(fig); plt.close(fig)
        st.caption(T("Colored lines = zone laterals, purple squares = zone valves, navy = main, red dot = pump. Preliminary layout."))
    with tabs[1]:
        df = pd.DataFrame(res["R"]["rows"], columns=["Item", "Qty", "Unit", "Unit cost (USD)", "Total (USD)"])
        df["Unit cost (%s)" % CUR] = (df["Unit cost (USD)"] * fx).map(lambda v: round(v, 2))
        df["Total (%s)" % CUR] = (df["Total (USD)"] * fx).map(lambda v: round(v, 0))
        st.dataframe(tdf(df.drop(columns=["Unit cost (USD)", "Total (USD)"])), use_container_width=True, hide_index=True)
        sub = R["capex"]; vat_amt = sub * vat / 100.0
        sm = pd.DataFrame([("Materials & equipment subtotal", sub), ("VAT (%.0f %%)" % vat, vat_amt),
                           ("TOTAL CAPITAL COST incl. VAT", sub + vat_amt),
                           ("Annual energy cost", R["opex"]["energy"]), ("Annual maintenance", R["opex"]["maint"]),
                           ("Annual labour", R["opex"]["labor"]), ("Annual water cost", R["opex"]["water"]),
                           ("TOTAL ANNUAL OPEX", R["opex_t"]),
                           ("Life-cycle cost (%d years)" % P["life"], R["tco"])], columns=["Summary", "USD"])
        sm[CUR] = sm["USD"].map(lambda v: fmt_cur(v, CUR, fx))
        st.dataframe(tdf(sm.drop(columns=["USD"])), use_container_width=True, hide_index=True)
        cb1, cb2, cb3 = st.columns(3)
        cb1.metric(T("Optimistic CAPEX"), fmt_cur(R["capex_lo"], CUR, fx))
        cb2.metric(T("Base CAPEX excl. VAT"), fmt_cur(R["capex"], CUR, fx))
        cb3.metric(T("Incl. VAT - budget here"), fmt_cur(R["capex"] * (1 + vat / 100), CUR, fx))
        st.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"), "cost_report.csv", "text/csv")
    with tabs[2]:
        cc = st.columns(4)
        cc[0].metric(T("Irrigation interval"), T("every %d d") % SCHED["interval"])
        cc[1].metric(T("Events per day"), "%.2f" % SCHED["evpd"])
        cc[2].metric(T("Hours per event"), "%.2f" % SCHED["t_event"])
        cc[3].metric(T("Daily window"), "%.1f / %.1f h" % (R["hours"], P["maxh"]))
        if not SCHED["fits"]:
            st.error(T("The daily schedule DOES NOT FIT the available window: increase daily hours, reduce area or accept deficit irrigation."))
        dfc = pd.DataFrame(SCHED["rows"])
        dfc.columns = ["Zone", "Valve", "Flow (m³/h)", "Run hours/day", "Start", "End"]
        st.dataframe(tdf(dfc), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.markdown(tr_md(res["eng"]))
        pt = pd.DataFrame([(a, b, round(c, 1), round(d, 2), round(e_, 2), round(f, 2)) for a, b, c, d, e_, f in R["ptable"]],
                          columns=["Pipe", "Nominal D (mm)", "Length (m)", "Flow (m³/h)", "Velocity (m/s)", "Head loss (m)"])
        st.dataframe(tdf(pt), use_container_width=True, hide_index=True)
    with tabs[4]:
        st.markdown(tr_md(res["cli"]))
    with tabs[5]:
        st.markdown(tr_md(res["eco"]))
        ed = pd.DataFrame([(r["name"], round(100 * r["Ea"]), fmt_cur(r["capex"], CUR, fx), fmt_cur(r["opex_t"], CUR, fx),
                            money(round(r["Vann"])), fmt_cur(r["tco"], CUR, fx)) for r in ALT.values()],
                          columns=["System", "Efficiency %", "CAPEX", "Annual OPEX", "Annual water (m³)", "Life-cycle cost"])
        st.dataframe(tdf(ed), use_container_width=True, hide_index=True)
    with tabs[6]:
        if R["Nem"] > DXF_EMITTER_LIMIT:
            st.warning("⚠️ " + T("Too many emitters for individual plotting: the DXF contains pipes, valves and notes only."))
        st.download_button("⬇️ " + T("Download AutoCAD DXF"), res["dxf"], "irrigation_design.dxf", "application/dxf",
                           type="primary", use_container_width=True)
        st.caption("%s %s" % (T("Coordinates are real UTM metres in"), P["epsg"]))
    allrep = "\n\n".join(tr_md(x) for x in (res["eng"], res["cli"], res["eco"]))
    st.download_button("⬇️ " + T("Download all reports (.md)"), allrep.encode("utf-8"), "irrigation_reports.md", "text/markdown")
    st.caption("⚠️ " + T(DISCLAIMER))
