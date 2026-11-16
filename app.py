import io, math, tempfile
import numpy as np
import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

if "project" not in st.session_state: st.session_state.project = None
if "zones" not in st.session_state: st.session_state.zones = []
if "designed_results" not in st.session_state: st.session_state.designed_results = None

# ==========================================
# 1. قواعد البيانات
# ==========================================
AREA_UNITS = {"Feddan": 4200.0, "Hectare": 10000.0, "Acre": 4047.0, "Dunam": 1000.0, "m²": 1.0}
COUNTRY_INDEX = {"EG":1.0, "SA":1.35, "AE":1.4, "GR":1.2, "US":1.8, "EU":1.5, "INTL":1.0}
SOILS = {"Sandy":80, "Loamy Sand":110, "Sandy Loam":140, "Loam":170, "Clay Loam":190, "Clay":210}
LANDSCAPE_MEDIA = {"Prepared Soil":150, "Imported Topsoil":140, "Sand-Soil Mix":110, "Peat Mix":180, "Turf Base":100}

CROPS = {
    "Wheat":{"kc":1.10,"zr":1.0,"cat":"field","ar":"قمح"},"Maize":{"kc":1.15,"zr":1.0,"cat":"field","ar":"ذرة"},"Rice":{"kc":1.20,"zr":0.6,"cat":"field","ar":"أرز"},"Barley":{"kc":1.05,"zr":1.0,"cat":"field","ar":"شعير"},"Alfalfa":{"kc":1.05,"zr":1.5,"cat":"field","ar":"برسيم"},"Cotton":{"kc":1.15,"zr":1.0,"cat":"field","ar":"قطن"},
    "Tomato":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"طماطم"},"Potato":{"kc":1.10,"zr":0.5,"cat":"veg","ar":"بطاطس"},"Pepper":{"kc":1.00,"zr":0.5,"cat":"veg","ar":"فلفل"},"Cucumber":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"خيار"},"Eggplant":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"باذنجان"},"Onion":{"kc":1.05,"zr":0.4,"cat":"veg","ar":"بصل"},"Lettuce":{"kc":0.95,"zr":0.3,"cat":"veg","ar":"خس"},"Watermelon":{"kc":1.05,"zr":1.0,"cat":"veg","ar":"بطيخ"},"Strawberry":{"kc":1.00,"zr":0.3,"cat":"veg","ar":"فراولة"},
    "Olive":{"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"},"Citrus":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},"Mango":{"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"},"Date Palm":{"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل"},"Grape":{"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"},"Apple":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"تفاح"},"Pomegranate":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"رمان"},"Avocado":{"kc":0.90,"zr":0.8,"cat":"orchard","ar":"أفوكادو"},
    "Turf Bermuda":{"kc":0.80,"zr":0.3,"cat":"turf","ar":"نجيل"},"Bougainvillea":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"جهنمية"},"Ficus":{"kc":0.70,"zr":1.0,"cat":"tree","ar":"فيكس"},"Rose":{"kc":0.85,"zr":0.4,"cat":"flower","ar":"ورد"}
}

PROJECT_CROP_GROUPS = {
    "Agricultural": {"🌾 Field":["Wheat","Maize","Rice","Barley","Alfalfa","Cotton"], "🥬 Veg":["Tomato","Potato","Pepper","Cucumber","Eggplant","Onion","Lettuce","Watermelon","Strawberry"], "🍊 Orchards":["Olive","Citrus","Mango","Date Palm","Grape","Apple","Pomegranate","Avocado"]},
    "Landscape": {"🌿 Turf":["Turf Bermuda"], "🌳 Shrubs":["Bougainvillea"], "🌴 Trees":["Ficus"], "🌸 Flowers":["Rose"]}
}

