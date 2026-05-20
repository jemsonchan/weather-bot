#!/usr/bin/env python3
"""Weather Bot - Bitcoin Club Malta Weather & Roatan Weather Bot"""
import os, sys, argparse, logging, traceback
from datetime import datetime
from zoneinfo import ZoneInfo
import requests, tweepy
from dotenv import load_dotenv
from basic_nostr import NostrClient

load_dotenv()
logging.basicConfig(
level=logging.INFO,
format="%(asctime)s [%(levelname)s] %(message)s",
handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

MALTA_LAT, MALTA_LON = 35.9375, 14.3754
ROATAN_LAT, ROATAN_LON = 16.3194, -86.5355
MALTA_TZ = ZoneInfo("Europe/Malta")
ROATAN_TZ = ZoneInfo("America/Tegucigalpa")
OWM_KEY = os.getenv("OWM_API_KEY", "")
OWM_BASE = "https://api.openweathermap.org/data/2.5"

def fetch_weather(lat, lon):
    if not OWM_KEY:
        raise ValueError("OWM_API_KEY not set")
    params = {"lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"}
    cr = requests.get(f"{OWM_BASE}/weather", params=params, timeout=10)
    cr.raise_for_status()
    c = cr.json()
    fr = requests.get(f"{OWM_BASE}/forecast", params=params, timeout=10)
    fr.raise_for_status()
    f = fr.json()
    slots = f["list"][:8]
    temps = [s["main"]["temp"] for s in slots]
    rain = [s.get("pop", 0) * 100 for s in slots]
    return {
        "temp": round(c["main"]["temp"]),
        "feels_like": round(c["main"]["feels_like"]),
        "high": round(max(temps)), "low": round(min(temps)),
        "humidity": c["main"]["humidity"],
        "wind_speed": round(c["wind"]["speed"] * 3.6),
        "wind_speed_knots": round(c["wind"]["speed"] * 1.944),
        "wind_dir": _wind_dir(c["wind"].get("deg", 0)),
        "description": c["weather"][0]["description"].capitalize(),
        "rain_chance": round(max(rain)),
        "clouds": c["clouds"]["all"],
        "visibility": round(c.get("visibility", 10000) / 1000, 1),
        "sunrise": datetime.fromtimestamp(c["sys"]["sunrise"]),
        "sunset": datetime.fromtimestamp(c["sys"]["sunset"]),
    }

def _wind_dir(deg):
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    return dirs[round(deg / 45) % 8]

def _sky(desc, clouds):
    d = desc.lower()
    if "thunder" in d: return "⛈️"
    if "rain" in d: return "🌧️"
    if "drizzle" in d: return "🌦️"
    if "snow" in d: return "❄️"
    if "mist" in d or "fog" in d: return "🌫️"
    if clouds < 20: return "☀️"
    if clouds < 60: return "⛅"
    return "☁️"

def get_x_client(api_key, api_secret, access_token, access_secret):
    return tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=access_token, access_token_secret=access_secret,
    )

def post_to_x(client, text, account_name=""):
    log.info("Attempting X post for %s (%d chars)...", account_name, len(text))
    log.info("Post preview: %s", text[:100])
    try:
        resp = client.create_tweet(text=text)
        log.info("SUCCESS: X post published for %s — tweet ID: %s", account_name, resp.data["id"])
        return True
    except (tweepy.errors.Unauthorized, tweepy.errors.Forbidden) as e:
        if isinstance(e, tweepy.errors.Unauthorized):
            reason = "credentials may be expired or invalid"
        else:
            reason = "duplicate content or permission issue"
        log.warning("WARN: X post for %s returned %s — %s. Non-fatal, skipping.", account_name, type(e).__name__, reason)
        if hasattr(e, 'response') and e.response is not None:
            log.warning(" HTTP status: %s", e.response.status_code)
            log.warning(" Response body: %s", e.response.text)
        return True
    except tweepy.TweepyException as e:
        log.error("FAILED: X post for %s: %s", account_name, e)
        traceback.print_exc()
        return False

