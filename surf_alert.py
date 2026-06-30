import os
import json
import hashlib
import csv
from pathlib import Path
from datetime import datetime, timedelta

import requests

# ============================================================
# KONFIGURATION
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

FORECAST_DAYS = 5
ALERT_THRESHOLD = 60
SESSION_MIN_HOURS = 3
STATE_FILE = "state.json"
TIMEZONE = "Europe/Berlin"
HISTORY_FILE = Path("history.csv")

SPOTS = [
    {
        "name": "Klitmøller",
        "lat": 57.044,
        "lon": 8.494,

        # alte Felder erstmal drin lassen, damit nichts kaputtgeht
        "min_swell_height": 1.2,
        "min_swell_period": 11.0,
        "swell_dir_min": 285,
        "swell_dir_max": 345,
        "wind_dir_min": 70,
        "wind_dir_max": 150,
        "max_wind_speed": 11.0,
        "max_wind_gust": 16.0,
        "use_tide": False,
        "tide_pref": "any",

        # neue Felder
        "spot_class": "cold_hawaii_open",
        "swell_primary": {"center": 315, "tol": 25, "weight": 0.22},
        "swell_secondary": {"center": 290, "tol": 20, "weight": 0.10},
        "wind_offshore": {"center": 110, "tol": 30, "weight": 0.18},
        "wind_cross": {"center": 80, "tol": 25, "weight": 0.08},
        "period_profile": {"ok": 9.5, "good": 11.0, "excellent": 13.0, "weight": 0.22},
        "height_profile": {"ok": 1.0, "good": 1.5, "excellent": 2.2, "weight": 0.10},
        "tide_weight": 0.00,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.5, "penalty": 10},
    },

    {
        "name": "Nørre Vorupør",
        "lat": 56.951,
        "lon": 8.375,

        "min_swell_height": 1.2,
        "min_swell_period": 10.5,
        "swell_dir_min": 280,
        "swell_dir_max": 340,
        "wind_dir_min": 80,
        "wind_dir_max": 150,
        "max_wind_speed": 11.0,
        "max_wind_gust": 16.0,
        "use_tide": False,
        "tide_pref": "any",

        "spot_class": "cold_hawaii_pier",
        "swell_primary": {"center": 305, "tol": 22, "weight": 0.22},
        "swell_secondary": {"center": 285, "tol": 18, "weight": 0.10},
        "wind_offshore": {"center": 120, "tol": 28, "weight": 0.18},
        "wind_cross": {"center": 90, "tol": 25, "weight": 0.08},
        "period_profile": {"ok": 9.0, "good": 10.5, "excellent": 12.5, "weight": 0.22},
        "height_profile": {"ok": 1.0, "good": 1.4, "excellent": 2.0, "weight": 0.10},
        "tide_weight": 0.00,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.5, "penalty": 9},
    },

    {
        "name": "Hanstholm",
        "lat": 57.118,
        "lon": 8.616,

        "min_swell_height": 1.1,
        "min_swell_period": 10.0,
        "swell_dir_min": 285,
        "swell_dir_max": 345,
        "wind_dir_min": 80,
        "wind_dir_max": 160,
        "max_wind_speed": 12.0,
        "max_wind_gust": 17.0,
        "use_tide": False,
        "tide_pref": "any",

        "spot_class": "cold_hawaii_robust",
        "swell_primary": {"center": 315, "tol": 25, "weight": 0.22},
        "swell_secondary": {"center": 290, "tol": 20, "weight": 0.10},
        "wind_offshore": {"center": 120, "tol": 35, "weight": 0.18},
        "wind_cross": {"center": 85, "tol": 25, "weight": 0.08},
        "period_profile": {"ok": 9.0, "good": 10.5, "excellent": 12.5, "weight": 0.20},
        "height_profile": {"ok": 1.0, "good": 1.5, "excellent": 2.3, "weight": 0.12},
        "tide_weight": 0.00,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.0, "penalty": 8},
    },

    {
        "name": "Norderney",
        "lat": 53.715,
        "lon": 7.159,

        "min_swell_height": 0.8,
        "min_swell_period": 8.5,
        "swell_dir_min": 320,
        "swell_dir_max": 20,
        "wind_dir_min": 140,
        "wind_dir_max": 220,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid_high",

        "spot_class": "northsea_island",
        "swell_primary": {"center": 350, "tol": 18, "weight": 0.24},
        "swell_secondary": {"center": 325, "tol": 20, "weight": 0.10},
        "wind_offshore": {"center": 180, "tol": 25, "weight": 0.20},
        "wind_cross": {"center": 150, "tol": 20, "weight": 0.08},
        "period_profile": {"ok": 8.5, "good": 10.0, "excellent": 12.0, "weight": 0.22},
        "height_profile": {"ok": 0.8, "good": 1.1, "excellent": 1.6, "weight": 0.10},
        "tide_weight": 0.20,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.0, "penalty": 12},
    },

    {
        "name": "Scheveningen",
        "lat": 52.111,
        "lon": 4.273,

        "min_swell_height": 0.9,
        "min_swell_period": 8.5,
        "swell_dir_min": 305,
        "swell_dir_max": 20,
        "wind_dir_min": 120,
        "wind_dir_max": 220,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid_high",

        "spot_class": "northsea_city_beach",
        "swell_primary": {"center": 330, "tol": 22, "weight": 0.22},
        "swell_secondary": {"center": 355, "tol": 20, "weight": 0.10},
        "wind_offshore": {"center": 150, "tol": 25, "weight": 0.18},
        "wind_cross": {"center": 120, "tol": 20, "weight": 0.08},
        "period_profile": {"ok": 8.5, "good": 10.0, "excellent": 12.0, "weight": 0.22},
        "height_profile": {"ok": 0.9, "good": 1.2, "excellent": 1.8, "weight": 0.10},
        "tide_weight": 0.15,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.0, "penalty": 11},
    },

    {
        "name": "Domburg",
        "lat": 51.563,
        "lon": 3.495,

        "min_swell_height": 0.9,
        "min_swell_period": 8.5,
        "swell_dir_min": 320,
        "swell_dir_max": 30,
        "wind_dir_min": 120,
        "wind_dir_max": 210,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid_high",

        "spot_class": "northsea_zeeland",
        "swell_primary": {"center": 340, "tol": 25, "weight": 0.22},
        "swell_secondary": {"center": 10, "tol": 20, "weight": 0.10},
        "wind_offshore": {"center": 150, "tol": 25, "weight": 0.18},
        "wind_cross": {"center": 120, "tol": 20, "weight": 0.08},
        "period_profile": {"ok": 8.5, "good": 10.0, "excellent": 12.0, "weight": 0.22},
        "height_profile": {"ok": 0.9, "good": 1.2, "excellent": 1.8, "weight": 0.10},
        "tide_weight": 0.12,
        "windswell_penalty": {"enabled": True, "short_period_below": 8.0, "penalty": 10},
    },
]

# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def parse_dt(s):
    return datetime.fromisoformat(s)

def deg_diff(a, b):
    return abs((a - b + 180) % 360 - 180)

def range_midpoint(start, end):
    start %= 360
    end %= 360
    if start <= end:
        return (start + end) / 2
    width = (360 - start) + end
    return (start + width / 2) % 360

def score_direction(direction, start, end):
    if direction is None:
        return 0.0

    mid = range_midpoint(start, end)
    if start <= end:
        half_window = (end - start) / 2
    else:
        half_window = ((360 - start) + end) / 2

    diff = deg_diff(direction, mid)
    if diff <= half_window:
        return 100.0

    extra = diff - half_window
    return max(0.0, 100.0 - (extra / 90.0) * 100.0)

def score_min_threshold(value, minimum, full_score_at=None):
    if value is None:
        return 0.0
    if full_score_at is None:
        full_score_at = minimum * 1.6

    if value < minimum:
        return 0.0
    if value >= full_score_at:
        return 100.0

    return ((value - minimum) / (full_score_at - minimum)) * 100.0

def score_max_threshold(value, maximum, zero_score_at=None):
    if value is None:
        return 0.0
    if zero_score_at is None:
        zero_score_at = maximum * 1.8

    if value <= maximum:
        return 100.0
    if value >= zero_score_at:
        return 0.0

    return 100.0 - ((value - maximum) / (zero_score_at - maximum)) * 100.0

