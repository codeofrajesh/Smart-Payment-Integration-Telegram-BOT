import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_CHAT_ID
from database import settings_db, plans_db, save_db, SETTINGS_FILE, PLANS_FILE
from api_utils import send_colored_settings, send_colored_photo
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID

def is_coadmin(user):
    """Checks if a user is the Main Admin OR a Co-Admin in the database"""
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

def extract_bulletproof_html(message):
    """Event-based UTF-16 parser. Handles infinite nesting and forwarded stacked entities!"""
    if not message: return ""
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    
    if not entities: return text
    
    text_utf16 = text.encode('utf-16-le')
    events = []
    
    # 1. Map out every opening and closing tag event
    for i, ent in enumerate(entities):
        events.append({'offset': ent.offset, 'type': 'open', 'length': ent.length, 'id': i, 'ent': ent})
        events.append({'offset': ent.offset + ent.length, 'type': 'close', 'length': ent.length, 'id': i, 'ent': ent})
        
    # 2. Sort events symmetrically to guarantee perfect HTML nesting
    def sort_key(e):
        is_close = 0 if e['type'] == 'close' else 1
        len_sort = -e['length'] if e['type'] == 'open' else e['length']
        id_sort = e['id'] if e['type'] == 'open' else -e['id']
        return (e['offset'], is_close, len_sort, id_sort)
        
    events.sort(key=sort_key)
    
    result_utf16 = b""
    last_offset = 0
    
    # 3. Build the string exactly as Telegram rendered it
    for e in events:
        if e['offset'] > last_offset:
            result_utf16 += text_utf16[last_offset * 2 : e['offset'] * 2]
            last_offset = e['offset']
            
        ent = e['ent']
        if e['type'] == 'open':
            if ent.type == 'blockquote': tag = "<blockquote>"
            elif ent.type == 'bold': tag = "<b>"
            elif ent.type == 'italic': tag = "<i>"
            elif ent.type == 'underline': tag = "<u>"
            elif ent.type == 'strikethrough': tag = "<s>"
            elif ent.type == 'spoiler': tag = "<tg-spoiler>"
            elif ent.type == 'text_link': tag = f'<a href="{ent.url}">'
            elif ent.type == 'url': 
                url = text_utf16[ent.offset*2 : (ent.offset+ent.length)*2].decode('utf-16-le')
                tag = f'<a href="{url}">'
            elif ent.type == 'code': tag = "<code>"
            elif ent.type == 'pre': tag = "<pre>"
            else: tag = ""
            result_utf16 += tag.encode('utf-16-le')
            
        elif e['type'] == 'close':
            if ent.type == 'blockquote': tag = "</blockquote>"
            elif ent.type == 'bold': tag = "</b>"
            elif ent.type == 'italic': tag = "</i>"
            elif ent.type == 'underline': tag = "</u>"
            elif ent.type == 'strikethrough': tag = "</s>"
            elif ent.type == 'spoiler': tag = "</tg-spoiler>"
            elif ent.type in ['text_link', 'url']: tag = "</a>"
            elif ent.type == 'code': tag = "</code>"
            elif ent.type == 'pre': tag = "</pre>"
            else: tag = ""
            result_utf16 += tag.encode('utf-16-le')

    if last_offset * 2 < len(text_utf16):
        result_utf16 += text_utf16[last_offset * 2 :]
        
    return result_utf16.decode('utf-16-le')
   
async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Launch the Interactive Admin Dashboard"""
    user_id = update.effective_user.id
    if not is_coadmin(update.effective_user): return
        
    context.user_data.pop('admin_state', None)
    chat_id = update.effective_chat.id
    message_id = update.callback_query.message.message_id if update.callback_query else None
    upi_ids = settings_db.get('upi_ids', [])
    if not upi_ids and settings_db.get('upi_id'):
        upi_ids = [settings_db.get('upi_id')]
        settings_db['upi_ids'] = upi_ids
        save_db(SETTINGS_FILE, settings_db)

    upi_display = f"{len(upi_ids)} Active" if upi_ids else "❌ None Set"
    rzp_mode = settings_db.get('rzp_mode', 'Automatic').title()
    msg = f"""🎛️ <b>ADMIN CONTROL PANEL</b>

<blockquote>🏦 <b>UPI IDs:</b> {upi_display}
💳 <b>Gateway:</b> {rzp_mode}
📋 <b>Active Plans:</b> {len(plans_db)}
💬 <b>Custom Messages:</b> Active</blockquote>

