from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

BASE_IMAGE_URL = "https://i.postimg.cc/G2Y0pWfm/IMG-1149.jpg"

API_KEYS = {
    "BNGX": True,
    "20DAY": True,
    "busy": False
}

def is_key_valid(api_key):
    return API_KEYS.get(api_key, False)

def fetch_data(uid):
    url = f"https://infoplayerbngx-pi.vercel.app/get?uid={uid}"
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

def overlay_images(base_image_url, outfit_ids, character_id=None, weapon_ids=None, pet_skin_id=None):
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

    # تجهيز عناصر الزي
    items_to_fetch = [(i, outfit_ids[i]) for i in range(min(6, len(outfit_ids)))]

    # إضافة السلاح
    if weapon_ids:
        items_to_fetch.append((6, weapon_ids[0]))  # نعرض أول سلاح فقط في مكان السلاح

    # إضافة الحيوان الأليف
    if pet_skin_id:
        items_to_fetch.append((7, pet_skin_id))

    # تحميل الصور بشكل متوازي
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_pos = {executor.submit(fetch_image_by_id, item_id): pos for pos, item_id in items_to_fetch}
        for future in future_to_pos:
            pos = future_to_pos[future]
            _, img = future.result()
            if img:
                img = img.resize(sizes[pos], Image.LANCZOS)
                base.paste(img, positions[pos], img)

    # عرض الشخصية الكاملة في منتصف البانر
    if character_id:
        try:
            char_url = f"https://pika-ffitmes-api.vercel.app/?item_id={character_id}&watermark=TaitanApi&key=PikaApis"
            character_img = Image.open(BytesIO(requests.get(char_url).content)).convert("RGBA")
            character_img = character_img.resize((130, 130), Image.LANCZOS)

            center_x = (base.width - character_img.width) // 2
            center_y = 370
            base.paste(character_img, (center_x, center_y), character_img)

            font = get_font(25)
            text = "DEV: BNGX"
            textbbox = draw.textbbox((0, 0), text, font=font)
            text_width = textbbox[2] - textbbox[0]
            text_x = center_x + (130 - text_width) // 2
            text_y = center_y + 130 + 5
            draw.text((text_x, text_y), text, fill="white", font=font)
        except Exception as e:
            print(f"Error loading character {character_id}: {e}")

    return base

@app.route('/api', methods=['GET'])
def api():
    uid = request.args.get('uid')
    api_key = request.args.get('key')

    if not uid or not api_key:
        return jsonify({"error": "Missing uid or key parameter"}), 400

    if not is_key_valid(api_key):
        return jsonify({"error": "Invalid or inactive API key"}), 403

    data = fetch_data(uid)
    if not data:
        return jsonify({"error": "Failed to fetch valid profile data"}), 500

    profile_info = data.get("AccountProfileInfo", {})
    account_info = data.get("AccountInfo", {})

    outfit_ids = profile_info.get("EquippedOutfit", [])
    character_id = account_info.get("AccountAvatarId")  # هنا أصبح الشخصية الكاملة
    weapon_ids = account_info.get("weaponSkinShows", [])
    pet_skin_id = data.get("petInfo", {}).get("skinId")

    if not outfit_ids or not character_id:
        return jsonify({"error": "Missing equipped outfit or character data"}), 500

    image = overlay_images(BASE_IMAGE_URL, outfit_ids, character_id, weapon_ids, pet_skin_id)

    img_io = BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