def normalize(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return [None] * len(values)
    lo = min(clean)
    hi = max(clean)
    if hi - lo < 1e-9:
        return [0.5 if v is not None else None for v in values]
    return [None if v is None else (v - lo) / (hi - lo) for v in values]

def tide_score(norm_level, pref):
    if norm_level is None or pref == "any":
        return 100.0

    if pref == "low":
        target = 0.1
    elif pref == "mid":
        target = 0.5
    elif pref == "mid_high":
        target = 0.7
    elif pref == "high":
        target = 0.9
    else:
        target = 0.5

    diff = abs(norm_level - target)
    return max(0.0, 100.0 - (diff / 0.5) * 100.0)

# ============================================================
# NEUE SPOT-SPEZIFISCHE SCORE-HILFSFUNKTIONEN
# ============================================================

def score_direction_window(direction, center, tolerance):
    """
    100 Punkte im Kernfenster, danach weicher Abfall.
    tolerance = halbe Breite des idealen Fensters
    """
    if direction is None:
        return 0.0

    diff = deg_diff(direction, center)

    if diff <= tolerance:
        return 100.0

    # außerhalb des Fensters weicher Abfall über weitere 70°
    extra = diff - tolerance
    return max(0.0, 100.0 - (extra / 70.0) * 100.0)


def score_profile_direction(direction, primary=None, secondary=None):
    """
    Kombiniert Primary- und Secondary-Richtungsfenster.
    """
    scores = []

    if primary:
        s = score_direction_window(direction, primary["center"], primary["tol"])
        scores.append(s * primary.get("weight", 1.0))

    if secondary:
        s = score_direction_window(direction, secondary["center"], secondary["tol"])
        scores.append(s * secondary.get("weight", 1.0))

    if not scores:
        return 0.0

    # auf 0..100 normalisieren
    total_weight = 0.0
    if primary:
        total_weight += primary.get("weight", 1.0)
    if secondary:
        total_weight += secondary.get("weight", 1.0)

    return sum(scores) / total_weight if total_weight > 0 else 0.0


def score_period_profile(value, profile):
    """
    Beispiel:
    ok=8.5, good=10, excellent=12
    """
    if value is None or not profile:
        return 0.0

    ok_v = profile["ok"]
    good_v = profile["good"]
    excellent_v = profile["excellent"]

    if value < ok_v:
        # unterhalb von ok -> schnell abwerten
        if value <= ok_v - 2.0:
            return 0.0
        return max(0.0, ((value - (ok_v - 2.0)) / 2.0) * 45.0)

    if ok_v <= value < good_v:
        # 45 bis 75
        return 45.0 + ((value - ok_v) / (good_v - ok_v)) * 30.0

    if good_v <= value < excellent_v:
        # 75 bis 100
        return 75.0 + ((value - good_v) / (excellent_v - good_v)) * 25.0

    return 100.0


def score_height_profile(value, profile):
    """
    Beispiel:
    ok=0.9, good=1.2, excellent=1.8
    """
    if value is None or not profile:
        return 0.0

    ok_v = profile["ok"]
    good_v = profile["good"]
    excellent_v = profile["excellent"]

    if value < ok_v:
        if value <= ok_v * 0.55:
            return 0.0
        return max(0.0, ((value - ok_v * 0.55) / (ok_v - ok_v * 0.55)) * 45.0)

    if ok_v <= value < good_v:
        return 45.0 + ((value - ok_v) / (good_v - ok_v)) * 30.0

    if good_v <= value < excellent_v:
        return 75.0 + ((value - good_v) / (excellent_v - good_v)) * 25.0

    return 100.0


def compute_windswell_penalty(row, spot):
    cfg = spot.get("windswell_penalty", {})
    if not cfg.get("enabled"):
        return 0.0

    swell_period = row.get("swell_period_used")
    wind_wave_height = row.get("wind_wave_height")
    swell_height = row.get("swell_height_used")

    if swell_period is None:
        return 0.0

    penalty = 0.0

    # kurze Periode
    if swell_period < cfg.get("short_period_below", 8.0):
        penalty += cfg.get("penalty", 10)

    # wenn Windwave die Swellhöhe dominiert, zusätzlich abwerten
    if (
        wind_wave_height is not None
        and swell_height is not None
        and wind_wave_height > swell_height * 0.9
    ):
        penalty += 5.0

    return penalty
# ============================================================
# STATE
# ============================================================
def ensure_history_file():
    if HISTORY_FILE.exists():
        return

    with open(HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "timestamp",
            "spot",
            "score",
            "peak_period",
            "mean_period",
            "wave_period",
            "swell_height",
            "wave_height",
            "windwave_height",
            "wind_speed",
            "wind_direction",
            "gust",
            "confidence",
            "alert_sent"
        ])
        
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sent_alerts": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram-Token oder Chat-ID fehlen.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

