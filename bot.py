
import logging
import qrcode
import io
import json
import asyncio
import time
import secrets
import string
import aiohttp
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import (
    orders_db, members_db, invite_links_db, settings_db, plans_db, users_db,
    save_db, ORDERS_FILE, MEMBERS_FILE, INVITE_LINKS_FILE,SETTINGS_FILE, USERS_FILE,
    mongo_client, mongo_db
)
from admin_dashboard import (
    show_bot_stats, 
    show_stats_approved, 
    show_stats_revenue, 
    show_stats_links, 
    show_stats_pending
)
from admin_panel import show_dashboard, handle_admin_callbacks, handle_admin_text
from api_utils import send_colored_settings, send_colored_photo, smart_translate, show_language_menu, SUPPORTED_LANGS
import os

# Import config
try:
    from config import *
except Exception as e:
    print(f"❌ REAL ERROR: {e}")
    exit(1)

# Setup logging
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

#ADMIN CHECK AND ADD ADMIN COMMANDS
async def add_coadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main Admin ONLY: Add a co-admin by ID or Username"""
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("❌ *Access Denied:* Only the Main Admin can add Co-Admins.", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("⚠️ *Usage:* `/add <userID>` OR `/add @username`", parse_mode='Markdown')
        return

    target = context.args[0].replace('@', '')
    co_admins = settings_db.get('co_admins', [])

    if target in co_admins or target.lower() in [c.lower() for c in co_admins]:
        await update.message.reply_text("⚠️ This user is already a Co-Admin!")
        return

    co_admins.append(target)
    settings_db['co_admins'] = co_admins
    save_db(SETTINGS_FILE, settings_db)
    
    await update.message.reply_text(f"✅ *Successfully added* `{target}` *as a Co-Admin!*", parse_mode='Markdown')


async def remove_coadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main Admin ONLY: Remove a co-admin by ID or Username"""
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        return 

    if not context.args:
        await update.message.reply_text("⚠️ *Usage:* `/remove <userID>` OR `/remove @username`", parse_mode='Markdown')
        return

    target = context.args[0].replace('@', '')
    co_admins = settings_db.get('co_admins', [])
    for ca in co_admins:
        if ca.lower() == target.lower():
            co_admins.remove(ca)
            settings_db['co_admins'] = co_admins
            save_db(SETTINGS_FILE, settings_db)
            await update.message.reply_text(f"✅ *Successfully removed* `{target}` *from Co-Admins!*", parse_mode='Markdown')
            return

    await update.message.reply_text("❌ Could not find that user in the Co-Admin list.")


async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the roster of Admins (Admins & Co-Admins only)"""
    if not is_coadmin(update.effective_user):
        return

    co_admins = settings_db.get('co_admins', [])
    try:
        main_admin_chat = await context.bot.get_chat(ADMIN_CHAT_ID)
        main_admin_username = f"(@{main_admin_chat.username})" if main_admin_chat.username else "(No Username)"
    except Exception:
        main_admin_username = f"(@{ADMIN_USERNAME.replace('@', '')})"

    msg = f"👑 *MAIN ADMIN:*\n• `{ADMIN_CHAT_ID}` {main_admin_username}\n\n"
    msg += "🛡️ *CO-ADMINS:*\n"
    if not co_admins:
        msg += "• _No co-admins added yet._"
    else:
        for ca in co_admins:
            if ca.isdigit():
                try:
                    ca_chat = await context.bot.get_chat(int(ca))
                    ca_display = f"`{ca}` (@{ca_chat.username})" if ca_chat.username else f"`{ca}` ({ca_chat.first_name})"
                except Exception:
                    ca_display = f"`{ca}`" 
            else:
                ca_display = f"@{ca}"
                
            msg += f"• {ca_display}\n"
            
    await update.message.reply_text(msg, parse_mode='Markdown')

def is_coadmin(user):
    #Checks if a user is the Main Admin OR a Co-Admin in the database
    if str(user.id) == str(ADMIN_CHAT_ID):
        return True
        
    co_admins = settings_db.get('co_admins', [])
    
    if str(user.id) in co_admins:
        return True
        
    if user.username:
        clean_username = user.username.replace('@', '').lower()
        if clean_username in [c.lower() for c in co_admins]:
            return True
            
    return False

def generate_order_id(user_id: int) -> str:
    u_str = str(user_id)
    time_part = str(int(time.time() * 1000))[-4:]
    alphabet = string.ascii_uppercase
    prefix = ''.join(secrets.choice(alphabet) for _ in range(2))  # e.g., 'XJ'
    mid = secrets.choice(alphabet)                                # e.g., 'K'
    suffix = secrets.token_hex(1).upper()                         # e.g., 'F4'
    return f"ORD{prefix}{u_str}{mid}{time_part}{suffix}"


def generate_qr_code(upi_string):
    #Generate QR code
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        bio = io.BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"QR error: {e}")
        return None


def create_upi_string(order_id, amount, upi_id):
    """Create UPI payment string dynamically"""
    return (
        f"upi://pay?"
        f"pa={upi_id}&"
        f"pn={MERCHANT_NAME}&"
        f"am={amount}&"
        f"tn=Order%20{order_id}&"
        f"cu=INR"
    )

async def create_single_use_invite_link(context, user_id, username, order_id):
    """Create one-time invite link"""
    try:
        expiry_date = datetime.now() + timedelta(hours=INVITE_LINK_EXPIRY_HOURS)
        
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=PREMIUM_CHANNEL_ID,
            expire_date=int(expiry_date.timestamp()),
            member_limit=1,
            name=f"User_{user_id}_{int(time.time())}"
        )
        
        invite_links_db[str(user_id)] = {
            'link': invite_link.invite_link,
            'order_id': order_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': expiry_date.isoformat(),
            'used': False,
            'username': username
        }
        save_db(INVITE_LINKS_FILE, invite_links_db)
        
        logger.info(f"✅ Link created for user {user_id}")
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"❌ Link error: {e}")
        return None


def is_member(user_id):
    user_str = str(user_id)
    if user_str in members_db:
        return members_db[user_str].get('active', True) 
    return False


def add_member(user_id, username, order_id):
    """Add member to database"""
    members_db[str(user_id)] = {
        'username': username,
        'order_id': order_id,
        'joined_at': datetime.now().isoformat(),
        'active': True
    }
    save_db(MEMBERS_FILE, members_db)

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #Triggered by /stat
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_CHAT_ID):
        return
        
    class FakeQuery:
        message = update.message
    await show_bot_stats(FakeQuery(), context)

async def my_active_plans(query, context):
    #Shows the user's current plan status, expiry, and pending plans (Hides unpaid carts)
    user_id = query.from_user.id
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    user_orders = [
        (oid, o) for oid, o in orders_db.items() 
        if str(o.get('user_id')) == str(user_id) and o.get('status') not in ['not paid', 'not paid gateway']
    ]
    
    if not user_orders:
        await query.answer("❌ You don't have any active plans or pending orders.", show_alert=True)
        return
    
    user_orders.sort(key=lambda x: x[1].get('created_at', ''), reverse=True)
    
    msg = f"📊 <b>YOUR ACCOUNT DASHBOARD</b>\n\n"
    link_placeholders = {}

    for order_id, order in user_orders:
        status = order.get('status', 'pending')
        if status in ['approved', 'active']: display_status = "✅ Approved"
        elif status == 'rejected': display_status = "❌ Rejected"
        elif status == 'expired': display_status = "⚠️ Expired/Timeout"
        elif status == 'revoked': display_status = "🚫 Access Revoked" 
        elif status in ['pending', 'pending_gateway']: display_status = "⏳ Under Admin Review"
        else: display_status = "⏳ Processing"

        plan_name = order.get('plan_name', 'Unknown Plan')
        duration_text = "Lifetime"
        time_delta = None
        for p in plans_db.values():
            if p['name'] == plan_name:
                duration_text = p.get('duration', 'Lifetime')
                time_delta = parse_plan_duration(duration_text)
                break

        try:
            created_dt = datetime.fromisoformat(order.get('created_at', ''))
            time_str = created_dt.strftime('%d %b %Y, %I:%M %p')
        except:
            time_str = "Unknown"

        msg += f"<blockquote>"
        msg += f"🛍️ <b>Plan:</b> {plan_name}\n"
        msg += f"📋 <b>Order ID:</b> <code>{order_id}</code>\n"
        msg += f"⏳ <b>Duration:</b> {duration_text}\n"
        msg += f"💰 <b>Amount:</b> ₹{order.get('amount')}\n"
        msg += f"⏰ <b>Purchased:</b> {time_str}\n"
        msg += f"✨ <b>Status:</b> {display_status}\n"

        if status in ['approved', 'active']:
            approved_at = order.get('approved_at')
            if approved_at and time_delta:
                try:
                    app_dt = datetime.fromisoformat(approved_at)
                    exp_dt = app_dt + time_delta # Add the parsed time!
                    exp_str = exp_dt.strftime('%d %b %Y, %I:%M %p')
                    msg += f"🛑 <b>Expiry at:</b> {exp_str}\n"    
                except Exception as e:
                    logger.error(f"Date math error: {e}")
            else:
                msg += f"🛑 <b>Expiry at:</b> Never (Lifetime)\n"
                
            invite_link = order.get('invite_link')
            if invite_link:
                placeholder = f"URL_PLACEHOLDER_{order_id}"
                link_placeholders[placeholder] = invite_link
                msg += f"</blockquote>\n🔗 <b>Your Invite Link:</b>\n{invite_link}\n\n"
            else:
                msg += "</blockquote>\n\n"
        else:
            msg += "</blockquote>\n\n"

    final_msg = await smart_translate(msg, user_lang)
    for placeholder, real_link in link_placeholders.items():
        final_msg = final_msg.replace(placeholder, real_link)

    btn_browse = await smart_translate("🛍️ Browse Plans", user_lang)
    btn_back = await smart_translate("🔙 Back to Main Menu", user_lang)

    raw_kb = [
        [{"text": btn_browse, "callback_data": "join_membership", "style": "primary"}],
        [{"text": btn_back, "callback_data": "back_main", "style": "danger"}]
    ]
    
    try:
        if query.message.text:
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, chat_id=query.message.chat_id,
                text=final_msg, raw_keyboard=raw_kb, message_id=query.message.message_id
            )
        else:
            try:
                await query.message.delete()
            except:
                pass
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, chat_id=query.message.chat_id,
                text=final_msg, raw_keyboard=raw_kb
            )
    except Exception as e:
        logger.error(f"Error showing active plans: {e}")

def parse_plan_duration(duration_str):
 #'1d', '30min', or '1d30min' into a Python timedelta object

    if not duration_str or duration_str.lower() in ['lifetime', 'never']:
        return None
        
    days = 0
    minutes = 0
    d_match = re.search(r'(\d+)d', duration_str.lower())
    m_match = re.search(r'(\d+)min', duration_str.lower())
    
    if d_match:
        days = int(d_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
        
    if days == 0 and minutes == 0:
        return None
        
    return timedelta(days=days, minutes=minutes)        
        

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        user = update.callback_query.from_user
        message_to_edit = update.callback_query.message
    else:
        user = update.effective_user
        message_to_edit = None
        
    user_id = str(user.id)
    if user_id not in users_db or 'lang' not in users_db[user_id]:
        await show_language_menu(update, context, page=0)
        return
    user_lang = users_db[user_id].get('lang', 'en')
    is_active_member = False
    
    for oid, order in orders_db.items():
        if str(order.get('user_id')) == str(user_id):
            status = order.get('status')
            if status in ['approved', 'pending', 'pending_gateway']:
                is_active_member = True
                break

    btn_active = await smart_translate("📊 Active Plans", user_lang)
    btn_browse = await smart_translate("🚀 Browse Plans", user_lang)
    btn_contact = await smart_translate("📞 Contact Admin", user_lang)
    btn_join = await smart_translate("🚀 Join Membership", user_lang)
    btn_how = await smart_translate("ℹ️ How It Works", user_lang)
    btn_lang = await smart_translate("🌍 Language", user_lang)
    if is_active_member:
        raw_keyboard = [
            [{"text": btn_active, "callback_data": "my_active_plans", "style": "success"},
             {"text": btn_lang, "callback_data": "lang_page_0", "style": "primary"}],
            [{"text": btn_browse, "callback_data": "join_membership", "style": "primary"}],
            [{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}]
        ]
        fallback_kb = [
            [InlineKeyboardButton(btn_active, callback_data='my_active_plans'),
             InlineKeyboardButton(btn_lang, callback_data='lang_page_0')],
            [InlineKeyboardButton(btn_browse, callback_data='join_membership')],
            [InlineKeyboardButton(btn_contact, callback_data='contact_admin')]
        ]
    else:
        # Standard welcome for brand new users
        raw_keyboard = [
            [{"text": btn_join, "callback_data": "join_membership", "style": "success"}],
            [{"text": btn_how, "callback_data": "how_it_works", "style": "primary"},
             {"text": btn_lang, "callback_data": "lang_page_0", "style": "primary"}], 
            [{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}]
        ]
        fallback_kb = [
            [InlineKeyboardButton(btn_join, callback_data='join_membership')],
            [InlineKeyboardButton(btn_how, callback_data='how_it_works'),
             InlineKeyboardButton(btn_lang, callback_data='lang_page_0')],
            [InlineKeyboardButton(btn_contact, callback_data='contact_admin')]
        ]
    welcomee_message = f"""
