import re, io, math, json, datetime
import numpy as np
import pandas as pd
import streamlit as st

try: import ezdxf; EZDXF_OK = True
except: EZDXF_OK = False
try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.lines import Line2D
    MPL_OK = True
except: MPL_OK = False
try: import requests; REQUESTS_OK = True
except: REQUESTS_OK = False
try: import simplekml; KML_OK = True
except: KML_OK = False
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    PDF_OK = True
except: PDF_OK = False
try: from shapely.geometry import Polygon; SHAPELY_OK = True
except: SHAPELY_OK = False

def T(en, ar): return en if st.session_state.get("lang", "ar") == "en" else ar

# ============================================================
# 1. CONSTANTS & DATABASES
# ============================================================
AREA_UNITS = {"Feddan": 4200.0, "Hectare": 10000.0, "Acre": 4047.0, "Dunam": 1000.0, "m²": 1.0}
CURRENCIES = {"EGP":1.0, "USD":50.0, "EUR":54.0, "SAR":13.3, "AED":13.6, "GBP":63.0}
COUNTRY_INDEX = {"EG":1.0, "SA":1.35, "AE":1.4, "GR":1.2, "US":1.8, "EU":1.5, "INTL":1.0}

SOILS = {"Sandy":80, "Loamy Sand":110, "Sandy Loam":140, "Loam":170, "Clay Loam":190, "Clay":210}
LANDSCAPE_MEDIA = {"Prepared Soil":150, "Imported Topsoil":140, "Sand-Soil Mix":110, "Peat Mix":180, "Turf Base":100}
NURSERY_MEDIA = {"Peat+Perlite":200, "Coco Peat":190, "Soil Mix":160, "Hydroponic":150}

CROPS = {
    "Wheat":{"kc":1.10,"zr":1.0,"cat":"field","ar":"قمح"},"Maize":{"kc":1.15,"zr":1.0,"cat":"field","ar":"ذرة"},"Rice":{"kc":1.20,"zr":0.6,"cat":"field","ar":"أرز"},"Barley":{"kc":1.05,"zr":1.0,"cat":"field","ar":"شعير"},"Alfalfa":{"kc":1.05,"zr":1.5,"cat":"field","ar":"برسيم"},"Cotton":{"kc":1.15,"zr":1.0,"cat":"field","ar":"قطن"},
    "Tomato":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"طماطم"},"Potato":{"kc":1.10,"zr":0.5,"cat":"veg","ar":"بطاطس"},"Pepper":{"kc":1.00,"zr":0.5,"cat":"veg","ar":"فلفل"},"Cucumber":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"خيار"},"Eggplant":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"باذنجان"},"Onion":{"kc":1.05,"zr":0.4,"cat":"veg","ar":"بصل"},"Lettuce":{"kc":0.95,"zr":0.3,"cat":"veg","ar":"خس"},"Watermelon":{"kc":1.05,"zr":1.0,"cat":"veg","ar":"بطيخ"},"Strawberry":{"kc":1.00,"zr":0.3,"cat":"veg","ar":"فراولة"},
    "Olive":{"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"},"Citrus":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},"Mango":{"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"},"Date Palm":{"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل"},"Grape":{"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"},"Apple":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"تفاح"},"Pomegranate":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"رمان"},"Avocado":{"kc":0.90,"zr":0.8,"cat":"orchard","ar":"أفوكادو"},
    "Turf Bermuda":{"kc":0.80,"zr":0.3,"cat":"turf","ar":"نجيل برمودا"},"Bougainvillea":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"جهنمية"},"Ficus":{"kc":0.70,"zr":1.0,"cat":"tree","ar":"فيكس"},"Rose":{"kc":0.85,"zr":0.4,"cat":"flower","ar":"ورد"},"Lavender":{"kc":0.65,"zr":0.4,"cat":"flower","ar":"لافندر"},"Potted":{"kc":1.0,"zr":0.3,"cat":"pot","ar":"أصص"}
}