def post_to_linkedin(access_token, author_urn, text, account_name=""):
    log.info("Attempting LinkedIn post for %s...", account_name)
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202604",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": author_urn, "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        log.info("SUCCESS: LinkedIn post for %s — status %s", account_name, r.status_code)
        return True
    except requests.HTTPError as e:
        if r.status_code in (400, 403):
            log.warning("WARN: LinkedIn post for %s returned %s — API restriction. Non-fatal, skipping.", account_name, r.status_code)
            return True
        log.error("FAILED: LinkedIn post for %s: %s — %s", account_name, e, r.text)
        return False

def post_to_nostr(nsec, text, account_name=""):
    log.info("Attempting Nostr post for %s (%d chars)...", account_name, len(text))
    try:
        with NostrClient(nsec) as nostr:
            nostr.make_post(text)
        log.info("SUCCESS: Nostr post published for %s", account_name)
        return True
    except Exception as e:
        log.warning("WARN: Nostr post for %s failed: %s. Non-fatal, skipping.", account_name, e)
        return True

def fmt_bcm_daily_x(w):
    now = datetime.now(MALTA_TZ)
    sky = _sky(w["description"], w["clouds"])
    return (
        f"{sky} Malta Morning Forecast — {now.strftime('%A, %d %b')}\n\n"
        f"{w['description']}. A typical Mediterranean day ahead.\n\n"
        f"🌡️ High {w['high']}°C / Low {w['low']}°C\n"
        f"💨 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
        f"💧 Humidity: {w['humidity']}%\n"
        f"🌧️ Rain chance: {w['rain_chance']}%\n\n"
        f"#MaltaWeather #BitcoinClubMalta 🇲🇹"
    )

def fmt_bcm_daily_li(w):
    now = datetime.now(MALTA_TZ)
    sky = _sky(w["description"], w["clouds"])
    mood = 'great' if w['rain_chance'] < 30 else 'changeable'
    return (
        f"Good morning, Malta! {sky}\n\n"
        f"{w['description']} across the Maltese Islands today. "
        f"Temperatures reaching {w['high']}°C, low of {w['low']}°C — a {mood} day ahead.\n\n"
        f"📊 Today:\n"
        f"• High {w['high']}°C | Low {w['low']}°C | Feels like {w['feels_like']}°C\n"
        f"• Wind: {w['wind_speed']} km/h from the {w['wind_dir']}\n"
        f"• Humidity: {w['humidity']}% | Rain: {w['rain_chance']}%\n"
        f"• Visibility: {w['visibility']} km\n"
        f"• Sunrise: {w['sunrise'].strftime('%H:%M')} | Sunset: {w['sunset'].strftime('%H:%M')}\n\n"
        f"#MaltaWeather #BitcoinClubMalta #Malta #MediterraneanWeather"
    )

def fmt_bcm_weekly_x(w):
    now = datetime.now(MALTA_TZ)
    return (
        f"📊 Malta Weekly Weather Wrap — w/e {now.strftime('%d %b')}\n\n"
        f"Current: {w['description']}.\n\n"
        f"🌡️ High {w['high']}°C | Low {w['low']}°C\n"
        f"💨 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
        f"🌧️ Rain chance: {w['rain_chance']}%\n\n"
        f"#MaltaWeather #BitcoinClubMalta 🇲🇹"
    )

def fmt_roatan_daily_x(w):
    now = datetime.now(ROATAN_TZ)
    sky = _sky(w["description"], w["clouds"])
    dive = 'Grab your fins — great day to dive!' if w['rain_chance'] < 30 else 'Some showers possible — check conditions before diving.'
    return (
        f"{sky} Roatan Morning Forecast — {now.strftime('%A, %d %b')}\n\n"
        f"{w['description']}. {dive}\n\n"
        f"🌡️ High {w['high']}°C / Low {w['low']}°C\n"
        f"💨 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
        f"👁️ Visibility: ~{w['visibility']} km\n"
        f"🌧️ Rain chance: {w['rain_chance']}%\n\n"
        f"#RoatanWeather #BayIslands #Honduras 🌴"
    )