TREE_CROPS = {"Olive","Citrus","Mango","Date Palm","Grape","Apple","Pomegranate","Avocado"}
CANOPY = {"Olive":0.70, "Date Palm":0.80, "Mango":0.90, "Citrus":0.85, "Grape":0.75, "Apple":0.85, "Pomegranate":0.80, "Avocado":0.90}
P_ALLOW = {"field":0.50,"veg":0.35,"orchard":0.55,"turf":0.50,"shrub":0.45,"tree":0.50,"flower":0.40}
IRR_SYSTEMS = {"drip":{"ar":"تنقيط","eff":0.90,"p":15},"micro":{"ar":"ميكرو","eff":0.85,"p":20},"sprinkler":{"ar":"رشاش","eff":0.75,"p":25}}

REGULATIONS = {
    "EG": {"name":"مصر","max_h":10,"eff":0.7,"banned":["surface"]}, "SA": {"name":"السعودية","max_h":16,"eff":0.75,"banned":["surface"]},
    "AE": {"name":"الإمارات","max_h":14,"eff":0.75,"banned":["surface"]}, "GR": {"name":"اليونان","max_h":14,"eff":0.7,"banned":[]},
    "INTL": {"name":"دولي","max_h":24,"eff":0.6,"banned":[]}
}

PUMPS = [{"name":"Grundfos CR 5-10","Q":5,"H":90,"kw":2.2,"eff":65},{"name":"Grundfos CR 10-10","Q":10,"H":95,"kw":4.0,"eff":70},{"name":"Grundfos CR 15-8","Q":15,"H":80,"kw":5.5,"eff":72},{"name":"Lowara e-SV 22","Q":22,"H":75,"kw":7.5,"eff":75}]

# ==========================================
# 2. المحركات الحسابية
# ==========================================
def fetch_climate(lat, lon):
    try:
        import requests
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params={"latitude":lat,"longitude":lon,"start_date":"2023-07-01","end_date":"2023-08-31","daily":"et0_fao_evapotranspiration,temperature_2m_max"})
        d = r.json()["daily"]
        return {"eto":round(max([v for v in d["et0_fao_evapotranspiration"] if v is not None]+[5.5]),1), "temp":round(max([v for v in d["temperature_2m_max"] if v is not None]+[25]),1)}
    except: return {"eto":5.5, "temp":25.0}

def select_pipe(q, v=1.2):
    if q <= 0: return 16
    d = math.sqrt((4 * (q/3600.0)) / (math.pi * v)) * 1000
    for std in [16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 160, 200, 250, 300]:
        if std >= d: return std
    return 300

def hw(L, q, d):
    if q <= 0 or d <= 0: return 0
    return 10.67 * L * ((q/3600)**1.852) / ((140**1.852) * ((d/1000)**4.87))

def select_pump_best(q, h):
    best, score = None, 1e9
    for p in PUMPS:
        if p["Q"] >= q and p["H"] >= h:
            s = abs(p["Q"]-q) + abs(p["H"]-h)
            if s < score: score, best = s, p
    return best if best else PUMPS[-1]

def select_filter(wsrc):
    if wsrc == "Well": return "Media Filter"
    if wsrc == "Reclaimed": return "Disc Filter"
    return "Screen Filter"

def water_treatment(ec, ph, sar):
    rec = []
    if ec > 5: rec.append("Leaching (غسيل أملاح)")
    if ph > 8.2: rec.append("Acid Injection (حقن حامض)")
    if sar > 9: rec.append("Gypsum (إضافة جبس)")
    return rec

def calc_uniformity(op_p, hf_lat):
    p_end = max(1.0, op_p - hf_lat)
    p_avg = op_p - (hf_lat / 2)
    eu = 100 * math.sqrt(p_end / p_avg) if p_avg > 0 else 0
    return round(eu, 1)

def calc_npv(capex, annual_cf, years, rate):
    return round(-capex + sum(annual_cf / ((1 + rate)**t) for t in range(1, years+1)), 2)

def calc_irr(capex, annual_cf, years):
    low, high = -0.99, 1.0
    for _ in range(100):
        mid = (low + high) / 2
        npv = -capex + sum(annual_cf / ((1+mid)**t) for t in range(1, years+1))
        if abs(npv) < 1e-4: return round(mid * 100, 2)
        if npv > 0: low = mid
        else: high = mid
    return round(mid * 100, 2)