PROJECT_CROP_GROUPS = {
    "Agricultural": {"🌾 Field":["Wheat","Maize","Rice","Barley","Alfalfa","Cotton"], "🥬 Veg":["Tomato","Potato","Pepper","Cucumber","Eggplant","Onion","Lettuce","Watermelon","Strawberry"], "🍊 Orchards":["Olive","Citrus","Mango","Date Palm","Grape","Apple","Pomegranate","Avocado"]},
    "Landscape": {"🌿 Turf":["Turf Bermuda"], "🌳 Shrubs":["Bougainvillea"], "🌴 Trees":["Ficus"], "🌸 Flowers":["Rose","Lavender"]},
    "Greenhouse": {"🍅 GH Veg":["Tomato","Cucumber","Pepper"]},
    "Nursery": {"🪴 Potted":["Potted"]}
}
TREE_CROPS = {"Olive","Citrus","Mango","Date Palm","Grape","Apple","Pomegranate","Avocado"}
P_ALLOW = {"field":0.50,"veg":0.35,"orchard":0.55,"turf":0.50,"shrub":0.45,"tree":0.50,"flower":0.40,"pot":0.35}
IRR_SYSTEMS = {"drip":{"ar":"تنقيط","eff":0.90,"p":10},"micro":{"ar":"ميكرو","eff":0.85,"p":15},"bubbler":{"ar":"بابلر","eff":0.85,"p":12},"sprinkler":{"ar":"رشاش","eff":0.75,"p":25},"surface":{"ar":"غمر","eff":0.55,"p":2}}

REGULATIONS = {
    "INTL": {"name":"دولي","max_h":24,"eff":0.6,"banned":[],"ec":10,"sar":15},
    "EG": {"name":"مصر","max_h":10,"eff":0.7,"banned":["surface"],"ec":5,"sar":9},
    "SA": {"name":"السعودية","max_h":16,"eff":0.75,"banned":["surface"],"ec":5,"sar":9},
    "AE": {"name":"الإمارات","max_h":14,"eff":0.75,"banned":["surface"],"ec":5,"sar":9},
    "GR": {"name":"اليونان","max_h":14,"eff":0.7,"banned":[],"ec":6,"sar":10},
    "EU": {"name":"أوروبا","max_h":24,"eff":0.8,"banned":[],"ec":6,"sar":10},
    "US": {"name":"أمريكا","max_h":24,"eff":0.7,"banned":[],"ec":8,"sar":12},
}

FILTERS = ["Screen Filter","Disc Filter","Media Filter","Hydrocyclone"]
FILTER_AR = {"Screen Filter":"شبكي","Disc Filter":"ديسكات","Media Filter":"رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}

PUMPS = [
    {"name":"Grundfos CR 5-10","Q":5,"H":90,"kw":2.2,"eff":65},
    {"name":"Grundfos CR 10-10","Q":10,"H":95,"kw":4.0,"eff":70},
    {"name":"Grundfos CR 15-8","Q":15,"H":80,"kw":5.5,"eff":72},
    {"name":"Lowara e-SV 22","Q":22,"H":75,"kw":7.5,"eff":75},
    {"name":"Ebara EVMS 15","Q":15,"H":85,"kw":5.5,"eff":70},
]

DEFAULT_PRICES = {"main":80.0,"sub":45.0,"lat":6.0,"drip":3.0,"control":2500.0,"flush":450.0,"arv":1800.0,"acid":12000.0,"treat":20000.0,"pump_base":15000.0}

# ============================================================
# 2. AI & API ENGINES
# ============================================================
def parse_request(text):
    out = {"area":None, "unit":"Feddan", "crop":None, "loc":None, "source":None, "country":"EG"}
    if not text: return out
    m = re.search(r"(\d+(?:\.\d+)?)\s*(feddan|فدان|ha|hectare|هكتار|acre)", text, re.I)
    if m:
        out["area"] = float(m.group(1))
        if m.group(2).lower() in ("ha","hectare","هكتار"): out["unit"]="Hectare"
        if m.group(2).lower()=="acre": out["unit"]="Acre"
    tl = text.lower()
    for c in CROPS:
        if c.lower() in tl or CROPS[c]["ar"] in text: out["crop"]=c; break
    if "مطروح" in text or "matrouh" in tl: out["loc"]="Matrouh"; out["country"]="EG"
    elif "اليونان" in text or "greece" in tl: out["loc"]="Greece"; out["country"]="GR"
    elif "السعودية" in text or "saudi" in tl: out["loc"]="Saudi"; out["country"]="SA"
    elif "الامارات" in text or "uae" in tl: out["loc"]="UAE"; out["country"]="AE"
    if "well" in tl or "بئر" in text: out["source"]="Well"
    elif "nile" in tl or "نيل" in text: out["source"]="Nile"
    return out

def fetch_climate(lat, lon):
    if not REQUESTS_OK: return {"eto":5.5, "rain":0.0, "temp":25.0, "hum":50.0, "wind":2.0}
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=15, params={"latitude":lat,"longitude":lon,"start_date":"2023-07-01","end_date":"2023-08-31","daily":"et0_fao_evapotranspiration,precipitation_sum,temperature_2m_max,relative_humidity_2m_max,wind_speed_10m_max"})
        d = r.json()["daily"]
        return {"eto":round(max([v for v in d["et0_fao_evapotranspiration"] if v is not None]+[5.5]),1), "rain":round(np.mean([v for v in d["precipitation_sum"] if v is not None]+[0]),1), "temp":round(max([v for v in d["temperature_2m_max"] if v is not None]+[25]),1), "hum":round(np.mean([v for v in d["relative_humidity_2m_max"] if v is not None]+[50]),1), "wind":round(np.mean([v for v in d["wind_speed_10m_max"] if v is not None]+[10])/3.6,1)}
    except: return {"eto":5.5, "rain":0.0, "temp":25.0, "hum":50.0, "wind":2.0}

