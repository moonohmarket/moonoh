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
        from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
        import threading

        feeds_to_check = ['4', 'A', 'N', 'B', 'G', 'J', 'L', 'SI']
        results = {}
        lock = threading.Lock()

        def fetch_feed(line):
            delayed = {}  # route_id -> max delay_sec
            try:
                feed = NYCTFeed(line)
                for trip in feed.trips:
                    route = trip.route_id
                    # raw protobuf에서 직접 delay 초 읽기
                    try:
                        for stu in trip._trip_update.stop_time_update:
                            d = 0
                            if stu.HasField('arrival') and stu.arrival.delay > d:
                                d = stu.arrival.delay
                            if stu.HasField('departure') and stu.departure.delay > d:
                                d = stu.departure.delay
                            if d > 0:
                                # 라인별 최대 delay 추적
                                if route not in delayed or delayed[route] < d:
                                    delayed[route] = d
                                break  # 첫 번째 stop에서 delay 확인되면 충분
                    except:
                        pass
            except:
                pass
            return delayed

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_feed, line): line for line in feeds_to_check}
            done, _ = futures_wait(futures, timeout=12)
            for f in done:
                try:
                    results.update(f.result())
                except:
                    pass

        # 180초(3분) 이상 delay만 표시
        alerts = []
        for route, delay_sec in sorted(results.items()):
            if delay_sec >= 180:
                mins = delay_sec // 60
                alerts.append(f"{route} train  ~{mins} min delay")

        if not alerts:
            return {"good": True, "lines": [], "unavailable": False}
        return {"good": False, "lines": alerts[:4], "unavailable": False}

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
    MTA_TOP = 560
    MTA_BOT = 792   # 구분선(800) 8px 위까지
    DOT_W   = 26
    TEXT_X  = PAD + DOT_W + 16
    LINE_GAP = 10   # 텍스트 줄 간 최소 여백

    # 레이블 그리기
    draw.text((PAD, MTA_TOP), "MTA SUBWAY", fill=GRAY, font=f_label)
    lbl_bb = draw.textbbox((PAD, MTA_TOP), "MTA SUBWAY", font=f_label)
    content_y = lbl_bb[3] + 18  # 레이블 하단 + 18px 여백

    def draw_row(cy, dot_color, main_text, main_font, sub_text=None, sub_font=None):
        """Draw dot + main text + sub text. Returns next y."""
        # dot은 메인텍스트 중앙에 맞춤
        main_bb = draw.textbbox((TEXT_X, cy), main_text, font=main_font)
        main_h = main_bb[3] - main_bb[1]
        dot_y = cy + (main_h - DOT_W) // 2
        draw.ellipse([PAD, dot_y, PAD + DOT_W, dot_y + DOT_W], fill=dot_color)
        draw.text((TEXT_X, cy), main_text, fill=BLACK, font=main_font)
        next_y = main_bb[3] + LINE_GAP
        if sub_text and sub_font:
            draw.text((TEXT_X, next_y), sub_text, fill=GRAY, font=sub_font)
            sub_bb = draw.textbbox((TEXT_X, next_y), sub_text, font=sub_font)
            next_y = sub_bb[3] + LINE_GAP
        return next_y

    if mta.get("unavailable"):
        draw_row(content_y, "#888888", "Status unavailable", f_mta,
                 "Check mta.info for service status", f_sub)
    elif mta["good"]:
        draw_row(content_y, GREEN, "All lines running normally", f_mta,
                 "mta.info for full schedule", f_sub)
    else:
        lines = mta["lines"][:4]
        n = len(lines)

        # 각 아이템이 차지할 높이 미리 계산해서 MTA_BOT 안에 맞는지 확인
        # f_sub 48px 기준 한 줄 ~56px + LINE_GAP
        row_h_est = 56 + LINE_GAP
        note_h = 56  # "mta.info for details" 줄
        total_est = content_y + n * row_h_est + LINE_GAP + note_h

        # 공간 초과하면 폰트 축소
        if total_est > MTA_BOT:
            # 비율에 맞게 폰트 크기 줄이기
            available_per_row = max(36, (MTA_BOT - content_y - note_h - LINE_GAP) // n - LINE_GAP)
            try:
                _base = os.path.dirname(os.path.abspath(__file__))
                f_row = ImageFont.truetype(os.path.join(_base, "fonts", "DejaVuSans.ttf"), available_per_row)
            except:
                f_row = f_sub
        else:
            f_row = f_sub

        cy = content_y
        for i, line in enumerate(lines):
            col = RED if i == 0 else YELLOW
            dot_y = cy + (available_per_row if total_est > MTA_BOT else 48 - DOT_W) // 2
            draw.ellipse([PAD, cy, PAD + DOT_W, cy + DOT_W], fill=col)
            draw.text((TEXT_X, cy), line[:45], fill=BLACK, font=f_row)
            bb = draw.textbbox((TEXT_X, cy), line[:45], font=f_row)
            cy = bb[3] + LINE_GAP

        # "mta.info" 줄 — 항상 구분선 위에
        note_y = min(cy + 4, MTA_BOT - 52)
        draw.text((TEXT_X, note_y), "mta.info for details", fill=GRAY, font=f_sub)

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

@app.route("/test_craigslist")
def test_craigslist():
    try:
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        results = {}

        # 1. RSS feed 시도
        r = requests.get('https://newyork.craigslist.org/search/sss?format=rss&sort=date', headers=headers, timeout=10)
        results['rss_status'] = r.status_code
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'xml')
            items = soup.find_all('item')[:5]
            results['rss_items'] = [{'title': i.find('title').text, 'price': i.find('price').text if i.find('price') else None} for i in items]

        # 2. HTML 직접 시도
        r2 = requests.get('https://newyork.craigslist.org/search/sss?sort=date&postedToday=1', headers=headers, timeout=10)
        results['html_status'] = r2.status_code
        if r2.status_code == 200:
            soup2 = BeautifulSoup(r2.text, 'html.parser')
            items2 = soup2.select('li.cl-static-search-result')[:5]
            results['html_items'] = [i.get_text(' ', strip=True)[:80] for i in items2]

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/test_craigslist_full")
def test_craigslist_full():
    try:
        from bs4 import BeautifulSoup
        from collections import Counter
        import re

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # 여러 카테고리 동시 수집
        categories = {
            'furniture': 'fua',
            'electronics': 'ela',
            'clothing': 'cla',
            'bikes': 'bia',
            'free': 'zip',
        }

        cat_counts = {}
        all_prices = []
        highlights = []

        for cat_name, cat_code in categories.items():
            try:
                r = requests.get(
                    f'https://newyork.craigslist.org/search/{cat_code}?sort=date&postedToday=1',
                    headers=headers, timeout=8
                )
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    items = soup.select('li.cl-static-search-result')
                    cat_counts[cat_name] = len(items)

                    for item in items[:10]:
                        title = item.select_one('.title')
                        price = item.select_one('.price')
                        if title and price:
                            price_text = price.text.strip()
                            m = re.search(r'\$(\d+)', price_text)
                            if m:
                                all_prices.append(int(m.group(1)))
                            highlights.append({
                                'cat': cat_name,
                                'title': title.text.strip()[:50],
                                'price': price_text
                            })
            except:
                pass

        avg_price = sum(all_prices) // len(all_prices) if all_prices else 0

        return jsonify({
            'category_counts': cat_counts,
            'avg_price': avg_price,
            'total_items': sum(cat_counts.values()),
            'highlights': highlights[:10]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# ─────────────────────────────────────────────
# CRAIGSLIST DATA FETCHER
# ─────────────────────────────────────────────
def get_craigslist_data():
    from bs4 import BeautifulSoup
    from collections import Counter
    import re

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    categories = {
        '🛋 Furniture': 'fua',
        '📱 Electronics': 'ela',
        '👕 Clothing': 'cla',
        '🚲 Bikes': 'bia',
        '🆓 Free': 'zip',
    }

    cat_counts = {}
    all_prices = []
    picks = []
    free_items = []

    for cat_name, cat_code in categories.items():
        try:
            r = requests.get(
                f'https://newyork.craigslist.org/search/{cat_code}?sort=date&postedToday=1',
                headers=headers, timeout=8
            )
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.select('li.cl-static-search-result')
            cat_counts[cat_name] = len(items)

            for item in items[:20]:
                title_el = item.select_one('.title')
                price_el = item.select_one('.price')
                if not title_el:
                    continue
                title = title_el.text.strip()
                price_text = price_el.text.strip() if price_el else ''
                m = re.search(r'\$(\d+)', price_text)
                price_val = int(m.group(1)) if m else 0

                if cat_code == 'zip' or price_val == 0:
                    free_items.append(title[:40])
                elif price_val > 0:
                    all_prices.append(price_val)
                    if len(picks) < 3 and 20 <= price_val <= 300:
                        picks.append({'title': title[:38], 'price': price_text, 'cat': cat_name.split(' ')[1]})
        except:
            pass

    price_buckets = {'Under $50': 0, '$50–200': 0, 'Over $200': 0}
    for p in all_prices:
        if p < 50: price_buckets['Under $50'] += 1
        elif p <= 200: price_buckets['$50–200'] += 1
        else: price_buckets['Over $200'] += 1

    avg = sum(all_prices) // len(all_prices) if all_prices else 0
    total = sum(cat_counts.values())

    return {
        'cat_counts': cat_counts,
        'price_buckets': price_buckets,
        'avg_price': avg,
        'total': total,
        'picks': picks[:3],
        'free': free_items[:4],
    }


# ─────────────────────────────────────────────
# CAROUSEL IMAGE BUILDER
# ─────────────────────────────────────────────
def make_slide(draw_fn):
    W, H = 1080, 1080
    img = Image.new('RGB', (W, H), '#FFFFFF')
    draw = ImageDraw.Draw(img)
    _base = os.path.dirname(os.path.abspath(__file__))
    BOLD = os.path.join(_base, 'fonts', 'DejaVuSans-Bold.ttf')
    REG  = os.path.join(_base, 'fonts', 'DejaVuSans.ttf')
    fonts = {}
    for name, path, size in [
        ('logo', BOLD, 72), ('title', BOLD, 68), ('big', BOLD, 110),
        ('label', BOLD, 38), ('body', REG, 46), ('sub', REG, 40),
        ('tag', BOLD, 36), ('num', BOLD, 90),
    ]:
        try: fonts[name] = ImageFont.truetype(path, size)
        except: fonts[name] = ImageFont.load_default()

    colors = {
        'accent': '#3A46E2', 'black': '#111111', 'gray': '#888888',
        'lgray': '#E5E5E5', 'green': '#22C55E', 'red': '#EF4444',
        'yellow': '#F59E0B', 'bg2': '#F8F8FF', 'white': '#FFFFFF',
    }
    PAD = 64

    draw_fn(img, draw, fonts, colors, PAD, W, H)
    return img


def draw_footer(draw, fonts, colors, PAD, W, H):
    draw.line([(PAD, H - 110), (W - PAD, H - 110)], fill=colors['lgray'], width=2)
    draw.text((PAD, H - 88), 'moonoh', fill=colors['accent'], font=fonts['tag'], anchor='lm')
    draw.text((W - PAD, H - 88), 'moon-oh.com', fill=colors['gray'], font=fonts['tag'], anchor='rm')


def draw_header_bar(draw, fonts, colors, PAD, W):
    draw.text((PAD, 72), 'moonoh', fill=colors['accent'], font=fonts['logo'], anchor='lm')
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime('%b %d, %Y')
    draw.text((W - PAD, 72), today, fill=colors['gray'], font=fonts['sub'], anchor='rm')
    draw.line([(PAD, 112), (W - PAD, 112)], fill=colors['lgray'], width=2)


def slide_cover(data):
    def draw(img, d, f, c, PAD, W, H):
        # 배경 그라데이션 효과 (상단 파란 블록)
        img.paste((58, 70, 226), (0, 0, W, 420))
        d.text((PAD, 80), 'moonoh', fill=c['white'], font=f['logo'], anchor='lm')
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime('%b %d')
        d.text((W - PAD, 80), today, fill='#AAAAFF', font=f['sub'], anchor='rm')

        d.text((PAD, 180), 'NYC Secondhand', fill=c['white'], font=f['title'])
        d.text((PAD, 262), 'Today\'s Trends', fill='#CCCCFF', font=f['title'])

        # 총 매물 수 big number
        d.text((PAD, 360), f"{data['total']:,}개", fill=c['yellow'], font=f['num'], anchor='lm')
        d.text((PAD + 260, 360), 'listings today', fill=c['white'], font=f['body'], anchor='lm')

        # 하단 흰 영역
        d.rectangle([0, 420, W, H], fill=c['white'])
        d.text((PAD, 480), 'Category Rankings  ·  Price Breakdown', fill=c['gray'], font=f['sub'])
        d.text((PAD, 538), 'Today\'s Picks  ·  Free Stuff', fill=c['gray'], font=f['sub'])

        # 큰 화살표 힌트
        d.text((W // 2, 660), '→', fill=c['accent'], font=f['big'], anchor='mm')
        d.text((W // 2, 760), 'Swipe to explore', fill=c['gray'], font=f['body'], anchor='mm')

        draw_footer(d, f, c, PAD, W, H)
    return make_slide(draw)


def slide_categories(data):
    def draw(img, d, f, c, PAD, W, H):
        draw_header_bar(d, f, c, PAD, W)
        d.text((PAD, 148), 'Category Rankings', fill=c['black'], font=f['title'])
        d.text((PAD, 228), 'Today on NYC Craigslist', fill=c['gray'], font=f['sub'])

        cats = sorted(data['cat_counts'].items(), key=lambda x: -x[1])
        max_count = cats[0][1] if cats else 1
        BAR_X = PAD + 320
        BAR_MAX_W = W - BAR_X - PAD - 80
        y = 310

        for i, (name, count) in enumerate(cats):
            # 순위
            d.text((PAD, y + 28), f'#{i+1}', fill=c['accent'], font=f['label'], anchor='lm')
            # 카테고리명
            d.text((PAD + 68, y + 28), name, fill=c['black'], font=f['body'], anchor='lm')
            # 바 그래프
            bar_w = int(BAR_MAX_W * count / max_count)
            bar_colors = [c['accent'], '#6B7BF7', '#9BA8FF', '#B8C2FF', '#D4DAFF']
            d.rectangle([BAR_X, y + 8, BAR_X + bar_w, y + 48], fill=bar_colors[i])
            # 수치
            d.text((BAR_X + bar_w + 10, y + 28), f'{count}', fill=c['gray'], font=f['label'], anchor='lm')
            y += 110

        draw_footer(d, f, c, PAD, W, H)
    return make_slide(draw)


def slide_prices(data):
    def draw(img, d, f, c, PAD, W, H):
        draw_header_bar(d, f, c, PAD, W)
        d.text((PAD, 148), 'Price Breakdown', fill=c['black'], font=f['title'])
        d.text((PAD, 228), f"Avg. price  ${data['avg_price']}", fill=c['accent'], font=f['label'])

        buckets = data['price_buckets']
        total_b = sum(buckets.values()) or 1
        bcolors = [c['green'], c['accent'], c['red']]
        labels = list(buckets.keys())
        values = list(buckets.values())

        # 도넛 느낌 대신 큰 가로 바 3개
        y = 340
        for i, (label, val) in enumerate(zip(labels, values)):
            pct = int(val / total_b * 100)
            bar_w = int((W - PAD * 2) * val / total_b)
            d.rectangle([PAD, y, PAD + bar_w, y + 72], fill=bcolors[i])
            d.text((PAD + 16, y + 36), label, fill=c['white'], font=f['label'], anchor='lm')
            d.text((W - PAD, y + 36), f'{pct}%  ({val}개)', fill=c['gray'], font=f['label'], anchor='rm')
            y += 108

        # 인사이트
        dominant = max(buckets, key=buckets.get)
        d.rectangle([PAD, 700, W - PAD, 820], fill=c['bg2'])
        d.text((PAD + 20, 760), f'💡  {int(buckets[dominant]/total_b*100)}% of NYC listings today are {dominant}', fill=c['black'], font=f['body'], anchor='lm')

        draw_footer(d, f, c, PAD, W, H)
    return make_slide(draw)


def slide_picks(data):
    def draw(img, d, f, c, PAD, W, H):
        draw_header_bar(d, f, c, PAD, W)
        d.text((PAD, 148), 'Today\'s Picks 🔥', fill=c['black'], font=f['title'])
        d.text((PAD, 228), 'Handpicked deals $20–$300', fill=c['gray'], font=f['sub'])

        picks = data['picks']
        if not picks:
            d.text((W // 2, H // 2), 'No picks today', fill=c['gray'], font=f['body'], anchor='mm')
        else:
            y = 310
            for i, pick in enumerate(picks):
                bg = c['bg2'] if i % 2 == 0 else c['white']
                d.rectangle([PAD, y, W - PAD, y + 140], fill=bg)
                # 가격 badge
                d.rectangle([PAD + 12, y + 20, PAD + 160, y + 68], fill=c['accent'])
                d.text((PAD + 86, y + 44), pick['price'], fill=c['white'], font=f['label'], anchor='mm')
                # 제목
                d.text((PAD + 180, y + 44), pick['title'], fill=c['black'], font=f['body'], anchor='lm')
                # 카테고리
                d.text((PAD + 180, y + 96), pick['cat'], fill=c['gray'], font=f['tag'], anchor='lm')
                y += 160

        d.text((PAD, H - 170), '📲 List yours on moonoh', fill=c['accent'], font=f['label'])
        draw_footer(d, f, c, PAD, W, H)
    return make_slide(draw)


def slide_free(data):
    def draw(img, d, f, c, PAD, W, H):
        # 초록 상단
        img.paste((34, 197, 94), (0, 0, W, 380))
        d.text((PAD, 80), 'moonoh', fill=c['white'], font=f['logo'], anchor='lm')
        d.text((PAD, 168), '🆓 Free Stuff Today', fill=c['white'], font=f['title'])
        d.text((PAD, 260), 'Free listings on NYC Craigslist', fill='#AAFFCC', font=f['sub'])

        d.rectangle([0, 380, W, H], fill=c['white'])

        free = data['free']
        if not free:
            d.text((W // 2, 600), 'No free listings today', fill=c['gray'], font=f['body'], anchor='mm')
        else:
            y = 420
            for item in free[:4]:
                d.text((PAD, y), '•', fill=c['green'], font=f['body'], anchor='lm')
                d.text((PAD + 36, y), item, fill=c['black'], font=f['body'], anchor='lm')
                y += 74

        d.text((PAD, 800), 'List for free on moonoh 🗽', fill=c['accent'], font=f['label'])
        draw_footer(d, f, c, PAD, W, H)
    return make_slide(draw)


# ─────────────────────────────────────────────
# CAROUSEL GENERATE ENDPOINT
# ─────────────────────────────────────────────
@app.route('/generate_carousel')
def generate_carousel():
    try:
        data = get_craigslist_data()
        slides = [
            slide_cover(data),
            slide_categories(data),
            slide_prices(data),
            slide_picks(data),
            slide_free(data),
        ]

        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5)))
        ts = now.strftime('%Y-%m-%d-%H%M%S')
        image_urls = []

        for i, slide in enumerate(slides):
            buf = io.BytesIO()
            slide.save(buf, format='JPEG', quality=92)
            buf.seek(0)
            result = cloudinary.uploader.upload(
                buf,
                public_id=f'moonoh_carousel_{ts}_slide{i+1}',
                overwrite=True
            )
            image_urls.append(result['secure_url'])

        caption = f"""🗽 NYC Secondhand Market — Today's Trends

Today on NYC Craigslist — {data['total']:,} new listings.
Avg. price ${data['avg_price']}

Buy & sell locally on moonoh 🏙️
No fees. List in seconds.

📲 moon-oh.com

#NYC #NewYork #secondhand #NYCLife #moonoh #Craigslist #NYCMarketplace #secondhand #thrift"""

        return jsonify({
            'ok': True,
            'image_urls': image_urls,
            'caption': caption,
            'data': data,
        })

    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()})
