#!/usr/bin/env python3
"""
Weather Bot - Bitcoin Club Malta Weather & Roatan Weather Bot
Fetches live weather from OpenWeatherMap and posts to X and LinkedIn.
"""
import os
import sys
import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import tweepy
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("weather_bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

MALTA_LAT,  MALTA_LON  = 35.9375,  14.3754
ROATAN_LAT, ROATAN_LON = 16.3194, -86.5355
MALTA_TZ  = ZoneInfo("Europe/Malta")
ROATAN_TZ = ZoneInfo("America/Tegucigalpa")
OWM_KEY = os.getenv("OWM_API_KEY", "")
OWM_BASE = "https://api.openweathermap.org/data/2.5"


def fetch_weather(lat: float, lon: float) -> dict:
    if not OWM_KEY:
        raise ValueError("OWM_API_KEY not set in .env")
    current_url = f"{OWM_BASE}/weather"
    forecast_url = f"{OWM_BASE}/forecast"
    params = {"lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"}
    current_r = requests.get(current_url, params=params, timeout=10)
    current_r.raise_for_status()
    current = current_r.json()
    forecast_r = requests.get(forecast_url, params=params, timeout=10)
    forecast_r.raise_for_status()
    forecast = forecast_r.json()
    today_slots = forecast["list"][:8]
    temps = [s["main"]["temp"] for s in today_slots]
    rain_chances = [s.get("pop", 0) * 100 for s in today_slots]
    return {
        "temp":        round(current["main"]["temp"]),
        "feels_like":  round(current["main"]["feels_like"]),
        "high":        round(max(temps)),
        "low":         round(min(temps)),
        "humidity":    current["main"]["humidity"],
        "wind_speed":  round(current["wind"]["speed"] * 3.6),
        "wind_speed_knots": round(current["wind"]["speed"] * 1.944),
        "wind_dir":    _wind_direction(current["wind"].get("deg", 0)),
        "description": current["weather"][0]["description"].capitalize(),
        "rain_chance": round(max(rain_chances)),
        "clouds":      current["clouds"]["all"],
        "visibility":  round(current.get("visibility", 10000) / 1000, 1),
        "sunrise":     datetime.fromtimestamp(current["sys"]["sunrise"]),
        "sunset":      datetime.fromtimestamp(current["sys"]["sunset"]),
        "raw_current": current,
        "raw_forecast": forecast,
    }


def _wind_direction(deg: float) -> str:
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(deg / 45) % 8]


def _sky_emoji(description: str, clouds: int) -> str:
    desc = description.lower()
    if "thunder" in desc:   return "⛈️"
    if "rain" in desc:      return "U0001f327️"
    if "drizzle" in desc:   return "U0001f326️"
    if "snow" in desc:      return "❄️"
    if "mist" in desc or "fog" in desc: return "U0001f32b️"
    if clouds < 20:         return "☀️"
    if clouds < 60:         return "⛅"
    return "☁️"


def get_x_client(api_key: str, api_secret: str,
                 access_token: str, access_secret: str) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )


def post_to_x(client: tweepy.Client, text: str, dry_run: bool = False) -> bool:
    if dry_run:
        log.info("[DRY RUN] X post (%d chars):\n%s\n", len(text), text)
        return True
    try:
        resp = client.create_tweet(text=text)
        log.info("X post published — tweet ID: %s", resp.data["id"])
        return True
    except tweepy.TweepyException as e:
        log.error("X post failed: %s", e)
        return False


def post_to_linkedin(access_token: str, author_urn: str,
                     text: str, dry_run: bool = False) -> bool:
    if dry_run:
        log.info("[DRY RUN] LinkedIn post (%d chars):\n%s\n", len(text), text)
        return True
    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        log.info("LinkedIn post published — status %s", r.status_code)
        return True
    except requests.HTTPError as e:
        log.error("LinkedIn post failed: %s — %s", e, r.text)
        return False


def format_bcm_daily_x(w: dict) -> str:
    now = datetime.now(MALTA_TZ)
    sky = _sky_emoji(w["description"], w["clouds"])
    return (
        f"{sky} Malta Morning Forecast — {now.strftime('%A, %d %b')}\n"
        f"\n"
        f"{w['description']}. A typical Mediterranean day ahead.\n"
        f"\n"
        f"U0001f321️ High {w['high']}°C / Low {w['low']}°C\n"
        f"U0001f4a8 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
        f"U0001f4a7 Humidity: {w['humidity']}%\n"
        f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
        f"\n"
        f"#MaltaWeather #BitcoinClubMalta U0001f1f2U0001f1f9"
    )


