"""
SMART IRRIGATION AI — V10.1
============================
- V10: كل الـ 28 مهمة منفذة
- V10.1: Polygon Area Module (KML / GeoJSON / Coordinates)
Deps: streamlit, pandas, numpy, ezdxf, matplotlib
"""

import re, io, math, json
import numpy as np
import pandas as pd
import streamlit as st

try:
    import ezdxf
    EZDXF_OK = True
except Exception:
    EZDXF_OK = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.lines import Line2D
    MPL_OK = True
except Exception:
    MPL_OK = False

# ============================================================
# TRANSLATION (Task 1 — simple dict, no deep_translator)
# ============================================================
def T(en, ar):
    return en if st.session_state.get("lang", "ar") == "en" else ar

# ============================================================
# CONSTANTS
# ============================================================
FEDDAN_M2 = 4200.0
V_MIN_MAIN, V_MAX_MAIN = 0.6, 2.5
TDH_WARN = 120
DXF_EMITTER_LIMIT = 10000
MAX_PLOT_LINES = 3000

P_ALLOW = {"turf":0.50,"shrub":0.45,"tree":0.50,"veg":0.35,"orchard":0.55,"field":0.50}

SOILS = {
    "Sandy":       {"taw":80, "ar":"رملية"},
    "Loamy Sand":  {"taw":110,"ar":"رملية طميية"},
    "Sandy Loam":  {"taw":140,"ar":"طميية رملية"},
    "Loam":        {"taw":170,"ar":"طميية"},
    "Clay Loam":   {"taw":190,"ar":"طميية طينية"},
    "Clay":        {"taw":210,"ar":"طينية"},
}
LANDSCAPE_SOILS = {
    "Imported Landscape Soil": {"taw":150,"ar":"تربة لاندسكيب مستوردة"},
    "Artificial Turf Base":    {"taw":120,"ar":"قاعدة نجيل صناعي"},
}

CROPS = {
    "Tomato":    {"kc":1.05,"zr":0.6,"cat":"veg",    "ar":"طماطم"},
    "Potato":    {"kc":1.10,"zr":0.5,"cat":"veg",    "ar":"بطاطس"},
    "Pepper":    {"kc":1.00,"zr":0.5,"cat":"veg",    "ar":"فلفل"},
    "Cucumber":  {"kc":1.05,"zr":0.7,"cat":"veg",    "ar":"خيار"},
    "Olive":     {"kc":0.70,"zr":1.2,"cat":"orchard","ar":"زيتون"},
    "Citrus":    {"kc":0.85,"zr":1.0,"cat":"orchard","ar":"موالح"},
    "Mango":     {"kc":0.85,"zr":1.2,"cat":"orchard","ar":"مانجو"},
    "Date Palm": {"kc":0.95,"zr":1.5,"cat":"orchard","ar":"نخيل"},
    "Grape":     {"kc":0.75,"zr":1.0,"cat":"orchard","ar":"عنب"},
    "Wheat":     {"kc":1.10,"zr":1.0,"cat":"field",  "ar":"قمح"},
    "Maize":     {"kc":1.15,"zr":1.0,"cat":"field",  "ar":"ذرة"},
    "Alfalfa":   {"kc":1.05,"zr":1.5,"cat":"field",  "ar":"برسيم"},
    "Turf":      {"kc":0.80,"zr":0.3,"cat":"turf",   "ar":"نجيل"},
    "Shrubs":    {"kc":0.60,"zr":0.5,"cat":"shrub",  "ar":"شجيرات"},
}
TREE_CROPS = {"Olive","Date Palm","Mango","Citrus","Grape"}

DRIP_FLOWS = [1.6, 2.0, 4.0, 8.0, 16.0]
FILTERS = ["Screen Filter","Disc Filter","Media Filter","Hydrocyclone"]
FILTER_AR = {"Screen Filter":"فلتر شبكي","Disc Filter":"فلتر ديسكات",
             "Media Filter":"فلتر رملي","Hydrocyclone":"هيدروسيكلون"}
FILTER_PRICE = {"Screen Filter":8000,"Disc Filter":12000,
                "Media Filter":25000,"Hydrocyclone":20000}
FERT_SYS = ["None","Venturi","Dosing Pump","Fertilizer Tank"]
FERT_AR = {"None":"بدون","Venturi":"فنتوري","Dosing Pump":"مضخة حقن",
           "Fertilizer Tank":"تانك تسميد"}
FERT_PRICE = {"None":0,"Venturi":3500,"Dosing Pump":15000,"Fertilizer Tank":6000}

DEFAULT_PRICES = {"main":80.0,"sub":45.0,"lat":6.0,"drip":3.0,
                  "control":2500.0,"flush":450.0,"arv":1800.0,
                  "acid":12000.0,"treat":20000.0}

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

