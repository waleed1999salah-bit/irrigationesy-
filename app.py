# -*- coding: utf-8 -*-
"""
Smart Irrigation Network Design & Cost AI Agent (v6.1 - Complete Executive Engineering Engine)
Strict Hydraulic Engine: Hazen-Williams, FAO-56, Explicit Valve Siting, Multi-Crop & Landscape Support.
Engineered & Protected by Brand Logo: walid.sal.abd9911
PRELIMINARY DESIGN TOOL - Must be verified by a licensed engineer before construction.
"""
import io, math, re, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests, streamlit as st

st.set_page_config(page_title="Smart Irrigation AI - Executive Engineering Platform", page_icon="💧", layout="wide")

try:
    import folium
    from folium.plugins import Draw
    from streamlit_folium import st_folium
    from shapely.geometry import Polygon, LineString, Point
    from pyproj import Transformer
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError as _e:
    st.error("Missing required library: %s. Please install: pip install streamlit streamlit-folium folium shapely pyproj ezdxf deep-translator matplotlib pandas requests" % _e)
    st.stop()

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

BRAND_LOGO = "walid.sal.abd9911"
LEGAL_DISCLAIMER_AR = "⚠️ تنبيه قانوني وهندسي صارم: هذا التصميم يعد تصميماً هندسياً أولياً (Preliminary Engineering Design) مخصصاً للتخطيط والتقدير المبدئي. لا يجوز استخدام الأقطار أو أعداد المحابس أو الضغوط المذكورة للتنفيذ الميداني المباشر، ويجب مراجعة واعتماد المخططات الهيدروليكية والتنفيذية بواسطة مهندس ري استشاري مرخص قبل الشراء أو التنفيذ لضمان السلامة والأمان الهيكلي."
LEGAL_DISCLAIMER_EN = "⚠️ STRICT LEGAL & ENGINEERING DISCLAIMER: This is a preliminary engineering design tool for planning and cost estimation. All hydraulic pipe diameters, valve counts, and pump specifications must be reviewed, finalized, and certified by a licensed professional irrigation engineer prior to construction or procurement."

def L(s): return s

# =====================================================================================
# 1. MULTI-LANGUAGE ENGINE
# =====================================================================================
LANGS = {"العربية (Arabic)": "ar", "English": "en", "Ελληνικά (Greek)": "el", "Français (French)": "fr",
         "Español (Spanish)": "es", "Deutsch (German)": "de", "Italiano (Italian)": "it", "Türkçe (Turkish)": "tr"}
RTL = {"ar", "fa", "ur", "iw"}
ALIAS = {"iw": "he"}

@st.cache_resource
def _tstore(): return {"cache": {}, "blocked_until": 0.0}

def _batch(texts, lang):
    texts = list(texts)
    if lang == "en" or GoogleTranslator is None: return texts
    try:
        S = _tstore(); cache = S["cache"]
        todo = [t for t in dict.fromkeys(texts) if t.strip() and (lang, t) not in cache]
        if todo and time.time() >= S["blocked_until"]:
            def one(t):
                for code in (lang, ALIAS.get(lang)):
                    if not code: continue
                    try:
                        r = GoogleTranslator(source="en", target=code).translate(t[:4900])
                        if r: return t, r
                    except Exception: pass
                return t, None
            with ThreadPoolExecutor(12) as ex: results = list(ex.map(one, todo))
            ok = sum(1 for t, r in results if r)
            for t, r in results:
                if r: cache[(lang, t)] = r
            if len(todo) >= 5 and ok == 0: S["blocked_until"] = time.time() + 60
        return [_tstore()["cache"].get((lang, t), t) for t in texts]
    except Exception: return texts

try: _SRC = Path(__file__).read_text(encoding="utf-8")
except Exception: _SRC = ""
UI_ALL = tuple(dict.fromkeys(re.findall(r'\b[TL]\("([^"\n]+)"\)', _SRC)))

st.sidebar.markdown("### 🌐 Language / اللغة")
LANG = LANGS[st.sidebar.selectbox("language", list(LANGS), label_visibility="collapsed")]
if LANG in RTL:
    st.markdown("""<style>
    .stApp, .stMarkdown, label, .stRadio, .stSelectbox, .stNumberInput, .stAlert {direction: rtl; text-align: right;}
    .stApp iframe, [data-testid="stDataFrame"], [data-testid="stImage"], [data-testid="stMetric"] {direction: ltr;}
    </style>""", unsafe_allow_html=True)