def calc_lcc(capex, opex, years, rate):
    return round(capex + sum(opex / ((1 + rate)**t) for t in range(1, years+1)), 2)

def design_zone(z, proj):
    c = CROPS[z["crop"]]
    eff = IRR_SYSTEMS[z["system"]]["eff"]
    taw = SOILS.get(z.get("soil"), 140) if proj["project_type"] == "Agricultural" else LANDSCAPE_MEDIA.get(z.get("media"), 150)
    etc = proj["eto"] * c["kc"]
    max_i = 3 if c["cat"] in ("veg","flower") else 7 if c["cat"] in ("orchard","tree") else 5
    interval = max(1, min(int(round((P_ALLOW[c["cat"]]*taw*c["zr"])/etc if etc>0 else max_i)), max_i))
    
    area = z["area_val"] * AREA_UNITS[z["area_unit"]]
    vol = ((etc * interval) / eff) * area / 1000
    
    # [التعديل الجوهري]: التفريق بين الأشجار والخضروات في عدد المنقطات
    if z["crop"] in TREE_CROPS:
        # مساحة الشجرة = مسافة الشجرة × مسافة الصف
        tree_area = z.get("esp", 5.0) * z.get("lsp", 6.0)
        num_trees = int(area / tree_area)
        emitters = num_trees * 2 # منقطين لكل شجرة (افتراضي)
    else:
        # مساحة المنقط = مسافة المنقط × مسافة الخرطوم
        emitters = int(area / (z.get("esp",0.3) * z.get("lsp",0.8)))
        
    q_m3h = (emitters * z.get("q",4.0)) / 1000
    dur = vol / q_m3h if q_m3h>0 else 0
    
    L_lat = math.sqrt(area)
    d_lat = select_pipe(q_m3h / max(1, int(L_lat/z.get("lsp",0.8))), 0.8)
    d_sub = select_pipe(q_m3h, 1.2)
    
    hf_lat = hw(L_lat, q_m3h, d_lat)
    op_p = IRR_SYSTEMS[z["system"]]["p"]
    eu = calc_uniformity(op_p, hf_lat)
    tdh = (proj.get("elev",0) + proj.get("suction",2) + hw(L_lat*1.5, q_m3h, d_sub) + op_p + 5) * 1.15
    
    water_tree = None
    if z["crop"] in TREE_CROPS:
        daily = etc * (z.get("esp",5)*z.get("lsp",6)) * CANOPY.get(z["crop"], 1.0)
        water_tree = {"daily": round(daily,1), "event": round(daily*interval,1)}
        
    return {**z, "etc":etc, "interval":interval, "vol":vol, "q_m3h":q_m3h, "dur":dur, "d_sub":d_sub, "d_lat":d_lat, "tdh":tdh, "water_tree":water_tree, "eu": eu, "treatment": water_treatment(proj["ec"], proj["ph"], proj["sar"])}

def compute_boq(proj, zones, total_h):
    idx = COUNTRY_INDEX.get(proj["country"], 1.0)
    rows = []
    peak_q = max(z["q_m3h"] for z in zones) if zones else 0
    pump = select_pump_best(peak_q, max(z["tdh"] for z in zones) if zones else 50)
    
    rows.append(("Pump & Motor", f"{pump['name']} ({pump['kw']} kW)", 15000 * (pump['kw']/2) * idx))
    rows.append(("Controller", "Auto Panel", 5000 * idx))
    tank = sum(z['vol']/z['interval'] for z in zones) * 1.2
    rows.append(("Water Tank", f"{tank:.1f} m³", tank * 2000 * idx))
    if peak_q > 30: rows.append(("Pressure Regulator", "1 Unit", 3500 * idx))
    rows.append(("Main Pipe", f"Ø{select_pipe(peak_q)}mm", 100 * 80.0 * idx))
    
    for z in zones:
        rows.append((f"Zone {z['name']} - Sub", f"Ø{z['d_sub']}mm", 50 * 45.0 * idx))
        rows.append((f"Zone {z['name']} - Lat", f"Ø{z['d_lat']}mm", 200 * 6.0 * idx))
        rows.append((f"Zone {z['name']} - Valve", "1", 2500.0 * idx))
        
    rows.append((f"Filter ({proj['filter']})", proj['filter'], 15000 * idx))
    subtotal = sum(r[2] for r in rows)
    rows.append(("Fittings (10%)", "-", subtotal * 0.1))
    capex = subtotal * 1.1
    opex = ((pump['kw'] * total_h * 365) / (pump['eff']/100) * 0.15 * idx) + (capex * 0.03)
    return rows, capex, opex, pump, tank