# ============================================================
# WATER QUALITY WARNINGS (Task 5,20)
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
# RECOMMENDATION ENGINE (Task 14)
# ============================================================
def recommend(P, R):
    L = []
    cat = CROPS[P["crop"]]["cat"]
    if cat == "veg":     L.append(("محصول خضري — دورة قصيرة ≤3 أيام","Vegetable — short cycle ≤3d","info"))
    if cat == "orchard": L.append(("أشجار — دورة أسبوعية","Orchard — weekly cycle","info"))
    L += water_quality_warnings(P["ec"], P["ph"], P["sar"])
    if P["wind"] > 4:   L.append(("رياح قوية (>4 م/ث) — عدّل التوقيت","Strong wind (>4 m/s) — adjust timing","warn"))
    if P["slope"] > 5:  L.append(("ميل >5% — PC dripper + زونات","Slope >5% — PC + zoning","warn"))
    if P["power_source"] == "Solar":     L.append(("طاقة شمسية — ري نهاري مفضل","Solar — prefer daytime irrigation","info"))
    if P["power_source"] == "Diesel":    L.append(("ديزل — احسب استهلاك الوقود","Diesel — calculate fuel","info"))
    if P["water_source"] == "Well":      L.append(("بئر — فلتر رملي + تحليل مياه","Well — media filter + water test","info"))
    if P["water_source"] == "Reclaimed": L.append(("مياه معالجة — معالجة إضافية مطلوبة","Reclaimed — extra treatment needed","warn"))
    if R["tdh"] > TDH_WARN:              L.append(("TDH >120م — زونات أو مضخة معززة","TDH >120m — zoning/booster","warn"))
    if R["v_main"] < V_MIN_MAIN:         L.append(("سرعة منخفضة — خطر ترسيب","Low velocity — sediment risk","warn"))
    if R["v_main"] > V_MAX_MAIN:         L.append(("سرعة مرتفعة — خطر تآكل","High velocity — erosion risk","warn"))
    return L

# ============================================================
# AI AGENT — rule-based (Task 28)
# ============================================================
def parse_request(text):
    out = {"area": None, "crop": None, "location": None, "water_source": None}
    if not text: return out
    m = re.search(r"(\d+(?:\.\d+)?)\s*(feddan|فدان|fed|acre|hectare|هكتار|ha)\b", text, re.I)
    if m:
        v = float(m.group(1)); u = m.group(2).lower()
        if u in ("hectare","هكتار","ha"): v *= 2.38
        elif u == "acre": v *= 1.038
        out["area"] = v
    tl = text.lower()
    for c in CROPS:
        if c.lower() in tl or CROPS[c]["ar"] in text: out["crop"] = c; break
    for L in ["matrouh","مطروح","cairo","القاهرة","alexandria","الإسكندرية",
              "noubaria","النوبارية","toshka","توشكى","sinai","سيناء"]:
        if L in tl or L in text: out["location"] = L; break
    if any(w in tl for w in ["well","بئر"]):                out["water_source"] = "Well"
    elif any(w in tl for w in ["nile","نيل"]):              out["water_source"] = "Nile"
    elif any(w in tl for w in ["reclaimed","معالجة"]):      out["water_source"] = "Reclaimed"
    return out

# ============================================================
# V10.1 — POLYGON AREA MODULE
# ============================================================
def polygon_area_m2(coords):
    if len(coords) < 3: return 0.0
    lat0 = sum(c[0] for c in coords) / len(coords)
    m_lat = 111320.0
    m_lon = 111320.0 * math.cos(math.radians(lat0))
    pts = [(lon * m_lon, lat * m_lat) for lat, lon in coords]
    s = 0.0; n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0

def polygon_bbox(coords):
    lats = [c[0] for c in coords]; lons = [c[1] for c in coords]
    lat0, lat1 = min(lats), max(lats)
    lon0, lon1 = min(lons), max(lons)
    latm = (lat0 + lat1) / 2
    W = (lon1 - lon0) * 111320.0 * math.cos(math.radians(latm))
    H = (lat1 - lat0) * 111320.0
    return W, H, latm, (lon0 + lon1) / 2

def parse_kml_coords(kml_bytes):
    txt = kml_bytes.decode("utf-8", errors="ignore")
    m = re.search(r"<coordinates>(.*?)</coordinates>", txt, re.S)
    if not m: return []
    out = []
    for tok in m.group(1).split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0]); lat = float(parts[1])
                out.append((lat, lon))
            except Exception:
                pass
    return out