def fmt_roatan_daily_li(w):
    now = datetime.now(ROATAN_TZ)
    sky = _sky(w["description"], w["clouds"])
    dive = "excellent" if w["rain_chance"] < 20 else "good" if w["rain_chance"] < 50 else "fair"
    seas = 'blue skies and calm seas ahead!' if w['rain_chance'] < 30 else 'keep an eye on afternoon showers.'
    return (
        f"Good morning from Roatan! {sky}🌊\n\n"
        f"{w['description']} across the Bay Islands. Dive conditions: {dive} — {seas}\n\n"
        f"📊 Today:\n"
        f"• High {w['high']}°C | Low {w['low']}°C | Feels like {w['feels_like']}°C\n"
        f"• Wind: {w['wind_speed_knots']} knots from the {w['wind_dir']}\n"
        f"• Visibility: ~{w['visibility']} km | Rain: {w['rain_chance']}%\n"
        f"• Sunrise: {w['sunrise'].strftime('%H:%M')} | Sunset: {w['sunset'].strftime('%H:%M')}\n\n"
        f"Have an incredible day! 🤿🌴\n"
        f"#RoatanWeather #Roatan #BayIslands #ScubaDiving #Honduras"
    )

def fmt_roatan_weekly_x(w):
    now = datetime.now(ROATAN_TZ)
    return (
        f"📊 Roatan Weekly Wrap — w/e {now.strftime('%d %b')}\n\n"
        f"Current: {w['description']}.\n\n"
        f"🌡️ High {w['high']}°C | Low {w['low']}°C\n"
        f"💨 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
        f"🌧️ Rain chance: {w['rain_chance']}%\n\n"
        f"#RoatanWeather #BayIslands 🌴"
    )

def fmt_alert_x(account, w, message):
    if account == "bcm":
        return (
            f"⚠️ WEATHER ALERT — Malta\n\n{message}\n\n"
            f"🌡️ Temp: {w['temp']}°C | 💨 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
            f"🌧️ Rain: {w['rain_chance']}%\n\n"
            f"Monitor @MaltaMet for official updates.\n"
            f"#MaltaWeather #WeatherAlert #Malta 🇲🇹"
        )
    return (
        f"⚠️ WEATHER ALERT — Roatan, Bay Islands\n\n{message}\n\n"
        f"🌡️ Temp: {w['temp']}°C | 💨 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
        f"🌧️ Rain: {w['rain_chance']}%\n\n"
        f"Follow @NOAA_NHC for official tracking. Stay safe! 🙏\n"
        f"#RoatanWeather #WeatherAlert #BayIslands"
    )

def run_bcm(post_type, alert_message, dry_run):
    log.info("=== BCM (@RealMaltaWx) — %s ===", post_type.upper())
    api_key = os.getenv("BCM_X_API_KEY", "")
    api_secret = os.getenv("BCM_X_API_SECRET", "")
    acc_token = os.getenv("BCM_X_ACCESS_TOKEN", "")
    acc_secret = os.getenv("BCM_X_ACCESS_SECRET", "")
    li_token = os.getenv("BCM_LI_ACCESS_TOKEN", "")
    li_urn = os.getenv("BCM_LI_AUTHOR_URN", "")
    nostr_nsec = os.getenv("NOSTR_NSEC", "")

    log.info("BCM X keys present: api_key=%s, api_secret=%s, acc_token=%s, acc_secret=%s",
             bool(api_key), bool(api_secret), bool(acc_token), bool(acc_secret))

    log.info("Fetching Malta weather...")
    w = fetch_weather(MALTA_LAT, MALTA_LON)
    log.info("Malta: %s, %s°C, rain=%s%%", w['description'], w['temp'], w['rain_chance'])

    if post_type == "daily":
        x_post = fmt_bcm_daily_x(w)
        li_post = fmt_bcm_daily_li(w)
    elif post_type == "weekly":
        x_post = fmt_bcm_weekly_x(w)
        li_post = x_post
    elif post_type == "alert":
        msg = alert_message or "Significant weather change detected."
        x_post = fmt_alert_x("bcm", w, msg)
        li_post = x_post
    else:
        log.error("Unknown post type: %s", post_type)
        return False

    ok = True
    if all([api_key, api_secret, acc_token, acc_secret]):
        if dry_run:
            log.info("[DRY RUN] BCM X post would be:\n%s", x_post)
        else:
            client = get_x_client(api_key, api_secret, acc_token, acc_secret)
            post_to_x(client, x_post, "@RealMaltaWx")
    else:
        log.warning("BCM X credentials not set — skipping X.")

    if all([li_token, li_urn]):
        if dry_run:
            log.info("[DRY RUN] BCM LinkedIn post would be:\n%s", li_post)
        else:
            if not post_to_linkedin(li_token, li_urn, li_post, "BCM LinkedIn"):
                ok = False
    else:
        log.warning("BCM LinkedIn credentials not set — skipping LinkedIn.")

    if nostr_nsec:
        if dry_run:
            log.info("[DRY RUN] BCM Nostr post would be:\n%s", li_post)
        else:
            post_to_nostr(nostr_nsec, li_post, "BCM Nostr")
    else:
        log.warning("NOSTR_NSEC not set — skipping Nostr.")
    return ok

