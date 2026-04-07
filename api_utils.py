import aiohttp
import json
import re
import boto3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import settings_db, translations_db, save_db, TRANSLATIONS_FILE

translate_client = boto3.client(
    'translate',
    region_name='eu-north-1',                  # The region from your screenshot
    aws_access_key_id='AKIAW5M7TICFY5MVLDU4',     # 👈 Paste Key from Step 1
    aws_secret_access_key='SEzk/hRqsW3R47pi2TRLflznNKfT8nuLE0z7xFs9'  # 👈 Paste Secret from Step 1
)

async def send_colored_animation(bot_token: str, chat_id: int, animation_url: str, caption: str, raw_keyboard: list, reply_to: int = None):
    """Bypasses wrapper to send an animation with Bot API 9.4 Colored Buttons"""
    url = f"https://api.telegram.org/bot{bot_token}/sendAnimation"
    payload = {
        "chat_id": chat_id,
        "animation": animation_url,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": raw_keyboard}
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
        
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            if not result.get("ok"):
                print(f"\n❌ TELEGRAM API ERROR (Animation): {result}\n") 

"""
async def send_colored_settings(bot_token: str, chat_id: int, text: str, raw_keyboard: list, message_id: int = None):
    \"\"\"Bypasses wrapper to send/edit text menus, with automatic fallback for deleted messages!\"\"\"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True}, 
        "reply_markup": {"inline_keyboard": raw_keyboard}
    }
    
    if message_id:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload["message_id"] = message_id
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            
            # 👇 THE MAGIC FALLBACK BLOCK 👇
            if not result.get("ok") and result.get("error_code") == 400:
                error_desc = result.get("description", "").lower()
                
                if "not modified" in error_desc:
                    return {"ok": True, "result": {"message_id": message_id}}
                elif "not found" in error_desc or "can't be edited" in error_desc:
                    print(f"⚠️ [SMART FALLBACK] Old message lost. Sending new menu!")
                    fallback_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    if "message_id" in payload:
                        del payload["message_id"] # Remove the dead ID
                        
                    # Fire the new message!
                    async with session.post(fallback_url, json=payload) as fallback_response:
                        return await fallback_response.json()
            
                else:
                    print(f"❌ TELEGRAM API ERROR (Settings Menu): {result}")
            return result"""

async def send_colored_settings(bot_token: str, chat_id: int, text: str, raw_keyboard: list, message_id: int = None):
    """Bypasses wrapper to send/edit text menus, with automatic fallback for deleted messages!"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True}, 
        "reply_markup": {"inline_keyboard": raw_keyboard}
    }
    
    if message_id:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload["message_id"] = message_id
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            
            # 👇 THE MAGIC FALLBACK BLOCK 👇
            if not result.get("ok"):
                error_code = result.get("error_code")
                error_desc = result.get("description", "").lower()
                
                if error_code == 400:
                    if "not modified" in error_desc:
                        return {"ok": True, "result": {"message_id": message_id}}
                    elif "not found" in error_desc or "can't be edited" in error_desc:
                        print(f"⚠️ [SMART FALLBACK] Old message lost. Sending new menu!")
                        fallback_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        if "message_id" in payload:
                            del payload["message_id"] # Remove the dead ID
                            
                        # Fire the new message!
                        async with session.post(fallback_url, json=payload) as fallback_response:
                            fallback_result = await fallback_response.json()
                            # 👇 NEW: Check if the fallback ALSO failed (e.g., broken HTML on the new message)
                            if not fallback_result.get("ok"):
                                raise Exception(f"Fallback Telegram API Error: {fallback_result.get('description')}")
                            return fallback_result
                    else:
                        # 👇 NEW: Force Python to crash for HTML parse errors!
                        print(f"❌ TELEGRAM API ERROR (Settings Menu): {result}")
                        raise Exception(f"Telegram API Error: {result.get('description')}")
                else:
                    # 👇 NEW: Catch any other weird Telegram errors (like 403 Forbidden)
                    print(f"❌ TELEGRAM API ERROR (Settings Menu): {result}")
                    raise Exception(f"Telegram API Error: {result.get('description')}")
                    
            return result            

async def send_colored_photo(bot_token: str, chat_id: int, photo_bytes, caption: str, raw_keyboard: list):
    """Bypasses wrapper to send a Photo with Bot API 9.4 Colored Buttons"""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    data = aiohttp.FormData()
    data.add_field('chat_id', str(chat_id))
    data.add_field('caption', caption)
    data.add_field('parse_mode', 'HTML')
    data.add_field('reply_markup', json.dumps({"inline_keyboard": raw_keyboard}))
    

    if isinstance(photo_bytes, str):
        data.add_field('photo', photo_bytes)
    else:
        actual_bytes = photo_bytes.getvalue() if hasattr(photo_bytes, 'getvalue') else photo_bytes
        data.add_field('photo', actual_bytes, filename='image.png', content_type='image/png')

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            if not result.get("ok"):
                error_msg = f"❌ TELEGRAM API ERROR (Photo): {result.get('description')}"
                print(error_msg)
                raise Exception(error_msg) # This triggers the safe fallback in /start!
                
            return result  


async def smart_translate(text: str, target_lang: str) -> str:
    """Enterprise AWS API: Natively ignores and preserves HTML tags!"""
    if target_lang == 'en' or not text: 
        return text
    
    use_cache = settings_db.get('cache_translations', True)

    # 2. Check the Database Cache first
    if use_cache:
        if target_lang in translations_db and text in translations_db[target_lang]:
            return translations_db[target_lang][text]

    try:
        # 3. Call AWS Translate (It preserves HTML naturally)
        result = await asyncio.to_thread(
            translate_client.translate_text,
            Text=text,
            SourceLanguageCode='en',     # Auto-detects English
            TargetLanguageCode=target_lang # e.g., 'mr' for Marathi
        )
        translated_text = result.get('TranslatedText')

        # 4. Save the perfect HTML to Database
        if use_cache:
            if target_lang not in translations_db: 
                translations_db[target_lang] = {}
            translations_db[target_lang][text] = translated_text
            save_db(TRANSLATIONS_FILE, translations_db)
            print(f"💾 Cached Enterprise AWS translation for [{target_lang}]")

        return translated_text

    except Exception as e:
        print(f"AWS Translate API failed: {e}")
        return text
    
    
    
SUPPORTED_LANGS = [
    {"code": "en", "name": "🇬🇧 English"},
    {"code": "hi", "name": "🇮🇳 Hindi"},
    {"code": "mr", "name": "🚩 Marathi"},
    {"code": "bn", "name": "🟢 Bengali"},
    {"code": "gu", "name": "🟠 Gujarati"},
    {"code": "ta", "name": "🟣 Tamil"},
    {"code": "te", "name": "🟡 Telugu"}
]

async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Generates a 2x2 paginated language selection menu (Photo-Safe)"""
    items_per_page = 4 # 2x2 grid = 4 items per page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_langs = SUPPORTED_LANGS[start_idx:end_idx]

    keyboard = []
    row = []
    
    # Build the 2x2 grid
    for lang in page_langs:
        row.append(InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: # Catch any odd remaining buttons
        keyboard.append(row)

    # Add Pagination Controls
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"lang_page_{page-1}"))
    if end_idx < len(SUPPORTED_LANGS):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"lang_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    msg = "🌍 <b>Please select your preferred language:</b>\n<i>कृपया अपनी पसंदीदा भाषा चुनें:</i>"

    # 👇 THE SMART PHOTO-SAFE LOGIC 👇
    if update.callback_query:
        try:
            # 1. First, try to smoothly edit it (works if it was already a text menu)
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        except Exception:
            # 2. If it crashes (because it's a Photo), delete the photo and send clean text!
            await update.callback_query.message.delete()
            await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')