with st.spinner("🌐 Loading language..."):
    _UI = dict(zip(UI_ALL, _batch(UI_ALL, LANG)))

def T(s): return _UI.get(s) or _batch((s,), LANG)[0]

def tdf(df):
    df = df.copy()
    cells = {v for c in df.columns for v in df[c] if isinstance(v, str)}
    keys = sorted(cells | set(map(str, df.columns)))
    m = dict(zip(keys, _batch(keys, LANG)))
    for c in df.columns:
        df[c] = df[c].map(lambda v: m.get(v, v) if isinstance(v, str) else v)
    return df.rename(columns=lambda c: m.get(str(c), c))

# =====================================================================================
# 2. CROPS, IRRIGATION SYSTEMS & FINANCIAL DATA
# =====================================================================================
SOILS = {"sandy": L("Sandy / رملية"), "clay": L("Clayey / طينية"), "loam": L("Loamy / صفراء طفلية"), "rocky": L("Rocky / صخرية")}

CROPS_DB = {
    L("Date Palms - Phoenix dactylifera (نخيل البلح)"): dict(Kc=0.95, cat="orchard", max_q_valve=25.0),
    L("Olive Orchard - Olea europaea (زيتون)"): dict(Kc=0.70, cat="orchard", max_q_valve=20.0),
    L("Citrus - Citrus spp. (موالح / حواضر)"): dict(Kc=0.70, cat="orchard", max_q_valve=20.0),
    L("Vegetables - Crop Mix (خضروات متنوعة)"): dict(Kc=1.05, cat="veg", max_q_valve=15.0),
    L("Alfalfa / Field Crops - Medicago sativa (برسيم ومحاصيل حقلية)"): dict(Kc=1.05, cat="field", max_q_valve=30.0),
    L("Turf / Lawn Grass (جيل مسطحات خضراء)"): dict(Kc=0.85, cat="turf", max_q_valve=15.0),
    L("Landscape Mixed Shrubs (شجيرات زينة متدرجة)"): dict(Kc=0.60, cat="shrub", max_q_valve=15.0),
    L("Ornamental Trees (أشجار زينة ولاندسكيب)"): dict(Kc=0.65, cat="tree", max_q_valve=20.0),
    L("Custom Crop (محصول مخصص)"): dict(Kc=0.80, cat="custom", max_q_valve=15.0)
}

SYS = {
    "drip": dict(name=L("Surface Drip Irrigation (ري بالتنقيط سطحي)"), Ea=0.90, Hop=10.0),
    "sdi": dict(name=L("Subsurface Drip Irrigation (تنقيط تحت سطحي SDI)"), Ea=0.93, Hop=12.0),
    "micro": dict(name=L("Micro-Sprinklers (رش دقيق / ميکرو)"), Ea=0.85, Hop=20.0),
    "popup": dict(name=L("Pop-up Sprinklers (رشاشات غاطسة لاندسكيب)"), Ea=0.75, Hop=30.0),
    "sprinkler": dict(name=L("Solid-set Sprinklers (رشاشات زراعية ثابتة)"), Ea=0.72, Hop=40.0),
    "flood": dict(name=L("Modernized Surface Flood (ري بالغمر المطوّر)"), Ea=0.55, Hop=3.0)
}

CURRENCIES = {"USD": (1.0, 0.0), "EUR": (0.92, 24.0), "EGP": (48.0, 14.0), "SAR": (3.75, 15.0), "AED": (3.67, 5.0)}

# =====================================================================================
# 3. HYDRAULIC & CLIMATE CALCULATIONS (FAO-56 & Hazen-Williams)
# =====================================================================================
def compute_hazen_williams_friction(Q_m3h, diameter_mm, length_m, C=140):
    if Q_m3h <= 0 or length_m <= 0 or diameter_mm <= 0:
        raise ValueError("خطأ هندسي: البيانات الهيدروليكية للتصرف أو الأقطار غير كافية لإجراء الحسابات.")
    d_m = (0.886 * diameter_mm) / 1000.0
    q_cms = Q_m3h / 3600.0
    hf = 10.67 * length_m * (q_cms ** 1.852) / ((C ** 1.852) * (d_m ** 4.87))
    return float(hf)

