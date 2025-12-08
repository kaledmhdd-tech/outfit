from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import textwrap

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
    url = f"https://info-five-mauve.vercel.app/accinfo?uid={uid}&region=IND"
    try:
        res = requests.get(url, timeout=10)
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

def fetch_image_by_id(item_id, retries=3):
    url = f"https://pika-ffitmes-api.vercel.app/?item_id={item_id}&watermark=TaitanApi&key=PikaApis"
    for attempt in range(1, retries + 1):
        try:
            img = Image.open(BytesIO(requests.get(url, timeout=5).content)).convert("RGBA")
            return item_id, img
        except Exception as e:
            print(f"[Retry {attempt}/{retries}] Error loading item {item_id}: {e}")
            if attempt == retries:
                return item_id, None

def add_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width=2):
    """إضافة نص مع حدود (outline)"""
    x, y = position
    
    # رسم حدود النص من جميع الجهات
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    
    # رسم النص الرئيسي
    draw.text(position, text, font=font, fill=fill_color)

def overlay_images(base_image_url, clothes_ids, avatar_id=None, weapon_skin_id=None, pet_skin_id=None, player_data=None):
    try:
        base = Image.open(BytesIO(requests.get(base_image_url, timeout=10).content)).convert("RGBA")
    except Exception as e:
        print(f"Error loading base image: {e}")
        # إنشاء صورة أساسية في حالة الخطأ
        base = Image.new('RGBA', (800, 1000), (40, 40, 60, 255))
    
    draw = ImageDraw.Draw(base)

    # ===== إضافة معلومات اللاعب =====
    if player_data:
        try:
            font_small = get_font(20)
            font_medium = get_font(24)
            font_large = get_font(30)
            
            basic_info = player_data.get("basicInfo", {})
            clan_info = player_data.get("clanBasicInfo", {})
            profile_info = player_data.get("profileInfo", {})
            
            # معلومات اللاعب في الأعلى
            nickname = basic_info.get("nickname", "Unknown")
            level = basic_info.get("level", 1)
            rank = basic_info.get("rank", 0)
            clan_name = clan_info.get("clanName", "No Clan")
            
            # إضافة الاسم والمستوى
            name_text = f"{nickname} | Lvl {level}"
            add_text_with_outline(draw, (250, 50), name_text, font_large, "white", "black", 2)
            
            # إضافة الرتبة
            rank_text = f"Rank: {rank}"
            add_text_with_outline(draw, (250, 90), rank_text, font_medium, "cyan", "black", 1)
            
            # إضافة اسم العشيرة
            clan_text = f"Clan: {clan_name}"
            # لف النص إذا كان طويلاً
            max_width = 400
            wrapped_clan = textwrap.fill(clan_text, width=30)
            clan_lines = wrapped_clan.split('\n')
            
            for i, line in enumerate(clan_lines):
                add_text_with_outline(draw, (250, 130 + i*30), line, font_small, "yellow", "black", 1)
            
            # إضافة معلومات إضافية
            info_y = 200
            info_items = [
                f"EXP: {basic_info.get('exp', 0):,}",
                f"Likes: {basic_info.get('liked', 0):,}",
                f"Badges: {basic_info.get('badgeCnt', 0)}",
                f"Region: {basic_info.get('region', 'Unknown')}"
            ]
            
            for i, info in enumerate(info_items):
                add_text_with_outline(draw, (50, info_y + i*35), info, font_small, "lightgreen", "black", 1)
            
        except Exception as e:
            print(f"Error adding player info: {e}")

    # ===== إضافة العناصر =====
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

    items_to_fetch = []
    
    # إضافة الملابس (cosmeticItems)
    if clothes_ids and isinstance(clothes_ids, list):
        for i in range(min(6, len(clothes_ids))):
            if clothes_ids[i]:
                items_to_fetch.append((i, clothes_ids[i]))
    
    if weapon_skin_id:
        items_to_fetch.append((6, weapon_skin_id))
    if pet_skin_id:
        items_to_fetch.append((7, pet_skin_id))

    fetched_images = {}
    if items_to_fetch:
        with ThreadPoolExecutor(max_workers=min(10, len(items_to_fetch))) as executor:
            futures = {executor.submit(fetch_image_by_id, item_id): pos for pos, item_id in items_to_fetch}
            for future in as_completed(futures):
                pos = futures[future]
                item_id, img = future.result()
                fetched_images[pos] = img

    for pos, img in fetched_images.items():
        if img:
            try:
                img = img.resize(sizes[pos], Image.LANCZOS)
                base.paste(img, positions[pos], img)
            except Exception as e:
                print(f"Error processing image for position {pos}: {e}")

    # جلب الصورة الرمزية (Avatar)
    if avatar_id:
        try:
            avatar_url = f"https://pika-ffitmes-api.vercel.app/?item_id={avatar_id}&watermark=TaitanApi&key=PikaApis"
            avatar_response = requests.get(avatar_url, timeout=5)
            avatar = Image.open(BytesIO(avatar_response.content)).convert("RGBA")
            avatar = avatar.resize((130, 130), Image.LANCZOS)
            center_x = (base.width - avatar.width) // 2
            center_y = 370
            base.paste(avatar, (center_x, center_y), avatar)

            # إضافة نص "DEV: BNGX"
            font = get_font(25)
            text = "DEV: BNGX"
            textbbox = draw.textbbox((0, 0), text, font=font)
            text_width = textbbox[2] - textbbox[0]
            text_x = center_x + (130 - text_width) // 2
            text_y = center_y + 130 + 5
            add_text_with_outline(draw, (text_x, text_y), text, font, "white", "black", 1)
            
        except Exception as e:
            print(f"Error loading avatar {avatar_id}: {e}")
            # إضافة مكان للصورة الرمزية في حالة الخطأ
            avatar_placeholder = Image.new('RGBA', (130, 130), (100, 100, 150, 200))
            center_x = (base.width - 130) // 2
            center_y = 370
            base.paste(avatar_placeholder, (center_x, center_y))

    # إضافة حدود زخرفية
    try:
        border_color = (255, 215, 0, 255)  # ذهبي
        border_width = 5
        draw.rectangle([(border_width, border_width), 
                       (base.width - border_width, base.height - border_width)], 
                      outline=border_color, width=border_width)
    except Exception as e:
        print(f"Error adding border: {e}")

    return base

