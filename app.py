"""
SMART IRRIGATION AI — V10.3 (Global)
=====================================
V10   : 28 مهمة أساسية
V10.1 : Polygon area (KML/GeoJSON/Coords)
V10.2 : AI Agent (Open-Meteo + SoilGrids + Nominatim)
V10.3 : Global (وحدات/عملات/VAT) + Landscape + Nursery + 85 محصول ونبات
Deps  : streamlit, pandas, numpy, ezdxf, matplotlib, requests
"""

import re, io, math, json
import numpy as np
import pandas as pd
import streamlit as st

try:
    import ezdxf; EZDXF_OK = True
except Exception:
    EZDXF_OK = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon as MplPolygon
    from matplotlib.lines import Line2D
    MPL_OK = True
except Exception:
    MPL_OK = False

try:
    import requests; REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

def T(en, ar):
    return en if st.session_state.get("lang","ar") == "en" else ar

# ============================================================
# GLOBAL UNITS
# ============================================================
AREA_UNITS = {
    "Feddan":  {"m2":4200.0,   "ar":"فدان"},
    "Hectare": {"m2":10000.0,  "ar":"هكتار"},
    "Acre":    {"m2":4047.0,   "ar":"أكر"},
    "Dunam":   {"m2":1000.0,   "ar":"دونم"},
    "m²":      {"m2":1.0,      "ar":"متر مربع"},
}

CURRENCIES = {
    "EGP": {"ar":"ج.م", "to_egp":1.0},
    "USD": {"ar":"$",   "to_egp":50.0},
    "EUR": {"ar":"€",   "to_egp":54.0},
    "SAR": {"ar":"ر.س","to_egp":13.3},
    "AED": {"ar":"د.إ","to_egp":13.6},
    "GBP": {"ar":"£",   "to_egp":63.0},
}

# ============================================================
# SOILS & MEDIA
# ============================================================
SOILS = {
    "Sandy":      {"taw":80, "ar":"رملية"},
    "Loamy Sand": {"taw":110,"ar":"رملية طميية"},
    "Sandy Loam": {"taw":140,"ar":"طميية رملية"},
    "Loam":       {"taw":170,"ar":"طميية"},
    "Clay Loam":  {"taw":190,"ar":"طميية طينية"},
    "Clay":       {"taw":210,"ar":"طينية"},
}

