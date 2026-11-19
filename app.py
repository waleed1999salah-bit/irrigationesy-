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

st.set_page_config(page_title="Smart Irrigation AI V15.1", layout="wide")

if "project" not in st.session_state: st.session_state.project = None
if "zones" not in st.session_state: st.session_state.zones = []
if "results" not in st.session_state: st.session_state.results = None

# ==========================================
# 1. DATABASES (استعادة كاملة + الجديد)
# ==========================================
FEDDAN_M2 = 4200.0
AREA_UNITS = {"Feddan": 4200.0, "Hectare": 10000.0, "Acre": 4047.0, "Dunam": 1000.0, "m²": 1.0}
COUNTRY_INDEX = {"EG":1.0, "SA":1.35, "AE":1.4, "GR":1.2, "US":1.8, "EU":1.5, "INTL":1.0}

OPEN_FIELD_SOILS = {
    "Sandy (رملية)": {"taw": 50, "p_allow": 0.30},
    "Loamy Sand (رملية طميية)": {"taw": 80, "p_allow": 0.40},
    "Sandy Loam (طميية رملية)": {"taw": 100, "p_allow": 0.50},
    "Loam (طمية)": {"taw": 120, "p_allow": 0.50},
    "Clay Loam (طميية طينية)": {"taw": 130, "p_allow": 0.45},
    "Clay (طينية)": {"taw": 140, "p_allow": 0.40}
}
LANDSCAPE_MEDIA = {"Prepared Soil": {"taw": 120, "p_allow": 0.50}, "Imported Topsoil": {"taw": 110, "p_allow": 0.50}, "Peat Mix": {"taw": 150, "p_allow": 0.50}}
GREENHOUSE_MEDIA = {"Peat+Perlite": {"taw": 180, "p_allow": 0.40}, "Coco Peat": {"taw": 170, "p_allow": 0.40}}
NURSERY_MEDIA = {"Peat Moss": {"taw": 160, "p_allow": 0.45}, "Coco Peat": {"taw": 150, "p_allow": 0.45}}

