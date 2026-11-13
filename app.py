"""
SMART IRRIGATION AI — V11.1 (Engineering Office Agent)
=======================================================
Fixes: Streamlit state crash on Polygon | Added Location Search
Multi-Zone | Operation Schedule | Regulatory Compliance
Engineering Report | Landscape Presets | 85+ crops
Deps: streamlit, pandas, numpy, ezdxf, matplotlib, requests
"""

import re, io, math, json
import numpy as np
import pandas as pd
import streamlit as st

try:
    import ezdxf; EZDXF_OK = True
except Exception: EZDXF_OK = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon as MplPolygon
    from matplotlib.lines import Line2D
    MPL_OK = True
except Exception: MPL_OK = False
try:
    import requests; REQUESTS_OK = True
except Exception: REQUESTS_OK = False

def T(en, ar):
    return en if st.session_state.get("lang", "ar") == "en" else ar

# ============================================================
# UNITS & CURRENCIES
# ============================================================
AREA_UNITS = {
    "Feddan":  {"m2":4200.0,  "ar":"فدان"},
    "Hectare": {"m2":10000.0, "ar":"هكتار"},
    "Acre":    {"m2":4047.0,  "ar":"أكر"},
    "Dunam":   {"m2":1000.0,  "ar":"دونم"},
    "m²":      {"m2":1.0,     "ar":"م²"},
}
CURRENCIES = {
    "EGP":{"ar":"ج.م","to_egp":1.0}, "USD":{"ar":"$","to_egp":50.0},
    "EUR":{"ar":"€","to_egp":54.0}, "SAR":{"ar":"ر.س","to_egp":13.3},
    "AED":{"ar":"د.إ","to_egp":13.6}, "GBP":{"ar":"£","to_egp":63.0},
}

# ============================================================
# SOILS & MEDIA
# ============================================================
SOILS = {
    "Sandy":{"taw":80,"ar":"رملية"},"Loamy Sand":{"taw":110,"ar":"رملية طميية"},
    "Sandy Loam":{"taw":140,"ar":"طميية رملية"},"Loam":{"taw":170,"ar":"طميية"},
    "Clay Loam":{"taw":190,"ar":"طميية طينية"},"Clay":{"taw":210,"ar":"طينية"},
}
LANDSCAPE_MEDIA = {
    "Prepared Agricultural Soil":{"taw":150,"ar":"تربة زراعية مجهزة"},
    "Imported Topsoil":{"taw":140,"ar":"تربة سطحية مستوردة"},
    "Sand-Soil Mix (60/40)":{"taw":110,"ar":"خليط رمل/تربة"},
    "Peat-based Mix":{"taw":180,"ar":"خليط بيت موس"},
    "Artificial Turf Base":{"taw":100,"ar":"قاعدة نجيل صناعي"},
}
NURSERY_MEDIA = {
    "Peat Moss + Perlite":{"taw":200,"ar":"بيت موس + بيرلايت"},
    "Coco Peat":{"taw":190,"ar":"كوكوبيت"},
    "Soil-based Mix":{"taw":160,"ar":"خليط ترابي"},
    "Hydroponic Substrate":{"taw":150,"ar":"ركيزة هيدروبونيك"},
}

# ============================================================
# CROPS
# ============================================================
CROPS = {
    "Wheat":{"kc":1.10,"zr":1.0,"cat":"field","ar":"قمح"},
    "Maize":{"kc":1.15,"zr":1.0,"cat":"field","ar":"ذرة"},
    "Rice":{"kc":1.20,"zr":0.6,"cat":"field","ar":"أرز"},
    "Barley":{"kc":1.05,"zr":1.0,"cat":"field","ar":"شعير"},
    "Alfalfa":{"kc":1.05,"zr":1.5,"cat":"field","ar":"برسيم"},
    "Cotton":{"kc":1.15,"zr":1.0,"cat":"field","ar":"قطن"},
    "Sunflower":{"kc":1.00,"zr":1.0,"cat":"field","ar":"عباد الشمس"},
    "Soybean":{"kc":1.05,"zr":0.8,"cat":"field","ar":"فول صويا"},
    "Sugar Beet":{"kc":1.10,"zr":1.0,"cat":"field","ar":"بنجر"},
    "Sugarcane":{"kc":1.25,"zr":1.5,"cat":"field","ar":"قصب"},
    "Tomato":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"طماطم"},
    "Potato":{"kc":1.10,"zr":0.5,"cat":"veg","ar":"بطاطس"},
    "Pepper":{"kc":1.00,"zr":0.5,"cat":"veg","ar":"فلفل"},
    "Cucumber":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"خيار"},
    "Eggplant":{"kc":1.05,"zr":0.7,"cat":"veg","ar":"باذنجان"},
    "Onion":{"kc":1.05,"zr":0.4,"cat":"veg","ar":"بصل"},
    "Garlic":{"kc":1.00,"zr":0.4,"cat":"veg","ar":"ثوم"},
    "Carrot":{"kc":1.05,"zr":0.5,"cat":"veg","ar":"جزر"},
    "Lettuce":{"kc":0.95,"zr":0.3,"cat":"veg","ar":"خس"},
    "Cabbage":{"kc":1.05,"zr":0.5,"cat":"veg","ar":"كرنب"},
    "Watermelon":{"kc":1.05,"zr":1.0,"cat":"veg","ar":"بطيخ"},
    "Melon":{"kc":1.05,"zr":0.9,"cat":"veg","ar":"شمام"},
    "Strawberry":{"kc":1.00,"zr":0.3,"cat":"veg","ar":"فراولة"},
    "Zucchini":{"kc":1.00,"zr":0.6,"cat":"veg","ar":"كوسة"},
    "Bean":{"kc":1.05,"zr":0.6,"cat":"veg","ar":"فاصوليا"},
    "Olive":{"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"},
    "Citrus":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},
    "Orange":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"برتقال"},
    "Lemon":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"ليمون"},
    "Mango":{"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"},
    "Date Palm":{"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل"},
    "Grape":{"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"},
    "Apple":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"تفاح"},
    "Pear":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"كمثرى"},
    "Peach":{"kc":0.95,"zr":1.0,"cat":"orchard","ar":"خوخ"},
    "Fig":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"تين"},
    "Pomegranate":{"kc":0.85,"zr":1.0,"cat":"orchard","ar":"رمان"},
    "Banana":{"kc":1.10,"zr":0.7,"cat":"orchard","ar":"موز"},
    "Avocado":{"kc":0.90,"zr":0.8,"cat":"orchard","ar":"أفوكادو"},
    "Turf Bermuda":{"kc":0.80,"zr":0.3,"cat":"turf","ar":"نجيل برمودا"},
    "Turf Fescue":{"kc":0.90,"zr":0.3,"cat":"turf","ar":"نجيل فيسكيوب"},
    "Turf Ryegrass":{"kc":0.85,"zr":0.3,"cat":"turf","ar":"نجيل راي"},
    "Turf Zoysia":{"kc":0.75,"zr":0.3,"cat":"turf","ar":"نجيل زويسيا"},
    "Bougainvillea":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"جهنمية"},
    "Hibiscus":{"kc":0.90,"zr":0.5,"cat":"shrub","ar":"خطمي"},
    "Lantana":{"kc":0.55,"zr":0.5,"cat":"shrub","ar":"لانتانا"},
    "Duranta":{"kc":0.75,"zr":0.6,"cat":"shrub","ar":"دورانتا"},
    "Jasmine":{"kc":0.75,"zr":0.6,"cat":"shrub","ar":"ياسمين"},
    "Oleander":{"kc":0.55,"zr":0.7,"cat":"shrub","ar":"دفلة"},
    "Pittosporum":{"kc":0.70,"zr":0.5,"cat":"shrub","ar":"بيتوسبورم"},
    "Vinca":{"kc":0.75,"zr":0.4,"cat":"shrub","ar":"ونكا"},
    "Ficus":{"kc":0.70,"zr":1.0,"cat":"tree","ar":"فيكس"},
    "Conocarpus":{"kc":0.55,"zr":1.2,"cat":"tree","ar":"كونوكاربس"},
    "Eucalyptus":{"kc":0.65,"zr":1.5,"cat":"tree","ar":"كافتوس"},
    "Delonix":{"kc":0.60,"zr":1.0,"cat":"tree","ar":"بوانسيانا"},
    "Cassia":{"kc":0.65,"zr":1.0,"cat":"tree","ar":"كاسيا"},
    "Washingtonia":{"kc":0.75,"zr":1.2,"cat":"tree","ar":"واشنطونيا"},
    "Phoenix":{"kc":0.70,"zr":1.2,"cat":"tree","ar":"فينكس"},
    "Royal Palm":{"kc":0.80,"zr":1.2,"cat":"tree","ar":"رويال"},
    "Rose":{"kc":0.85,"zr":0.4,"cat":"flower","ar":"ورد"},
    "Petunia":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"بيتونيا"},
    "Marigold":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"قطيفة"},
    "Geranium":{"kc":0.90,"zr":0.4,"cat":"flower","ar":"جرانيوم"},
    "Chrysanthemum":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"أقحوان"},
    "Carnation":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"قرنفل"},
    "Gerbera":{"kc":1.05,"zr":0.3,"cat":"flower","ar":"جربيرا"},
    "Gladiolus":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"جلاديولس"},
    "Dahlia":{"kc":1.00,"zr":0.4,"cat":"flower","ar":"داليا"},
    "Zinnia":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"زينيا"},
    "Gazania":{"kc":0.55,"zr":0.3,"cat":"flower","ar":"جازانيا"},
    "Lavender":{"kc":0.65,"zr":0.4,"cat":"flower","ar":"لافندر"},
    "Lily":{"kc":1.00,"zr":0.3,"cat":"flower","ar":"زنبق"},
    "Aster":{"kc":0.95,"zr":0.3,"cat":"flower","ar":"أستر"},
    "Ficus Benjamina":{"kc":0.75,"zr":0.6,"cat":"foliage","ar":"بنجامينا"},
    "Dracaena":{"kc":0.65,"zr":0.5,"cat":"foliage","ar":"دراسينا"},
    "Schefflera":{"kc":0.75,"zr":0.5,"cat":"foliage","ar":"شيفليرا"},
    "Aglaonema":{"kc":0.80,"zr":0.3,"cat":"foliage","ar":"أجلونيما"},
    "Croton":{"kc":0.85,"zr":0.4,"cat":"foliage","ar":"كروتون"},
    "Wedelia":{"kc":0.65,"zr":0.2,"cat":"groundcover","ar":"ويدليا"},
    "Asparagus Fern":{"kc":0.75,"zr":0.3,"cat":"groundcover","ar":"اسباراجوس"},
    "Liriope":{"kc":0.70,"zr":0.2,"cat":"groundcover","ar":"ليريوبي"},
    "Aptenia":{"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"أبتينيا"},
    "Portulaca":{"kc":0.50,"zr":0.2,"cat":"groundcover","ar":"بورتولاكا"},
    "Ivy":{"kc":0.70,"zr":0.6,"cat":"climber","ar":"لبلاب"},
    "Wisteria":{"kc":0.70,"zr":0.8,"cat":"climber","ar":"ويستيريا"},
    "Passion Flower":{"kc":0.75,"zr":0.7,"cat":"climber","ar":"الآلام"},
    "Aloe Vera":{"kc":0.35,"zr":0.2,"cat":"succulent","ar":"صبار"},
    "Agave":{"kc":0.30,"zr":0.3,"cat":"succulent","ar":"أجاف"},
    "Sedum":{"kc":0.40,"zr":0.2,"cat":"succulent","ar":"سيدم"},
    "Potted Flowering":{"kc":1.10,"zr":0.25,"cat":"pot","ar":"أصص مزهرة"},
    "Potted Foliage":{"kc":1.00,"zr":0.25,"cat":"pot","ar":"أصص ورقية"},
    "Potted Herb":{"kc":1.00,"zr":0.20,"cat":"pot","ar":"أصص أعشاب"},
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
    "Nursery": {
        "🌸 Flowers": ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera","Gladiolus","Dahlia","Zinnia","Lavender","Lily","Aster"],
        "🍃 Foliage": ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"],
        "🌳 Shrubs": ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine","Oleander","Pittosporum","Vinca"],
        "🪴 Potted": ["Potted Flowering","Potted Foliage","Potted Herb"],
    },
}

