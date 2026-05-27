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
        from nyct_gtfs import NYCTFeed
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        import threading

        # 각 feed 대표 라인 — 한 feed당 한 번만 호출
        # '4' = 1234567S, 'A' = ACE, 'N' = NQRW, 'B' = BDFM, 'G', 'J' = JZ, 'L', 'SI'
        feeds_to_check = ['4', 'A', 'N', 'B', 'G', 'J', 'L', 'SI']

        alerts = []
        seen_routes = set()
        lock = threading.Lock()

        def fetch_feed(line):
            results = []
            try:
                feed = NYCTFeed(line)
                for trip in feed.trips:
                    route = trip.route_id
                    if trip.has_delay_alert:
                        delay_sec = 0
                        try:
                            for stu in trip._trip_update.stop_time_update:
                                if stu.HasField('arrival') and stu.arrival.delay > 0:
                                    delay_sec = stu.arrival.delay
                                    break
                                if stu.HasField('departure') and stu.departure.delay > 0:
                                    delay_sec = stu.departure.delay
                                    break
                        except:
                            pass
                        label = f"{route} train  ~{delay_sec // 60} min delay" if delay_sec >= 60 else f"{route} train  delayed"
                        results.append((route, label))
            except:
                pass
            return results

        # 병렬로 모든 feed 동시 호출, 전체 10초 제한
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_feed, line): line for line in feeds_to_check}
            import concurrent.futures
            done, _ = concurrent.futures.wait(futures, timeout=10)
            for f in done:
                for route, label in f.result():
                    if route not in seen_routes and len(alerts) < 4:
                        seen_routes.add(route)
                        alerts.append(label)

        if not alerts:
            return {"good": True, "lines": [], "unavailable": False}
        return {"good": False, "lines": sorted(alerts), "unavailable": False}

    except Exception as e:
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
    # 가용 공간: 560~795 (구분선 800 바로 위까지)
    MTA_TOP   = 560   # 레이블 상단
    MTA_BOT   = 795   # 구분선 직전 최대 y
    CONTENT_Y = 605   # 첫 번째 아이템 dot 시작 y
    DOT_W     = 28
    TEXT_X    = PAD + DOT_W + 18

    draw.text((PAD, MTA_TOP), "MTA SUBWAY", fill=GRAY, font=f_label)

    if mta.get("unavailable"):
        cy = CONTENT_Y
        draw.ellipse([PAD, cy, PAD + DOT_W, cy + DOT_W], fill="#888888")
        draw.text((TEXT_X, cy + DOT_W // 2), "Status unavailable", fill=GRAY, font=f_mta, anchor="lm")
        draw.text((TEXT_X, cy + DOT_W + 10), "Check mta.info for service status", fill=GRAY, font=f_sub, anchor="lm")
    elif mta["good"]:
        cy = CONTENT_Y
        draw.ellipse([PAD, cy, PAD + DOT_W, cy + DOT_W], fill=GREEN)
        draw.text((TEXT_X, cy + DOT_W // 2), "All lines running normally", fill=BLACK, font=f_mta, anchor="lm")
        draw.text((TEXT_X, cy + DOT_W + 10), "mta.info for full schedule", fill=GRAY, font=f_sub, anchor="lm")
    else:
        lines = mta["lines"][:4]  # 최대 4개
        n = len(lines)
        # 가용 높이에서 "mta.info" 줄(60px) 뺀 뒤 균등 배분
        available = MTA_BOT - CONTENT_Y - 60
        row_h = max(44, min(72, available // n))

        cy = CONTENT_Y
        for i, line in enumerate(lines):
            col = RED if i == 0 else YELLOW
            draw.ellipse([PAD, cy, PAD + DOT_W, cy + DOT_W], fill=col)
            # 텍스트가 너무 길면 폰트 크기 줄이기
            txt = line[:45]
            draw.text((TEXT_X, cy + DOT_W // 2), txt, fill=BLACK, font=f_sub, anchor="lm")
            cy += row_h

        # "mta.info" 줄은 항상 마지막 아이템 아래, 구분선 위에
        note_y = min(cy + 4, MTA_BOT - 52)
        draw.text((TEXT_X, note_y), "mta.info for details", fill=GRAY, font=f_sub, anchor="lm")

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
        results = {}
        for line in ["4", "A", "N", "L"]:
            try:
                feed = NYCTFeed(line)
                delayed_trips = []
                for t in feed.trips:
                    if t.has_delay_alert:
                        delay_sec = 0
                        try:
                            for stu in t._trip_update.stop_time_update:
                                if stu.HasField("arrival") and stu.arrival.delay > 0:
                                    delay_sec = stu.arrival.delay
                                    break
                                if stu.HasField("departure") and stu.departure.delay > 0:
                                    delay_sec = stu.departure.delay
                                    break
                        except:
                            pass
                        delayed_trips.append({"route": t.route_id, "delay_sec": delay_sec})
                results[line] = {"total": len(feed.trips), "delayed": delayed_trips[:5]}
            except Exception as e:
                results[line] = {"error": str(e)}
        return jsonify({"ok": True, "results": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/health")
def health():
    return jsonify({"ok": True, "threads_token": bool(THREADS_ACCESS_TOKEN), "ig_token": bool(INSTAGRAM_ACCESS_TOKEN)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