def fetch_soil(lat, lon):
    if not REQUESTS_OK: return "Sandy Loam"
    try:
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query", params=[("lon",lon),("lat",lat),("property","clay"),("property","sand"),("depth","0-30cm")], timeout=10)
        vals = {L["name"]: L["depths"][0]["values"]["mean"]/10.0 for L in r.json()["properties"]["layers"] if L["depths"][0]["values"]["mean"]}
        s, c = vals.get("sand", 50), vals.get("clay", 20)
        if c>=40: return "Clay"
        if c>=25 and s<=45: return "Clay Loam"
        if s>=85: return "Sandy"
        if s>=70: return "Loamy Sand"
        if s>=50: return "Sandy Loam"
        return "Loam"
    except: return "Sandy Loam"

# ============================================================
# 3. MATH & HYDRAULIC ENGINES
# ============================================================
def poly_area(coords):
    if len(coords)<3: return 0
    lat0=sum(c[0] for c in coords)/len(coords)
    pts=[(c[1]*111320*math.cos(math.radians(lat0)), c[0]*111320) for c in coords]
    s=sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
    return abs(s)/2

def poly_centroid(coords):
    if len(coords)<3: return 30.0, 30.0
    lat0=sum(c[0] for c in coords)/len(coords)
    mlat,mlon=111320,111320*math.cos(math.radians(lat0))
    pts=[(c[1]*mlon,c[0]*mlat) for c in coords]
    a=cx=cy=0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]
        cr=x1*y2-x2*y1; a+=cr; cx+=(x1+x2)*cr; cy+=(y1+y2)*cr
    a/=2
    return (round(cy/(6*a)/mlat,6), round(cx/(6*a)/mlon,6)) if a!=0 else (30.0, 30.0)

def select_pipe_diameter(q_m3h, v_target=1.2):
    if q_m3h <= 0: return 16
    d_m = math.sqrt((4 * (q_m3h/3600.0)) / (math.pi * v_target))
    for d in [16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 160, 200]:
        if d >= d_m * 1000: return d
    return 200

def hazen_williams(L, q_m3h, d_mm, C=140):
    if q_m3h <= 0 or d_mm <= 0: return 0
    return 10.67 * L * ((q_m3h/3600)**1.852) / ((C**1.852) * ((d_mm/1000)**4.87))

def choose_system(cat, ec, slope, wind):
    if ec > 5 or slope > 5: return "drip"
    if cat in ["orchard", "veg", "field"]: return "drip" if cat != "field" else "sprinkler"
    if cat == "turf": return "sprinkler"
    if wind > 4.5: return "drip"
    return "micro"

def select_pump(q_m3h, tdh):
    for p in PUMPS:
        if p["Q"] >= q_m3h and p["H"] >= tdh: return p
    return PUMPS[-1]

def water_treatment(ec, ph, sar):
    t = []
    if ec > 5: t.append("Leaching (غسيل أملاح)")
    if ph > 8.2: t.append("Acid Injection (حقن حامض)")
    if sar > 9: t.append("Gypsum (جبس)")
    return t

def derive_defaults(wsrc, country, ptype, pipe_inch):
    d = {}
    if wsrc == "Nile": d.update({"ec":0.8,"ph":7.8,"sar":2.5,"filter":"Media Filter"})
    elif wsrc == "Well": d.update({"ec":2.5,"ph":8.0,"sar":4.5,"filter":"Media Filter"})
    elif wsrc == "Reclaimed": d.update({"ec":1.8,"ph":7.2,"sar":6.0,"filter":"Disc Filter"})
    else: d.update({"ec":0.6,"ph":7.2,"sar":2.0,"filter":"Screen Filter"})
    q_map = {"1.5\"": 8.0, "2\"": 15.0, "3\"": 30.0, "4\"": 50.0, "6\"": 100.0, "Canal": 200.0}
    d["q_source"] = q_map.get(pipe_inch, 40.0)
    d["curr"] = {"EG":"EGP", "SA":"SAR", "AE":"AED", "GR":"EUR"}.get(country, "USD")
    d["fert"] = "Venturi" if ptype in ["Agricultural", "Landscape"] else "None"
    return d