# ============================================================
# DATEN LADEN
# ============================================================

def fetch_forecast(spot):
    marine_url = "https://marine-api.open-meteo.com/v1/marine"
    weather_url = "https://api.open-meteo.com/v1/forecast"

    marine_params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "forecast_days": FORECAST_DAYS,
        "timezone": TIMEZONE,
        "hourly": ",".join([
            "wave_height",
            "wave_direction",
            "wave_period",
            "swell_wave_height",
            "swell_wave_direction",
            "swell_wave_period",
            "swell_wave_peak_period",
            "wind_wave_height",
            "wind_wave_direction",
            "wind_wave_period",
            "sea_level_height_msl"
        ])
    }

    weather_params = {
        "latitude": spot["lat"],
        "longitude": spot["lon"],
        "forecast_days": FORECAST_DAYS,
        "timezone": TIMEZONE,
        "wind_speed_unit": "ms",
        "hourly": ",".join([
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "pressure_msl"
        ])
    }

    last_error = None

    for attempt in range(3):
        try:
            marine_resp = requests.get(marine_url, params=marine_params, timeout=45)
            weather_resp = requests.get(weather_url, params=weather_params, timeout=45)

            marine_resp.raise_for_status()
            weather_resp.raise_for_status()

            return {
                "marine": marine_resp.json(),
                "weather": weather_resp.json()
            }

        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"Fehler bei {spot['name']} (Versuch {attempt + 1}/3): {e}")

            if attempt < 2:
                import time
                time.sleep(5)

    raise last_error

# ============================================================
# ROWS BAUEN
# ============================================================

def build_rows(raw):
    marine = raw["marine"]["hourly"]
    weather = raw["weather"]["hourly"]

    times = marine["time"]
    sea_levels = marine.get("sea_level_height_msl", [None] * len(times))
    sea_levels_norm = normalize(sea_levels)

    rows = []

    for i, ts in enumerate(times):
        rows.append({
            "time": ts,
            "dt": parse_dt(ts),

            "wave_height": marine.get("wave_height", [None] * len(times))[i],
            "wave_direction": marine.get("wave_direction", [None] * len(times))[i],
            "wave_period": marine.get("wave_period", [None] * len(times))[i],

            "swell_height": marine.get("swell_wave_height", [None] * len(times))[i],
            "swell_direction": marine.get("swell_wave_direction", [None] * len(times))[i],
            "swell_period": marine.get("swell_wave_period", [None] * len(times))[i],
            "swell_peak_period": marine.get("swell_wave_peak_period", [None] * len(times))[i],

            "wind_wave_height": marine.get("wind_wave_height", [None] * len(times))[i],
            "wind_wave_direction": marine.get("wind_wave_direction", [None] * len(times))[i],
            "wind_wave_period": marine.get("wind_wave_period", [None] * len(times))[i],

            "sea_level": sea_levels[i] if i < len(sea_levels) else None,
            "sea_level_norm": sea_levels_norm[i] if i < len(sea_levels_norm) else None,

            "wind_speed": weather.get("wind_speed_10m", [None] * len(times))[i],
            "wind_direction": weather.get("wind_direction_10m", [None] * len(times))[i],
            "wind_gust": weather.get("wind_gusts_10m", [None] * len(times))[i],
            "pressure": weather.get("pressure_msl", [None] * len(times))[i],
        })

    return rows

# ============================================================
# SCORING
# ============================================================

