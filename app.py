"""
SMART IRRIGATION AI — V12.3 (THE ULTIMATE ENGINE)
Part 1: Imports, Constants, Databases (85+ Crops, Pumps, Regs)
"""
import re, io, math, json, datetime
import numpy as np
import pandas as pd
import streamlit as st

try: import ezdxf; EZDXF_OK = True
except Exception: EZDXF_OK = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon as MplPolygon
    from matplotlib.lines import Line2D
    MPL_OK = True
except Exception: MPL_OK = False

try: import requests; REQUESTS_OK = True
except Exception: REQUESTS_OK = False

try: import simplekml; KML_OK = True
except Exception: KML_OK = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    PDF_OK = True
except Exception: PDF_OK = False

try:
    from shapely.geometry import Polygon
    SHAPELY_OK = True
except Exception: SHAPELY_OK = False

def T(en, ar): 
    return en if st.session_state.get("lang", "ar") == "en" else ar

# ============================================================
# 1. UNITS, CURRENCIES, AND INDEXES
# ============================================================
AREA_UNITS = {
    "Feddan":  {"m2":4200.0,  "ar":"فدان"},
    "Hectare": {"m2":10000.0, "ar":"هكتار"},
    "Acre":    {"m2":4047.0,  "ar":"أكر"},
    "Dunam":   {"m2":1000.0,  "ar":"دونم"},
    "m²":      {"m2":1.0,     "ar":"م²"},
}

CURRENCIES = {
    "EGP": {"ar":"ج.م", "to_egp":1.0},
    "USD": {"ar":"$",   "to_egp":50.0},
    "EUR": {"ar":"€",   "to_egp":54.0},
    "SAR": {"ar":"ر.س","to_egp":13.3},
    "AED": {"ar":"د.إ","to_egp":13.6},
    "GBP": {"ar":"£",   "to_egp":63.0},
}

COUNTRY_INDEX = {
    "EG": 1.00, "SA": 1.35, "AE": 1.40, "GR": 1.20, 
    "US": 1.80, "EU": 1.50, "INTL": 1.0
}

# ============================================================
# 2. SOILS & MEDIA
# ============================================================
SOILS = {
    "Sandy":       {"taw":80, "ar":"رملية"},
    "Loamy Sand":  {"taw":110,"ar":"رملية طميية"},
    "Sandy Loam":  {"taw":140,"ar":"طميية رملية"},
    "Loam":        {"taw":170,"ar":"طميية"},
    "Clay Loam":   {"taw":190,"ar":"طميية طينية"},
    "Clay":        {"taw":210,"ar":"طينية"},
}

LANDSCAPE_MEDIA = {
    "Prepared Agricultural Soil": {"taw":150,"ar":"تربة زراعية مجهزة"},
    "Imported Topsoil":           {"taw":140,"ar":"تربة سطحية مستوردة"},
    "Sand-Soil Mix (60/40)":      {"taw":110,"ar":"خليط رمل/تربة"},
    "Peat-based Mix":             {"taw":180,"ar":"خليط بيت موس"},
    "Artificial Turf Base":       {"taw":100,"ar":"قاعدة نجيل صناعي"},
}

NURSERY_MEDIA = {
    "Peat Moss + Perlite": {"taw":200,"ar":"بيت موس + بيرلايت"},
    "Coco Peat":           {"taw":190,"ar":"كوكوبيت"},
    "Soil-based Mix":      {"taw":160,"ar":"خليط ترابي"},
    "Hydroponic Substrate":{"taw":150,"ar":"ركيزة هيدروبونيك"},
}