👇 <i>Select an option below to configure your bot:</i>"""

    # 4. Build the 2-Column Colored Grid
    raw_keyboard = [
        [
            {"text": "🏦 Manage UPI", "callback_data": "admin_edit_upi", "style": "primary"},
            {"text": "💳 Gateway Setup", "callback_data": "admin_gateway", "style": "primary"}
        ],
        [
            {"text": "📋 Manage Plans", "callback_data": "admin_manage_plans", "style": "primary"},
            {"text": "💬 Edit Messages", "callback_data": "admin_edit_msgs", "style": "primary"}
        ],
        [
            {"text": "📊 Open Live Analytics", "callback_data": "stats_main", "style": "success"}
        ],
        [
            {"text": "💾 Toggle Translation Cache", "callback_data": "admin_toggle_cache", "style": "primary"}
        ],
        [
            {"text": "❌ Close Panel", "callback_data": "admin_close", "style": "danger"}
        ]
    ]
    
    # 5. Send via your custom API bypass
    try:
        await send_colored_settings(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=chat_id,
            text=msg,
            raw_keyboard=raw_keyboard,
            message_id=message_id
        )
    except Exception as e:
        logger.error(f"Error showing admin dashboard: {e}")

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes button clicks from the admin dashboard"""
    query = update.callback_query
    
    if query.data == 'admin_dash':
        await show_dashboard(update, context)
        
    elif query.data == 'admin_close':
        await query.message.delete()
        
    elif query.data == 'admin_edit_upi':
        upi_ids = settings_db.get('upi_ids', [])
        keyboard = []
        
        # List all current UPIs with a Delete button
        for i, upi in enumerate(upi_ids):
            keyboard.append([InlineKeyboardButton(f"❌ Delete: {upi}", callback_data=f'admin_del_upi_{i}')])
            
        keyboard.append([InlineKeyboardButton("➕ Add New UPI", callback_data='admin_add_upi')])
        keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')])
        
        await query.edit_message_text(
            "🏦 *UPI MANAGEMENT*\n\nClick a UPI ID to delete it, or click Add to create a new one.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif query.data == 'admin_add_upi':
        context.user_data['admin_state'] = 'waiting_for_new_upi'
        await query.edit_message_text(
            "➕ *Send the new UPI ID* (e.g., `name@okaxis`):\n\n_Or click cancel below._",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_edit_upi')]]),
            parse_mode='Markdown'
        )

    elif query.data.startswith('admin_del_upi_'):
        idx = int(query.data.replace('admin_del_upi_', ''))
        upi_ids = settings_db.get('upi_ids', [])
        
        if 0 <= idx < len(upi_ids):
            deleted = upi_ids.pop(idx)
            settings_db['upi_ids'] = upi_ids
            save_db(SETTINGS_FILE, settings_db)
            await query.answer(f"✅ Deleted {deleted}!")
            
        keyboard = [[InlineKeyboardButton(f"❌ Delete: {u}", callback_data=f'admin_del_upi_{i}')] for i, u in enumerate(upi_ids)]
        keyboard.append([InlineKeyboardButton("➕ Add New UPI", callback_data='admin_add_upi')])
        keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')])
        await query.edit_message_text("🏦 *UPI MANAGEMENT*\n\nClick a UPI ID to delete it, or click Add to create a new one.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif query.data == 'admin_manage_plans':
        keyboard = []
        for p_id, p_data in plans_db.items():
            keyboard.append([InlineKeyboardButton(f"✏️ {p_data['name']} - ₹{p_data['price']}", callback_data=f'admin_del_plan_{p_id}')])
            
        keyboard.append([InlineKeyboardButton("➕ Add New Plan", callback_data='admin_add_plan')])
        keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')])
        
        await query.edit_message_text(
            "📋 *PLAN MANAGEMENT*\n\nClick a plan to delete it, or add a new one.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    elif query.data == 'admin_add_plan':
        context.user_data['admin_state'] = 'waiting_for_plan_name'
        await query.edit_message_text(
            "➕ *Step 1/4: Send the Name of the new plan*\n(e.g., `1 Month VIP` or `Lifetime`)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_manage_plans')]]),
            parse_mode='Markdown'
        )
        
    elif query.data.startswith('admin_del_plan_'):
        p_id = query.data.replace('admin_del_plan_', '')
        if p_id in plans_db:
            del plans_db[p_id]
            save_db(PLANS_FILE, plans_db)
            await query.answer("✅ Plan Deleted!")
        else:
            await query.answer("❌ Plan not found!", show_alert=True)
        if not plans_db:
            await show_dashboard(update, context)
        else:
            keyboard = []
            for p, p_data in plans_db.items():
                keyboard.append([InlineKeyboardButton(f"✏️ {p_data['name']} - ₹{p_data['price']}", callback_data=f'admin_del_plan_{p}')])
            keyboard.append([InlineKeyboardButton("➕ Add New Plan", callback_data='admin_add_plan')])
            keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')])
            
            await query.edit_message_text(
                "📋 *PLAN MANAGEMENT*\n\nClick a plan to delete it, or add a new one.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    elif query.data == 'admin_edit_msgs':
        keyboard = [
            [InlineKeyboardButton("📝 Edit Welcome TEXT", callback_data='admin_msg_welcome')],
            [InlineKeyboardButton("📸 Edit Welcome IMAGE", callback_data='admin_welcome_image')],
            [InlineKeyboardButton("✅ Edit Approval Msg", callback_data='admin_msg_approval')],
            [InlineKeyboardButton("🔙 Back", callback_data='admin_dash')]
        ]
        await query.edit_message_text("💬 *Which message do you want to edit?*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif query.data == 'admin_welcome_image':
        context.user_data['admin_state'] = 'waiting_for_welcome_image'
        await query.edit_message_text(
            "📸 *Send the new Default Welcome Image.*\n\n_This will only be shown if the user doesn't have a profile picture._",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_edit_msgs')]]),
            parse_mode='Markdown'
        )

    elif query.data.startswith('admin_msg_'):
        msg_type = query.data.replace('admin_msg_', '')
        context.user_data['admin_state'] = f'waiting_for_msg_{msg_type}'
        await query.edit_message_text(
            f"💬 *Send the new {msg_type.title()} Message.*\n\n⚠️ *Pro Tip:* Use Telegram's built-in formatting!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_edit_msgs')]]),
            parse_mode='Markdown'
        )
    elif query.data == 'admin_gateway':
        current_mode = settings_db.get('rzp_mode', 'manual').lower()
        display_mode = "Automatic" if current_mode == 'auto' else "Manual"
        
        key_status = "✅ Set" if settings_db.get('rzp_key_id') else "❌ Not Set"
        
        msg = (
            f"💳 *PAYMENT GATEWAY SETTINGS*\n\n"
            f"🔑 *API Keys:* {key_status}\n"
            f"⚙️ *Current Mode:* {display_mode.upper()}\n\n"
            f"_Manual = Admin must still verify the gateway payment._\n"
            f"_Auto = Bot auto-approves and sends link instantly._"
        )
        
        kb = [
            [InlineKeyboardButton("🔑 Set/Edit API Keys", callback_data='admin_rzp_keys')],
            # 👇 Here is the dynamic button!
            [InlineKeyboardButton(f"🔄 Mode: {display_mode}", callback_data='admin_rzp_toggle')],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
    elif query.data == 'admin_rzp_toggle':
        current_mode = settings_db.get('rzp_mode', 'manual').lower()
        new_mode = 'auto' if current_mode == 'manual' else 'manual'
        
        settings_db['rzp_mode'] = new_mode
        save_db(SETTINGS_FILE, settings_db)

        display_mode = "Automatic" if new_mode == 'auto' else "Manual"
        key_status = "✅ Set" if settings_db.get('rzp_key_id') else "❌ Not Set"
        
        msg = (
            f"💳 *PAYMENT GATEWAY SETTINGS*\n\n"
            f"🔑 *API Keys:* {key_status}\n"
            f"⚙️ *Current Mode:* {display_mode.upper()}\n\n"
            f"_Manual = Admin must still verify the gateway payment._\n"
            f"_Auto = Bot auto-approves and sends link instantly._"
        )
        
        kb = [
            [InlineKeyboardButton("🔑 Set/Edit API Keys", callback_data='admin_rzp_keys')],
            [InlineKeyboardButton(f"🔄 Mode: {display_mode}", callback_data='admin_rzp_toggle')],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data='admin_dash')]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        await query.answer(f"✅ Mode switched to {display_mode}!", show_alert=False)

    elif query.data == 'admin_rzp_keys':
        context.user_data['admin_state'] = 'waiting_for_rzp_key'
        await query.edit_message_text(
            "🔑 *Step 1/2: Send your Razorpay KEY ID*\n\n_Or click cancel below._",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_gateway')]]),
            parse_mode='Markdown'
        )    

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches text inputs for changing settings"""
    user_id = update.effective_user.id
    if not is_coadmin(update.effective_user): 
        return

    state = context.user_data.get('admin_state')
    if not state: return

    text = update.message.text
    
    if state == 'waiting_for_new_upi':
        if '@' not in text:
            await update.message.reply_text("❌ Invalid UPI format. Must contain '@'.")
            return
            
        upi_ids = settings_db.get('upi_ids', [])
        if text in upi_ids:
            await update.message.reply_text("❌ This UPI is already in your list!")
            return
            
        upi_ids.append(text)
        settings_db['upi_ids'] = upi_ids
        save_db(SETTINGS_FILE, settings_db)
        
        await update.message.reply_text(f"✅ UPI ID successfully added: `{text}`", parse_mode='Markdown')
        context.user_data.pop('admin_state', None)
        await show_dashboard(update, context) 
        return
        
    elif state == 'waiting_for_rzp_key':
        context.user_data['temp_rzp_key'] = text
        context.user_data['admin_state'] = 'waiting_for_rzp_secret'
        await update.message.reply_text("✅ Key ID saved.\n\n🔐 *Step 2/2: Now send your Razorpay KEY SECRET:*", parse_mode='Markdown')
        return

    elif state == 'waiting_for_rzp_secret':
        settings_db['rzp_key_id'] = context.user_data['temp_rzp_key']
        settings_db['rzp_key_secret'] = text
        if 'rzp_mode' not in settings_db:
            settings_db['rzp_mode'] = 'manual' 
        save_db(SETTINGS_FILE, settings_db)
        
        await update.message.reply_text("✅ Razorpay Keys successfully saved!")
        context.user_data.pop('admin_state', None) # Clears the state
        await show_dashboard(update, context) # Shows the dashboard again
        return
        
    elif state == 'waiting_for_plan_name':
        context.user_data['temp_plan_name'] = text
        context.user_data['admin_state'] = 'waiting_for_plan_desc'
        await update.message.reply_text(
            f"✅ Name set to '{text}'.\n\n"
            f"📝 *Step 2/4: Send a short DESCRIPTION for this plan.*"
        )
        return
        
    elif state == 'waiting_for_plan_desc':
        context.user_data['temp_plan_desc'] = update.message.text_html
        context.user_data['admin_state'] = 'waiting_for_plan_duration'
        
        # Fixed the nested quotes syntax error here!
        msg = (
            "✅ Description saved.\n\n"
            "⏳ *Step 3/4: Enter Plan Duration*\n\n"
            "Use our smart time format:\n"
            "• `30d` (30 Days)\n"
            "• `2min` (2 Minutes)\n"
            "• `1d30min` (1 Day and 30 Mins)\n"
            "• `Lifetime` (Never expires)\n\n"
            "Reply with the duration:"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    elif state == 'waiting_for_plan_duration':
        # ❌ REMOVED the text.isdigit() check! We WANT letters now.
        
        display_text = text.strip() # Just take exactly what they typed
        
        context.user_data['temp_plan_duration'] = display_text 
        # ❌ REMOVED context.user_data['temp_plan_duration_days'] completely!
        
        context.user_data['admin_state'] = 'waiting_for_plan_price'
        await update.message.reply_text(
            f"✅ Duration set to '{display_text}'.\n\n"
            f"💰 *Step 4/4: Send the PRICE in rupees (Numbers only).* mechanics.",
            parse_mode='Markdown'
        )
        return
        
    elif state == 'waiting_for_plan_price':
        if not text.isdigit():
            await update.message.reply_text("❌ Price must be a number (e.g., 99). Try again.")
            return
        
        plan_id = f"plan_{int(time.time())}"
        plans_db[plan_id] = {
            "name": context.user_data['temp_plan_name'],
            "desc": context.user_data['temp_plan_desc'],
            "duration": context.user_data['temp_plan_duration'], 
            # ❌ REMOVED "duration_days" KEY COMPLETELY!
            "price": int(text)
        }
        save_db(PLANS_FILE, plans_db)
        await update.message.reply_text(f"✅ Plan '{context.user_data['temp_plan_name']}' added successfully for ₹{text}!")
        
    elif state.startswith('waiting_for_msg_'):
        msg_type = state.replace('waiting_for_msg_', '')
        settings_db[f"{msg_type}_msg"] = extract_bulletproof_html(update.message)
        save_db(SETTINGS_FILE, settings_db)
        await update.message.reply_text(f"✅ {msg_type.title()} message updated!")

    elif state == 'waiting_for_welcome_image':
        if not update.message.photo and not update.message.document:
            await update.message.reply_text("❌ Please send an IMAGE, not text.")
            return
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        else:
            file_id = update.message.document.file_id

        settings_db['welcome_image_id'] = file_id
        save_db(SETTINGS_FILE, settings_db)
        
        await update.message.reply_text("✅ Default Welcome Image successfully updated!")
        context.user_data.pop('admin_state', None)
        await show_dashboard(update, context)
        return    

    context.user_data.pop('admin_state', None)
    await show_dashboard(update, context)