def score_row(spot, row):
    swell_height = row["swell_height"] if row["swell_height"] is not None else row["wave_height"]
    swell_period = (
        row["swell_peak_period"]
        if row["swell_peak_period"] is not None
        else row["swell_period"] if row["swell_period"] is not None else row["wave_period"]
    )
    swell_direction = row["swell_direction"] if row["swell_direction"] is not None else row["wave_direction"]

    # damit compute_windswell_penalty() auf dieselben Werte zugreifen kann
    row = {
        **row,
        "swell_height_used": swell_height,
        "swell_period_used": swell_period,
        "swell_direction_used": swell_direction
    }

    # ------------------------------------------------------------
    # 1) neue spot-spezifische Komponenten
    # ------------------------------------------------------------
    swell_dir_score = score_profile_direction(
        swell_direction,
        spot.get("swell_primary"),
        spot.get("swell_secondary")
    )

    wind_dir_score = score_profile_direction(
        row["wind_direction"],
        spot.get("wind_offshore"),
        spot.get("wind_cross")
    )

    period_score = score_period_profile(swell_period, spot.get("period_profile"))
    height_score = score_height_profile(swell_height, spot.get("height_profile"))

    wind_speed_score = score_max_threshold(
        row["wind_speed"],
        spot["max_wind_speed"],
        spot["max_wind_speed"] * 2.0
    )

    wind_gust_score = score_max_threshold(
        row["wind_gust"],
        spot["max_wind_gust"],
        spot["max_wind_gust"] * 1.8
    )

    tide_component = 100.0
    if spot.get("use_tide"):
        tide_component = tide_score(row["sea_level_norm"], spot.get("tide_pref", "any"))

    windswell_penalty = compute_windswell_penalty(row, spot)

    # ------------------------------------------------------------
    # 2) Gewichte aus Spot-Profilen ziehen
    # ------------------------------------------------------------
    swell_dir_weight = spot.get("swell_primary", {}).get("weight", 0.22) + spot.get("swell_secondary", {}).get("weight", 0.10)
    wind_dir_weight = spot.get("wind_offshore", {}).get("weight", 0.18) + spot.get("wind_cross", {}).get("weight", 0.08)
    period_weight = spot.get("period_profile", {}).get("weight", 0.22)
    height_weight = spot.get("height_profile", {}).get("weight", 0.10)
    tide_weight = spot.get("tide_weight", 0.0)

    # Restgewichte konservativ
    wind_speed_weight = 0.08
    wind_gust_weight = 0.05

    total_weight = (
        swell_dir_weight
        + wind_dir_weight
        + period_weight
        + height_weight
        + tide_weight
        + wind_speed_weight
        + wind_gust_weight
    )

    # falls tide_weight 0 ist, bleibt es trotzdem sauber normiert
    raw_score = (
        swell_dir_score * swell_dir_weight
        + wind_dir_score * wind_dir_weight
        + period_score * period_weight
        + height_score * height_weight
        + wind_speed_score * wind_speed_weight
        + wind_gust_score * wind_gust_weight
        + tide_component * tide_weight
    ) / total_weight

    final_score = max(0.0, raw_score - windswell_penalty)

    return {
        **row,
        "score": round(final_score, 1),

        "swell_height_used": swell_height,
        "swell_period_used": swell_period,
        "swell_direction_used": swell_direction,

        # Debug / spätere Nachricht
        "component_swell_dir": round(swell_dir_score, 1),
        "component_wind_dir": round(wind_dir_score, 1),
        "component_period": round(period_score, 1),
        "component_height": round(height_score, 1),
        "component_wind_speed": round(wind_speed_score, 1),
        "component_wind_gust": round(wind_gust_score, 1),
        "component_tide": round(tide_component, 1),
        "windswell_penalty": round(windswell_penalty, 1),
    }

# ============================================================
# SESSIONEN BAUEN
# ============================================================

def group_sessions(scored_rows, threshold=ALERT_THRESHOLD, min_hours=SESSION_MIN_HOURS):
    good = [r for r in scored_rows if r["score"] >= threshold]
    good.sort(key=lambda x: x["dt"])

    sessions = []
    current = []

    for row in good:
        if not current:
            current = [row]
            continue

        prev = current[-1]
        diff = row["dt"] - prev["dt"]

        if diff <= timedelta(hours=1, minutes=5):
            current.append(row)
        else:
            if len(current) >= min_hours:
                sessions.append(current)
            current = [row]

    if current and len(current) >= min_hours:
        sessions.append(current)

    return sessions

