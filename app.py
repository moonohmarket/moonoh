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
        r = requests.get(
            "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alert.json",
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            alerts = []
            seen = set()
            for entity in data.get("entity", [])[:30]:
                alert = entity.get("alert", {})
                header = alert.get("header_text", {}).get("translation", [{}])[0].get("text", "")
                for ie in alert.get("informed_entity", []):
                    route = ie.get("route_id", "")
                    if route and route not in seen and len(alerts) < 3:
                        if any(w in header.lower() for w in ["delay", "suspend", "skip", "reroute", "service change"]):
                            seen.add(route)
                            alerts.append(f"{route}  {header.split('.')[0][:40]}")
            if not alerts:
                return {"good": True, "lines": []}
            return {"good": False, "lines": alerts}
    except:
        pass
    return {"good": True, "lines": []}

def create_image(weather, mta):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    try:
        f_logo  = ImageFont.truetype(BOLD, 52)
        f_date  = ImageFont.truetype(REG, 26)
        f_label = ImageFont.truetype(REG, 20)
        f_temp  = ImageFont.truetype(BOLD, 120)
        f_desc  = ImageFont.truetype(REG, 36)
        f_sub   = ImageFont.truetype(REG, 28)
        f_mta   = ImageFont.truetype(REG, 34)
        f_tag   = ImageFont.truetype(BOLD, 38)
        f_url   = ImageFont.truetype(BOLD, 36)
    except:
        f_logo = f_date = f_label = f_temp = f_desc = f_sub = f_mta = f_tag = f_url = ImageFont.load_default()

    BLACK  = "#111111"
    GRAY   = "#999999"
    LGRAY  = "#EBEBEB"
    ACCENT = "#3A46E2"
    GREEN  = "#22C55E"
    RED    = "#EF4444"
    YELLOW = "#F59E0B"
    PAD    = 72

    draw.text((PAD, 90), "moonoh", fill=ACCENT, font=f_logo, anchor="lm")
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%b %d, %Y")
    draw.text((W - PAD, 90), today, fill=GRAY, font=f_date, anchor="rm")
    draw.line([(PAD, 130), (W - PAD, 130)], fill=LGRAY, width=1)

    draw.text((PAD, 162), "NYC WEATHER", fill=GRAY, font=f_label)
    draw.text((PAD, 175), f"{weather['temp']}°F", fill=BLACK, font=f_temp)
    draw.text((PAD + 390, 225), f"{weather['emoji']}  {weather['desc']}", fill=BLACK, font=f_desc, anchor="lm")
    draw.text((PAD + 390, 275), f"Feels like {weather['feels_like']}°F  ·  Humidity {weather['humidity']}%", fill=GRAY, font=f_sub, anchor="lm")
    draw.line([(PAD, 370), (W - PAD, 370)], fill=LGRAY, width=1)

    draw.text((PAD, 395), "MTA SUBWAY", fill=GRAY, font=f_label)

    if mta["good"]:
        draw.ellipse([PAD, 428, PAD + 18, 446], fill=GREEN)
        draw.text((PAD + 30, 437), "All lines running normally", fill=BLACK, font=f_mta, anchor="lm")
        draw.text((PAD + 30, 482), "Check mta.info for details", fill=GRAY, font=f_sub, anchor="lm")
    else:
        y = 428
        for i, line in enumerate(mta["lines"][:3]):
            col = RED if i == 0 else YELLOW
            draw.ellipse([PAD, y, PAD + 18, y + 18], fill=col)
            draw.text((PAD + 30, y + 9), line[:52], fill=BLACK, font=f_sub, anchor="lm")
            y += 46
        draw.text((PAD + 30, y + 8), "Check mta.info for details", fill=GRAY, font=f_sub, anchor="lm")

    draw.line([(PAD, 555), (W - PAD, 555)], fill=LGRAY, width=1)

    draw.text((PAD, 600), "Buy & Sell with Your NYC Neighbors on moonoh", fill=BLACK, font=f_tag)
    draw.text((PAD, 665), "moon-oh.com", fill=ACCENT, font=f_url)
    bb = draw.textbbox((PAD, 665), "moon-oh.com", font=f_url)
    draw.line([(bb[0], bb[3] + 3), (bb[2], bb[3] + 3)], fill=ACCENT, width=2)

    return img

def build_caption(weather, mta):
    if mta["good"]:
        mta_text = "🚇 All subway lines running normally"
    else:
        mta_text = "🚨 MTA Delays:\n" + "\n".join(f"• {l}" for l in mta["lines"])

    return f"""🌆 Good morning, New York!

{weather['emoji']} {weather['temp']}°F · {weather['desc']} · Feels like {weather['feels_like']}°F

{mta_text}

—

Buy & Sell with Your NYC Neighbors on moonoh 🗽
No fees. List in seconds. Meet your neighbors.

📲 moon-oh.com

#NYC #NewYork #NYCLife #NYCWeather #MTA #moonoh #NYCMarketplace #GoodMorningNYC"""

def post_to_threads(image_url, caption, access_token):
    try:
        # Get user ID
        me = requests.get(f"https://graph.threads.net/v1.0/me?access_token={access_token}").json()
        user_id = me.get("id")
        if not user_id:
            return {"error": "No user ID", "detail": me}

        # Create container
        r1 = requests.post(f"https://graph.threads.net/v1.0/{user_id}/threads", data={
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
            "access_token": access_token
        })
        container_id = r1.json().get("id")
        if not container_id:
            return {"error": "No container", "detail": r1.json()}

        import time; time.sleep(3)

        # Publish
        r2 = requests.post(f"https://graph.threads.net/v1.0/{user_id}/threads_publish", data={
            "creation_id": container_id,
            "access_token": access_token
        })
        return {"success": True, "post_id": r2.json().get("id"), "detail": r2.json()}
    except Exception as e:
        return {"error": str(e)}

def post_to_instagram(image_url, caption, page_id, access_token):
    try:
        # Create container
        r1 = requests.post(f"https://graph.facebook.com/v21.0/{page_id}/media", data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token
        })
        container_id = r1.json().get("id")
        if not container_id:
            return {"error": "No container", "detail": r1.json()}

        # Publish
        r2 = requests.post(f"https://graph.facebook.com/v21.0/{page_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": access_token
        })
        return {"success": True, "post_id": r2.json().get("id"), "detail": r2.json()}
    except Exception as e:
        return {"error": str(e)}