def format_bcm_daily_linkedin(w: dict) -> str:
    now = datetime.now(MALTA_TZ)
    sky = _sky_emoji(w["description"], w["clouds"])
    return (
        f"Good morning, Malta! {sky}\n"
        f"\n"
        f"{w['description']} across the Maltese Islands today. "
        f"Temperatures reaching {w['high']}°C with a low of {w['low']}°C — "
        f"a {'great' if w['rain_chance'] < 30 else 'changeable'} day ahead.\n"
        f"\n"
        f"U0001f4ca Today's stats:\n"
        f"• High: {w['high']}°C  |  Low: {w['low']}°C\n"
        f"• Feels like: {w['feels_like']}°C\n"
        f"• Wind: {w['wind_speed']} km/h from the {w['wind_dir']}\n"
        f"• Humidity: {w['humidity']}%  |  Rain chance: {w['rain_chance']}%\n"
        f"• Visibility: {w['visibility']} km\n"
        f"• Sunrise: {w['sunrise'].strftime('%H:%M')}  |  Sunset: {w['sunset'].strftime('%H:%M')}\n"
        f"\n"
        f"Stay ahead of the forecast U0001f447\n"
        f"#MaltaWeather #BitcoinClubMalta #Malta #MediterraneanWeather"
    )


def format_bcm_weekly_x(w: dict) -> str:
    now = datetime.now(MALTA_TZ)
    return (
        f"U0001f4ca Malta Weekly Weather Wrap — w/e {now.strftime('%d %b')}\n"
        f"\n"
        f"Current conditions: {w['description']}.\n"
        f"\n"
        f"U0001f321️ Today: High {w['high']}°C  |  Low {w['low']}°C\n"
        f"U0001f4a8 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
        f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
        f"\n"
        f"Full week summary in thread below U0001f447\n"
        f"#MaltaWeather #BitcoinClubMalta U0001f1f2U0001f1f9"
    )


def format_roatan_daily_x(w: dict) -> str:
    now = datetime.now(ROATAN_TZ)
    sky = _sky_emoji(w["description"], w["clouds"])
    return (
        f"{sky} Roatan Morning Forecast — {now.strftime('%A, %d %b')}\n"
        f"\n"
        f"{w['description']}. "
        f"{'Grab your fins — great day to dive!' if w['rain_chance'] < 30 else 'Some showers possible — check conditions before diving.'}\n"
        f"\n"
        f"U0001f321️ High {w['high']}°C / Low {w['low']}°C\n"
        f"U0001f4a8 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
        f"U0001f441️ Visibility: ~{w['visibility']} km\n"
        f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
        f"\n"
        f"#RoatanWeather #BayIslands #Honduras U0001f334"
    )


def format_roatan_daily_linkedin(w: dict) -> str:
    now = datetime.now(ROATAN_TZ)
    sky = _sky_emoji(w["description"], w["clouds"])
    dive_conditions = "excellent" if w["rain_chance"] < 20 else "good" if w["rain_chance"] < 50 else "fair"
    return (
        f"Good morning from Roatan! {sky}U0001f30a\n"
        f"\n"
        f"{w['description']} across the Bay Islands today. "
        f"Dive conditions look {dive_conditions} — "
        f"{'blue skies and calm seas ahead!' if w['rain_chance'] < 30 else 'keep an eye on afternoon showers.'}\n"
        f"\n"
        f"U0001f4ca Today's forecast:\n"
        f"• High: {w['high']}°C  |  Low: {w['low']}°C\n"
        f"• Feels like: {w['feels_like']}°C\n"
        f"• Wind: {w['wind_speed_knots']} knots from the {w['wind_dir']}\n"
        f"• Surface visibility: ~{w['visibility']} km\n"
        f"• Rain chance: {w['rain_chance']}%  |  Humidity: {w['humidity']}%\n"
        f"• Sunrise: {w['sunrise'].strftime('%H:%M')}  |  Sunset: {w['sunset'].strftime('%H:%M')}\n"
        f"\n"
        f"Have an incredible day out there! U0001f93fU0001f334\n"
        f"#RoatanWeather #Roatan #BayIslands #ScubaDiving #Honduras"
    )


def format_roatan_weekly_x(w: dict) -> str:
    now = datetime.now(ROATAN_TZ)
    return (
        f"U0001f4ca Roatan Weekly Wrap — w/e {now.strftime('%d %b')}\n"
        f"\n"
        f"Current: {w['description']}.\n"
        f"\n"
        f"U0001f321️ Today: High {w['high']}°C  |  Low {w['low']}°C\n"
        f"U0001f4a8 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
        f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
        f"\n"
        f"Next week preview in thread U0001f447\n"
        f"#RoatanWeather #BayIslands U0001f334"
    )