# ==========================================
# 3. دوال التصدير
# ==========================================
def build_pdf(proj, res):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        elements = [Paragraph(f"Project: {proj['name']}", getSampleStyleSheet()['Title']), Spacer(1, 12)]
        elements.append(Paragraph(f"<b>Climate:</b> ETo {proj['eto']} mm/d | Temp {proj['temp']} C", getSampleStyleSheet()['Normal']))
        elements.append(Paragraph(f"<b>Water:</b> EC {proj['ec']}, pH {proj['ph']}, SAR {proj['sar']}", getSampleStyleSheet()['Normal']))
        elements.append(Paragraph(f"<b>Pump:</b> {res['pump']['name']} ({res['pump']['kw']} kW)", getSampleStyleSheet()['Normal']))
        elements.append(Spacer(1, 12))
        
        data = [["Zone", "Crop", "Flow (m3/h)", "Dur (h)", "EU (%)"]]
        for z in res['zones']: data.append([z['name'], z['crop'], f"{z['q_m3h']:.1f}", f"{z['dur']:.1f}", f"{z['eu']}"])
        t = Table(data); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        elements.append(t)
        doc.build(elements); buf.seek(0)
        return buf
    except Exception: return None

def build_dxf(res):
    try:
        import ezdxf
        doc = ezdxf.new("R2010"); msp = doc.modelspace()
        for l in ["MAIN", "PUMP", "TANK", "SUBMAIN"]: doc.layers.add(l)
        msp.add_lwpolyline([(0,0),(100,0),(100,80),(0,80),(0,0)], dxfattribs={"layer":"MAIN"})
        msp.add_circle((50, -10), 2, dxfattribs={"layer":"PUMP"})
        msp.add_circle((0, 0), 3, dxfattribs={"layer":"TANK"})
        y = 0
        for z in res['zones']:
            msp.add_line((0, y), (100, y), dxfattribs={"layer":"SUBMAIN"})
            y += 80 / len(res['zones'])
        
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            path = tmp.name
        doc.saveas(path)
        with open(path, "rb") as f:
            return io.BytesIO(f.read())
    except Exception: return None

def build_plot_image(res):
    try:
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        y = 0
        for z in res['zones']:
            h = 80 / len(res['zones'])
            ax.add_patch(Rectangle((0, y), 100, h, fill=True, alpha=0.2, ec="black"))
            ax.text(50, y+h/2, f"{z['name']}: {CROPS[z['crop']]['ar']}", ha='center', va='center', bbox=dict(fc='white'))
            y += h
        
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 80)
        ax.axis("off")
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception: return None