CROPS = {
    # Field Crops
    "Wheat":{"kc_ini":0.35,"kc_mid":1.15,"kc_late":0.45,"cat":"field","ar":"قمح","ec_100":6.0,"ec_90":7.4,"root":1.2}, "Maize":{"kc_ini":0.30,"kc_mid":1.20,"kc_late":0.50,"cat":"field","ar":"ذرة","ec_100":1.7,"ec_90":2.5,"root":0.8},
    "Rice":{"kc_ini":1.05,"kc_mid":1.20,"kc_late":0.90,"cat":"field","ar":"أرز","ec_100":3.0,"ec_90":3.8,"root":0.6}, "Barley":{"kc_ini":0.35,"kc_mid":1.15,"kc_late":0.45,"cat":"field","ar":"شعير","ec_100":8.0,"ec_90":10.0,"root":1.2},
    "Alfalfa":{"kc_ini":0.40,"kc_mid":1.15,"kc_late":1.10,"cat":"field","ar":"برسيم","ec_100":1.5,"ec_90":3.2,"root":1.2}, "Cotton":{"kc_ini":0.35,"kc_mid":1.15,"kc_late":0.70,"cat":"field","ar":"قطن","ec_100":7.7,"ec_90":9.6,"root":1.0},
    "Sunflower":{"kc_ini":0.35,"kc_mid":1.00,"kc_late":0.35,"cat":"field","ar":"عباد الشمس","ec_100":4.8,"ec_90":6.0,"root":1.0}, "Soybean":{"kc_ini":0.40,"kc_mid":1.15,"kc_late":0.50,"cat":"field","ar":"فول صويا","ec_100":5.0,"ec_90":6.0,"root":0.8},
    "Sugar Beet":{"kc_ini":0.35,"kc_mid":1.20,"kc_late":0.70,"cat":"field","ar":"بنجر سكر","ec_100":7.0,"ec_90":9.0,"root":1.0}, "Sugarcane":{"kc_ini":0.40,"kc_mid":1.25,"kc_late":0.75,"cat":"field","ar":"قصب سكر","ec_100":1.7,"ec_90":3.4,"root":1.5},
    # Vegetables
    "Tomato":{"kc_ini":0.45,"kc_mid":1.15,"kc_late":0.70,"cat":"veg","ar":"طماطم","ec_100":2.5,"ec_90":3.5,"root":0.8}, "Potato":{"kc_ini":0.45,"kc_mid":1.15,"kc_late":0.75,"cat":"veg","ar":"بطاطس","ec_100":1.7,"ec_90":2.5,"root":0.5},
    "Cucumber":{"kc_ini":0.45,"kc_mid":1.00,"kc_late":0.80,"cat":"veg","ar":"خيار","ec_100":2.5,"ec_90":3.3,"root":0.7}, "Pepper":{"kc_ini":0.35,"kc_mid":1.05,"kc_late":0.90,"cat":"veg","ar":"فلفل","ec_100":1.5,"ec_90":2.2,"root":0.6},
    "Eggplant":{"kc_ini":0.60,"kc_mid":1.05,"kc_late":0.90,"cat":"veg","ar":"باذنجان","ec_100":1.1,"ec_90":1.8,"root":0.7}, "Onion":{"kc_ini":0.70,"kc_mid":1.05,"kc_late":0.75,"cat":"veg","ar":"بصل","ec_100":1.2,"ec_90":1.8,"root":0.4},
    "Garlic":{"kc_ini":0.70,"kc_mid":1.00,"kc_late":0.70,"cat":"veg","ar":"ثوم","ec_100":1.5,"ec_90":2.5,"root":0.4}, "Carrot":{"kc_ini":0.70,"kc_mid":1.05,"kc_late":0.95,"cat":"veg","ar":"جزر","ec_100":1.0,"ec_90":1.7,"root":0.5},
    "Lettuce":{"kc_ini":0.70,"kc_mid":1.00,"kc_late":0.95,"cat":"veg","ar":"خس","ec_100":1.3,"ec_90":2.1,"root":0.3}, "Cabbage":{"kc_ini":0.70,"kc_mid":1.05,"kc_late":0.95,"cat":"veg","ar":"كرنب","ec_100":1.8,"ec_90":2.8,"root":0.5},
    "Watermelon":{"kc_ini":0.45,"kc_mid":1.00,"kc_late":0.75,"cat":"veg","ar":"بطيخ","ec_100":1.0,"ec_90":1.6,"root":0.8}, "Melon":{"kc_ini":0.50,"kc_mid":1.05,"kc_late":0.75,"cat":"veg","ar":"شمام","ec_100":1.0,"ec_90":1.5,"root":0.9},
    "Strawberry":{"kc_ini":0.40,"kc_mid":1.00,"kc_late":0.75,"cat":"veg","ar":"فراولة","ec_100":1.0,"ec_90":1.3,"root":0.3}, "Zucchini":{"kc_ini":0.50,"kc_mid":1.00,"kc_late":0.80,"cat":"veg","ar":"كوسة","ec_100":4.7,"ec_90":5.8,"root":0.6},
    "Bean":{"kc_ini":0.40,"kc_mid":1.15,"kc_late":0.35,"cat":"veg","ar":"فاصوليا","ec_100":1.0,"ec_90":1.5,"root":0.6},
    # Orchards
    "Olive":{"kc_ini":0.65,"kc_mid":0.70,"kc_late":0.65,"cat":"orchard","ar":"زيتون","ec_100":2.7,"ec_90":3.8,"root":1.2}, "Citrus":{"kc_ini":0.70,"kc_mid":0.65,"kc_late":0.70,"cat":"orchard","ar":"موالح","ec_100":1.7,"ec_90":2.3,"root":1.0},
    "Orange":{"kc_ini":0.70,"kc_mid":0.65,"kc_late":0.70,"cat":"orchard","ar":"برتقال","ec_100":1.7,"ec_90":2.3,"root":1.0}, "Lemon":{"kc_ini":0.70,"kc_mid":0.65,"kc_late":0.70,"cat":"orchard","ar":"ليمون","ec_100":1.7,"ec_90":2.3,"root":1.0},
    "Mango":{"kc_ini":0.75,"kc_mid":0.85,"kc_late":0.75,"cat":"orchard","ar":"مانجو","ec_100":1.5,"ec_90":2.2,"root":1.0}, "Date Palm":{"kc_ini":0.90,"kc_mid":0.95,"kc_late":0.95,"cat":"orchard","ar":"نخيل","ec_100":4.0,"ec_90":6.8,"root":1.2},
    "Grape":{"kc_ini":0.30,"kc_mid":0.80,"kc_late":0.60,"cat":"orchard","ar":"عنب","ec_100":1.5,"ec_90":2.5,"root":1.0}, "Apple":{"kc_ini":0.45,"kc_mid":1.05,"kc_late":0.75,"cat":"orchard","ar":"تفاح","ec_100":1.0,"ec_90":1.8,"root":1.0},
    "Pear":{"kc_ini":0.45,"kc_mid":1.05,"kc_late":0.75,"cat":"orchard","ar":"كمثرى","ec_100":1.0,"ec_90":1.8,"root":1.0}, "Peach":{"kc_ini":0.45,"kc_mid":1.05,"kc_late":0.75,"cat":"orchard","ar":"خوخ","ec_100":1.7,"ec_90":2.4,"root":1.0},
    "Fig":{"kc_ini":0.50,"kc_mid":0.85,"kc_late":0.75,"cat":"orchard","ar":"تين","ec_100":2.0,"ec_90":3.0,"root":1.0}, "Pomegranate":{"kc_ini":0.50,"kc_mid":0.85,"kc_late":0.70,"cat":"orchard","ar":"رمان","ec_100":2.7,"ec_90":4.0,"root":1.0},
    "Banana":{"kc_ini":0.50,"kc_mid":1.10,"kc_late":1.00,"cat":"orchard","ar":"موز","ec_100":1.0,"ec_90":1.5,"root":0.7}, "Avocado":{"kc_ini":0.60,"kc_mid":0.90,"kc_late":0.85,"cat":"orchard","ar":"أفوكادو","ec_100":1.2,"ec_90":1.8,"root":0.8},
    # Turf
    "Turf Bermuda":{"kc_ini":0.80,"kc_mid":0.85,"kc_late":0.80,"cat":"turf","ar":"نجيل برمودا","ec_100":3.0,"ec_90":5.0,"root":0.3}, "Turf Fescue":{"kc_ini":0.90,"kc_mid":0.90,"kc_late":0.85,"cat":"turf","ar":"نجيل فيسكيوب","ec_100":3.0,"ec_90":5.0,"root":0.3},
    "Turf Ryegrass":{"kc_ini":0.85,"kc_mid":0.85,"kc_late":0.80,"cat":"turf","ar":"نجيل راي","ec_100":3.0,"ec_90":5.0,"root":0.3}, "Turf Zoysia":{"kc_ini":0.75,"kc_mid":0.75,"kc_late":0.75,"cat":"turf","ar":"نجيل زويسيا","ec_100":3.0,"ec_90":5.0,"root":0.3},
    # Shrubs
    "Bougainvillea":{"kc_ini":0.30,"kc_mid":0.55,"kc_late":0.50,"cat":"shrub","ar":"جهنمية","ec_100":2.0,"ec_90":3.0,"root":0.5}, "Hibiscus":{"kc_ini":0.50,"kc_mid":0.90,"kc_late":0.80,"cat":"shrub","ar":"خطمي","ec_100":1.5,"ec_90":2.5,"root":0.5},
    "Lantana":{"kc_ini":0.30,"kc_mid":0.55,"kc_late":0.50,"cat":"shrub","ar":"لانتانا","ec_100":2.0,"ec_90":3.0,"root":0.5}, "Duranta":{"kc_ini":0.40,"kc_mid":0.75,"kc_late":0.65,"cat":"shrub","ar":"دورانتا","ec_100":2.0,"ec_90":3.0,"root":0.6},
    "Jasmine":{"kc_ini":0.40,"kc_mid":0.75,"kc_late":0.65,"cat":"shrub","ar":"ياسمين","ec_100":1.5,"ec_90":2.5,"root":0.6}, "Oleander":{"kc_ini":0.30,"kc_mid":0.55,"kc_late":0.50,"cat":"shrub","ar":"دفلة","ec_100":2.5,"ec_90":4.0,"root":0.7},
    "Pittosporum":{"kc_ini":0.40,"kc_mid":0.70,"kc_late":0.60,"cat":"shrub","ar":"بيتوسبورم","ec_100":2.0,"ec_90":3.0,"root":0.5}, "Vinca":{"kc_ini":0.50,"kc_mid":0.75,"kc_late":0.70,"cat":"shrub","ar":"ونكا","ec_100":2.0,"ec_90":3.0,"root":0.4},
    # Trees
    "Ficus":{"kc_ini":0.50,"kc_mid":0.70,"kc_late":0.65,"cat":"tree","ar":"فيكس","ec_100":2.0,"ec_90":3.0,"root":1.0}, "Conocarpus":{"kc_ini":0.40,"kc_mid":0.55,"kc_late":0.50,"cat":"tree","ar":"كونوكاربس","ec_100":3.0,"ec_90":5.0,"root":1.2},
    "Eucalyptus":{"kc_ini":0.40,"kc_mid":0.65,"kc_late":0.60,"cat":"tree","ar":"كافتوس","ec_100":2.5,"ec_90":4.0,"root":1.5}, "Delonix":{"kc_ini":0.40,"kc_mid":0.60,"kc_late":0.55,"cat":"tree","ar":"بوانسيانا","ec_100":2.0,"ec_90":3.0,"root":1.0},
    "Cassia":{"kc_ini":0.40,"kc_mid":0.65,"kc_late":0.60,"cat":"tree","ar":"كاسيا","ec_100":2.0,"ec_90":3.0,"root":1.0}, "Washingtonia":{"kc_ini":0.60,"kc_mid":0.75,"kc_late":0.70,"cat":"tree","ar":"واشنطونيا","ec_100":3.0,"ec_90":5.0,"root":1.2},
    "Phoenix":{"kc_ini":0.50,"kc_mid":0.70,"kc_late":0.65,"cat":"tree","ar":"فينكس","ec_100":3.0,"ec_90":5.0,"root":1.2}, "Royal Palm":{"kc_ini":0.60,"kc_mid":0.80,"kc_late":0.75,"cat":"tree","ar":"رويال","ec_100":2.0,"ec_90":3.0,"root":1.2},
    # Flowers
    "Rose":{"kc_ini":0.60,"kc_mid":0.85,"kc_late":0.75,"cat":"flower","ar":"ورد","ec_100":1.5,"ec_90":2.5,"root":0.5}, "Petunia":{"kc_ini":0.60,"kc_mid":1.00,"kc_late":0.90,"cat":"flower","ar":"بيتونيا","ec_100":1.0,"ec_90":2.0,"root":0.3},
    "Marigold":{"kc_ini":0.60,"kc_mid":0.95,"kc_late":0.85,"cat":"flower","ar":"قطيفة","ec_100":1.5,"ec_90":2.5,"root":0.3}, "Geranium":{"kc_ini":0.60,"kc_mid":0.90,"kc_late":0.80,"cat":"flower","ar":"جرانيوم","ec_100":1.5,"ec_90":2.5,"root":0.4},
    "Chrysanthemum":{"kc_ini":0.60,"kc_mid":1.00,"kc_late":0.90,"cat":"flower","ar":"أقحوان","ec_100":1.5,"ec_90":2.5,"root":0.3}, "Carnation":{"kc_ini":0.60,"kc_mid":0.95,"kc_late":0.85,"cat":"flower","ar":"قرنفل","ec_100":2.0,"ec_90":3.0,"root":0.3},
    "Gerbera":{"kc_ini":0.60,"kc_mid":1.05,"kc_late":0.95,"cat":"flower","ar":"جربيرا","ec_100":1.5,"ec_90":2.5,"root":0.3}, "Gladiolus":{"kc_ini":0.60,"kc_mid":1.00,"kc_late":0.90,"cat":"flower","ar":"جلاديولس","ec_100":1.5,"ec_90":2.5,"root":0.3},
    "Dahlia":{"kc_ini":0.60,"kc_mid":1.00,"kc_late":0.90,"cat":"flower","ar":"داليا","ec_100":1.5,"ec_90":2.5,"root":0.4}, "Zinnia":{"kc_ini":0.60,"kc_mid":0.95,"kc_late":0.85,"cat":"flower","ar":"زينيا","ec_100":1.5,"ec_90":2.5,"root":0.3},
    "Gazania":{"kc_ini":0.30,"kc_mid":0.55,"kc_late":0.50,"cat":"flower","ar":"جازانيا","ec_100":2.0,"ec_90":3.0,"root":0.3}, "Lavender":{"kc_ini":0.40,"kc_mid":0.65,"kc_late":0.60,"cat":"flower","ar":"لافندر","ec_100":2.0,"ec_90":3.0,"root":0.4},
    "Lily":{"kc_ini":0.60,"kc_mid":1.00,"kc_late":0.90,"cat":"flower","ar":"زنبق","ec_100":1.5,"ec_90":2.5,"root":0.3}, "Aster":{"kc_ini":0.60,"kc_mid":0.95,"kc_late":0.85,"cat":"flower","ar":"أستر","ec_100":1.5,"ec_90":2.5,"root":0.3},
    # Foliage
    "Ficus Benjamina":{"kc_ini":0.50,"kc_mid":0.75,"kc_late":0.65,"cat":"foliage","ar":"بنجامينا","ec_100":2.0,"ec_90":3.0,"root":0.6}, "Dracaena":{"kc_ini":0.45,"kc_mid":0.65,"kc_late":0.60,"cat":"foliage","ar":"دراسينا","ec_100":2.0,"ec_90":3.0,"root":0.5},
    "Schefflera":{"kc_ini":0.50,"kc_mid":0.75,"kc_late":0.65,"cat":"foliage","ar":"شيفليرا","ec_100":2.0,"ec_90":3.0,"root":0.5}, "Aglaonema":{"kc_ini":0.60,"kc_mid":0.80,"kc_late":0.75,"cat":"foliage","ar":"أجلونيما","ec_100":1.5,"ec_90":2.5,"root":0.3},
    "Croton":{"kc_ini":0.60,"kc_mid":0.85,"kc_late":0.75,"cat":"foliage","ar":"كروتون","ec_100":1.5,"ec_90":2.5,"root":0.4},
    # Groundcovers
    "Wedelia":{"kc_ini":0.40,"kc_mid":0.65,"kc_late":0.60,"cat":"groundcover","ar":"ويدليا","ec_100":2.0,"ec_90":3.0,"root":0.2}, "Asparagus Fern":{"kc_ini":0.50,"kc_mid":0.75,"kc_late":0.65,"cat":"groundcover","ar":"اسباراجوس","ec_100":2.0,"ec_90":3.0,"root":0.3},
    "Liriope":{"kc_ini":0.45,"kc_mid":0.70,"kc_late":0.60,"cat":"groundcover","ar":"ليريوبي","ec_100":2.0,"ec_90":3.0,"root":0.2}, "Aptenia":{"kc_ini":0.30,"kc_mid":0.50,"kc_late":0.45,"cat":"groundcover","ar":"أبتينيا","ec_100":2.5,"ec_90":4.0,"root":0.2},
    "Portulaca":{"kc_ini":0.30,"kc_mid":0.50,"kc_late":0.45,"cat":"groundcover","ar":"بورتولاكا","ec_100":2.5,"ec_90":4.0,"root":0.2},
    # Climbers
    "Ivy":{"kc_ini":0.45,"kc_mid":0.70,"kc_late":0.60,"cat":"climber","ar":"لبلاب","ec_100":2.0,"ec_90":3.0,"root":0.6}, "Wisteria":{"kc_ini":0.45,"kc_mid":0.70,"kc_late":0.60,"cat":"climber","ar":"ويستيريا","ec_100":2.0,"ec_90":3.0,"root":0.8},
    "Passion Flower":{"kc_ini":0.50,"kc_mid":0.75,"kc_late":0.65,"cat":"climber","ar":"زهرة الآلام","ec_100":1.5,"ec_90":2.5,"root":0.7},
    # Succulents
    "Aloe Vera":{"kc_ini":0.25,"kc_mid":0.35,"kc_late":0.30,"cat":"succulent","ar":"صبار","ec_100":3.0,"ec_90":5.0,"root":0.2}, "Agave":{"kc_ini":0.20,"kc_mid":0.30,"kc_late":0.25,"cat":"succulent","ar":"أجاف","ec_100":3.0,"ec_90":5.0,"root":0.3},
    "Sedum":{"kc_ini":0.30,"kc_mid":0.40,"kc_late":0.35,"cat":"succulent","ar":"سيدم","ec_100":2.5,"ec_90":4.0,"root":0.2},
    # Potted
    "Potted Flowering":{"kc_ini":0.80,"kc_mid":1.10,"kc_late":0.90,"cat":"pot","ar":"أصص مزهرة","ec_100":1.0,"ec_90":2.0,"root":0.25}, "Potted Foliage":{"kc_ini":0.70,"kc_mid":1.00,"kc_late":0.85,"cat":"pot","ar":"أصص ورقية","ec_100":1.0,"ec_90":2.0,"root":0.25},
    "Potted Herb":{"kc_ini":0.70,"kc_mid":1.00,"kc_late":0.85,"cat":"pot","ar":"أصص أعشاب","ec_100":1.0,"ec_90":2.0,"root":0.20}
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

TREE_CROPS = {"Olive","Citrus","Orange","Lemon","Mango","Date Palm","Grape","Apple","Pear","Peach","Fig","Pomegranate","Avocado"}
CANOPY = {"Olive":0.70, "Date Palm":0.80, "Mango":0.90, "Citrus":0.85, "Grape":0.75, "Apple":0.85, "Pomegranate":0.80, "Avocado":0.90}

IRR_SYSTEMS = {"drip":{"ar":"تنقيط","eff":0.90,"p":15},"micro":{"ar":"ميكرو","eff":0.85,"p":20},"sprinkler":{"ar":"رشاش","eff":0.75,"p":25}}
REGULATIONS = {
    "EG":{"name":"مصر","max_h":10,"banned":["surface"]}, "SA":{"name":"السعودية","max_h":16,"banned":["surface"]},
    "AE":{"name":"الإمارات","max_h":14,"banned":["surface"]}, "GR":{"name":"اليونان","max_h":14,"banned":[]},
    "INTL":{"name":"دولي","max_h":24,"banned":[]}
}

FILTERS = {"Screen Filter":"فلتر شبكي","Disc Filter":"فلتر ديسكات","Media Filter":"فلتر رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,"Media Filter":25000,"Hydrocyclone":20000}

PUMPS = [
    {"name":"Grundfos CR 5-10","Q":5,"H":90,"kw":2.2,"eff":65,"NPSHr":2.0,"BEP_Q":5,"BEP_H":85,"curve":[(0,95),(2.5,92),(5,85),(7.5,75),(10,60),(12.5,40)], "price_egp": 25000},
    {"name":"Grundfos CR 10-10","Q":10,"H":95,"kw":4.0,"eff":70,"NPSHr":2.5,"BEP_Q":10,"BEP_H":82,"curve":[(0,100),(5,95),(10,82),(15,70),(20,55)], "price_egp": 38000},
    {"name":"Grundfos CR 15-8","Q":15,"H":80,"kw":5.5,"eff":72,"NPSHr":3.0,"BEP_Q":15,"BEP_H":70,"curve":[(0,85),(7.5,82),(15,70),(22.5,55),(30,35)], "price_egp": 52000},
    {"name":"Ebara EVMS 15","Q":15,"H":85,"kw":5.5,"eff":70,"NPSHr":3.0,"BEP_Q":15,"BEP_H":75,"curve":[(0,90),(7.5,88),(15,75),(22.5,60),(30,40)], "price_egp": 48000},
    {"name":"Lowara e-SV 22","Q":22,"H":75,"kw":7.5,"eff":75,"NPSHr":3.5,"BEP_Q":22,"BEP_H":65,"curve":[(0,80),(11,78),(22,65),(33,50),(44,30)], "price_egp": 68000},
    {"name":"Grundfos CR 20-5","Q":20,"H":60,"kw":5.5,"eff":73,"NPSHr":3.5,"BEP_Q":20,"BEP_H":50,"curve":[(0,65),(10,63),(20,50),(30,35),(40,20)], "price_egp": 55000},
    {"name":"Grundfos CR 32-4","Q":35,"H":60,"kw":11.0,"eff":75,"NPSHr":4.0,"BEP_Q":32,"BEP_H":50,"curve":[(0,65),(16,63),(32,50),(48,35),(64,20)], "price_egp": 95000},
    {"name":"Grundfos CR 64-2","Q":65,"H":40,"kw":15.0,"eff":78,"NPSHr":4.5,"BEP_Q":64,"BEP_H":30,"curve":[(0,45),(32,43),(64,30),(96,15)], "price_egp": 135000}
]

MAX_DRIP_HOURS = 8.0
MAX_SPRINKLER_HOURS = 6.0
MAX_ZONE_AREA_DRIP = 10.0
MAX_ZONE_AREA_SPRINKLER = 5.0
ATM_PRESSURE = 10.3
VAPOR_PRESSURE = 0.24

# ==========================================
# 2. ENGINES & CALCULATIONS
# ==========================================
def fetch_climate(lat, lon):
    if not REQUESTS_OK: return {"eto":5.5,"temp":25.0}
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=10, params={"latitude":lat,"longitude":lon,"start_date":"2023-07-01","end_date":"2023-08-31","daily":"et0_fao_evapotranspiration,temperature_2m_max"})
        d = r.json()["daily"]
        return {"eto":round(max([v for v in d["et0_fao_evapotranspiration"] if v is not None]+[5.5]),1), "temp":round(max([v for v in d["temperature_2m_max"] if v is not None]+[25]),1)}
    except: return {"eto":5.5,"temp":25.0}

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

def calc_salt_tolerance(ecw, crop_data):
    ece = ecw * 1.5
    if ece <= crop_data["ec_100"]: return 100.0, 0.0
    if ece >= crop_data["ec_90"]:
        slope = (90 - 50) / (crop_data["ec_90"] - crop_data["ec_100"])
        yield_pct = max(0, 90 - slope * (ece - crop_data["ec_90"]))
    else:
        slope = (100 - 90) / (crop_data["ec_100"] - crop_data["ec_90"])
        yield_pct = 100 - slope * (ece - crop_data["ec_100"])
    ece_target = crop_data["ec_90"]
    lr = max(0.0, ecw / (5 * ece_target - ecw))
    return round(yield_pct, 1), round(lr, 2)

def explain_etc(etc, kc, eto, stage):
    stage_ar = {"ini":"بداية","mid":"منتصف","late":"نهاية"}[stage]
    return f"ETc = Kc × ETo = {kc} × {eto} = **{etc:.2f} mm/day** (مرحلة {stage_ar})"

def explain_yield(yield_pct, ecw, ece, ec_100, ec_90):
    if yield_pct >= 95: return f"✅ ملوحة المياه ({ecw} dS/m) ضمن النطاق الآمن → إنتاجية **{yield_pct}%**"
    elif yield_pct >= 80: return f"⚠️ ملوحة المياه ({ecw} dS/m) تسبب خسارة بسيطة → إنتاجية **{yield_pct}%**"
    else: return f"🚨 ملوحة المياه ({ecw} dS/m) تسبب خسارة كبيرة → إنتاجية **{yield_pct}%**"

def explain_lr(lr, ecw, ece_target):
    if lr <= 0: return "✅ لا تحتاج غسيل أملاح"
    return f"💧 تحتاج غسيل أملاح بمعدل **{lr*100:.1f}%** مياه إضافية"

def design_zone(z, proj):
    c = CROPS[z["crop"]]
    cat = c["cat"]
    soil_info = OPEN_FIELD_SOILS.get(z.get("soil", "Loam (طمية)"), OPEN_FIELD_SOILS["Loam (طمية)"])
    if proj["project_type"] == "Landscape": soil_info = list(LANDSCAPE_MEDIA.values())[0]
    elif proj["project_type"] == "Greenhouse": soil_info = list(GREENHOUSE_MEDIA.values())[0]
    elif proj["project_type"] == "Nursery": soil_info = list(NURSERY_MEDIA.values())[0]
    
    taw = soil_info["taw"]
    p_allow = soil_info["p_allow"]
    root_depth = c["root"]
    stage = z.get("stage", "mid")
    kc = c[f"kc_{stage}"]
    etc = proj["eto"] * kc
    raw = p_allow * taw * root_depth
    max_i = 3 if cat in ("veg","flower","pot") else 7 if cat in ("orchard","tree") else 14 if cat=="succulent" else 5
    interval = max(1, min(int(round(raw/etc if etc>0 else max_i)), max_i))
    area = z["area_val"] * AREA_UNITS[z["area_unit"]]
    
    yield_pct, lr = calc_salt_tolerance(proj["ec"], c)
    eff = IRR_SYSTEMS[z["system"]]["eff"]
    vol = ((etc * interval) / (eff * (1 - lr))) * area / 1000
    
    if cat in TREE_CROPS:
        esp, lsp = z.get("esp",5.0), z.get("lsp",6.0)
        n_trees = int(area/(esp*lsp))
        emitters = n_trees * z.get("emitters_per_tree", 4)
        q_lph = emitters * z.get("q",8.0)
    elif cat == "turf":
        emitters = int(area/144); q_lph = emitters*1000.0
    elif cat in ("tree","shrub"):
        n = int(area/(3.0*4.0)); emitters = n*z.get("emitters_per_tree",4); q_lph = emitters*z.get("q",4.0)
    elif cat in ("flower","foliage","groundcover","climber","pot"):
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
    v_lat = (q_lat/3600) / (math.pi * (d_lat/2000)**2) if d_lat > 0 else 0
    v_sub = (q_m3h/3600) / (math.pi * (d_sub/2000)**2) if d_sub > 0 else 0
    
    return {**z, "kc": kc, "etc":etc, "interval":interval, "vol":vol,
            "q_m3h":q_m3h, "dur":dur, "d_lat":d_lat, "d_sub":d_sub, "hf_lat":hf_lat,
            "hf_sub":hf_sub, "tdh":tdh, "eu":eu, "emitters":emitters, "npsha":npsha,
            "yield_pct": yield_pct, "lr": lr, "root": root_depth, "raw": raw,
            "v_lat": v_lat, "v_sub": v_sub, "stage": stage}

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

def compare_pumps(peak_q, max_tdh, top_n=3):
    candidates = []
    for p in PUMPS:
        if p["Q"] >= peak_q and p["H"] >= max_tdh:
            score = pump_score(p, peak_q, max_tdh)
            head_at_q = curve_head_at_q(p["curve"], peak_q)
            candidates.append({"pump": p, "score": score, "head_at_q": head_at_q, "bep_q": p["BEP_Q"], "bep_h": p["BEP_H"], "kw": p["kw"], "eff": p["eff"], "npshr": p["NPSHr"], "price": p["price_egp"]})
    candidates.sort(key=lambda x: x["score"])
    return candidates[:top_n]

def smart_advisories(proj, zones, split_reasons, pump_info, alternatives):
    adv = []
    for z in zones:
        if z["yield_pct"] < 90:
            adv.append({"level": "error", "title": f"🧂 {z['zone_label']}: خسارة إنتاجية {100-z['yield_pct']:.0f}%", "cause": f"ECw = {proj['ec']} dS/m → ECe = {proj['ec']*1.5:.1f} → تجاوز حد 90% ({CROPS[z['crop']]['ec_90']})", "fix": f"1) اخلط مياه بئر مع نيل لخفض EC، 2) استخدم LR = {z['lr']*100:.1f}%، 3) فكّر في محصول أكثر تحملاً"})
        elif z["yield_pct"] < 100 and z["lr"] > 0:
            adv.append({"level": "warning", "title": f"💧 {z['zone_label']}: غسيل أملاح مطلوب", "cause": f"إنتاجية متوقعة {z['yield_pct']}% بسبب ملوحة {proj['ec']} dS/m", "fix": f"تمت إضافة {z['lr']*100:.1f}% مياه للتصميم. راجع برنامج الغسيل كل 3 ريات."})
    if pump_info["pump"]:
        p = pump_info["pump"]
        score = pump_score(p, pump_info["req_q"], pump_info["req_h"])
        if score > 15:
            best_alt = alternatives[0] if alternatives else None
            fix = f"الأفضل: {best_alt['pump']['name']} (Score={best_alt['score']:.1f})" if best_alt else "راجع المضخة"
            adv.append({"level": "warning", "title": f"⚙️ نقطة التشغيل بعيدة عن BEP", "cause": f"المضخة المختارة: {p['name']} (Score={score:.1f})", "fix": fix})
    npsha = npsh_available(proj.get("suction",2), pump_info["hf_sub"])
    npshr = pump_info["pump"]["NPSHr"]
    status = npsh_status(npsha, npshr)
    if status == "risk":
        adv.append({"level": "error", "title": f"🌊 Cavitation Risk!", "cause": f"NPSHa = {npsha}m < NPSHr = {npshr}m", "fix": "1) خفّض عمق الشفط، 2) قلل الفواقد في ماسورة الشفط، 3) استخدم مضخة بـ NPSHr أقل"})
    elif status == "tight":
        adv.append({"level": "warning", "title": f"🌊 NPSH هامش ضيق", "cause": f"NPSHa = {npsha}m ~ NPSHr = {npshr}m", "fix": "راقب التشغيل، أي انسداد في الفلتر يسبب Cavitation"})
    for z in zones:
        max_h = MAX_DRIP_HOURS if z["system"] in ("drip","micro") else MAX_SPRINKLER_HOURS
        if z["dur"] > max_h:
            adv.append({"level": "error", "title": f"⏰ {z['zone_label']}: زمن الري طويل", "cause": f"{z['dur']:.1f}h > حد {max_h}h", "fix": "1) قسّم الزونة، 2) استخدم منقطات أكبر، 3) استخدم رشاشات بدل التنقيط"})
        if z["eu"] < 80:
            adv.append({"level": "warning", "title": f"📊 {z['zone_label']}: EU منخفض", "cause": f"EU = {z['eu']}% (الحد المقبول 80%)", "fix": "1) استخدم PC drippers، 2) قسّر طول الخراطيم، 3) كبّر قطر الخرطوم"})
        if z["v_lat"] < 0.5:
            adv.append({"level": "info", "title": f"💨 {z['zone_label']}: سرعة خرطوم منخفضة", "cause": f"v = {z['v_lat']:.2f} m/s (خطر ترسيب)", "fix": "قلل قطر الخرطوم (مثلاً من 20mm إلى 16mm)"})
        if z["v_sub"] > 2.0:
            adv.append({"level": "warning", "title": f"💨 {z['zone_label']}: سرعة ماسورة عالية", "cause": f"v = {z['v_sub']:.2f} m/s (خطر تآكل)", "fix": "كبّر قطر الماسورة الفرعية"})
    if split_reasons:
        adv.insert(0, {"level": "info", "title": f"🔧 المشروع مقسّم إلى {len(zones)} زونة", "cause": split_reasons, "fix": "التقسيم تلقائي وفقاً للحدود الهندسية"})
    return adv

def compute_boq(proj, zones, autonomy_days=1.0):
    idx = COUNTRY_INDEX.get(proj["country"], 1.0)
    rows = []
    peak_q = max(z["q_m3h"] for z in zones) if zones else 0
    max_tdh = max(z["tdh"] for z in zones) if zones else 50
    max_hf_sub = max(z["hf_sub"] for z in zones) if zones else 0
    if proj.get("pump_choice") == "Auto":
        pump = select_pump_best(peak_q, max_tdh)
    else:
        pump = next((p for p in PUMPS if p["name"]==proj["pump_choice"]), PUMPS[0])
    pk, pk_kw, pk_eff, pk_price = pump["name"], pump["kw"], pump["eff"], pump["price_egp"]
    rows.append(("Pump & Motor", f"{pk} ({pk_kw} kW)", pk_price * idx))
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
# 3. EXPORTS
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
        features = [{"type": "Feature", "properties": {"name": proj["name"], "total_area": sum(z["area_val"] for z in zones), "n_zones": len(zones)}, "geometry": {"type":"Polygon","coordinates": coords}}]
        return json.dumps({"type":"FeatureCollection","features":features}, ensure_ascii=False, indent=2)
    except: return None

def build_shapefile_zip(proj, zones):
    if not GIS_OK: return None
    try:
        coords = get_polygon_coords(proj, zones)
        poly = Polygon(coords)
        gdf = gpd.GeoDataFrame({"name":[proj["name"]], "area_fed":[sum(z["area_val"] for z in zones)]}, geometry=[poly], crs="EPSG:4326")
        tmpdir = tempfile.mkdtemp()
        shp_path = os.path.join(tmpdir, "farm.shp")
        gdf.to_file(shp_path, driver="ESRI Shapefile")
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in os.listdir(tmpdir): zf.write(os.path.join(tmpdir, fn), fn)
        zip_buf.seek(0); return zip_buf
    except: return None

def build_pdf(proj, zones, boq, capex, opex, npv, irr, lcc, tank, pump_info, advisories, alternatives):
    if not PDF_OK: return None
    try:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        el = []
        
        el.append(Paragraph(f"<b>{proj['name']}</b>", styles['Title']))
        el.append(Spacer(1,12))
        el.append(Paragraph("Smart Irrigation AI — Engineering Design Report", styles['Heading2']))
        el.append(Paragraph(f"Type: {proj['project_type']} | Country: {REGULATIONS[proj['country']]['name']}", styles['Normal']))
        el.append(Paragraph(f"Date: {date.today().strftime('%Y-%m-%d')}", styles['Normal']))
        el.append(Spacer(1,30))
        
        el.append(Paragraph("<b>1. Executive Summary</b>", styles['Heading2']))
        el.append(Spacer(1,6))
        summary_lines = [
            f"• <b>المشروع:</b> {proj['project_type']} في {REGULATIONS[proj['country']]['name']}",
            f"• <b>المساحة:</b> {sum(z['area_val'] for z in zones):.2f} فدان على {len(zones)} زونة",
            f"• <b>المناخ:</b> ETo = {proj['eto']} mm/day | T = {proj['temp']}°C",
            f"• <b>المياه:</b> EC = {proj['ec']} dS/m | pH = {proj['ph']} | SAR = {proj['sar']}",
            f"• <b>المضخة المختارة:</b> {pump_info['pump']['name']} ({pump_info['pump']['kw']} kW)",
            f"• <b>التصرف الأقصى:</b> {pump_info['req_q']:.1f} m³/h",
            f"• <b>CAPEX:</b> {capex:,.0f} EGP",
            f"• <b>NPV:</b> {npv:,.0f} EGP | <b>IRR:</b> {irr}%",
        ]
        for line in summary_lines: el.append(Paragraph(line, styles['Normal']))
        el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>2. Pump Selection Analysis</b>", styles['Heading2']))
        el.append(Paragraph("تمت مقارنة أفضل 3 مضخات وفقاً لمعايير BEP:", styles['Normal']))
        el.append(Spacer(1,6))
        comp_data = [["#", "Pump", "kW", "Eff %", "BEP Q/H", "Score", "Price (EGP)"]]
        for i, alt in enumerate(alternatives, 1):
            comp_data.append([str(i), alt["pump"]["name"], f"{alt['kw']}", f"{alt['eff']}%", f"{alt['bep_q']}/{alt['bep_h']}", f"{alt['score']:.1f}", f"{alt['price']:,}"])
        comp_table = Table(comp_data, colWidths=[20, 100, 40, 40, 60, 40, 70])
        comp_table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.lightgrey), ('FONTSIZE',(0,0),(-1,-1),8)]))
        el.append(comp_table)
        el.append(Paragraph(f"<b>التوصية:</b> المضخة {alternatives[0]['pump']['name']} (Score={alternatives[0]['score']:.1f}) هي الأفضل.", styles['Normal']))
        el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>3. Zones & Irrigation Parameters</b>", styles['Heading2']))
        data = [["Zone","Crop","Area","ETc","Interval","Flow","Duration","Yield","LR"]]
        for z in zones: data.append([z["zone_label"], CROPS[z["crop"]]["ar"], f"{z['area_val']:.2f} fd", f"{z['etc']:.1f}", f"{z['interval']}d", f"{z['q_m3h']:.1f}", f"{z['dur']:.1f}h", f"{z['yield_pct']}%", f"{z['lr']*100:.1f}%"])
        t = Table(data, colWidths=[50, 40, 50, 40, 50, 45, 45, 40, 40])
        t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.lightgrey), ('FONTSIZE',(0,0),(-1,-1),8)]))
        el.append(t)
        el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>4. Engineering Recommendations</b>", styles['Heading2']))
        for adv in advisories[:10]:
            icon = {"error":"❌","warning":"⚠️","info":"ℹ️"}[adv["level"]]
            el.append(Paragraph(f"{icon} <b>{adv['title']}</b>", styles['Normal']))
            el.append(Paragraph(f"<i>السبب:</i> {adv['cause']}", styles['Normal']))
            el.append(Paragraph(f"<i>الحل:</i> {adv['fix']}", styles['Normal']))
            el.append(Spacer(1,4))
        el.append(Spacer(1,12))
        
        el.append(Paragraph("<b>5. Financial Summary</b>", styles['Heading2']))
        fdata = [["Item","Value"], ["CAPEX",f"{capex:,.0f} EGP"],["OPEX/Year",f"{opex:,.0f} EGP"], ["NPV",f"{npv:,.0f} EGP"],["IRR",f"{irr}%"], ["LCC",f"{lcc:,.0f} EGP"],["Tank",f"{tank:.1f} m³"]]
        ft = Table(fdata, colWidths=[200, 200])
        ft.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
        el.append(ft)
        
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
            ax.text(50, y+step/2, f"{z['zone_label']} | {CROPS[z['crop']]['ar']} | {z['area_val']:.2f}fd | Yield {z['yield_pct']}%", ha='center', va='center', fontsize=9, bbox=dict(fc='white', ec=color))
            y += step
        ax.set_xlim(0,100); ax.set_ylim(0,80); ax.axis("off")
        buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches=None)
        buf.seek(0); plt.close(fig); return buf
    except: return None