# ============================================================
# 3. 85+ CROPS DATABASE
# ============================================================
CROPS = {
    # === Field ===
    "Wheat":      {"kc":1.10,"zr":1.0,"cat":"field","ar":"قمح"},
    "Maize":      {"kc":1.15,"zr":1.0,"cat":"field","ar":"ذرة"},
    "Rice":       {"kc":1.20,"zr":0.6,"cat":"field","ar":"أرز"},
    "Barley":     {"kc":1.05,"zr":1.0,"cat":"field","ar":"شعير"},
    "Alfalfa":    {"kc":1.05,"zr":1.5,"cat":"field","ar":"برسيم"},
    "Cotton":     {"kc":1.15,"zr":1.0,"cat":"field","ar":"قطن"},
    "Sunflower":  {"kc":1.00,"zr":1.0,"cat":"field","ar":"عباد الشمس"},
    "Soybean":    {"kc":1.05,"zr":0.8,"cat":"field","ar":"فول صويا"},
    "Sugar Beet": {"kc":1.10,"zr":1.0,"cat":"field","ar":"بنجر سكر"},
    "Sugarcane":  {"kc":1.25,"zr":1.5,"cat":"field","ar":"قصب سكر"},
    # === Vegetables ===
    "Tomato":     {"kc":1.05,"zr":0.6,"cat":"veg","ar":"طماطم"},
    "Potato":     {"kc":1.10,"zr":0.5,"cat":"veg","ar":"بطاطس"},
    "Pepper":     {"kc":1.00,"zr":0.5,"cat":"veg","ar":"فلفل"},
    "Cucumber":   {"kc":1.05,"zr":0.7,"cat":"veg","ar":"خيار"},
    "Eggplant":   {"kc":1.05,"zr":0.7,"cat":"veg","ar":"باذنجان"},
    "Onion":      {"kc":1.05,"zr":0.4,"cat":"veg","ar":"بصل"},
    "Garlic":     {"kc":1.00,"zr":0.4,"cat":"veg","ar":"ثوم"},
    "Carrot":     {"kc":1.05,"zr":0.5,"cat":"veg","ar":"جزر"},
    "Lettuce":    {"kc":0.95,"zr":0.3,"cat":"veg","ar":"خس"},
    "Cabbage":    {"kc":1.05,"zr":0.5,"cat":"veg","ar":"كرنب"},
    "Watermelon": {"kc":1.05,"zr":1.0,"cat":"veg","ar":"بطيخ"},
    "Melon":      {"kc":1.05,"zr":0.9,"cat":"veg","ar":"شمام"},
    "Strawberry": {"kc":1.00,"zr":0.3,"cat":"veg","ar":"فراولة"},
    "Zucchini":   {"kc":1.00,"zr":0.6,"cat":"veg","ar":"كوسة"},
    "Bean":       {"kc":1.05,"zr":0.6,"cat":"veg","ar":"فاصوليا"},
    # === Orchards ===
    "Olive":       {"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"},
    "Citrus":      {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},
    "Orange":      {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"برتقال"},
    "Lemon":       {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"ليمون"},
    "Mango":       {"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"},
    "Date Palm":   {"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل بلح"},
    "Grape":       {"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"},
    "Apple":       {"kc":0.95,"zr":1.0,"cat":"orchard","ar":"تفاح"},
    "Pear":        {"kc":0.95,"zr":1.0,"cat":"orchard","ar":"كمثرى"},
    "Peach":       {"kc":0.95,"zr":1.0,"cat":"orchard","ar":"خوخ"},
    "Fig":         {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"تين"},
    "Pomegranate": {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"رمان"},
    "Banana":      {"kc":1.10,"zr":0.7,"cat":"orchard","ar":"موز"},
    "Avocado":     {"kc":0.90,"zr":0.8,"cat":"orchard","ar":"أفوكادو"},
    # === Turf ===
    "Turf Bermuda":  {"kc":0.80,"zr":0.3,"cat":"turf","ar":"نجيل برمودا"},
    "Turf Fescue":   {"kc":0.90,"zr":0.3,"cat":"turf","ar":"نجيل فيسكيوب"},
    "Turf Ryegrass": {"kc":0.85,"zr":0.3,"cat":"turf","ar":"نجيل راي"},
    "Turf Zoysia":   {"kc":0.75,"zr":0.3,"cat":"turf","ar":"نجيل زويسيا"},
    # === Shrubs ===
    "Bougainvillea": {"kc":0.55,"zr":0.5,"cat":"shrub","ar":"جهنمية"},
    "Hibiscus":      {"kc":0.90,"zr":0.5,"cat":"shrub","ar":"خطمي"},
    "Lantana":       {"kc":0.55,"zr":0.5,"cat":"shrub","ar":"لانتانا"},
    "Duranta":       {"kc":0.75,"zr":0.6,"cat":"shrub","ar":"دورانتا"},
    "Jasmine":       {"kc":0.75,"zr":0.6,"cat":"shrub","ar":"ياسمين"},
    "Oleander":      {"kc":0.55,"zr":0.7,"cat":"shrub","ar":"دفلة"},
    "Pittosporum":   {"kc":0.70,"zr":0.5,"cat":"shrub","ar":"بيتوسبورم"},
    "Vinca":         {"kc":0.75,"zr":0.4,"cat":"shrub","ar":"ونكا"},
    # === Landscape Trees ===
    "Ficus":         {"kc":0.70,"zr":1.0,"cat":"tree","ar":"فيكس"},
    "Conocarpus":    {"kc":0.55,"zr":1.2,"cat":"tree","ar":"كونوكاربس"},
    "Eucalyptus":    {"kc":0.65,"zr":1.5,"cat":"tree","ar":"كافتوس"},
    "Delonix":       {"kc":0.60,"zr":1.0,"cat":"tree","ar":"بوانسيانا"},
    "Cassia":        {"kc":0.65,"zr":1.0,"cat":"tree","ar":"كاسيا"},
    "Washingtonia":  {"kc":0.75,"zr":1.2,"cat":"tree","ar":"نخيل واشنطونيا"},
    "Phoenix":       {"kc":0.70,"zr":1.2,"cat":"tree","ar":"نخيل فينكس"},
    "Royal Palm":    {"kc":0.80,"zr":1.2,"cat":"tree","ar":"نخيل رويال"},
    # === Flowering ===
    "Rose":          {"kc":0.85,"zr":0.4,"cat":"flower","ar":"ورد"},
    "Petunia":       {"kc":1.00,"zr":0.3,"cat":"flower","ar":"بيتونيا"},
    "Marigold":      {"kc":0.95,"zr":0.3,"cat":"flower","ar":"قطيفة"},
    "Geranium":      {"kc":0.90,"zr":0.4,"cat":"flower","ar":"جرانيوم"},
    "Chrysanthemum": {"kc":1.00,"zr":0.3,"cat":"flower","ar":"أقحوان"},
    "Carnation":     {"kc":0.95,"zr":0.3,"cat":"flower","ar":"قرنفل"},
    "Gerbera":       {"kc":1.05,"zr":0.3,"cat":"flower","ar":"جربيرا"},
    "Gladiolus":     {"kc":1.00,"zr":0.3,"cat":"flower","ar":"جلاديولس"},
    "Dahlia":        {"kc":1.00,"zr":0.4,"cat":"flower","ar":"داليا"},
    "Zinnia":        {"kc":0.95,"zr":0.3,"cat":"flower","ar":"زينيا"},
    "Gazania":       {"kc":0.55,"zr":0.3,"cat":"flower","ar":"جازانيا"},
    "Lavender":      {"kc":0.65,"zr":0.4,"cat":"flower","ar":"لافندر"},
    "Lily":          {"kc":1.00,"zr":0.3,"cat":"flower","ar":"زنبق"},
    "Aster":         {"kc":0.95,"zr":0.3,"cat":"flower","ar":"أستر"},
    # === Foliage ===
    "Ficus Benjamina": {"kc":0.75,"zr":0.6,"cat":"foliage","ar":"فيكس بنجامينا"},
    "Dracaena":        {"kc":0.65,"zr":0.5,"cat":"foliage","ar":"دراسينا"},
    "Schefflera":      {"kc":0.75,"zr":0.5,"cat":"foliage","ar":"شيفليرا"},
    "Aglaonema":       {"kc":0.80,"zr":0.3,"cat":"foliage","ar":"أجلونيما"},
    "Croton":          {"kc":0.85,"zr":0.4,"cat":"foliage","ar":"كروتون"},
    # === Groundcovers ===
    "Wedelia":      {"kc":0.65,"zr":0.2,"cat":"groundcover","ar":"ويدليا"},
    "Asparagus Fern":{"kc":0.75,"zr":0.3,"cat":"groundcover","ar":"اسباراجوس"},
    "Liriope":      {"kc":0.70,"zr":0.2,"cat":"groundcover","ar":"ليريوبي"},
    "Aptenia":      {"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"أبتينيا"},
    "Portulaca":    {"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"بورتولاكا"},
    # === Climbers ===
    "Ivy":          {"kc":0.70,"zr":0.6,"cat":"climber","ar":"لبلاب"},
    "Wisteria":     {"kc":0.70,"zr":0.8,"cat":"climber","ar":"ويستيريا"},
    "Passion Flower":{"kc":0.75,"zr":0.7,"cat":"climber","ar":"زهرة الآلام"},
    # === Succulents ===
    "Aloe Vera":    {"kc":0.35,"zr":0.2,"cat":"succulent","ar":"صبار"},
    "Agave":        {"kc":0.30,"zr":0.3,"cat":"succulent","ar":"أجاف"},
    "Sedum":        {"kc":0.40,"zr":0.2,"cat":"succulent","ar":"سيدم"},
    # === Potted ===
    "Potted Flowering":{"kc":1.10,"zr":0.25,"cat":"pot","ar":"أصص مزهرة"},
    "Potted Foliage":  {"kc":1.00,"zr":0.25,"cat":"pot","ar":"أصص ورقية"},
    "Potted Herb":     {"kc":1.00,"zr":0.20,"cat":"pot","ar":"أصص أعشاب"},
}

PROJECT_CROP_GROUPS = {
    "Agricultural": {
        "🌾 Field": ["Wheat","Maize","Rice","Barley","Alfalfa","Cotton","Sunflower","Soybean","Sugar Beet","Sugarcane"],
        "🥬 Vegetables": ["Tomato","Potato","Pepper","Cucumber","Eggplant","Onion","Garlic","Carrot","Lettuce","Cabbage","Watermelon","Melon","Strawberry","Zucchini","Bean"],
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
    "Greenhouse": {
        "🍅 GH Vegetables": ["Tomato","Cucumber","Pepper","Strawberry"],
    },
    "Nursery": {
        "🌸 Flowers": ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera","Gladiolus","Dahlia","Zinnia","Lavender","Lily","Aster"],
        "🍃 Foliage": ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"],
        "🌳 Shrubs": ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine","Oleander","Pittosporum","Vinca"],
        "🪴 Potted": ["Potted Flowering","Potted Foliage","Potted Herb"],
    },
}

TREE_CROPS = {"Olive","Citrus","Orange","Lemon","Mango","Date Palm","Grape","Apple","Pear","Peach","Fig","Pomegranate","Avocado"}

P_ALLOW = {
    "field":0.50,"veg":0.35,"orchard":0.55,"turf":0.50,"shrub":0.45,
    "tree":0.50,"flower":0.40,"foliage":0.45,"groundcover":0.45,
    "climber":0.45,"succulent":0.30,"pot":0.35,
}

# ============================================================
# 4. IRRIGATION SYSTEMS & REGULATIONS
# ============================================================
IRR_SYSTEMS = {
    "drip": {"ar":"تنقيط", "eff":0.90, "pressure":10.0},
    "micro": {"ar":"ميكرو", "eff":0.85, "pressure":15.0},
    "bubbler": {"ar":"بابلر", "eff":0.85, "pressure":12.0},
    "sprinkler": {"ar":"رشاش", "eff":0.75, "pressure":25.0},
    "surface": {"ar":"غمر", "eff":0.55, "pressure":2.0},
}

REGULATIONS = {
    "INTL": {"name":"دولي","max_h":24,"eff":0.60,"banned":[],"ec":10,"sar":15,"reuse":True,"notes":"FAO Guidelines"},
    "EG": {"name":"مصر","max_h":10,"eff":0.70,"banned":["surface"],"ec":5,"sar":9,"reuse":False,"notes":"قانون 147/2021: منع الغمر في الصحراء"},
    "SA": {"name":"السعودية","max_h":16,"eff":0.75,"banned":["surface"],"ec":5,"sar":9,"reuse":True,"notes":"كفاءة ≥75% إلزامية"},
    "AE": {"name":"الإمارات","max_h":14,"eff":0.75,"banned":["surface"],"ec":5,"sar":9,"reuse":True,"notes":"منع الغمر، قيود على مياه الصرف"},
    "GR": {"name":"اليونان","max_h":14,"eff":0.70,"banned":[],"ec":6,"sar":10,"reuse":True,"notes":"قيود صيفية (11ص-5م)"},
    "EU": {"name":"أوروبا","max_h":24,"eff":0.80,"banned":[],"ec":6,"sar":10,"reuse":True,"notes":"EU Water Framework Directive"},
    "US": {"name":"أمريكا","max_h":24,"eff":0.70,"banned":[],"ec":8,"sar":12,"reuse":True,"notes":"ASABE Standards"},
}

# ============================================================
# 5. PUMPS & FILTERS & PRICES
# ============================================================
FILTERS = ["Screen Filter","Disc Filter","Media Filter","Hydrocyclone"]
FILTER_AR = {"Screen Filter":"فلتر شبكي","Disc Filter":"فلتر ديسكات","Media Filter":"فلتر رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}

PUMPS = [
    {"name":"Grundfos CR 5-10","Q":5,"H":90,"kw":2.2,"eff":65},
    {"name":"Grundfos CR 10-10","Q":10,"H":95,"kw":4.0,"eff":70},
    {"name":"Grundfos CR 15-8","Q":15,"H":80,"kw":5.5,"eff":72},
    {"name":"Lowara e-SV 10","Q":10,"H":70,"kw":3.0,"eff":68},
    {"name":"Lowara e-SV 22","Q":22,"H":75,"kw":7.5,"eff":75},
    {"name":"Ebara EVMS 15","Q":15,"H":85,"kw":5.5,"eff":70},
]

DEFAULT_PRICES = {
    "main":80.0, "sub":45.0, "lat":6.0, "drip":3.0, 
    "control":2500.0, "flush":450.0, "arv":1800.0, 
    "acid":12000.0, "treat":20000.0, "pump_base":15000.0
  }# ============================================================
# 6. AI PARSER & API ENGINES
# ============================================================
def parse_request(text):
    """استخراج البيانات من النص الطبيعي (AI Assistant)"""
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
    """جلب بيانات المناخ الحقيقية من Open-Meteo"""
    if not REQUESTS_OK: return {"eto":5.5, "rain":0.0, "temp":25.0, "hum":50.0, "wind":2.0}
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=15, params={
            "latitude":lat, "longitude":lon,
            "start_date":"2023-07-01", "end_date":"2023-08-31",
            "daily":"et0_fao_evapotranspiration,precipitation_sum,temperature_2m_max,relative_humidity_2m_max,wind_speed_10m_max"
        })
        d = r.json()["daily"]
        return {
            "eto": round(max([v for v in d["et0_fao_evapotranspiration"] if v is not None]+[5.5]), 1),
            "rain": round(np.mean([v for v in d["precipitation_sum"] if v is not None]+[0]), 1),
            "temp": round(max([v for v in d["temperature_2m_max"] if v is not None]+[25]), 1),
            "hum": round(np.mean([v for v in d["relative_humidity_2m_max"] if v is not None]+[50]), 1),
            "wind": round(np.mean([v for v in d["wind_speed_10m_max"] if v is not None]+[10])/3.6, 1)
        }
    except Exception:
        return {"eto":5.5, "rain":0.0, "temp":25.0, "hum":50.0, "wind":2.0}

def fetch_soil(lat, lon):
    """جلب نوع التربة من ISRIC SoilGrids"""
    if not REQUESTS_OK: return "Sandy Loam"
    try:
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query", params=[
            ("lon",lon),("lat",lat),("property","clay"),("property","sand"),("depth","0-30cm")
        ], timeout=10)
        vals = {L["name"]: L["depths"][0]["values"]["mean"]/10.0 for L in r.json()["properties"]["layers"] if L["depths"][0]["values"]["mean"]}
        s, c = vals.get("sand", 50), vals.get("clay", 20)
        if c>=40: return "Clay"
        if c>=25 and s<=45: return "Clay Loam"
        if s>=85: return "Sandy"
        if s>=70: return "Loamy Sand"
        if s>=50: return "Sandy Loam"
        return "Loam"
    except Exception:
        return "Sandy Loam"

def fetch_location_name(lat, lon):
    """جلب اسم المكان من OpenStreetMap"""
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat":lat, "lon":lon, "format":"json", "accept-language":"ar"
        }, headers={"User-Agent":"IrrigationAI/12"}, timeout=8)
        addr = r.json().get("address",{})
        parts = [addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county"), addr.get("state")]
        return ", ".join([p for p in parts if p]) or r.json().get("display_name","")[:60]
    except Exception:
        return None

# ============================================================
# 7. GEOMETRY & MATH HELPERS
# ============================================================
def poly_area(coords):
    """حساب مساحة الـ Polygon (Shoelace Formula)"""
    if len(coords) < 3: return 0
    lat0 = sum(c[0] for c in coords) / len(coords)
    pts = [(c[1]*111320*math.cos(math.radians(lat0)), c[0]*111320) for c in coords]
    s = sum(pts[i][0]*pts[(i+1)%len(pts)][1] - pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
    return abs(s) / 2

def poly_centroid(coords):
    """حساب مركز الأرض (Centroid)"""
    if len(coords) < 3: return 30.0, 30.0
    lat0 = sum(c[0] for c in coords) / len(coords)
    mlat, mlon = 111320, 111320*math.cos(math.radians(lat0))
    pts = [(c[1]*mlon, c[0]*mlat) for c in coords]
    a = cx = cy = 0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i+1)%len(pts)]
        cr = x1*y2 - x2*y1
        a += cr
        cx += (x1+x2)*cr
        cy += (y1+y2)*cr
    a /= 2
    return (round(cy/(6*a)/mlat, 6), round(cx/(6*a)/mlon, 6)) if a != 0 else (30.0, 30.0)

