import io, math, os, json, tempfile, zipfile
from datetime import date, timedelta
import numpy as np
import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

try:
    import requests; REQUESTS_OK = True
except ImportError: REQUESTS_OK = False

try:
    import ezdxf; EZDXF_OK = True
except ImportError: EZDXF_OK = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    PDF_OK = True
except ImportError: PDF_OK = False

try:
    import pyfao56 as fao; PYFAO_OK = True
except ImportError: PYFAO_OK = False

try:
    import geopandas as gpd
    from shapely.geometry import Polygon
    GIS_OK = True
except ImportError: GIS_OK = False

st.set_page_config(page_title="Smart Irrigation AI V14.5", layout="wide")

if "project" not in st.session_state: st.session_state.project = None
if "zones" not in st.session_state: st.session_state.zones = []
if "results" not in st.session_state: st.session_state.results = None

# ==========================================
# DATABASES
# ==========================================
FEDDAN_M2 = 4200.0
AREA_UNITS = {"Feddan": 4200.0, "Hectare": 10000.0, "Acre": 4047.0, "m²": 1.0}
COUNTRY_INDEX = {"EG":1.0, "SA":1.35, "AE":1.4, "GR":1.2, "INTL":1.0}

OPEN_FIELD_SOILS = {"Sandy":80, "Loamy Sand":110, "Sandy Loam":140, "Loam":170, "Clay Loam":190, "Clay":210}
LANDSCAPE_MEDIA = {"Prepared Soil":150, "Imported Topsoil":140, "Peat Mix":180, "Sand-Soil Mix":110, "Turf Base":100}
GREENHOUSE_MEDIA = {"Peat+Perlite":200, "Coco Peat":190, "Rockwool":160, "Hydroponic":150}
NURSERY_MEDIA = {"Peat Moss":200, "Coco Peat":190, "Soil Mix":160}