# ==== المسار الرئيسي ====

@app.route('/api', methods=['GET'])
def api():
    uid = request.args.get('uid')
    api_key = request.args.get('key')
    show_info = request.args.get('info', 'true').lower() == 'true'

    if not uid or not api_key:
        return jsonify({"error": "Missing uid or key parameter"}), 400

    if not is_key_valid(api_key):
        return jsonify({"error": "Invalid or inactive API key"}), 403

    data = fetch_data(uid)
    if not data:
        return jsonify({"error": "Failed to fetch player data"}), 500

    # التحقق من وجود البيانات الأساسية
    if "basicInfo" not in data:
        return jsonify({"error": "Invalid player data structure"}), 500

    profile = data.get("profileInfo", {})
    basic_info = data.get("basicInfo", {})
    
    # استخراج cosmeticItems (الملابس)
    clothes_ids = []
    if "cosmeticItems" in profile:
        clothes_ids = profile.get("cosmeticItems", [])
    elif "clothes" in profile:  # للتوافق مع النسخ القديمة
        clothes_ids = profile.get("clothes", [])
    
    # استخراج avatarId
    avatar_id = profile.get("avatarId")
    if not avatar_id:
        avatar_id = basic_info.get("headPic")
    
    # استخراج weapon skin
    weapon_skin_list = basic_info.get("weaponSkinShows", [])
    weapon_skin_id = weapon_skin_list[0] if weapon_skin_list else None
    
    # استخراج pet skin
    pet_skin_id = None
    if "petInfo" in data:
        pet_skin_id = data.get("petInfo", {}).get("skinId")

    # التحقق من البيانات المطلوبة
    if not clothes_ids and not avatar_id:
        return jsonify({
            "error": "Missing equipped items data",
            "debug": {
                "has_clothes": bool(clothes_ids),
                "has_avatar": bool(avatar_id),
                "clothes_ids": clothes_ids,
                "avatar_id": avatar_id
            }
        }), 500

    try:
        # تمرير بيانات اللاعب إذا طلب المستخدم المعلومات
        player_data_for_image = data if show_info else None
        image = overlay_images(
            BASE_IMAGE_URL, 
            clothes_ids, 
            avatar_id, 
            weapon_skin_id, 
            pet_skin_id,
            player_data_for_image
        )

        img_io = BytesIO()
        image.save(img_io, 'PNG', optimize=True, quality=85)
        img_io.seek(0)
        
        # إضافة رؤوس للتحسين
        response = send_file(img_io, mimetype='image/png')
        response.headers['Cache-Control'] = 'public, max-age=300'
        response.headers['X-API-Version'] = '2.0'
        response.headers['X-Player-UID'] = uid
        
        return response
        
    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({
            "error": "Failed to generate image",
            "details": str(e)
        }), 500

# ==== مسار الصحة ====
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "FreeFire Player Card Generator",
        "version": "2.0",
        "active_keys": len([k for k, v in API_KEYS.items() if v])
    })

# ==== مسار معلومات المفاتيح ====
@app.route('/keys', methods=['GET'])
def keys_info():
    return jsonify({
        "available_keys": [k for k, v in API_KEYS.items() if v],
        "total_keys": len(API_KEYS)
    })

if __name__ == '__main__':
    print("Starting FreeFire Player Card Generator API...")
    print(f"Available API keys: {[k for k, v in API_KEYS.items() if v]}")
    app.run(host='0.0.0.0', port=5000, debug=True)