P_ALLOW = {"field":0.50,"veg":0.35,"orchard":0.55,"turf":0.50,"shrub":0.45,
           "tree":0.50,"flower":0.40,"foliage":0.45,"groundcover":0.45,
           "climber":0.45,"succulent":0.30,"pot":0.35}
PER_PLANT_CATS = {"orchard","tree","shrub","flower","foliage","pot","climber"}

# ============================================================
# IRRIGATION SYSTEMS
# ============================================================
IRR_SYSTEMS = {
    "drip": {"ar":"تنقيط", "eff":0.90, "pressure":10.0},
    "micro": {"ar":"ميكرو", "eff":0.85, "pressure":15.0},
    "bubbler": {"ar":"بابلر", "eff":0.85, "pressure":12.0},
    "sprinkler": {"ar":"رشاش", "eff":0.75, "pressure":25.0},
    "surface": {"ar":"غمر", "eff":0.55, "pressure":2.0},
}

DRIP_FLOWS = [1.6, 2.0, 4.0, 8.0, 16.0]
FILTERS = ["Screen Filter","Disc Filter","Media Filter","Hydrocyclone"]
FILTER_AR = {"Screen Filter":"شبكي","Disc Filter":"ديسكات","Media Filter":"رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}
FERT_SYS = ["None","Venturi","Dosing Pump","Fertilizer Tank"]
FERT_AR = {"None":"بدون","Venturi":"فنتوري","Dosing Pump":"مضخة حقن","Fertilizer Tank":"تانك"}
FERT_PRICE = {"None":0,"Venturi":3500,"Dosing Pump":15000,"Fertilizer Tank":6000}

DEFAULT_PRICES = {"main":80.0,"sub":45.0,"lat":6.0,"drip":3.0,"control":2500.0,
                  "flush":450.0,"arv":1800.0,"acid":12000.0,"treat":20000.0}

CLIMATE_ZONES = {
    "Arid/Desert":{"eto":6.5,"wind":3.5,"ar":"صحراوي"},
    "Semi-Arid":{"eto":5.5,"wind":3.0,"ar":"شبه جاف"},
    "Mediterranean":{"eto":4.8,"wind":3.0,"ar":"متوسطي"},
    "Subtropical":{"eto":5.0,"wind":2.0,"ar":"شبه مداري"},
    "Tropical":{"eto":4.5,"wind":1.5,"ar":"مداري"},
    "Temperate":{"eto":3.5,"wind":2.5,"ar":"معتدل"},
    "Continental":{"eto":3.0,"wind":3.0,"ar":"قاري"},
}

# ============================================================
# REGULATORY ENGINE
# ============================================================
REGULATIONS = {
    "INTL": {"name":"دولي","name_en":"International","max_daily_hours":24.0,"min_eff":0.60,"forbidden_systems":[],"ec_max":10.0,"sar_max":15.0,"notes_ar":"معايير FAO","notes_en":"FAO guidelines"},
    "EG": {"name":"مصر","name_en":"Egypt","max_daily_hours":10.0,"min_eff":0.70,"forbidden_systems":["surface"],"ec_max":5.0,"sar_max":9.0,"notes_ar":"قانون 147/2021: 10 ساعات تشغيل كحد أقصى، منع الري بالغمر","notes_en":"Law 147/2021: max 10h/day, surface banned"},
    "SA": {"name":"السعودية","name_en":"Saudi Arabia","max_daily_hours":16.0,"min_eff":0.75,"forbidden_systems":["surface"],"ec_max":5.0,"sar_max":9.0,"notes_ar":"كفاءة ≥75%، منع الغمر","notes_en":"Eff ≥75%, surface banned"},
    "AE": {"name":"الإمارات","name_en":"UAE","max_daily_hours":14.0,"min_eff":0.75,"forbidden_systems":["surface"],"ec_max":5.0,"sar_max":9.0,"notes_ar":"منع الغمر، قيود على المياه المعالجة","notes_en":"Surface banned, treated water limits"},
    "GR": {"name":"اليونان","name_en":"Greece","max_daily_hours":14.0,"min_eff":0.70,"forbidden_systems":[],"ec_max":6.0,"sar_max":10.0,"summer_restriction":(11,17),"notes_ar":"قيود صيفية على الري نهاراً (11ص-5م)","notes_en":"Summer midday restriction (11am-5pm)"},
    "US": {"name":"الولايات المتحدة","name_en":"United States","max_daily_hours":24.0,"min_eff":0.70,"forbidden_systems":[],"ec_max":8.0,"sar_max":12.0,"notes_ar":"معايير ASABE","notes_en":"ASABE standards"},
    "ES": {"name":"إسبانيا","name_en":"Spain","max_daily_hours":14.0,"min_eff":0.70,"forbidden_systems":[],"ec_max":6.0,"sar_max":10.0,"notes_ar":"سياسة مياه صارمة","notes_en":"Strict water policy"},
}

# ============================================================
# LANDSCAPE PRESETS
# ============================================================
LANDSCAPE_PRESETS = {
    "Villa Residential (فيلا سكنية)": [
        {"name":"Lawn","crop":"Turf Bermuda","pct":0.40,"system":"sprinkler"},
        {"name":"Trees","crop":"Ficus","pct":0.25,"system":"drip"},
        {"name":"Shrubs","crop":"Bougainvillea","pct":0.20,"system":"drip"},
        {"name":"Flowers","crop":"Rose","pct":0.15,"system":"micro"},
    ],
    "Public Park (حديقة عامة)": [
        {"name":"Lawn","crop":"Turf Bermuda","pct":0.55,"system":"sprinkler"},
        {"name":"Trees","crop":"Washingtonia","pct":0.20,"system":"drip"},
        {"name":"Shrubs","crop":"Duranta","pct":0.15,"system":"drip"},
        {"name":"Flowers","crop":"Petunia","pct":0.10,"system":"micro"},
    ],
    "Corporate (شركات)": [
        {"name":"Lawn","crop":"Turf Zoysia","pct":0.50,"system":"sprinkler"},
        {"name":"Palms","crop":"Royal Palm","pct":0.25,"system":"drip"},
        {"name":"Succulents","crop":"Agave","pct":0.25,"system":"drip"},
    ],
}

# ============================================================
# HELPERS
# ============================================================
def velocity_ms(q_lps, d_mm):
    if d_mm <= 0: return 0.0
    return (q_lps/1000.0) / (math.pi*(d_mm/1000.0)**2/4.0)

def head_loss_hw(L, q_lps, d_mm, C=140.0):
    if d_mm <= 0 or q_lps <= 0: return 0.0
    Q = q_lps/1000.0; D = d_mm/1000.0
    return 10.67 * L * (Q**1.852) / ((C**1.852)*(D**4.87))

def to_curr(v_egp, curr): return v_egp / CURRENCIES[curr]["to_egp"]
def fmt_money(v, curr): return f"{v:,.0f} {CURRENCIES[curr]['ar']}"

def water_quality_warnings(ec, ph, sar):
    W = []
    if ec > 5: W.append(("EC عالي (>5) — غسيل أملاح","Very high EC (>5) — leaching","warn"))
    elif ec > 3: W.append(("EC مرتفع (>3) — مراقبة","High EC (>3) — monitor","info"))
    if ph > 8.2: W.append(("pH مرتفع (>8.2) — حقن حامض","High pH (>8.2) — acid injection","warn"))
    if sar > 9: W.append(("SAR عالي (>9) — خطر نفاذية","High SAR (>9) — infiltration","warn"))
    return W

# ============================================================
# POLYGON
# ============================================================
def polygon_area_m2(coords):
    if len(coords) < 3: return 0.0
    lat0 = sum(c[0] for c in coords)/len(coords)
    mlat, mlon = 111320.0, 111320.0*math.cos(math.radians(lat0))
    pts = [(lon*mlon, lat*mlat) for lat,lon in coords]
    s = sum(pts[i][0]*pts[(i+1)%len(pts)][1] - pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
    return abs(s)/2.0

def polygon_centroid(coords):
    if len(coords) < 3: return None, None
    lat0 = sum(c[0] for c in coords)/len(coords)
    mlat, mlon = 111320.0, 111320.0*math.cos(math.radians(lat0))
    pts = [(lon*mlon, lat*mlat) for lat,lon in coords]
    a=cx=cy=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]
        cr=x1*y2-x2*y1; a+=cr; cx+=(x1+x2)*cr; cy+=(y1+y2)*cr
    a/=2.0
    if a==0: return None,None
    return round(cy/(6*a)/mlat,6), round(cx/(6*a)/mlon,6)

# ============================================================
# API
# ============================================================
def fetch_eto(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
            params={"latitude":lat,"longitude":lon,
                    "daily":"et0_fao_evapotranspiration,wind_speed_10m_max",
                    "timezone":"auto","forecast_days":3}, timeout=8)
        r.raise_for_status(); d = r.json().get("daily",{})
        ev=[v for v in d.get("et0_fao_evapotranspiration",[]) if v is not None]
        wv=[v for v in d.get("wind_speed_10m_max",[]) if v is not None]
        return {"eto":sum(ev)/len(ev) if ev else None,
                "wind":(sum(wv)/len(wv))/3.6 if wv else None}
    except: return None

def fetch_soil(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query",
            params=[("lon",lon),("lat",lat),("property","clay"),
                    ("property","sand"),("depth","0-30cm")], timeout=12)
        r.raise_for_status()
        vals = {}
        for L in r.json().get("properties",{}).get("layers",[]):
            d = L.get("depths",[])
            if d:
                v = d[0].get("values",{}).get("mean")
                if v is not None: vals[L.get("name")] = v/10.0
        s, c = vals.get("sand"), vals.get("clay")
        if s is None or c is None: return None
        if c>=40: return "Clay"
        if c>=25 and s<=45: return "Clay Loam"
        if s>=85: return "Sandy"
        if s>=70: return "Loamy Sand"
        if s>=50: return "Sandy Loam"
        return "Loam"
    except: return None

def fetch_location(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
            params={"lat":lat,"lon":lon,"format":"json","accept-language":"ar"},
            headers={"User-Agent":"SmartIrrigationAI/11"}, timeout=8)
        r.raise_for_status(); a = r.json().get("address",{})
        parts = [a.get("city") or a.get("town") or a.get("village") or a.get("county"), a.get("state")]
        return ", ".join([p for p in parts if p]) or r.json().get("display_name","")[:60]
    except: return None

def search_location_name(query):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "accept-language":"ar"},
            headers={"User-Agent": "SmartIrrigationAI/11"}, timeout=8)
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name","")[:60]
    except: pass
    return None

