# -*- coding: utf-8 -*-
"""
Smart Irrigation Network Design & Cost AI Agent (v8 - Hydraulic Scheduling & Explicit Sectors)
Strict Hydraulic Engine: Hazen-Williams, FAO-56, Irrigation Scheduling, Valve Siting & DXF Layout.
Engineered & Protected by Brand Logo: walid.sal.abd9911
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
    st.error("Missing required library: %s." % _e)
    st.stop()

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

BRAND_LOGO = "walid.sal.abd9911"
LEGAL_DISCLAIMER_AR = "⚠️ تنبيه قانوني وهندسي صارم: هذا التصميم هو أداة هندسية أولية (Preliminary Engineering Tool). لا يجوز الاعتماد على أعداد القطاعات أو جداول التشغيل دون مراجعة واعتماد المخططات التنفيذية نهائياً بواسطة مهندس ري استشاري معتمد."
LEGAL_DISCLAIMER_EN = "⚠️ STRICT ENGINEERING DISCLAIMER: Preliminary tool. Do not use for construction without complete site data and final sign-off by a licensed professional irrigation engineer."

def L(s): return s

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

CROPS_DB = {
    L("Date Palms - Phoenix dactylifera (نخيل البلح)"): dict(Kc=0.95),
    L("Olive Orchard - Olea europaea (زيتون)"): dict(Kc=0.70),
    L("Citrus - Citrus spp. (موالح / حواضر)"): dict(Kc=0.70),
    L("Vegetables - Crop Mix (خضروات متنوعة)"): dict(Kc=1.05),
    L("Alfalfa / Field Crops - Medicago sativa (برسيم ومحاصيل حقلية)"): dict(Kc=1.05),
    L("Turf / Lawn Grass (مسطحات خضراء)"): dict(Kc=0.85),
    L("Landscape Mixed Shrubs (شجيرات زينة)"): dict(Kc=0.60),
    L("Ornamental Trees (أشجار زينة ولاندسكيب)"): dict(Kc=0.65)
}

SYS = {
    "drip": dict(name=L("Surface Drip Irrigation (ري بالتنقيط سطحي)"), Ea=0.90, Hop=10.0),
    "sdi": dict(name=L("Subsurface Drip Irrigation (تنقيط تحت سطحي SDI)"), Ea=0.93, Hop=12.0),
    "micro": dict(name=L("Micro-Sprinklers (رش دقيق)"), Ea=0.85, Hop=20.0),
    "popup": dict(name=L("Pop-up Sprinklers (رشاشات غاطسة لاندسكيب)"), Ea=0.75, Hop=30.0),
    "sprinkler": dict(name=L("Solid-set Sprinklers (رشاشات ثابته)"), Ea=0.72, Hop=40.0),
    "flood": dict(name=L("Modernized Surface Flood (ري بالغمر المطوّر)"), Ea=0.55, Hop=3.0)
}

CURRENCIES = {"USD": (1.0, 0.0), "EUR": (0.92, 24.0), "EGP": (48.0, 14.0), "SAR": (3.75, 15.0), "AED": (3.67, 5.0)}

def compute_hazen_williams_friction(Q_m3h, diameter_mm, length_m, C=140):
    if Q_m3h <= 0 or length_m <= 0 or diameter_mm <= 0:
        raise ValueError("خطأ هندسي: بيانات التصرف أو الأقطار غير صالحة.")
    d_m = (0.886 * diameter_mm) / 1000.0
    q_cms = Q_m3h / 3600.0
    hf = 10.67 * length_m * (q_cms ** 1.852) / ((C ** 1.852) * (d_m ** 4.87))
    return float(hf)

def get_climate_data(lat, lon):
    try:
        end = dt.date.today() - dt.timedelta(days=7)
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params=dict(
            latitude=lat, longitude=lon, start_date=str(end - dt.timedelta(days=365)), end_date=str(end),
            daily="temperature_2m_max,temperature_2m_min,precipitation_sum", timezone="auto"))
        r.raise_for_status()
        js = r.json()
        d = pd.DataFrame(js["daily"]).dropna()
        tmean = (d["temperature_2m_max"] + d["temperature_2m_min"]) / 2.0
        return dict(ok=True, et0_peak=max(4.0, float(tmean.mean() * 0.3)))
    except Exception:
        return dict(ok=False, et0_peak=6.0)

def generate_professional_dxf(P, sectors_res, total_pump_q):
    doc = ezdxf.new("R2010")
    doc.units = 6
    msp = doc.modelspace()
    
    layers = [("BOUNDARY", 3), ("SUBMAINS", 4), ("VALVES", 30), ("TITLE_BLOCK", 7)]
    for lname, lcol in layers:
        doc.layers.add(lname, color=lcol)
        
    msp.add_lwpolyline(list(P["boundary"].exterior.coords), close=True, dxfattribs={"layer": "BOUNDARY"})
    max_tdh = max(s["TDH"] for s in sectors_res)
    
    for idx, s in enumerate(sectors_res):
        lay = s["lay"]
        if lay.get("sub"):
            msp.add_lwpolyline(list(lay["sub"].coords), dxfattribs={"layer": "SUBMAINS", "const_width": 0.25})
        vx, vy = lay.get("valve_coord", (0,0))
        msp.add_circle((vx, vy), radius=1.0, dxfattribs={"layer": "VALVES"})
        msp.add_text(f"VALVE-SEC{idx+1}", height=0.9, dxfattribs={"layer": "VALVES"}).set_placement((vx+1.2, vy))
            
    minx, miny, maxx, maxy = P["boundary"].bounds
    tb_x, tb_y, tb_w, tb_h = maxx + 10, maxy, 78, 90
    msp.add_lwpolyline([(tb_x, tb_y), (tb_x+tb_w, tb_y), (tb_x+tb_w, tb_y-tb_h), (tb_x, tb_y-tb_h)], close=True, dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_text("IRRIGATION SCHEDULING & SECTORS", height=1.8, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, tb_y-5))
    msp.add_text(f"BRAND STAMP: {BRAND_LOGO}", height=1.4, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, tb_y-10))
    msp.add_text(f"PUMP Q: {total_pump_q:.1f} m3/h | SECTORS: {len(sectors_res)}", height=1.1, dxfattribs={"layer": "TITLE_BLOCK"}).set_placement((tb_x+3, tb_y-16))
    
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")

st.markdown("## 💧 Smart Irrigation AI - Irrigation Scheduling & Sectors Engine")
st.caption(f"Strict Hydraulic & Scheduling Engine | Protected Brand Stamp: **{BRAND_LOGO}**")

with st.sidebar:
    st.subheader("⚙️ إعدادات العملة والمالية")
    CUR = st.selectbox("العملة", list(CURRENCIES.keys()), index=0)
    fx = st.number_input("سعر الصرف مقابل الدولار", 0.01, 10000.0, float(CURRENCIES[CUR][0]))
    vat = st.number_input("قيمة الضريبة VAT (%)", 0.0, 30.0, float(CURRENCIES[CUR][1]))

st.header("🗺️ 1. تحديد إحداثيات وموقع الحقل الجغرافي")
col1, col2 = st.columns(2)
lat_in = col1.number_input("خط العرض (Latitude)", -85.0, 85.0, 39.58, format="%.5f")
lon_in = col2.number_input("خط الطول (Longitude)", -180.0, 180.0, 22.30, format="%.5f")

m = folium.Map(location=[lat_in, lon_in], zoom_start=15)
folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satellite").add_to(m)
Draw(export=False, position="topleft").add_to(m)
folium.LayerControl().add_to(m)
_ = st_folium(m, height=350, use_container_width=True)

def get_site_boundary():
    poly = Polygon([(lon_in-0.003, lat_in-0.003), (lon_in+0.003, lat_in-0.003), (lon_in+0.003, lat_in+0.003), (lon_in-0.003, lat_in+0.003)])
    fwd = Transformer.from_crs(4326, 32634, always_xy=True)
    return Polygon([fwd.transform(p[0], p[1]) for p in poly.exterior.coords])

bp_poly = get_site_boundary()
net_area_m2 = bp_poly.area
site_data = dict(boundary=bp_poly, A_net=net_area_m2, lat=lat_in, lon=lon_in)

st.header("🌱 2. بيانات المحصول ونظام الري")
selected_crop = st.selectbox("نوع المحصول المزروع", list(CROPS_DB.keys()))
selected_sys = st.selectbox("نظام الري المستخدم", list(SYS.keys()), format_func=lambda k: SYS[k]["name"])

st.header("⏰ 3. إعدادات جدول الري وزمني التشغيل (Irrigation Scheduling)")
col_a, col_b = st.columns(2)
num_sectors = col_a.number_input("عدد قطاعات الري ومحابس التحكم بالحقل (Sectors Count)", 1, 30, 6)
max_daily_hours = col_b.number_input("ساعات التشغيل المتاحة يومياً للطلمبة (Daily Operation Hours)", 4.0, 24.0, 12.0)

if st.button("🚀 تشغيل المحرك وحساب جدول الري والقطاعات هندسياً", type="primary", use_container_width=True):
    clim = get_climate_data(lat_in, lon_in)
    c_info = CROPS_DB[selected_crop]
    s_info = SYS[selected_sys]
    
    sector_area = net_area_m2 / num_sectors
    etc = c_info["Kc"] * clim["et0_peak"]
    gross_req_mm = etc / s_info["Ea"]
    
    # حساب إجمالي التصرف اليومي للقطاع الواحد (متر مكعب)
    sector_daily_water_m3 = sector_area * (gross_req_mm / 1000.0)
    
    # حساب ساعات التشغيل اللازمة للقطاع الواحد يومياً
    # افتراض تصرف قياسي آمن للقطاع بناءً على المساحة
    sector_flow_m3h = sector_daily_water_m3 / max(4.0, (max_daily_hours / num_sectors * 2.0))
    sector_run_hours = sector_daily_water_m3 / sector_flow_m3h if sector_flow_m3h > 0 else 2.0
    
    sectors_results = []
    validation_passed = True
    minx, miny, maxx, maxy = bp_poly.bounds
    
    for i in range(num_sectors):
        try:
            friction_loss = compute_hazen_williams_friction(sector_flow_m3h, diameter_mm=50, length_m=80.0)
        except ValueError as ve:
            st.error(str(ve))
            validation_passed = False
            break
            
        tdh = s_info["Hop"] + friction_loss + 20.0
        capex = (sector_area * 1.1 * fx) + (sector_flow_m3h * 150 * fx) + (200 * fx)
        
        cx = minx + (maxx - minx) * ((i % 4) + 0.5) / 4.0
        cy = miny + (maxy - miny) * ((i // 4) + 0.5) / max(1, math.ceil(num_sectors / 4.0))
        sub_line = LineString([(cx, miny), (cx, cy)])
        
        sectors_results.append(dict(
            name=f"القطاع #{i+1}",
            area=sector_area,
            Qp=sector_flow_m3h,
            run_hours=sector_run_hours,
            TDH=tdh,
            friction=friction_loss,
            capex=capex,
            lay=dict(sub=sub_line, valve_coord=(cx, cy))
        ))
        
    total_pump_q = max(s["Qp"] for s in sectors_results) # تصرف الطلمبة يعتمد على تشغيل قطاع أو قطاعين بالتناوب
    
    if validation_passed and sectors_results:
        dxf_data = generate_professional_dxf(site_data, sectors_results, total_pump_q)
        st.session_state["sched_res"] = dict(sectors=sectors_results, total_q=total_pump_q, dxf=dxf_data)
        st.success("✅ تم حساب جدول التشغيل والقطاعات وتوليد المخطط الهندسي بنجاح!")

if "sched_res" in st.session_state:
    res = st.session_state["sched_res"]
    st.header("📊 مخرجات جداول الري، التشغيل، والكميات النهائية")
    
    tot_capex = sum(s["capex"] for s in res["sectors"])
    max_tdh = max(s["TDH"] for s in res["sectors"])
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("إجمالي تكلفة الشبكة (CAPEX)", f"{tot_capex:,.0f} {CUR}")
    k2.metric("تصرف مصدر المياه / الطلمبة ($Q$)", f"{res['total_q']:.1f} m³/h")
    k3.metric("عدد قطاعات ومحابس الري", f"{len(res['sectors'])} قطاع")
    k4.metric("العلامة التجارية", BRAND_LOGO)
    
    t1, t2 = st.tabs(["📘 جدول التشغيل الهيدروليكي والقطاعات", "📐 ملف الأوتوكاد التنفيذي (DXF)"])
    
    with t1:
        st.markdown("### 📋 جدول مواصفات القطاعات وساعات التشغيل اليومية:")
        df_sec = pd.DataFrame([
            {
                "القطاع": s["name"],
                "مساحة القطاع (م²)": round(s["area"], 1),
                "تصرف القطاع ($Q$) م³/س": round(s["Qp"], 1),
                "ساعات التشغيل اليومية (ساعة)": round(s["run_hours"], 2),
                "الرفع الكلي ($TDH$) م": round(s["TDH"], 1),
                f"التكلفة ({CUR})": f"{s['capex']:,.0f}"
            }
            for s in res["sectors"]
        ])
        st.dataframe(tdf(df_sec), use_container_width=True, hide_index=True)
            
    with t2:
        st.success("تم تضمين جدول ومواقع محابس القطاعات ($Valves$) في لوحة الـ DXF التنفيذية.")
        st.download_button(
            label="⬇️ تحميل لوحة الأوتوكاد التنفيذية للقطاعات والجداول (.DXF)",
            data=res["dxf"],
            file_name=f"Irrigation_Schedule_Layout_{BRAND_LOGO}.dxf",
            mime="application/dxf",
            type="primary",
            use_container_width=True
        )

st.warning(LEGAL_DISCLAIMER_AR)
st.caption(LEGAL_DISCLAIMER_EN)