def select_pipe_diameter(q_m3h, v_target=1.2):
    """اختيار قطر الماسورة بناءً على التصرف والسرعة"""
    if q_m3h <= 0: return 16
    d_m = math.sqrt((4 * (q_m3h/3600.0)) / (math.pi * v_target))
    for d in [16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 160, 200]:
        if d >= d_m * 1000: return d
    return 200

def hazen_williams(L, q_m3h, d_mm, C=140):
    """حساب فواقد الاحتكاك (Hazen-Williams)"""
    if q_m3h <= 0 or d_mm <= 0: return 0
    return 10.67 * L * ((q_m3h/3600)**1.852) / ((C**1.852) * ((d_mm/1000)**4.87))

# ============================================================
# 8. DESIGN & SELECTION ENGINES
# ============================================================
def choose_system(cat, ec, slope, wind):
    """اختيار نظام الري تلقائياً"""
    if ec > 5 or slope > 5: return "drip"
    if cat in ["orchard", "veg"]: return "drip"
    if cat == "field": return "sprinkler"
    if cat == "turf": return "sprinkler"
    if wind > 4.5: return "drip" # Avoid spray drift
    return "micro"

def select_pump(q_m3h, tdh):
    """اختيار مضخة من الكتالوج"""
    for p in PUMPS:
        if p["Q"] >= q_m3h and p["H"] >= tdh:
            return p
    return PUMPS[-1] # Return largest if nothing fits