def format_alert_x(account: str, w: dict, message: str) -> str:
    if account == "bcm":
        return (
            f"U000026a0️ WEATHER ALERT — Malta\n"
            f"\n"
            f"{message}\n"
            f"\n"
            f"U0001f321️ Temp: {w['temp']}°C  |  U0001f4a8 Wind: {w['wind_speed']} km/h {w['wind_dir']}\n"
            f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
            f"\n"
            f"Monitor @MaltaMet for official updates.\n"
            f"#MaltaWeather #WeatherAlert #Malta U0001f1f2U0001f1f9"
        )
    else:
        return (
            f"U000026a0️ WEATHER ALERT — Roatan, Bay Islands\n"
            f"\n"
            f"{message}\n"
            f"\n"
            f"U0001f321️ Temp: {w['temp']}°C  |  U0001f4a8 Wind: {w['wind_speed_knots']} knots {w['wind_dir']}\n"
            f"U0001f327️ Rain chance: {w['rain_chance']}%\n"
            f"\n"
            f"Follow @NOAA_NHC for official tracking. Stay safe! U0001f64f\n"
            f"#RoatanWeather #WeatherAlert #BayIslands"
        )


def run_bcm(post_type: str, alert_message: str, dry_run: bool):
    log.info("=== Bitcoin Club Malta Weather — %s ===", post_type.upper())
    api_key    = os.getenv("BCM_X_API_KEY", "")
    api_secret = os.getenv("BCM_X_API_SECRET", "")
    acc_token  = os.getenv("BCM_X_ACCESS_TOKEN", "")
    acc_secret = os.getenv("BCM_X_ACCESS_SECRET", "")
    li_token   = os.getenv("BCM_LI_ACCESS_TOKEN", "")
    li_urn     = os.getenv("BCM_LI_AUTHOR_URN", "")
    w = fetch_weather(MALTA_LAT, MALTA_LON)
    log.info("Malta weather fetched: %s, %s°C", w["description"], w["temp"])
    if post_type == "daily":
        x_post = format_bcm_daily_x(w)
        li_post = format_bcm_daily_linkedin(w)
    elif post_type == "weekly":
        x_post = format_bcm_weekly_x(w)
        li_post = x_post
    elif post_type == "alert":
        msg = alert_message or "Significant weather change detected. Check conditions."
        x_post = format_alert_x("bcm", w, msg)
        li_post = x_post
    else:
        log.error("Unknown post type: %s", post_type)
        return
    if all([api_key, api_secret, acc_token, acc_secret]):
        x_client = get_x_client(api_key, api_secret, acc_token, acc_secret)
        post_to_x(x_client, x_post, dry_run=dry_run)
    else:
        log.warning("BCM X credentials missing — skipping X post.")
    if all([li_token, li_urn]):
        post_to_linkedin(li_token, li_urn, li_post, dry_run=dry_run)
    else:
        log.warning("BCM LinkedIn credentials missing — skipping LinkedIn post.")


def run_roatan(post_type: str, alert_message: str, dry_run: bool):
    log.info("=== Roatan Weather Bot — %s ===", post_type.upper())
    api_key    = os.getenv("ROA_X_API_KEY", "")
    api_secret = os.getenv("ROA_X_API_SECRET", "")
    acc_token  = os.getenv("ROA_X_ACCESS_TOKEN", "")
    acc_secret = os.getenv("ROA_X_ACCESS_SECRET", "")
    li_token   = os.getenv("ROA_LI_ACCESS_TOKEN", "")
    li_urn     = os.getenv("ROA_LI_AUTHOR_URN", "")
    w = fetch_weather(ROATAN_LAT, ROATAN_LON)
    log.info("Roatan weather fetched: %s, %s°C", w["description"], w["temp"])
    if post_type == "daily":
        x_post = format_roatan_daily_x(w)
        li_post = format_roatan_daily_linkedin(w)
    elif post_type == "weekly":
        x_post = format_roatan_weekly_x(w)
        li_post = x_post
    elif post_type == "alert":
        msg = alert_message or "Significant weather change detected. Check conditions."
        x_post = format_alert_x("roatan", w, msg)
        li_post = x_post
    else:
        log.error("Unknown post type: %s", post_type)
        return
    if all([api_key, api_secret, acc_token, acc_secret]):
        x_client = get_x_client(api_key, api_secret, acc_token, acc_secret)
        post_to_x(x_client, x_post, dry_run=dry_run)
    else:
        log.warning("ROA X credentials missing — skipping X post.")
    if all([li_token, li_urn]):
        post_to_linkedin(li_token, li_urn, li_post, dry_run=dry_run)
    else:
        log.warning("ROA LinkedIn credentials missing — skipping LinkedIn post.")


def main():
    parser = argparse.ArgumentParser(description="Weather bot poster")
    parser.add_argument("--account", choices=["bcm", "roatan", "both"], default="both")
    parser.add_argument("--type", dest="post_type", choices=["daily", "weekly", "alert"], default="daily")
    parser.add_argument("--message", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        log.info("*** DRY RUN MODE — nothing will be published ***")
    if args.account in ("bcm", "both"):
        run_bcm(args.post_type, args.message, args.dry_run)
    if args.account in ("roatan", "both"):
        run_roatan(args.post_type, args.message, args.dry_run)
    log.info("Done.")


if __name__ == "__main__":
    main()