LANDSCAPE_MEDIA = {
    "Prepared Agricultural Soil": {"taw":150,"ar":"تربة زراعية مجهزة"},
    "Imported Topsoil":           {"taw":140,"ar":"تربة سطحية مستوردة"},
    "Sand-Soil Mix (60/40)":      {"taw":110,"ar":"خليط رمل/تربة 60/40"},
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
# CROPS DATABASE (~85 crop)
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

# Grouped by project type
PROJECT_CROP_GROUPS = {
    "Agricultural": {
        "🌾 Field Crops":  ["Wheat","Maize","Rice","Barley","Alfalfa","Cotton","Sunflower","Soybean","Sugar Beet","Sugarcane"],
        "🥬 Vegetables":   ["Tomato","Potato","Pepper","Cucumber","Eggplant","Onion","Garlic","Carrot","Lettuce","Cabbage","Watermelon","Melon","Strawberry","Zucchini","Bean"],
        "🍊 Orchards":     ["Olive","Citrus","Orange","Lemon","Mango","Date Palm","Grape","Apple","Pear","Peach","Fig","Pomegranate","Banana","Avocado"],
    },
    "Landscape": {
        "🌿 Turf":         ["Turf Bermuda","Turf Fescue","Turf Ryegrass","Turf Zoysia"],
        "🌳 Shrubs":       ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine","Oleander","Pittosporum","Vinca"],
        "🌴 Trees":        ["Ficus","Conocarpus","Eucalyptus","Delonix","Cassia","Washingtonia","Phoenix","Royal Palm"],
        "🌸 Flowering":    ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera","Gladiolus","Dahlia","Zinnia","Gazania","Lavender","Lily","Aster"],
        "🍃 Foliage":      ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"],
        "🌱 Groundcovers": ["Wedelia","Asparagus Fern","Liriope","Aptenia","Portulaca"],
        "🌿 Climbers":     ["Ivy","Wisteria","Passion Flower"],
        "🌵 Succulents":   ["Aloe Vera","Agave","Sedum"],
    },
    "Nursery": {
        "🌸 Flowering":    ["Rose","Petunia","Marigold","Geranium","Chrysanthemum","Carnation","Gerbera","Gladiolus","Dahlia","Zinnia","Lavender","Lily","Aster"],
        "🍃 Foliage":      ["Ficus Benjamina","Dracaena","Schefflera","Aglaonema","Croton"],
        "🌳 Shrubs":       ["Bougainvillea","Hibiscus","Lantana","Duranta","Jasmine","Oleander","Pittosporum","Vinca"],
        "🪴 Potted":       ["Potted Flowering","Potted Foliage","Potted Herb"],
    },
}

P_ALLOW = {
    "field":0.50,"veg":0.35,"orchard":0.55,"turf":0.50,"shrub":0.45,
    "tree":0.50,"flower":0.40,"foliage":0.45,"groundcover":0.45,
    "climber":0.45,"succulent":0.30,"pot":0.35,
}

PER_PLANT_CATS = {"orchard","tree","shrub","flower","foliage","pot","climber"}

DRIP_FLOWS = [1.6, 2.0, 4.0, 8.0, 16.0]
FILTERS = ["Screen Filter","Disc Filter","Media Filter","Hydrocyclone"]
FILTER_AR = {"Screen Filter":"فلتر شبكي","Disc Filter":"فلتر ديسكات",
             "Media Filter":"فلتر رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}
FERT_SYS = ["None","Venturi","Dosing Pump","Fertilizer Tank"]
FERT_AR = {"None":"بدون","Venturi":"فنتوري","Dosing Pump":"مضخة حقن","Fertilizer Tank":"تانك تسميد"}
FERT_PRICE = {"None":0,"Venturi":3500,"Dosing Pump":15000,"Fertilizer Tank":6000}

DEFAULT_PRICES = {"main":80.0,"sub":45.0,"lat":6.0,"drip":3.0,
                  "control":2500.0,"flush":450.0,"arv":1800.0,
                  "acid":12000.0,"treat":20000.0}

CLIMATE_ZONES = {
    "Arid/Desert":   {"eto":6.5,"wind":3.5,"ar":"صحراوي"},
    "Semi-Arid":     {"eto":5.5,"wind":3.0,"ar":"شبه جاف"},
    "Mediterranean": {"eto":4.8,"wind":3.0,"ar":"متوسطي"},
    "Subtropical":   {"eto":5.0,"wind":2.0,"ar":"شبه مداري"},
    "Tropical":      {"eto":4.5,"wind":1.5,"ar":"مداري"},
    "Temperate":     {"eto":3.5,"wind":2.5,"ar":"معتدل"},
    "Continental":   {"eto":3.0,"wind":3.0,"ar":"قاري"},
}

V_MIN_MAIN, V_MAX_MAIN = 0.6, 2.5
TDH_WARN = 120
DXF_EMITTER_LIMIT = 10000
MAX_PLOT_LINES = 3000

# ============================================================
# HYDRAULIC HELPERS
# ============================================================
def velocity_ms(q_lps, d_mm):
    if d_mm <= 0: return 0.0
    a = math.pi * (d_mm/1000.0)**2 / 4.0
    return (q_lps/1000.0) / a

def head_loss_hw(L_m, q_lps, d_mm, C=140.0):
    if d_mm <= 0 or q_lps <= 0: return 0.0
    Q = q_lps/1000.0; D = d_mm/1000.0
    return 10.67 * L_m * (Q**1.852) / ((C**1.852) * (D**4.87))

def to_currency(price_egp, curr):
    return price_egp / CURRENCIES[curr]["to_egp"]

def fmt_money(value, curr):
    sym = CURRENCIES[curr]["ar"]
    return f"{value:,.0f} {sym}"

# ============================================================
# WATER QUALITY
# ============================================================
def water_quality_warnings(ec, ph, sar):
    W = []
    if ec > 5:   W.append(("EC عالي (>5) — ري بالتنقيط مع غسيل أملاح","Very high EC (>5) — drip + leaching","warn"))
    elif ec > 3: W.append(("EC مرتفع (>3) — راقب تراكم الأملاح","High EC (>3) — monitor salts","info"))
    if ph > 8.2: W.append(("pH مرتفع (>8.2) — حقن حامض","High pH (>8.2) — acid injection","warn"))
    elif ph < 6.0:W.append(("pH منخفض (<6) — يحتاج تعديل","Low pH (<6) — may need adjustment","info"))
    if sar > 9:  W.append(("SAR عالي (>9) — خطر نفاذية","High SAR (>9) — infiltration risk","warn"))
    elif sar > 6:W.append(("SAR متوسط (>6) — راقب النفاذية","Medium SAR (>6) — monitor infiltration","info"))
    return W

# ============================================================
# RECOMMENDATIONS
# ============================================================
def recommend(P, R):
    L = []
    cat = CROPS[P["crop"]]["cat"]
    if cat == "veg":     L.append(("خضري — دورة ≤3 أيام","Vegetable — cycle ≤3d","info"))
    if cat == "orchard": L.append(("أشجار مثمرة — دورة أسبوعية","Orchard — weekly cycle","info"))
    if cat == "succulent":L.append(("عصاريات — ري نادر (10-14 يوم)","Succulents — infrequent (10-14d)","info"))
    if cat == "pot":     L.append(("أصص — ري يومي بكميات صغيرة","Potted — daily small volumes","info"))
    L += water_quality_warnings(P["ec"], P["ph"], P["sar"])
    if P["wind"] > 4:   L.append(("رياح قوية — عدّل التوقيت","Strong wind — adjust timing","warn"))
    if P["slope"] > 5:  L.append(("ميل >5% — PC dripper + زونات","Slope >5% — PC + zoning","warn"))
    if P["power_source"] == "Solar":  L.append(("طاقة شمسية — ري نهاري","Solar — daytime irrigation","info"))
    if P["water_source"] == "Well":   L.append(("بئر — فلتر رملي","Well — media filter","info"))
    if P["water_source"] == "Reclaimed":L.append(("مياه معالجة — معالجة إضافية","Reclaimed — extra treatment","warn"))
    if R["tdh"] > TDH_WARN:           L.append(("TDH >120 — زونات/booster","TDH >120 — zoning/booster","warn"))
    if R["v_main"] < V_MIN_MAIN:      L.append(("سرعة منخفضة — خطر ترسيب","Low velocity — sediment","warn"))
    if R["v_main"] > V_MAX_MAIN:      L.append(("سرعة مرتفعة — خطر تآكل","High velocity — erosion","warn"))
    return L

# ============================================================
# AI PARSER (multi-language)
# ============================================================
LOCATION_KWS = {
    "Cairo":["cairo","القاهرة"],"Alexandria":["alexandria","الإسكندرية"],
    "Matrouh":["matrouh","مطروح"],"Nubaria":["nubaria","النوبارية"],
    "Riyadh":["riyadh","الرياض"],"Jeddah":["jeddah","جدة"],
    "Dubai":["dubai","دبي"],"Abu Dhabi":["abu dhabi","أبوظبي"],
    "Doha":["doha","الدوحة"],"Kuwait":["kuwait","الكويت"],
    "Madrid":["madrid","مدريد"],"Rome":["rome","روما"],
    "Athens":["athens","أثينا"],"Istanbul":["istanbul","إسطنبول"],
    "Tunis":["tunis","تونس"],"Algiers":["algiers","الجزائر"],
    "Casablanca":["casablanca","الدار البيضاء"],
}

def parse_request(text):
    out = {"area":None,"area_unit":None,"crop":None,"location":None,
           "water_source":None,"project_type":None}
    if not text: return out
    m = re.search(r"(\d+(?:\.\d+)?)\s*(feddan|فدان|fed|acre|hectare|هكتار|ha|dunam|دونم)\b", text, re.I)
    if m:
        out["area"] = float(m.group(1))
        u = m.group(2).lower()
        if u in ("feddan","فدان","fed"): out["area_unit"]="Feddan"
        elif u in ("hectare","هكتار","ha"): out["area_unit"]="Hectare"
        elif u=="acre": out["area_unit"]="Acre"
        elif u in ("dunam","دونم"): out["area_unit"]="Dunam"
    tl = text.lower()
    for c in CROPS:
        if c.lower() in tl or CROPS[c]["ar"] in text: out["crop"]=c; break
    for city, kws in LOCATION_KWS.items():
        if any(k in tl or k in text for k in kws): out["location"]=city; break
    if any(w in tl for w in ["well","بئر"]): out["water_source"]="Well"
    elif any(w in tl for w in ["nile","نيل"]): out["water_source"]="Nile"
    elif any(w in tl for w in ["reclaimed","معالجة"]): out["water_source"]="Reclaimed"
    if any(w in tl for w in ["landscape","لاندسكيب","حديقة","park","garden"]):
        out["project_type"]="Landscape"
    elif any(w in tl for w in ["nursery","مشتل","إنتاج نباتات"]):
        out["project_type"]="Nursery"
    elif any(w in tl for w in ["crop","محصول","زراعة","farm","field"]):
        out["project_type"]="Agricultural"
    return out

# ============================================================
# POLYGON MODULE
# ============================================================
def polygon_area_m2(coords):
    if len(coords) < 3: return 0.0
    lat0 = sum(c[0] for c in coords)/len(coords)
    m_lat=111320.0; m_lon=111320.0*math.cos(math.radians(lat0))
    pts=[(lon*m_lon,lat*m_lat) for lat,lon in coords]
    s=0.0; n=len(pts)
    for i in range(n):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%n]
        s+=x1*y2-x2*y1
    return abs(s)/2.0

def polygon_bbox(coords):
    lats=[c[0] for c in coords]; lons=[c[1] for c in coords]
    lat0,lat1=min(lats),max(lats); lon0,lon1=min(lons),max(lons)
    latm=(lat0+lat1)/2
    W=(lon1-lon0)*111320.0*math.cos(math.radians(latm))
    H=(lat1-lat0)*111320.0
    return W,H,latm,(lon0+lon1)/2

def polygon_centroid(coords):
    if len(coords)<3: return None,None
    lat0=sum(c[0] for c in coords)/len(coords)
    m_lat=111320.0; m_lon=111320.0*math.cos(math.radians(lat0))
    pts=[(lon*m_lon,lat*m_lat) for lat,lon in coords]
    a=0.0;cx=0.0;cy=0.0;n=len(pts)
    for i in range(n):
        x1,y1=pts[i];x2,y2=pts[(i+1)%n]
        cr=x1*y2-x2*y1; a+=cr; cx+=(x1+x2)*cr; cy+=(y1+y2)*cr
    a/=2.0
    if a==0: return None,None
    return round(cy/(6*a)/m_lat,6), round(cx/(6*a)/m_lon,6)

def parse_kml_coords(kml_bytes):
    txt = kml_bytes.decode("utf-8", errors="ignore")
    m = re.search(r"<coordinates>(.*?)</coordinates>", txt, re.S)
    if not m: return []
    out=[]
    for tok in m.group(1).split():
        p=tok.split(",")
        if len(p)>=2:
            try: out.append((float(p[1]),float(p[0])))
            except: pass
    return out

def parse_geojson_coords(gj_bytes):
    try: gj=json.loads(gj_bytes.decode("utf-8",errors="ignore"))
    except: return []
    def find(n):
        if isinstance(n,list) and n and isinstance(n[0],list):
            if isinstance(n[0][0],list): return find(n[0])
            return [(lat,lon) for lon,lat in n]
        return []
    if gj.get("type")=="FeatureCollection":
        for f in gj.get("features",[]):
            g=f.get("geometry",{})
            if g.get("type") in ("Polygon","MultiPolygon"):
                return find(g["coordinates"])
    elif gj.get("type") in ("Polygon","MultiPolygon"):
        return find(gj["coordinates"])
    return []

# ============================================================
# API FETCHERS
# ============================================================
def usda_texture(sand, clay):
    if sand is None or clay is None: return None
    if clay>=40: return "Clay"
    if clay>=25 and sand<=45: return "Clay Loam"
    if sand>=85: return "Sandy"
    if sand>=70: return "Loamy Sand"
    if sand>=50: return "Sandy Loam"
    return "Loam"

def fetch_eto_openmeteo(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
            params={"latitude":lat,"longitude":lon,
                    "daily":"et0_fao_evapotranspiration,wind_speed_10m_max",
                    "timezone":"auto","forecast_days":3}, timeout=8)
        r.raise_for_status()
        d = r.json().get("daily",{})
        ev = [v for v in d.get("et0_fao_evapotranspiration",[]) if v is not None]
        wv = [v for v in d.get("wind_speed_10m_max",[]) if v is not None]
        return {"eto":sum(ev)/len(ev) if ev else None,
                "wind":(sum(wv)/len(wv))/3.6 if wv else None}
    except Exception:
        return None

def fetch_soil_soilgrids(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query",
            params=[("lon",lon),("lat",lat),("property","clay"),
                    ("property","sand"),("depth","0-30cm")], timeout=12)
        r.raise_for_status()
        layers = r.json().get("properties",{}).get("layers",[])
        vals={}
        for L in layers:
            d = L.get("depths",[])
            if d:
                v=d[0].get("values",{}).get("mean")
                if v is not None: vals[L.get("name")]=v/10.0
        return usda_texture(vals.get("sand"), vals.get("clay"))
    except Exception:
        return None

def fetch_location_name(lat, lon):
    if not REQUESTS_OK: return None
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
            params={"lat":lat,"lon":lon,"format":"json","accept-language":"ar"},
            headers={"User-Agent":"SmartIrrigationAI/10.3"}, timeout=8)
        r.raise_for_status()
        a = r.json().get("address",{})
        parts=[a.get("city") or a.get("town") or a.get("village") or a.get("county"), a.get("state")]
        return ", ".join([p for p in parts if p]) or r.json().get("display_name","")[:60]
    except Exception:
        return None