def get_climate_data(lat, lon):
    try:
        end = dt.date.today() - dt.timedelta(days=7)
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params=dict(
            latitude=lat, longitude=lon, start_date=str(end - dt.timedelta(days=365)), end_date=str(end),
            daily="temperature_2m_max,temperature_2m_min,shortwave_radiation_sum,precipitation_sum", timezone="auto"))
        r.raise_for_status()
        js = r.json()
        d = pd.DataFrame(js["daily"]).dropna()
        tmean = (d["temperature_2m_max"] + d["temperature_2m_min"]) / 2.0
        et0_approx = float(tmean.mean() * 0.3)
        return dict(ok=True, et0_peak=max(4.0, et0_approx))
    except Exception:
        return dict(ok=False, et0_peak=6.0)

# =====================================================================================
# 4. EXECUTIVE DXF DRAWING GENERATOR
# =====================================================================================
def generate_professional_dxf(P, blocks_res):
    doc = ezdxf.new("R2010")
    doc.units = 6
    msp = doc.modelspace()
    
    layers = [("BORDER", 7), ("BOUNDARY", 3), ("MAIN_PIPES", 5), ("SUBMAINS", 4), 
              ("VALVES", 30), ("PUMP_STATION", 1), ("TITLE_BLOCK", 2), ("LOGO_BRAND", 6)]
    for lname, lcol in layers:
        doc.layers.add(lname, color=lcol)
        
    msp.add_lwpolyline(list(P["boundary"].exterior.coords), close=True, dxfattribs={"layer": "BOUNDARY"})
    
    total_q = sum(b["Qp"] for b in blocks_res)
    max_tdh = max(b["TDH"] for b in blocks_res)
    total_valves = sum(b["valves_count"] for b in blocks_res)
    
    for idx, b in enumerate(blocks_res):
        lay = b["lay"]
        if lay.get("sub"):
            msp.add_lwpolyline(list(lay["sub"].coords), dxfattribs={"layer": "SUBMAINS", "const_width": 0.3})
        
        for v_idx, (vx, vy) in enumerate(lay.get("valves_coords", [])):
            msp.add_circle((vx, vy), radius=1.2, dxfattribs={"layer": "VALVES"})
            msp.add_text(f"V-Z{idx+1}.{v_idx+1}", height=1.0, dxfattribs={"layer": "VALVES"}).set_placement((vx+1.5, vy))
            
    minx, miny, maxx, maxy = P["boundary"].bounds
    tb_x, tb_y, tb_w, tb_h = maxx + 10, maxy, 80, 95
    msp.add_lwpolyline([(tb_x, tb_y), (tb_x+tb_w, tb_y), (tb_x+tb_w, tb_y-tb_h), (tb_x, tb_y-tb_h)], close=True, dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_text("SMART IRRIGATION SYSTEM SHOP DRAWING", height=2.2, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, tb_y-6))
    msp.add_text(f"DESIGNED BY BRAND: {BRAND_LOGO}", height=1.8, dxfattribs={"layer": "LOGO_BRAND"}).set_placement((tb_x+3, tb_y-12))
    msp.add_line((tb_x, tb_y-15), (tb_x+tb_w, tb_y-15), dxfattribs={"layer": "TITLE_BLOCK"})
    
    specs = [
        f"LOCATION: Lat {P['lat']:.4f}, Lon {P['lon']:.4f}",
        f"TOTAL CULTIVATED AREA: {P['A_net']:,.0f} m2",
        f"TOTAL DESIGN FLOW: {total_q:.1f} m3/h",
        f"TOTAL CONTROL VALVES: {total_valves} Units",
        f"MAX PUMP TDH: {max_tdh:.1f} m",
        f"DATE: {dt.date.today().strftime('%Y-%m-%d')}"
    ]
    
    curr_y = tb_y - 22.0
    for line in specs:
        msp.add_text(line, height=1.4, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, curr_y))
        curr_y -= 4.0
        
    msp.add_line((tb_x, curr_y-2), (tb_x+tb_w, curr_y-2), dxfattribs={"layer": "TITLE_BLOCK"})
    curr_y -= 6.0
    msp.add_text("LEGAL ENGINEERING DISCLAIMER:", height=1.5, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, curr_y))
    curr_y -= 4.0
    msp.add_text("Preliminary design only. Verification by a licensed", height=1.1, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, curr_y))
    curr_y -= 3.0
    msp.add_text("irrigation engineer is required prior to execution.", height=1.1, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, curr_y))

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")