CROPS = {
    "Wheat":{"kc":1.10,"zr":1.0,"cat":"field","ar":"قمح"}, "Maize":{"kc":1.15,"zr":1.0,"cat":"field","ar":"ذرة"},
    "Rice":{"kc":1.20,"zr":0.6,"cat":"field","ar":"أرز"}, "Barley":{"kc":1.05,"zr":1.0,"cat":"field","ar":"شعير"},
    "Alfalfa":{"kc":1.05,"zr":1.5,"cat":"field","ar":"برسيم"}, "Cotton":{"kc":1.15,"zr":1.0,"cat":"field","ar":"قطن"},
    "Sunflower":{"kc":1.00,"zr":1.0,"cat":"field","ar":"عباد الشمس"}, "Soybean":{"kc":1.05,"zr":0.8,"cat":"field","ar":"فول صويا"},
    "Sugar Beet":{"kc":1.10,"zr":1.0,"cat":"field","ar":"بنجر"}, "Sugarcane":{"kc":1.25,"zr":1.5,"cat":"field","ar":"قصب"},
    "Tomato":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"طماطم"}, "Potato":{"kc":1.10,"zr":0.5,"cat":"veg","ar":"بطاطس"},
    "Cucumber":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"خيار"}, "Pepper":{"kc":1.00,"zr":0.5,"cat":"veg","ar":"فلفل"},
    "Eggplant":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"باذنجان"}, "Onion":{"kc":1.05,"zr":0.4,"cat":"veg","ar":"بصل"},
    "Garlic":{"kc":1.00,"zr":0.4,"cat":"veg","ar":"ثوم"}, "Carrot":{"kc":1.05,"zr":0.5,"cat":"veg","ar":"جزر"},
    "Lettuce":{"kc":0.95,"zr":0.3,"cat":"veg","ar":"خس"}, "Cabbage":{"kc":1.05,"zr":0.5,"cat":"veg","ar":"كرنب"},
    "Watermelon":{"kc":1.05,"zr":1.0,"cat":"veg","ar":"بطيخ"}, "Melon":{"kc":1.05,"zr":0.9,"cat":"veg","ar":"شمام"},
    "Strawberry":{"kc":1.00,"zr":0.3,"cat":"veg","ar":"فراولة"}, "Zucchini":{"kc":1.00,"zr":0.6,"cat":"veg","ar":"كوسة"},
    "Bean":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"فاصوليا"},
    "Olive":{"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"}, "Citrus":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},
    "Orange":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"برتقال"}, "Lemon":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"ليمون"},
    "Mango":{"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"}, "Date Palm":{"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل"},
    "Grape":{"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"}, "Apple":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"تفاح"},
    "Pear":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"كمثرى"}, "Peach":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"خوخ"},
    "Fig":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"تين"}, "Pomegranate":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"رمان"},
    "Banana":{"kc":1.10,"zr":0.7,"cat":"orchard","ar":"موز"}, "Avocado":{"kc":0.90,"zr":0.8,"cat":"orchard","ar":"أفوكادو"},
    "Turf Bermuda":{"kc":0.80,"zr":0.3,"cat":"turf","ar":"نجيل برمودا"}, "Turf Fescue":{"kc":0.90,"zr":0.3,"cat":"turf","ar":"نجيل فيسكيوب"},
    "Turf Ryegrass":{"kc":0.85,"zr":0.3,"cat":"turf","ar":"نجيل راي"}, "Turf Zoysia":{"kc":0.75,"zr":0.3,"cat":"turf","ar":"نجيل زويسيا"},
    "Bougainvillea":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"جهنمية"}, "Hibiscus":{"kc":0.90,"zr":0.5,"cat":"shrub","ar":"خطمي"},
    "Lantana":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"لانتانا"}, "Duranta":{"kc":0.75,"zr":0.6,"cat":"shrub","ar":"دورانتا"},
    "Jasmine":{"kc":0.75,"zr":0.6,"cat":"shrub","ar":"ياسمين"}, "Oleander":{"kc":0.55,"zr":0.7,"cat":"shrub","ar":"دفلة"},
    "Pittosporum":{"kc":0.70,"zr":0.5,"cat":"shrub","ar":"بيتوسبورم"}, "Vinca":{"kc":0.75,"zr":0.4,"cat":"shrub","ar":"ونكا"},
    "Ficus":{"kc":0.70,"zr":1.0,"cat":"tree","ar":"فيكس"}, "Conocarpus":{"kc":0.55,"zr":1.2,"cat":"tree","ar":"كونوكاربس"},
    "Eucalyptus":{"kc":0.65,"zr":1.5,"cat":"tree","ar":"كافتوس"}, "Delonix":{"kc":0.60,"zr":1.0,"cat":"tree","ar":"بوانسيانا"},
    "Cassia":{"kc":0.65,"zr":1.0,"cat":"tree","ar":"كاسيا"}, "Washingtonia":{"kc":0.75,"zr":1.2,"cat":"tree","ar":"واشنطونيا"},
    "Phoenix":{"kc":0.70,"zr":1.2,"cat":"tree","ar":"فينكس"}, "Royal Palm":{"kc":0.80,"zr":1.2,"cat":"tree","ar":"رويال"},
    "Rose":{"kc":0.85,"zr":0.4,"cat":"flower","ar":"ورد"}, "Petunia":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"بيتونيا"},
    "Marigold":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"قطيفة"}, "Geranium":{"kc":0.90,"zr":0.4,"cat":"flower","ar":"جرانيوم"},
    "Chrysanthemum":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"أقحوان"}, "Carnation":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"قرنفل"},
    "Gerbera":{"kc":1.05,"zr":0.3,"cat":"flower","ar":"جربيرا"}, "Gladiolus":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"جلاديولس"},
    "Dahlia":{"kc":1.00,"zr":0.4,"cat":"flower","ar":"داليا"}, "Zinnia":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"زينيا"},
    "Gazania":{"kc":0.55,"zr":0.3,"cat":"flower","ar":"جازانيا"}, "Lavender":{"kc":0.65,"zr":0.4,"cat":"flower","ar":"لافندر"},
    "Lily":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"زنبق"}, "Aster":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"أستر"},
    "Ficus Benjamina":{"kc":0.75,"zr":0.6,"cat":"foliage","ar":"بنجامينا"}, "Dracaena":{"kc":0.65,"zr":0.5,"cat":"foliage","ar":"دراسينا"},
    "Schefflera":{"kc":0.75,"zr":0.5,"cat":"foliage","ar":"شيفليرا"}, "Aglaonema":{"kc":0.80,"zr":0.3,"cat":"foliage","ar":"أجلونيما"},
    "Croton":{"kc":0.85,"zr":0.4,"cat":"foliage","ar":"كروتون"},
    "Wedelia":{"kc":0.65,"zr":0.2,"cat":"groundcover","ar":"ويدليا"}, "Asparagus Fern":{"kc":0.75,"zr":0.3,"cat":"groundcover","ar":"اسباراجوس"},
    "Liriope":{"kc":0.70,"zr":0.2,"cat":"groundcover","ar":"ليريوبي"}, "Aptenia":{"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"أبتينيا"},
    "Portulaca":{"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"بورتولاكا"},
    "Ivy":{"kc":0.70,"zr":0.6,"cat":"climber","ar":"لبلاب"}, "Wisteria":{"kc":0.70,"zr":0.8,"cat":"climber","ar":"ويستيريا"},
    "Passion Flower":{"kc":0.75,"zr":0.7,"cat":"climber","ar":"زهرة الآلام"},
    "Aloe Vera":{"kc":0.35,"zr":0.2,"cat":"succulent","ar":"صبار"}, "Agave":{"kc":0.30,"zr":0.3,"cat":"succulent","ar":"أجاف"},
    "Sedum":{"kc":0.40,"zr":0.2,"cat":"succulent","ar":"سيدم"},
    "Potted Flowering":{"kc":1.10,"zr":0.25,"cat":"pot","ar":"أصص مزهرة"}, "Potted Foliage":{"kc":1.00,"zr":0.25,"cat":"pot","ar":"أصص ورقية"},
    "Potted Herb":{"kc":1.00,"zr":0.20,"cat":"pot","ar":"أصص أعشاب"}
}

CROP_GROUPS = {
    "Agricultural": {
        "🌾 Field": ["Wheat","Maize","Rice","Barley","Alfalfa","Cotton","Sunflower","Soybean","Sugar Beet","Sugarcane"],
        "🥬 Veg": ["Tomato","Potato","Cucumber","Pepper","Eggplant","Onion","Garlic","Carrot","Lettuce","Cabbage","Watermelon","Melon","Strawberry","Zucchini","Bean"],
        "🍊 Orchards": ["Olive","Citrus","Orange","Lemon","Mango","Date Palm","Grape","Apple","Pear","Peach","Fig","Pomegranate","Banana","Avocado"],
    },
    "Landscape": {
        "🌿 Turf": ["Turf Bermuda","Turf Fescue","Turf Ryegrass","Turf Zoysia"],
        "🌳 Shrubs": ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine","Oleander","Pittosporum","Vinca"],
        "🌴 Trees": ["Ficus","Conocarpus","Eucalyptus","Delonix","Cassia","Washingtonia","Phoenix","Royal Palm"],
        "🌸 Flowers": ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera","Gladiolus","Dahlia","Zinnia","Gazania","Lavender","Lily","Aster"],
        "🍃 Foliage": ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"],
        "🌱 Ground": ["Wedelia","Asparagus Fern","Liriope","Aptenia","Portulaca"],
        "🌿 Climbers": ["Ivy","Wisteria","Passion Flower"],
        "🌵 Succulents": ["Aloe Vera","Agave","Sedum"],
    },
    "Greenhouse": {"🍅 GH Veg": ["Tomato","Cucumber","Pepper","Strawberry"], "🌸 GH Flowers": ["Rose","Gerbera","Carnation","Lily"]},
    "Nursery": {"🌸 Flowers": ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera"], "🍃 Foliage": ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"], "🌳 Shrubs": ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine"], "🪴 Potted": ["Potted Flowering","Potted Foliage","Potted Herb"]},
}

P_ALLOW = {"field":0.50, "veg":0.35, "orchard":0.55, "turf":0.50, "shrub":0.45, "tree":0.50, "flower":0.40, "foliage":0.45, "groundcover":0.45, "climber":0.45, "succulent":0.30, "pot":0.35}
TREE_CROPS = {"Olive","Citrus","Orange","Lemon","Mango","Date Palm","Grape","Apple","Pear","Peach","Fig","Pomegranate","Avocado"}
CANOPY = {"Olive":0.70, "Date Palm":0.80, "Mango":0.90, "Citrus":0.85, "Grape":0.75, "Apple":0.85, "Pomegranate":0.80, "Avocado":0.90}

IRR_SYSTEMS = {"drip":{"ar":"تنقيط","eff":0.90,"p":15},"micro":{"ar":"ميكرو","eff":0.85,"p":20},"sprinkler":{"ar":"رشاش","eff":0.75,"p":25}}

REGULATIONS = {
    "EG":{"name":"مصر","max_h":10,"banned":["surface"]}, "SA":{"name":"السعودية","max_h":16,"banned":["surface"]},
    "AE":{"name":"الإمارات","max_h":14,"banned":["surface"]}, "GR":{"name":"اليونان","max_h":14,"banned":[]}, "INTL":{"name":"دولي","max_h":24,"banned":[]}
}

FILTERS = {"Screen Filter":"فلتر شبكي","Disc Filter":"فلتر ديسكات","Media Filter":"فلتر رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}

PUMPS = [
    {"name":"Grundfos CR 5-10","Q":5,"H":90,"kw":2.2,"eff":65,"NPSHr":2.0,"BEP_Q":5,"BEP_H":85,"BEP_eff":65,"curve":[(0,95),(2.5,92),(5,85),(7.5,75),(10,60),(12.5,40)]},
    {"name":"Grundfos CR 10-10","Q":10,"H":95,"kw":4.0,"eff":70,"NPSHr":2.5,"BEP_Q":10,"BEP_H":82,"BEP_eff":70,"curve":[(0,100),(5,95),(10,82),(15,70),(20,55)]},
    {"name":"Grundfos CR 15-8","Q":15,"H":80,"kw":5.5,"eff":72,"NPSHr":3.0,"BEP_Q":15,"BEP_H":70,"BEP_eff":72,"curve":[(0,85),(7.5,82),(15,70),(22.5,55),(30,35)]},
    {"name":"Ebara EVMS 15","Q":15,"H":85,"kw":5.5,"eff":70,"NPSHr":3.0,"BEP_Q":15,"BEP_H":75,"BEP_eff":70,"curve":[(0,90),(7.5,88),(15,75),(22.5,60),(30,40)]},
    {"name":"Lowara e-SV 22","Q":22,"H":75,"kw":7.5,"eff":75,"NPSHr":3.5,"BEP_Q":22,"BEP_H":65,"BEP_eff":75,"curve":[(0,80),(11,78),(22,65),(33,50),(44,30)]},
    {"name":"Grundfos CR 20-5","Q":20,"H":60,"kw":5.5,"eff":73,"NPSHr":3.5,"BEP_Q":20,"BEP_H":50,"BEP_eff":73,"curve":[(0,65),(10,63),(20,50),(30,35),(40,20)]},
]

MAX_DRIP_HOURS = 8.0
MAX_SPRINKLER_HOURS = 6.0
MAX_ZONE_AREA_DRIP = 10.0
MAX_ZONE_AREA_SPRINKLER = 5.0
ATM_PRESSURE = 10.3
VAPOR_PRESSURE = 0.24

# ==========================================
# ENGINES
# ==========================================
def fetch_climate(lat, lon):
    if not REQUESTS_OK: return {"eto":5.5,"temp":25.0}
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params={"latitude":lat,"longitude":lon,"start_date":"2023-07-01","end_date":"2023-08-31","daily":"et0_fao_evapotranspiration,temperature_2m_max"})
        d = r.json()["daily"]
        return {"eto":round(max([v for v in d["et0_fao_evapotranspiration"] if v is not None]+[5.5]),1), "temp":round(max([v for v in d["temperature_2m_max"] if v is not None]+[25]),1)}
    except: return {"eto":5.5,"temp":25.0}

def calc_etc(kc, zr, eto, taw, et_method):
    if et_method == "FAO56" and PYFAO_OK:
        try:
            par = fao.Parameters(); par.kc = kc; par.zr = zr
            wth = fao.Weather(); wth.eto = eto; wth.tmax = eto*2.5+10; wth.tmin = wth.tmax-12; wth.rhmax = 85; wth.rhmin = 30; wth.u2 = 2.0; wth.rs = eto*2.5
            start = date.today()-timedelta(days=1); end = date.today()
            m = fao.Model(start, end, par, wth); m.run()
            etc = float(np.asarray(m.etc).flatten()[-1])
            return max(etc, kc*eto*0.5), "pyfao56"
        except: pass
    if et_method == "FAO56":
        kc_adj = max(kc*0.9, kc - 0.05)
        return kc_adj*eto, "FAO-56 (adj)"
    return kc*eto, "Standard"

def select_pipe(q, v=1.2):
    if q <= 0: return 16
    d = math.sqrt((4*(q/3600.0))/(math.pi*v))*1000
    for std in [16,20,25,32,40,50,63,75,90,110,125,160,200,250,300,400]:
        if std >= d: return std
    return 400

def hw(L, q, d):
    if q <= 0 or d <= 0: return 0
    return 10.67*L*((q/3600)**1.852)/((140**1.852)*((d/1000)**4.87))

def calc_uniformity(op_p, hf):
    p_end = max(1.0, op_p - hf); p_avg = op_p - hf/2
    return round(100*math.sqrt(p_end/p_avg) if p_avg>0 else 0, 1)

def curve_head_at_q(curve, q):
    pts = sorted(curve, key=lambda x: x[0])
    if q <= pts[0][0]: return pts[0][1]
    if q >= pts[-1][0]: return pts[-1][1]
    for i in range(len(pts)-1):
        q1,h1 = pts[i]; q2,h2 = pts[i+1]
        if q1 <= q <= q2:
            return h1 + (h2-h1)*(q-q1)/max(1e-9,(q2-q1))
    return pts[-1][1]

def pump_score(p, req_q, req_h):
    return abs(p["BEP_Q"]-req_q) + abs(p["BEP_H"]-req_h)

def select_pump_best(q, h):
    cands = [p for p in PUMPS if p["Q"] >= q and p["H"] >= h]
    if cands: return min(cands, key=lambda p: pump_score(p, q, h))
    return min(PUMPS, key=lambda p: pump_score(p, q, h))

def npsh_available(suction, losses, atm=ATM_PRESSURE, vapor=VAPOR_PRESSURE):
    return round(atm - suction - losses - vapor, 2)

def npsh_status(npsha, npshr):
    if npsha >= npshr + 0.5: return "safe"
    if npsha >= npshr: return "tight"
    return "risk"

def select_filter(wsrc):
    return "Media Filter" if wsrc=="Well" else "Disc Filter" if wsrc=="Reclaimed" else "Screen Filter"

def water_treatment(ec, ph, sar):
    t = []
    if ec > 5: t.append("Leaching (غسيل أملاح)")
    if ph > 8.2: t.append("Acid Injection (حقن حامض)")
    if sar > 9: t.append("Gypsum (جبس)")
    return t

def design_zone(z, proj):
    c = CROPS[z["crop"]]
    eff = IRR_SYSTEMS[z["system"]]["eff"]
    p_allow = P_ALLOW.get(c["cat"], 0.5)
    
    etc, method = calc_etc(c["kc"], c["zr"], proj["eto"], z["taw"], proj["et_method"])
    raw = p_allow * z["taw"] * c["zr"]
    
    max_i = 3 if c["cat"] in ("veg","flower","pot") else 7 if c["cat"] in ("orchard","tree") else 14 if c["cat"]=="succulent" else 5
    interval = max(1, min(int(round(raw/etc if etc>0 else max_i)), max_i))
    
    area = z["area_val"] * AREA_UNITS[z["area_unit"]]
    vol = ((etc*interval)/eff) * area / 1000
    
    if c["cat"] in TREE_CROPS:
        esp, lsp = z.get("esp",5.0), z.get("lsp",6.0)
        n_trees = int(area/(esp*lsp))
        emitters = n_trees * z.get("emitters_per_tree", 4)
        q_lph = emitters * z.get("q",8.0)
    elif c["cat"] == "turf":
        emitters = int(area/100); q_lph = emitters*800
    elif c["cat"] in ("tree","shrub"):
        n = int(area/(3.0*4.0)); emitters = n*z.get("emitters_per_tree",4); q_lph = emitters*z.get("q",4.0)
    elif c["cat"] in ("flower","foliage","groundcover","climber","pot"):
        emitters = int(area/0.5); q_lph = emitters*z.get("q",2.0)
    else:
        emitters = int(area/(z.get("esp",0.3)*z.get("lsp",0.8))); q_lph = emitters*z.get("q",4.0)
    
    q_m3h = q_lph/1000
    dur = vol/q_m3h if q_m3h>0 else 0
    
    L_lat = math.sqrt(area)
    n_lat = max(1, int(L_lat/z.get("lsp",0.8)))
    q_lat = q_m3h/n_lat
    d_lat = select_pipe(q_lat, 0.8)
    d_sub = select_pipe(q_m3h, 1.2)
    hf_lat = hw(L_lat, q_lat, d_lat)
    hf_sub = hw(L_lat*1.5, q_m3h, d_sub)
    
    op_p = IRR_SYSTEMS[z["system"]]["p"]
    eu = calc_uniformity(op_p, hf_lat)
    tdh = (proj.get("elev",0) + proj.get("suction",2) + hf_sub + op_p + 5) * proj.get("safety", 1.15)
    npsha = npsh_available(proj.get("suction",2), hf_sub)
    
    return {**z, "etc":etc, "method":method, "interval":interval, "vol":vol,
            "q_m3h":q_m3h, "dur":dur, "d_lat":d_lat, "d_sub":d_sub, "hf_lat":hf_lat,
            "hf_sub":hf_sub, "tdh":tdh, "eu":eu, "emitters":emitters, "npsha":npsha,
            "treatment": water_treatment(proj["ec"], proj["ph"], proj["sar"])}

def intelligent_zone_split(z, proj):
    base = design_zone(z, proj)
    is_drip = z["system"] in ("drip","micro")
    max_h = MAX_DRIP_HOURS if is_drip else MAX_SPRINKLER_HOURS
    max_a = MAX_ZONE_AREA_DRIP if is_drip else MAX_ZONE_AREA_SPRINKLER
    
    n_time = math.ceil(base["dur"]/max_h) if base["dur"]>max_h else 1
    n_area = math.ceil(z["area_val"]/max_a) if z["area_val"]>max_a else 1
    n_zones = max(1, n_time, n_area)
    
    reasons = []
    if n_time > 1: reasons.append(f"الزمن ({base['dur']:.1f}h) > {max_h}h")
    if n_area > 1: reasons.append(f"المساحة ({z['area_val']:.1f}) > {max_a}")
    
    if n_zones == 1:
        base["zone_label"] = z["name"]; base["zone_idx"] = 1
        return [base], None
    
    split_area = z["area_val"]/n_zones
    zones = []
    for i in range(n_zones):
        z_sub = {**z, "area_val": split_area, "name": f"{z['name']}-Z{i+1}"}
        d = design_zone(z_sub, proj)
        d["zone_label"] = f"{z['name']}-Z{i+1}"; d["zone_idx"] = i+1
        zones.append(d)
    return zones, " + ".join(reasons)

def advisor(proj, zones, split_reasons, pump_info):
    adv = []
    if not PYFAO_OK and proj["et_method"]=="FAO56": adv.append(("warning", "⚠️ pyfao56 غير مثبتة - استخدام FAO-56 (adj)"))
    elif PYFAO_OK and proj["et_method"]=="FAO56": adv.append(("info", "✅ pyfao56 Active"))
    if not GIS_OK: adv.append(("info", "ℹ️ Shapefile غير متاح - استخدم GeoJSON"))
    
    p = pump_info
    req_q, req_h = p["req_q"], p["req_h"]
    head_at_q = curve_head_at_q(p["pump"]["curve"], req_q)
    bep_dist = pump_score(p["pump"], req_q, req_h)
    adv.append(("info", f"🔧 Pump: {p['pump']['name']} | BEP=({p['pump']['BEP_Q']},{p['pump']['BEP_H']}) | Head@Q={head_at_q:.1f}m | Score={bep_dist:.1f}"))
    
    if bep_dist > 15: adv.append(("warning", f"⚙️ نقطة التشغيل بعيدة عن BEP. فكّر في مضخة أخرى."))
    
    # [إضافة جديدة]: تحذير المصدر
    if req_q > 50: adv.append(("error", f"🚨 التصرف المطلوب ({req_q:.1f} m³/h) ضخم جداً! راجع مسافات المنقطات أو استخدم رشاشات."))
    
    npsha = npsh_available(proj.get("suction",2), p["hf_sub"])
    npshr = p["pump"]["NPSHr"]
    status = npsh_status(npsha, npshr)
    if status == "risk": adv.append(("error", f"🌊 Cavitation Risk! NPSHa={npsha}m < NPSHr={npshr}m."))
    elif status == "tight": adv.append(("warning", f"🌊 NPSH هامش ضيق: NPSHa={npsha}m ~ NPSHr={npshr}m"))
    else: adv.append(("info", f"🌊 NPSH Safe: NPSHa={npsha}m > NPSHr={npshr}m"))
    
    for z in zones:
        max_h = MAX_DRIP_HOURS if z["system"] in ("drip","micro") else MAX_SPRINKLER_HOURS
        if z["dur"] > max_h: adv.append(("error", f"⏰ {z['zone_label']}: {z['dur']:.1f}h طويل جداً"))
        if z["eu"] < 80: adv.append(("warning", f"📊 {z['zone_label']}: EU {z['eu']}% < 80%"))
        if z["tdh"] > 120: adv.append(("warning", f"🔧 {z['zone_label']}: TDH {z['tdh']:.1f}m مرتفع"))
        for t in z["treatment"]: adv.append(("warning", f"💧 {z['zone_label']}: {t}"))
    
    if split_reasons: adv.insert(0, ("info", f"🔧 الوكيل الهندسي قسّم المشروع. السبب: {split_reasons}"))
    if proj["project_type"] == "Greenhouse": adv.append(("info", "🏠 صوبة: ETo×0.6 | 25°C"))
    if proj["project_type"] == "Landscape": adv.append(("info", "🌳 لاندسكيب: ميديا مجهزة"))
    if proj["project_type"] == "Nursery": adv.append(("info", "🪴 مشتل: ميديا ثابتة"))
    
    return adv

def compute_boq(proj, zones, autonomy_days=1.0):
    idx = COUNTRY_INDEX.get(proj["country"], 1.0)
    rows = []
    peak_q = max(z["q_m3h"] for z in zones) if zones else 0
    max_tdh = max(z["tdh"] for z in zones) if zones else 50
    max_hf_sub = max(z["hf_sub"] for z in zones) if zones else 0
    
    if proj.get("pump_choice") == "Auto":
        pump = select_pump_best(peak_q, max_tdh)
        pk, pk_kw, pk_eff = pump["name"], pump["kw"], pump["eff"]
    else:
        pump = next((p for p in PUMPS if p["name"]==proj["pump_choice"]), PUMPS[0])
        pk = proj["pump_choice"]
        pk_kw, pk_eff = proj.get("pump_kw",7.5), proj.get("pump_eff",75)
    
    rows.append(("Pump & Motor", f"{pk} ({pk_kw} kW)", 15000*(pk_kw/2)*idx))
    rows.append(("Controller", "Auto Panel", 5000*idx))
    
    tank = sum(z["vol"]/z["interval"] for z in zones) * 1.2 * autonomy_days
    rows.append(("Water Tank", f"{tank:.1f} m³", tank*2000*idx))
    
    if peak_q > 30: rows.append(("Pressure Regulator", "1", 3500*idx))
    rows.append(("Main Pipe", f"Ø{select_pipe(peak_q)}mm", 100*80.0*idx))
    
    for z in zones:
        rows.append((f"{z['zone_label']} Sub", f"Ø{z['d_sub']}mm", 50*45.0*idx))
        rows.append((f"{z['zone_label']} Lat", f"Ø{z['d_lat']}mm", 200*6.0*idx))
        rows.append((f"{z['zone_label']} Valve", "1", 2500.0*idx))
    
    rows.append((f"Filter ({proj['filter']})", proj["filter"], FILTER_PRICE.get(proj["filter"],0)*idx))
    
    subtotal = sum(r[2] for r in rows)
    rows.append(("Fittings (10%)", "-", subtotal*0.1))
    capex = subtotal*1.1
    
    total_h = max(z["dur"] for z in zones) if zones else 0
    opex = ((pk_kw*total_h*365)/(pk_eff/100)*0.15*idx) + (capex*0.03)
    
    pump_info = {"pump": pump, "req_q": peak_q, "req_h": max_tdh, "hf_sub": max_hf_sub}
    return rows, capex, opex, tank, pump_info

def calc_npv(capex, annual_cf, years, rate):
    return round(-capex + sum(annual_cf/((1+rate)**t) for t in range(1,years+1)), 2)

def calc_irr(capex, annual_cf, years):
    if annual_cf <= 0: return 0.0
    try:
        lo, hi = -0.99, 2.0
        for _ in range(80):
            mid = (lo+hi)/2
            npv = -capex + sum(annual_cf/((1+mid)**t) for t in range(1,years+1))
            if abs(npv) < 1: return round(mid*100, 2)
            if npv > 0: lo = mid
            else: hi = mid
        return round(mid*100, 2)
    except: return 0.0

def calc_lcc(capex, opex, years, rate):
    return round(capex + sum(opex/((1+rate)**t) for t in range(1,years+1)), 2)

# ==========================================
# EXPORTS
# ==========================================
def get_polygon_coords(proj, zones):
    lat0, lon0 = proj["lat"], proj["lon"]
    total_m2 = sum(z["area_val"]*AREA_UNITS[z["area_unit"]] for z in zones)
    side_m = math.sqrt(total_m2)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat0))
    dlat = side_m / m_per_deg_lat
    dlon = side_m / max(1e-9, m_per_deg_lon)
    return [(lon0, lat0), (lon0+dlon, lat0), (lon0+dlon, lat0+dlat), (lon0, lat0+dlat), (lon0, lat0)]