🎉 *Welcome to {BOT_NAME}!* 🎉

Hello {user.first_name}! 👋

Get *Lifetime Premium Access* for just *₹{MEMBERSHIP_PRICE}*! 🚀

✨ *What You'll Get:*
• 📚 Exclusive premium content
• ♾️ Lifetime access
• 🎯 Fast approval (within hours)
• 🔄 Regular updates

💳 *Payment Process:*
1️⃣ Click "Join Membership"
2️⃣ Pay ₹{MEMBERSHIP_PRICE} via UPI
3️⃣ Send payment screenshot
4️⃣ Admin approves
5️⃣ Get instant access!

Ready to join? 👇
"""
    
    raw_welcome = settings_db.get(
        'welcome_msg', 
        "🎉 <b>Welcome to {BOT_NAME}!</b> 🎉\n\nHello {USER_NAME}! 👋\n\nGet <b>Premium Access</b> today for just ₹{PRICE}!"
    )

    welcome_message_formatted = raw_welcome.replace("{bot_name}", str(BOT_NAME)).replace("{BOT_NAME}", str(BOT_NAME)) \
                                 .replace("{user_name}", str(user.first_name)).replace("{USER_NAME}", str(user.first_name)) \
                                 .replace("{price}", str(MEMBERSHIP_PRICE)).replace("{PRICE}", str(MEMBERSHIP_PRICE)) \
                                 .replace("{MEMBERSHIP_PRICE}", str(MEMBERSHIP_PRICE))    
    
    welcome_message = await smart_translate(welcome_message_formatted, user_lang)
    photo_id = None
    try:
        photos = await context.bot.get_user_profile_photos(user.id)
        if photos.total_count > 0:
            photo_id = photos.photos[0][-1].file_id # User's Profile Picture
        else:
            photo_id = settings_db.get('welcome_image_id') # Admin
    except Exception as e:
        logger.error(f"Error fetching DP: {e}")
        
    clean_text = re.sub(r'<[^>]+>', '', welcome_message)
    # Image format 
    if photo_id:
        try:
            await send_colored_photo(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=user.id,
                photo_bytes=photo_id, 
                caption=welcome_message,      
                raw_keyboard=raw_keyboard     
            )
            if update.callback_query:
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass
                
            return 
            
        except Exception as e:
            print(f"Colored photo failed (likely an HTML typo). Deploying safe photo... Error: {e}")
            
            try:
                if update.callback_query:
                    await context.bot.send_photo(
                        chat_id=user.id, 
                        photo=photo_id, 
                        caption=clean_text, 
                        reply_markup=InlineKeyboardMarkup(fallback_kb)
                    )
                    await update.callback_query.message.delete()
                else:
                    await update.message.reply_photo(
                        photo=photo_id, 
                        caption=clean_text, 
                        reply_markup=InlineKeyboardMarkup(fallback_kb)
                    )
                return
                
            except Exception as e2:
                print(f"Safe photo fallback failed entirely: {e2}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        #Handle buttons

    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('admin_'):
        await handle_admin_callbacks(update, context)
        return
    elif query.data == 'my_active_plans':
        await my_active_plans(query, context)
    elif query.data == 'join_membership':
        await clean_abandoned_orders(context, query.from_user.id)
        await show_membership_plan(query, context)
    elif query.data.startswith('get_access_'):
        await clean_abandoned_orders(context, query.from_user.id)
        plan_id = query.data.replace('get_access_', '')
        await choose_payment_method(query, context, plan_id)
    elif query.data.startswith('select_upi_'):
        parts = query.data.split('_')
        order_id = parts[2]
        upi_idx = int(parts[3])
        await show_payment_screen(query, context, order_id, upi_idx)
    elif query.data.startswith('change_upi_'):
        order_id = query.data.replace('change_upi_', '')
        await show_upi_selection(query, context, order_id)    
    elif query.data.startswith('pay_gateway_'):
        plan_id = query.data.replace('pay_gateway_', '')
        await initiate_gateway_payment(query, context, plan_id)
    elif query.data.startswith('pay_direct_'):
        plan_id = query.data.replace('pay_direct_', '')
        await initiate_payment(query, context, plan_id)
    elif query.data.startswith('confirm_payment_'):
        order_id = query.data.replace('confirm_payment_', '')
        await request_screenshot(query, context, order_id)
    elif query.data == 'contact_admin':
        await contact_admin(query, context)
    elif query.data == 'how_it_works':
        await show_how_it_works(query, context)  
    elif query.data.startswith('btn_approve_'):
        await approve_order(update, context)
    elif query.data.startswith('btn_reject_'):
        await reject_order(update, context) 
    elif query.data.startswith('verify_rzp_'):
        order_id = query.data.replace('verify_rzp_', '')
        
        if order_id not in orders_db:
            await query.answer("❌ Order not found.", show_alert=True)
            return
            
        order = orders_db[order_id]
        status = order.get('status')
        
        if status == 'approved':
            await query.answer("✅ Your payment is already approved! Check your chat history.", show_alert=True)
            return

        rzp_link_id = order.get('rzp_link_id')
        key_id = settings_db.get('rzp_key_id')
        key_secret = settings_db.get('rzp_key_secret')

        if rzp_link_id and key_id and key_secret:
            await query.answer("🔄 Checking Razorpay servers...", show_alert=False)
            url = f"https://api.razorpay.com/v1/payment_links/{rzp_link_id}"
            auth = aiohttp.BasicAuth(key_id, key_secret)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, auth=auth) as response:
                        rzp_data = await response.json()
                        
                        if rzp_data.get('status') == 'paid':
                            if order.get('is_processing'):
                                await query.answer("⏳ Payment received! We are generating your premium link right now. Please wait a few seconds.", show_alert=True)
                                return
                            orders_db[order_id]['is_processing'] = True
                            save_db(ORDERS_FILE, orders_db)
                            current_mode = settings_db.get('rzp_mode', 'manual').lower()

                            if current_mode == 'auto':
                                confirming_msg_id = order.get('confirming_msg_id')
                                if confirming_msg_id:
                                    try:
                                        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=confirming_msg_id)
                                    except Exception:
                                        pass
                                success = await process_approval(context, order_id, message_id_to_edit=order.get('status_msg_id'))
                                
                                '''if success:
                                    first_name = order.get('first_name', 'User')
                                    username_display = f" (@{order.get('username')})" if order.get('username') else ""
                                    u_id = order.get('user_id', 'Unknown')
                                    plan_name = order.get('plan_name', 'Premium Plan')
                                    amount = order.get('amount', '0')
                                    
                                    admin_msg = f"""🤖 <b>AUTO-APPROVED RAZORPAY</b> ✅

<blockquote>📋 <b>Order ID:</b> <code>{order_id}</code>
👤 <b>User:</b> {first_name}{username_display}
🆔 <b>User ID:</b> <code>{u_id}</code>
🛍️ <b>Plan:</b> {plan_name}
💰 <b>Amount:</b> ₹{amount}</blockquote>

<i>The gateway confirmed payment and the user was automatically sent their invite link.</i>

🛠️ <b>Admin Quick Actions:</b>
Kick User & Revoke Link:
<code>/revoke {order_id}</code>

Delete User Data:
<code>/deleteuser {u_id}</code>"""

                                    # 3. Send using HTML format
                                    await context.bot.send_message(
                                        chat_id=ADMIN_CHAT_ID, 
                                        text=admin_msg, 
                                        parse_mode='HTML'
                                    )
                                else:
                                    await query.answer("❌ Error creating link. Admin notified.", show_alert=True)
                                return'''
                                if success:
                                # 1. Extract and SANITIZE user details to prevent HTML crashes
                                    first_name = str(order.get('first_name', 'User')).replace('<', '&lt;').replace('>', '&gt;')
                                    raw_username = order.get('username')
                                    username_display = f" (@{raw_username})" if raw_username else ""
                                    username_display = username_display.replace('<', '&lt;').replace('>', '&gt;')
                                    
                                    u_id = order.get('user_id', 'Unknown')
                                    plan_name = str(order.get('plan_name', 'Premium Plan')).replace('<', '&lt;').replace('>', '&gt;')
                                    amount = order.get('amount', '0')
                                    
                                    # 2. Build the detailed Admin Quote Box
                                    admin_msg = f"""🤖 <b>AUTO-APPROVED RAZORPAY</b> ✅

<blockquote>📋 <b>Order ID:</b> <code>{order_id}</code>
👤 <b>User:</b> {first_name}{username_display}
🆔 <b>User ID:</b> <code>{u_id}</code>
🛍️ <b>Plan:</b> {plan_name}
💰 <b>Amount:</b> ₹{amount}</blockquote>

<i>The gateway confirmed payment and the user was automatically sent their invite link.</i>

🛠️ <b>Admin Quick Actions:</b>
Kick User & Revoke Link:
<code>/revoke {order_id}</code>

