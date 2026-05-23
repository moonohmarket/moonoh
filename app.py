from flask import Flask, jsonify
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

def get_weather():
    try:
        r = requests.get("https://wttr.in/New+York?format=j1", timeout=8)
        data = r.json()
        current = data["current_condition"][0]
        temp_f = current["temp_F"]
        desc = current["weatherDesc"][0]["value"]
        feels_f = current["FeelsLikeF"]
        humidity = current["humidity"]
        
        # Weather emoji
        code = int(current.get("weatherCode", 113))
        if code == 113: emoji = "☀️"
        elif code in [116, 119]: emoji = "⛅"
        elif code in [122, 143]: emoji = "☁️"
        elif code in [176, 179, 182, 185, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 311, 314, 317, 320, 323, 326, 329, 332, 335, 338, 350, 353, 356, 359, 362, 365, 368, 371, 374, 377]: emoji = "🌧️"
        elif code in [200, 386, 389, 392, 395]: emoji = "⛈️"
        else: emoji = "🌤️"
        
        return {
            "emoji": emoji,
            "temp": temp_f,
            "feels_like": feels_f,
            "desc": desc,
            "humidity": humidity
        }
    except Exception as e:
        return {"emoji": "🌤️", "temp": "N/A", "feels_like": "N/A", "desc": "Check weather.gov", "humidity": "N/A"}