def build_geojson(proj, zones):
    try:
        coords = [get_polygon_coords(proj, zones)]
        features = [{
            "type": "Feature",
            "properties": {"name": proj["name"], "project_type": proj["project_type"], "total_area_fed": sum(z["area_val"] for z in zones), "n_zones": len(zones), "pump": proj.get("_pump_name","")},
            "geometry": {"type":"Polygon","coordinates": coords}
        }]
        return json.dumps({"type":"FeatureCollection","features":features}, ensure_ascii=False, indent=2)
    except: return None

def build_shapefile_zip(proj, zones):
    if not GIS_OK: return None
    try:
        coords = get_polygon_coords(proj, zones)
        poly = Polygon(coords)
        gdf = gpd.GeoDataFrame({"name":[proj["name"]], "area_fed":[sum(z["area_val"] for z in zones)], "n_zones":[len(zones)], "project":[proj["project_type"]]}, geometry=[poly], crs="EPSG:4326")
        tmpdir = tempfile.mkdtemp()
        shp_path = os.path.join(tmpdir, "farm.shp")
        gdf.to_file(shp_path, driver="ESRI Shapefile")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in os.listdir(tmpdir): zf.write(os.path.join(tmpdir, fn), fn)
        zip_buf.seek(0); return zip_buf
    except: return None