Delete User Data:
<code>/deleteuser {u_id}</code>"""

                                # 3. Send and Log
                                try:
                                    await context.bot.send_message(
                                        chat_id=ADMIN_CHAT_ID, 
                                        text=admin_msg, 
                                        parse_mode='HTML'
                                    )
                                    print(f"✅ [ADMIN NOTIFIED] Auto-approval message sent for {order_id}")
                                except Exception as e:
                                    print(f"⚠️ [ADMIN NOTIFY FAILED] Telegram rejected the admin message: {e}")
                            else:
                                # 🚨 THE FIX: 'query' doesn't exist here! Send the error to the Admin instead!
                                try:
                                    fail_msg = f"❌ <b>AUTO-APPROVAL FAILED</b>\n\nOrder <code>{order_id}</code> was paid via Razorpay, but the bot failed to generate the invite link! Please manually send the link to User ID: <code>{order.get('user_id')}</code>."
                                    await context.bot.send_message(
                                        chat_id=ADMIN_CHAT_ID, 
                                        text=fail_msg,
                                        parse_mode='HTML'
                                    )
                                    print(f"❌ [AUTO-APPROVE FAILED] Alerted admin about {order_id}")
                                except Exception:
                                    pass
                            return

            except Exception as e:
                logger.error(f"Error checking Razorpay manually: {e}")

        await query.answer("🔄 Payment not received yet. Please wait a moment or use the Contact Admin button below.", show_alert=True) 

    elif query.data == 'back_main':
        await clean_abandoned_orders(context, query.from_user.id) 
        try:
            await query.message.delete()
        except: pass
        await start(update, context)          
      
    elif query.data == 'stats_main':
        await show_bot_stats(query, context)
        
    elif query.data.startswith('stats_approved_'):
        parts = query.data.split('_')
        page = int(parts[2]) if len(parts) > 2 else 0
        await show_stats_approved(query, context, page)
        
    elif query.data.startswith('stats_pending_'):
        parts = query.data.split('_')
        index = int(parts[2]) if len(parts) > 2 else 0
        await show_stats_pending(query, context, index)
        
    elif query.data == 'stats_revenue':
        await show_stats_revenue(query, context, 'main')
        
    elif query.data == 'stats_rev_upi':
        await show_stats_revenue(query, context, 'upi')
        
    elif query.data == 'stats_rev_gateway':
        await show_stats_revenue(query, context, 'gateway')
        
    elif query.data == 'stats_links':
        await show_stats_links(query, context)
        
    elif query.data == 'stats_close':
        try:
            await query.message.delete()
        except:
            pass
    elif query.data.startswith('deck_approve_'):
        order_id = query.data.replace('deck_approve_', '')
        await handle_deck_action(update, context, order_id, 'approve')
        
    elif query.data.startswith('deck_reject_'):
        order_id = query.data.replace('deck_reject_', '')
        await handle_deck_action(update, context, order_id, 'reject')

    elif query.data == 'admin_toggle_cache':
        current_state = settings_db.get('cache_translations', True)
        settings_db['cache_translations'] = not current_state
        save_db(SETTINGS_FILE, settings_db)
        
        new_state = "ON" if not current_state else "OFF"
        await query.answer(f"Translation Cache is now {new_state}!", show_alert=True)
        await show_dashboard(update, context)    

    elif query.data.startswith('lang_page_'):
        page = int(query.data.split('_')[2])
        await show_language_menu(update, context, page)

    elif query.data.startswith('setlang_'):
        selected_lang = query.data.replace('setlang_', '')
        user_id = str(query.from_user.id)
        if user_id not in users_db:
            users_db[user_id] = {}
            
        users_db[user_id]['lang'] = selected_lang
        save_db(USERS_FILE, users_db)
        await start(update, context)

async def show_how_it_works(query, context):
    #Show instructions
    user_id = query.from_user.id    
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    message = f"""
❓ <b>How It Works</b>

<b>Step 1: Join Membership</b>
Click "Join Membership" button

<b>Step 2: Get QR Code</b>
Click "Get Access Now" to see payment QR

<b>Step 3: Pay via UPI</b>
Scan QR with any UPI app and pay ₹{MEMBERSHIP_PRICE}

<b>Step 4: Send Screenshot</b>
Click "✅ I Have Paid" and send payment screenshot

<b>Step 5: Admin Approval</b>
Admin verifies payment (usually within 1-2 hours)

<b>Step 6: Get Access</b>
After approval, you get one-time invite link

<b>Step 7: Join Channel</b>
Click link and join premium channel!

⚡ <b>Safe & Secure!</b> Admin verifies every payment.

🔒 <b>One-time links</b> - Cannot be shared.
"""
    final_message = await smart_translate(message, user_lang)
    btn_start = await smart_translate("🚀 Get Started", user_lang)
    btn_back = await smart_translate("🔙 Back", user_lang)

    keyboard = [
        [InlineKeyboardButton(btn_start, callback_data='join_membership')],
        [InlineKeyboardButton(btn_back, callback_data='back_main')],
    ]
    if query.message.text:
        try:
            await query.edit_message_text(
                final_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Edit error: {e}")
    else:
        chat_id = query.message.chat_id
        try:
            await query.message.delete()
        except:
            pass
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=final_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML',
                protect_content=True
            )
        except Exception as e:
            logger.error(f"Send error: {e}")

async def show_upi_selection(query, context, order_id):
    #   Shows dynamic multi-UPI selection menu
    user_id = query.from_user.id
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    order = orders_db.get(order_id)
    upi_ids = settings_db.get('upi_ids', [])
    
    if not upi_ids and settings_db.get('upi_id'):
        upi_ids = [settings_db.get('upi_id')]
    if len(upi_ids) <= 1:
        await show_payment_screen(query, context, order_id, 0)
        return

    plan_id = order.get('plan_id')
    plan = plans_db.get(plan_id, {})
    duration = plan.get('duration', 'Lifetime')

    msg = f"""🏦 <b>SELECT PAYMENT METHOD</b>

<blockquote>🛍️ <b>Plan:</b> {order.get('plan_name')}
💰 <b>Amount:</b> ₹{order.get('amount')}
⏳ <b>Duration:</b> {duration}
📋 <b>Order ID:</b> <code>{order_id}</code></blockquote>

👇 <i>Choose a UPI gateway below to generate your QR Code:</i>"""

    final_msg = await smart_translate(msg, user_lang)
    raw_keyboard = []
    buttons = []
    for i, upi in enumerate(upi_ids):
        btn_text = await smart_translate(f"🏦 Option {i+1}", user_lang)
        buttons.append({"text": btn_text, "callback_data": f"select_upi_{order_id}_{i}", "style": "primary"})
        
    for i in range(0, len(buttons), 2):
        raw_keyboard.append(buttons[i:i+2])
        
    btn_back = await smart_translate("🔙 Back", user_lang)
    raw_keyboard.append([{"text": btn_back, "callback_data": f"get_access_{order['plan_id']}", "style": "danger"}])
    
    try:
        if query.message.text:
            await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, final_msg, raw_keyboard, message_id=query.message.message_id)
        else:
            try: await query.message.delete()
            except: pass
            await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, final_msg, raw_keyboard)
    except Exception as e:
        logger.error(f"Error showing UPIs: {e}")


async def clean_abandoned_orders(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    #Hunts down and deletes abandoned checkouts, messages, and timers
    orders_to_delete = []
    
    for oid, order in orders_db.items():
        if str(order.get('user_id')) == str(user_id):
            status = order.get('status')
            if status in ['not paid', 'not paid gateway']:
                orders_to_delete.append((oid, order))

    if not orders_to_delete: 
        return 

    for oid, order in orders_to_delete:
        status_msg_id = order.get('status_msg_id')
        print(f"🗑️ Timer trying to delete Gateway Message ID: {status_msg_id}")
        if status_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=status_msg_id)
            except Exception:
                pass 
        confirming_msg_id = order.get('confirming_msg_id')
        if confirming_msg_id:
            try: await context.bot.delete_message(chat_id=user_id, message_id=confirming_msg_id)
            except Exception: pass
        qr_msg_id = order.get('qr_msg_id')
        print(f"🗑️ Timer trying to delete QR Message ID: {qr_msg_id}")
        if qr_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=qr_msg_id)
            except Exception:
                pass
                
        if context.job_queue:
            for timer_name in [f"timeout_{oid}", f"gateway_timeout_{oid}"]:
                current_jobs = context.job_queue.get_jobs_by_name(timer_name)
                for job in current_jobs:
                    job.schedule_removal()
                    logger.info(f"🛑 Terminated background timer '{timer_name}'")

        del orders_db[oid]

    save_db(ORDERS_FILE, orders_db)
    logger.info(f"🧹 Cleaned up {len(orders_to_delete)} abandoned orders for user {user_id}")

async def direct_pay_timeout_task(context: ContextTypes.DEFAULT_TYPE):
        #JobQueue task: Checks if order is paid, deletes and notifies if not
    user_id = context.job.data['user_id']
    order_id = context.job.data['order_id']
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    print(f"🚨 [TIMER FINISHED] Checking order {order_id} for user {user_id}")
    order = orders_db.get(order_id)
    if not order:
        print(f"❌ [ABORT] Order {order_id} no longer exists in the database. Someone deleted it!")
        return
    status = order.get('status')
    has_screenshot = order.get('screenshot_uploaded')
    if order and order.get('status') == 'not paid' and not order.get('screenshot_uploaded'):
        qr_msg_id = order.get('qr_msg_id')
        if qr_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=qr_msg_id)
            except Exception as e:
                print(f"⚠️ [DIRECT PAY] Telegram refused to delete QR code: {e}")

        print("✅ [ACTION] Order is pending with no screenshot. Triggering deletion and message...")
        del orders_db[order_id]
        save_db(ORDERS_FILE, orders_db)
        logger.info(f"👻 Ghost order {order_id} automatically deleted due to timeout.")
        

        timeout_msg = (
            f"⏳ <b>PAYMENT TIMEOUT</b>\n\n"
            f"Your payment session for Order <code>{order_id}</code> has expired because no screenshot was uploaded in time.\n\n"
            f"<i>If money was deducted, it is safe. Just click below to generate a new order or contact the admin.</i>"
        )
        
        final_timeout_msg = await smart_translate(timeout_msg, user_lang)
        btn_try = await smart_translate("🔄 Try Again", user_lang)
        btn_contact = await smart_translate("📞 Contact Admin", user_lang)
        
        keyboard = [
            [InlineKeyboardButton(btn_try, callback_data="join_membership")],
            [InlineKeyboardButton(btn_contact, callback_data="contact_admin")]
        ]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=final_timeout_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send timeout notification to {user_id}: {e}")
    else:
        print("❌ [ABORT] Order was already paid or status changed. Timer ignoring it.")        

async def gateway_timeout_task(context: ContextTypes.DEFAULT_TYPE):
    #JobQueue task: Cleans up expired Razorpay links after 15 mins
    user_id = context.job.data['user_id']
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    order_id = context.job.data['order_id']
    
    order = orders_db.get(order_id)
    if order and order.get('status') == 'not paid gateway':
        status_msg_id = order.get('status_msg_id')
        
        if status_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=status_msg_id)
            except Exception as e:
                print(f"⚠️ [GATEWAY TIMER] Failed to delete: {e}")
        confirming_msg_id = order.get('confirming_msg_id')   
        print(f"🗑️ [GATEWAY TIMER] Attempting to delete Confirming Text ID: {confirming_msg_id}")     
        if confirming_msg_id:
            try: await context.bot.delete_message(chat_id=user_id, message_id=confirming_msg_id)
            except Exception: pass        
        # Wipe the order
        del orders_db[order_id]
        save_db(ORDERS_FILE, orders_db)
        logger.info(f"👻 Gateway timeout for {order_id}. Order and loading message deleted.")
        
        # Notify the user 
        raw_timeout = f"⏳ <b>PAYMENT LINK EXPIRED</b>\n\nYour Razorpay link for Order <code>{order_id}</code> has expired. Please generate a new one if you wish to continue."
        final_timeout = await smart_translate(raw_timeout, user_lang)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=final_timeout,
                parse_mode='HTML'
            )
        except Exception:
            pass

async def auto_expire_task(context: ContextTypes.DEFAULT_TYPE):
    #JobQueue task: Wakes up when a plan expires, kicks the user, and sends a quote box
    data = context.job.data
    order_id = data['order_id']
    user_id = data['user_id']
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    
    print(f"⏰ [TIMER WOKE UP] Checking expiry for Order {order_id}...")
    order = orders_db.get(order_id)
    if not order:
        print(f"🛑 [TIMER ABORTED] Order {order_id} no longer exists in database.")
        return 
    current_status = order.get('status')
    if current_status not in ['approved', 'active']:
        print(f"🛑 [TIMER ABORTED] Order {order_id} is currently '{current_status}', not active. Ignoring!")
        return 

    orders_db[order_id]['status'] = 'expired'
    orders_db[order_id]['expired_at'] = datetime.now().isoformat()
    save_db(ORDERS_FILE, orders_db)
    
    if str(user_id) in members_db:
        members_db[str(user_id)]['active'] = False
        save_db(MEMBERS_FILE, members_db)

    try:
        channel_id = settings_db.get('channel_id') or PREMIUM_CHANNEL_ID
        if channel_id:
            await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
            old_link = order.get('invite_link')
            if old_link:
                try:
                    await context.bot.revoke_chat_invite_link(chat_id=channel_id, invite_link=old_link)
                except Exception as e:
                    print(f"⚠️ Link already revoked or not found: {e}")
                    
            print(f"🚪 [SUCCESS] Auto-kicked {user_id} and destroyed link for order {order_id}")
    except Exception as e:
        logger.error(f"Failed to auto-kick user {user_id}: {e}")

    plan_name = order.get('plan_name', 'Premium Plan')
    amount = order.get('amount', 0)
    
    expire_msg = f"""⚠️ <b>MEMBERSHIP EXPIRED</b> ⚠️