def summarize_session(spot_name, session):
    start = session[0]["dt"]
    end = session[-1]["dt"]

    avg_score = round(sum(r["score"] for r in session) / len(session), 1)
    max_score = round(max(r["score"] for r in session), 1)

    best_row = max(session, key=lambda r: r["score"])

    swell_heights = [r["swell_height_used"] for r in session if r["swell_height_used"] is not None]
    swell_periods = [r["swell_period_used"] for r in session if r["swell_period_used"] is not None]
    wind_speeds = [r["wind_speed"] for r in session if r["wind_speed"] is not None]
    wind_dirs = [r["wind_direction"] for r in session if r["wind_direction"] is not None]
    swell_dirs = [r["swell_direction_used"] for r in session if r["swell_direction_used"] is not None]

    tide_scores = [r.get("component_tide") for r in session if r.get("component_tide") is not None]
    windswell_penalties = [r.get("windswell_penalty", 0.0) for r in session]

    def fmt_range(values, decimals=1):
        if not values:
            return "n/a"
        lo = round(min(values), decimals)
        hi = round(max(values), decimals)
        if lo == hi:
            return f"{lo}"
        return f"{lo}–{hi}"

    swell_dir = round(best_row["swell_direction_used"]) if best_row["swell_direction_used"] is not None else None
    wind_dir = round(best_row["wind_direction"]) if best_row["wind_direction"] is not None else None

    avg_tide_score = round(sum(tide_scores) / len(tide_scores), 1) if tide_scores else None
    avg_windswell_penalty = round(sum(windswell_penalties) / len(windswell_penalties), 1) if windswell_penalties else 0.0

    return {
        "spot": spot_name,
        "start": start,
        "end": end,
        "avg_score": avg_score,
        "max_score": max_score,
        "hours": len(session),

        "best_time": best_row["dt"],
        "best_score": best_row["score"],

        "swell_height_range": fmt_range(swell_heights),
        "swell_period_range": fmt_range(swell_periods),
        "wind_speed_range": fmt_range(wind_speeds),

        "swell_dir": swell_dir,
        "wind_dir": wind_dir,

        "best_swell_height": best_row["swell_height_used"],
        "best_swell_period": best_row["swell_period_used"],
        "best_swell_dir": best_row["swell_direction_used"],
        "best_wind_speed": best_row["wind_speed"],
        "best_wind_dir": best_row["wind_direction"],

        "swell_dir_compass": deg_to_compass(swell_dir) if swell_dir is not None else "n/a",
        "wind_dir_compass": deg_to_compass(wind_dir) if wind_dir is not None else "n/a",

        "avg_tide_score": avg_tide_score,
        "avg_windswell_penalty": avg_windswell_penalty,
    }

# ============================================================
# LESBARE AUSGABE / INTERPRETATION
# ============================================================

def deg_to_compass(deg):
    if deg is None:
        return "n/a"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round((deg % 360) / 22.5) % 16
    return dirs[idx]

def classify_quality(avg_score):
    if avg_score >= 85:
        return "sehr gut"
    if avg_score >= 75:
        return "gut"
    if avg_score >= 65:
        return "okay"
    return "grenzwertig"


def classify_confidence(avg_score, best_period, windswell_penalty):
    score = 0

    if avg_score >= 82:
        score += 2
    elif avg_score >= 74:
        score += 1

    if best_period is not None:
        if best_period >= 11.5:
            score += 2
        elif best_period >= 9.5:
            score += 1

    if windswell_penalty <= 2:
        score += 2
    elif windswell_penalty <= 7:
        score += 1

    if score >= 5:
        return "hoch"
    if score >= 3:
        return "mittel"
    return "niedrig"


def classify_groundswell(best_period):
    if best_period is None:
        return "unbekannt"
    if best_period >= 12:
        return "hoch"
    if best_period >= 9.5:
        return "mittel"
    return "niedrig"


def classify_windswell_risk(avg_penalty):
    if avg_penalty >= 10:
        return "hoch"
    if avg_penalty >= 4:
        return "mittel"
    return "niedrig"