def get_mta_status():
    try:
        r = requests.get(
            "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alert.json",
            headers={"x-api-key": ""},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            alerts = []
            entities = data.get("entity", [])
            seen_lines = set()
            for entity in entities[:20]:
                alert = entity.get("alert", {})
                informed = alert.get("informed_entity", [])
                header = alert.get("header_text", {}).get("translation", [{}])[0].get("text", "")
                
                for ie in informed:
                    route = ie.get("route_id", "")
                    if route and route not in seen_lines and len(alerts) < 4:
                        if any(word in header.lower() for word in ["delay", "suspend", "skip", "reroute", "service change"]):
                            seen_lines.add(route)
                            short = header.split(".")[0][:50] if header else "Service disruption"
                            alerts.append(f"{route} train: {short}")
            
            if not alerts:
                return {"status": "good", "alerts": [], "summary": "All lines running normally ✓"}
            else:
                return {"status": "delays", "alerts": alerts[:3], "summary": f"{len(alerts)} line(s) affected"}
        else:
            return {"status": "unknown", "alerts": [], "summary": "Check mta.info for updates"}
    except Exception as e:
        return {"status": "unknown", "alerts": [], "summary": "Check mta.info for updates"}

def create_image(weather, mta):
    W, H = 1080, 1080
    
    # Background - dark navy with gradient feel
    img = Image.new("RGB", (W, H), "#0A0E1A")
    draw = ImageDraw.Draw(img)
    
    # Subtle gradient overlay - lighter at top
    for y in range(H):
        alpha = int(20 * (1 - y / H))
        r = min(255, 10 + alpha)
        g = min(255, 14 + alpha)
        b = min(255, 26 + alpha)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))
    
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        font_logo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_tagline = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_section = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        font_weather_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 88)
        font_weather_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_weather_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        font_mta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        font_mta_alert = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        font_url = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_logo = font_tagline = font_section = font_weather_big = font_weather_med = font_weather_small = font_mta = font_mta_alert = font_cta = font_url = font_date = ImageFont.load_default()

    # Colors
    PURPLE = "#7C3AED"
    PURPLE_LIGHT = "#A78BFA"
    WHITE = "#FFFFFF"
    GRAY = "#9CA3AF"
    GREEN = "#10B981"
    RED = "#EF4444"
    YELLOW = "#F59E0B"
    BG_CARD = "#111827"

    # ─── TOP SECTION: moonoh branding ───
    # Logo pill background
    pill_x1, pill_y1, pill_x2, pill_y2 = 60, 55, 340, 115
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=30, fill=PURPLE)
    draw.text((200, 85), "moonoh", fill=WHITE, font=font_logo, anchor="mm")
    
    # Date top right
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%b %d, %Y")
    draw.text((W - 60, 85), today, fill=GRAY, font=font_date, anchor="rm")
    
    # Tagline
    draw.text((60, 135), "NYC's free neighborhood marketplace", fill=GRAY, font=font_tagline)
    
    # Divider line
    draw.line([(60, 175), (W - 60, 175)], fill="#1F2937", width=2)
    
    # ─── WEATHER SECTION ───
    # Section label
    draw.text((60, 200), "NYC WEATHER TODAY", fill=PURPLE_LIGHT, font=font_section)
    
    # Big temperature
    draw.text((60, 255), f"{weather['temp']}°F", fill=WHITE, font=font_weather_big)
    
    # Weather emoji and description
    draw.text((380, 275), weather['emoji'], fill=WHITE, font=font_weather_big)
    
    # Description and feels like
    draw.text((60, 370), f"{weather['desc']}", fill=GRAY, font=font_weather_med)
    draw.text((60, 415), f"Feels like {weather['feels_like']}°F  ·  Humidity {weather['humidity']}%", fill=GRAY, font=font_weather_small)

    # Weather card outline
    draw.rounded_rectangle([50, 190, W - 50, 460], radius=20, outline="#1F2937", width=2)
    
    # ─── MTA SECTION ───
    draw.line([(60, 480), (W - 60, 480)], fill="#1F2937", width=2)
    draw.text((60, 505), "MTA SUBWAY STATUS", fill=PURPLE_LIGHT, font=font_section)
    
    if mta["status"] == "good":
        # Green checkmark area
        draw.rounded_rectangle([60, 550, W - 60, 640], radius=16, fill="#064E3B")
        draw.text((W // 2, 595), f"✓  {mta['summary']}", fill=GREEN, font=font_mta, anchor="mm")
    else:
        # Red/yellow alert area
        y_pos = 550
        for i, alert in enumerate(mta["alerts"][:3]):
            bg = "#450A0A" if i == 0 else "#422006"
            draw.rounded_rectangle([60, y_pos, W - 60, y_pos + 58], radius=12, fill=bg)
            alert_color = RED if i == 0 else YELLOW
            # Truncate if too long
            if len(alert) > 45:
                alert = alert[:42] + "..."
            draw.text((80, y_pos + 29), f"⚠  {alert}", fill=alert_color, font=font_mta_alert, anchor="lm")
            y_pos += 68
        
        if not mta["alerts"]:
            draw.rounded_rectangle([60, 550, W - 60, 610], radius=12, fill="#1F2937")
            draw.text((W // 2, 580), mta["summary"], fill=GRAY, font=font_mta, anchor="mm")

    # ─── BOTTOM CTA SECTION ───
    draw.line([(60, 780), (W - 60, 780)], fill="#1F2937", width=2)
    
    # Purple CTA box
    draw.rounded_rectangle([60, 805, W - 60, 960], radius=24, fill="#1E1B4B")
    draw.rounded_rectangle([60, 805, W - 60, 960], radius=24, outline=PURPLE, width=2)
    
    draw.text((W // 2, 850), "Buy & sell with your NYC neighbors", fill=WHITE, font=font_cta, anchor="mm")
    draw.text((W // 2, 898), "Download moonoh — free on App Store & Google Play", fill=PURPLE_LIGHT, font=font_weather_small, anchor="mm")
    draw.text((W // 2, 938), "moon-oh.com", fill=PURPLE, font=font_cta, anchor="mm")

    # Bottom moonoh dot
    draw.ellipse([W//2 - 6, 985, W//2 + 6, 997], fill=PURPLE)

    return img

@app.route("/generate", methods=["GET"])
def generate():
    weather = get_weather()
    mta = get_mta_status()
    
    img = create_image(weather, mta)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    result = cloudinary.uploader.upload(
        buf,
        public_id=f"moonoh_daily_{today_str}",
        overwrite=True,
        resource_type="image"
    )
    
    image_url = result["secure_url"]
    
    # Build caption
    weather_line = f"{weather['emoji']} {weather['temp']}°F · {weather['desc']} · Feels like {weather['feels_like']}°F"
    
    if mta["status"] == "good":
        mta_line = "🚇 All subway lines running normally"
    else:
        mta_line = "🚨 MTA Delays:\n" + "\n".join(f"• {a}" for a in mta["alerts"][:3])
    
    caption = f"""🌆 Good morning, New York!

{weather_line}

{mta_line}

—

moonoh is NYC's free neighborhood marketplace 🗽
Buy & sell with your neighbors — no fees, no hassle.

📲 Download free → moon-oh.com
Available on App Store & Google Play

#NYC #NewYork #NYCLife #NewYorkCity #NYCWeather #MTA #MTASubway #moonoh #NYCMarketplace #BuyAndSell #NYCNeighborhood #LocalNYC #GoodMorningNYC #NYCSubway #FreeListing"""
    
    return jsonify({
        "image_url": image_url,
        "caption": caption,
        "weather": weather,
        "mta": mta
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