# ==========================================
# 4. واجهة المستخدم
# ==========================================
def main():
    st.sidebar.title("💧 Smart Irrigation")
    tabs = st.tabs(["1. Setup & Water", "2. Zones", "3. Design & EU", "4. Finance & BOQ", "5. Exports"])

    # --- Tab 1 ---
    with tabs[0]:
        st.subheader("Project Setup")
        c1, c2 = st.columns(2)
        with c1: pname = st.text_input("Name", "My Farm")
        with c2: country = st.selectbox("Country", list(REGULATIONS.keys()), format_func=lambda x: REGULATIONS[x]["name"])
        
        st.markdown("---")
        st.subheader("Location")
        lc1, lc2 = st.columns(2)
        with lc1: lat = st.number_input("Latitude", 20.0, 40.0, 30.0)
        with lc2: lon = st.number_input("Longitude", 20.0, 40.0, 31.0)
        
        eto, temp = 5.5, 25.0
        if st.button("🌤️ Fetch Climate"):
            clim = fetch_climate(lat, lon)
            st.session_state["eto"], st.session_state["temp"] = clim["eto"], clim["temp"]
            st.success(f"Fetched: ETo {clim['eto']} mm/d")
            
        eto = st.session_state.get("eto", 5.5)
        temp = st.session_state.get("temp", 25.0)
        
        st.markdown("---")
        st.subheader("Water Quality & Source")
        wq1, wq2, wq3 = st.columns(3)
        with wq1: ec = st.number_input("EC (dS/m)", 0.0, 20.0, 2.0)
        with wq2: ph = st.number_input("pH", 4.0, 10.0, 7.5)
        with wq3: sar = st.number_input("SAR", 0.0, 30.0, 5.0)
        
        wsrc = st.selectbox("Water Source", ["Nile", "Well", "Reclaimed"])
        filt = select_filter(wsrc)
        st.info(f"🤖 Auto-Selected Filter: **{filt}** based on source.")
        
        st.markdown("---")
        st.subheader("Financial Inputs")
        fc1, fc2, fc3 = st.columns(3)
        with fc1: discount_rate = st.number_input("Discount Rate (%)", 1.0, 30.0, 10.0) / 100
        with fc2: lifespan = st.number_input("Lifespan (Years)", 1, 30, 10)
        with fc3: revenue = st.number_input("Annual Revenue (EGP)", 0.0, 10000000.0, 100000.0, step=10000.0)

        st.session_state.project = {"name": pname, "country": country, "eto": eto, "temp": temp, "ec": ec, "ph": ph, "sar": sar, "wsrc": wsrc, "filter": filt, "slope": 0.0, "pc": "PC Dripper", "area_unit": "Feddan", "elev": 0.0, "suction": 2.0, "rate": discount_rate, "years": lifespan, "revenue": revenue, "project_type": "Agricultural"}

    proj = st.session_state.get("project")
    if proj is None: st.stop()

    # --- Tab 2 ---
    with tabs[1]:
        st.subheader("Zones Manager")
        if st.button("➕ Add Zone"):
            st.session_state.zones.append({"name":f"Z{len(st.session_state.zones)+1}", "crop":"Tomato", "area_val":1.0, "area_unit":proj["area_unit"], "system":"drip", "q":4.0, "esp":0.3, "lsp":0.8, "soil":"Sandy Loam"})
            st.rerun()
            
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']} ({CROPS[z['crop']]['ar']})", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: z["name"] = st.text_input("Name", z["name"], key=f"n{i}")
                grp = PROJECT_CROP_GROUPS[proj["project_type"]]
                with c2: grp_sel = st.selectbox("Group", list(grp.keys()), key=f"g{i}")
                with c3: 
                    z["crop"] = st.selectbox("Crop", grp[grp_sel], format_func=lambda x: CROPS[x]['ar'], key=f"c{i}")
                    z["q"] = 8 if z["crop"] in ["Olive", "Date Palm"] else 2 if z["crop"] in ["Tomato", "Pepper"] else 4
                
                c1, c2, c3 = st.columns(3)
                with c1: z["area_val"] = st.number_input("Area (Feddan)", value=z["area_val"], key=f"a{i}")
                with c2: 
                    # لو شجرة نطلب مسافات الأشجار، لو خضار نطلب مسافات المنقطات
                    if z["crop"] in TREE_CROPS:
                        z["esp"] = st.number_input("Tree Spacing (m)", value=z.get("esp", 5.0), key=f"e{i}", help="مسافة الشجرة عن الشجرة")
                    else:
                        z["esp"] = st.number_input("Emitter Spacing (m)", value=z.get("esp", 0.3), key=f"e{i}", help="مسافة المنقط")
                with c3: 
                    if z["crop"] in TREE_CROPS:
                        z["lsp"] = st.number_input("Row Spacing (m)", value=z.get("lsp", 6.0), key=f"l{i}", help="مسافة الصف عن الصف")
                    else:
                        z["lsp"] = st.number_input("Lateral Spacing (m)", value=z.get("lsp", 0.8), key=f"l{i}", help="مسافة الخرطوم")
                
                if st.button("🗑️ Delete", key=f"d{i}"):
                    st.session_state.zones.pop(i); st.rerun()

        if st.button("🚀 Calculate Design", type="primary"):
            if not st.session_state.zones: st.error("Add zones first.")
            else:
                try:
                    designed = [design_zone(z, proj) for z in st.session_state.zones]
                    total_flow = sum(z["q_m3h"] for z in designed)
                    strategy = "Parallel" if total_flow <= 40.0 else "Sequential"
                    total_h = max(z["dur"] for z in designed) if strategy == "Parallel" else sum(z["dur"] for z in designed) + (len(designed)*0.25)
                    
                    boq, capex, opex, pump, tank = compute_boq(proj, designed, total_h)
                    annual_cf = proj["revenue"] - opex
                    
                    res = {
                        "zones": designed, "hours": total_h, "strategy": strategy, "boq": boq, "capex": capex, "opex": opex, "pump": pump, "tank": tank,
                        "npv": calc_npv(capex, annual_cf, proj["years"], proj["rate"]),
                        "irr": calc_irr(capex, annual_cf, proj["years"]),
                        "lcc": calc_lcc(capex, opex, proj["years"], proj["rate"])
                    }
                    st.session_state.designed_results = res
                    st.success("Calculated! Scroll down or click the next tabs.")
                except Exception as e:
                    st.error(f"Error: {e}")

    res = st.session_state.get("designed_results")

    # --- Tab 3 ---
    with tabs[2]:
        if not res: st.info("Go to Zones and calculate.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Hours", f"{res['hours']:.1f} h")
            c2.metric("Pump", res['pump']['name'])
            c3.metric("Tank", f"{res['tank']:.1f} m³")
            c4.metric("Strategy", res['strategy'])
            
            for z in res['zones']:
                st.markdown(f"**{z['name']}:** Flow {z['q_m3h']:.1f} m³/h | Duration {z['dur']:.1f}h")
                color = "green" if z['eu'] >= 80 else "red"
                st.markdown(f"📊 **EU (انتظامية الري):** :{color}[{z['eu']}%]")
                for t in z['treatment']: st.warning(f"💧 {t}")

    # --- Tab 4 ---
    with tabs[3]:
        if not res: st.info("Calculate design first.")
        else:
            st.subheader("💰 Financial Analysis")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CAPEX", f"{res['capex']:,.0f} EGP")
            c2.metric("OPEX", f"{res['opex']:,.0f} EGP")
            c3.metric("NPV", f"{res['npv']:,.0f} EGP")
            c4.metric("IRR", f"{res['irr']}%")
            st.metric("LCC", f"{res['lcc']:,.0f} EGP")
            
            st.dataframe(pd.DataFrame(res['boq'], columns=["Item", "Spec", "Cost"]))

    # --- Tab 5 ---
    with tabs[4]:
        if not res: st.info("Calculate design first.")
        else:
            st.subheader("📐 Exports")
            c1, c2 = st.columns(2)
            with c1:
                pdf = build_pdf(proj, res)
                if pdf: st.download_button("⬇️ Download PDF", pdf, file_name="report.pdf")
                else: st.warning("PDF issue.")
            with c2:
                dxf = build_dxf(res)
                if dxf: st.download_button("⬇️ Download DXF", dxf, file_name="design.dxf")
                else: st.warning("DXF issue.")
            
            img_buf = build_plot_image(res)
            if img_buf:
                st.image(img_buf, caption="مخطط الزونات", use_column_width=True)
            else:
                st.warning("Plot issue.")

if __name__ == "__main__":
    main()