# ============================================================
# ZONE DESIGN ENGINE
# ============================================================
def design_zone(zone, project):
    ci = CROPS[zone["crop"]]
    kc, zr, cat = ci["kc"], ci["zr"], ci["cat"]
    sys_info = IRR_SYSTEMS[zone["system"]]
    eff = sys_info["eff"]

    if project["project_type"] == "Agricultural":
        taw = float(SOILS[zone.get("soil","Sandy Loam")]["taw"])
    elif project["project_type"] == "Landscape":
        taw = float(LANDSCAPE_MEDIA[zone.get("media","Prepared Agricultural Soil")]["taw"])
    else:
        taw = float(NURSERY_MEDIA[zone.get("media","Peat Moss + Perlite")]["taw"])

    raw_mm = P_ALLOW[cat] * taw * zr
    eto = project["eto"]
    etc = eto * kc

    if cat in ("veg","flower","pot"): max_int = 3
    elif cat in ("orchard","tree"): max_int = 7
    elif cat == "succulent": max_int = 14
    else: max_int = 5
    interval = max(1, min(raw_mm/etc if etc > 0 else max_int, max_int))
    interval = int(round(interval))

    net_event_mm = etc * interval
    gross_event_mm = net_event_mm / eff

    area_m2 = zone["area_value"] * AREA_UNITS[zone["area_unit"]]["m2"]
    vol_event_m3 = gross_event_mm * area_m2 / 1000.0
    annual_m3 = (etc * 365 / eff) * area_m2 / 1000.0

    q_drip = float(zone.get("emitter_flow", 2.0))
    esp = float(zone.get("emitter_spacing", 0.5))
    lsp = float(zone.get("lateral_spacing", 0.8))

    if zone["system"] in ("drip","micro"):
        emitters_m2 = 1.0/(esp*lsp) if esp>0 and lsp>0 else 0
        zone_emitters = int(emitters_m2 * area_m2)
        zone_q_lph = zone_emitters * q_drip
    elif zone["system"] == "sprinkler":
        n_heads = int(area_m2 / 144)
        zone_q_lph = n_heads * 1000.0
        zone_emitters = n_heads
    elif zone["system"] == "bubbler":
        sx = zone.get("tree_spacing", 5.0); sy = zone.get("row_spacing", 6.0)
        n_bub = int(area_m2 / (sx*sy))
        zone_q_lph = n_bub * 100.0
        zone_emitters = n_bub
    else:
        zone_q_lph = area_m2 / 10.0
        zone_emitters = 0

    zone_q_lps = zone_q_lph / 3600.0
    zone_q_m3h = zone_q_lph / 1000.0
    duration_hr = vol_event_m3 / zone_q_m3h if zone_q_m3h > 0 else 0

    per_plant = None
    if cat in PER_PLANT_CATS:
        sx = zone.get("tree_spacing", 5.0); sy = zone.get("row_spacing", 6.0)
        L_day = etc * (sx*sy); L_ev = L_day * interval
        per_plant = {"L_day": round(L_day,1), "L_event": round(L_ev,1)}

    L_main_zone = math.sqrt(area_m2) * 1.5
    D_zone = 63
    v_zone = velocity_ms(zone_q_lps, D_zone)
    hf_zone = head_loss_hw(L_main_zone, zone_q_lps, D_zone)
    op_press = sys_info["pressure"]
    tdh_zone = project["elevation"] + project["suction_lift"] + hf_zone + op_press + project["safety"]

    return {
        **zone,
        "kc":kc, "cat":cat, "zr":zr, "taw":taw, "raw_mm":raw_mm,
        "etc":etc, "interval":interval, "net_event_mm":net_event_mm,
        "gross_event_mm":gross_event_mm, "event_volume_m3":vol_event_m3,
        "annual_m3":annual_m3, "area_m2":area_m2,
        "zone_emitters":zone_emitters, "zone_q_m3h":zone_q_m3h,
        "zone_q_lps":zone_q_lps, "duration_hr":duration_hr,
        "per_plant":per_plant, "v_zone":v_zone, "hf_zone":hf_zone,
        "tdh_zone":tdh_zone, "op_pressure":op_press,
    }