# ============================================================
# 4. DESIGN & SCHEDULING
# ============================================================
def design_zone(z, proj):
    c = CROPS[z["crop"]]
    eff = IRR_SYSTEMS[z["system"]]["eff"]
    taw = SOILS.get(z.get("soil"), 140) if proj["project_type"] in ["Agricultural","Greenhouse"] else LANDSCAPE_MEDIA.get(z.get("media"), 150)
    raw_mm = P_ALLOW[c["cat"]] * taw * c["zr"]
    etc = proj["eto"] * c["kc"]
    if proj["project_type"] == "Greenhouse": etc *= 0.7
    max_i = 3 if c["cat"] in ("veg","flower") else 7 if c["cat"] in ("orchard","tree") else 14 if c["cat"]=="succulent" else 5
    interval = max(1, min(int(round(raw_mm/etc if etc>0 else max_i)), max_i))
    area = z["area_val"] * AREA_UNITS[z["area_unit"]]
    vol = ((etc * interval) / eff) * area / 1000
    if z["system"] in ("drip","micro"):
        emitters = int(area / (z.get("esp",0.5) * z.get("lsp",0.8)))
        q_m3h = (emitters * z.get("q",2.0)) / 1000
    elif z["system"] == "sprinkler":
        emitters = int(area / (z.get("esp",12) * z.get("lsp",12)))
        q_m3h = (emitters * 1000) / 1000
    else:
        emitters = int(area / (z.get("esp",5) * z.get("lsp",6)))
        q_m3h = (emitters * 100) / 1000
    dur = vol / q_m3h if q_m3h>0 else 0
    d_lat = select_pipe_diameter(q_m3h / max(1, int(math.sqrt(area)/z.get("lsp",0.8))), v_target=0.8)
    d_sub = select_pipe_diameter(q_m3h, v_target=1.2)
    hf_sub = hazen_williams(math.sqrt(area)*2, q_m3h, d_sub)
    tdh = proj.get("elev",0) + proj.get("suction",2) + hf_sub + IRR_SYSTEMS[z["system"]]["p"] + 5
    water_tree = None
    if z["crop"] in TREE_CROPS:
        daily = etc * (z.get("esp",5)*z.get("lsp",6))
        water_tree = {"daily": round(daily,1), "event": round(daily*interval,1)}
    return {**z, "etc":etc, "raw_mm":raw_mm, "interval":interval, "vol":vol, "q_m3h":q_m3h, "dur":dur, "d_sub":d_sub, "d_lat":d_lat, "tdh":tdh, "water_tree":water_tree, "treat":water_treatment(proj["ec"], proj["ph"], proj["sar"])}

def build_schedule(zones, strategy, source_cap):
    if strategy == "sequential":
        cur = 5.0
        for z in zones:
            z["start"] = cur; z["end"] = cur + z["dur"]; cur = z["end"] + 0.25
        return zones, cur - 5.0
    else:
        timeline = []
        for z in sorted(zones, key=lambda x: -x["dur"]):
            found = False
            for t_int in range(0, 96):
                t = 5.0 + t_int*0.25
                overlap = sum(sl["flow"] for sl in timeline if sl["start"] < t + z["dur"] and sl["end"] > t)
                if overlap + z["q_m3h"] <= source_cap:
                    z["start"] = t; z["end"] = t + z["dur"]
                    timeline.append({"start": t, "end": z["end"], "flow": z["q_m3h"]})
                    found = True; break
            if not found:
                max_e = max((sl["end"] for sl in timeline), default=5.0)
                z["start"] = max_e + 0.25; z["end"] = z["start"] + z["dur"]
                timeline.append({"start": z["start"], "end": z["end"], "flow": z["q_m3h"]})
        return zones, max(z["end"] for z in zones) - 5.0

def check_compliance(proj, zones, total_h):
    reg = REGULATIONS[proj["country"]]
    issues = []
    if total_h > reg["max_h"]:
        issues.append(("error", f"⛔ ساعات التشغيل {total_h:.1f}h تتجاوز الحد المسموح {reg['max_h']}h"))
    for z in zones:
        if z["system"] in reg["banned"]:
            issues.append(("error", f"⛔ زونة {z['name']}: نظام {z['system']} ممنوع"))
    if proj["ec"] > reg["ec"]: issues.append(("error", f"⛔ ملوحة المياه {proj['ec']} تتجاوز الحد"))
    if proj["sar"] > reg["sar"]: issues.append(("error", f"⛔ SAR يتجاوز الحد"))
    return issues, reg