# ============================================================
# DESIGN ENGINE
# ============================================================
def run_design(P):
    ci = CROPS[P["crop"]]
    kc, zr, cat = ci["kc"], ci["zr"], ci["cat"]

    # Soil TAW per project type
    if P["project_type"] == "Agricultural":
        taw = float(SOILS[P["soil"]]["taw"])
    elif P["project_type"] == "Landscape":
        taw = float(LANDSCAPE_MEDIA[P["landscape_media"]]["taw"])
    else:  # Nursery
        taw = float(NURSERY_MEDIA[P["nursery_media"]]["taw"])

    raw_mm = P_ALLOW[cat] * taw * zr
    eto = float(P["eto"]); etc = eto * kc

    if cat in ("veg","flower","pot"):   max_int = 3
    elif cat in ("orchard","tree"):     max_int = 7
    elif cat == "succulent":            max_int = 14
    else:                               max_int = 5
    interval = max(1, min(raw_mm/etc if etc>0 else max_int, max_int))
    interval = int(round(interval))

    net_event_mm = etc * interval
    eff = 0.90
    gross_event_mm = net_event_mm/eff

    area_m2 = P["area_value"] * AREA_UNITS[P["area_unit"]]["m2"]
    poly_W = st.session_state.get("poly_W"); poly_H = st.session_state.get("poly_H")
    if poly_W and poly_H:
        field_W, field_H = float(poly_W), float(poly_H)
    else:
        field_W = field_H = math.sqrt(area_m2)

    vol_event_m3 = gross_event_mm * area_m2 / 1000.0
    annual_m3 = (etc * 365 / eff) * area_m2 / 1000.0

    n_zones = max(1,int(P["n_zones"]))
    zone_area = area_m2/n_zones
    spacing=float(P["dripper_spacing"]); lat_sp=float(P["lateral_spacing"])
    emitters_m2 = 1.0/(spacing*lat_sp) if spacing>0 and lat_sp>0 else 0
    zone_emitters = int(emitters_m2*zone_area)
    q_drip=float(P["dripper_flow"])
    zone_q_lph=zone_emitters*q_drip
    zone_q_lps=zone_q_lph/3600.0

    D_main=float(P["d_main"]); D_sub=float(P["d_sub"]); D_lat=float(P["d_lat"])
    L_main=float(P["L_main"]); L_sub=float(P["L_sub"]); L_lat=float(P["L_lat"])

    v_main = velocity_ms(zone_q_lps, D_main)
    v_sub  = velocity_ms(zone_q_lps*0.5, D_sub)
    n_lat_per_sub = max(1,int(L_sub/lat_sp)) if lat_sp>0 else 1
    q_one_lat_lps = zone_q_lps/n_lat_per_sub
    v_lat = velocity_ms(q_one_lat_lps, D_lat)

    hf_main = head_loss_hw(L_main, zone_q_lps, D_main)
    hf_sub  = 0.4*head_loss_hw(L_sub, zone_q_lps, D_sub)
    hf_lat  = 0.36*head_loss_hw(L_lat, q_one_lat_lps, D_lat)

    op_press = 15.0 if P["pc_dripper"]=="PC Dripper" else 10.0+hf_lat
    tdh = max(0.0,float(P["elevation"])) + float(P["suction_lift"]) + hf_main + hf_sub + hf_lat + op_press + float(P["safety"])

    per_plant = None
    if cat in PER_PLANT_CATS and P.get("tree_spacing",0)>0 and P.get("row_spacing",0)>0:
        sx=float(P["tree_spacing"]); sy=float(P["row_spacing"])
        L_day = etc*(sx*sy); L_ev = L_day*interval
        per_plant = {"L/day":round(L_day,1), "L/event":round(L_ev,1)}

    R = dict(kc=kc, cat=cat, zr=zr, p_allow=P_ALLOW[cat], taw=taw,
             raw_mm=raw_mm, etc=etc, eto=eto, interval=interval,
             net_event_mm=net_event_mm, gross_event_mm=gross_event_mm,
             event_depth_mm=gross_event_mm, event_volume_m3=vol_event_m3,
             annual_m3=annual_m3, area_m2=area_m2, n_zones=n_zones,
             zone_area_m2=zone_area, zone_emitters=zone_emitters,
             zone_q_lps=zone_q_lps, zone_q_m3h=zone_q_lph/1000.0,
             v_main=v_main, v_sub=v_sub, v_lat=v_lat,
             hf_main=hf_main, hf_sub=hf_sub, hf_lat=hf_lat,
             tdh=tdh, op_pressure=op_press, per_plant=per_plant,
             D_main=D_main, D_sub=D_sub, D_lat=D_lat,
             L_main=L_main, L_sub=L_sub, L_lat=L_lat,
             field_W=field_W, field_H=field_H)
    R["recommendations"] = recommend(P, R)
    return R