# ==========================================
# 4. UI
# ==========================================
def main():
    st.sidebar.title("💧 Smart Irrigation AI V15.1")
    design_mode = st.sidebar.radio("Design Mode", ["Client","Engineer"], format_func=lambda x: "👤 Client" if x=="Client" else "👨‍🔧 Engineer")
    et_method = st.sidebar.radio("ET Method", ["Standard","FAO56"], format_func=lambda x: "Standard" if x=="Standard" else "FAO-56")
    if PYFAO_OK: st.sidebar.success("✅ pyfao56 Active")
    if GIS_OK: st.sidebar.success("✅ GIS Ready")
    
    tabs = st.tabs(["1. Setup","2. Water Quality","3. Zones","4. Hydraulic Design","5. Design Review","6. BOQ & Finance","7. Reports","8. Exports"])
    
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
        
        st.session_state.project = {"name": pname, "project_type": project_type, "country": country, "eto": eto, "temp": temp, "lat": lat, "lon": lon, "ec": 2.0, "ph": 7.5, "sar": 5.0, "wsrc": "Nile", "filter": "Screen Filter", "et_method": et_method, "design_mode": design_mode, "safety": safety, "elev": elevation, "suction": suction, "pump_choice": pump_choice, "pump_kw": pump_kw, "pump_eff": pump_eff, "revenue": st.session_state.get("revenue", 200000.0)}
    
    proj = st.session_state.get("project")
    if not proj: st.stop()
    proj["et_method"] = et_method; proj["design_mode"] = design_mode; st.session_state.project = proj
    
    with tabs[1]:
        st.subheader("Water Quality & Source")
        wq1, wq2, wq3 = st.columns(3)
        with wq1: ec = st.number_input("ECw (dS/m)", 0.0, 20.0, 2.0)
        with wq2: ph = st.number_input("pH", 4.0, 10.0, 7.5)
        with wq3: sar = st.number_input("SAR", 0.0, 30.0, 5.0)
        wsrc = st.selectbox("Water Source", ["Nile","Well","Reclaimed"])
        auto_filter = "Media Filter" if wsrc=="Well" else "Disc Filter" if wsrc=="Reclaimed" else "Screen Filter"
        st.info(f"🤖 Auto Filter: **{auto_filter}**")
        proj["ec"], proj["ph"], proj["sar"] = ec, ph, sar
        proj["wsrc"] = wsrc; proj["filter"] = auto_filter; st.session_state.project = proj
    
    with tabs[2]:
        st.subheader("Zones Manager")
        if st.button("➕ Add Zone"):
            st.session_state.zones.append({"name": f"Z{len(st.session_state.zones)+1}", "crop": "Tomato", "stage": "mid", "area_val": 1.0, "area_unit": "Feddan", "system": "drip", "soil": "Loam (طمية)", "q": 4.0, "esp": 0.3, "lsp": 0.8, "emitters_per_tree": 4})
            st.rerun()
        
        for i, z in enumerate(st.session_state.zones):
            with st.expander(f"🌱 {z['name']}", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: z["name"] = st.text_input("Name", z["name"], key=f"n{i}")
                grp = CROP_GROUPS[proj["project_type"]]
                with c2: grp_sel = st.selectbox("Group", list(grp.keys()), key=f"g{i}")
                with c3:
                    old_crop = z["crop"]
                    z["crop"] = st.selectbox("Crop", grp[grp_sel], format_func=lambda x: CROPS[x]["ar"], key=f"c{i}")
                    if old_crop != z["crop"]:
                        cat = CROPS[z["crop"]]["cat"]
                        if cat in TREE_CROPS: z["esp"], z["lsp"], z["q"], z["emitters_per_tree"] = 5.0, 6.0, 8.0, 4; z["system"] = "drip"
                        elif cat in ("field", "turf"): z["esp"], z["lsp"], z["q"] = 12.0, 12.0, 1000.0; z["system"] = "sprinkler"
                        else: z["esp"], z["lsp"], z["q"] = 0.3, 0.8, 4.0; z["system"] = "drip"
                
                c1, c2, c3 = st.columns(3)
                with c1: z["area_val"] = st.number_input("Area", value=z["area_val"], key=f"a{i}")
                with c2: z["stage"] = st.selectbox("Growth Stage", ["ini", "mid", "late"], format_func=lambda x: {"ini":"Initial","mid":"Mid","late":"Late"}[x], key=f"st{i}")
                with c3: 
                    if proj["project_type"] == "Agricultural": z["soil"] = st.selectbox("Soil", list(OPEN_FIELD_SOILS.keys()), key=f"t{i}")
                    elif proj["project_type"] == "Landscape": z["soil"] = list(LANDSCAPE_MEDIA.keys())[0]
                    elif proj["project_type"] == "Greenhouse": z["soil"] = list(GREENHOUSE_MEDIA.keys())[0]
                    else: z["soil"] = list(NURSERY_MEDIA.keys())[0]
                
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
                        alternatives = compare_pumps(pump_info["req_q"], pump_info["req_h"], top_n=3)
                        annual_cf = proj["revenue"] - opex
                        npv = calc_npv(capex, annual_cf, 10, 0.10); irr = calc_irr(capex, annual_cf, 10); lcc = calc_lcc(capex, opex, 10, 0.10)
                        advisories = smart_advisories(proj, all_zones, " + ".join(split_reasons) if split_reasons else None, pump_info, alternatives)
                        proj["_pump_name"] = pump_info["pump"]["name"]; st.session_state.project = proj
                        st.session_state.results = {"zones": all_zones, "boq": boq, "capex": capex, "opex": opex, "tank": tank, "pump_info": pump_info, "alternatives": alternatives, "npv": npv, "irr": irr, "lcc": lcc, "advisories": advisories, "split_reasons": split_reasons}
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
            
            st.markdown("### ⚙️ Pump Alternatives (Best 3)")
            comp_data = []
            for i, alt in enumerate(res["alternatives"], 1):
                comp_data.append({"": "🥇" if i==1 else "🥈" if i==2 else "🥉", "Pump": alt["pump"]["name"], "kW": alt["kw"], "Eff%": alt["eff"], "BEP Q/H": f"{alt['bep_q']}/{alt['bep_h']}", "Score": round(alt["score"], 1), "Price (EGP)": f"{alt['price']:,}"})
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True)
            
            st.markdown("### 🌊 NPSH Analysis")
            nc1, nc2, nc3 = st.columns(3)
            nc1.metric("NPSHa", f"{npsha} m"); nc2.metric("NPSHr", f"{p['NPSHr']} m"); nc3.metric("Status", {"safe":"✅ Safe","tight":"⚠️ Tight","risk":"❌ Risk"}[status])
            
            st.markdown("### Zone-by-Zone Details")
            for z in res["zones"]:
                with st.expander(f"🌱 {z['zone_label']} — {CROPS[z['crop']]['ar']}"):
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    ec1.metric("ETc", f"{z['etc']:.1f} mm/d"); ec2.metric("Yield", f"{z['yield_pct']}%"); ec3.metric("LR", f"{z['lr']*100:.1f}%"); ec4.metric("EU", f"{z['eu']}%")
                    st.markdown(f"**🔍 التفسير الهندسي:**")
                    st.info(explain_etc(z['etc'], z['kc'], proj['eto'], z['stage']))
                    st.info(f"RAW = P_allow × TAW × Zr = {z['raw']:.0f} mm")
                    st.info(f"الدورة = RAW / ETc = {z['interval']} يوم")
                    st.info(explain_yield(z['yield_pct'], proj['ec'], proj['ec']*1.5, CROPS[z['crop']]['ec_100'], CROPS[z['crop']]['ec_90']))
                    st.info(explain_lr(z['lr'], proj['ec'], CROPS[z['crop']]['ec_90']))
    
    with tabs[4]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("🧠 Design Review — Executive Summary")
            st.markdown(f"""
            - **المشروع:** {proj['project_type']} في {REGULATIONS[proj['country']]['name']}
            - **المساحة:** {sum(z['area_val'] for z in res['zones']):.2f} فدان على {len(res['zones'])} زونة
            - **المناخ:** ETo = {proj['eto']} mm/day | T = {proj['temp']}°C
            - **المياه:** EC = {proj['ec']} dS/m | pH = {proj['ph']} | SAR = {proj['sar']}
            - **المضخة:** {res['pump_info']['pump']['name']} ({res['pump_info']['pump']['kw']} kW)
            - **التصرف الأقصى:** {res['pump_info']['req_q']:.1f} m³/h
            """)
            st.markdown("### 🎯 التوصيات الهندسية (Engineering Recommendations)")
            for adv in res["advisories"]:
                if adv["level"] == "error":
                    with st.container(): st.error(f"### {adv['title']}"); st.markdown(f"**🔍 السبب:** {adv['cause']}"); st.markdown(f"**🔧 الحل:** {adv['fix']}")
                elif adv["level"] == "warning":
                    with st.container(): st.warning(f"### {adv['title']}"); st.markdown(f"**🔍 السبب:** {adv['cause']}"); st.markdown(f"**🔧 الحل:** {adv['fix']}")
                else:
                    with st.container(): st.info(f"### {adv['title']}"); st.markdown(f"**🔍 السبب:** {adv['cause']}"); st.markdown(f"**🔧 الحل:** {adv['fix']}")
    
    with tabs[5]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("💰 BOQ & Finance")
            c1,c2,c3 = st.columns(3); c1.metric("CAPEX", f"{res['capex']:,.0f} EGP"); c2.metric("OPEX/Year", f"{res['opex']:,.0f} EGP"); c3.metric("Tank", f"{res['tank']:.1f} m³")
            c1,c2,c3 = st.columns(3); c1.metric("NPV", f"{res['npv']:,.0f} EGP"); c2.metric("IRR", f"{res['irr']}%"); c3.metric("LCC", f"{res['lcc']:,.0f} EGP")
            st.dataframe(pd.DataFrame(res["boq"], columns=["Item","Spec","Cost"]), use_container_width=True)
    
    with tabs[6]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("📄 Reports")
            pdf = build_pdf(proj, res["zones"], res["boq"], res["capex"], res["opex"], res["npv"], res["irr"], res["lcc"], res["tank"], res["pump_info"], res["advisories"], res["alternatives"])
            if pdf: st.download_button("⬇️ Download Engineering Report PDF", pdf, file_name=f"{proj['name']}_engineering_report.pdf", mime="application/pdf")
            else: st.warning("PDF generation failed")
    
    with tabs[7]:
        if not res: st.info("Calculate design first")
        else:
            st.subheader("📐 Exports (CAD + GIS)")
            c1, c2 = st.columns(2)
            with c1:
                dxf = build_dxf(proj, res["zones"])
                if dxf: st.download_button("⬇️ Download DXF", dxf, file_name="design.dxf")
            with c2:
                geojson_str = build_geojson(proj, res["zones"])
                if geojson_str: st.download_button("⬇️ Download GeoJSON", geojson_str, file_name=f"{proj['name']}.geojson", mime="application/geo+json")
                if GIS_OK:
                    shp_zip = build_shapefile_zip(proj, res["zones"])
                    if shp_zip: st.download_button("⬇️ Download Shapefile (ZIP)", shp_zip, file_name=f"{proj['name']}_shp.zip", mime="application/zip")
            plot = build_plot(res["zones"])
            if plot: st.image(plot, caption="Zone Layout", use_column_width=True)

if __name__ == "__main__":
    main()