Hello {order.get('first_name', 'User')}, your premium access has ended.

<blockquote>📋 <b>Order ID:</b> <code>{order_id}</code>
🛍️ <b>Plan:</b> {plan_name}
💰 <b>Amount:</b> ₹{amount}
🛑 <b>Status:</b> Expired
⏰ <b>Ended At:</b> {datetime.now().strftime('%d %b %Y, %I:%M %p')}</blockquote>

<i>We hope you enjoyed the premium content! If you wish to regain access, please purchase a new plan using the button below.</i>"""

    final_expire_msg = await smart_translate(expire_msg, user_lang)
    btn_renew = await smart_translate("🚀 Renew Membership", user_lang)
    btn_contact = await smart_translate("📞 Contact Admin", user_lang)

    keyboard = [
        [InlineKeyboardButton(btn_renew, callback_data='join_membership')],
        [InlineKeyboardButton(btn_contact, callback_data='contact_admin')]
    ]

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=final_expire_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.warning(f"Could not send expiry notification to {user_id}: {e}")

async def show_membership_plan(query, context):
    """Show dynamic plans in 2-column HTML layout using direct API bypass"""
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    raw_keyboard = []
    
    if not plans_db:
        message = "❌ <i>No membership plans are available right now. Please contact the admin.</i>"
    else:
        # --- HTML MESSAGE ---
        message = "💎 <b>PREMIUM MEMBERSHIP PLANS</b> 💎\n\n"
        message += "<blockquote><b>⚡ AVAILABLE PLANS:</b>\n"
        message += "┌───────────────────\n"
        for plan_id, plan_data in plans_db.items():
            duration = plan_data.get('duration', 'Lifetime') 
            message += f"├ 💳 <b>{plan_data['name']}</b> ({duration}) » ₹{plan_data['price']}\n"
        message += "└───────────────────</blockquote>\n\n"
        
        # 2. Detailed Descriptions in a separate Blockquote
        message += "<blockquote><b>📋 PLAN DETAILS:</b>\n\n"
        for plan_id, plan_data in plans_db.items():
            # in the dashboard instead of * and _ when typing descriptions!
            desc = plan_data.get('desc', 'Get exclusive premium access to the channel.')
            duration = plan_data.get('duration', 'Lifetime')
            message += f"🔹 <b>{plan_data['name']}</b> [⏳ {duration}]:\n{desc}\n\n"
        message += "</blockquote>\n"
            
        # 3. Footer
        message += (
            "<b>💳 Payment:</b>\n"
            "• Secure UPI\n"
            "• Any UPI app works\n"
            "• Screenshot verification\n"
            "• Admin approval\n\n"
            "<b>🔒 Security:</b>\n"
            "• Manual verification\n"
            "• One-time links\n"
            f"• {INVITE_LINK_EXPIRY_HOURS}h validity\n"
            "• Safe & secure\n\n"
        )
        message += "👇 <b>Choose your plan below:</b>"
        final_message = await smart_translate(message, user_lang)


        plan_buttons = []
        for plan_id, plan_data in plans_db.items():
            btn_text = f"{plan_data['name']} (₹{plan_data['price']})"
            translated_btn_text = await smart_translate(btn_text, user_lang)
            plan_buttons.append({"text": translated_btn_text, "callback_data": f"get_access_{plan_id}", "style": "primary"})

        for i in range(0, len(plan_buttons), 2):
            raw_keyboard.append(plan_buttons[i:i+2])

    btn_how = await smart_translate("❓ How It Works", user_lang)
    btn_back = await smart_translate("🔙 Back", user_lang)       
    raw_keyboard.append([{"text": btn_how, "callback_data": "how_it_works", "style": "success"}])
    raw_keyboard.append([{"text": btn_back, "callback_data": "back_main", "style": "danger"}])
    try:
        if query.message.text:
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=chat_id,
                text=final_message,
                raw_keyboard=raw_keyboard,
                message_id=query.message.message_id
            )
        else:
            try:
                await query.message.delete()
            except:
                pass
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=chat_id,
                text=final_message,
                raw_keyboard=raw_keyboard
            )
    except Exception as e:
        logger.error(f"Error showing plans with custom API: {e}")
    
async def choose_payment_method(query, context, plan_id):
#direct vs Gateway payment
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id
    user_lang = users_db.get(user_id, {}).get('lang', 'en')
    if plan_id not in plans_db:
        error_msg = await smart_translate("❌ This plan is no longer available!", user_lang)
        await query.answer(error_msg, show_alert=True)
        return
        
    plan = plans_db[plan_id]
    duration = plan.get('duration', 'Lifetime')
    desc = plan.get('desc', 'Premium Access')

    message = (
        f"🛒 <b>CHECKOUT</b>\n\n"
        f"<blockquote>🛍️ <b>Plan:</b> {plan['name']}\n"
        f"💰 <b>Amount:</b> ₹{plan['price']}\n"
        f"⏳ <b>Duration:</b> {duration}\n"
        f"ℹ️ <b>Plan Info:</b> <i>{desc}</i></blockquote>\n\n"
        f"👇 <i>Please choose your preferred payment method:</i>"
    )
    
    final_message = await smart_translate(message, user_lang)
    btn_direct = await smart_translate("🏦 Pay Direct (UPI / QR)", user_lang)
    btn_gateway = await smart_translate("💳 Pay via Gateway (Card / NetBanking)", user_lang)
    btn_cancel = await smart_translate("❌ Cancel", user_lang)

    raw_keyboard = [
        [{"text": btn_direct, "callback_data": f"pay_direct_{plan_id}", "style": "primary"}],
        [{"text": btn_gateway, "callback_data": f"pay_gateway_{plan_id}", "style": "success"}],
        [{"text": btn_cancel, "callback_data": "join_membership", "style": "danger"}]
    ]
    
    try:
        await send_colored_settings(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=chat_id,
            text=final_message,
            raw_keyboard=raw_keyboard,
            message_id=query.message.message_id
        )
    except Exception as e:
        logger.error(f"Error showing payment choice: {e}")


async def initiate_payment(query, context, plan_id):
    """Create order based on selected dynamic plan"""
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    await clean_abandoned_orders(context, user_id)
    # Verify the plan still exists
    if plan_id not in plans_db:
        error_msg = await smart_translate("❌ This plan is no longer available!", user_lang)
        await query.answer(error_msg, show_alert=True)
        await show_membership_plan(query, context)
        return
        
    selected_plan = plans_db[plan_id]
    plan_price = selected_plan['price']
    plan_name = selected_plan['name']

    order_id = generate_order_id(user_id)
    
    orders_db[order_id] = {
        'user_id': user_id,
        'username': username,
        'first_name': query.from_user.first_name,
        'amount': plan_price,   
        'plan_name': plan_name,
        'plan_id': plan_id,   
        'status': 'not paid',
        'created_at': datetime.now().isoformat(),
        'screenshot_uploaded': False
    }
    save_db(ORDERS_FILE, orders_db)
    
    logger.info(f"📦 Order {order_id} created by {username} for {plan_name} (₹{plan_price})")
    context.job_queue.run_once(
        direct_pay_timeout_task, 
        when=600, # 10 minutes
        data={'user_id': user_id, 'order_id': order_id},
        name=f"timeout_{order_id}"
    )
    await show_upi_selection(query, context, order_id)

async def initiate_gateway_payment(query, context, plan_id):
#Phase 2 & 3: Generate Razorpay Link and handoff to User
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')

    plan = plans_db[plan_id]
    order_id = generate_order_id(user_id)
    
    #key fetching
    key_id = settings_db.get('rzp_key_id')
    key_secret = settings_db.get('rzp_key_secret')
    
    if not key_id or not key_secret:
        err_msg = await smart_translate("❌ Gateway is currently unavailable. Please use Direct Payment.", user_lang)
        await query.answer(err_msg, show_alert=True)
        return

    # Convert to Paise
    amount_in_paise = int(plan['price']) * 100
    
    url = "https://api.razorpay.com/v1/payment_links"
    payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "description": f"{BOT_NAME} - {plan['name']}",
        "expire_by": int(time.time()) + (16 * 60), # link kills after 16 mins
        "notes": {
            "telegram_id": str(user_id),
            "order_id": order_id 
        }
    }

    auth = aiohttp.BasicAuth(key_id, key_secret)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, auth=auth) as response:
                rzp_data = await response.json()
                
                if 'short_url' not in rzp_data:
                    logger.error(f"Razorpay Error: {rzp_data}")
                    await query.answer("❌ Failed to generate payment link.", show_alert=True)
                    return
                
                short_url = rzp_data['short_url']
                rzp_link_id = rzp_data['id']
                
    except Exception as e:
        logger.error(f"Razorpay Request Error: {e}")
        await query.answer("❌ Connection error with gateway.", show_alert=True)
        return

    # Save it
    orders_db[order_id] = {
        'user_id': user_id,
        'username': username,
        'first_name': query.from_user.first_name,
        'amount': plan['price'],
        'plan_name': plan['name'],
        'status': 'not paid gateway',
        'method': 'razorpay',
        'rzp_link_id': rzp_link_id, 
        'created_at': datetime.now().isoformat()
    }

    # The Handoff UI
    message = f"""