def build_pdf(proj, zones, boq, capex, opex, npv, irr, lcc, tank, pump_info):
    if not PDF_OK: return None
    try:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        el = [Paragraph(f"Project: {proj['name']}", styles['Title']), Spacer(1,12)]
        el.append(Paragraph(f"Type: {proj['project_type']} | Country: {REGULATIONS[proj['country']]['name']}", styles['Normal']))
        el.append(Paragraph(f"Climate: ETo={proj['eto']} mm/d | T={proj['temp']}°C", styles['Normal']))
        el.append(Paragraph(f"Water: EC={proj['ec']} pH={proj['ph']} SAR={proj['sar']} | Filter: {proj['filter']}", styles['Normal']))
        el.append(Paragraph(f"ET Method: {proj['et_method']}", styles['Normal']))
        el.append(Spacer(1,12))
        
        p = pump_info["pump"]
        el.append(Paragraph("<b>Pump</b>", styles['Heading2']))
        el.append(Paragraph(f"{p['name']} | {p['kw']} kW | BEP=({p['BEP_Q']},{p['BEP_H']}) | NPSHr={p['NPSHr']}m", styles['Normal']))
        npsha = npsh_available(proj.get("suction",2), pump_info["hf_sub"])
        status = npsh_status(npsha, p["NPSHr"])
        el.append(Paragraph(f"NPSHa = {npsha}m | Status = {status.upper()}", styles['Normal']))
        el.append(Spacer(1,12))
        
        data = [["Zone","Crop","Area","ETc","Interval","Flow","Duration","EU"]]
        for z in zones: data.append([z["zone_label"], CROPS[z["crop"]]["ar"], f"{z['area_val']:.2f}", f"{z['etc']:.1f}", f"{z['interval']}d", f"{z['q_m3h']:.1f}", f"{z['dur']:.1f}h", f"{z['eu']}%"])
        t = Table(data); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.lightgrey)]))
        el.append(t); el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>Financial</b>", styles['Heading2']))
        fdata = [["Item","Value"], ["CAPEX",f"{capex:,.0f} EGP"],["OPEX/Year",f"{opex:,.0f} EGP"], ["NPV",f"{npv:,.0f} EGP"],["IRR",f"{irr}%"], ["LCC",f"{lcc:,.0f} EGP"],["Tank",f"{tank:.1f} m³"]]
        ft = Table(fdata); ft.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        el.append(ft); el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>BOQ</b>", styles['Heading2']))
        bdata = [["Item","Spec","Cost"]] + [[r[0],r[1],f"{r[2]:,.0f}"] for r in boq]
        bt = Table(bdata); bt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        el.append(bt)
        
        doc.build(el); buf.seek(0); return buf
    except: return None