def classify_tide_fit(avg_tide_score, use_tide):
    if not use_tide:
        return "irrelevant"
    if avg_tide_score is None:
        return "unbekannt"
    if avg_tide_score >= 80:
        return "gut"
    if avg_tide_score >= 55:
        return "okay"
    return "schwach"

def classify_wind_for_spot(spot_name, wind_dir_deg):
    if wind_dir_deg is None:
        return "unbekannt"

    d = wind_dir_deg % 360

    # Klitmøller / Vorupør / Hanstholm:
    # grob offshore bei E bis SE
    if spot_name in ["Klitmøller", "Nørre Vorupør", "Hanstholm"]:
        if 70 <= d <= 150:
            return "offshore"
        if 40 <= d < 70 or 150 < d <= 190:
            return "cross-offshore"
        if 250 <= d <= 330:
            return "onshore"
        return "cross"

    # Norderney:
    # grob gut bei S bis ESE / SE
    if spot_name == "Norderney":
        if 120 <= d <= 210:
            return "offshore"
        if 90 <= d < 120 or 210 < d <= 240:
            return "cross-offshore"
        if d >= 300 or d <= 30:
            return "onshore"
        return "cross"

    # Scheveningen:
    if spot_name == "Scheveningen":
        if 120 <= d <= 220:
            return "offshore"
        if 90 <= d < 120 or 220 < d <= 250:
            return "cross-offshore"
        if d >= 300 or d <= 30:
            return "onshore"
        return "cross"

    # Domburg:
    if spot_name == "Domburg":
        if 130 <= d <= 210:
            return "offshore"
        if 100 <= d < 130 or 210 < d <= 240:
            return "cross-offshore"
        if d >= 320 or d <= 40:
            return "onshore"
        return "cross"

    return "unbekannt"

def build_comment(summary):
    spot = summary["spot"]
    swell_period = summary.get("best_swell_period")
    wind_class = summary.get("wind_class")
    swell_dir = summary.get("best_swell_dir_compass")

    parts = []

    if swell_period is not None:
        if swell_period >= 12:
            parts.append("lange, energiereiche Dünung")
        elif swell_period >= 9:
            parts.append("ordentliche Dünung")
        else:
            parts.append("eher kurzperiodische Dünung")

    if swell_dir:
        parts.append(f"Swell aus {swell_dir}")

    if wind_class == "offshore":
        parts.append("mit Offshore-Wind")
    elif wind_class == "cross-offshore":
        parts.append("mit leicht brauchbarem Cross-Offshore")
    elif wind_class == "cross":
        parts.append("mit eher seitlichem Wind")
    elif wind_class == "onshore":
        parts.append("aber onshore-anfällig")

    if spot in ["Klitmøller", "Nørre Vorupør", "Hanstholm"] and swell_period is not None and swell_period >= 11:
        return "Cold-Hawaii-Setup mit interessanter Periode. " + ", ".join(parts) + "."
    if spot == "Norderney":
        return "Nordsee-Fenster für Norderney. " + ", ".join(parts) + "."
    if spot in ["Scheveningen", "Domburg"]:
        return "Nordsee-/NL-Fenster. " + ", ".join(parts) + "."

    return ", ".join(parts) + "."

# ============================================================
# ALERT TEXT
# ============================================================

