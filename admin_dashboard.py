from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    orders_db, members_db, invite_links_db, settings_db, plans_db,
    save_db, ORDERS_FILE, MEMBERS_FILE, INVITE_LINKS_FILE,SETTINGS_FILE,
    mongo_client, mongo_db
)
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, MONGO_URI
from api_utils import send_colored_settings, send_colored_photo
async def show_bot_stats(query, context):
    """Generates the advanced HTML Stats Dashboard"""
    approved_count = 0
    pending_count = 0
    revoked_count = 0
    
    upi_revenue = 0.0
    razorpay_revenue = 0.0
    active_links = 0
    unique_members = set()
    for oid, order in orders_db.items():
        status = order.get('status')
        user_id = order.get('user_id')
        try:
            raw_amount = str(order.get('amount', 0)).replace('₹', '').replace(',', '').strip()
            amount = float(raw_amount)
        except ValueError:
            amount = 0.0
        
        if status in ['approved', 'active']:
            approved_count += 1
            unique_members.add(user_id)
            if order.get('selected_upi') or order.get('screenshot_uploaded') or order.get('qr_msg_id'):
                upi_revenue += amount
            else:
                razorpay_revenue += amount
                
            if order.get('invite_link'):
                active_links += 1
                
        elif status in ['pending', 'pending_gateway']:
            pending_count += 1
        elif status == 'revoked':
            revoked_count += 1

    net_razorpay = razorpay_revenue * 0.98
    net_revenue = upi_revenue + net_razorpay
    storage_type = "MongoDB (Persistent) 🟢" if MONGO_URI else "Local JSON (SERVER STORAGE) 🟡"

    msg = f"""📊 <b>BOT STATISTICS DASHBOARD</b>

<blockquote>✅ <b>Approved:</b> {approved_count}
⏳ <b>Pending:</b> {pending_count}
🚫 <b>Revoked:</b> {revoked_count}
💰 <b>Net Revenue:</b> ₹{net_revenue:.2f}
👥 <b>Members:</b> {len(unique_members)}
🔗 <b>Active Links:</b> {active_links}
🗄️ <b>Storage Mode:</b> {storage_type}</blockquote>

<i>*Note: GST is not included. Final prices may differ due to GST charges on Razorpay revenue.</i>"""

    keyboard = [
        [
            {"text": "✅ Approved", "callback_data": "stats_approved_0", "style": "success"},
            {"text": "⏳ Pending", "callback_data": "stats_pending_0", "style": "primary"}
        ],
        [
            {"text": "💰 Revenue", "callback_data": "stats_revenue", "style": "primary"},
            {"text": "🔗 Active Links", "callback_data": "stats_links", "style": "primary"}
        ],
        [{"text": "❌ Close Panel", "callback_data": "stats_close", "style": "danger"}]
    ]

    await send_colored_settings(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=query.message.chat_id,
        text=msg,
        raw_keyboard=keyboard,
        message_id=query.message.message_id
    )

#==== SUB-MENU HANDLERS FOR STATS DASHBOARD ====

async def show_stats_approved(query, context, page: int):
    """Paginated list of approved orders"""
    approved_orders = [(oid, o) for oid, o in orders_db.items() if o.get('status') in ['approved', 'active']]
    approved_orders.sort(key=lambda x: x[1].get('approved_at', x[1].get('created_at', '')), reverse=True)
    
    if not approved_orders:
        await query.answer("No approved requests found!", show_alert=True)
        return
        
    ITEMS_PER_PAGE = 3
    total_pages = (len(approved_orders) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_chunk = approved_orders[start_idx:end_idx]
    
    msg = f"✅ <b>APPROVED REQUESTS (Page {page+1}/{total_pages})</b>\n\n"
    
    for oid, order in current_chunk:
        msg += f"<blockquote>👤 <b>User:</b> {order.get('first_name')} (@{order.get('username')})\n"
        msg += f"🛍️ <b>Plan:</b> {order.get('plan_name')}\n"
        msg += f"💰 <b>Amount:</b> ₹{order.get('amount')}\n"
        msg += f"📋 <b>Order ID:</b> <code>{oid}</code></blockquote>\n"
        
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append({"text": "⬅️ Prev", "callback_data": f"stats_approved_{page-1}", "style": "primary"})
    if page < total_pages - 1:
        nav_row.append({"text": f"Next ({page+2}/{total_pages}) ➡️", "callback_data": f"stats_approved_{page+1}", "style": "primary"})
        
    if nav_row: keyboard.append(nav_row)
    keyboard.append([{"text": "🔙 Back to Stats", "callback_data": "stats_main", "style": "danger"}])
    
    await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, msg, keyboard, query.message.message_id)