def parse_geojson_coords(gj_bytes):
    try:
        gj = json.loads(gj_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return []
    def find(node):
        if isinstance(node, list) and node and isinstance(node[0], list):
            if isinstance(node[0][0], list): return find(node[0])
            return [(lat, lon) for lon, lat in node]
        return []
    if gj.get("type") == "FeatureCollection":
        for f in gj.get("features", []):
            g = f.get("geometry", {})
            if g.get("type") in ("Polygon", "MultiPolygon"):
                return find(g["coordinates"])
    elif gj.get("type") in ("Polygon", "MultiPolygon"):
        return find(gj["coordinates"])
    return []

# ============================================================
# DESIGN ENGINE (Tasks 3,4,6,9,10,11,22)
# ============================================================
def run_design(P):
    ci = CROPS[P["crop"]]
    kc, zr, cat = ci["kc"], ci["zr"], ci["cat"]

    # Task 3 — landscape can be None
    if P["project_type"] == "Landscape":
        if P.get("landscape_soil") and P["landscape_soil"] in LANDSCAPE_SOILS:
            taw = float(LANDSCAPE_SOILS[P["landscape_soil"]]["taw"])
        else:
            taw = 150.0
    else:
        taw = float(SOILS[P["soil"]]["taw"])

    # Task 4 + 9 — P_ALLOW[cat]
    raw_mm = P_ALLOW[cat] * taw * zr
    eto = float(P["eto"]); etc = eto * kc

    # Task 9 — limit interval
    max_int = 3 if cat == "veg" else 7 if cat == "orchard" else 5
    interval = max(1, min(raw_mm/etc if etc > 0 else max_int, max_int))
    interval = int(round(interval))

    net_event_mm = etc * interval
    eff = 0.90
    gross_event_mm = net_event_mm / eff

    area_m2 = P["area_feddan"] * FEDDAN_M2
    # V10.1 — use polygon dims if available
    poly_W = st.session_state.get("poly_W")
    poly_H = st.session_state.get("poly_H")
    if poly_W and poly_H:
        field_W, field_H = float(poly_W), float(poly_H)
    else:
        field_W = field_H = math.sqrt(area_m2)

    vol_event_m3 = gross_event_mm * area_m2 / 1000.0
    annual_m3 = (etc * 365 / eff) * area_m2 / 1000.0

    n_zones = max(1, int(P["n_zones"]))
    zone_area = area_m2 / n_zones
    spacing = float(P["dripper_spacing"]); lat_sp = float(P["lateral_spacing"])
    emitters_m2 = 1.0/(spacing*lat_sp) if spacing > 0 and lat_sp > 0 else 0
    zone_emitters = int(emitters_m2 * zone_area)
    q_drip = float(P["dripper_flow"])
    zone_q_lph = zone_emitters * q_drip
    zone_q_lps = zone_q_lph / 3600.0

    D_main = float(P["d_main"]); D_sub = float(P["d_sub"]); D_lat = float(P["d_lat"])
    L_main = float(P["L_main"]); L_sub = float(P["L_sub"]); L_lat = float(P["L_lat"])

    v_main = velocity_ms(zone_q_lps, D_main)
    v_sub  = velocity_ms(zone_q_lps*0.5, D_sub)
    n_lat_per_sub = max(1, int(L_sub/lat_sp)) if lat_sp > 0 else 1
    q_one_lat_lps = zone_q_lps / n_lat_per_sub
    v_lat = velocity_ms(q_one_lat_lps, D_lat)

    hf_main = head_loss_hw(L_main, zone_q_lps, D_main)
    hf_sub  = 0.4 * head_loss_hw(L_sub, zone_q_lps, D_sub)
    hf_lat  = 0.36 * head_loss_hw(L_lat, q_one_lat_lps, D_lat)

    op_press = 15.0 if P["pc_dripper"] == "PC Dripper" else 10.0 + hf_lat
    tdh = max(0.0, float(P["elevation"])) + float(P["suction_lift"]) + \
          hf_main + hf_sub + hf_lat + op_press + float(P["safety"])

    # Task 22 — per tree
    per_tree = None
    if P["crop"] in TREE_CROPS:
        sx = float(P.get("tree_spacing", 5.0)); sy = float(P.get("row_spacing", 6.0))
        L_day = etc * (sx*sy); L_ev = L_day * interval
        per_tree = {"L/day": round(L_day,1), "L/event": round(L_ev,1)}

    R = dict(kc=kc, cat=cat, zr=zr, p_allow=P_ALLOW[cat], taw=taw,
             raw_mm=raw_mm, etc=etc, eto=eto, interval=interval,
             net_event_mm=net_event_mm, gross_event_mm=gross_event_mm,
             event_depth_mm=gross_event_mm, event_volume_m3=vol_event_m3,
             annual_m3=annual_m3, area_m2=area_m2, n_zones=n_zones,
             zone_area_m2=zone_area, zone_emitters=zone_emitters,
             zone_q_lps=zone_q_lps, zone_q_m3h=zone_q_lph/1000.0,
             v_main=v_main, v_sub=v_sub, v_lat=v_lat,
             hf_main=hf_main, hf_sub=hf_sub, hf_lat=hf_lat,
             tdh=tdh, op_pressure=op_press, per_tree=per_tree,
             D_main=D_main, D_sub=D_sub, D_lat=D_lat,
             L_main=L_main, L_sub=L_sub, L_lat=L_lat,
             field_W=field_W, field_H=field_H)
    R["recommendations"] = recommend(P, R)
    return R

# ============================================================
# BOQ (Tasks 12,13,25)
# ============================================================
def compute_boq(P, R, prices=None, vat=14.0):
    if prices is None: prices = DEFAULT_PRICES
    rows = []
    rows.append((T("Main pipe","مواسير رئيسي"),   f"{R['L_main']:.0f} m",           R["L_main"]*prices["main"]))
    rows.append((T("Submain","فرعي"),              f"{R['L_sub']:.0f} m",            R["L_sub"]*prices["sub"]))
    n_z = R["n_zones"]
    rows.append((T("Lateral","خراطيم"),            f"{R['L_lat']*n_z:.0f} m",        R["L_lat"]*n_z*prices["lat"]))
    total_drip = R["zone_emitters"] * n_z
    rows.append((T("Drippers","منقطات"),           f"{total_drip:,}",                total_drip*prices["drip"]))
    rows.append((T("Filter","فلتر"),               FILTER_AR.get(P["filter_type"], P["filter_type"]), FILTER_PRICE.get(P["filter_type"], 0)))
    if FERT_PRICE.get(P["fert_sys"], 0) > 0:
        rows.append((T("Fertigation","تسميد"),     FERT_AR.get(P["fert_sys"], P["fert_sys"]), FERT_PRICE[P["fert_sys"]]))
    rows.append((T("Control valves","محابس تحكم"), f"{n_z}",                         n_z*prices["control"]))
    rows.append((T("Flush valves","محابس غسيل"),   f"{n_z*2}",                       n_z*2*prices["flush"]))
    rows.append((T("Air release valves","محابس هواء"), "4",                           4*prices["arv"]))
    if P["ph"] > 8.2:
        rows.append((T("Acid injection","حقن حامض"), "1", prices["acid"]))
    if P["ec"] > 5:
        rows.append((T("Water treatment","معالجة مياه"), "-", prices["treat"]))
    before = sum(r[2] for r in rows)
    rows.append((T("Fittings (10%)","وصلات 10%"), "-", 0.10*before))
    subtotal = sum(r[2] for r in rows)
    vat_amt = subtotal * vat/100
    total = subtotal + vat_amt
    return rows, subtotal, vat_amt, total

# ============================================================
# PLOT (Tasks 23,24)
# ============================================================
def build_plot(P, R):
    W = R.get("field_W", math.sqrt(R["area_m2"]))
    H = R.get("field_H", W)
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, lw=2))
    ax.plot([0, W], [H, H], color="blue", lw=2.5)

    n_sub = min(15, max(2, int(W/40)+1))
    xs = [i*W/(n_sub-1) if n_sub > 1 else W/2 for i in range(n_sub)]
    for x in xs:
        ax.plot([x, x], [0, H], color="green", lw=1)

    truncated = False; drawn = 0
    n_lat = 30
    for x in xs:
        for j in range(n_lat):
            y = j*H/(n_lat-1) if n_lat > 1 else H/2
            ax.plot([max(0, x-W/(2*n_sub)), min(W, x+W/(2*n_sub))], [y, y],
                    color="orange", lw=0.3, alpha=0.7)
            drawn += 1
            if drawn >= MAX_PLOT_LINES: truncated = True; break
        if truncated: break

    ax.annotate("", xy=(W*0.95, H*1.02), xytext=(W*0.95, H*0.9),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.text(W*0.95, H*1.03, "N", ha="center", fontsize=12, fontweight="bold")
    s_len = round(W/5)
    ax.plot([W*0.05, W*0.05+s_len], [H*0.05, H*0.05], color="black", lw=4)
    ax.text(W*0.05+s_len/2, H*0.02, f"{s_len} m", ha="center")
    ax.plot(W*0.02, H*0.98, marker="s", ms=12, color="red")
    ax.text(W*0.04, H*0.98, T("Pump","مضخة"), fontsize=10)
    ax.text(W*0.5, H*0.5,
            f"{P['project_name']}\n{P['area_feddan']:.2f} feddan\n{P['crop']}",
            ha="center", va="center", fontsize=12,
            bbox=dict(boxstyle="round", fc="white", ec="black"))
    ax.set_xlim(-W*0.05, W*1.1); ax.set_ylim(-H*0.05, H*1.1)
    ax.set_aspect("equal"); ax.set_title(T("Plot Layout","مخطط الحقل"))
    handles = [Line2D([0],[0],color="blue",lw=2,label="Main"),
               Line2D([0],[0],color="green",lw=1,label="Submain"),
               Line2D([0],[0],color="orange",lw=0.5,label="Lateral")]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    plt.tight_layout()
    return fig, {"truncated": truncated}

# ============================================================
# DXF (Tasks 15,16,17,18,19)
# ============================================================
def build_dxf(P, R, vat_pct, total_cost):
    if not EZDXF_OK: return None
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for lay in ["MAIN","SUBMAIN","LATERAL","EMITTER","FILTER","FERTIGATION",
                "AIR_RELEASE","FLUSH","CONTROL","HYDRANT","LABELS","TITLE"]:
        if lay not in doc.layers: doc.layers.add(lay)

    W = R.get("field_W", math.sqrt(R["area_m2"]))
    H = R.get("field_H", W)
    msp.add_lwpolyline([(0,0),(W,0),(W,H),(0,H),(0,0)], dxfattribs={"layer":"MAIN"})
    msp.add_line((0,H),(W,H), dxfattribs={"layer":"MAIN"})

    n_sub = min(15, max(2, int(W/40)+1))
    xs = [i*W/(n_sub-1) if n_sub > 1 else W/2 for i in range(n_sub)]
    for x in xs:
        msp.add_line((x,0),(x,H), dxfattribs={"layer":"SUBMAIN"})

    n_lat = 30
    emitters_drawn = 0
    for x in xs:
        for j in range(n_lat):
            y = j*H/(n_lat-1) if n_lat > 1 else H/2
            x1 = max(0, x-W/(2*n_sub)); x2 = min(W, x+W/(2*n_sub))
            msp.add_line((x1,y),(x2,y), dxfattribs={"layer":"LATERAL"})
            for k in range(5):
                if emitters_drawn >= DXF_EMITTER_LIMIT: break
                xe = x1 + (x2-x1)*(k+0.5)/5
                msp.add_circle((xe,y), 0.05, dxfattribs={"layer":"EMITTER"})
                emitters_drawn += 1

    for x in xs:
        msp.add_circle((x, 0), 0.3, dxfattribs={"layer":"FLUSH"})
        msp.add_circle((x, H), 0.3, dxfattribs={"layer":"FLUSH"})

    for pt in [(0,H),(W,H)]:
        msp.add_circle(pt, 0.4, dxfattribs={"layer":"AIR_RELEASE"})

    msp.add_circle((W*0.05, H*0.03), 1.0, dxfattribs={"layer":"FILTER"})
    t = msp.add_text("FILTER", dxfattribs={"layer":"LABELS","height":1.0})
    t.dxf.insert = (W*0.05+1.2, H*0.03)
    if P["fert_sys"] != "None":
        msp.add_circle((W*0.05, H*0.07), 1.0, dxfattribs={"layer":"FERTIGATION"})
        t = msp.add_text(P["fert_sys"].upper(), dxfattribs={"layer":"LABELS","height":1.0})
        t.dxf.insert = (W*0.05+1.2, H*0.07)

    msp.add_circle((W*0.1, H), 0.5, dxfattribs={"layer":"CONTROL"})
    msp.add_circle((W*0.5, H*0.5), 0.5, dxfattribs={"layer":"HYDRANT"})

    title = f"{P['project_name']} | {P['crop']} | {P['area_feddan']:.2f} feddan"
    t = msp.add_text(title, dxfattribs={"layer":"TITLE","height":2.0})
    t.dxf.insert = (W*0.02, H*1.10)
    t = msp.add_text(f"Total incl. VAT ({vat_pct:.0f}%): {total_cost:,.0f} EGP",
                     dxfattribs={"layer":"TITLE","height":1.5})
    t.dxf.insert = (W*0.02, H*1.05)

    buf = io.BytesIO(); doc.saveas(buf); buf.seek(0)
    return buf

# ============================================================
# REPORTS (Tasks 21,26)
# ============================================================
def agronomic_report_text(P, R):
    lines = []
    lines.append("="*60)
    lines.append(T("AGRONOMIC REPORT","التقرير الزراعي"))
    lines.append("="*60)
    lines.append(f"{T('Project','المشروع')}: {P['project_name']}")
    lines.append(f"{T('Crop','المحصول')}: {P['crop']} ({CROPS[P['crop']]['ar']})")
    lines.append(f"{T('Category','الفئة')}: {R['cat']}")
    lines.append(f"{T('Area','المساحة')}: {P['area_feddan']:.2f} feddan ({R['area_m2']:.0f} m2)")
    lines.append("")
    lines.append(f"{T('Kc','معامل المحصول')}: {R['kc']:.2f}")
    lines.append(f"ETo: {R['eto']:.2f} mm/day")
    lines.append(f"ETc: {R['etc']:.2f} mm/day")
    lines.append(f"{T('RAW','المياه المتاحة')}: {R['raw_mm']:.1f} mm")
    lines.append(f"{T('Interval','دورة الري')}: {R['interval']} day(s)")
    lines.append(f"{T('Depth/event','عمق الريّة')}: {R['event_depth_mm']:.1f} mm")
    lines.append(f"{T('Volume/event','حجم الريّة')}: {R['event_volume_m3']:.1f} m3")
    lines.append(f"{T('Annual water','الاستهلاك السنوي')}: {R['annual_m3']:.0f} m3")
    if R["per_tree"]:
        lines.append(f"{T('Water/tree/day','مياه/شجرة/يوم')}: {R['per_tree']['L/day']} L")
        lines.append(f"{T('Water/tree/event','مياه/شجرة/ريّة')}: {R['per_tree']['L/event']} L")
    lines.append("")
    lines.append(T("--- Water Quality ---","--- جودة المياه ---"))
    lines.append(f"EC: {P['ec']} dS/m | pH: {P['ph']} | SAR: {P['sar']}")
    lines.append("")
    lines.append(T("--- Recommendations ---","--- التوصيات ---"))
    for ar, en, lvl in R["recommendations"]:
        lines.append(f"[{lvl.upper()}] {T(en, ar)}")
    return "\n".join(lines)

# ============================================================
# MAIN UI (Task 27)
# ============================================================
def main():
    st.set_page_config(page_title="Smart Irrigation AI V10.1", layout="wide",
                       initial_sidebar_state="expanded")
    if "lang" not in st.session_state: st.session_state.lang = "ar"

    with st.sidebar:
        lang_sel = st.selectbox("Language / اللغة", ["العربية","English"])
        st.session_state.lang = "ar" if lang_sel == "العربية" else "en"
        st.markdown("---")
        st.caption("Smart Irrigation AI — V10.1")
        st.caption("© 2025")

    st.title("💧 " + T("Smart Irrigation AI V10.1","الري الذكي V10.1"))
    st.caption(T("All V10 tasks + Polygon Area","كل مهام V10 + حساب المساحة بالـ Polygon"))

    # AI Assistant (Task 28)
    st.markdown("### 🤖 " + T("Quick Setup (AI Assistant)","إعداد سريع (المساعد الذكي)"))
    q = st.text_input(T("Describe your project","اكتب وصف مشروعك"), "",
                      placeholder=T("e.g. 25 feddans olive in Matrouh with well",
                                    "مثال: 25 فدان زيتون في مطروح مصدر بئر"))
    parsed = parse_request(q)
    if any(v is not None for v in parsed.values()):
        st.success(f"🔎 {parsed}")

    tabs = st.tabs([
        "📝 " + T("Inputs","المدخلات"),
        "📊 " + T("Design","التصميم"),
        "🌾 " + T("Agronomic","زراعي"),
        "💧 " + T("Water Quality","جودة المياه"),
        "💰 " + T("BOQ","الكميات"),
        "🗺️ " + T("Plot","المخطط"),
        "📐 DXF",
    ])

    # ---------- Tab 0: Inputs ----------
    with tabs[0]:
        st.subheader(T("Project Info","بيانات المشروع"))
        c1, c2, c3 = st.columns(3)
        with c1:
            proj = st.text_input(T("Project name","اسم المشروع"), "Project-01")
            ptype = st.selectbox(T("Type","النوع"), ["Agricultural","Landscape"])
            crop_default = parsed.get("crop") or "Tomato"
            idx = list(CROPS).index(crop_default) if crop_default in CROPS else 0
            crop = st.selectbox(T("Crop","المحصول"), list(CROPS.keys()),
                                format_func=lambda k: f"{CROPS[k]['ar']} / {k}", index=idx)
        with c2:
            eto = st.number_input(T("ETo (mm/day)","ETo (مم/يوم)"), 0.5, 20.0, 5.5)
            wind = st.number_input(T("Wind (m/s)","الرياح (م/ث)"), 0.0, 20.0, 2.0)
            slope = st.number_input(T("Slope (%)","الميل (%)"), 0.0, 50.0, 0.0)
            wsrc = st.selectbox(T("Water source","مصدر المياه"),
                                ["Nile","Well","Reclaimed","Mixed"])
            psrc = st.selectbox(T("Power","الطاقة"), ["Grid","Solar","Diesel"])
        with c3:
            lat = st.number_input(T("Latitude","خط العرض"), -90.0, 90.0, 30.0, 0.0001)
            lon = st.number_input(T("Longitude","خط الطول"), -180.0, 180.0, 30.0, 0.0001)
            if ptype == "Agricultural":
                soil = st.selectbox(T("Soil","التربة"), list(SOILS.keys()),
                                    format_func=lambda k: f"{SOILS[k]['ar']} / {k}")
                lsoil = None
            else:
                soil = None
                lsoil = st.selectbox(T("Landscape base","قاعدة اللاندسكيب"),
                                     ["__none__"] + list(LANDSCAPE_SOILS.keys()),
                                     format_func=lambda k: T("None (no soil)","لا شيء (بدون تربة)")
                                     if k == "__none__" else LANDSCAPE_SOILS[k]["ar"])

        # ---- V10.1 — Area Source ----
        st.markdown("---")
        st.markdown("### 🗺️ " + T("Area Source","مصدر المساحة"))
        area_mode = st.radio(
            T("How to define area?","إزاي تحدد المساحة؟"),
            [T("Manual (feddan)","يدوي (فدان)"),
             T("Coordinates","إحداثيات"),
             T("Upload KML/GeoJSON","رفع KML/GeoJSON")],
            horizontal=True, label_visibility="collapsed")

        if area_mode == T("Manual (feddan)","يدوي (فدان)"):
            area = st.number_input(T("Area (feddan)","المساحة (فدان)"),
                                   0.1, 10000.0, float(parsed.get("area") or 5.0))
            st.session_state.pop("poly_W", None)
            st.session_state.pop("poly_H", None)
        else:
            coords = []
            if area_mode == T("Coordinates","إحداثيات"):
                txt = st.text_area(
                    T("Paste (lat, lon) — one per line","الصق (lat, lon) — سطر لكل نقطة"),
                    "30.0450, 31.2350\n30.0450, 31.2360\n30.0440, 31.2360\n30.0440, 31.2350",
                    height=140)
                for line in txt.strip().split("\n"):
                    try:
                        a, b = line.replace(";", ",").split(",")
                        coords.append((float(a.strip()), float(b.strip())))
                    except Exception:
                        pass
            else:
                up = st.file_uploader(T("Upload file","ارفع الملف"),
                                      type=["kml","geojson","json"])
                if up is not None:
                    nm = up.name.lower(); raw = up.read()
                    if nm.endswith(".kml"):
                        coords = parse_kml_coords(raw)
                    else:
                        coords = parse_geojson_coords(raw)

            if len(coords) >= 3:
                area_m2_poly = polygon_area_m2(coords)
                pW, pH, cx_lat, cx_lon = polygon_bbox(coords)
                fed = area_m2_poly / FEDDAN_M2
                st.success(
                    f"✅ {T('Area','المساحة')}: **{area_m2_poly:,.0f} m²** = "
                    f"**{fed:.2f} {T('feddan','فدان')}** | "
                    f"{T('BBox','الأبعاد')}: {pW:.0f} × {pH:.0f} m")
                aspect = max(pW, pH) / max(1.0, min(pW, pH))
                if aspect > 4:
                    st.warning(T("الشكل ممدود (>4:1) — راجع الرسم",
                                 "Elongated plot (>4:1) — verify polygon"))
                area = fed
                st.session_state["poly_W"] = pW
                st.session_state["poly_H"] = pH
            else:
                st.info(T("أدخل 3 نقاط على الأقل","Enter at least 3 points"))
                area = 5.0
                st.session_state.pop("poly_W", None)
                st.session_state.pop("poly_H", None)

        st.markdown("---")
        st.subheader("💧 " + T("Water Quality","جودة المياه"))
        w1, w2, w3 = st.columns(3)
        with w1: ec = st.number_input("EC (dS/m)", 0.0, 20.0, 1.2)
        with w2: ph = st.number_input("pH", 4.0, 10.0, 7.5)
        with w3: sar = st.number_input("SAR", 0.0, 30.0, 3.0)

        st.markdown("---")
        st.subheader("💧 " + T("Emitter Selection","اختيار المنقط"))
        e1, e2, e3 = st.columns(3)
        with e1: dflow = st.selectbox(T("Dripper flow (L/h)","التصرف (لتر/س)"), DRIP_FLOWS, index=1)
        with e2: pc = st.selectbox(T("Dripper type","النوع"), ["PC Dripper","Non-PC Dripper"])
        with e3: dsp = st.number_input(T("Dripper spacing (m)","مسافة المنقط (م)"), 0.1, 5.0, 0.5)
        e4, e5 = st.columns(2)
        with e4: lsp = st.number_input(T("Lateral spacing (m)","مسافة الخراطيم (م)"), 0.1, 10.0, 0.8)
        with e5:
            if crop in TREE_CROPS:
                tsp = st.number_input(T("Tree spacing (m)","مسافة الأشجار (م)"), 1.0, 20.0, 5.0)
            else:
                tsp = 5.0
        if crop in TREE_CROPS:
            rsp = st.number_input(T("Row spacing (m)","مسافة الصفوف (م)"), 1.0, 20.0, 6.0)
        else:
            rsp = 6.0

        st.markdown("---")
        st.subheader("🔧 " + T("Filter & Fertigation","الفلاتر والتسميد"))
        f1, f2 = st.columns(2)
        with f1: filt = st.selectbox(T("Filter","الفلتر"), FILTERS, format_func=lambda k: FILTER_AR[k])
        with f2: fert = st.selectbox(T("Fertigation","التسميد"), FERT_SYS, format_func=lambda k: FERT_AR[k])

        st.markdown("---")
        st.subheader("📏 " + T("Hydraulics","الهيدروليكا"))
        h1, h2, h3 = st.columns(3)
        with h1:
            d_main = st.selectbox(T("Main Ø (mm)","قطر الرئيسي"), [50,63,75,90,110,125,160,200], index=3)
            L_main = st.number_input(T("Main length (m)","طول الرئيسي"), 1.0, 5000.0, 200.0)
        with h2:
            d_sub = st.selectbox(T("Submain Ø (mm)","قطر الفرعي"), [32,40,50,63,75,90], index=2)
            L_sub = st.number_input(T("Submain length (m)","طول الفرعي"), 1.0, 5000.0, 200.0)
        with h3:
            d_lat = st.selectbox(T("Lateral Ø (mm)","قطر الخرطوم"), [12,16,20,25], index=1)
            L_lat = st.number_input(T("Lateral length (m)","طول الخرطوم"), 1.0, 500.0, 50.0)
        h4, h5, h6 = st.columns(3)
        with h4: nz = st.number_input(T("Zones","عدد الزونات"), 1, 50, 1)
        with h5: elev = st.number_input(T("Elev. diff (m)","فرق المنسوب"), 0.0, 200.0, 0.0)
        with h6: succ = st.number_input(T("Suction lift (m)","الشفط"), 0.0, 15.0, 2.0)
        safe = st.number_input(T("Safety margin (m)","هامش أمان"), 0.0, 30.0, 5.0)

        P = dict(project_name=proj, project_type=ptype, crop=crop, area_feddan=area,
                 eto=eto, wind=wind, slope=slope, water_source=wsrc, power_source=psrc,
                 lat=lat, lon=lon, soil=soil, landscape_soil=lsoil,
                 ec=ec, ph=ph, sar=sar, dripper_flow=dflow, pc_dripper=pc,
                 dripper_spacing=dsp, lateral_spacing=lsp, tree_spacing=tsp, row_spacing=rsp,
                 filter_type=filt, fert_sys=fert, d_main=d_main, d_sub=d_sub, d_lat=d_lat,
                 L_main=L_main, L_sub=L_sub, L_lat=L_lat, n_zones=nz,
                 elevation=elev, suction_lift=succ, safety=safe)
        st.session_state["P"] = P
        st.session_state["R"] = run_design(P)
        st.success(T("Inputs saved","تم حفظ المدخلات"))

    P = st.session_state.get("P"); R = st.session_state.get("R")
    if not P or not R:
        st.info(T("Fill Inputs then check other tabs","املأ المدخلات ثم راجع باقي التبويبات"))
        return

    # ---------- Tab 1: Design ----------
    with tabs[1]:
        st.subheader(T("Design Results","نتائج التصميم"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ETc (mm/d)", round(R["etc"], 2))
        c2.metric("RAW (mm)", round(R["raw_mm"], 1))
        c3.metric(T("Interval (d)","الدورة (ي)"), R["interval"])
        c4.metric("TDH (m)", round(R["tdh"], 1))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(T("Depth/event (mm)","عمق الريّة"), round(R["event_depth_mm"], 1))
        c2.metric(T("Vol/event (m³)","حجم الريّة"), round(R["event_volume_m3"], 1))
        c3.metric(T("Annual (m³)","سنوي"), round(R["annual_m3"], 0))
        c4.metric(T("Zone flow (m³/h)","تصرف الزون"), round(R["zone_q_m3h"], 1))
        if R["per_tree"]:
            st.success(f"🌳 {T('Per tree','لكل شجرة')}: "
                       f"{R['per_tree']['L/day']} L/day | "
                       f"{R['per_tree']['L/event']} L/event")

        st.markdown("### " + T("Hydraulics","الهيدروليكا"))
        st.table(pd.DataFrame([
            {"Pipe": T("Main","رئيسي"),    "D (mm)": R["D_main"], "L (m)": R["L_main"],
             "V (m/s)": round(R["v_main"], 2), "Hf (m)": round(R["hf_main"], 2)},
            {"Pipe": T("Submain","فرعي"),  "D (mm)": R["D_sub"],  "L (m)": R["L_sub"],
             "V (m/s)": round(R["v_sub"], 2),  "Hf (m)": round(R["hf_sub"], 2)},
            {"Pipe": T("Lateral","خرطوم"), "D (mm)": R["D_lat"],  "L (m)": R["L_lat"],
             "V (m/s)": round(R["v_lat"], 2),  "Hf (m)": round(R["hf_lat"], 2)},
        ]))

        if R["v_main"] < V_MIN_MAIN:
            st.warning(T("سرعة الرئيسي منخفضة (<0.6 م/ث) — خطر ترسيب",
                         "Main velocity < 0.6 m/s — sediment risk"))
        if R["v_main"] > V_MAX_MAIN:
            st.warning(T("سرعة الرئيسي مرتفعة (>2.5 م/ث) — خطر تآكل",
                         "Main velocity > 2.5 m/s — erosion risk"))
        if R["tdh"] > TDH_WARN:
            st.error(T("TDH > 120 م — راجع الزونات أو أضف مضخة معززة",
                       "TDH > 120 m — review zoning or add booster"))

        st.markdown("### " + T("Recommendations","التوصيات"))
        for ar, en, lvl in R["recommendations"]:
            msg = T(en, ar)
            if lvl == "warn": st.warning(msg)
            else:             st.info(msg)

    # ---------- Tab 2: Agronomic ----------
    with tabs[2]:
        st.subheader("🌾 " + T("Agronomic Report","التقرير الزراعي"))
        st.text(agronomic_report_text(P, R))
        st.download_button(
            "⬇️ " + T("Download Agronomic Report","تحميل التقرير الزراعي"),
            agronomic_report_text(P, R),
            file_name=f"agronomic_{P['project_name']}.txt")

    # ---------- Tab 3: Water Quality ----------
    with tabs[3]:
        st.subheader("💧 " + T("Water Quality Report","تقرير جودة المياه"))
        st.table(pd.DataFrame([
            {"Parameter":"EC", "Value": P["ec"], "Unit":"dS/m"},
            {"Parameter":"pH", "Value": P["ph"], "Unit":"-"},
            {"Parameter":"SAR","Value": P["sar"],"Unit":"-"},
        ]))
        warns = water_quality_warnings(P["ec"], P["ph"], P["sar"])
        if not warns:
            st.success(T("المياه في النطاق الآمن","Water within safe range"))
        for ar, en, lvl in warns:
            msg = T(en, ar)
            if lvl == "warn": st.warning(msg)
            else:             st.info(msg)

    # ---------- Tab 4: BOQ ----------
    with tabs[4]:
        st.subheader("💰 " + T("Bill of Quantities","جدول الكميات"))
        rows, subtotal, vat_amt, total = compute_boq(P, R)
        df_boq = pd.DataFrame(rows, columns=[T("Item","البند"), T("Spec","المواصفات"),
                                              T("Cost (EGP)","التكلفة (ج.م)")])
        st.dataframe(df_boq, use_container_width=True)
        st.metric(T("Subtotal (EGP)","الإجمالي قبل الضريبة"), f"{subtotal:,.0f}")
        st.metric(T("VAT 14% (EGP)","ضريبة 14%"), f"{vat_amt:,.0f}")
        st.metric(T("TOTAL (EGP)","الإجمالي النهائي"), f"{total:,.0f}")
        st.download_button(
            "⬇️ " + T("Download BOQ (CSV)","تحميل الكميات (CSV)"),
            df_boq.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"boq_{P['project_name']}.csv")

    # ---------- Tab 5: Plot ----------
    with tabs[5]:
        st.subheader("🗺️ " + T("Plot Layout","مخطط الحقل"))
        if MPL_OK:
            fig, info = build_plot(P, R)
            st.pyplot(fig)
            if info["truncated"]:
                st.warning(T(f"تم عرض أول {MAX_PLOT_LINES} خط فقط",
                             f"Showing first {MAX_PLOT_LINES} lines only"))
            buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150); buf.seek(0)
            st.download_button("⬇️ PNG", buf,
                               file_name=f"plot_{P['project_name']}.png",
                               mime="image/png")
        else:
            st.error("matplotlib not installed")

    # ---------- Tab 6: DXF ----------
    with tabs[6]:
        st.subheader("📐 " + T("DXF Drawing","ملف DXF"))
        if not EZDXF_OK:
            st.error("ezdxf not installed")
        else:
            rows, subtotal, vat_amt, total = compute_boq(P, R)
            dxf_buf = build_dxf(P, R, 14.0, total)
            if dxf_buf:
                st.download_button(
                    "⬇️ " + T("Download DXF","تحميل DXF"),
                    dxf_buf,
                    file_name=f"design_{P['project_name']}.dxf",
                    mime="application/dxf")
                st.success(T("DXF جاهز","DXF ready"))

if __name__ == "__main__":
    main()