def build_message(summary):
    start_str = summary["start"].strftime("%a %d.%m %H:%M")
    end_str = summary["end"].strftime("%a %d.%m %H:%M")
    best_time_str = summary["best_time"].strftime("%a %H:%M")

    quality = classify_quality(summary["avg_score"])
    wind_class = classify_wind_for_spot(summary["spot"], summary["wind_dir"])

    groundswell_factor = classify_groundswell(summary.get("best_swell_period"))
    windswell_risk = classify_windswell_risk(summary.get("avg_windswell_penalty", 0.0))
    confidence = classify_confidence(
        summary["avg_score"],
        summary.get("best_swell_period"),
        summary.get("avg_windswell_penalty", 0.0),
    )

    use_tide = summary["spot"] in ["Norderney", "Scheveningen", "Domburg"]
    tide_fit = classify_tide_fit(summary.get("avg_tide_score"), use_tide)

    summary["wind_class"] = wind_class
    summary["best_swell_dir_compass"] = summary.get("swell_dir_compass")

    comment = build_comment(summary)

    swell_dir_text = (
        f"{summary['swell_dir_compass']} ({summary['swell_dir']}°)"
        if summary["swell_dir"] is not None else "n/a"
    )
    wind_dir_text = (
        f"{summary['wind_dir_compass']} ({summary['wind_dir']}°)"
        if summary["wind_dir"] is not None else "n/a"
    )

    tide_block = ""
    if use_tide:
        tide_block = (
            f"\nTide:\n"
            f"• Tide-Fit: {tide_fit}\n"
        )

    return (
        f"🏄 Surf Alert — {summary['spot']}\n"
        f"Qualität: {quality}\n"
        f"Confidence: {confidence}\n"
        f"Fenster: {start_str} bis {end_str} ({summary['hours']} h)\n"
        f"Beste Stunde: {best_time_str}\n"
        f"Ø Score: {summary['avg_score']} | Peak: {summary['max_score']}\n\n"
        f"Swell:\n"
        f"• {summary['swell_height_range']} m\n"
        f"• {summary['swell_period_range']} s\n"
        f"• {swell_dir_text}\n"
        f"• Groundswell-Faktor: {groundswell_factor}\n\n"
        f"Wind:\n"
        f"• {summary['wind_speed_range']} m/s\n"
        f"• {wind_dir_text}\n"
        f"• {wind_class}\n"
        f"• Windswell-Risiko: {windswell_risk}\n"
        f"{tide_block}\n"
        f"Einschätzung:\n"
        f"{comment}"
    )
# ============================================================
# HAUPTPROGRAMM
# ============================================================

def passes_hard_rules(spot, session, summary):
    rules = spot.get("hard_rules")

    if not rules:
        return True

    # Mindest-Peakperiode
    if summary["best_period"] < rules["min_peak_period"]:
        print(f"❌ {spot['name']}: Peakperiode {summary['best_period']:.1f}s < {rules['min_peak_period']}s")
        return False

    # Mindestdauer
    if summary["hours"] < rules["min_session_hours"]:
        print(f"❌ {spot['name']}: Session nur {summary['hours']}h")
        return False

    # Mindest-Swellhöhe
    swell_heights = [
        r["swell_height_used"]
        for r in session
        if r["swell_height_used"] is not None
    ]

    if swell_heights and max(swell_heights) < rules["min_wave_height"]:
        print(f"❌ {spot['name']}: Swellhöhe zu klein")
        return False

    # Windswell
    if (
        rules["require_groundswell"]
        and summary["avg_windswell_penalty"] >= 8
    ):
        print(f"❌ {spot['name']}: Zu viel Windswell")
        return False

    return True
    def session_id(summary):
    return (
        f"{summary['spot']}|"
        f"{summary['start'].isoformat()}|"
        f"{summary['end'].isoformat()}|"
        f"{summary['max_score']}"
    )


def main():
    print("DEBUG: main() wurde gestartet")
    
    ensure_history_file()
    
    state = load_state()
    already_sent = set(state.get("sent_alerts", []))
    new_sent = list(already_sent)

    all_new_alerts = []

    for spot in SPOTS:
        print(f"Prüfe {spot['name']} ...")

        try:
            raw = fetch_forecast(spot)
            rows = build_rows(raw)
            scored = [score_row(spot, r) for r in rows]
            sessions = group_sessions(scored)

            for sess in sessions:
                summary = summarize_session(spot["name"], sess)

                if not passes_hard_rules(spot, sess, summary):
                    continue

                sid = session_id(summary)

                if sid not in already_sent:
                    msg = build_message(summary)
                    all_new_alerts.append((sid, msg))

        except Exception as e:
            print(f"Spot {spot['name']} konnte nicht verarbeitet werden: {e}")
            continue

    if not all_new_alerts:
        print("Keine neuen Surf-Alerts.")
        return

    for sid, msg in all_new_alerts:
        print("Sende Alert:")
        print(msg)
        send_telegram(msg)
        new_sent.append(sid)

    state["sent_alerts"] = new_sent[-300:]
    save_state(state)

if __name__ == "__main__":
    main()