💳 <b>SECURE GATEWAY CHECKOUT</b>

🛍️ <b>Plan:</b> {plan['name']}
💰 <b>Amount:</b> ₹{plan['price']}
📋 <b>Order ID:</b> <code>{order_id}</code>

👇 <i>Click the link below to securely pay via Razorpay (Cards, UPI, Netbanking).</i>
"""
    final_message = await smart_translate(message, user_lang)
    btn_pay = await smart_translate("🔗 Pay Securely Now", user_lang)
    btn_check = await smart_translate("🔄 Check Payment Status", user_lang)
    btn_contact = await smart_translate("📞 Contact Admin", user_lang)
    btn_cancel = await smart_translate("🔙 Cancel", user_lang)

    raw_keyboard = [
        [{"text": btn_pay, "url": short_url, "style": "success"}],
        [{"text": btn_check, "callback_data": f"verify_rzp_{order_id}", "style": "primary"}],
        [{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}],
        [{"text": btn_cancel, "callback_data": "join_membership", "style": "danger"}]
    ]

    await send_colored_settings(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=query.message.chat_id,
        text=final_message,
        raw_keyboard=raw_keyboard,
        message_id=query.message.message_id
    )
    confirm_text = "⏳ <b>Confirming your payment...</b>\n\n<i>(This may take 1-2 minutes. Please complete the payment on Razorpay and be patient)</i>"
    final_confirm = await smart_translate(confirm_text, user_lang)

    confirm_msg = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=final_confirm,
        parse_mode='HTML'
    )
    gateway_msg_id = query.message.message_id
    orders_db[order_id]['status_msg_id'] = gateway_msg_id
    orders_db[order_id]['confirming_msg_id'] = confirm_msg.message_id
    save_db(ORDERS_FILE, orders_db)
    print(f"✅ SUCCESS: Saved Gateway Message ID [{gateway_msg_id}] & Confirming Message ID [{confirm_msg.message_id}] for Order {order_id}")
    if context.job_queue:
        context.job_queue.run_once(
            gateway_timeout_task, 
            when=15 * 60, # 15 minutes
            data={'user_id': user_id, 'order_id': order_id},
            name=f"gateway_timeout_{order_id}"
        )
    asyncio.create_task(auto_verify_background_task(context, user_id, order_id, rzp_link_id))


async def show_payment_screen(query, context, order_id, upi_idx=0):
#Display QR code 

    user_id = str(query.from_user.id)
    user_lang = users_db.get(user_id, {}).get('lang', 'en')

    order = orders_db[order_id]
    upi_ids = settings_db.get('upi_ids', [])
    if not upi_ids: 
        current_upi = settings_db.get('upi_id', UPI_ID)
    else: 
        current_upi = upi_ids[upi_idx] if upi_idx < len(upi_ids) else upi_ids[0]
        
    orders_db[order_id]['selected_upi'] = current_upi
    save_db(ORDERS_FILE, orders_db)
    upi_string = create_upi_string(order_id, order['amount'], current_upi)
    qr_image = generate_qr_code(upi_string)
    
    if not qr_image:
        error_msg = await smart_translate(f"❌ Error! Contact: {ADMIN_USERNAME}", user_lang)
        await query.message.reply_text(
            error_msg,
            parse_mode='HTML'
        )
        return
        
    # Format 
    username_display = f" (@{order.get('username')})" if order.get('username') else ""
    user_display = f"{order.get('first_name', 'User')}{username_display}"
    current_time = datetime.now().strftime('%d %b %Y, %I:%M %p')
    plan_name = order.get('plan_name', 'Premium Membership')
    
    # --- Main Message ---
    payment_message = f"""
💳 <b>PAYMENT DETAILS</b>

<blockquote>👤 <b>User:</b> {user_display}
🛍️ <b>Plan:</b> {plan_name}
📋 <b>Order ID:</b> <code>{order_id}</code>
💰 <b>Amount:</b> ₹{order['amount']}
⏰ <b>Time:</b> {current_time}</blockquote>

<b>📱 INSTRUCTIONS:</b>

1️⃣ Scan QR code with UPI app
2️⃣ Pay ₹{order['amount']}
3️⃣ Take screenshot of payment
4️⃣ Click "✅ I Have Paid" below
5️⃣ Send screenshot to bot
6️⃣ Wait for admin approval

⏳ <b>Approval Time:</b> 1-2 hours

🏦 <b>UPI ID:</b> <code>{current_upi}</code>

<i>Need help?</i> {ADMIN_USERNAME}
"""
    
    #translate
    final_message = await smart_translate(payment_message, user_lang)
    btn_paid = await smart_translate("✅ I Have Paid", user_lang)
    btn_change = await smart_translate("🔄 Change UPI", user_lang)
    btn_contact = await smart_translate("📞 Contact Admin", user_lang)

    raw_keyboard = [
        [{"text": btn_paid, "callback_data": f"confirm_payment_{order_id}", "style": "success"}]
    ]
    if len(upi_ids) > 1:
        raw_keyboard.append([{"text": btn_change, "callback_data": f"change_upi_{order_id}", "style": "primary"}])
        
    raw_keyboard.append([{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}])
    

    try:
        sent_msg = await send_colored_photo(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=query.message.chat_id,
            photo_bytes=qr_image,
            caption=final_message,
            raw_keyboard=raw_keyboard
        )
        if sent_msg and isinstance(sent_msg, dict) and sent_msg.get('ok'):
            orders_db[order_id]['qr_msg_id'] = sent_msg['result']['message_id']
            save_db(ORDERS_FILE, orders_db)
        try:
            await query.message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error showing payment screen: {e}")

async def auto_verify_background_task(context: ContextTypes.DEFAULT_TYPE, user_id: int, order_id: str, rzp_link_id: str):
#Silently checks Razorpay every 10 seconds (after a 1-minute delay) for exactly 15 minutes
    key_id = settings_db.get('rzp_key_id')
    key_secret = settings_db.get('rzp_key_secret')
    
    if not key_id or not key_secret:
        return
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    url = f"https://api.razorpay.com/v1/payment_links/{rzp_link_id}"
    auth = aiohttp.BasicAuth(key_id, key_secret)

    # The 15-Minute Synchronized Loop
    # Wait 60 seconds first, then check every 10 seconds for the remaining 14 minutes.
    # Total API calls:85 per user
    check_intervals = [60] + [10] * 84

    for wait_time in check_intervals:
        await asyncio.sleep(wait_time)
        order = orders_db.get(order_id)
        if not order or order.get('status') in ['approved', 'rejected', 'expired']:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth) as response:
                    if response.status == 429:
                        logger.warning(f"Rate limited by Razorpay for order {order_id}! Pausing 10s...")
                        await asyncio.sleep(10)
                        continue
                        
                    rzp_data = await response.json()
                    link_status = rzp_data.get('status')
                    
                    if link_status == 'paid':
                        order = orders_db[order_id]
                        if order.get('is_processing'):
                            print(f"🔒 [TIMER] Order {order_id} is already being processed by the manual button. Timer aborting gracefully.")
                            return
                        orders_db[order_id]['is_processing'] = True
                        save_db(ORDERS_FILE, orders_db)
                        confirming_msg_id = order.get('confirming_msg_id')
                        current_mode = settings_db.get('rzp_mode', 'manual').lower()
                        if confirming_msg_id:
                            try:
                                await context.bot.delete_message(chat_id=order['user_id'], message_id=confirming_msg_id)
                                print(f"🗑️ [SUCCESS] Deleted Confirming message for Order {order_id}")
                            except Exception as e:
                                pass
                        if current_mode == 'auto':
                            try:
                                # 1. Process Approval
                                success = await process_approval(context, order_id, message_id_to_edit=order.get('status_msg_id'))
                                
                                if success:
                                    import html
                                    u_id = str(order.get('user_id', 'Unknown'))
                                    first_name = html.escape(str(order.get('first_name', 'User')))
                                    raw_username = order.get('username', '')
                                    username_display = f" (@{html.escape(raw_username)})" if raw_username else ""
                                    plan_name = html.escape(str(order.get('plan_name', 'Premium Plan')))
                                    amount = str(order.get('amount', '0'))
                                    
                                    admin_msg = (
                                        f"🤖 <b>AUTO-APPROVED RAZORPAY (BACKGROUND)</b> ✅\n\n"
                                        f"<blockquote>📋 <b>Order ID:</b> <code>{order_id}</code>\n"
                                        f"👤 <b>User:</b> {first_name}{username_display}\n"
                                        f"🆔 <b>User ID:</b> <code>{u_id}</code>\n"
                                        f"🛍️ <b>Plan:</b> {plan_name}\n"
                                        f"💰 <b>Amount:</b> ₹{amount}</blockquote>\n\n"
                                        f"<i>The gateway confirmed payment in the background and the user was sent their invite link.</i>\n\n"
                                        f"🛠️ <b>Admin Quick Actions:</b>\n"
                                        f"Kick User & Revoke Link:\n"
                                        f"<code>/revoke {order_id}</code>\n\n"
                                        f"Delete User Data:\n"
                                        f"<code>/deleteuser {u_id}</code>"
                                    )
                                    try:
                                        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode='HTML')
                                        print(f"✅ [ADMIN] Background auto-approve notification sent for {order_id}")
                                    except Exception as e1:
                                        safe_msg = f"🤖 AUTO-APPROVED RAZORPAY (BACKGROUND) ✅\nOrder: {order_id}\nUser: {first_name} ({u_id})\nRevoke: /revoke {order_id}"
                                        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=safe_msg)
                                        print(f"✅ [ADMIN] Background safe-text fallback sent.")

                                else:
                                    fail_msg = f"❌ AUTO-APPROVAL FAILED\n\nOrder {order_id} paid via Razorpay in background, but link generation failed. User ID: {order.get('user_id')}"
                                    try:
                                        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=fail_msg)
                                    except Exception: pass

                            except Exception as critical_crash:
                                logger.error(f"Background Auto-Approve Crash for {order_id}: {critical_crash}")
                                crash_report = f"⚠️ CRITICAL BACKGROUND CRASH ⚠️\n\nOrder {order_id} was paid, but the background timer crashed!\n\nError: {critical_crash}"
                                try:
                                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=crash_report)
                                except Exception: pass
                            
                            return

                        elif current_mode == 'manual':
                            orders_db[order_id]['status'] = 'pending_gateway'
                            save_db(ORDERS_FILE, orders_db)
                            if context.job_queue:
                                current_jobs = context.job_queue.get_jobs_by_name(f"gateway_timeout_{order_id}")
                                for job in current_jobs:
                                    job.schedule_removal()

                            keyboard = [[
                                InlineKeyboardButton("✅ Approve", callback_data=f'btn_approve_{order_id}'),
                                InlineKeyboardButton("❌ Reject", callback_data=f'btn_reject_{order_id}')
                            ]]
                            
                            username_display = f" (@{order.get('username')})" if order.get('username') else ""
                            current_time = datetime.now().strftime('%d %b %Y, %I:%M %p')
                            plan_name = order.get('plan_name', 'Premium Plan')

                            admin_msg = f"""💳 <b>RAZORPAY VERIFIED (BACKGROUND)</b>