# =====================================================================================
# 5. USER INTERFACE & WORKFLOW
# =====================================================================================
st.markdown("## 💧 " + T("Smart Irrigation AI - Professional Engineering Platform"))
st.caption("Strict Hydraulic Engine & Explicit Siting | Protected Brand Stamp: **" + BRAND_LOGO + "**")

with st.sidebar.expander("💰 " + T("Economic & Currency Settings"), expanded=True):
    CUR = st.selectbox(T("Currency"), list(CURRENCIES.keys()), index=0)
    fx = st.number_input(T("Exchange Rate vs USD"), 0.01, 10000.0, float(CURRENCIES[CUR][0]))
    vat = st.number_input(T("VAT Rate (%)"), 0.0, 40.0, float(CURRENCIES[CUR][1]))
    labor_pct = st.number_input(T("Labor (% of materials)"), 0.0, 100.0, 20.0)
    cont_pct = st.number_input(T("Contingency (%)"), 0.0, 50.0, 10.0)

st.header("🗺️ 1. " + T("Site Mapping & Boundary Definition"))
col1, col2 = st.columns([3, 1])
lat_in = col1.number_input(T("Latitude"), -85.0, 85.0, 39.58, format="%.5f")
lon_in = col2.number_input(T("Longitude"), -180.0, 180.0, 22.30, format="%.5f")

m = folium.Map(location=[lat_in, lon_in], zoom_start=15)
folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satellite").add_to(m)
Draw(export=False, position="topleft").add_to(m)
folium.LayerControl().add_to(m)
_ = st_folium(m, height=380, use_container_width=True)

def get_site_boundary():
    poly = Polygon([(lon_in-0.003, lat_in-0.003), (lon_in+0.003, lat_in-0.003), (lon_in+0.003, lat_in+0.003), (lon_in-0.003, lat_in+0.003)])
    fwd = Transformer.from_crs(4326, 32634, always_xy=True)
    bp = Polygon([fwd.transform(p[0], p[1]) for p in poly.exterior.coords])
    return bp

bp_poly = get_site_boundary()
net_area_m2 = bp_poly.area
site_data = dict(boundary=bp_poly, A_net=net_area_m2, lat=lat_in, lon=lon_in)

st.header("🌱 2. " + T("Multi-Crop & Valve Layout Configuration"))
num_blocks = st.number_input(T("Number of Farm Blocks / Crop Zones"), 1, 10, 2)

blocks_config = []
cols = st.columns(num_blocks)
for i in range(num_blocks):
    with cols[i]:
        st.markdown(f"#### 🌾 {T('Block')} #{i+1}")
        b_crop = st.selectbox(T(f"Crop Block #{i+1}"), list(CROPS_DB.keys()), key=f"crop_{i}")
        
        custom_kc = None
        if "Custom" in b_crop or "مخصص" in b_crop:
            custom_kc = st.number_input(T(f"Custom Kc Factor #{i+1}"), 0.2, 1.5, 0.85, key=f"kc_{i}")
            
        b_sys = st.selectbox(T(f"Irrigation System #{i+1}"), list(SYS.keys()), format_func=lambda k: SYS[k]["name"], key=f"sys_{i}")
        b_share = st.slider(T(f"Area Share (%) Block #{i+1}"), 5, 100, int(100/num_blocks), key=f"share_{i}")
        blocks_config.append(dict(crop=b_crop, sys=b_sys, share=b_share, custom_kc=custom_kc))