# ============================================================
# 5. BOQ, PLOT, EXPORTS
# ============================================================
def compute_boq(proj, zones, total_h):
    idx = COUNTRY_INDEX.get(proj["country"], 1.0)
    rows = []
    peak_q = max(z["q_m3h"] for z in zones) if zones else 0
    max_tdh = max(z["tdh"] for z in zones) if zones else 50
    pump = select_pump(peak_q, max_tdh)
    rows.append(("Pump & Motor", f"{pump['name']} ({pump['kw']} kW)", DEFAULT_PRICES["pump_base"] * (pump['kw']/2) * idx))
    rows.append(("Controller", "Auto Panel", 5000 * idx))
    rows.append(("Main Pipe", f"Ø{select_pipe_diameter(peak_q)}mm", 100 * DEFAULT_PRICES["main"] * idx))
    for z in zones:
        rows.append((f"Zone {z['name']} - Sub", f"Ø{z['d_sub']}mm", 50 * DEFAULT_PRICES["sub"] * idx))
        rows.append((f"Zone {z['name']} - Lat", f"Ø{z['d_lat']}mm", 200 * DEFAULT_PRICES["lat"] * idx))
        rows.append((f"Zone {z['name']} - Valve", "1", DEFAULT_PRICES["control"] * idx))
    total_area = sum(z["area_val"]*AREA_UNITS[z["area_unit"]] for z in zones)
    hydrants = max(1, int(total_area / 10000))
    rows.append(("Hydrants", f"{hydrants}", hydrants * 1500 * idx))
    rows.append(("Filter", FILTER_AR.get(proj["filter"],""), FILTER_PRICE.get(proj["filter"],0) * idx))
    rows.append(("Air/Flush Valves", "Set", 4 * DEFAULT_PRICES["arv"] * idx))
    if proj["ph"] > 8.2: rows.append(("Acid Injection", "1", DEFAULT_PRICES["acid"] * idx))
    if proj["ec"] > 5: rows.append(("Water Treatment", "1", DEFAULT_PRICES["treat"] * idx))
    subtotal = sum(r[2] for r in rows)
    rows.append(("Fittings (10%)", "-", subtotal * 0.1))
    total_capex = subtotal * 1.1
    kwh = (pump['kw'] * total_h * 365) / (pump['eff']/100)
    opex = (kwh * 0.15 * idx) + (total_capex * 0.03)
    return rows, total_capex, opex, pump

def build_pdf(proj, zones, boq, total_h, pump):
    if not PDF_OK: return None
    buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = [Paragraph(f"Engineering Report: {proj['name']}", getSampleStyleSheet()['Title']), Spacer(1,12)]
    elements.append(Paragraph(f"<b>Pump:</b> {pump['name']} ({pump['kw']} kW, Eff: {pump['eff']}%)", getSampleStyleSheet()['Normal']))
    elements.append(Paragraph(f"<b>Total Op Hours:</b> {total_h:.1f} h", getSampleStyleSheet()['Normal']))
    elements.append(Spacer(1,12))
    data = [["Zone", "Crop", "ETc", "Interval", "Vol(m3)", "Water/Tree"]]
    for z in zones:
        wt = f"{z['water_tree']['daily']} L/d" if z.get("water_tree") else "-"
        data.append([z['name'], z['crop'], f"{z['etc']:.1f}", f"{z['interval']}d", f"{z['vol']:.1f}", wt])
    t = Table(data); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.grey)]))
    elements.append(t); elements.append(Spacer(1,12))
    elements.append(Paragraph("<b>Bill of Quantities</b>", getSampleStyleSheet()['Heading2']))
    bdata = [["Item", "Cost"]] + [[r[0], f"{r[2]:,.0f}"] for r in boq]
    bt = Table(bdata); bt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
    elements.append(bt); doc.build(elements); buf.seek(0)
    return buf

def build_kml(proj):
    if not KML_OK or "poly" not in st.session_state or not st.session_state["poly"]: return None
    kml = simplekml.Kml(); kml.newpolygon(name=proj["name"], outerboundaryis=[(c[1], c[0]) for c in st.session_state["poly"]])
    return kml.kml()

def build_geojson(proj):
    if "poly" not in st.session_state or not st.session_state["poly"]: return None
    return json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[c[1],c[0]] for c in st.session_state["poly"]]]}}]})

def build_plot(proj, zones):
    fig, ax = plt.subplots(figsize=(10, 8))
    if "poly" in st.session_state and len(st.session_state["poly"]) >= 3 and SHAPELY_OK:
        poly = Polygon([(c[1], c[0]) for c in st.session_state["poly"]])
        x, y = poly.exterior.xy; ax.fill(x, y, alpha=0.1, fc='green', ec='black'); ax.plot(x, y, color='black', lw=2)
        minx, miny, maxx, maxy = poly.bounds; W, H = maxx-minx, maxy-miny
        for i, z in enumerate(zones):
            ax.plot([minx, maxx], [miny + (i/len(zones))*H]*2, color='green', lw=2, ls='--')
        ax.text((minx+maxx)/2, maxy, "Zones inside Polygon", ha='center', fontsize=12, bbox=dict(fc='white'))
    else:
        W = math.sqrt(sum(z["area_val"]*AREA_UNITS[z["area_unit"]] for z in zones))
        ax.add_patch(Rectangle((0,0), W, W*0.8, fill=False, lw=2)); ax.plot([W/2, W/2], [0, W*0.8], color="blue", lw=3)
    ax.legend(handles=[Line2D([0],[0], color='black', lw=2, label='Boundary'), Line2D([0],[0], color='green', lw=2, ls='--', label='Zones')], loc='upper right')
    ax.axis("off"); return fig