async def show_stats_revenue(query, context, menu_type: str):
    """Handles the Revenue Splitting Menus"""
    if menu_type == 'main':
        msg = "💰 <b>REVENUE BREAKDOWN</b>\n\nChoose a payment gateway to view detailed earnings:"
        keyboard = [
            [{"text": "🏦 UPI Earnings", "callback_data": "stats_rev_upi", "style": "primary"}],
            [{"text": "💳 Razorpay Earnings", "callback_data": "stats_rev_gateway", "style": "primary"}],
            [{"text": "🔙 Back to Stats", "callback_data": "stats_main", "style": "danger"}]
        ]
    elif menu_type == 'upi':
        upi_totals = {}
        for oid, order in orders_db.items():
            if order.get('status') in ['approved', 'active'] and not order.get('revenue_cleared', False) and (order.get('screenshot_uploaded') or order.get('qr_msg_id')):
                
                # Safe Math
                try:
                    raw_amt = str(order.get('amount', 0)).replace('₹', '').replace(',', '').strip()
                    amt = float(raw_amt)
                except ValueError:
                    amt = 0.0
                    
                upi_id = order.get('selected_upi', 'Unknown UPI')
                upi_totals[upi_id] = upi_totals.get(upi_id, 0) + amt
                
        msg = "🏦 <b>UPI EARNINGS (By ID)</b>\n\n"
        if not upi_totals: msg += "<i>No UPI earnings yet.</i>"
        for upi, total in upi_totals.items():
            msg += f"<blockquote>💳 <b>{upi}</b>\n💰 Total: ₹{total:.2f}</blockquote>\n"
            
        keyboard = [
            [{"text": "🔄 Reset UPI Revenue", "callback_data": "reset_rev_upi", "style": "primary"}],
            [{"text": "🔙 Back", "callback_data": "stats_revenue", "style": "danger"}]
        ]
        
    elif menu_type == 'gateway':
        total = 0
        for oid, order in orders_db.items():
            if order.get('status') in ['approved', 'active'] and not order.get('revenue_cleared', False)  and ('status_msg_id' in order or 'gateway_menu_msg_id' in order):
                total += float(order.get('amount', 0))
                
        net = total * 0.98
        msg = f"💳 <b>RAZORPAY EARNINGS</b>\n\n<blockquote>💵 <b>Gross Processed:</b> ₹{total:.2f}\n📉 <b>Gateway Fee (2%):</b> -₹{(total * 0.02):.2f}\n💰 <b>Net Earned:</b> ₹{net:.2f}</blockquote>"
        keyboard = [
            [{"text": "🔄 Reset Gateway Revenue", "callback_data": "reset_rev_gateway", "style": "primary"}],
            [{"text": "🔙 Back", "callback_data": "stats_revenue", "style": "danger"}]
        ]

    await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, msg, keyboard, query.message.message_id)

async def show_stats_links(query, context):
    """Shows all active invite links"""
    active_links = []
    for oid, order in orders_db.items():
        if order.get('status') in ['approved', 'active'] and order.get('invite_link'):
            active_links.append((order.get('username', 'User'), order.get('invite_link')))
            
    msg = "🔗 <b>ACTIVE INVITE LINKS</b>\n\n"
    if not active_links:
        await query.answer("🔗 No active links found!", show_alert=True)
        return
    msg = "🔗 <b>ACTIVE INVITE LINKS</b>\n\n"
    for user, link in active_links:
        msg += f"👤 @{user}\n<code>{link}</code>\n\n"
            
    keyboard = [[{"text": "🔙 Back to Stats", "callback_data": "stats_main", "style": "danger"}]]
    await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, msg, keyboard, query.message.message_id)

# pending REQUEST LOGIC
#===========================
async def show_stats_pending(query, context, index: int):
    """The Innovative 'Review Deck' for pending orders"""
    pending_orders = [(oid, o) for oid, o in orders_db.items() if o.get('status') in ['pending', 'pending_gateway']]
    
    if not pending_orders:
        msg = "🎉 <b>QUEUE IS EMPTY</b>\n\nThere are currently no pending orders waiting for review. Great job!"
        keyboard = [[{"text": "🔙 Back to Stats", "callback_data": "stats_main", "style": "danger"}]]
        
        await send_colored_settings(
            bot_token=TELEGRAM_BOT_TOKEN, 
            chat_id=query.message.chat_id, 
            text=msg, 
            raw_keyboard=keyboard, 
            message_id=query.message.message_id
        )
        return
                
    # Keep index in bounds
    if index >= len(pending_orders): index = 0
    if index < 0: index = len(pending_orders) - 1
    index = max(0, min(index, len(pending_orders) - 1))
    oid, order = pending_orders[index]
    
    msg = f"⏳ <b>PENDING REVIEW DECK ({index+1}/{len(pending_orders)})</b>\n\n"
    msg += f"<blockquote>👤 <b>User:</b> {order.get('first_name')} (@{order.get('username')})\n"
    msg += f"🛍️ <b>Plan:</b> {order.get('plan_name')}\n"
    msg += f"💰 <b>Amount:</b> ₹{order.get('amount')}\n"
    msg += f"📋 <b>Order ID:</b> <code>{oid}</code>\n"
    msg += f"⏰ <b>Time:</b> {order.get('created_at')}</blockquote>\n\n"
    msg += "<i>*To view the screenshot, check the bot's chat history.</i>"

    # Action Buttons specifically for this order
    keyboard = [
        [
            # 👇 CHANGED TO deck_approve and deck_reject 👇
            {"text": "✅ Approve", "callback_data": f"deck_approve_{oid}", "style": "success"},
            {"text": "❌ Reject", "callback_data": f"deck_reject_{oid}", "style": "danger"}
        ],
        [
            {"text": "⬅️ Prev", "callback_data": f"stats_pending_{index-1}", "style": "primary"},
            {"text": "Next ➡️", "callback_data": f"stats_pending_{index+1}", "style": "primary"}
        ],
        [{"text": "🔙 Back to Stats", "callback_data": "stats_main", "style": "danger"}]
    ]
    await send_colored_settings(TELEGRAM_BOT_TOKEN, query.message.chat_id, msg, keyboard, query.message.message_id)