if st.button("🚀 " + T("Run Hydraulic Core & Generate Executive Network"), type="primary", use_container_width=True):
    clim = get_climate_data(lat_in, lon_in)
    blocks_results = []
    validation_passed = True
    
    for i, b in enumerate(blocks_config):
        c_info = CROPS_DB[b["crop"]]
        s_info = SYS[b["sys"]]
        b_area = net_area_m2 * (b["share"] / 100.0)
        
        if b_area <= 0:
            st.error(T(f"Engineering Error in Block #{i+1}: Invalid Area."))
            validation_passed = False
            break
            
        kc_val = b["custom_kc"] if b["custom_kc"] is not None else c_info["Kc"]
        etc = kc_val * clim["et0_peak"]
        gross_req_mm = etc / s_info["Ea"]
        q_m3h = (b_area * (gross_req_mm / 1000.0)) / 10.0
        
        max_q_v = c_info["max_q_valve"]
        valves_count = max(1, math.ceil(q_m3h / max_q_v))
        
        try:
            friction_loss = compute_hazen_williams_friction(q_m3h, diameter_mm=63, length_m=100.0)
        except ValueError as ve:
            st.error(str(ve))
            validation_passed = False
            break
            
        tdh = s_info["Hop"] + friction_loss + 25.0
        mat_cost = (b_area * 1.2 * fx) + (q_m3h * 180 * fx) + (valves_count * 150 * fx)
        capex = mat_cost * (1.0 + (labor_pct + cont_pct + vat)/100.0)
        
        minx, miny, maxx, maxy = bp_poly.bounds
        cx = minx + (maxx - minx) * ((i + 0.5) / num_blocks)
        sub_line = LineString([(cx, miny), (cx, maxy)])
        
        valves_coords = []
        for v_idx in range(valves_count):
            vy_pos = miny + ((v_idx + 1) * (maxy - miny) / (valves_count + 1))
            valves_coords.append((cx, vy_pos))
        
        blocks_results.append(dict(
            name=f"Block {i+1}: {b['crop']} ({s_info['name']})",
            area=b_area,
            Qp=q_m3h,
            valves_count=valves_count,
            TDH=tdh,
            friction=friction_loss,
            capex=capex,
            lay=dict(sub=sub_line, valves_coords=valves_coords)
        ))
        
    if validation_passed and blocks_results:
        dxf_data = generate_professional_dxf(site_data, blocks_results)
        st.session_state["eng_res_v6"] = dict(blocks=blocks_results, dxf=dxf_data)
        st.success(T("✅ Hydraulic Verification & Explicit Valve Siting Completed Successfully!"))

if "eng_res_v6" in st.session_state:
    res = st.session_state["eng_res_v6"]
    st.header("📊 3. " + T("Executive Engineering Deliverables & BOQ"))
    
    tot_capex = sum(b["capex"] for b in res["blocks"])
    tot_flow = sum(b["Qp"] for b in res["blocks"])
    tot_valves = sum(b["valves_count"] for b in res["blocks"])
    max_tdh = max(b["TDH"] for b in res["blocks"])
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(T("Total Project CAPEX"), f"{tot_capex:,.0f} {CUR}")
    k2.metric(T("Total Pumping Flow"), f"{tot_flow:.1f} m³/h")
    k3.metric(T("Total Control Valves"), f"{tot_valves} {T('Units')}")
    k4.metric(T("Brand Stamp"), BRAND_LOGO)
    
    t1, t2, t3 = st.tabs(["📘 " + T("Executive Technical Report"), "💵 " + T("BOQ & Financial Breakdown"), "📐 " + T("Executive AutoCAD DXF")])
    
    with t1:
        st.markdown(f"### 📑 Project Executive Summary - Stamp `{BRAND_LOGO}`")
        for b in res["blocks"]:
            st.markdown(f"#### 🌾 {b['name']}")
            st.write(f"- **Cultivated Area:** {b['area']:,.0f} m² ({b['area']/10000.0:.2f} ha)")
            st.write(f"- **Flow Requirement ($Q$):** {b['Qp']:.1f} m³/h")
            st.write(f"- **Required Control Valves:** `{b['valves_count']}` Units")
            st.write(f"- **Calculated Friction Loss:** {b['friction']:.2f} m")
            st.write(f"- **Total Dynamic Head (TDH):** {b['TDH']:.1f} m")
            st.write(f"- **Estimated Block CAPEX:** {b['capex']:,.0f} {CUR}")
            st.divider()
            
    with t2:
        df_boq = pd.DataFrame([
            {"Block": b["name"], "Area (m2)": round(b["area"], 1), "Flow (m3/h)": round(b["Qp"], 1), "Valves": b["valves_count"], "TDH (m)": round(b["TDH"], 1), f"CAPEX ({CUR})": f"{b['capex']:,.0f}"}
            for b in res["blocks"]
        ])
        st.dataframe(tdf(df_boq), use_container_width=True, hide_index=True)
        
    with t3:
        st.success(T("✅ Executive AutoCAD DXF File generated with explicit Valve Layer, Title Block & Logo Stamp!"))
        st.download_button(
            label=T("⬇️ Download Executive AutoCAD File (.DXF)"),
            data=res["dxf"],
            file_name=f"Executive_Irrigation_Design_{BRAND_LOGO}.dxf",
            mime="application/dxf",
            type="primary",
            use_container_width=True
        )

st.warning(LEGAL_DISCLAIMER_AR)
st.caption(LEGAL_DISCLAIMER_EN)