def build_dxf(proj, zones):
    if not EZDXF_OK: return None
    try:
        doc = ezdxf.new("R2010"); msp = doc.modelspace()
        for l in ["MAIN","PUMP","TANK","SUBMAIN","ZONE","BOUNDARY"]: doc.layers.add(l)
        W = 100.0
        msp.add_lwpolyline([(0,0),(W,0),(W,80),(0,80),(0,0)], dxfattribs={"layer":"BOUNDARY"})
        msp.add_circle((50,-10), 2, dxfattribs={"layer":"PUMP"})
        msp.add_circle((0,0), 3, dxfattribs={"layer":"TANK"})
        y = 0; step = 80/max(1,len(zones))
        for z in zones:
            msp.add_line((0,y),(W,y), dxfattribs={"layer":"SUBMAIN"})
            msp.add_circle((W*0.9, y+step/2), 0.5, dxfattribs={"layer":"ZONE"})
            t = msp.add_text(z["zone_label"], dxfattribs={"layer":"ZONE","height":1.5})
            t.dxf.insert = (5, y+step/2)
            y += step
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp: path = tmp.name
        doc.saveas(path)
        with open(path,"rb") as f: return io.BytesIO(f.read())
    except: return None

def build_plot(zones):
    try:
        fig, ax = plt.subplots(figsize=(9,4), dpi=100)
        y = 0; step = 80/max(1,len(zones))
        for z in zones:
            color = "#4CAF50" if z["eu"] >= 80 else "#F44336"
            ax.add_patch(Rectangle((0,y), 100, step, fill=True, alpha=0.25, ec=color, lw=2))
            ax.text(50, y+step/2, f"{z['zone_label']} | {CROPS[z['crop']]['ar']} | {z['area_val']:.2f}fd", ha='center', va='center', fontsize=9, bbox=dict(fc='white', ec=color))
            y += step
        ax.set_xlim(0,100); ax.set_ylim(0,80); ax.axis("off")
        buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches=None)
        buf.seek(0); plt.close(fig); return buf
    except: return None