def water_treatment(ec, ph, sar):
    """تحديد معالجة المياه المطلوبة"""
    t = []
    if ec > 5: t.append("Leaching Program (غسيل أملاح)")
    if ph > 8.2: t.append("Acid Injection (حقن حامض)")
    if sar > 9: t.append("Gypsum Application (إضافة جبس)")
    return t

def design_zone(z, proj):
    """المحرك الأساسي لتصميم الزونة الواحدة"""
    c = CROPS[z["crop"]]
    eff = IRR_SYSTEMS[z["system"]]["eff"]
    
    # Soil TAW
    taw = SOILS.get(z.get("soil"), 140)["taw"] if proj["project_type"] in ["Agricultural","Greenhouse"] else LANDSCAPE_MEDIA.get(z.get("media"), 150)["taw"]
    
    # Water Balance
    raw_mm = P_ALLOW[c["cat"]] * taw * c["zr"]
    etc = proj["eto"] * c["kc"]
    if proj["project_type"] == "Greenhouse": etc *= 0.7 # GH multiplier
    
    max_i = 3 if c["cat"] in ("veg","flower") else 7 if c["cat"] in ("orchard","tree") else 14 if c["cat"]=="succulent" else 5
    interval = max(1, min(int(round(raw_mm/etc if etc>0 else max_i)), max_i))
    
    area = z["area_val"] * AREA_UNITS[z["area_unit"]]["m2"]
    vol = ((etc * interval) / eff) * area / 1000
    
    # Flow Calc
    if z["system"] in ("drip","micro"):
        emitters = int(area / (z.get("esp",0.5) * z.get("lsp",0.8)))
        q_m3h = (emitters * z.get("q",2.0)) / 1000
    elif z["system"] == "sprinkler":
        emitters = int(area / (z.get("esp",12) * z.get("lsp",12)))
        q_m3h = (emitters * 1000) / 1000
    else:
        emitters = int(area / (z.get("esp",5) * z.get("lsp",6)))
        q_m3h = (emitters * 100) / 1000
        
    dur = vol / q_m3h if q_m3h > 0 else 0
    
    # Hydraulics
    d_lat = select_pipe_diameter(q_m3h / max(1, int(math.sqrt(area)/z.get("lsp",0.8))), v_target=0.8)
    d_sub = select_pipe_diameter(q_m3h, v_target=1.2)
    hf_sub = hazen_williams(math.sqrt(area)*2, q_m3h, d_sub)
    tdh = proj.get("elev",0) + proj.get("suction",2) + hf_sub + IRR_SYSTEMS[z["system"]]["pressure"] + 5
    
    # Water Per Tree
    water_tree = None
    if z["crop"] in TREE_CROPS:
        daily = etc * (z.get("esp",5) * z.get("lsp",6))
        water_tree = {"daily": round(daily,1), "event": round(daily*interval,1)}
        
    return {**z, "etc":etc, "raw_mm":raw_mm, "interval":interval, "vol":vol, "q_m3h":q_m3h, "dur":dur, 
            "d_sub":d_sub, "d_lat":d_lat, "tdh":tdh, "water_tree":water_tree, 
            "treat":water_treatment(proj["ec"], proj["ph"], proj["sar"])}

def build_schedule(zones, strategy, source_cap):
    """بناء جدول التشغيل (Sequential أو Parallel)"""
    if strategy == "sequential":
        cur = 5.0
        for z in zones:
            z["start"] = cur
            z["end"] = cur + z["dur"]
            cur = z["end"] + 0.25
        return zones, cur - 5.0
    else:
        timeline = []
        for z in sorted(zones, key=lambda x: -x["dur"]):
            found = False
            for t_int in range(0, 96):
                t = 5.0 + t_int*0.25
                overlap = sum(sl["flow"] for sl in timeline if sl["start"] < t + z["dur"] and sl["end"] > t)
                if overlap + z["q_m3h"] <= source_cap:
                    z["start"] = t
                    z["end"] = t + z["dur"]
                    timeline.append({"start": t, "end": z["end"], "flow": z["q_m3h"]})
                    found = True
                    break
            if not found:
                max_e = max((sl["end"] for sl in timeline), default=5.0)
                z["start"] = max_e + 0.25
                z["end"] = z["start"] + z["dur"]
                timeline.append({"start": z["start"], "end": z["end"], "flow": z["q_m3h"]})
        return zones, max(z["end"] for z in zones) - 5.0

def check_compliance(proj, zones, total_h):
    """فحص الامتثال للوائح الدولة"""
    reg = REGULATIONS[proj["country"]]
    issues = []
    if total_h > reg["max_h"]:
        issues.append(("error", f"⛔ ساعات التشغيل {total_h:.1f}h تتجاوز الحد المسموح {reg['max_h']}h في {reg['name']}"))
    for z in zones:
        if z["system"] in reg["banned"]:
            issues.append(("error", f"⛔ زونة {z['name']}: نظام الري ({z['system']}) ممنوع في {reg['name']}"))
    if proj["ec"] > reg["ec"]: 
        issues.append(("error", f"⛔ ملوحة المياه ({proj['ec']}) تتجاوز الحد المسموح ({reg['ec']})"))
    if proj["sar"] > reg["sar"]: 
        issues.append(("error", f"⛔ SAR ({proj['sar']}) يتجاوز الحد المسموح ({reg['sar']})"))
    return issues, reg

