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
    api_key=os.environ.get("CLOUDINARY_API_KEY", "985832125852486"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

def get_weather():
    try:
        r = requests.get("https://wttr.in/New+York?format=j1", timeout=5)
        data = r.json()
        current = data["current_condition"][0]
        temp_f = current["temp_F"]
        desc = current["weatherDesc"][0]["value"]
        feels_f = current["FeelsLikeF"]
        return f"{temp_f}°F · {desc} · Feels like {feels_f}°F"
    except:
        return "Weather data unavailable"

def get_mta():
    try:
        r = requests.get("https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace", timeout=5)
        return "A C E: Check MTA for updates"
    except:
        return "Check mta.info for service updates"

def create_image(weather, mta):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    # Purple gradient overlay (manual)
    for y in range(H):
        r = int(26 + (138 - 26) * y / H)
        g = int(26 + (43 - 26) * y / H)
        b = int(46 + (62 - 46) * y / H)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)

    try:
        font_logo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font_logo = font_title = font_body = font_small = font_cta = ImageFont.load_default()

    today = datetime.datetime.now().strftime("%B %d, %Y")

    # Top: moonoh logo text small
    draw.text((60, 60), "moonoh", fill="#a78bfa", font=font_logo)
    draw.text((W - 60, 60), today, fill="#9ca3af", font=font_small, anchor="ra")

    # Divider
    draw.line([(60, 140), (W - 60, 140)], fill="#4c1d95", width=2)

    # Weather section
    draw.text((60, 180), "🌤  NYC WEATHER", fill="#a78bfa", font=font_title)
    draw.text((60, 280), weather, fill="#f9fafb", font=font_body)

    # Divider
    draw.line([(60, 380), (W - 60, 380)], fill="#4c1d95", width=2)

    # MTA section
    draw.text((60, 420), "🚇  MTA STATUS", fill="#a78bfa", font=font_title)
    
    # Wrap MTA text
    words = mta.split()
    lines = []
    current_line = ""
    for word in words:
        test = (current_line + " " + word).strip()
        if len(test) < 38:
            current_line = test
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    y_pos = 520
    for line in lines[:4]:
        draw.text((60, y_pos), line, fill="#f9fafb", font=font_body)
        y_pos += 60

    # Divider
    draw.line([(60, 800), (W - 60, 800)], fill="#4c1d95", width=2)

    # CTA
    draw.text((W // 2, 860), "Buy & sell with your NYC neighbors", fill="#e5e7eb", font=font_small, anchor="mm")
    draw.text((W // 2, 920), "moonoh — Free on App Store & Google Play", fill="#a78bfa", font=font_cta, anchor="mm")
    draw.text((W // 2, 980), "moon-oh.com", fill="#7c3aed", font=font_small, anchor="mm")

    return img

@app.route("/generate", methods=["GET"])
def generate():
    weather = get_weather()
    mta = get_mta()
    
    img = create_image(weather, mta)
    
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    
    # Upload to Cloudinary
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    result = cloudinary.uploader.upload(
        buf,
        public_id=f"moonoh_daily_{today_str}",
        overwrite=True,
        resource_type="image"
    )
    
    image_url = result["secure_url"]
    
    caption = f"🌆 Good morning NYC!\n\n☀️ Weather: {weather}\n\n🚇 MTA: {mta}\n\nBuy & sell with your neighbors on moonoh — NYC's free local marketplace 🗽\n\nDownload free on App Store & Google Play\nmouth-oh.com\n\n#NYC #NewYork #NYCLife #NYCWeather #MTA #Subway #moonoh #NYCMarketplace #BuyAndSell #Neighbors"
    
    return jsonify({
        "image_url": image_url,
        "caption": caption,
        "weather": weather,
        "mta": mta
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
