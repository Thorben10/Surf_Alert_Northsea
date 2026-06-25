import os
import json
import hashlib
from datetime import datetime, timedelta

import requests

# ============================================================
# KONFIGURATION
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

FORECAST_DAYS = 5
ALERT_THRESHOLD = 20
SESSION_MIN_HOURS = 3
STATE_FILE = "state.json"
TIMEZONE = "Europe/Berlin"

SPOTS = [
    {
        "name": "Klitmøller",
        "lat": 57.044,
        "lon": 8.494,
        "min_swell_height": 1.2,
        "min_swell_period": 11.0,
        "swell_dir_min": 300,
        "swell_dir_max": 350,
        "wind_dir_min": 70,
        "wind_dir_max": 150,
        "max_wind_speed": 11.0,
        "max_wind_gust": 16.0,
        "use_tide": False,
        "tide_pref": "any",
    },
    {
        "name": "Nørre Vorupør",
        "lat": 56.951,
        "lon": 8.375,
        "min_swell_height": 1.2,
        "min_swell_period": 10.5,
        "swell_dir_min": 300,
        "swell_dir_max": 350,
        "wind_dir_min": 70,
        "wind_dir_max": 150,
        "max_wind_speed": 11.0,
        "max_wind_gust": 16.0,
        "use_tide": False,
        "tide_pref": "any",
    },
    {
        "name": "Hanstholm",
        "lat": 57.118,
        "lon": 8.616,
        "min_swell_height": 1.1,
        "min_swell_period": 10.0,
        "swell_dir_min": 300,
        "swell_dir_max": 350,
        "wind_dir_min": 80,
        "wind_dir_max": 160,
        "max_wind_speed": 12.0,
        "max_wind_gust": 17.0,
        "use_tide": False,
        "tide_pref": "any",
    },
    {
        "name": "Norderney",
        "lat": 53.715,
        "lon": 7.159,
        "min_swell_height": 0.8,
        "min_swell_period": 8.0,
        "swell_dir_min": 315,
        "swell_dir_max": 20,
        "wind_dir_min": 120,
        "wind_dir_max": 210,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid_high",
    },
    {
        "name": "Scheveningen",
        "lat": 52.111,
        "lon": 4.273,
        "min_swell_height": 0.9,
        "min_swell_period": 8.5,
        "swell_dir_min": 315,
        "swell_dir_max": 20,
        "wind_dir_min": 120,
        "wind_dir_max": 220,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid",
    },
    {
        "name": "Domburg",
        "lat": 51.563,
        "lon": 3.495,
        "min_swell_height": 0.9,
        "min_swell_period": 8.5,
        "swell_dir_min": 340,
        "swell_dir_max": 40,
        "wind_dir_min": 130,
        "wind_dir_max": 210,
        "max_wind_speed": 10.0,
        "max_wind_gust": 14.0,
        "use_tide": True,
        "tide_pref": "mid_high",
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
# STATE
# ============================================================

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

    s_height = score_min_threshold(swell_height, spot["min_swell_height"], spot["min_swell_height"] * 1.8)
    s_period = score_min_threshold(swell_period, spot["min_swell_period"], spot["min_swell_period"] + 4.0)
    s_swell_dir = score_direction(swell_direction, spot["swell_dir_min"], spot["swell_dir_max"])
    s_wind_dir = score_direction(row["wind_direction"], spot["wind_dir_min"], spot["wind_dir_max"])
    s_wind_speed = score_max_threshold(row["wind_speed"], spot["max_wind_speed"], spot["max_wind_speed"] * 2.0)
    s_wind_gust = score_max_threshold(row["wind_gust"], spot["max_wind_gust"], spot["max_wind_gust"] * 1.8)

    total = (
        s_height * 0.20 +
        s_period * 0.28 +
        s_swell_dir * 0.18 +
        s_wind_dir * 0.16 +
        s_wind_speed * 0.10 +
        s_wind_gust * 0.08
    )

    if spot["use_tide"]:
        s_tide = tide_score(row["sea_level_norm"], spot["tide_pref"])
        total = total * 0.9 + s_tide * 0.1

    return {
        **row,
        "score": round(total, 1),
        "swell_height_used": swell_height,
        "swell_period_used": swell_period,
        "swell_direction_used": swell_direction
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
    }
    
    def fmt_range(values, decimals=1):
        if not values:
            return "n/a"
        lo = round(min(values), decimals)
        hi = round(max(values), decimals)
        if lo == hi:
            return f"{lo}"
        return f"{lo}–{hi}"

    swell_dir = round(swell_dirs[0]) if swell_dirs else "n/a"
    wind_dir = round(wind_dirs[0]) if wind_dirs else "n/a"

    return {
        "spot": spot_name,
        "start": start,
        "end": end,
        "avg_score": avg_score,
        "max_score": max_score,
        "hours": len(session),
        "swell_height_range": fmt_range(swell_heights),
        "swell_period_range": fmt_range(swell_periods),
        "wind_speed_range": fmt_range(wind_speeds),
        "swell_dir": swell_dir,
        "wind_dir": wind_dir,
    }

def session_id(summary):
    raw = f"{summary['spot']}|{summary['start'].isoformat()}|{summary['end'].isoformat()}|{summary['avg_score']}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

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
    if avg_score >= 88:
        return "stark"
    if avg_score >= 80:
        return "sehr gut"
    if avg_score >= 74:
        return "gut"
    if avg_score >= 68:
        return "brauchbar"
    return "mäßig"

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

    return (
        f"🏄 Surf Alert — {summary['spot']}\n"
        f"Qualität: {quality}\n"
        f"Fenster: {start_str} bis {end_str} ({summary['hours']} h)\n"
        f"Beste Stunde: {best_time_str}\n"
        f"Ø Score: {summary['avg_score']} | Peak: {summary['max_score']}\n\n"
        f"Swell:\n"
        f"• {summary['swell_height_range']} m\n"
        f"• {summary['swell_period_range']} s\n"
        f"• {swell_dir_text}\n\n"
        f"Wind:\n"
        f"• {summary['wind_speed_range']} m/s\n"
        f"• {wind_dir_text}\n"
        f"• {wind_class}\n\n"
        f"Einschätzung:\n"
        f"{comment}"
    )

# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main():
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