# ============================================================
# 9. BOQ & FINANCIALS
# ============================================================
def compute_boq(proj, zones, total_h):
    """حساب الكميات (BOQ) والتكاليف (CAPEX / OPEX)"""
    idx = COUNTRY_INDEX.get(proj["country"], 1.0)
    rows = []
    
    peak_q = max(z["q_m3h"] for z in zones) if zones else 0
    max_tdh = max(z["tdh"] for z in zones) if zones else 50
    pump = select_pump(peak_q, max_tdh)
    
    # Pump & Controller
    rows.append(("Pump & Motor", f"{pump['name']} ({pump['kw']} kW)", DEFAULT_PRICES["pump_base"] * (pump['kw']/2) * idx))
    rows.append(("Controller Panel", "Auto Starter", 5000 * idx))
    
    # Pipes & Fittings
    d_main = select_pipe_diameter(peak_q)
    rows.append(("Main Pipe", f"Ø{d_main}mm", 100 * DEFAULT_PRICES["main"] * idx))
    
    for z in zones:
        rows.append((f"Zone {z['name']} - Sub-main", f"Ø{z['d_sub']}mm", 50 * DEFAULT_PRICES["sub"] * idx))
        rows.append((f"Zone {z['name']} - Lateral", f"Ø{z['d_lat']}mm", 200 * DEFAULT_PRICES["lat"] * idx))
        rows.append((f"Zone {z['name']} - Control Valve", "1", DEFAULT_PRICES["control"] * idx))
        
    # Accessories
    total_area = sum(z["area_val"] * AREA_UNITS[z["area_unit"]]["m2"] for z in zones)
    hydrants = max(1, int(total_area / 10000))
    rows.append(("Hydrants", f"{hydrants} units", hydrants * 1500 * idx))
    rows.append(("Filter", FILTER_AR.get(proj["filter"],""), FILTER_PRICE.get(proj["filter"],0) * idx))
    rows.append(("Air/Flush Valves", "Set", 4 * DEFAULT_PRICES["arv"] * idx))
    
    if proj["ph"] > 8.2: rows.append(("Acid Injection", "1 unit", DEFAULT_PRICES["acid"] * idx))
    if proj["ec"] > 5: rows.append(("Water Treatment", "1 unit", DEFAULT_PRICES["treat"] * idx))
    
    subtotal = sum(r[2] for r in rows)
    rows.append(("Fittings & Valves (10%)", "-", subtotal * 0.1))
    total_capex = subtotal * 1.1
    
    # OPEX
    kwh = (pump['kw'] * total_h * 365) / (pump['eff']/100)
    energy_cost = kwh * 0.15 * idx
    maintenance = total_capex * 0.03
    opex = energy_cost + maintenance
    
    return rows, total_capex, opex, pump

# ============================================================
# 10. EXPORTS (PDF, KML, DXF, PLOT)
# ============================================================
def build_pdf(proj, zones, boq, total_h, pump):
    """توليد تقرير PDF متكامل"""
    if not PDF_OK: return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = [
        Paragraph(f"Engineering Report: {proj['name']}", getSampleStyleSheet()['Title']),
        Spacer(1, 12)
    ]
    
    elements.append(Paragraph(f"<b>Project Type:</b> {proj['project_type']}", getSampleStyleSheet()['Normal']))
    elements.append(Paragraph(f"<b>Pump Selected:</b> {pump['name']} ({pump['kw']} kW, Eff: {pump['eff']}%)", getSampleStyleSheet()['Normal']))
    elements.append(Paragraph(f"<b>Total Operating Hours:</b> {total_h:.1f} h", getSampleStyleSheet()['Normal']))
    elements.append(Paragraph(f"<b>Source Capacity:</b> {proj['src_q']} m3/h", getSampleStyleSheet()['Normal']))
    elements.append(Spacer(1, 12))
    
    # Zones Table
    data = [["Zone", "Crop", "ETc", "Interval", "Vol (m3)", "Water/Tree"]]
    for z in zones:
        wt = f"{z['water_tree']['daily']} L/d" if z.get("water_tree") else "-"
        data.append([z['name'], z['crop'], f"{z['etc']:.1f}", f"{z['interval']}d", f"{z['vol']:.1f}", wt])
    
    t = Table(data)
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.grey)]))
    elements.append(t)
    elements.append(Spacer(1, 12))
    
    # BOQ Table
    elements.append(Paragraph("<b>Bill of Quantities</b>", getSampleStyleSheet()['Heading2']))
    bdata = [["Item", "Cost"]] + [[r[0], f"{r[2]:,.0f}"] for r in boq]
    bt = Table(bdata)
    bt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
    elements.append(bt)
    
    doc.build(elements)
    buf.seek(0)
    return buf

def build_kml(proj):
    """توليد ملف KML لفتحه على Google Earth"""
    if not KML_OK or "poly" not in st.session_state or not st.session_state["poly"]: 
        return None
    kml = simplekml.Kml()
    kml.newpolygon(name=proj["name"], outerboundaryis=[(c[1], c[0]) for c in st.session_state["poly"]])
    return kml.kml()

def build_geojson(proj):
    """توليد ملف GeoJSON"""
    if "poly" not in st.session_state or not st.session_state["poly"]: 
        return None
    return json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[c[1],c[0]] for c in st.session_state["poly"]]]}}]})