def build_dxf(proj, zones):
    if not EZDXF_OK: return None
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for l in ["MAIN","SUBMAIN","LATERAL","EMITTER","FILTER","FERTIGATION","AIR_RELEASE","FLUSH","CONTROL","HYDRANT","PUMP","TITLE"]:
        if l not in doc.layers: doc.layers.add(l)
    W = math.sqrt(sum(z["area_val"]*AREA_UNITS[z["area_unit"]] for z in zones))
    msp.add_lwpolyline([(0,0),(W,0),(W,W*0.8),(0,W*0.8),(0,0)], dxfattribs={"layer":"MAIN"})
    msp.add_circle((W/2, -5), 2, dxfattribs={"layer":"PUMP"}); msp.add_circle((W*0.1, W*0.1), 1, dxfattribs={"layer":"FILTER"})
    y = 0
    for z in zones:
        z_h = (W*0.8) * (z["area_val"]/sum(zz["area_val"] for zz in zones))
        msp.add_line((0,y), (W,y), dxfattribs={"layer":"SUBMAIN"}); msp.add_circle((W*0.9, y+z_h/2), 0.5, dxfattribs={"layer":"CONTROL"}); y += z_h
    buf = io.BytesIO(); doc.saveas(buf); buf.seek(0); return buf

# ============================================================
# 6. MAIN UI
# ============================================================
def main():
    st.set_page_config(page_title="Irrigation AI V12", layout="wide")
    if "zones" not in st.session_state: st.session_state.zones = []
    if "lang" not in st.session_state: st.session_state.lang = "ar"
    
    st.sidebar.title("💧 Irrigation AI V12")
    lang = st.sidebar.radio("Language", ["العربية", "English"])
    st.session_state.lang = "ar" if lang=="العربية" else "en"
    
    tabs = st.tabs(["1️⃣ Setup", "2️⃣ Zones", "3️⃣ Design", "4️⃣ Reports", "5️⃣ Plot", "6️⃣ BOQ & Finance", "7️⃣ Exports"])

    with tabs[0]:
        st.markdown("### 🤖 AI Assistant (Natural Language)")
        q = st.text_input("Describe your project (e.g., '25 feddans olive in Matrouh with well')")
        if q:
            parsed = parse_request(q)
            if parsed["area"]: st.success(f"Parsed: {parsed}")

        st.markdown("---")
        mode = st.radio(T("Mode","وضع الاستخدام"), ["Simplified", "Advanced"], horizontal=True)
        c1, c2, c3 = st.columns(3)
        with c1: pname = st.text_input(T("Name","اسم المشروع"), "My Farm")
        with c2: ptype = st.selectbox(T("Type","النوع"), ["Agricultural", "Landscape", "Greenhouse", "Nursery"])
        with c3: country = st.selectbox(T("Country","الدولة"), list(REGULATIONS.keys()), format_func=lambda x: REGULATIONS[x]["name"])
        
        st.markdown("---")
        sc1, sc2 = st.columns([3,1])
        with sc1: search_q = st.text_input(T("Search Location","ابحث عن الموقع"), value=parsed.get("loc") or "")
        with sc2:
            st.write(""); st.write("")
            if st.button("🔍 Search") and search_q and REQUESTS_OK:
                try:
                    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q":search_q,"format":"json","limit":1}, headers={"User-Agent":"AI/12"}, timeout=8)
                    if r.json():
                        st.session_state["lat"] = float(r.json()[0]["lat"]); st.session_state["lon"] = float(r.json()[0]["lon"])
                        st.success("Found!")
                except: st.error("API Error")
        
        lat, lon = st.session_state.get("lat", 30.0), st.session_state.get("lon", 30.0)
        
        area_mode = st.radio(T("Area Mode","المساحة"), ["Polygon","Manual"], horizontal=True)
        if area_mode == "Polygon":
            txt = st.text_area(T("Coords (lat, lon)","إحداثيات"), "30.5010, 30.4990\n30.5011, 30.5012\n30.4999, 30.5009\n30.5001, 30.4993", height=100)
            coords = []
            for ln in txt.split("\n"):
                try: coords.append((float(ln.split(",")[0]), float(ln.split(",")[1])))
                except: pass
            if len(coords)>=3:
                st.session_state["poly"] = coords
                st.success("✅ Polygon Saved")
        else:
            c1, c2 = st.columns(2)
            with c1: area_val = st.number_input(T("Area","المساحة"), 0.1, value=parsed.get("area") or 5.0)
            with c2: area_unit = st.selectbox(T("Unit","الوحدة"), list(AREA_UNITS.keys()))
            st.session_state["poly"] = []

        if st.button("🌤️ Fetch Real Climate & Soil"):
            with st.spinner("Fetching..."):
                clim = fetch_climate(lat, lon)
                soil = fetch_soil(lat, lon)
                st.session_state["eto"], st.session_state["wind"] = clim["eto"], clim["wind"]
                st.session_state["soil"] = soil
                st.success(f"✅ ETo: {clim['eto']} mm/d | Temp: {clim['temp']}°C | Soil: {soil}")

        eto = st.session_state.get("eto", 5.5); wind = st.session_state.get("wind", 2.0); soil = st.session_state.get("soil", "Sandy Loam")

        st.markdown("---")
        wsrc = st.selectbox(T("Water Source","مصدر المياه"), ["Nile","Well","Reclaimed","Mixed"])
        if mode == "Simplified":
            pipe = st.selectbox(T("Source Pipe","ماسورة المصدر"), ["1.5\"", "2\"", "3\"", "4\"", "6\"", "Canal"])
            tech = derive_defaults(wsrc, country, ptype, pipe)
            ec, ph, sar, filt, src_q, curr = tech["ec"], tech["ph"], tech["sar"], tech["filter"], tech["q_source"], tech["curr"]
            st.info("🤖 Expert System derived Water Quality & Source Q.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1: ec = st.number_input("EC", value=1.2)
            with c2: ph = st.number_input("pH", value=7.5)
            with c3: sar = st.number_input("SAR", value=3.0)
            c1, c2, c3 = st.columns(3)
            with c1: filt = st.selectbox("Filter", FILTERS, format_func=lambda x: FILTER_AR[x])
            with c2: src_q = st.number_input("Source Q (m3/h)", value=40.0)
            with c3: curr = st.selectbox("Currency", list(CURRENCIES.keys()))
            
        pc_choice = st.radio("Dripper Type", ["PC Dripper", "Non-PC Dripper"], horizontal=True)
        strat = st.radio("Operation Strategy", ["sequential", "parallel"], horizontal=True)
        
        st.session_state.project = {"name": pname, "project_type": ptype, "country": country, "eto": eto, "wind": wind, "ec": ec, "ph": ph, "sar": sar, "wsrc": wsrc, "filter": filt, "src_q": src_q, "curr": st.session_state.get("curr","EGP"), "mode": mode, "strategy": strat, "area_unit": area_unit, "lat": lat, "lon": lon, "pc": pc_choice, "slope": 0.0, "elev": 0.0, "suction": 2.0}

    proj = st.session_state.project
    if not proj: return

    with tabs[1]:
        if st.button("➕ Add Zone"):
            st.session_state.zones.append({"id":len(st.session_state.zones)+1, "name":f"Z{len(st.session_state.zones)+1}", "crop":"Tomato", "area_val":1.0, "area_unit":proj["area_unit"], "system":"drip", "q":2.0, "esp":0.3, "lsp":0.8, "soil":soil, "media":"Prepared Soil"})
            st.rerun()
            
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']} ({CROPS[z['crop']]['ar']})", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: z["name"] = st.text_input("Name", z["name"], key=f"n{i}")
                grp = PROJECT_CROP_GROUPS[proj["project_type"]]
                with c2: grp_sel = st.selectbox("Group", list(grp.keys()), key=f"g{i}")
                with c3: z["crop"] = st.selectbox("Crop", grp[grp_sel], format_func=lambda x: CROPS[x]['ar'], key=f"c{i}")
                
                c1, c2, c3 = st.columns(3)
                with c1: z["area_val"] = st.number_input("Area", value=z["area_val"], key=f"a{i}")
                with c2: z["area_unit"] = st.selectbox("Unit", list(AREA_UNITS.keys()), index=list(AREA_UNITS.keys()).index(z["area_unit"]), key=f"au{i}")
                with c3:
                    if proj["project_type"] in ["Agricultural","Greenhouse"]: z["soil"] = st.selectbox("Soil", list(SOILS.keys()), index=list(SOILS.keys()).index(z.get("soil", "Sandy Loam")), key=f"so{i}")
                    else: z["media"] = st.selectbox("Media", list(LANDSCAPE_MEDIA.keys()), key=f"m{i}")
                
                auto_sys = choose_system(CROPS[z["crop"]]["cat"], proj["ec"], proj["slope"], proj["wind"])
                if proj["mode"] == "Advanced":
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: z["system"] = st.selectbox("System", list(IRR_SYSTEMS.keys()), index=list(IRR_SYSTEMS.keys()).index(auto_sys), key=f"s{i}")
                    with c2: z["q"] = st.number_input("q L/h", value=z["q"], key=f"q{i}")
                    with c3: z["esp"] = st.number_input("Spacing (m)", value=z["esp"], key=f"e{i}")
                    with c4: z["lsp"] = st.number_input("Row Sp (m)", value=z["lsp"], key=f"l{i}")
                else:
                    z["system"] = auto_sys
                    st.caption(f"🤖 System: {IRR_SYSTEMS[auto_sys]['ar']}")
                
                if st.button("🗑️ Delete", key=f"d{i}"):
                    st.session_state.zones.pop(i); st.rerun()

    zones = st.session_state.zones
    if not zones: return

    designed = [design_zone(z, proj) for z in zones]
    designed, total_h = build_schedule(designed, proj["strategy"], proj["src_q"])
    issues, reg = check_compliance(proj, designed, total_h)
    boq_rows, capex, opex, pump = compute_boq(proj, designed, total_h)
    payback = f"{capex/(50000-opex):.1f} Years" if (50000-opex) > 0 else "N/A"

    with tabs[2]:
        st.markdown("### 📊 Dashboard")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Hours", f"{total_h:.1f} h")
        c2.metric("Daily Water", f"{sum(z['vol']/z['interval'] for z in designed):.1f} m³")
        c3.metric("Peak Flow", f"{max(z['q_m3h'] for z in designed):.1f} m³/h")
        c4.metric("Pump Power", f"{pump['kw']} kW")
        
        st.markdown("---")
        for z in designed:
            st.markdown(f"**{z['name']}:** {z['start']:.1f}h ➔ {z['end']:.1f}h | Flow: {z['q_m3h']:.1f} m³/h")
            if z.get("water_tree"): st.info(f"🌳 Water/Tree: {z['water_tree']['daily']} L/d | {z['water_tree']['event']} L/event")
            for t in z["treat"]: st.warning(f"💧 {t}")
            v = (z["q_m3h"]/3600) / (math.pi * (z["d_sub"]/2000)**2)
            if v < 0.6: st.warning(f"⚠️ Low Velocity ({v:.2f} m/s) in {z['name']} - Sediment risk")
            if v > 2.5: st.warning(f"⚠️ High Velocity ({v:.2f} m/s) in {z['name']} - Erosion risk")
            if proj["pc"] == "Non-PC Dripper" and proj["slope"] > 3: st.error("⛔ Use PC Drippers for slope > 3%")

    with tabs[3]:
        st.subheader("📄 Agronomic & Engineering Reports")
        if PDF_OK:
            pdf = build_pdf(proj, designed, boq_rows, total_h, pump)
            if pdf: st.download_button("⬇️ Download Full PDF Report", pdf, file_name="engineering_report.pdf", mime="application/pdf")
        else: st.warning("Install `reportlab` for PDF.")

    with tabs[4]:
        if MPL_OK:
            fig = build_plot(proj, designed)
            st.pyplot(fig)
            buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150); buf.seek(0)
            st.download_button("⬇️ PNG", buf, file_name="layout.png", mime="image/png")

    with tabs[5]:
        st.subheader("💰 Bill of Quantities & Financials")
        df = pd.DataFrame(boq_rows, columns=["Item", "Spec", f"Cost ({proj['curr']})"])
        st.dataframe(df, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("CAPEX", f"{capex:,.0f} {proj['curr']}")
        c2.metric("Annual OPEX", f"{opex:,.0f} {proj['curr']}")
        c3.metric("Payback Period", payback)

    with tabs[6]:
        st.subheader("📐 CAD & GIS Exports")
        c1, c2 = st.columns(2)
        with c1:
            dxf = build_dxf(proj, designed)
            if dxf: st.download_button("⬇️ Download DXF (AutoCAD)", dxf, file_name="design.dxf")
        with c2:
            if KML_OK and "poly" in st.session_state:
                kml_str = build_kml(proj)
                if kml_str: st.download_button("⬇️ Download KML (Google Earth)", kml_str.encode('utf-8'), file_name="farm.kml", mime="application/vnd.google-earth.kml+xml")
            geojson_str = build_geojson(proj)
            if geojson_str: st.download_button("⬇️ Download GeoJSON", geojson_str, file_name="farm.geojson")

if __name__ == "__main__":
    main()