# ============================================================
# SCHEDULING
# ============================================================
def build_schedule(zones, strategy, source_capacity_m3h, day_start=5.0):
    if not zones: return zones, 0.0
    if strategy == "sequential":
        current = day_start
        for z in zones:
            z["start_hr"] = current
            z["end_hr"] = current + z["duration_hr"]
            current = z["end_hr"] + 0.25
        total = current - day_start
    else:
        sorted_z = sorted(zones, key=lambda x: -x["duration_hr"])
        timeline = []
        for z in sorted_z:
            found = False
            for t_int in range(0, 96):
                t = day_start + t_int*0.25
                overlap = sum(sl["flow"] for sl in timeline 
                              if sl["start"] < t + z["duration_hr"] and sl["end"] > t)
                if overlap + z["zone_q_m3h"] <= source_capacity_m3h:
                    z["start_hr"] = t
                    z["end_hr"] = t + z["duration_hr"]
                    timeline.append({"start": t, "end": z["end_hr"], "flow": z["zone_q_m3h"]})
                    found = True
                    break
            if not found:
                max_end = max((sl["end"] for sl in timeline), default=day_start)
                z["start_hr"] = max_end + 0.25
                z["end_hr"] = z["start_hr"] + z["duration_hr"]
                timeline.append({"start": z["start_hr"], "end": z["end_hr"], "flow": z["zone_q_m3h"]})
        total = max(z["end_hr"] for z in zones) - day_start
    return zones, total

# ============================================================
# AGGREGATE
# ============================================================
def aggregate(zones):
    if not zones:
        return {"total_area_m2":0, "total_daily_water_m3":0, "peak_flow_m3h":0,
                "total_event_water_m3":0, "total_annual_m3":0, "n_zones":0, "sum_flows_m3h":0}
    return {
        "n_zones": len(zones),
        "total_area_m2": sum(z["area_m2"] for z in zones),
        "total_daily_water_m3": sum(z["event_volume_m3"]/z["interval"] for z in zones),
        "peak_flow_m3h": max(z["zone_q_m3h"] for z in zones),
        "sum_flows_m3h": sum(z["zone_q_m3h"] for z in zones),
        "total_event_water_m3": sum(z["event_volume_m3"] for z in zones),
        "total_annual_m3": sum(z["annual_m3"] for z in zones),
    }

# ============================================================
# COMPLIANCE
# ============================================================
def check_compliance(project, zones, agg, total_hours):
    country = project["country"]
    reg = REGULATIONS[country]
    issues = []
    if total_hours > reg["max_daily_hours"]:
        issues.append(("error", f"⛔ ساعات التشغيل {total_hours:.1f}h تتجاوز حد {reg['max_daily_hours']}h ({reg['name']})", f"⛔ {total_hours:.1f}h exceeds limit {reg['max_daily_hours']}h ({reg['name_en']})"))
    elif total_hours > reg["max_daily_hours"] * 0.9:
        issues.append(("warning", f"⚠️ ساعات التشغيل {total_hours:.1f}h قريبة من الحد ({reg['max_daily_hours']}h)", f"⚠️ {total_hours:.1f}h near limit ({reg['max_daily_hours']}h)"))
    for z in zones:
        if z["system"] in reg["forbidden_systems"]:
            issues.append(("error", f"⛔ زونة {z['name']}: نظام '{IRR_SYSTEMS[z['system']]['ar']}' ممنوع في {reg['name']}", f"⛔ Zone {z['name']}: '{z['system']}' forbidden in {reg['name_en']}"))
        eff = IRR_SYSTEMS[z["system"]]["eff"]
        if eff < reg["min_eff"]:
            issues.append(("warning", f"⚠️ زونة {z['name']}: كفاءة {eff:.0%} أقل من الحد {reg['min_eff']:.0%}", f"⚠️ Zone {z['name']}: eff {eff:.0%} < required {reg['min_eff']:.0%}"))
    if project["ec"] > reg["ec_max"]:
        issues.append(("error", f"⛔ EC ({project['ec']}) يتجاوز حد {reg['ec_max']}", f"⛔ EC ({project['ec']}) exceeds {reg['ec_max']}"))
    if project["sar"] > reg["sar_max"]:
        issues.append(("error", f"⛔ SAR ({project['sar']}) يتجاوز حد {reg['sar_max']}", f"⛔ SAR ({project['sar']}) exceeds {reg['sar_max']}"))
    if agg["peak_flow_m3h"] > project["source_capacity_m3h"]:
        issues.append(("error", f"⛔ أعلى تصرف زونة {agg['peak_flow_m3h']:.1f} م³/س يتجاوز قدرة المصدر {project['source_capacity_m3h']}", f"⛔ Peak zone flow {agg['peak_flow_m3h']:.1f} > source {project['source_capacity_m3h']}"))
    if "summer_restriction" in reg:
        r_start, r_end = reg["summer_restriction"]
        for z in zones:
            if z["start_hr"] < r_end and z["end_hr"] > r_start:
                issues.append(("warning", f"⚠️ زونة {z['name']} تعمل أثناء فترة القيود الصيفية ({r_start}:00-{r_end}:00)", f"⚠️ Zone {z['name']} runs during summer restriction ({r_start}-{r_end})"))
    return issues, reg

# ============================================================
# BOQ
# ============================================================
def compute_boq(project, zones, agg):
    curr = project["currency"]
    rows = []
    main_flow = agg["peak_flow_m3h"]
    if main_flow > 30: D_main = 110
    elif main_flow > 15: D_main = 90
    else: D_main = 75
    L_main = math.sqrt(agg["total_area_m2"]) * 2
    rows.append(("أنبوب رئيسي", f"Ø{D_main}mm × {L_main:.0f}m", L_main * DEFAULT_PRICES["main"]))
    for z in zones:
        rows.append((f"زونة {z['name']} — مواسير فرعية", f"{math.sqrt(z['area_m2'])*2:.0f}m", math.sqrt(z["area_m2"])*2*DEFAULT_PRICES["sub"]))
        if z["system"] in ("drip","micro"):
            rows.append((f"زونة {z['name']} — منقطات", f"{z['zone_emitters']:,}", z["zone_emitters"]*DEFAULT_PRICES["drip"]))
        rows.append((f"زونة {z['name']} — محبس تحكم", "1", DEFAULT_PRICES["control"]))
        rows.append((f"زونة {z['name']} — محبس غسيل", "1", DEFAULT_PRICES["flush"]))
    rows.append(("فلتر رئيسي", FILTER_AR.get(project["filter_type"],"فلتر"), FILTER_PRICE.get(project["filter_type"], 0)))
    if FERT_PRICE.get(project["fert_sys"], 0) > 0:
        rows.append(("نظام تسميد", FERT_AR.get(project["fert_sys"],""), FERT_PRICE[project["fert_sys"]]))
    rows.append(("محابس هواء", "4", 4*DEFAULT_PRICES["arv"]))
    if project["ph"] > 8.2: rows.append(("حقن حامض", "1", DEFAULT_PRICES["acid"]))
    if project["ec"] > 5: rows.append(("معالجة مياه", "-", DEFAULT_PRICES["treat"]))
    before = sum(r[2] for r in rows)
    rows.append(("وصلات 10%", "-", 0.10*before))
    rows_curr = [(r[0], r[1], to_curr(r[2], curr)) for r in rows]
    subtotal = sum(r[2] for r in rows_curr)
    vat_amt = subtotal * project["vat"]/100
    return rows_curr, subtotal, vat_amt, subtotal+vat_amt