def build_plot(proj, zones):
    """رسم المخطط الهندسي (Plot)"""
    fig, ax = plt.subplots(figsize=(10, 8))
    poly_coords = st.session_state.get("poly", [])
    
    if len(poly_coords) >= 3 and SHAPELY_OK:
        poly = Polygon([(c[1], c[0]) for c in poly_coords])
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.1, fc='green', ec='black')
        ax.plot(x, y, color='black', lw=2)
        
        minx, miny, maxx, maxy = poly.bounds
        W, H = maxx-minx, maxy-miny
        
        # Draw zones (conceptual division inside polygon)
        for i, z in enumerate(zones):
            ax.plot([minx, maxx], [miny + (i/len(zones))*H]*2, color='green', lw=2, ls='--')
        ax.text((minx+maxx)/2, maxy, "Zones layout (Conceptual)", ha='center', fontsize=12, bbox=dict(fc='white'))
    else:
        # Rectangular fallback
        W = math.sqrt(sum(z["area_val"] * AREA_UNITS[z["area_unit"]]["m2"] for z in zones))
        ax.add_patch(Rectangle((0,0), W, W*0.8, fill=False, lw=2))
        ax.plot([W/2, W/2], [0, W*0.8], color="blue", lw=3)
        
    legend_elements = [
        Line2D([0],[0], color='black', lw=2, label='Boundary'),
        Line2D([0],[0], color='green', lw=2, ls='--', label='Zones'),
        Line2D([0],[0], color='blue', lw=3, label='Main Pipe')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    ax.axis("off")
    return fig

def build_dxf(proj, zones):
    """توليد ملف DXF للـ AutoCAD"""
    if not EZDXF_OK: return None
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    
    layers = ["MAIN","SUBMAIN","LATERAL","EMITTER","FILTER","FERTIGATION","AIR_RELEASE","FLUSH","CONTROL","HYDRANT","PUMP","TITLE"]
    for l in layers:
        if l not in doc.layers: doc.layers.add(l)
    
    W = math.sqrt(sum(z["area_val"] * AREA_UNITS[z["area_unit"]]["m2"] for z in zones))
    msp.add_lwpolyline([(0,0),(W,0),(W,W*0.8),(0,W*0.8),(0,0)], dxfattribs={"layer":"MAIN"})
    msp.add_circle((W/2, -5), 2, dxfattribs={"layer":"PUMP"})
    msp.add_circle((W*0.1, W*0.1), 1, dxfattribs={"layer":"FILTER"})
    
    y = 0
    for z in zones:
        z_h = (W*0.8) * (z["area_val"] / sum(zz["area_val"] for zz in zones))
        msp.add_line((0,y), (W,y), dxfattribs={"layer":"SUBMAIN"})
        msp.add_circle((W*0.9, y+z_h/2), 0.5, dxfattribs={"layer":"CONTROL"})
        y += z_h
        
    buf = io.BytesIO()
    doc.saveas(buf)
    buf.seek(0)# ============================================================
# 11. MAIN UI (Streamlit)
# ============================================================
def main():
    st.set_page_config(page_title="Irrigation AI V12 Ultimate", layout="wide", initial_sidebar_state="expanded")
    
    # --- Session Init ---
    if "zones" not in st.session_state: st.session_state.zones = []
    if "lang" not in st.session_state: st.session_state.lang = "ar"
    if "poly" not in st.session_state: st.session_state.poly = []
    
    # --- Sidebar ---
    with st.sidebar:
        st.title("💧 Irrigation AI V12")
        lang = st.radio("Language / اللغة", ["العربية", "English"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        st.markdown("---")
        st.caption("Ultimate Engineering Suite")
        st.caption("© 2025")
    
    st.title("💧 " + T("Smart Irrigation AI V12", "الري الذكي V12"))
    
    tabs = st.tabs([
        "1️⃣ " + T("Setup", "الإعداد"),
        "2️⃣ " + T("Zones", "الزونات"),
        "3️⃣ " + T("Design", "التصميم"),
        "4️⃣ " + T("Reports", "التقارير"),
        "5️⃣ " + T("Plot", "المخطط"),
        "6️⃣ " + T("BOQ & Finance", "الكميات والمالية"),
        "7️⃣ " + T("Exports", "التصدير")
    ])

    # ============ TAB 1: SETUP ============
    with tabs[0]:
        st.markdown("### 🤖 " + T("AI Assistant (Natural Language)", "المساعد الذكي (لغة طبيعية)"))
        q = st.text_input(T("Describe your project...", "اكتب وصف مشروعك..."), 
                          placeholder="e.g., 25 feddans olive in Matrouh with well")
        
        parsed = {"area": None, "crop": None, "loc": None, "source": None, "country": "EG"}
        if q:
            parsed = parse_request(q)
            if parsed["area"]:
                st.success(f"🔎 {T('Parsed', 'تم الاستخراج')}: {parsed}")

        st.markdown("---")
        st.markdown("### ⚙️ " + T("Project Details", "بيانات المشروع"))
        
        mode = st.radio(T("Mode", "وضع الاستخدام"), ["Simplified", "Advanced"], horizontal=True,
                        format_func=lambda x: "👤 " + T("Simplified (Client)", "مبسط (للعميل)") if x == "Simplified" else "👨‍🔧 " + T("Advanced (Engineer)", "متقدم (للمهندس)"))
        
        c1, c2, c3 = st.columns(3)
        with c1: 
            pname = st.text_input(T("Project Name", "اسم المشروع"), "My Farm")
        with c2: 
            ptype = st.selectbox(T("Project Type", "نوع المشروع"), ["Agricultural", "Landscape", "Greenhouse", "Nursery"],
                                 format_func=lambda x: {"Agricultural":"🌾 إنتاج زراعي", "Landscape":"🌳 لاندسكيب", "Greenhouse":"🏠 بيوت محمية", "Nursery":"🪴 مشتل"}.get(x, x))
        with c3: 
            country = st.selectbox(T("Country", "الدولة"), list(REGULATIONS.keys()), 
                                   format_func=lambda x: REGULATIONS[x]["name"])
            reg = REGULATIONS[country]
            st.caption(f"📜 {reg['notes']}")

        st.markdown("---")
        st.markdown("### 📍 " + T("Location & Area", "الموقع والمساحة"))
        
        # Search Location
        sc1, sc2 = st.columns([3, 1])
        with sc1:
            search_q = st.text_input(T("Search Location (e.g. Larissa, Greece)", "ابحث عن الموقع (مثال: اليونان، لاريسا)"), 
                                     value=parsed.get("loc") or "")
        with sc2:
            st.write(""); st.write("") # Spacer
            if st.button("🔍 " + T("Search", "بحث"), use_container_width=True) and search_q and REQUESTS_OK:
                try:
                    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": search_q, "format": "json", "limit": 1}, headers={"User-Agent": "IrrigationAI/12"}, timeout=8)
                    if r.json():
                        st.session_state["lat"] = float(r.json()[0]["lat"])
                        st.session_state["lon"] = float(r.json()[0]["lon"])
                        st.success("✅ " + T("Location Found", "تم العثور على الموقع"))
                except Exception:
                    st.error("API Error")

        lat = st.session_state.get("lat", 30.0)
        lon = st.session_state.get("lon", 30.0)

        area_mode = st.radio(T("Area Mode", "طريقة تحديد المساحة"), ["Polygon", "Manual"], horizontal=True)
        
        if area_mode == "Polygon":
            txt = st.text_area(T("Coords (lat, lon per line)", "إحداثيات الأرض (خط عرض، خط طول)"), 
                               "30.5010, 30.4990\n30.5011, 30.5012\n30.4999, 30.5009\n30.5001, 30.4993", height=120)
            coords = []
            for ln in txt.split("\n"):
                try:
                    parts = ln.split(",")
                    coords.append((float(parts[0]), float(parts[1])))
                except Exception:
                    pass
            
            if len(coords) >= 3:
                st.session_state["poly"] = coords
                a_m2 = poly_area(coords)
                area_val = a_m2 / 4200.0
                area_unit = "Feddan"
                lat, lon = poly_centroid(coords)
                st.info(f"✅ {T('Calculated Area', 'المساحة المحسوبة')}: **{a_m2:,.0f} m²** = **{area_val:.2f} {T('Feddan', 'فدان')}**")
                st.caption(f"📍 {T('Centroid', 'المركز')}: {lat:.4f}, {lon:.4f}")
            else:
                st.warning(T("Enter at least 3 points.", "أدخل 3 نقاط على الأقل."))
                area_val = 0
                area_unit = "Feddan"
        else:
            c1, c2 = st.columns(2)
            with c1: area_val = st.number_input(T("Area", "المساحة"), 0.1, value=parsed.get("area") or 5.0)
            with c2: area_unit = st.selectbox(T("Unit", "الوحدة"), list(AREA_UNITS.keys()), format_func=lambda x: AREA_UNITS[x]["ar"])
            st.session_state["poly"] = []

        if st.button("🌤️ " + T("Fetch Real Climate & Soil", "جلب بيانات المناخ والتربة")):
            with st.spinner(T("Fetching from APIs...", "جاري الجلب من الخدمات...")):
                clim = fetch_climate(lat, lon)
                soil = fetch_soil(lat, lon)
                loc_name = fetch_location_name(lat, lon)
                st.session_state["eto"] = clim["eto"]
                st.session_state["wind"] = clim["wind"]
                st.session_state["soil"] = soil
                st.success(f"✅ ETo: {clim['eto']} mm/d | Temp: {clim['temp']}°C | Wind: {clim['wind']} m/s | Soil: {soil}")
                if loc_name: st.info(f"📍 {loc_name}")

        eto = st.session_state.get("eto", 5.5)
        wind = st.session_state.get("wind", 2.0)
        soil = st.session_state.get("soil", "Sandy Loam")

        st.markdown("---")
        st.markdown("### 💧 " + T("Water Source & Strategy", "مصدر المياه والاستراتيجية"))
        
        wsrc = st.selectbox(T("Water Source", "مصدر المياه"), ["Nile", "Well", "Reclaimed", "Mixed"])
        
        if mode == "Simplified":
            pipe = st.selectbox(T("Source Pipe Diameter", "ماسورة المصدر"), ["1.5\"", "2\"", "3\"", "4\"", "6\"", "Canal"])
            q_map = {"1.5\"": 8.0, "2\"": 15.0, "3\"": 30.0, "4\"": 50.0, "6\"": 100.0, "Canal": 200.0}
            src_q = q_map.get(pipe, 40.0)
            
            if wsrc == "Nile": ec, ph, sar, filt = 0.8, 7.8, 2.5, "Media Filter"
            elif wsrc == "Well": ec, ph, sar, filt = 2.5, 8.0, 4.5, "Media Filter"
            elif wsrc == "Reclaimed": ec, ph, sar, filt = 1.8, 7.2, 6.0, "Disc Filter"
            else: ec, ph, sar, filt = 1.5, 7.2, 5.0, "Disc Filter"
            
            st.info("🤖 " + T("The Expert System has derived Water Quality, Filter, and Capacity automatically.", "الوكيل الذكي استنتج جودة المياه، الفلتر، والقدرة تلقائياً."))
        else:
            c1, c2, c3 = st.columns(3)
            with c1: ec = st.number_input("EC (dS/m)", value=1.2)
            with c2: ph = st.number_input("pH", value=7.5)
            with c3: sar = st.number_input("SAR", value=3.0)
            
            c1, c2, c3 = st.columns(3)
            with c1: filt = st.selectbox(T("Filter", "الفلتر"), list(FILTER_AR.keys()), format_func=lambda x: FILTER_AR[x])
            with c2: src_q = st.number_input(T("Source Capacity (m³/h)", "قدرة المصدر"), value=40.0)
            with c3: curr = st.selectbox(T("Currency", "العملة"), list(CURRENCIES.keys()))

        c1, c2 = st.columns(2)
        with c1: pc_choice = st.radio(T("Dripper Type", "نوع المنقط"), ["PC Dripper", "Non-PC Dripper"], horizontal=True)
        with c2: strat = st.radio(T("Operation Strategy", "استراتيجية التشغيل"), ["sequential", "parallel"], horizontal=True,
                                  format_func=lambda x: "🔄 تتابعي" if x == "sequential" else "⚡ متوازي")

        st.session_state.project = {
            "name": pname, "project_type": ptype, "country": country, "eto": eto, "wind": wind, 
            "ec": ec, "ph": ph, "sar": sar, "wsrc": wsrc, "filter": filt, "src_q": src_q, 
            "curr": st.session_state.get("curr", "EGP"), "mode": mode, "strategy": strat, 
            "area_unit": area_unit, "lat": lat, "lon": lon, "pc": pc_choice, "slope": 0.0, "elev": 0.0, "suction": 2.0
        }

    proj = st.session_state.project
    if not proj: return

    # ============ TAB 2: ZONES ============
    with tabs[1]:
        st.markdown("### 🌾 " + T("Zones Manager", "إدارة الزونات"))
        
        if st.button("➕ " + T("Add Zone", "إضافة زونة")):
            st.session_state.zones.append({
                "id": len(st.session_state.zones)+1, "name": f"Z{len(st.session_state.zones)+1}", 
                "crop": "Tomato", "area_val": 1.0, "area_unit": proj["area_unit"], 
                "system": "drip", "q": 2.0, "esp": 0.3, "lsp": 0.8, "soil": soil, "media": "Prepared Agricultural Soil"
            })
            st.rerun()
            
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']} ({CROPS[z['crop']]['ar']})", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: z["name"] = st.text_input(T("Name", "الاسم"), z["name"], key=f"n{i}")
                
                grp = PROJECT_CROP_GROUPS[proj["project_type"]]
                with c2: 
                    grp_sel = st.selectbox(T("Group", "المجموعة"), list(grp.keys()), key=f"g{i}")
                with c3: 
                    z["crop"] = st.selectbox(T("Crop", "المحصول"), grp[grp_sel], format_func=lambda x: CROPS[x]['ar'], key=f"c{i}")
                
                c1, c2, c3 = st.columns(3)
                with c1: 
                    z["area_val"] = st.number_input(T("Area", "المساحة"), value=z["area_val"], key=f"a{i}")
                with c2: 
                    z["area_unit"] = st.selectbox(T("Unit", "الوحدة"), list(AREA_UNITS.keys()), index=list(AREA_UNITS.keys()).index(z["area_unit"]), key=f"au{i}")
                with c3:
                    if proj["project_type"] in ["Agricultural", "Greenhouse"]: 
                        z["soil"] = st.selectbox(T("Soil", "التربة"), list(SOILS.keys()), index=list(SOILS.keys()).index(z.get("soil", "Sandy Loam")), key=f"so{i}")
                    else: 
                        z["media"] = st.selectbox(T("Media", "البيئة"), list(LANDSCAPE_MEDIA.keys()), key=f"m{i}")
                
                auto_sys = choose_system(CROPS[z["crop"]]["cat"], proj["ec"], proj["slope"], proj["wind"])
                
                if proj["mode"] == "Advanced":
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: z["system"] = st.selectbox(T("System", "النظام"), list(IRR_SYSTEMS.keys()), index=list(IRR_SYSTEMS.keys()).index(auto_sys), key=f"s{i}")
                    with c2: z["q"] = st.number_input(T("Emitter q (L/h)", "تصرف المنقط"), value=z["q"], key=f"q{i}")
                    with c3: z["esp"] = st.number_input(T("Spacing (m)", "مسافة النبات"), value=z["esp"], key=f"e{i}")
                    with c4: z["lsp"] = st.number_input(T("Row Spacing (m)", "مسافة الصف"), value=z["lsp"], key=f"l{i}")
                else:
                    z["system"] = auto_sys
                    st.caption(f"🤖 {T('Auto-selected System', 'النظام المختار تلقائياً')}: **{IRR_SYSTEMS[auto_sys]['ar']}**")
                
                if st.button("🗑️ " + T("Delete", "حذف"), key=f"d{i}"):
                    st.session_state.zones.pop(i)
                    st.rerun()

    zones = st.session_state.zones
    if not zones:
        st.info("👈 " + T("Add at least one zone to start designing.", "أضف زونة واحدة على الأقل لبدء التصميم."))
        return

    # --- CALCULATIONS ---
    designed = [design_zone(z, proj) for z in zones]
    designed, total_h = build_schedule(designed, proj["strategy"], proj["src_q"])
    issues, reg = check_compliance(proj, designed, total_h)
    boq_rows, capex, opex, pump = compute_boq(proj, designed, total_h)
    payback = f"{capex/(50000-opex):.1f} Years" if (50000-opex) > 0 else "N/A"

    # ============ TAB 3: DESIGN & DASHBOARD ============
    with tabs[2]:
        st.markdown("### 📊 " + T("Dashboard", "لوحة النتائج"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(T("Total Hours", "ساعات التشغيل"), f"{total_h:.1f} h")
        c2.metric(T("Daily Water", "مياه يومية"), f"{sum(z['vol']/z['interval'] for z in designed):.1f} m³")
        c3.metric(T("Peak Flow", "أعلى تصرف"), f"{max(z['q_m3h'] for z in designed):.1f} m³/h")
        c4.metric(T("Pump Power", "قدرة المضخة"), f"{pump['kw']} kW")
        
        if issues:
            for sev, msg in issues: st.error(msg)
        else:
            st.success("✅ " + T("Design is compliant with local regulations.", "التصميم مطابق للوائح الدولة."))

        st.markdown("---")
        st.markdown("### 🌾 " + T("Zone Details & Warnings", "تفاصيل الزونات والتحذيرات"))
        
        for z in designed:
            st.markdown(f"#### ▶ {z['name']} ({CROPS[z['crop']]['ar']})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ETc (mm/d)", f"{z['etc']:.1f}")
            c2.metric(T("Flow", "التصرف"), f"{z['q_m3h']:.2f} m³/h")
            c3.metric(T("Duration", "المدة"), f"{z['dur']:.1f} h")
            c4.metric(T("Schedule", "الجدول"), f"{z['start']:.1f}h - {z['end']:.1f}h")
            
            if z.get("water_tree"): 
                st.info(f"🌳 {T('Water per Tree', 'مياه الشجرة')}: {z['water_tree']['daily']} L/day | {z['water_tree']['event']} L/event")
            
            # Warnings
            v = (z["q_m3h"] / 3600) / (math.pi * (z["d_sub"] / 2000)**2) if z["d_sub"] > 0 else 0
            if v < 0.6: st.warning(f"⚠️ {T('Low Velocity', 'سرعة منخفضة')} ({v:.2f} m/s) - {T('Sediment risk', 'خطر ترسيب')}")
            if v > 2.5: st.warning(f"⚠️ {T('High Velocity', 'سرعة مرتفعة')} ({v:.2f} m/s) - {T('Erosion risk', 'خطر تآكل')}")
            if proj["pc"] == "Non-PC Dripper" and proj["slope"] > 3: 
                st.error("⛔ " + T("Use PC Drippers for sloped terrain.", "استخدم منقطات PC للأراضي المنحدرة."))
            
            for t in z["treat"]: 
                st.warning(f"💧 {T('Water Treatment Required', 'معالجة مياه مطلوبة')}: {t}")

    # ============ TAB 4: REPORTS ============
    with tabs[3]:
        st.markdown("### 📄 " + T("Engineering Reports", "التقارير الهندسية"))
        if PDF_OK:
            pdf = build_pdf(proj, designed, boq_rows, total_h, pump)
            if pdf: 
                st.download_button(
                    label="⬇️ " + T("Download Full PDF Report", "تحميل التقرير الهندسي (PDF)"),
                    data=pdf, 
                    file_name=f"{proj['name']}_report.pdf", 
                    mime="application/pdf",
                    use_container_width=True
                )
        else: 
            st.warning(T("Install `reportlab` for PDF export.", "قم بتثبيت `reportlab` لتصدير PDF."))

    # ============ TAB 5: PLOT ============
    with tabs[4]:
        st.markdown("### 🗺️ " + T("Hydraulic Plot", "المخطط الهيدروليكي"))
        if MPL_OK:
            fig = build_plot(proj, designed)
            st.pyplot(fig)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150)
            buf.seek(0)
            st.download_button(
                label="⬇️ " + T("Download Image (PNG)", "تحميل الصورة (PNG)"),
                data=buf, 
                file_name="layout.png", 
                mime="image/png",
                use_container_width=True
            )
        else:
            st.error(T("Matplotlib is missing.", "مكتبة Matplotlib غير موجودة."))

    # ============ TAB 6: BOQ & FINANCE ============
    with tabs[5]:
        st.markdown("### 💰 " + T("Bill of Quantities & Financials", "الكميات والتحليل المالي"))
        
        df = pd.DataFrame(boq_rows, columns=[T("Item", "البند"), T("Spec", "المواصفات"), f"{T('Cost', 'التكلفة')} ({proj['curr']})"])
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric(T("CAPEX", "التكلفة الرأسمالية"), f"{capex:,.0f} {proj['curr']}")
        c2.metric(T("Annual OPEX", "التشغيل السنوي"), f"{opex:,.0f} {proj['curr']}")
        c3.metric(T("Payback Period", "فترة الاسترداد"), payback)

    # ============ TAB 7: EXPORTS ============
    with tabs[6]:
        st.markdown("### 📐 " + T("CAD & GIS Exports", "تصدير ملفات CAD و GIS"))
        
        c1, c2 = st.columns(2)
        with c1:
            dxf = build_dxf(proj, designed)
            if dxf: 
                st.download_button(
                    label="⬇️ " + T("Download DXF (AutoCAD)", "تحميل ملف DXF (أوتوكاد)"),
                    data=dxf, 
                    file_name=f"{proj['name']}_design.dxf",
                    use_container_width=True
                )
            else:
                st.warning(T("ezdxf is missing.", "مكتبة ezdxf غير موجودة."))
                
        with c2:
            if KML_OK and "poly" in st.session_state and st.session_state["poly"]:
                kml_str = build_kml(proj)
                if kml_str: 
                    st.download_button(
                        label="⬇️ " + T("Download KML (Google Earth)", "تحميل KML (جوجل إيرث)"),
                        data=kml_str.encode('utf-8'), 
                        file_name=f"{proj['name']}_farm.kml", 
                        mime="application/vnd.google-earth.kml+xml",
                        use_container_width=True
                    )
            
            if "poly" in st.session_state and st.session_state["poly"]:
                geojson_str = build_geojson(proj)
                if geojson_str: 
                    st.download_button(
                        label="⬇️ " + T("Download GeoJSON", "تحميل GeoJSON"),
                        data=geojson_str, 
                        file_name=f"{proj['name']}_farm.geojson",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()
    return buf