# ==========================================
# UI
# ==========================================
def main():
    st.sidebar.title("💧 Smart Irrigation AI V14.5")
    design_mode = st.sidebar.radio("Design Mode", ["Client","Engineer"], format_func=lambda x: "👤 Client" if x=="Client" else "👨‍🔧 Engineer")
    et_method = st.sidebar.radio("ET Method", ["Standard","FAO56"], format_func=lambda x: "Standard (Kc×ETo)" if x=="Standard" else "FAO-56")
    
    if PYFAO_OK: st.sidebar.success("✅ pyfao56 Active")
    if GIS_OK: st.sidebar.success("✅ GIS Ready")
    
    tabs = st.tabs(["1. Setup","2. Water Quality","3. Zones","4. Hydraulic Design","5. Engineering Advisor","6. BOQ & Finance","7. Reports","8. Exports"])
    
    with tabs[0]:
        st.subheader("Project Setup")
        c1, c2 = st.columns(2)
        with c1:
            pname = st.text_input("Project Name", "My Farm")
            project_type = st.selectbox("Project Type", list(CROP_GROUPS.keys()))
        with c2:
            country = st.selectbox("Country", list(REGULATIONS.keys()), format_func=lambda x: REGULATIONS[x]["name"])
        
        st.markdown("### Location & Climate")
        lc1, lc2, lc3 = st.columns(3)
        with lc1: lat = st.number_input("Latitude", 20.0, 40.0, 30.0, 0.01)
        with lc2: lon = st.number_input("Longitude", 20.0, 40.0, 31.0, 0.01)
        with lc3:
            st.write(""); st.write("")
            if st.button("🌤️ Fetch Climate"):
                clim = fetch_climate(lat, lon)
                st.session_state["eto"] = clim["eto"]; st.session_state["temp"] = clim["temp"]
                st.success(f"ETo={clim['eto']} | T={clim['temp']}°C")
        eto = st.session_state.get("eto", 6.5)
        temp = st.session_state.get("temp", 28.0)
        
        st.markdown("### Engineering Tuning")
        ec1, ec2 = st.columns(2)
        with ec1:
            safety = st.number_input("Safety Factor", 1.0, 2.0, 1.15)
            elevation = st.number_input("Elevation Diff (m)", 0.0, 100.0, 0.0)
        with ec2:
            suction = st.number_input("Suction Lift (m)", 0.0, 15.0, 2.0)
            pump_choice = st.selectbox("Pump Selection", ["Auto"] + [p["name"] for p in PUMPS])
        
        pump_kw, pump_eff = 7.5, 75
        if pump_choice != "Auto":
            pk1, pk2 = st.columns(2)
            with pk1: pump_kw = st.number_input("Pump kW", 0.0, 100.0, 7.5)
            with pk2: pump_eff = st.number_input("Pump Eff (%)", 10.0, 100.0, 75.0)
        
        st.session_state.project = {
            "name": pname, "project_type": project_type, "country": country,
            "eto": eto, "temp": temp, "lat": lat, "lon": lon,
            "ec": 2.0, "ph": 7.5, "sar": 5.0, "wsrc": "Nile", "filter": "Screen Filter",
            "et_method": et_method, "design_mode": design_mode,
            "safety": safety, "elev": elevation, "suction": suction,
            "pump_choice": pump_choice, "pump_kw": pump_kw, "pump_eff": pump_eff,
            "revenue": st.session_state.get("revenue", 200000.0),
        }
    
    proj = st.session_state.get("project")
    if not proj: st.stop()
    proj["et_method"] = et_method; proj["design_mode"] = design_mode; st.session_state.project = proj
    
    with tabs[1]:
        st.subheader("Water Quality & Source")
        wq1, wq2, wq3 = st.columns(3)
        with wq1: ec = st.number_input("EC (dS/m)", 0.0, 20.0, 2.0)
        with wq2: ph = st.number_input("pH", 4.0, 10.0, 7.5)
        with wq3: sar = st.number_input("SAR", 0.0, 30.0, 5.0)
        
        wsrc = st.selectbox("Water Source", ["Nile","Well","Reclaimed"])
        auto_filter = select_filter(wsrc)
        st.info(f"🤖 Auto Filter: **{auto_filter}**")
        
        if design_mode == "Engineer":
            fo = st.selectbox("Override Filter", ["Auto"] + list(FILTERS.keys()))
            if fo != "Auto": auto_filter = fo
        
        treatments = water_treatment(ec, ph, sar)
        if treatments:
            st.markdown("### Water Treatment Required:")
            for t in treatments: st.warning(f"💧 {t}")
        else: st.success("✅ Water quality is acceptable")
        
        proj["ec"], proj["ph"], proj["sar"] = ec, ph, sar
        proj["wsrc"] = wsrc; proj["filter"] = auto_filter; st.session_state.project = proj
    
    with tabs[2]:
        st.subheader("Zones Manager")
        if st.button("➕ Add Zone"):
            st.session_state.zones.append({
                "name": f"Z{len(st.session_state.zones)+1}", "crop": "Tomato",
                "area_val": 1.0, "area_unit": "Feddan", "system": "drip",
                "q": 4.0, "esp": 0.3, "lsp": 0.8, "taw": OPEN_FIELD_SOILS["Sandy Loam"],
                "emitters_per_tree": 4,
            })
            st.rerun()
        
        if proj["project_type"] == "Landscape": taw_opts = LANDSCAPE_MEDIA; st.info("🌳 Landscape: ميديا مجهزة")
        elif proj["project_type"] == "Greenhouse": taw_opts = GREENHOUSE_MEDIA; st.info("🏠 Greenhouse: ETo×0.6 | 25°C")
        elif proj["project_type"] == "Nursery": taw_opts = NURSERY_MEDIA
        else: taw_opts = OPEN_FIELD_SOILS
        
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: z["name"] = st.text_input("Name", z["name"], key=f"n{i}")
                grp = CROP_GROUPS[proj["project_type"]]
                with c2: grp_sel = st.selectbox("Group", list(grp.keys()), key=f"g{i}")
                with c3:
                    old_crop = z["crop"]
                    z["crop"] = st.selectbox("Crop", grp[grp_sel], format_func=lambda x: CROPS[x]["ar"], key=f"c{i}")
                    # [تحديث ذكي]: لو غيرت المحصول، بيظبط المسافات لوحده
                    if old_crop != z["crop"]:
                        cat = CROPS[z["crop"]]["cat"]
                        if cat in TREE_CROPS:
                            z["esp"], z["lsp"], z["q"], z["emitters_per_tree"] = 5.0, 6.0, 8.0, 4
                        elif cat == "field":
                            z["esp"], z["lsp"], z["q"] = 0.15, 1.5, 4.0 # مسافات حقول
                        else:
                            z["esp"], z["lsp"], z["q"] = 0.3, 0.8, 4.0 # مسافات خضار
                
                c1, c2, c3 = st.columns(3)
                with c1: z["area_val"] = st.number_input("Area", value=z["area_val"], key=f"a{i}")
                with c2: z["system"] = st.selectbox("System", list(IRR_SYSTEMS.keys()), key=f"s{i}")
                with c3:
                    if design_mode == "Engineer":
                        taw_key = st.selectbox("Media/Soil", list(taw_opts.keys()), key=f"t{i}"); z["taw"] = taw_opts[taw_key]
                    else: z["taw"] = list(taw_opts.values())[0]
                
                if design_mode == "Engineer":
                    ac1, ac2, ac3, ac4 = st.columns(4)
                    with ac1:
                        if CROPS[z["crop"]]["cat"] in TREE_CROPS: z["esp"] = st.number_input("Tree Spacing", value=z.get("esp",5.0), key=f"e{i}")
                    with ac2:
                        if CROPS[z["crop"]]["cat"] in TREE_CROPS: z["lsp"] = st.number_input("Row Spacing", value=z.get("lsp",6.0), key=f"l{i}")
                    with ac3: z["q"] = st.number_input("Emitter Flow (L/h)", value=z.get("q",4.0), key=f"q{i}")
                    with ac4:
                        if CROPS[z["crop"]]["cat"] in TREE_CROPS: z["emitters_per_tree"] = st.number_input("Emitters/Tree", 1, 12, value=z.get("emitters_per_tree",4), key=f"ep{i}")
                
                if st.button("🗑️ Delete", key=f"d{i}"): st.session_state.zones.pop(i); st.rerun()
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            revenue = st.number_input("Annual Revenue (EGP)", 0.0, 10000000.0, value=proj.get("revenue",200000.0), step=10000.0)
            autonomy = st.number_input("Tank Autonomy (Days)", 0.5, 7.0, 1.0, step=0.5)
            proj["revenue"] = revenue; st.session_state.project = proj
        with c2:
            if st.button("🚀 Calculate Design", type="primary"):
                if not st.session_state.zones: st.error("Add zones first")
                else:
                    with st.spinner("Calculating..."):
                        all_zones = []; split_reasons = []
                        for z in st.session_state.zones:
                            sub, reason = intelligent_zone_split(z, proj)
                            all_zones.extend(sub)
                            if reason: split_reasons.append(f"{z['name']}: {reason}")
                        
                        boq, capex, opex, tank, pump_info = compute_boq(proj, all_zones, autonomy)
                        annual_cf = proj["revenue"] - opex
                        npv = calc_npv(capex, annual_cf, 10, 0.10); irr = calc_irr(capex, annual_cf, 10); lcc = calc_lcc(capex, opex, 10, 0.10)
                        advisories = advisor(proj, all_zones, " + ".join(split_reasons) if split_reasons else None, pump_info)
                        
                        proj["_pump_name"] = pump_info["pump"]["name"]; st.session_state.project = proj
                        st.session_state.results = {"zones": all_zones, "boq": boq, "capex": capex, "opex": opex, "tank": tank, "pump_info": pump_info, "npv": npv, "irr": irr, "lcc": lcc, "advisories": advisories, "split_reasons": split_reasons}
                        st.success(f"✅ Design calculated! {len(all_zones)} zones")
    
    res = st.session_state.get("results")
    
    with tabs[3]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("Hydraulic Design")
            p = res["pump_info"]["pump"]; req_q = res["pump_info"]["req_q"]; req_h = res["pump_info"]["req_h"]
            head_at_q = curve_head_at_q(p["curve"], req_q); npsha = npsh_available(proj.get("suction",2), res["pump_info"]["hf_sub"])
            status = npsh_status(npsha, p["NPSHr"])
            
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Pump", p["name"]); c2.metric("Pump kW", f"{p['kw']} kW"); c3.metric("Tank", f"{res['tank']:.1f} m³"); c4.metric("Req. Q / H", f"{req_q:.1f} / {req_h:.1f}")
            
            st.markdown("### ⚙️ Pump Analysis (Curve + BEP + NPSH)")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("BEP Q", f"{p['BEP_Q']} m³/h"); pc2.metric("BEP H", f"{p['BEP_H']} m"); pc3.metric("Head @ Req Q", f"{head_at_q:.1f} m"); pc4.metric("BEP Score", f"{pump_score(p, req_q, req_h):.1f}")
            
            st.markdown("### 🌊 NPSH Analysis")
            nc1, nc2, nc3 = st.columns(3)
            nc1.metric("NPSHa", f"{npsha} m"); nc2.metric("NPSHr", f"{p['NPSHr']} m"); nc3.metric("Status", {"safe":"✅ Safe","tight":"⚠️ Tight","risk":"❌ Risk"}[status])
            
            with st.expander("📈 Pump Curve"):
                curve_df = pd.DataFrame(p["curve"], columns=["Q (m³/h)","H (m)"]); curve_df["BEP"] = ((curve_df["Q (m³/h)"]==p["BEP_Q"])).map({True:"⭐ BEP",False:""})
                st.dataframe(curve_df, use_container_width=True)
            
            st.markdown("### Zone-by-Zone Hydraulics")
            df = pd.DataFrame([{"Zone": z["zone_label"], "Crop": CROPS[z["crop"]]["ar"], "Area": f"{z['area_val']:.2f} fd", "Flow": f"{z['q_m3h']:.2f} m³/h", "Duration": f"{z['dur']:.1f}h", "TDH": f"{z['tdh']:.1f}m", "Sub Ø": f"Ø{z['d_sub']}mm", "Lat Ø": f"Ø{z['d_lat']}mm", "EU": f"{z['eu']}%", "Interval": f"{z['interval']}d"} for z in res["zones"]])
            st.dataframe(df, use_container_width=True)
    
    with tabs[4]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("🧠 Engineering Advisor")
            for level, msg in res["advisories"]:
                if level == "error": st.error(msg)
                elif level == "warning": st.warning(msg)
                else: st.info(msg)
    
    with tabs[5]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("💰 BOQ & Finance")
            c1,c2,c3 = st.columns(3); c1.metric("CAPEX", f"{res['capex']:,.0f} EGP"); c2.metric("OPEX/Year", f"{res['opex']:,.0f} EGP"); c3.metric("Tank", f"{res['tank']:.1f} m³")
            c1,c2,c3 = st.columns(3); c1.metric("NPV", f"{res['npv']:,.0f} EGP"); c2.metric("IRR", f"{res['irr']}%"); c3.metric("LCC", f"{res['lcc']:,.0f} EGP")
            st.markdown("### BOQ Table"); st.dataframe(pd.DataFrame(res["boq"], columns=["Item","Spec","Cost"]), use_container_width=True)
    
    with tabs[6]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("📄 Reports")
            pdf = build_pdf(proj, res["zones"], res["boq"], res["capex"], res["opex"], res["npv"], res["irr"], res["lcc"], res["tank"], res["pump_info"])
            if pdf: st.download_button("⬇️ Download PDF Report", pdf, file_name=f"{proj['name']}_report.pdf", mime="application/pdf")
            else: st.warning("PDF generation failed")
    
    with tabs[7]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("📐 Exports (CAD + GIS)")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**CAD Export**")
                dxf = build_dxf(proj, res["zones"])
                if dxf: st.download_button("⬇️ Download DXF", dxf, file_name="design.dxf")
                else: st.warning("DXF failed")
            with c2:
                st.markdown("**GIS Export**")
                geojson_str = build_geojson(proj, res["zones"])
                if geojson_str: st.download_button("⬇️ Download GeoJSON", geojson_str, file_name=f"{proj['name']}.geojson", mime="application/geo+json")
                if GIS_OK:
                    shp_zip = build_shapefile_zip(proj, res["zones"])
                    if shp_zip: st.download_button("⬇️ Download Shapefile (ZIP)", shp_zip, file_name=f"{proj['name']}_shp.zip", mime="application/zip")
                else: st.info("ℹ️ Shapefile: ثبّت geopandas+fiona")
            
            plot = build_plot(res["zones"])
            if plot: st.image(plot, caption="Zone Layout", use_column_width=True)

if __name__ == "__main__":
    main()