<blockquote>📋 <b>Order:</b> <code>{order_id}</code>
👤 <b>User:</b> {order.get('first_name', 'User')}{username_display}
🛍️ <b>Plan:</b> {plan_name}
💰 <b>Amount:</b> ₹{order['amount']}
⏰ <b>Time:</b> {current_time}</blockquote>

<i>Please approve to send the access link:</i>"""

                            await context.bot.send_message(
                                chat_id=ADMIN_CHAT_ID,
                                text=admin_msg,
                                reply_markup=InlineKeyboardMarkup(keyboard), 
                                parse_mode='HTML'  # 🚀 Switched to HTML for blockquotes
                            )
                            
                            user_msg = f"""✅ <b>PAYMENT RECEIVED!</b> 🎉

Your bank has cleared the payment for Order <code>{order_id}</code>.

<blockquote>👤 <b>User:</b> {order.get('first_name', 'User')}{username_display}
🆔 <b>User ID:</b> <code>{order['user_id']}</code>
🛍️ <b>Plan:</b> {order.get('plan_name')}
💰 <b>Amount:</b> ₹{order['amount']}
⏰ <b>Time:</b> {current_time}
💳 <b>Method:</b> <i>Razorpay Gateway</i></blockquote>

⏳ We are just waiting for the Admin to manually approve your access. You will receive your link shortly!"""
                            
                            final_user_msg = await smart_translate(user_msg, user_lang)
                            status_msg_id = order.get('status_msg_id')
                            try:
                                if status_msg_id:
                                    await context.bot.edit_message_text(chat_id=order['user_id'], message_id=status_msg_id, text=final_user_msg, parse_mode='HTML')
                                else:
                                    raise Exception("No status message ID")
                            except Exception:
                                await context.bot.send_message(chat_id=order['user_id'], text=final_user_msg, parse_mode='HTML')
                            return    
                        
                    elif link_status in ['cancelled', 'expired']:
                        break
        except Exception as e:
            logger.error(f"Background Check Error for {order_id}: {e}")

    # TIMEOUT / FAILURE CLEANUP
    order = orders_db.get(order_id)
    if order and order.get('status') == 'pending_gateway':
        orders_db[order_id]['status'] = 'expired'
        save_db(ORDERS_FILE, orders_db)
        
        status_msg_id = order.get('status_msg_id')
        if status_msg_id:
            fail_msg = "❌ *PAYMENT TIMEOUT OR FAILED*\n\nYour payment session expired or failed. If money was deducted, it will be refunded automatically by your bank in 3-5 days.\n\n👇 Click below to try again."
            final_fail_msg = await smart_translate(fail_msg, user_lang)
            btn_try_again = await smart_translate("🔄 Try Again", user_lang)
            keyboard = [[InlineKeyboardButton(btn_try_again, callback_data="join_membership")]]
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id, message_id=status_msg_id, 
                    text=final_fail_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML'
                )
            except Exception:
                pass

async def revoke_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to surgically revoke a specific Order ID"""
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    if not is_coadmin(update.effective_user): 
        return

    # Check if they provided an Order ID
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/revoke <OrderID>`\n"
            "Example: `/revoke ORD123456789`", 
            parse_mode='Markdown'
        )
        return

    target_order_id = context.args[0]

    # Check if the order exists
    if target_order_id not in orders_db:
        await update.message.reply_text(f"❌ Could not find Order `{target_order_id}` in the database.", parse_mode='Markdown')
        return

    order = orders_db[target_order_id]
    current_status = order.get('status')
    user_id = order.get('user_id')

    # Prevent double-revoking
    if current_status == 'revoked':
        await update.message.reply_text(f"⚠️ Order `{target_order_id}` is already revoked!", parse_mode='Markdown')
        return

    # 1. Update Database
    orders_db[target_order_id]['status'] = 'revoked'
    orders_db[target_order_id]['revoked_at'] = datetime.now().isoformat()
    save_db(ORDERS_FILE, orders_db)

    kick_msg = ""
    
    # 2. Attempt to kick from channel if it was an active/approved order
    """ if current_status in ['approved', 'active']:
        try:
            channel_id = settings_db.get('channel_id') or PREMIUM_CHANNEL_ID
            if channel_id:
                # Banning and immediately unbanning effectively "kicks" them out
                await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
                await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
                old_link = order.get('invite_link')
                if old_link:
                    try:
                        await context.bot.revoke_chat_invite_link(chat_id=channel_id, invite_link=old_link)
                    except Exception as e:
                        pass # Ignore if already revoked
                    
                kick_msg = "\n🚪 _User was successfully kicked and their invite link was destroyed._"
        except Exception as e:
            logger.error(f"Error kicking user during revoke: {e}")
            kick_msg = "\n⚠️ _Could not kick user from channel (Check bot permissions)._"
 """
    # 3. Confirm to Admin
    await update.message.reply_text(
        f"✅ *ORDER REVOKED*\n\n"
        f"📋 *Order ID:* `{target_order_id}`\n"
        f"👤 *User ID:* `{user_id}`"
        f"{kick_msg}", 
        parse_mode='Markdown'
    )

    # 4. Notify the User
    try:
        text=f"❌ *Notice:* Your access for Order `{target_order_id}` has been revoked by the administrator."
        final_text= await smart_translate(text, user_lang)
        await context.bot.send_message(
            chat_id=user_id,
            text=final_text,
            parse_mode='Markdown'
        )
    except Exception:
        pass 

async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to kick a user and revoke their database access"""
    if not is_coadmin(update.effective_user): return
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/deleteuser <user_id>` OR `/deleteuser @username`", 
            parse_mode='Markdown'
        )
        return

    target = context.args[0].replace('@', '')
    target_user_id = None
    target_order_id = None
    
    for order_id, data in orders_db.items():
        db_user_id = str(data.get('user_id'))
        db_username = str(data.get('username', '')).lower()
        
        if db_user_id == target or db_username == target.lower():
            target_user_id = data.get('user_id')
            target_order_id = order_id
            if data.get('status') == 'approved':
                break 

    if not target_user_id:
        await update.message.reply_text(f"❌ Could not find *{target}* in the database. Are you sure they bought a plan?", parse_mode='Markdown')
        return

    try:
        channel_id = settings_db.get('channel_id') or os.getenv('PREMIUM_CHANNEL_ID')
        
        if channel_id:
            await context.bot.ban_chat_member(chat_id=channel_id, user_id=target_user_id)
            await context.bot.unban_chat_member(chat_id=channel_id, user_id=target_user_id)
        
        #  Update the Database
        orders_modified = False
        for oid, o_data in orders_db.items():
            if str(o_data.get('user_id')) == str(target_user_id):
                orders_db[oid]['status'] = 'revoked'
                orders_db[oid]['revoked_at'] = datetime.now().isoformat()
                orders_modified = True
                
        if orders_modified:
            save_db(ORDERS_FILE, orders_db)
            
        if str(target_user_id) in members_db:
            members_db[str(target_user_id)]['active'] = False
            save_db(MEMBERS_FILE, members_db)

        #  Confirm to Admin
        await update.message.reply_text(f"✅ *SUCCESS*\n\nUser `{target}` has been kicked from the channel and their database status is set to revoked.", parse_mode='Markdown')
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id, 
                text="❌ *Notice:* Your premium access has been revoked by the administrator.",
                parse_mode='Markdown'
            )
        except Exception:
            pass 

    except Exception as e:
        logger.error(f"Error kicking user: {e}")
        await update.message.reply_text(f"❌ *Failed to kick user from the channel!*\n\nError: `{e}`\n\n_Make sure the bot is an Admin in the channel with 'Ban Users' permission!_", parse_mode='Markdown')


