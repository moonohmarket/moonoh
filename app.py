from flask import Flask, jsonify, request
import requests
from PIL import Image, ImageDraw, ImageFont
import cloudinary
import cloudinary.uploader
import io
import datetime
import os

app = Flask(__name__)

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "duoohunvq"),
    api_key=os.environ.get("CLOUDINARY_API_KEY", "837255854716678"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

THREADS_APP_ID = "1017664257631999"
THREADS_APP_SECRET = os.environ.get("THREADS_APP_SECRET", "51a6843eab6b48acc329b01531e88905")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
INSTAGRAM_PAGE_ID = os.environ.get("INSTAGRAM_PAGE_ID", "17841468166460350")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

def get_weather():
    try:
        r = requests.get("https://wttr.in/New+York?format=j1", timeout=8)
        data = r.json()
        c = data["current_condition"][0]
        code = int(c.get("weatherCode", 113))
        if code == 113: emoji = "☀️"
        elif code in [116, 119]: emoji = "⛅"
        elif code in [122, 143]: emoji = "☁️"
        elif code in [200, 386, 389]: emoji = "⛈️"
        else: emoji = "🌧️"
        return {
            "emoji": emoji,
            "temp": c["temp_F"],
            "feels_like": c["FeelsLikeF"],
            "desc": c["weatherDesc"][0]["value"],
            "humidity": c["humidity"]
        }
    except:
        return {"emoji": "🌤️", "temp": "—", "feels_like": "—", "desc": "See weather.gov", "humidity": "—"}

def get_mta():
    try:
        api_key = _os.environ.get("MTA_API_KEY", "")
        headers = {"x-api-key": api_key} if api_key else {}
        r = requests.get(
            "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alert.json",
            headers=headers,
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            alerts = []
            seen = set()
            for entity in data.get("entity", [])[:50]:
                alert = entity.get("alert", {})
                header = alert.get("header_text", {}).get("translation", [{}])[0].get("text", "")
                for ie in alert.get("informed_entity", []):
                    route = ie.get("route_id", "")
                    if route and route not in seen and len(alerts) < 3:
                        if any(w in header.lower() for w in [
                            "delay", "suspend", "skip", "reroute", "service change",
                            "local", "express", "detour", "no service", "reduced"
                        ]):
                            seen.add(route)
                            alerts.append(f"{route}  {header.split('.')[0][:40]}")
            if not alerts:
                return {"good": True, "lines": [], "unavailable": False}
            return {"good": False, "lines": alerts, "unavailable": False}
        else:
            # API not reachable — be honest
            return {"good": False, "lines": [], "unavailable": True}
    except:
        return {"good": False, "lines": [], "unavailable": True}

def create_image(weather, mta):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    BOLD = _os.path.join(_base, "fonts", "DejaVuSans-Bold.ttf")
    REG  = _os.path.join(_base, "fonts", "DejaVuSans.ttf")

    try:
        f_logo  = ImageFont.truetype(BOLD, 80)
        f_date  = ImageFont.truetype(REG,  44)
        f_label = ImageFont.truetype(BOLD, 36)
        f_temp  = ImageFont.truetype(BOLD, 180)
        f_desc  = ImageFont.truetype(REG,  60)
        f_sub   = ImageFont.truetype(REG,  48)
        f_mta   = ImageFont.truetype(REG,  56)
        f_tag   = ImageFont.truetype(BOLD, 52)
        f_url   = ImageFont.truetype(BOLD, 52)
    except:
        f_logo = f_date = f_label = f_temp = f_desc = f_sub = f_mta = f_tag = f_url = ImageFont.load_default()

    BLACK  = "#111111"
    GRAY   = "#888888"
    LGRAY  = "#E5E5E5"
    ACCENT = "#3A46E2"
    GREEN  = "#22C55E"
    RED    = "#EF4444"
    YELLOW = "#F59E0B"
    PAD    = 64

    # ── HEADER (y: 0–130) ──
    y = 80
    draw.text((PAD, y), "moonoh", fill=ACCENT, font=f_logo, anchor="lm")
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%b %d, %Y")
    draw.text((W - PAD, y), today, fill=GRAY, font=f_date, anchor="rm")
    draw.line([(PAD, 120), (W - PAD, 120)], fill=LGRAY, width=2)

    # ── WEATHER SECTION (y: 140–560) ──
    draw.text((PAD, 150), "NYC WEATHER", fill=GRAY, font=f_label)

    # Big temp
    draw.text((PAD, 175), f"{weather['temp']}°F", fill=BLACK, font=f_temp)

    # Weather desc below temp
    draw.text((PAD, 385), f"{weather['emoji']}  {weather['desc']}", fill=BLACK, font=f_desc)
    draw.text((PAD, 460), f"Feels like {weather['feels_like']}°F  ·  Humidity {weather['humidity']}%", fill=GRAY, font=f_sub)

    draw.line([(PAD, 540), (W - PAD, 540)], fill=LGRAY, width=2)

    # ── MTA SECTION (y: 560–800) ──
    draw.text((PAD, 560), "MTA SUBWAY", fill=GRAY, font=f_label)

    if mta.get("unavailable"):
        dot_y = 625
        draw.ellipse([PAD, dot_y, PAD + 32, dot_y + 32], fill="#888888")
        draw.text((PAD + 50, dot_y + 16), "Status unavailable", fill=GRAY, font=f_mta, anchor="lm")
        draw.text((PAD + 50, dot_y + 84), "Check mta.info for service status", fill=GRAY, font=f_sub, anchor="lm")
    elif mta["good"]:
        dot_y = 625
        draw.ellipse([PAD, dot_y, PAD + 32, dot_y + 32], fill=GREEN)
        draw.text((PAD + 50, dot_y + 16), "All lines running normally", fill=BLACK, font=f_mta, anchor="lm")
        draw.text((PAD + 50, dot_y + 84), "mta.info for full schedule", fill=GRAY, font=f_sub, anchor="lm")
    else:
        y = 625
        for i, line in enumerate(mta["lines"][:2]):
            col = RED if i == 0 else YELLOW
            draw.ellipse([PAD, y, PAD + 32, y + 32], fill=col)
            draw.text((PAD + 50, y + 16), line[:40], fill=BLACK, font=f_sub, anchor="lm")
            y += 90
        draw.text((PAD + 50, y + 8), "mta.info for details", fill=GRAY, font=f_sub, anchor="lm")

    draw.line([(PAD, 800), (W - PAD, 800)], fill=LGRAY, width=2)

    # ── FOOTER (y: 820–1060) ──
    draw.text((PAD, 850), "Buy & Sell with Your NYC", fill=BLACK, font=f_tag)
    draw.text((PAD, 918), "Neighbors on moonoh 🗽", fill=BLACK, font=f_tag)
    draw.text((PAD, 990), "moon-oh.com", fill=ACCENT, font=f_url)
    bb = draw.textbbox((PAD, 990), "moon-oh.com", font=f_url)
    draw.line([(bb[0], bb[3] + 4), (bb[2], bb[3] + 4)], fill=ACCENT, width=3)

    return img

def build_caption(weather, mta):
    if mta.get("unavailable"):
        mta_text = "🚇 MTA status unavailable — check mta.info"
    elif mta["good"]:
        mta_text = "🚇 All subway lines running normally"
    else:
        mta_text = "🚨 MTA Alerts:\n" + "\n".join(f"• {l}" for l in mta["lines"])

    return f"""🌆 Good morning, New York!

{weather['emoji']} {weather['temp']}°F · {weather['desc']} · Feels like {weather['feels_like']}°F

{mta_text}

—

Buy & Sell with Your NYC Neighbors on moonoh 🗽
No fees. List in seconds. Meet your neighbors.

📲 moon-oh.com

#NYC #NewYork #NYCLife #NYCWeather #MTA #moonoh #NYCMarketplace #GoodMorningNYC"""

@app.route("/generate")
def generate():
    weather = get_weather()
    mta = get_mta()
    img = create_image(weather, mta)
    caption = build_caption(weather, mta)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    result = cloudinary.uploader.upload(buf, public_id=f"moonoh_daily_{ts}", overwrite=True, resource_type="image")
    image_url = result["secure_url"]

    return jsonify({"image_url": image_url, "caption": caption, "weather": weather, "mta": mta})

@app.route("/post")
def post_all():
    weather = get_weather()
    mta = get_mta()
    img = create_image(weather, mta)
    caption = build_caption(weather, mta)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    result = cloudinary.uploader.upload(buf, public_id=f"moonoh_daily_{ts}", overwrite=True, resource_type="image")
    image_url = result["secure_url"]

    results = {"image_url": image_url, "caption": caption[:100]}

    ig_token = INSTAGRAM_ACCESS_TOKEN
    if ig_token:
        try:
            r1 = requests.post(f"https://graph.facebook.com/v21.0/{INSTAGRAM_PAGE_ID}/media", data={
                "image_url": image_url, "caption": caption, "access_token": ig_token
            })
            cid = r1.json().get("id")
            if cid:
                r2 = requests.post(f"https://graph.facebook.com/v21.0/{INSTAGRAM_PAGE_ID}/media_publish", data={
                    "creation_id": cid, "access_token": ig_token
                })
                results["instagram"] = {"success": True, "post_id": r2.json().get("id")}
            else:
                results["instagram"] = {"error": r1.json()}
        except Exception as e:
            results["instagram"] = {"error": str(e)}
    else:
        results["instagram"] = {"skipped": "No Instagram token"}

    return jsonify(results)

@app.route("/threads/callback")
def threads_callback():
    code = request.args.get("code")
    if code:
        r = requests.post("https://graph.threads.net/oauth/access_token", data={
            "client_id": THREADS_APP_ID, "client_secret": THREADS_APP_SECRET,
            "code": code, "redirect_uri": "https://web-production-87d57.up.railway.app/threads/callback",
            "grant_type": "authorization_code"
        })
        token_data = r.json()
        short_token = token_data.get("access_token", "")
        if short_token:
            r2 = requests.get("https://graph.threads.net/access_token", params={
                "grant_type": "th_exchange_token", "client_secret": THREADS_APP_SECRET,
                "access_token": short_token
            })
            long_token = r2.json().get("access_token", short_token)
            return jsonify({"success": True, "THREADS_ACCESS_TOKEN": long_token})
        return jsonify({"code": code, "token_response": token_data})
    return jsonify({"message": "No code received"})

@app.route("/threads_post")
def threads_post():
    image_url = request.args.get("image_url", "")
    caption = request.args.get("caption", "")
    token = THREADS_ACCESS_TOKEN

    if not token:
        return jsonify({"error": "No Threads token"})

    if not image_url:
        return jsonify({"error": "No image_url"})

    try:
        # Step 1: Create media container
        r1 = requests.post(
            "https://graph.threads.net/v1.0/me/threads",
            params={
                "media_type": "IMAGE",
                "image_url": image_url,
                "text": caption[:500],
                "access_token": token
            }
        )
        data1 = r1.json()
        container_id = data1.get("id")

        if not container_id:
            return jsonify({"error": "Failed to create container", "detail": data1})

        # Step 2: Publish
        import time
        time.sleep(3)
        r2 = requests.post(
            "https://graph.threads.net/v1.0/me/threads_publish",
            params={
                "creation_id": container_id,
                "access_token": token
            }
        )
        data2 = r2.json()
        return jsonify({"success": True, "thread_id": data2.get("id"), "detail": data2})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/test_mta")
def test_mta():
    try:
        from nyct_gtfs import NYCTFeed
        # 1,2,3,4,5,6,7 feed
        feed = NYCTFeed("1")
        trips = feed.trips
        delayed = []
        for t in trips:
            try:
                if t.underway:
                    delay = getattr(t, "delay", 0) or 0
                    if delay > 180:
                        delayed.append({"route": t.route_id, "delay_min": delay // 60})
            except:
                pass
        return jsonify({"ok": True, "total_trips": len(trips), "delayed": delayed[:10]})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/health")
def health():
    return jsonify({"ok": True, "threads_token": bool(THREADS_ACCESS_TOKEN), "ig_token": bool(INSTAGRAM_ACCESS_TOKEN)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