# ============================================================
# BOQ
# ============================================================
def compute_boq(P, R, vat=14.0):
    curr = P["currency"]
    rows = []
    rows.append((T("Main pipe","مواسير رئيسي"),   f"{R['L_main']:.0f} m", R["L_main"]*DEFAULT_PRICES["main"]))
    rows.append((T("Submain","فرعي"),              f"{R['L_sub']:.0f} m",  R["L_sub"]*DEFAULT_PRICES["sub"]))
    n_z = R["n_zones"]
    rows.append((T("Lateral","خراطيم"),            f"{R['L_lat']*n_z:.0f} m", R["L_lat"]*n_z*DEFAULT_PRICES["lat"]))
    tot_drip = R["zone_emitters"]*n_z
    rows.append((T("Drippers","منقطات"),           f"{tot_drip:,}", tot_drip*DEFAULT_PRICES["drip"]))
    rows.append((T("Filter","فلتر"),               FILTER_AR.get(P["filter_type"],P["filter_type"]), FILTER_PRICE.get(P["filter_type"],0)))
    if FERT_PRICE.get(P["fert_sys"],0)>0:
        rows.append((T("Fertigation","تسميد"),     FERT_AR.get(P["fert_sys"],P["fert_sys"]), FERT_PRICE[P["fert_sys"]]))
    rows.append((T("Control valves","محابس تحكم"), f"{n_z}", n_z*DEFAULT_PRICES["control"]))
    rows.append((T("Flush valves","محابس غسيل"),   f"{n_z*2}", n_z*2*DEFAULT_PRICES["flush"]))
    rows.append((T("Air release valves","محابس هواء"), "4", 4*DEFAULT_PRICES["arv"]))
    if P["ph"]>8.2: rows.append((T("Acid injection","حقن حامض"), "1", DEFAULT_PRICES["acid"]))
    if P["ec"]>5:   rows.append((T("Water treatment","معالجة مياه"), "-", DEFAULT_PRICES["treat"]))
    before = sum(r[2] for r in rows)
    rows.append((T("Fittings (10%)","وصلات 10%"), "-", 0.10*before))
    # convert to currency
    rows_curr = [(r[0], r[1], to_currency(r[2], curr)) for r in rows]
    subtotal = sum(r[2] for r in rows_curr)
    vat_amt = subtotal*vat/100
    total = subtotal+vat_amt
    return rows_curr, subtotal, vat_amt, total