# ============================================================
# ENGINEERING REPORT
# ============================================================
def build_engineering_report(project, zones, agg, schedule_hours, compliance, reg):
    lines = []
    sep = "="*70
    lines.append(sep)
    lines.append("SMART IRRIGATION DESIGN REPORT — التقرير الهندسي")
    lines.append(sep)
    lines.append("")
    lines.append("[1] الملخص التنفيذي / EXECUTIVE SUMMARY")
    lines.append("-"*70)
    lines.append(f"المشروع: {project['name']}")
    lines.append(f"نوع المشروع: {project['project_type']}")
    lines.append(f"الموقع: {st.session_state.get('loc_name', 'غير محدد')}")
    lines.append(f"عدد الزونات: {agg['n_zones']}")
    lines.append(f"المساحة الإجمالية: {agg['total_area_m2']:,.0f} م² ({agg['total_area_m2']/AREA_UNITS['Feddan']['m2']:.2f} فدان)")
    lines.append(f"الاحتياج المائي اليومي: {agg['total_daily_water_m3']:.1f} م³/يوم")
    lines.append(f"الاحتياج السنوي: {agg['total_annual_m3']:.0f} م³/سنة")
    lines.append(f"ساعات التشغيل اليومية: {schedule_hours:.1f} ساعة")
    lines.append(f"قدرة المصدر: {project['source_capacity_m3h']} م³/س")
    lines.append(f"الجهة التنظيمية: {reg['name']}")
    issues_errors = sum(1 for i in compliance if i[0]=="error")
    lines.append(f"الامتثال: {'✅ متوافق' if issues_errors==0 else f'⛔ {issues_errors} مخالفة'}")
    lines.append("")
    lines.append("[2] بيانات الموقع والمناخ / SITE & CLIMATE")
    lines.append("-"*70)
    lines.append(f"الإحداثيات: {project['lat']:.4f}, {project['lon']:.4f}")
    lines.append(f"ETo: {project['eto']:.2f} mm/day")
    lines.append(f"سرعة الرياح: {project['wind']:.1f} m/s")
    lines.append(f"الميل: {project['slope']:.1f}%")
    lines.append(f"فرق المنسوب: {project['elevation']:.1f}m")
    lines.append("")
    lines.append("[3] جودة المياه / WATER QUALITY")
    lines.append("-"*70)
    lines.append(f"EC: {project['ec']} dS/m (حد {reg['ec_max']})")
    lines.append(f"pH: {project['ph']}")
    lines.append(f"SAR: {project['sar']} (حد {reg['sar_max']})")
    lines.append(f"مصدر المياه: {project['water_source']}")
    for w_ar,w_en,lvl in water_quality_warnings(project['ec'], project['ph'], project['sar']):
        lines.append(f"  [{lvl.upper()}] {w_ar}")
    lines.append("")
    lines.append("[4] الزونات والتصميم / ZONES DESIGN")
    lines.append("-"*70)
    for z in zones:
        lines.append(f"\n▶ زونة {z['name']} — {CROPS[z['crop']]['ar']} ({z['crop']})")
        lines.append(f"  المساحة: {z['area_value']} {z['area_unit']}")
        lines.append(f"  النظام: {IRR_SYSTEMS[z['system']]['ar']}")
        lines.append(f"  الفئة: {z['cat']} | Kc: {z['kc']:.2f}")
        lines.append(f"  ETc: {z['etc']:.2f} mm/day")
        lines.append(f"  RAW: {z['raw_mm']:.1f} mm | الفترة: {z['interval']} يوم")
        lines.append(f"  عمق الريّة: {z['gross_event_mm']:.1f} mm")
        lines.append(f"  حجم الريّة: {z['event_volume_m3']:.1f} م³")
        lines.append(f"  التصرف: {z['zone_q_m3h']:.2f} م³/س")
        lines.append(f"  المدة: {z['duration_hr']:.2f} ساعة")
        lines.append(f"  الجدول: من {z.get('start_hr',0):.1f}:00 إلى {z.get('end_hr',0):.1f}:00")
        if z.get("per_plant"):
            lines.append(f"  مياه/نبات/يوم: {z['per_plant']['L_day']} L")
            lines.append(f"  مياه/نبات/ريّة: {z['per_plant']['L_event']} L")
    lines.append("")
    lines.append("[5] جدول التشغيل / OPERATION SCHEDULE")
    lines.append("-"*70)
    lines.append(f"{'الزونة':<15} {'البداية':<10} {'النهاية':<10} {'المدة':<8} {'التصرف':<10}")
    lines.append("-"*70)
    for z in zones:
        lines.append(f"{z['name']:<15} {z.get('start_hr',0):<10.1f} {z.get('end_hr',0):<10.1f} {z['duration_hr']:<8.2f} {z['zone_q_m3h']:<10.2f}")
    lines.append(f"\nإجمالي نافذة التشغيل: {schedule_hours:.1f} ساعة")
    lines.append(f"أعلى تصرف لحظي: {agg['peak_flow_m3h']:.2f} م³/س")
    lines.append("")
    lines.append("[6] الامتثال التنظيمي / COMPLIANCE")
    lines.append("-"*70)
    lines.append(f"الجهة: {reg['name']}")
    if not compliance:
        lines.append("✅ التصميم متوافق تماماً مع اللوائح المحلية")
    else:
        for sev, ar, en in compliance:
            mark = "⛔" if sev=="error" else "⚠️"
            lines.append(f"{mark} {ar}")
    lines.append("")
    lines.append("[7] التوصيات الفنية / RECOMMENDATIONS")
    lines.append("-"*70)
    recs = []
    if agg["peak_flow_m3h"] > project["source_capacity_m3h"] * 0.9:
        recs.append("المصدر قريب من الطاقة القصوى — فكر في مضخة إضافية أو خزان")
    if schedule_hours > reg["max_daily_hours"]:
        recs.append(f"تجاوز الحد التنظيمي — قسّم المشروع على مرحلتين")
    if project["ec"] > 3: recs.append("EC مرتفع — راجع برنامج غسيل الأملاح")
    if project["ph"] > 8.2: recs.append("pH قلوي — حقن حامض ضروري")
    if not recs: recs.append("التصميم سليم — لا توصيات إضافية")
    for r in recs: lines.append(f"• {r}")
    lines.append("")
    lines.append(sep)
    import datetime
    lines.append(f"تم التوليد: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("Smart Irrigation AI V11.1 — Engineering Report")
    lines.append(sep)
    return "\n".join(lines)

# ============================================================
# PLOT
# ============================================================
def build_plot(project, zones):
    W = math.sqrt(sum(z["area_m2"] for z in zones)) if zones else 100
    H = W
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.add_patch(Rectangle((0,0), W, H, fill=False, lw=2.5, edgecolor="black"))
    colors = ["#4CAF50","#2196F3","#FF9800","#E91E63","#9C27B0","#00BCD4","#FFC107","#795548"]
    y = 0
    total_a = sum(z["area_m2"] for z in zones) if zones else 1
    for i, z in enumerate(zones):
        z_h = H * (z["area_m2"]/total_a)
        color = colors[i % len(colors)]
        ax.add_patch(Rectangle((0, y), W, z_h, fill=True, facecolor=color, alpha=0.4, edgecolor=color, lw=1.5))
        cx, cy = W/2, y + z_h/2
        ax.text(cx, cy, f"Zone {z['name']}\n{CROPS[z['crop']]['ar']}\n{z['area_value']:.1f} {z['area_unit']}",
                ha="center", va="center", fontsize=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color))
        y += z_h
    ax.annotate("", xy=(W*1.02, H*0.95), xytext=(W*1.02, H*0.85), arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.text(W*1.02, H*0.97, "N", ha="center", fontsize=12, fontweight="bold")
    s_len = round(W/4)
    ax.plot([W*0.05, W*0.05+s_len], [H*0.03, H*0.03], color="black", lw=4)
    ax.text(W*0.05+s_len/2, H*0.01, f"{s_len} m", ha="center", fontsize=9)
    ax.set_xlim(-W*0.1, W*1.1)
    ax.set_ylim(-H*0.05, H*1.05)
    ax.set_aspect("equal")
    ax.set_title(f"{project['name']} — مخطط المناطق ({len(zones)} zones)", fontsize=13, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    return fig

# ============================================================
# DXF
# ============================================================
def build_dxf(project, zones, total_cost):
    if not EZDXF_OK: return None
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for lay in ["FIELD","ZONE_LABELS","PIPE_MAIN","PIPE_SUB","VALVE","FILTER","FERTIGATION","AIR_VALVE","FLUSH","TITLE"]:
        if lay not in doc.layers: doc.layers.add(lay)
    W = math.sqrt(sum(z["area_m2"] for z in zones)) if zones else 100
    H = W
    msp.add_lwpolyline([(0,0),(W,0),(W,H),(0,H),(0,0)], dxfattribs={"layer":"FIELD"})
    y = 0
    total_a = sum(z["area_m2"] for z in zones) if zones else 1
    for z in zones:
        z_h = H * (z["area_m2"]/total_a)
        msp.add_lwpolyline([(0,y),(W,y),(W,y+z_h),(0,y+z_h),(0,y)], dxfattribs={"layer":"PIPE_SUB"})
        t = msp.add_text(f"{z['name']} — {z['crop']}", dxfattribs={"layer":"ZONE_LABELS","height":2.5})
        t.dxf.insert = (W/2 - 5, y + z_h/2)
        msp.add_circle((W*0.05, y + z_h/2), 0.5, dxfattribs={"layer":"VALVE"})
        msp.add_circle((W*0.95, y + z_h/2), 0.3, dxfattribs={"layer":"FLUSH"})
        y += z_h
    msp.add_circle((2, H+3), 1.0, dxfattribs={"layer":"FILTER"})
    t = msp.add_text("FILTER", dxfattribs={"layer":"TITLE","height":1.5})
    t.dxf.insert = (4, H+3)
    if project["fert_sys"] != "None":
        msp.add_circle((2, H+7), 1.0, dxfattribs={"layer":"FERTIGATION"})
        t = msp.add_text(project["fert_sys"].upper(), dxfattribs={"layer":"TITLE","height":1.5})
        t.dxf.insert = (4, H+7)
    t = msp.add_text(f"{project['name']} | {len(zones)} Zones", dxfattribs={"layer":"TITLE","height":3})
    t.dxf.insert = (0, H+15)
    t = msp.add_text(f"Total: {total_cost:,.0f} {CURRENCIES[project['currency']]['ar']}", dxfattribs={"layer":"TITLE","height":2})
    t.dxf.insert = (0, H+11)
    buf = io.BytesIO(); doc.saveas(buf); buf.seek(0)
    return buf

# ============================================================
# SESSION INIT
# ============================================================
def init_session():
    defaults = {
        "lang":"ar","project":None,"zones":[],
        "eto_val":5.5,"wind_val":2.0,"slope_val":0.0,
        "ec_val":1.2,"ph_val":7.5,"sar_val":3.0,
        "soil_val":"Sandy Loam","search_lat":30.50,"search_lon":30.50,
        "loc_name":"","proj_name":"Project-01",
        "country":"EG","currency":"EGP","vat_val":14.0,
        "project_type":"Agricultural","strategy":"sequential",
        "source_capacity":40.0,
        "area_value":5.0,"area_unit":"Feddan",
        "elevation":0.0,"suction_lift":2.0,"safety":5.0,
        "filter_type":"Screen Filter","fert_sys":"None",
    }
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

def new_zone(idx, project_type):
    grp = PROJECT_CROP_GROUPS[project_type]
    first_group = list(grp.keys())[0]
    first_crop = grp[first_group][0]
    return {
        "id": f"zone_{idx}", "name": f"Z{idx}",
        "crop": first_crop, "group": first_group,
        "area_value": 1.0, "area_unit": "Feddan",
        "system": "drip",
        "emitter_flow": 2.0, "emitter_spacing": 0.5,
        "lateral_spacing": 0.8,
        "tree_spacing": 5.0, "row_spacing": 6.0,
        "soil": "Sandy Loam",
        "media": "Prepared Agricultural Soil" if project_type=="Landscape" else "Peat Moss + Perlite",
    }

# ============================================================
# MAIN UI
# ============================================================
def main():
    st.set_page_config(page_title="Smart Irrigation AI V11.1", layout="wide", initial_sidebar_state="expanded")
    init_session()

    with st.sidebar:
        lang = st.selectbox("Language / اللغة", ["العربية","English"])
        st.session_state.lang = "ar" if lang=="العربية" else "en"
        st.markdown("---")
        st.caption("**Smart Irrigation AI V11.1**")
        st.caption("Engineering Office Agent")
        st.markdown("---")
        if REQUESTS_OK: st.success("🌐 APIs متاحة")
        else: st.warning("⚠️ APIs غير متاحة")

    st.title("💧 " + T("Smart Irrigation AI V11","الري الذكي V11"))
    st.caption(T("Multi-Zone | Operation Schedule | Regulatory Compliance | Engineering Report",
                 "زونات متعددة | جدولة تشغيلية | امتثال تنظيمي | تقرير هندسي"))

    tabs = st.tabs([
        "1️⃣ " + T("Project","المشروع"),
        "2️⃣ " + T("Zones","الزونات"),
        "3️⃣ " + T("Design & Schedule","التصميم والجدولة"),
        "4️⃣ " + T("Compliance & Reports","الامتثال والتقارير"),
        "5️⃣ " + T("BOQ","الكميات"),
        "6️⃣ " + T("Plot","المخطط"),
        "7️⃣ " + T("DXF","CAD"),
    ])

    # ============ Tab 1: Project ============
    with tabs[0]:
        st.subheader("📋 " + T("Project Setup","إعداد المشروع"))
        c1, c2, c3 = st.columns(3)
        with c1: proj_name = st.text_input(T("Project name","اسم المشروع"), key="proj_name")
        with c2:
            ptype = st.selectbox(T("Project type","نوع المشروع"),
                                 ["Agricultural","Landscape","Nursery"],
                                 format_func=lambda k: {"Agricultural":"🌾 إنتاج زراعي",
                                                        "Landscape":"🌳 لاندسكيب",
                                                        "Nursery":"🪴 مشتل"}[k],
                                 key="project_type")
        with c3:
            country = st.selectbox(T("Country (regulations)","الدولة (اللوائح)"),
                                   list(REGULATIONS.keys()),
                                   format_func=lambda k: REGULATIONS[k]["name"],
                                   key="country")
        reg = REGULATIONS[country]
        st.info(f"📜 {T('Regulations','اللوائح')}: {reg['notes_ar'] if st.session_state.lang=='ar' else reg['notes_en']}")

        st.markdown("---")
        st.subheader("📍 " + T("Location & Area","الموقع والمساحة"))
        
        # --- 1. Free Location Search ---
        st.markdown("##### 🔍 " + T("Search Location (Online)","ابحث عن موقع (أونلاين)"))
        sc1, sc2 = st.columns([3,1])
        with sc1:
            search_query = st.text_input(T("Type city or address (e.g. Larissa, Greece)","اكتب اسم المدينة أو العنوان"), key="search_q", placeholder="Larissa, Greece")
        with sc2:
            st.write("") # Spacer
            st.write("") # Spacer
            if st.button("🔍 " + T("Search","بحث"), use_container_width=True) and search_query:
                if REQUESTS_OK:
                    with st.spinner(T("Searching...","جاري البحث...")):
                        res = search_location_name(search_query)
                        if res:
                            st.session_state.search_lat, st.session_state.search_lon, st.session_state.loc_name = res
                            st.success(f"✅ {T('Found','تم العثور')}: {st.session_state.loc_name}")
                            st.rerun()
                        else:
                            st.error(T("Location not found","لم يتم العثور على الموقع"))
                else:
                    st.error("requests library missing")

        # --- 2. Area Mode ---
        area_mode = st.radio(T("Area Mode","طريقة تحديد المساحة"),
                            ["Manual","Polygon"],
                            horizontal=True, label_visibility="collapsed")

        lat, lon = st.session_state.search_lat, st.session_state.search_lon
        if area_mode == "Manual":
            am1, am2 = st.columns(2)
            with am1: area_unit = st.selectbox(T("Unit","الوحدة"), list(AREA_UNITS.keys()), format_func=lambda k: f"{AREA_UNITS[k]['ar']}", key="area_unit")
            with am2: area_value = st.number_input(T("Total Area","المساحة الإجمالية"), 0.01, 100000.0, key="area_value")
            st.session_state.pop("poly_coords", None)
            
            lc1, lc2 = st.columns(2)
            with lc1: lat = st.number_input("Center Latitude", -90.0, 90.0, value=lat, step=0.0001, format="%.4f")
            with lc2: lon = st.number_input("Center Longitude", -180.0, 180.0, value=lon, step=0.0001, format="%.4f")
            
        else:
            # Polygon Mode
            txt = st.text_area(T("Coords (lat, lon per line)","إحداثيات (lat, lon)"),
                              "30.5010, 30.4990\n30.5011, 30.5012\n30.4999, 30.5009\n30.5001, 30.4993", height=120)
            coords = []
            for ln in txt.strip().split("\n"):
                try:
                    a,b = ln.replace(";",",").split(",")
                    coords.append((float(a.strip()),float(b.strip())))
                except: pass
            
            if len(coords)>=3:
                a_m2 = polygon_area_m2(coords)
                area_value = a_m2 / AREA_UNITS["Feddan"]["m2"]
                area_unit = "Feddan"
                st.success(f"✅ {T('Calculated Area','المساحة المحسوبة')}: **{a_m2:,.0f} m²** = **{area_value:.2f} فدان**")
                st.session_state["poly_coords"] = coords
                
                # Calculate centroid for weather APIs
                poly_centroid = polygon_centroid(coords)
                if poly_centroid[0]:
                    lat, lon = poly_centroid
                    st.info(f"📍 {T('Center Point (for Weather/Soil)','مركز الأرض (للطقس والتربة)')}: {lat:.4f}, {lon:.4f}")
            else:
                area_value = 5.0; area_unit = "Feddan"
                st.session_state.pop("poly_coords", None)
                st.info(T("Enter at least 3 points to calculate area","أدخل 3 نقاط على الأقل لحساب المساحة"))

        st.session_state.total_area_value = area_value
        st.session_state.total_area_unit = area_unit

        st.markdown("---")
        st.subheader("🌤️ " + T("Auto-fill Climate & Soil","جلب بيانات المناخ والتربة"))
        ab1, ab2 = st.columns(2)
        with ab1:
            btn_api = st.button("🌐 " + T("Fetch from Location","جلب من الموقع"), use_container_width=True, disabled=not REQUESTS_OK)
        with ab2:
            btn_clim = st.button("🌍 " + T("Climate Preset","منطقة مناخية"), use_container_width=True)

        if btn_api:
            with st.spinner("🌐..."):
                eto_d = fetch_eto(lat, lon)
                soil_d = fetch_soil(lat, lon) if ptype=="Agricultural" else None
                loc_d = fetch_location(lat, lon)
            msg = []
            if eto_d and eto_d.get("eto"): st.session_state.eto_val = round(eto_d["eto"],1); msg.append("ETo")
            if eto_d and eto_d.get("wind") is not None: st.session_state.wind_val = round(eto_d["wind"],1); msg.append("Wind")
            if soil_d: st.session_state.soil_val = soil_d; msg.append("Soil")
            if loc_d: st.session_state.loc_name = loc_d; msg.append("Location")
            if msg: st.success(f"✅ {T('Fetched','جلب')}: {', '.join(msg)}")
            else: st.error(T("API failed","فشل API"))

        if btn_clim:
            st.session_state.show_clim = True
        if st.session_state.get("show_clim"):
            cc1, cc2 = st.columns([3,1])
            with cc1:
                clim = st.selectbox(T("Climate","المناخ"), list(CLIMATE_ZONES.keys()), format_func=lambda k: f"{CLIMATE_ZONES[k]['ar']} / {k}")
            with cc2:
                st.write("") 
                if st.button("✅", use_container_width=True):
                    z = CLIMATE_ZONES[clim]
                    st.session_state.eto_val = z["eto"]; st.session_state.wind_val = z["wind"]
                    st.session_state.loc_name = z["ar"]; st.session_state.show_clim = False
                    st.rerun()

        if st.session_state.loc_name:
            st.info(f"📍 **{T('Current Location','الموقع الحالي')}**: {st.session_state.loc_name}")

        st.markdown("---")
        st.subheader("💧 " + T("Water & Source","المياه والمصدر"))
        wq1, wq2, wq3 = st.columns(3)
        with wq1: ec = st.number_input("EC (dS/m)", 0.0, 20.0, step=0.1, key="ec_val")
        with wq2: ph = st.number_input("pH", 4.0, 10.0, step=0.1, key="ph_val")
        with wq3: sar = st.number_input("SAR", 0.0, 30.0, step=0.1, key="sar_val")
        
        ws1, ws2, ws3 = st.columns(3)
        with ws1: wsrc = st.selectbox(T("Water source","مصدر المياه"), ["Nile","Well","Reclaimed","Mixed"])
        with ws2: psrc = st.selectbox(T("Power","الطاقة"), ["Grid","Solar","Diesel"])
        with ws3: src_cap = st.number_input(T("Source capacity (m³/h)","قدرة المصدر (م³/س)"), 1.0, 500.0, 40.0, key="source_capacity")

        st.markdown("---")
        st.subheader("💰 " + T("Currency & VAT","العملة والضريبة"))
        cu1, cu2 = st.columns(2)
        with cu1: currency = st.selectbox(T("Currency","العملة"), list(CURRENCIES.keys()), key="currency")
        with cu2: vat = st.number_input("VAT %", 0.0, 30.0, key="vat_val")

        st.markdown("---")
        st.subheader("🔧 " + T("Shared Infrastructure","البنية التحتية المشتركة"))
        ic1, ic2 = st.columns(2)
        with ic1: filt = st.selectbox(T("Filter","الفلتر"), FILTERS, format_func=lambda k: FILTER_AR[k], key="filter_type")
        with ic2: fert = st.selectbox(T("Fertigation","التسميد"), FERT_SYS, format_func=lambda k: FERT_AR[k], key="fert_sys")

        e1, e2, e3 = st.columns(3)
        with e1: elev = st.number_input(T("Elevation (m)","المنسوب"), 0.0, 200.0, key="elevation")
        with e2: succ = st.number_input(T("Suction (m)","الشفط"), 0.0, 15.0, key="suction_lift")
        with e3: safety = st.number_input(T("Safety (m)","أمان"), 0.0, 30.0, key="safety")

        strat = st.radio(T("Operation strategy","استراتيجية التشغيل"),
                        ["sequential","parallel"],
                        format_func=lambda k: {"sequential":"🔄 تتابعي (زونة بعد الأخرى)",
                                               "parallel":"⚡ متوازي (حسب قدرة المصدر)"}[k],
                        horizontal=True, key="strategy")

        project = {
            "name": proj_name, "project_type": ptype, "country": country,
            "lat": lat, "lon": lon, "eto": st.session_state.eto_val,
            "wind": st.session_state.wind_val, "slope": st.session_state.slope_val,
            "ec": ec, "ph": ph, "sar": sar,
            "water_source": wsrc, "power_source": psrc,
            "source_capacity_m3h": src_cap,
            "currency": currency, "vat": vat,
            "filter_type": filt, "fert_sys": fert,
            "elevation": elev, "suction_lift": succ, "safety": safety,
            "strategy": strat,
        }
        st.session_state.project = project

    project = st.session_state.project
    if not project:
        st.info(T("Fill Project tab first","املأ بيانات المشروع"))
        return

    # ============ Tab 2: Zones ============
    with tabs[1]:
        st.subheader("🌾 " + T("Zones Manager","إدارة الزونات"))
        st.caption(T("Each zone = independent crop + system + soil", "كل زونة = محصول + نظام + تربة مستقلة"))
        
        if project["project_type"] == "Landscape":
            st.markdown("### 🎨 " + T("Quick Presets","قوالب جاهزة"))
            preset_name = st.selectbox(T("Choose preset","اختر قالب"), ["—"]+list(LANDSCAPE_PRESETS.keys()))
            if preset_name != "—" and st.button("✨ " + T("Create zones","إنشاء الزونات")):
                preset = LANDSCAPE_PRESETS[preset_name]
                zones = []
                total_a = st.session_state.get("total_area_value", 1.0)
                for i, p in enumerate(preset):
                    z = new_zone(len(zones)+1, "Landscape")
                    z["name"] = p["name"]; z["crop"] = p["crop"]; z["system"] = p["system"]
                    z["area_value"] = total_a * p["pct"]
                    z["area_unit"] = st.session_state.get("total_area_unit", "Feddan")
                    zones.append(z)
                st.session_state.zones = zones
                st.success(f"✅ {len(zones)} زونات"); st.rerun()
        
        c_add, c_info = st.columns([1,3])
        with c_add:
            if st.button("➕ " + T("Add zone","أضف زونة"), use_container_width=True):
                st.session_state.zones.append(new_zone(len(st.session_state.zones)+1, project["project_type"]))
                st.rerun()
        with c_info:
            st.info(f"📊 {len(st.session_state.zones)} " + T("zones","زونة"))

        total_zone_area = 0
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']} — {CROPS[z['crop']]['ar']} ({z['area_value']} {z['area_unit']})", expanded=(i==len(st.session_state.zones)-1)):
                col1, col2 = st.columns([3,1])
                with col1:
                    z["name"] = st.text_input(T("Zone name","اسم الزونة"), value=z["name"], key=f"zname_{z['id']}")
                with col2:
                    if st.button("🗑️", key=f"del_{z['id']}", use_container_width=True):
                        st.session_state.zones.pop(i); st.rerun()
                
                cc1, cc2 = st.columns(2)
                with cc1:
                    grp = PROJECT_CROP_GROUPS[project["project_type"]]
                    if z.get("group") not in grp: z["group"] = list(grp.keys())[0]
                    grp_sel = st.selectbox(T("Group","المجموعة"), list(grp.keys()),
                                          index=list(grp.keys()).index(z["group"]),
                                          key=f"grp_{z['id']}")
                    z["group"] = grp_sel
                with cc2:
                    crops_in = grp[grp_sel]
                    if z["crop"] not in crops_in: z["crop"] = crops_in[0]
                    z["crop"] = st.selectbox(T("Crop","المحصول"), crops_in,
                                            format_func=lambda k: f"{CROPS[k]['ar']} / {k}",
                                            index=crops_in.index(z["crop"]),
                                            key=f"crop_{z['id']}")
                
                ac1, ac2, ac3 = st.columns(3)
                with ac1: z["area_value"] = st.number_input(T("Area","المساحة"), 0.001, 10000.0, value=z["area_value"], step=0.1, key=f"av_{z['id']}")
                with ac2: z["area_unit"] = st.selectbox(T("Unit","الوحدة"), list(AREA_UNITS.keys()),
                                                        index=list(AREA_UNITS.keys()).index(z["area_unit"]),
                                                        format_func=lambda k: AREA_UNITS[k]["ar"],
                                                        key=f"au_{z['id']}")
                with ac3:
                    if project["project_type"] == "Agricultural":
                        z["soil"] = st.selectbox(T("Soil","التربة"), list(SOILS.keys()),
                                                index=list(SOILS.keys()).index(z.get("soil","Sandy Loam")),
                                                format_func=lambda k: SOILS[k]["ar"], key=f"soil_{z['id']}")
                    elif project["project_type"] == "Landscape":
                        z["media"] = st.selectbox(T("Media","البيئة"), list(LANDSCAPE_MEDIA.keys()),
                                                 format_func=lambda k: LANDSCAPE_MEDIA[k]["ar"], key=f"med_{z['id']}")
                    else:
                        z["media"] = st.selectbox(T("Media","البيئة"), list(NURSERY_MEDIA.keys()),
                                                 format_func=lambda k: NURSERY_MEDIA[k]["ar"], key=f"med_{z['id']}")
                
                sc1, sc2 = st.columns(2)
                with sc1: z["system"] = st.selectbox(T("System","النظام"), list(IRR_SYSTEMS.keys()),
                                                     index=list(IRR_SYSTEMS.keys()).index(z["system"]),
                                                     format_func=lambda k: IRR_SYSTEMS[k]["ar"], key=f"sys_{z['id']}")
                with sc2:
                    if z["system"] in ("drip","micro"):
                        z["emitter_flow"] = st.selectbox(T("Emitter flow (L/h)","تصرف المنقط"), DRIP_FLOWS,
                                                        index=DRIP_FLOWS.index(z.get("emitter_flow",2.0)),
                                                        key=f"ef_{z['id']}")
                    else:
                        z["emitter_flow"] = 0
                
                if z["system"] in ("drip","micro"):
                    ec1, ec2 = st.columns(2)
                    with ec1: z["emitter_spacing"] = st.number_input(T("Emitter spacing (m)","مسافة المنقط"), 0.1, 5.0, value=z.get("emitter_spacing",0.5), step=0.1, key=f"es_{z['id']}")
                    with ec2: z["lateral_spacing"] = st.number_input(T("Lateral spacing (m)","مسافة الخرطوم"), 0.1, 10.0, value=z.get("lateral_spacing",0.8), step=0.1, key=f"ls_{z['id']}")
                
                if CROPS[z["crop"]]["cat"] in PER_PLANT_CATS:
                    pc1, pc2 = st.columns(2)
                    with pc1: z["tree_spacing"] = st.number_input(T("Plant spacing (m)","مسافة النبات"), 0.2, 20.0, value=z.get("tree_spacing",5.0), step=0.5, key=f"ts_{z['id']}")
                    with pc2: z["row_spacing"] = st.number_input(T("Row spacing (m)","مسافة الصف"), 0.2, 20.0, value=z.get("row_spacing",6.0), step=0.5, key=f"rs_{z['id']}")
                
                total_zone_area += z["area_value"] if z["area_unit"]=="Feddan" else z["area_value"]*AREA_UNITS[z["area_unit"]]["m2"]/AREA_UNITS["Feddan"]["m2"]
        
        if st.session_state.zones:
            proj_area = st.session_state.get("total_area_value", 5.0)
            proj_unit = st.session_state.get("total_area_unit", "Feddan")
            proj_area_fed = proj_area if proj_unit=="Feddan" else proj_area*AREA_UNITS[proj_unit]["m2"]/AREA_UNITS["Feddan"]["m2"]
            if abs(total_zone_area - proj_area_fed) > 0.1:
                st.warning(f"⚠️ مجموع الزونات ({total_zone_area:.2f} فدان) ≠ المساحة الكلية ({proj_area_fed:.2f} فدان)")

    zones = st.session_state.zones
    if not zones:
        st.info(T("Add at least one zone","أضف زونة واحدة على الأقل"))
        return

    # === Compute designs ===
    designed_zones = [design_zone(z, project) for z in zones]
    agg = aggregate(designed_zones)
    scheduled_zones, total_hours = build_schedule(designed_zones, project["strategy"], project["source_capacity_m3h"])
    st.session_state.zones = scheduled_zones 
    
    compliance, reg = check_compliance(project, scheduled_zones, agg, total_hours)

    # ============ Tab 3: Design & Schedule ============
    with tabs[2]:
        st.subheader("📊 " + T("Design Results","نتائج التصميم"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(T("Zones","الزونات"), agg["n_zones"])
        c2.metric(T("Total area","المساحة"), f"{agg['total_area_m2']:,.0f} m²")
        c3.metric(T("Daily water","مياه يومية"), f"{agg['total_daily_water_m3']:.1f} m³")
        c4.metric(T("Annual","سنوي"), f"{agg['total_annual_m3']:.0f} m³")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(T("Peak zone flow","أعلى تصرف"), f"{agg['peak_flow_m3h']:.2f} m³/h")
        c2.metric(T("Sum flows","مجموع التصرفات"), f"{agg['sum_flows_m3h']:.2f} m³/h")
        c3.metric(T("Op hours","ساعات"), f"{total_hours:.1f} h")
        c4.metric(T("Source cap","قدرة المصدر"), f"{project['source_capacity_m3h']} m³/h")

        st.markdown("---")
        st.subheader("🌾 " + T("Per-Zone Design","تصميم كل زونة"))
        for z in scheduled_zones:
            with st.expander(f"▶ {z['name']} — {CROPS[z['crop']]['ar']} ({z['area_value']} {z['area_unit']})", expanded=False):
                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric("ETc (mm/d)", f"{z['etc']:.2f}")
                cc2.metric("RAW (mm)", f"{z['raw_mm']:.1f}")
                cc3.metric(T("Interval","الدورة"), f"{z['interval']}d")
                cc4.metric("TDH (m)", f"{z['tdh_zone']:.1f}")
                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric(T("Depth","العمق"), f"{z['gross_event_mm']:.1f} mm")
                cc2.metric(T("Volume","الحجم"), f"{z['event_volume_m3']:.1f} m³")
                cc3.metric(T("Flow","التصرف"), f"{z['zone_q_m3h']:.2f} m³/h")
                cc4.metric(T("Duration","المدة"), f"{z['duration_hr']:.2f} h")
                if z.get("per_plant"):
                    st.info(f"🌱 {T('Per plant','لكل نبات')}: {z['per_plant']['L_day']} L/d | {z['per_plant']['L_event']} L/event")

        st.markdown("---")
        st.subheader("🕐 " + T("Operation Schedule","جدول التشغيل"))
        st.caption(f"{T('Strategy','الاستراتيجية')}: {project['strategy']} | {T('Start','البداية')}: 05:00")
        
        sched_df = pd.DataFrame([
            {"Zone": z["name"], "Crop": CROPS[z["crop"]]["ar"],
             "Start": f"{z['start_hr']:.1f}:00", "End": f"{z['end_hr']:.1f}:00",
             "Duration": f"{z['duration_hr']:.2f}h", "Flow": f"{z['zone_q_m3h']:.2f}",
             "Interval": f"{z['interval']}d"}
            for z in scheduled_zones
        ])
        st.dataframe(sched_df, use_container_width=True)
        
        if MPL_OK:
            fig, ax = plt.subplots(figsize=(11, max(3, len(scheduled_zones)*0.6)))
            colors = ["#4CAF50","#2196F3","#FF9800","#E91E63","#9C27B0","#00BCD4","#FFC107","#795548"]
            for i, z in enumerate(scheduled_zones):
                ax.barh(i, z["duration_hr"], left=z["start_hr"], height=0.6,
                        color=colors[i%len(colors)], alpha=0.8, edgecolor="black")
                ax.text(z["start_hr"] + z["duration_hr"]/2, i, z["name"],
                        ha="center", va="center", color="white", fontweight="bold", fontsize=9)
            ax.set_yticks(range(len(scheduled_zones)))
            ax.set_yticklabels([z["name"] for z in scheduled_zones])
            ax.set_xlabel("Hour of Day")
            ax.set_xlim(0, 24)
            ax.set_title(f"Operation Timeline ({total_hours:.1f}h total)")
            ax.grid(True, axis="x", alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)

    # ============ Tab 4: Compliance & Reports ============
    with tabs[3]:
        st.subheader("⚖️ " + T("Regulatory Compliance","الامتثال التنظيمي"))
        st.info(f"📜 {reg['name']} — {reg['notes_ar'] if st.session_state.lang=='ar' else reg['notes_en']}")
        
        if not compliance:
            st.success("✅ " + T("Fully compliant","التصميم متوافق تماماً"))
        else:
            errors = [c for c in compliance if c[0]=="error"]
            warnings = [c for c in compliance if c[0]=="warning"]
            if errors: st.error(f"⛔ {len(errors)} " + T("errors","مخالفات حرجة"))
            if warnings: st.warning(f"⚠️ {len(warnings)} " + T("warnings","تحذيرات"))
            for sev, ar, en in compliance:
                msg = T(en, ar)
                (st.error if sev=="error" else st.warning)(msg)

        st.markdown("---")
        st.subheader("📄 " + T("Engineering Report","التقرير الهندسي"))
        report = build_engineering_report(project, scheduled_zones, agg, total_hours, compliance, reg)
        st.text_area(T("Report preview","معاينة"), report, height=400)
        st.download_button("⬇️ " + T("Download Report","تحميل التقرير"),
                          report.encode("utf-8"),
                          file_name=f"engineering_report_{project['name']}.txt",
                          mime="text/plain")

    # ============ Tab 5: BOQ ============
    with tabs[4]:
        st.subheader("💰 " + T("Bill of Quantities","جدول الكميات"))
        rows, subtotal, vat_amt, total = compute_boq(project, scheduled_zones, agg)
        curr_sym = CURRENCIES[project["currency"]]["ar"]
        df = pd.DataFrame(rows, columns=[T("Item","البند"), T("Spec","المواصفات"), f"{T('Cost','التكلفة')} ({curr_sym})"])
        st.dataframe(df, use_container_width=True)
        st.metric(T("Subtotal","قبل الضريبة"), fmt_money(subtotal, project["currency"]))
        st.metric(f"VAT {project['vat']:.0f}%", fmt_money(vat_amt, project["currency"]))
        st.metric(T("TOTAL","الإجمالي"), fmt_money(total, project["currency"]))
        st.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"),
                          file_name=f"boq_{project['name']}.csv")

    # ============ Tab 6: Plot ============
    with tabs[5]:
        st.subheader("🗺️ " + T("Plot","المخطط"))
        if MPL_OK:
            fig = build_plot(project, scheduled_zones)
            st.pyplot(fig)
            buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150); buf.seek(0)
            st.download_button("⬇️ PNG", buf,
                              file_name=f"plot_{project['name']}.png", mime="image/png")
        else:
            st.error("matplotlib missing")

    # ============ Tab 7: DXF ============
    with tabs[6]:
        st.subheader("📐 DXF")
        if not EZDXF_OK:
            st.error("ezdxf missing")
        else:
            _, _, _, total = compute_boq(project, scheduled_zones, agg)
            buf = build_dxf(project, scheduled_zones, total)
            if buf:
                st.download_button("⬇️ DXF", buf,
                                  file_name=f"design_{project['name']}.dxf",
                                  mime="application/dxf")
                st.success("✅ " + T("Ready","جاهز"))

if __name__ == "__main__":
    main()