@app.route("/generate")
def generate():
    weather = get_weather()
    mta = get_mta()
    img = create_image(weather, mta)
    caption = build_caption(weather, mta)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    result = cloudinary.uploader.upload(buf, public_id=f"moonoh_daily_{today_str}", overwrite=True, resource_type="image")
    image_url = result["secure_url"]

    return jsonify({"image_url": image_url, "caption": caption, "weather": weather, "mta": mta})

@app.route("/post")
def post_all():
    """Generate image and post to both Instagram and Threads"""
    weather = get_weather()
    mta = get_mta()
    img = create_image(weather, mta)
    caption = build_caption(weather, mta)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    result = cloudinary.uploader.upload(buf, public_id=f"moonoh_daily_{today_str}", overwrite=True, resource_type="image")
    image_url = result["secure_url"]

    results = {"image_url": image_url, "caption": caption[:100]}

    # Post to Instagram
    ig_token = INSTAGRAM_ACCESS_TOKEN
    if ig_token:
        ig_result = post_to_instagram(image_url, caption, INSTAGRAM_PAGE_ID, ig_token)
        results["instagram"] = ig_result
    else:
        results["instagram"] = {"skipped": "No Instagram token"}

    # Post to Threads
    th_token = THREADS_ACCESS_TOKEN
    if th_token:
        th_result = post_to_threads(image_url, caption, th_token)
        results["threads"] = th_result
    else:
        results["threads"] = {"skipped": "No Threads token"}

    return jsonify(results)

@app.route("/threads/callback")
def threads_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return jsonify({"error": error})
    if code:
        # Auto-exchange for token
        r = requests.post("https://graph.threads.net/oauth/access_token", data={
            "client_id": THREADS_APP_ID,
            "client_secret": THREADS_APP_SECRET,
            "code": code,
            "redirect_uri": "https://web-production-87d57.up.railway.app/threads/callback",
            "grant_type": "authorization_code"
        })
        token_data = r.json()
        short_token = token_data.get("access_token", "")

        if short_token:
            # Exchange for long-lived token
            r2 = requests.get(f"https://graph.threads.net/access_token", params={
                "grant_type": "th_exchange_token",
                "client_secret": THREADS_APP_SECRET,
                "access_token": short_token
            })
            long_data = r2.json()
            long_token = long_data.get("access_token", short_token)
            return jsonify({
                "success": True,
                "THREADS_ACCESS_TOKEN": long_token,
                "message": "Copy THREADS_ACCESS_TOKEN to Railway Variables!"
            })
        return jsonify({"code": code, "token_response": token_data})
    return jsonify({"message": "No code received"})

@app.route("/health")
def health():
    return jsonify({"ok": True, "threads_token": bool(THREADS_ACCESS_TOKEN), "ig_token": bool(INSTAGRAM_ACCESS_TOKEN)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