# ============================================================
# PLOT
# ============================================================
def build_plot(P, R):
    W = R.get("field_W", math.sqrt(R["area_m2"]))
    H = R.get("field_H", W)
    fig, ax = plt.subplots(figsize=(10,10))
    poly = st.session_state.get("poly_coords")
    if poly and len(poly)>=3:
        xs=[c[1] for c in poly]; ys=[c[0] for c in poly]
        xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
        sx=W/max(1e-6,(xmax-xmin)); sy=H/max(1e-6,(ymax-ymin))
        poly_xy=[((lon-xmin)*sx,(lat-ymin)*sy) for lat,lon in poly]
        ax.add_patch(MplPolygon(poly_xy, closed=True, fill=False, edgecolor="black", lw=2.5))
    else:
        ax.add_patch(Rectangle((0,0), W, H, fill=False, lw=2))
        ax.plot([0,W],[H,H], color="blue", lw=2.5)
    n_sub=min(15,max(2,int(W/40)+1))
    xs_=[i*W/(n_sub-1) if n_sub>1 else W/2 for i in range(n_sub)]
    for x in xs_: ax.plot([x,x],[0,H], color="green", lw=1, alpha=0.6)
    trunc=False; drawn=0
    for x in xs_:
        for j in range(30):
            y=j*H/29 if 30>1 else H/2
            ax.plot([max(0,x-W/(2*n_sub)),min(W,x+W/(2*n_sub))],[y,y], color="orange", lw=0.3, alpha=0.5)
            drawn+=1
            if drawn>=MAX_PLOT_LINES: trunc=True; break
        if trunc: break
    ax.annotate("", xy=(W*0.95,H*1.02), xytext=(W*0.95,H*0.9),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.text(W*0.95, H*1.03, "N", ha="center", fontsize=12, fontweight="bold")
    s_len=round(W/5)
    ax.plot([W*0.05,W*0.05+s_len],[H*0.05,H*0.05], color="black", lw=4)
    ax.text(W*0.05+s_len/2, H*0.02, f"{s_len} m", ha="center")
    ax.plot(W*0.02, H*0.98, marker="s", ms=12, color="red")
    ax.text(W*0.04, H*0.98, T("Pump","مضخة"), fontsize=10)
    ax.text(W*0.5, H*0.5, f"{P['project_name']}\n{P['area_value']:.2f} {P['area_unit']}\n{CROPS[P['crop']]['ar']}",
            ha="center", va="center", fontsize=12,
            bbox=dict(boxstyle="round", fc="white", ec="black"))
    ax.set_xlim(-W*0.05, W*1.1); ax.set_ylim(-H*0.05, H*1.1)
    ax.set_aspect("equal"); ax.set_title(T("Plot Layout","مخطط الحقل"))
    handles=[Line2D([0],[0],color="blue",lw=2,label="Main"),
             Line2D([0],[0],color="green",lw=1,label="Submain"),
             Line2D([0],[0],color="orange",lw=0.5,label="Lateral")]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    plt.tight_layout()
    return fig, {"truncated":trunc}

# ============================================================
# DXF
# ============================================================
def build_dxf(P, R, vat_pct, total_cost, curr):
    if not EZDXF_OK: return None
    doc=ezdxf.new("R2010"); msp=doc.modelspace()
    for lay in ["MAIN","SUBMAIN","LATERAL","EMITTER","FILTER","FERTIGATION",
                "AIR_RELEASE","FLUSH","CONTROL","HYDRANT","LABELS","TITLE"]:
        if lay not in doc.layers: doc.layers.add(lay)
    W=R.get("field_W", math.sqrt(R["area_m2"])); H=R.get("field_H", W)
    msp.add_lwpolyline([(0,0),(W,0),(W,H),(0,H),(0,0)], dxfattribs={"layer":"MAIN"})
    msp.add_line((0,H),(W,H), dxfattribs={"layer":"MAIN"})
    n_sub=min(15,max(2,int(W/40)+1))
    xs_=[i*W/(n_sub-1) if n_sub>1 else W/2 for i in range(n_sub)]
    for x in xs_: msp.add_line((x,0),(x,H), dxfattribs={"layer":"SUBMAIN"})
    n_lat=30; emit_drawn=0
    for x in xs_:
        for j in range(n_lat):
            y=j*H/(n_lat-1) if n_lat>1 else H/2
            x1=max(0,x-W/(2*n_sub)); x2=min(W,x+W/(2*n_sub))
            msp.add_line((x1,y),(x2,y), dxfattribs={"layer":"LATERAL"})
            for k in range(5):
                if emit_drawn>=DXF_EMITTER_LIMIT: break
                msp.add_circle((x1+(x2-x1)*(k+0.5)/5, y), 0.05, dxfattribs={"layer":"EMITTER"})
                emit_drawn+=1
    for x in xs_:
        msp.add_circle((x,0),0.3,dxfattribs={"layer":"FLUSH"})
        msp.add_circle((x,H),0.3,dxfattribs={"layer":"FLUSH"})
    for pt in [(0,H),(W,H)]: msp.add_circle(pt,0.4,dxfattribs={"layer":"AIR_RELEASE"})
    msp.add_circle((W*0.05,H*0.03),1.0,dxfattribs={"layer":"FILTER"})
    t=msp.add_text("FILTER",dxfattribs={"layer":"LABELS","height":1.0}); t.dxf.insert=(W*0.05+1.2,H*0.03)
    if P["fert_sys"]!="None":
        msp.add_circle((W*0.05,H*0.07),1.0,dxfattribs={"layer":"FERTIGATION"})
        t=msp.add_text(P["fert_sys"].upper(),dxfattribs={"layer":"LABELS","height":1.0}); t.dxf.insert=(W*0.05+1.2,H*0.07)
    msp.add_circle((W*0.1,H),0.5,dxfattribs={"layer":"CONTROL"})
    msp.add_circle((W*0.5,H*0.5),0.5,dxfattribs={"layer":"HYDRANT"})
    title=f"{P['project_name']} | {P['crop']} | {P['area_value']:.2f} {P['area_unit']}"
    t=msp.add_text(title,dxfattribs={"layer":"TITLE","height":2.0}); t.dxf.insert=(W*0.02,H*1.10)
    t=msp.add_text(f"Total incl VAT ({vat_pct:.0f}%): {total_cost:,.0f} {CURRENCIES[curr]['ar']}",
                   dxfattribs={"layer":"TITLE","height":1.5}); t.dxf.insert=(W*0.02,H*1.05)
    buf=io.BytesIO(); doc.saveas(buf); buf.seek(0)
    return buf

# ============================================================
# REPORTS
# ============================================================
def agronomic_report_text(P, R):
    L=["="*60, T("AGRONOMIC REPORT","التقرير الزراعي"), "="*60]
    if st.session_state.get("loc_name"):
        L.append(f"{T('Location','الموقع')}: {st.session_state.loc_name}")
    L.append(f"{T('Project','المشروع')}: {P['project_name']}")
    L.append(f"{T('Type','النوع')}: {P['project_type']}")
    L.append(f"{T('Crop','المحصول')}: {P['crop']} ({CROPS[P['crop']]['ar']})")
    L.append(f"{T('Category','الفئة')}: {R['cat']}")
    L.append(f"{T('Area','المساحة')}: {P['area_value']:.2f} {P['area_unit']} ({R['area_m2']:.0f} m2)")
    L.append("")
    L.append(f"{T('Kc','معامل المحصول')}: {R['kc']:.2f}")
    L.append(f"ETo: {R['eto']:.2f} mm/day")
    L.append(f"ETc: {R['etc']:.2f} mm/day")
    L.append(f"{T('RAW','المياه المتاحة')}: {R['raw_mm']:.1f} mm")
    L.append(f"{T('Interval','دورة الري')}: {R['interval']} day(s)")
    L.append(f"{T('Depth/event','عمق الريّة')}: {R['event_depth_mm']:.1f} mm")
    L.append(f"{T('Volume/event','حجم الريّة')}: {R['event_volume_m3']:.1f} m3")
    L.append(f"{T('Annual water','الاستهلاك السنوي')}: {R['annual_m3']:.0f} m3")
    if R["per_plant"]:
        L.append(f"{T('Water/plant/day','مياه/نبات/يوم')}: {R['per_plant']['L/day']} L")
        L.append(f"{T('Water/plant/event','مياه/نبات/ريّة')}: {R['per_plant']['L/event']} L")
    L.append("")
    L.append(T("--- Water Quality ---","--- جودة المياه ---"))
    L.append(f"EC: {P['ec']} dS/m | pH: {P['ph']} | SAR: {P['sar']}")
    L.append("")
    L.append(T("--- Recommendations ---","--- التوصيات ---"))
    for ar,en,lvl in R["recommendations"]:
        L.append(f"[{lvl.upper()}] {T(en,ar)}")
    return "\n".join(L)

# ============================================================
# SESSION INIT
# ============================================================
def init_session():
    defaults = {
        "lang":"ar","eto_val":5.5,"wind_val":2.0,"slope_val":0.0,
        "ec_val":1.2,"ph_val":7.5,"sar_val":3.0,
        "soil_val":"Sandy Loam","lat_val":30.50,"lon_val":30.50,
        "loc_name":"","loc_source":"","proj_name":"Project-01",
        "area_unit":"Feddan","currency":"EGP","vat_val":14.0,
        "project_type":"Agricultural",
    }
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

# ============================================================
# MAIN UI
# ============================================================
def main():
    st.set_page_config(page_title="Smart Irrigation AI V10.3", layout="wide",
                       initial_sidebar_state="expanded")
    init_session()

    with st.sidebar:
        lang_sel = st.selectbox("Language / اللغة", ["العربية","English"])
        st.session_state.lang = "ar" if lang_sel=="العربية" else "en"
        st.markdown("---")
        st.caption("Smart Irrigation AI — V10.3")
        st.caption("Global + Landscape + Nursery")
        st.markdown("---")
        if REQUESTS_OK: st.success("🌐 APIs متاحة")
        else:            st.warning("⚠️ requests غير مثبتة")

    st.title("💧 " + T("Smart Irrigation AI V10.3","الري الذكي V10.3"))
    st.caption(T("Global | 85+ crops | 3 project types | Auto-fill from location",
                 "عالمي | 85+ محصول | 3 أنواع مشاريع | Auto-fill من الموقع"))

    # Quick AI setup
    st.markdown("### 🤖 " + T("Quick Setup","إعداد سريع"))
    q = st.text_input(T("Describe your project","اكتب وصف مشروعك"), "",
                      placeholder=T("e.g. 25 feddans olive in Matrouh with well / 2 hectares landscape in Dubai",
                                    "مثال: 25 فدان زيتون في مطروح / 2 هكتار لاندسكيب في دبي"))
    parsed = parse_request(q)
    if any(v is not None for v in parsed.values()):
        st.success(f"🔎 {parsed}")

    # ============ PROJECT TYPE (top-level choice) ============
    st.markdown("### 🎯 " + T("Project Type","نوع المشروع"))
    pt1, pt2, pt3 = st.columns(3)
    pt_options = [
        ("Agricultural", "🌾 " + T("Agricultural Production","إنتاج زراعي"),
         T("Field crops, vegetables, orchards (natural soil)","محاصيل، خضروات، أشجار (تربة طبيعية)")),
        ("Landscape", "🌳 " + T("Landscape","لاندسكيب"),
         T("Gardens, parks, green areas (prepared soil)","حدائق، منتزهات (تربة مجهزة)")),
        ("Nursery", "🪴 " + T("Ornamental Nursery","مشتل نباتات"),
         T("Plant production (growing media)","إنتاج نباتات (بيئة نمو)")),
    ]
    for col, (key, label, desc) in zip([pt1,pt2,pt3], pt_options):
        with col:
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.project_type==key else "secondary",
                         key=f"pt_{key}"):
                st.session_state.project_type = key
                st.session_state.pop("selected_crop", None)
                st.rerun()
            st.caption(desc)

    project_type = st.session_state.project_type

    tabs = st.tabs([
        "📝 " + T("Inputs","المدخلات"),
        "📊 " + T("Design","التصميم"),
        "🌾 " + T("Agronomic","زراعي"),
        "💧 " + T("Water","المياه"),
        "💰 " + T("BOQ","الكميات"),
        "🗺️ " + T("Plot","المخطط"),
        "📐 DXF",
    ])

    # ============ Tab 0: Inputs ============
    with tabs[0]:
        st.subheader("📋 " + T("Project Info","بيانات المشروع"))
        c1, c2, c3 = st.columns(3)
        with c1: proj = st.text_input(T("Project name","اسم المشروع"), key="proj_name")
        with c2:
            crop_groups = PROJECT_CROP_GROUPS[project_type]
            group = st.selectbox(T("Group","المجموعة"), list(crop_groups.keys()))
        with c3:
            crops_in_group = crop_groups[group]
            default_crop = parsed.get("crop")
            if default_crop in crops_in_group: idx = crops_in_group.index(default_crop)
            else: idx = 0
            crop = st.selectbox(T("Crop","المحصول"), crops_in_group,
                                format_func=lambda k: f"{CROPS[k]['ar']} / {k}", index=idx)

        # --- Location & Auto-fill ---
        st.markdown("---")
        st.subheader("📍 " + T("Location & Auto-fill","الموقع والجلب التلقائي"))
        cl1, cl2 = st.columns(2)
        with cl1: lat = st.number_input(T("Latitude","خط العرض"), -90.0, 90.0, step=0.0001, key="lat_val", format="%.4f")
        with cl2: lon = st.number_input(T("Longitude","خط الطول"), -180.0, 180.0, step=0.0001, key="lon_val", format="%.4f")

        if st.session_state.loc_name:
            src = {"api":"🌐 API","region":"📚 Climate"}.get(st.session_state.loc_source,"")
            st.info(f"📍 **{st.session_state.loc_name}**  {src}")

        ab1, ab2 = st.columns(2)
        with ab1:
            btn_api = st.button("🌐 " + T("Auto-fill from APIs","جلب من الإنترنت"),
                                use_container_width=True, disabled=not REQUESTS_OK)
        with ab2:
            btn_region = st.button("🌍 " + T("Climate preset","منطقة مناخية"),
                                   use_container_width=True)

        if btn_api:
            with st.spinner("🌐 " + T("Contacting services...","جاري الاتصال...")):
                eto_data = fetch_eto_openmeteo(lat,lon)
                soil_class = fetch_soil_soilgrids(lat,lon)
                loc_name = fetch_location_name(lat,lon)
            updated=[]
            if eto_data and eto_data.get("eto") and eto_data["eto"]>0.5:
                st.session_state.eto_val = round(eto_data["eto"],1); updated.append("ETo")
            if eto_data and eto_data.get("wind") is not None:
                st.session_state.wind_val = round(eto_data["wind"],1); updated.append("Wind")
            if soil_class and project_type=="Agricultural":
                st.session_state.soil_val = soil_class; updated.append("Soil")
            if loc_name:
                st.session_state.loc_name = loc_name; updated.append("Location")
            if updated:
                st.session_state.loc_source = "api"
                st.session_state.last_fill_msg = f"✅ {T('Fetched','تم جلب')}: {', '.join(updated)}"
                st.rerun()
            else:
                st.error(T("API failed — try climate preset","فشل — استخدم منطقة مناخية"))

        if btn_region:
            st.session_state.show_climate = True

        if st.session_state.get("show_climate"):
            rc1, rc2 = st.columns([3,1])
            with rc1:
                rc = st.selectbox(T("Climate zone","المنطقة المناخية"),
                                  list(CLIMATE_ZONES.keys()),
                                  format_func=lambda k: f"{CLIMATE_ZONES[k]['ar']} / {k}")
            with rc2:
                if st.button("✅ " + T("Apply","تطبيق"), use_container_width=True):
                    z = CLIMATE_ZONES[rc]
                    st.session_state.eto_val = z["eto"]
                    st.session_state.wind_val = z["wind"]
                    st.session_state.loc_name = z["ar"]
                    st.session_state.loc_source = "region"
                    st.session_state.show_climate = False
                    st.session_state.last_fill_msg = f"✅ {T('Applied','تم تطبيق')}: {z['ar']}"
                    st.rerun()

        if st.session_state.get("last_fill_msg"):
            st.success(st.session_state.last_fill_msg)
            del st.session_state.last_fill_msg

        # --- Area & Currency ---
        st.markdown("---")
        st.markdown("### 🗺️ " + T("Area & Currency","المساحة والعملة"))
        am1, am2, am3 = st.columns(3)
        with am1:
            area_unit = st.selectbox(T("Area unit","وحدة المساحة"), list(AREA_UNITS.keys()),
                                     format_func=lambda k: f"{AREA_UNITS[k]['ar']} / {k}",
                                     key="area_unit")
        with am2:
            currency = st.selectbox(T("Currency","العملة"), list(CURRENCIES.keys()),
                                    key="currency")
        with am3:
            vat = st.number_input("VAT %", 0.0, 30.0, key="vat_val")

        area_mode = st.radio(T("How to define area?","إزاي تحدد المساحة؟"),
            [T("Manual","يدوي"),T("Coordinates","إحداثيات"),T("Upload KML/GeoJSON","رفع ملف")],
            horizontal=True, label_visibility="collapsed")

        if area_mode == T("Manual","يدوي"):
            area = st.number_input(f"{T('Area','المساحة')} ({AREA_UNITS[area_unit]['ar']})",
                                   0.001, 100000.0, float(parsed.get("area") or 5.0))
            st.session_state.pop("poly_W", None); st.session_state.pop("poly_H", None)
            st.session_state.pop("poly_coords", None)
        else:
            coords=[]
            if area_mode == T("Coordinates","إحداثيات"):
                txt = st.text_area(T("Paste (lat, lon) — one per line","الصق (lat, lon) — سطر لكل نقطة"),
                    "30.5010, 30.4990\n30.5011, 30.5012\n30.4999, 30.5009\n30.5001, 30.4993",
                    height=140)
                for line in txt.strip().split("\n"):
                    try:
                        a,b = line.replace(";",",").split(",")
                        coords.append((float(a.strip()),float(b.strip())))
                    except: pass
            else:
                up = st.file_uploader(T("Upload","ارفع"), type=["kml","geojson","json"])
                if up is not None:
                    nm = up.name.lower(); raw = up.read()
                    coords = parse_kml_coords(raw) if nm.endswith(".kml") else parse_geojson_coords(raw)
            if len(coords)>=3:
                a_m2 = polygon_area_m2(coords)
                pW,pH,c_lat_c,c_lon_c = polygon_bbox(coords)
                area_in_unit = a_m2 / AREA_UNITS[area_unit]["m2"]
                st.success(f"✅ {T('Area','المساحة')}: **{a_m2:,.0f} m²** = "
                           f"**{area_in_unit:.2f} {AREA_UNITS[area_unit]['ar']}** | BBox: {pW:.0f}×{pH:.0f} m")
                area = area_in_unit
                st.session_state["poly_W"]=pW; st.session_state["poly_H"]=pH
                st.session_state["poly_coords"]=coords
                c_lat, c_lon = polygon_centroid(coords)
                if c_lat and c_lon:
                    st.session_state.lat_val = c_lat; st.session_state.lon_val = c_lon
                    st.caption(f"📍 {T('Centroid','المركز')}: {c_lat:.4f}, {c_lon:.4f}")
            else:
                st.info(T("3 نقاط على الأقل","At least 3 points"))
                area = 5.0
                for k in ("poly_W","poly_H","poly_coords"): st.session_state.pop(k,None)

        # --- Agronomic ---
        st.markdown("---")
        st.subheader("🌾 " + T("Agronomic","الزراعة"))
        a1,a2,a3 = st.columns(3)
        with a1: eto = st.number_input("ETo (mm/day)", 0.5, 20.0, step=0.1, key="eto_val")
        with a2: wind = st.number_input(T("Wind (m/s)","الرياح"), 0.0, 20.0, step=0.1, key="wind_val")
        with a3: slope = st.number_input(T("Slope %","الميل %"), 0.0, 50.0, step=0.1, key="slope_val")

        # Soil per project type
        a4,a5,a6 = st.columns(3)
        with a4:
            if project_type == "Agricultural":
                soil = st.selectbox(T("Soil","التربة"), list(SOILS.keys()),
                                    format_func=lambda k: f"{SOILS[k]['ar']} / {k}", key="soil_val")
                lm = None; nm = None
            elif project_type == "Landscape":
                soil = None
                lm = st.selectbox(T("Prepared soil mix","خليط التربة المجهزة"),
                                  list(LANDSCAPE_MEDIA.keys()),
                                  format_func=lambda k: LANDSCAPE_MEDIA[k]["ar"])
                nm = None
                st.caption(T("🌱 Soil fixed to prepared mix for landscape",
                             "🌱 التربة ثابتة: خليط مجهز للاندسكيب"))
            else:  # Nursery
                soil = None; lm = None
                nm = st.selectbox(T("Growing media","بيئة النمو"),
                                  list(NURSERY_MEDIA.keys()),
                                  format_func=lambda k: NURSERY_MEDIA[k]["ar"])
                st.caption(T("🌱 Growing media fixed for nursery",
                             "🌱 بيئة نمو ثابتة للمشتل"))
        with a5: wsrc = st.selectbox(T("Water source","مصدر المياه"), ["Nile","Well","Reclaimed","Mixed"])
        with a6: psrc = st.selectbox(T("Power","الطاقة"), ["Grid","Solar","Diesel"])

        # --- Water Quality ---
        st.markdown("---")
        st.subheader("💧 " + T("Water Quality","جودة المياه"))
        w1,w2,w3 = st.columns(3)
        with w1: ec = st.number_input("EC (dS/m)", 0.0, 20.0, step=0.1, key="ec_val")
        with w2: ph = st.number_input("pH", 4.0, 10.0, step=0.1, key="ph_val")
        with w3: sar = st.number_input("SAR", 0.0, 30.0, step=0.1, key="sar_val")

        # --- Emitter ---
        st.markdown("---")
        st.subheader("💧 " + T("Emitter","المنقط"))
        e1,e2,e3 = st.columns(3)
        with e1: dflow = st.selectbox(T("Dripper flow (L/h)","التصرف"), DRIP_FLOWS, index=1)
        with e2: pc = st.selectbox(T("Type","النوع"), ["PC Dripper","Non-PC Dripper"])
        with e3: dsp = st.number_input(T("Dripper spacing (m)","مسافة المنقط"), 0.1, 5.0, 0.5)
        e4,e5 = st.columns(2)
        with e4: lsp = st.number_input(T("Lateral spacing (m)","مسافة الخراطيم"), 0.1, 10.0, 0.8)
        cat_now = CROPS[crop]["cat"]
        need_spacing = cat_now in PER_PLANT_CATS
        with e5:
            tsp = st.number_input(T("Plant spacing (m)","مسافة النباتات"), 0.2, 20.0, 5.0 if cat_now in ("orchard","tree") else 0.5) if need_spacing else 5.0
        rsp = st.number_input(T("Row spacing (m)","مسافة الصفوف"), 0.2, 20.0, 6.0 if cat_now in ("orchard","tree") else 1.0) if need_spacing else 6.0

        # --- Filter & Fertigation ---
        st.markdown("---")
        st.subheader("🔧 " + T("Filter & Fertigation","الفلاتر والتسميد"))
        f1,f2 = st.columns(2)
        with f1: filt = st.selectbox(T("Filter","الفلتر"), FILTERS, format_func=lambda k: FILTER_AR[k])
        with f2: fert = st.selectbox(T("Fertigation","التسميد"), FERT_SYS, format_func=lambda k: FERT_AR[k])

        # --- Hydraulics ---
        st.markdown("---")
        st.subheader("📏 " + T("Hydraulics","الهيدروليكا"))
        h1,h2,h3 = st.columns(3)
        with h1:
            d_main = st.selectbox(T("Main Ø (mm)","الرئيسي"), [50,63,75,90,110,125,160,200], index=3)
            L_main = st.number_input(T("Main length (m)","طول الرئيسي"), 1.0, 5000.0, 200.0)
        with h2:
            d_sub = st.selectbox(T("Submain Ø (mm)","الفرعي"), [32,40,50,63,75,90], index=2)
            L_sub = st.number_input(T("Submain length","طول الفرعي"), 1.0, 5000.0, 200.0)
        with h3:
            d_lat = st.selectbox(T("Lateral Ø (mm)","الخرطوم"), [12,16,20,25], index=1)
            L_lat = st.number_input(T("Lateral length","طول الخرطوم"), 1.0, 500.0, 50.0)
        h4,h5,h6 = st.columns(3)
        with h4: nz = st.number_input(T("Zones","الزونات"), 1, 50, 1)
        with h5: elev = st.number_input(T("Elev. diff (m)","فرق المنسوب"), 0.0, 200.0, 0.0)
        with h6: succ = st.number_input(T("Suction lift","الشفط"), 0.0, 15.0, 2.0)
        safe = st.number_input(T("Safety margin (m)","هامش أمان"), 0.0, 30.0, 5.0)

        P = dict(project_name=proj, project_type=project_type, crop=crop,
                 area_value=area, area_unit=area_unit, currency=currency,
                 eto=eto, wind=wind, slope=slope, water_source=wsrc, power_source=psrc,
                 lat=lat, lon=lon, soil=soil, landscape_media=lm, nursery_media=nm,
                 ec=ec, ph=ph, sar=sar, dripper_flow=dflow, pc_dripper=pc,
                 dripper_spacing=dsp, lateral_spacing=lsp, tree_spacing=tsp, row_spacing=rsp,
                 filter_type=filt, fert_sys=fert, d_main=d_main, d_sub=d_sub, d_lat=d_lat,
                 L_main=L_main, L_sub=L_sub, L_lat=L_lat, n_zones=nz,
                 elevation=elev, suction_lift=succ, safety=safe, vat=vat)
        st.session_state["P"] = P
        st.session_state["R"] = run_design(P)
        st.success("✅ " + T("Inputs saved","تم حفظ المدخلات"))

    P = st.session_state.get("P"); R = st.session_state.get("R")
    if not P or not R:
        st.info(T("Fill Inputs first","املأ المدخلات أولاً"))
        return

    # ============ Tab 1: Design ============
    with tabs[1]:
        st.subheader(T("Design Results","نتائج التصميم"))
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("ETc (mm/d)", round(R["etc"],2))
        c2.metric("RAW (mm)", round(R["raw_mm"],1))
        c3.metric(T("Interval (d)","الدورة"), R["interval"])
        c4.metric("TDH (m)", round(R["tdh"],1))
        c1,c2,c3,c4 = st.columns(4)
        c1.metric(T("Depth/event","عمق الريّة"), round(R["event_depth_mm"],1))
        c2.metric(T("Vol/event (m³)","حجم الريّة"), round(R["event_volume_m3"],1))
        c3.metric(T("Annual (m³)","سنوي"), round(R["annual_m3"],0))
        c4.metric(T("Zone flow","تصرف الزون"), round(R["zone_q_m3h"],1))
        if R["per_plant"]:
            st.success(f"🌱 {T('Per plant','لكل نبات')}: {R['per_plant']['L/day']} L/day | {R['per_plant']['L/event']} L/event")

        st.markdown("### " + T("Hydraulics","الهيدروليكا"))
        st.table(pd.DataFrame([
            {"Pipe":T("Main","رئيسي"),"D (mm)":R["D_main"],"L (m)":R["L_main"],"V (m/s)":round(R["v_main"],2),"Hf (m)":round(R["hf_main"],2)},
            {"Pipe":T("Submain","فرعي"),"D (mm)":R["D_sub"],"L (m)":R["L_sub"],"V (m/s)":round(R["v_sub"],2),"Hf (m)":round(R["hf_sub"],2)},
            {"Pipe":T("Lateral","خرطوم"),"D (mm)":R["D_lat"],"L (m)":R["L_lat"],"V (m/s)":round(R["v_lat"],2),"Hf (m)":round(R["hf_lat"],2)},
        ]))

        if R["v_main"] < V_MIN_MAIN: st.warning(T("سرعة منخفضة — خطر ترسيب","Low velocity — sediment"))
        if R["v_main"] > V_MAX_MAIN: st.warning(T("سرعة مرتفعة — خطر تآكل","High velocity — erosion"))
        if R["tdh"] > TDH_WARN:      st.error(T("TDH > 120 م — زونات/booster","TDH > 120 — zoning/booster"))

        st.markdown("### " + T("Recommendations","التوصيات"))
        for ar,en,lvl in R["recommendations"]:
            msg = T(en,ar); (st.warning if lvl=="warn" else st.info)(msg)

    # ============ Tab 2: Agronomic ============
    with tabs[2]:
        st.subheader("🌾 " + T("Agronomic Report","التقرير الزراعي"))
        st.text(agronomic_report_text(P, R))
        st.download_button("⬇️ " + T("Download","تحميل"),
                           agronomic_report_text(P, R),
                           file_name=f"agronomic_{P['project_name']}.txt")

    # ============ Tab 3: Water ============
    with tabs[3]:
        st.subheader("💧 " + T("Water Quality","جودة المياه"))
        st.table(pd.DataFrame([
            {"Parameter":"EC","Value":P["ec"],"Unit":"dS/m"},
            {"Parameter":"pH","Value":P["ph"],"Unit":"-"},
            {"Parameter":"SAR","Value":P["sar"],"Unit":"-"},
        ]))
        warns = water_quality_warnings(P["ec"],P["ph"],P["sar"])
        if not warns: st.success(T("مياه آمنة","Safe water"))
        for ar,en,lvl in warns:
            msg = T(en,ar); (st.warning if lvl=="warn" else st.info)(msg)

    # ============ Tab 4: BOQ ============
    with tabs[4]:
        st.subheader("💰 " + T("Bill of Quantities","جدول الكميات"))
        rows, subtotal, vat_amt, total = compute_boq(P, R, vat=P["vat"])
        df = pd.DataFrame(rows, columns=[T("Item","البند"),T("Spec","المواصفات"),
                                          f"{T('Cost','التكلفة')} ({CURRENCIES[P['currency']]['ar']})"])
        st.dataframe(df, use_container_width=True)
        st.metric(T("Subtotal","قبل الضريبة"), fmt_money(subtotal, P["currency"]))
        st.metric(f"VAT {P['vat']:.0f}%", fmt_money(vat_amt, P["currency"]))
        st.metric(T("TOTAL","الإجمالي"), fmt_money(total, P["currency"]))
        st.download_button("⬇️ CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"boq_{P['project_name']}.csv")

    # ============ Tab 5: Plot ============
    with tabs[5]:
        st.subheader("🗺️ " + T("Plot","المخطط"))
        if MPL_OK:
            fig, info = build_plot(P, R)
            st.pyplot(fig)
            if info["truncated"]: st.warning(T(f"أول {MAX_PLOT_LINES} خط","First {MAX_PLOT_LINES} lines"))
            buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150); buf.seek(0)
            st.download_button("⬇️ PNG", buf,
                               file_name=f"plot_{P['project_name']}.png", mime="image/png")
        else:
            st.error("matplotlib not installed")

    # ============ Tab 6: DXF ============
    with tabs[6]:
        st.subheader("📐 DXF")
        if not EZDXF_OK: st.error("ezdxf not installed")
        else:
            _,_,_,total = compute_boq(P, R, vat=P["vat"])
            dxf_buf = build_dxf(P, R, P["vat"], total, P["currency"])
            if dxf_buf:
                st.download_button("⬇️ DXF", dxf_buf,
                    file_name=f"design_{P['project_name']}.dxf",
                    mime="application/dxf")
                st.success("✅ " + T("جاهز","Ready"))

if __name__ == "__main__":
    main()