async def request_screenshot(query, context, order_id):
        #Request payment screenshot

    user_id = query.from_user.id
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')

    if order_id not in orders_db:
        err_msg = await smart_translate("❌ Order not found!", user_lang)
        await query.answer(err_msg, show_alert=True)
        return
    
    order = orders_db[order_id]
    
    if order['user_id'] != user_id:
        err_msg = await smart_translate("❌ Not your order!", user_lang)
        await query.answer(err_msg, show_alert=True)
        return
    
    if order['status'] == 'approved':
        success_msg = await smart_translate("✅ Already approved!", user_lang)
        await query.answer(success_msg, show_alert=True)
        return
    
    # Update order
    orders_db[order_id]['waiting_screenshot'] = True
    save_db(ORDERS_FILE, orders_db)
    
    # Store order_id for screenshot handler
    context.user_data['waiting_order_id'] = order_id
    
    first_name = order.get('first_name', 'User')
    username = f" (@{order.get('username')})" if order.get('username') else ""
    
    message = f"""
📸 *SEND PAYMENT SCREENSHOT*

Please send a clear screenshot of your payment.

👤 *User:* {first_name}{username}
📋 *Order ID:* `{order_id}`
💰 *Amount:* ₹{order['amount']}

⏳ *After sending:*
Admin will verify and approve within 1-2 hours.

*Need help?* {ADMIN_USERNAME}
"""
    final_message = await smart_translate(message, user_lang)
    btn_back = await smart_translate("🔙 Back", user_lang)

    keyboard = [
        [InlineKeyboardButton(btn_back, callback_data='back_main')],
    ]
    chat_id = query.message.chat_id
    
    # Delete the QR code 
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"Could not delete message: {e}")
    
    # Send new text message using bot.send_message (not query.message.reply_text)
    try:
        sent_prompt = await context.bot.send_message(
            chat_id=chat_id,
            text=final_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            protect_content=True
        )
        orders_db[order_id]['qr_msg_id'] = sent_prompt.message_id
        save_db(ORDERS_FILE, orders_db)
    except Exception as e:
        logger.error(f"Could not send message: {e}")
    
    # Notify admin
    '''try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⏳ *Payment Screenshot Requested*\n\n"
                 f"📋 Order: `{order_id}`\n"
                 f"👤 User: {order['first_name']} (@{order['username']})\n"
                 f"💰 Amount: ₹{order['amount']}\n\n"
                 f"Waiting for screenshot...",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Could not notify admin: {e}")'''


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
        #Handle screenshot upload
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')

    order_id = context.user_data.get('waiting_order_id')
    if not order_id:
        return
    if order_id not in orders_db:
        return
    
    order = orders_db[order_id]
    if order['user_id'] != user_id:
        return
    
    # Mark screenshot received
    orders_db[order_id]['screenshot_uploaded'] = True
    orders_db[order_id]['status'] = 'pending'
    orders_db[order_id]['screenshot_time'] = datetime.now().isoformat()
    save_db(ORDERS_FILE, orders_db)
    
    # Clear waiting status
    context.user_data.pop('waiting_order_id', None)
    if context.job_queue:
        current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{order_id}")
        for job in current_jobs:
            job.schedule_removal()

    # Confirm to user
    raw_confirm_msg = (
        f"✅ <b>Screenshot Received!</b>\n\n"
        f"📋 <b>Order:</b> <code>{order_id}</code>\n\n"
        f"⏳ Your payment is under review.\n"
        f"Admin will approve within 1-2 hours.\n\n"
        f"You'll get a notification when approved!\n\n"
        f"Thank you for your patience! 🙏"
    )
    final_confirm_msg = await smart_translate(raw_confirm_msg, user_lang)
    await update.message.reply_text(
        final_confirm_msg, 
        parse_mode='HTML', 
        protect_content=True
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f'btn_approve_{order_id}'),
            InlineKeyboardButton("❌ Reject", callback_data=f'btn_reject_{order_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Forward to admin with approval buttons
    try:
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=update.message.photo[-1].file_id,
                caption=f"💳 *PAYMENT SCREENSHOT*\n\n"
                        f"📋 Order: `{order_id}`\n"
                        f"👤 User: {order['first_name']} (@{username})\n"
                        f"🆔 User ID: `{user_id}`\n"
                        f"💰 Amount: ₹{order['amount']}\n"
                        f"⏰ Time: {datetime.now().strftime('%d %b, %I:%M %p')}\n\n"
                        f"*Verify payment and approve:*\n"
                        f"`/approve {order_id}`\n\n"
                        f"*Or reject:*\n"
                        f"`/reject {order_id}`",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📸 *Screenshot Received* (but not a photo)\n\n"
                     f"Order: `{order_id}`\n"
                     f"User: {username} ({user_id})\n\n"
                     f"Use: `/approve {order_id}`",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Admin notification error: {e}")

async def process_approval(context, order_id, message_id_to_edit=None):
        #function for all approvals (Manual & Auto)
    if order_id not in orders_db: return False
    
    order = orders_db[order_id]
    user_id = order['user_id']
    user_lang = users_db.get(str(user_id), {}).get('lang', 'en')
    invite_link = await create_single_use_invite_link(context, user_id, order.get('username', 'User'), order_id)
    if not invite_link: return False

    #  Update Database
    orders_db[order_id]['status'] = 'approved'
    orders_db[order_id]['approved_at'] = datetime.now().isoformat()
    orders_db[order_id]['invite_link'] = invite_link
    save_db(ORDERS_FILE, orders_db)
    add_member(user_id, order.get('username', 'User'), order_id)

    first_name = order.get('first_name', 'User')
    username_display = f" (@{order.get('username')})" if order.get('username') else ""
    plan_name = order.get('plan_name', 'Premium Plan')
    amount = order['amount']
    method = "Razorpay Gateway" if order.get('method') == 'razorpay' else "Direct Pay (UPI)"
    current_time = datetime.now().strftime('%d %b %Y, %I:%M %p')

    plan_duration_str = "Lifetime"
    time_delta = None
    
    for p in plans_db.values():
        if p['name'] == plan_name:
            plan_duration_str = p.get('duration', 'Lifetime')
            time_delta = parse_plan_duration(plan_duration_str)
            break

    if time_delta:
        expiry_date = datetime.now() + time_delta
        orders_db[order_id]['expires_at'] = expiry_date.isoformat()
        
        if context.job_queue:
            context.job_queue.run_once(
                auto_expire_task, 
                when=time_delta, # Waits exactly the calculated time!
                data={'user_id': user_id, 'order_id': order_id},
                name=f"auto_expire_{order_id}"
            )
            logger.info(f"⏰ Timer set! Order {order_id} will auto-expire at {expiry_date.strftime('%I:%M %p')}")
    else:
        orders_db[order_id]['expires_at'] = "Lifetime"
        
    save_db(ORDERS_FILE, orders_db)
    custom_admin_msg = settings_db.get('approval_msg', "")

    raw_msg = f"""✅ <b>PAYMENT APPROVED - ACCESS GRANTED!</b> ✅

<blockquote>📋 <b>Order ID:</b> <code>{order_id}</code>
👤 <b>User:</b> {first_name}{username_display}
🛍️ <b>Plan:</b> {plan_name}
⏳ <b>Validity:</b> {plan_duration_str}
💰 <b>Amount:</b> ₹{amount}
💳 <b>Method:</b> {method}
⏰ <b>Time:</b> {current_time}</blockquote>

━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <b>YOUR EXCLUSIVE INVITE LINK:</b>
{invite_link}
━━━━━━━━━━━━━━━━━━━━━━━━

{custom_admin_msg}"""

    translated_msg = await smart_translate(raw_msg, user_lang)
    full_msg = translated_msg.replace("INVITE_LINK_PLACEHOLDER", invite_link)
    btn_join = await smart_translate("🔗 Join Premium Channel", user_lang)

    raw_keyboard = [[{"text": btn_join, "url": invite_link, "style": "success"}]]

    # 7. Send via Custom API (or fallback if it fails)
    try:
        await send_colored_settings(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=user_id,
            text=full_msg,
            raw_keyboard=raw_keyboard,
            message_id=message_id_to_edit
        )
    except Exception as e:
        logger.error(f"Error sending custom colored approval msg: {e}")
        fallback_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Premium Channel", url=invite_link)]])
        if message_id_to_edit:
            try:
                await context.bot.edit_message_text(chat_id=user_id, message_id=message_id_to_edit, text=full_msg, reply_markup=fallback_kb, parse_mode='HTML')
            except Exception:
                await context.bot.send_message(chat_id=user_id, text=full_msg, reply_markup=fallback_kb, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=user_id, text=full_msg, reply_markup=fallback_kb, parse_mode='HTML')

    return True

async def handle_deck_action(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str, action: str):
    query = update.callback_query
    print(f"🔥 DECK ACTION FIRED: {action.upper()} on Order {order_id}")
    if order_id not in orders_db:
        await query.answer("❌ Order not found!", show_alert=True)
        return
        
    order = orders_db[order_id]
    if order['status'] in ['approved', 'rejected']:
        await query.answer(f"⚠️ Order already {order['status']}!", show_alert=True)
        await show_stats_pending(query, context, 0)
        return
        
    if action == 'approve':
        success = await process_approval(context, order_id)
        if success:
            await query.answer("✅ Approved! User notified.", show_alert=False) # Smooth popup
        else:
            await query.answer("❌ Error generating link!", show_alert=True)
            return
            
    elif action == 'reject':
        orders_db[order_id]['status'] = 'rejected'
        orders_db[order_id]['rejected_at'] = datetime.now().isoformat()
        save_db(ORDERS_FILE, orders_db)
        try:
            await context.bot.send_message(
                chat_id=order['user_id'],
                text=f"❌ *Payment Verification Failed*\n\nOrder: `{order_id}`\n\nPlease contact admin.",
                parse_mode='Markdown'
            )
        except: pass
        try: await query.answer("❌ Rejected! User notified.", show_alert=False)
        except: pass

    print("🔄 Redrawing Review Deck to show the next order...")
    await show_stats_pending(query, context, 0)

async def approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves order (Supports Command & Buttons)"""
    user_id = update.effective_user.id
    query = update.callback_query

    if str(user_id) != ADMIN_CHAT_ID:
        if query: await query.answer("❌ Unauthorized!", show_alert=True)
        else: await update.message.reply_text("❌ Unauthorized!")
        return
    
    # Get order ID (From Button or Command)
    if query:
        order_id = query.data.replace('btn_approve_', '')
    else:
        if not context.args:
            await update.message.reply_text(
                "Usage: `/approve ORDER_ID`\n\n"
                "Example: `/approve ORD1234567890`",
                parse_mode='Markdown'
            )
            return
        order_id = context.args[0]
    
    if order_id not in orders_db:
        if query: await query.answer(f"❌ Order {order_id} not found!", show_alert=True)
        else: await update.message.reply_text(f"❌ Order `{order_id}` not found!", parse_mode='Markdown')
        return
    
    order = orders_db[order_id]
    
    if order['status'] == 'approved':
        if query: await query.answer("✅ Already approved!", show_alert=True)
        else: await update.message.reply_text(f"✅ Order `{order_id}` already approved!", parse_mode='Markdown')
        return
    
    success = await process_approval(context, order_id)
    
    if not success:
        if query: await query.answer("❌ Error Creating Link!", show_alert=True)
        else: await update.message.reply_text("❌ *Error Creating Link!*", parse_mode='Markdown')
        return

    # Confirm to admin
    if query:
        await query.answer("✅ Approved successfully!")
        try:
            # 1. Grab the plain text to check WHERE the click came from
            plain_text = query.message.caption if query.message.photo else query.message.text
            
            # 2. If it came from the HTML Review Deck...
            if plain_text and "REVIEW DECK" in plain_text:
                # We MUST use .text_html to preserve the quote boxes!
                html_text = query.message.caption_html if query.message.photo else query.message.text_html
                new_text = f"{html_text}\n\n✅ <b>APPROVED BY ADMIN</b>"
                
                if query.message.photo:
                    await query.edit_message_caption(caption=new_text, parse_mode='HTML')
                else:
                    await query.edit_message_text(text=new_text, parse_mode='HTML')
                    
            # 3. If it came from the standard Admin Photo Upload...
            else:
                new_text = f"{plain_text}\n\n✅ *APPROVED BY ADMIN*"
                if query.message.photo:
                    await query.edit_message_caption(caption=new_text, parse_mode='Markdown')
                else:
                    await query.edit_message_text(text=new_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Edit error in approve: {e}")
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ *Approved!*\nOrder: `{order_id}`\nUser: {order.get('first_name', 'User')}\nLink sent to user!",
                parse_mode='Markdown'
            )
        except: pass
    else:
        await update.message.reply_text(f"✅ *Approved!*\nOrder: `{order_id}`\nLink sent to user!", parse_mode='Markdown')
    
    logger.info(f"✅ Order {order_id} approved by admin")



async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects order (Supports Command & Buttons)"""
    user_id = update.effective_user.id
    query = update.callback_query
    
    if str(user_id) != ADMIN_CHAT_ID:
        if query: await query.answer("❌ Unauthorized!", show_alert=True)
        else: await update.message.reply_text("❌ Unauthorized!")
        return
    
    if query:
        order_id = query.data.replace('btn_reject_', '')
    else:
        if not context.args:
            await update.message.reply_text("Usage: `/reject ORDER_ID`", parse_mode='Markdown')
            return
        order_id = context.args[0]
    
    if order_id not in orders_db:
        if query: await query.answer("❌ Order not found!", show_alert=True)
        else: await update.message.reply_text(f"❌ Order `{order_id}` not found!", parse_mode='Markdown')
        return
    
    order = orders_db[order_id]

    if order['status'] in ['approved', 'rejected']:
        if query: await query.answer(f"⚠️ Order already {order['status']}!", show_alert=True)
        else: await update.message.reply_text(f"⚠️ Order already {order['status']}!", parse_mode='Markdown')
        return
    
    # Update status
    orders_db[order_id]['status'] = 'rejected'
    orders_db[order_id]['rejected_at'] = datetime.now().isoformat()
    save_db(ORDERS_FILE, orders_db)
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=order['user_id'],
            text=f"❌ *Payment Verification Failed*\n\n"
                 f"Order: `{order_id}`\n\n"
                 f"Your payment could not be verified.\n\n"
                 f"Please contact admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
    except:
        pass
    
    # Confirm to admin
    username_display = f"(@{order['username']})" if order.get('username') else ""
    admin_confirm_msg = (
        f"❌ *Rejected!*\n\n"
        f"📋 Order: `{order_id}`\n"
        f"👤 User: {order.get('first_name', 'User')} {username_display}\n"
        f"📤 User has been notified."
    )

    if query:
        await query.answer("❌ Rejected successfully!")
        try:
            plain_text = query.message.caption if query.message.photo else query.message.text
            
            if plain_text and "REVIEW DECK" in plain_text:
                html_text = query.message.caption_html if query.message.photo else query.message.text_html
                new_text = f"{html_text}\n\n❌ <b>REJECTED BY ADMIN</b>"
                
                if query.message.photo:
                    await query.edit_message_caption(caption=new_text, parse_mode='HTML')
                else:
                    await query.edit_message_text(text=new_text, parse_mode='HTML')
            else:
                new_text = f"{plain_text}\n\n❌ *REJECTED BY ADMIN*"
                if query.message.photo:
                    await query.edit_message_caption(caption=new_text, parse_mode='Markdown')
                else:
                    await query.edit_message_text(text=new_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Edit error in reject: {e}")

        # ---confirmation message to the admin ---
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_confirm_msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending admin confirmation: {e}")
            
    else:
        # If triggered by text command, just reply normally
        await update.message.reply_text(admin_confirm_msg, parse_mode='Markdown')


async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending orders"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    pending = [o for o in orders_db.items() if o[1]['status'] == 'pending']
    
    if not pending:
        await update.message.reply_text("📭 No pending orders!")
        return
    
    message = f"⏳ *PENDING ORDERS ({len(pending)})*\n\n"
    
    for order_id, order in pending[:10]:
        screenshot = "✅" if order.get('screenshot_uploaded') else "❌"
        message += (
            f"📋 `{order_id}`\n"
            f"👤 {order['first_name']} (@{order.get('username', 'N/A')})\n"
            f"💰 ₹{order['amount']}\n"
            f"📸 Screenshot: {screenshot}\n"
            f"⏰ {order['created_at'][:16]}\n\n"
            f"Approve: `/approve {order_id}`\n"
            f"Reject: `/reject {order_id}`\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stats"""
    user_id = update.effective_user.id
    
    if not is_coadmin(update.effective_user): return
    
    total_orders = len(orders_db)
    approved = sum(1 for o in orders_db.values() if o['status'] == 'approved')
    pending = sum(1 for o in orders_db.values() if o['status'] == 'pending')
    rejected = sum(1 for o in orders_db.values() if o['status'] == 'rejected')
    total_members = len(members_db)
    revenue = sum(o['amount'] for o in orders_db.values() if o['status'] == 'approved')
    
    stats_message = f"""
📊 *BOT STATISTICS*

*Orders:*
📦 Total: {total_orders}
✅ Approved: {approved}
⏳ Pending: {pending}
❌ Rejected: {rejected}

*Members:*
👥 Total: {total_members}
🔗 Active Links: {len(invite_links_db)}

*Revenue:*
💰 Total: ₹{revenue}

*System:*
🔧 Mode: { "MongoDB (Cloud)" if mongo_db is not None else "Local JSON (Risk)" }
🛡️ Verification: Manual
"""
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')


async def contact_admin(query, context):
    """Contact admin with colorful buttons"""
    message = f"""📞 <b>CONTACT ADMIN</b>

Need help?

👤 <b>Admin:</b> {ADMIN_USERNAME}

<i>Click below to message:</i>"""
    raw_keyboard = [
        [{"text": "💬 Message Admin", "url": f"https://t.me/{ADMIN_USERNAME.replace('@', '')}", "style": "primary"}],
        [{"text": "🔙 Back", "callback_data": "back_main", "style": "danger"}]
    ]
    
    try:
        if query.message.text:
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, chat_id=query.message.chat_id,
                text=message, raw_keyboard=raw_keyboard, message_id=query.message.message_id
            )
        else:
            try:
                await query.message.delete()
            except:
                pass
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, chat_id=query.message.chat_id,
                text=message, raw_keyboard=raw_keyboard
            )
    except Exception as e:
        logger.error(f"Error showing contact admin: {e}")


async def back_to_main(query, context):
    """Back to main with colored buttons, multi-language, and smart routing"""
    user = query.from_user
    user_id = str(user.id)
    chat_id = query.message.chat_id
    
    # 👇 1. GRAB THE USER'S LANGUAGE
    user_lang = users_db.get(user_id, {}).get('lang', 'en')

    # 👇 2. SMART CHECK: ARE THEY ALREADY A MEMBER?
    is_active_member = False
    for oid, order in orders_db.items():
        if str(order.get('user_id')) == user_id and order.get('status') in ['approved', 'pending', 'pending_gateway']:
            is_active_member = True
            break

    # 👇 3. FORMAT WELCOME MESSAGE (Using HTML, NOT Markdown)
    raw_welcome = settings_db.get(
        'welcome_msg', 
        "🎉 <b>Welcome back!</b> 🎉\n\nGet <b>Premium Access</b> today for just ₹{PRICE}!"
    )
    
    welcome_message_formatted = raw_welcome.replace("{bot_name}", str(BOT_NAME)).replace("{BOT_NAME}", str(BOT_NAME)) \
                                 .replace("{user_name}", str(user.first_name)).replace("{USER_NAME}", str(user.first_name)) \
                                 .replace("{price}", str(MEMBERSHIP_PRICE)).replace("{PRICE}", str(MEMBERSHIP_PRICE)) \
                                 .replace("{MEMBERSHIP_PRICE}", str(MEMBERSHIP_PRICE))    

    # 👇 4. TRANSLATE MESSAGE & BUTTONS
    final_message = await smart_translate(welcome_message_formatted, user_lang)
    
    btn_active = await smart_translate("📊 Active Plans", user_lang)
    btn_join = await smart_translate("🚀 Join Membership", user_lang)
    btn_how = await smart_translate("ℹ️ How It Works", user_lang)
    btn_contact = await smart_translate("📞 Contact Admin", user_lang)
    btn_lang = await smart_translate("🌍 Language", user_lang)

    # 👇 5. BUILD THE COLORED KEYBOARD
    if is_active_member:
        # Dashboard for users who have a history
        raw_keyboard = [
            [{"text": btn_active, "callback_data": "my_active_plans", "style": "success"},
             {"text": btn_lang, "callback_data": "lang_page_0", "style": "primary"}],
            [{"text": btn_join, "callback_data": "join_membership", "style": "primary"}],
            [{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}]
        ]
    else:
        # Standard welcome for brand new users
        raw_keyboard = [
            [{"text": btn_join, "callback_data": "join_membership", "style": "success"}],
            [{"text": btn_how, "callback_data": "how_it_works", "style": "primary"},
             {"text": btn_lang, "callback_data": "lang_page_0", "style": "primary"}],
            [{"text": btn_contact, "callback_data": "contact_admin", "style": "primary"}]
        ]

    # 👇 6. SEND VIA CUSTOM API
    try:
        if query.message.text:
            # It's a text message, can seamlessly edit
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, 
                chat_id=chat_id,
                text=final_message, 
                raw_keyboard=raw_keyboard, 
                message_id=query.message.message_id
            )
        else:
            # It's a photo/QR message, must delete and send fresh text
            try:
                await query.message.delete()
            except:
                pass
            await send_colored_settings(
                bot_token=TELEGRAM_BOT_TOKEN, 
                chat_id=chat_id,
                text=final_message, 
                raw_keyboard=raw_keyboard
            )
    except Exception as e:
        logger.error(f"Error in back_to_main colored send: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"🚨 CRASH DETECTED: {context.error}", exc_info=context.error)


def validate_config():
    """Validate config"""
    errors = []
    
    try:
        _ = TELEGRAM_BOT_TOKEN
        if 'YOUR_BOT_TOKEN' in TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN) < 10:
            errors.append("❌ TELEGRAM_BOT_TOKEN invalid")
    except NameError:
        errors.append("❌ TELEGRAM_BOT_TOKEN not found")
    
    try:
        _ = ADMIN_CHAT_ID
    except NameError:
        errors.append("❌ ADMIN_CHAT_ID not found")
    
    try:
        _ = UPI_ID
        if 'your-upi-id' in UPI_ID.lower() or '@' not in UPI_ID:
            errors.append("❌ UPI_ID invalid")
    except NameError:
        errors.append("❌ UPI_ID not found")
    
    try:
        _ = PREMIUM_CHANNEL_ID
        if PREMIUM_CHANNEL_ID >= 0:
            errors.append("❌ PREMIUM_CHANNEL_ID must be negative")
    except NameError:
        errors.append("❌ PREMIUM_CHANNEL_ID not found")
    
    try:
        _ = BOT_NAME
    except NameError:
        globals()['BOT_NAME'] = "Premium Membership Bot"
    
    try:
        _ = ADMIN_USERNAME
    except NameError:
        globals()['ADMIN_USERNAME'] = "@admin"
    
    if errors:
        print("\n" + "="*70)
        print("🚫 CONFIGURATION ERRORS")
        print("="*70)
        for error in errors:
            print(error)
        print("="*70)
        return False
    
    return True


