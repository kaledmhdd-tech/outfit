from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

app = Flask(__name__)

BASE_IMAGE_URL = "https://i.postimg.cc/DyMZRFqX/IMG-0918-3.png"

API_KEYS = {
    "BNGX": True,
    "20DAY": True,
    "busy": False
}

# ==== الأدوات ====

def is_key_valid(api_key):
    return API_KEYS.get(api_key, False)

def fetch_data(uid):
    url = f"https://info-six-theta.vercel.app/get?uid={uid}"
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error fetching player data: {e}")
        return None

def get_font(size=24):
    try:
        return ImageFont.truetype("Tajawal-Bold.ttf", size)
    except:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)

def fetch_image_by_id(item_id):
    try:
        url = f"https://pika-ffitmes-api.vercel.app/?item_id={item_id}&watermark=TaitanApi&key=PikaApis"
        img = Image.open(BytesIO(requests.get(url).content)).convert("RGBA")
        return item_id, img
    except Exception as e:
        print(f"Error loading item {item_id}: {e}")
        return item_id, None

def overlay_images(base_image_url, item_ids, avatar_id=None, weapon_skin_id=None, pet_skin_id=None):
    base = Image.open(BytesIO(requests.get(base_image_url).content)).convert("RGBA")
    draw = ImageDraw.Draw(base)

    positions = [
        (520, 550),  # 0
        (330, 646),  # 1
        (320, 140),  # 2
        (519, 210),  # 3
        (590, 390),  # 4
        (145, 210),  # 5 -> outfit items
        (150, 550),  # 6 -> weapon
        (70, 380)    # 7 -> pet
    ]
    sizes = [(130, 130)] * len(positions)

    items_to_fetch = [(i, item_ids[i]) for i in range(min(6, len(item_ids)))]

    if weapon_skin_id:
        items_to_fetch.append((6, weapon_skin_id))
    if pet_skin_id:
        items_to_fetch.append((7, pet_skin_id))

    # ✅ جلب الصور واحد تلو الآخر
    for pos, item_id in items_to_fetch:
        _, img = fetch_image_by_id(item_id)
        if img:
            img = img.resize(sizes[pos], Image.LANCZOS)
            base.paste(img, positions[pos], img)

    if avatar_id:
        try:
            avatar_url = f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis"
            avatar = Image.open(BytesIO(requests.get(avatar_url).content)).convert("RGBA")
            avatar = avatar.resize((130, 130), Image.LANCZOS)

            center_x = (base.width - avatar.width) // 2
            center_y = 370
            base.paste(avatar, (center_x, center_y), avatar)

            font = get_font(25)
            text = "DEV: BNGX"
            textbbox = draw.textbbox((0, 0), text, font=font)
            text_width = textbbox[2] - textbbox[0]
            text_x = center_x + (130 - text_width) // 2
            text_y = center_y + 130 + 5
            draw.text((text_x, text_y), text, fill="white", font=font)

        except Exception as e:
            print(f"Error loading avatar {avatar_id}: {e}")

    return base

# ==== المسار الرئيسي ====

@app.route('/api', methods=['GET'])
def api():
    uid = request.args.get('uid')
    api_key = request.args.get('key')

    if not uid or not api_key:
        return jsonify({"error": "Missing uid or key parameter"}), 400

    if not is_key_valid(api_key):
        return jsonify({"error": "Invalid or inactive API key"}), 403

    data = fetch_data(uid)
    if not data or "AccountProfileInfo" not in data or "AccountInfo" not in data:
        return jsonify({"error": "Failed to fetch valid profile data"}), 500

    profile = data.get("AccountProfileInfo", {})
    item_ids = profile.get("EquippedOutfit", [])

    account_info = data.get("AccountInfo", {})
    avatar_id = account_info.get("AccountAvatarId")

    weapon_raw = account_info.get("EquippedWeapon", [])
    weapon_skin_id = weapon_raw[0] if isinstance(weapon_raw, list) and weapon_raw else (
        weapon_raw if isinstance(weapon_raw, int) else None
    )

    pet_skin_id = data.get("petInfo", {}).get("skinId")

    if not item_ids or not avatar_id:
        return jsonify({"error": "Missing equipped outfit or avatar data"}), 500

    image = overlay_images(BASE_IMAGE_URL, item_ids, avatar_id, weapon_skin_id, pet_skin_id)

    img_io = BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