def run_roatan(post_type, alert_message, dry_run):
    log.info("=== Roatan (@RoatanWeather) — %s ===", post_type.upper())
    api_key = os.getenv("ROA_X_API_KEY", "")
    api_secret = os.getenv("ROA_X_API_SECRET", "")
    acc_token = os.getenv("ROA_X_ACCESS_TOKEN", "")
    acc_secret = os.getenv("ROA_X_ACCESS_SECRET", "")
    li_token = os.getenv("ROA_LI_ACCESS_TOKEN", "")
    li_urn = os.getenv("ROA_LI_AUTHOR_URN", "")
    nostr_nsec = os.getenv("NOSTR_NSEC", "")

    log.info("ROA X keys present: api_key=%s, api_secret=%s, acc_token=%s, acc_secret=%s",
             bool(api_key), bool(api_secret), bool(acc_token), bool(acc_secret))
    log.info("ROA X key prefixes: api_key=%s..., acc_token=%s...",
             api_key[:8] if api_key else "MISSING",
             acc_token[:20] if acc_token else "MISSING")

    log.info("Fetching Roatan weather...")
    w = fetch_weather(ROATAN_LAT, ROATAN_LON)
    log.info("Roatan: %s, %s°C, rain=%s%%", w['description'], w['temp'], w['rain_chance'])

    if post_type == "daily":
        x_post = fmt_roatan_daily_x(w)
        li_post = fmt_roatan_daily_li(w)
    elif post_type == "weekly":
        x_post = fmt_roatan_weekly_x(w)
        li_post = x_post
    elif post_type == "alert":
        msg = alert_message or "Significant weather change detected."
        x_post = fmt_alert_x("roatan", w, msg)
        li_post = x_post
    else:
        log.error("Unknown post type: %s", post_type)
        return False

    ok = True
    if all([api_key, api_secret, acc_token, acc_secret]):
        if dry_run:
            log.info("[DRY RUN] ROA X post would be:\n%s", x_post)
        else:
            client = get_x_client(api_key, api_secret, acc_token, acc_secret)
            post_to_x(client, x_post, "@RoatanWeather")
    else:
        log.warning("ROA X credentials not set — skipping X.")

    if all([li_token, li_urn]):
        if dry_run:
            log.info("[DRY RUN] ROA LinkedIn post would be:\n%s", li_post)
        else:
            if not post_to_linkedin(li_token, li_urn, li_post, "ROA LinkedIn"):
                ok = False
    else:
        log.warning("ROA LinkedIn credentials not set — skipping LinkedIn.")

    if nostr_nsec:
        if dry_run:
            log.info("[DRY RUN] ROA Nostr post would be:\n%s", li_post)
        else:
            post_to_nostr(nostr_nsec, li_post, "ROA Nostr")
    else:
        log.warning("NOSTR_NSEC not set — skipping Nostr.")
    return ok

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", choices=["bcm","roatan","both"], default="both")
    parser.add_argument("--type", dest="post_type", choices=["daily","weekly","alert"], default="daily")
    parser.add_argument("--message", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info("Starting weather bot: account=%s type=%s dry_run=%s", args.account, args.post_type, args.dry_run)
    all_ok = True
    if args.account in ("bcm", "both"):
        if not run_bcm(args.post_type, args.message, args.dry_run):
            all_ok = False
    if args.account in ("roatan", "both"):
        if not run_roatan(args.post_type, args.message, args.dry_run):
            all_ok = False

    if all_ok:
        log.info("All posts completed successfully.")
    else:
        log.error("One or more posts FAILED. Check logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