def main():
    """Start bot"""
    
    if not validate_config():
        exit(1)
    
    print("\n" + "="*70)
    print("🚀 SEMI-AUTOMATIC MEMBERSHIP BOT")
    print("="*70)
    print(f"💳 Payment: UPI (₹{MEMBERSHIP_PRICE})")
    print(f"🔒 Verification: Manual (Admin Approval)")
    print(f"🔗 Links: One-time use ({INVITE_LINK_EXPIRY_HOURS}h)")
    print(f"📱 Channel: {PREMIUM_CHANNEL_ID}")
    print(f"👨‍💼 Admin: {ADMIN_USERNAME}")
    
    if mongo_client:
        print(f"💾 Storage: MongoDB (Persistent)")
    else:
        print(f"⚠️ Storage: Local JSON (Warning: Data lost on restart!)")
        
    print("")
    print("✨ FEATURES:")
    print("   ✅ Payment screenshot verification")
    print("   ✅ Manual admin approval")
    print("   ✅ One-time invite links")
    print("   ✅ Fraud prevention")
    print("="*70 + "\n")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # User handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_screenshot))
    application.add_handler(CommandHandler("admin", show_dashboard))
    application.add_handler(
        MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_admin_text), 
        group=1)
    # Admin commands
    application.add_handler(CommandHandler("approve", approve_order))
    application.add_handler(CommandHandler("reject", reject_order))
    application.add_handler(CommandHandler("pending", pending_orders))
    application.add_handler(CommandHandler("stats", stat_command))
    application.add_handler(CommandHandler("deleteuser", delete_user_command))
    application.add_handler(CommandHandler("revoke", revoke_order_command))
    
    #co-admin command
    application.add_handler(CommandHandler("add", add_coadmin))
    application.add_handler(CommandHandler("remove", remove_coadmin))
    application.add_handler(CommandHandler("adminlist", admin_list))

    application.add_error_handler(error_handler)
    
    logger.info("✅ Semi-Auto Bot Started!")
    logger.info(f"💰 Price: ₹{MEMBERSHIP_PRICE}")
    logger.info(f"🔒 Mode: Manual Approval")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
