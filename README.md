# 🤖 Semi-Automatic Telegram Membership Bot

**Simple UPI Payment | No Gateway Fees | Manual Verification | Single-Use Links**

---

## ✨ FEATURES (ALL INCLUDED)

✅ **QR-code payment display** - UPI QR for any app  
✅ **Order ID generation** - Unique tracking  
✅ **User payment confirmation** - "Payment Done" button  
✅ **Manual admin verification** - You approve each payment  
✅ **Single-use invite links** - 1 user, 1 link  
✅ **Invite link expiry** - Auto-expire after 24h  
✅ **Auto channel access** - After you approve  
✅ **No link sharing** - Links become invalid after use  
✅ **User & order logging** - All data saved  
✅ **No payment gateway** - Direct UPI, zero fees!  

---

## 💰 WHY SEMI-AUTOMATIC?

### Advantages:
- ✅ **Zero payment gateway fees** - 100% payment to you
- ✅ **Fraud prevention** - You verify each payment manually
- ✅ **Full control** - You decide who gets access
- ✅ **No API costs** - No Razorpay/Cashfree needed
- ✅ **Simple setup** - Just UPI ID needed
- ✅ **Security** - Manual verification prevents scams

### How It Works:
```
User pays → User clicks "Done" → You get notification → 
You check UPI app → You approve → User gets invite link
```

---

## 🚀 QUICK START

### 1. Extract Files
```bash
unzip SEMI_AUTO_BOT.zip
cd SEMI_AUTO_BOT
```

### 2. Configure
```bash
# Edit config.py
nano config.py

# Fill in:
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - ADMIN_CHAT_ID (from @userinfobot)
# - UPI_ID (your UPI ID)
# - PREMIUM_CHANNEL_ID (from @userinfobot)
```

### 3. Run
```bash
# Quick setup
chmod +x setup.sh
./setup.sh

# Bot is now running!
docker-compose logs -f
```

---

## 📋 SETUP STEPS

### Step 1: Install Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose -y
```

### Step 2: Create Telegram Bot

1. Message **@BotFather** on Telegram
2. Send `/newbot`
3. Choose name: "Premium Membership Bot"
4. Choose username: "premium_bot"
5. **Copy the token**

### Step 3: Get Admin Chat ID

1. Message **@userinfobot** on Telegram
2. Send `/start`
3. **Copy your User ID**

### Step 4: Setup Premium Channel

1. Create a **PRIVATE** Telegram channel
2. Add your bot as **administrator**
3. Give bot permission: **"Invite Users via Link"**
4. Forward any message from channel to **@userinfobot**
5. **Copy the channel ID** (negative number like -1001234567890)

### Step 5: Configure Bot

Edit `config.py`:
```python
TELEGRAM_BOT_TOKEN = "your_token_here"
ADMIN_CHAT_ID = "your_user_id"
UPI_ID = "9876543210@paytm"  # Your UPI ID
PREMIUM_CHANNEL_ID = -1001234567890  # Your channel ID
```

### Step 6: Run

```bash
./setup.sh
```

**Done! Bot is running!**

---

## 🎯 HOW TO USE

### For Users:

1. User starts bot: `/start`
2. Clicks "Join Membership"
3. Gets QR code for ₹99
4. Pays via any UPI app
5. Clicks "✅ I Have Paid"
6. Waits for admin approval

### For Admin (You):

1. You receive notification with order details
2. Check your UPI app for payment
3. If payment received:
   ```
   /approve ORD1234567890
   ```
4. Bot sends single-use invite link to user
5. User joins channel
6. Link becomes invalid

### Admin Commands:

```bash
/pending              # See all pending orders
/approve ORDER_ID     # Approve payment & send link
/reject ORDER_ID      # Reject payment
/stats                # View statistics
/members              # List all members
```

---

## 📱 USER FLOW

```
1. User: /start
   ↓
2. Bot: Shows welcome & "Join Membership" button
   ↓
3. User: Clicks "Join Membership"
   ↓
4. Bot: Shows ₹99 plan
   ↓
5. User: Clicks "Get Lifetime Access"
   ↓
6. Bot: Sends QR code + Order ID
   ↓
7. User: Scans QR, pays ₹99
   ↓
8. User: Clicks "✅ I Have Paid"
   ↓
9. Bot: Updates order status
   ↓
10. Bot: Notifies admin
    ↓
11. Admin: Checks UPI app
    ↓
12. Admin: /approve ORD1234567890
    ↓
13. Bot: Creates single-use invite link
    ↓
14. Bot: Sends link to user
    ↓
15. User: Clicks link, joins channel
    ↓
16. Link: Becomes invalid
```

---

## 🔒 SECURITY FEATURES

### Single-Use Links:
- Each user gets unique link
- Works only once
- Cannot be shared
- Expires after 24 hours

### Manual Verification:
- You check each payment
- Prevents fraud
- Block suspicious users
- Full control

### Logging:
- All orders saved to `data/orders.json`
- All members saved to `data/members.json`
- All invite links logged
- Complete audit trail

---

## 💳 PAYMENT SETUP

### You Need:
- Your UPI ID (e.g., `9876543210@paytm`)
- UPI app installed (any: GPay, PhonePe, Paytm, BHIM)

### Payment Flow:
1. User scans QR code
2. Payment goes directly to your UPI
3. You receive payment notification in UPI app
4. You verify and approve
5. Zero fees, 100% to you!

### Supported UPI Apps:
- ✅ Google Pay
- ✅ PhonePe
- ✅ Paytm
- ✅ BHIM
- ✅ Any UPI app

---

## 🐳 DOCKER COMMANDS

### Basic:
```bash
# Start bot
docker-compose up -d

# Stop bot
docker-compose down

# Restart bot
docker-compose restart

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Maintenance:
```bash
# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d

# Enter container
docker-compose exec telegram-bot bash

# View files
docker-compose exec telegram-bot ls -la data/

# Backup data
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

---

## 📊 ADMIN WORKFLOW

### Daily Routine:

**Morning:**
```bash
# Check pending orders
/pending

# View stats
/stats
```

**When Payment Notification Arrives:**
```bash
# 1. Open your UPI app
# 2. Verify payment received
# 3. Note the Order ID from bot message
# 4. Approve:
/approve ORD1234567890
```

**End of Day:**
```bash
# Check statistics
/stats

# List all members
/members
```

---

## 📁 FILE STRUCTURE

```
SEMI_AUTO_BOT/
├── bot.py                 # Main bot code
├── config.py              # Configuration (EDIT THIS)
├── Dockerfile             # Docker image
├── docker-compose.yml     # Docker setup
├── requirements.txt       # Python packages
├── setup.sh              # Quick setup script
├── README.md             # This file
├── SETUP_GUIDE.md        # Detailed guide
├── data/                 # Database (auto-created)
│   ├── orders.json       # Order logs
│   ├── members.json      # Member list
│   └── invite_links.json # Link logs
└── logs/                 # Logs (auto-created)
    └── bot.log           # Bot logs
```

---

## 🐛 TROUBLESHOOTING

### Bot Not Starting?
```bash
# Check logs
docker-compose logs

# Common issues:
# - Invalid bot token → Check config.py
# - Missing Docker → Install Docker
# - Port in use → Change in docker-compose.yml
```

### Single-Use Links Not Working?
```bash
# Verify:
1. Bot is admin in channel? ✅
2. Bot has "Invite Users" permission? ✅
3. Channel ID is correct? ✅
4. Channel is PRIVATE? ✅

# Test:
# Forward channel message to @userinfobot
# Verify channel ID matches config.py
```

### Admin Not Getting Notifications?
```bash
# Check:
1. ADMIN_CHAT_ID correct in config.py? ✅
2. You messaged the bot first? ✅
3. Bot is running? docker-compose ps ✅
```

---

## 🎯 TESTING CHECKLIST

Before going live:

- [ ] Docker installed
- [ ] Bot created via @BotFather
- [ ] Bot token added to config.py
- [ ] Admin Chat ID added
- [ ] UPI ID configured
- [ ] Premium channel created (PRIVATE)
- [ ] Bot added as admin in channel
- [ ] Bot has "Invite Users" permission
- [ ] Channel ID obtained and added
- [ ] config.py fully configured
- [ ] Bot running: `docker-compose ps`
- [ ] Test: Send `/start` to bot
- [ ] Test: Create test order
- [ ] Test: Approve with `/approve ORDER_ID`
- [ ] Test: Verify single-use link works
- [ ] Test: Link expires after use

---

## 💡 PRO TIPS

1. **Test with ₹1 first** - Set `MEMBERSHIP_PRICE = 1` for testing
2. **Respond quickly** - Users wait for approval
3. **Keep UPI app handy** - Check payments immediately
4. **Use order ID** - Always include in UPI transaction notes
5. **Backup regularly** - `tar -czf backup.tar.gz data/`
6. **Monitor logs** - `docker-compose logs -f`
7. **Check pending daily** - `/pending` command

---

## 📈 STATISTICS

### Track Your Growth:

```bash
# Daily stats
/stats

# See all members
/members

# Check pending
/pending
```

### Export Data:

```bash
# Orders
cat data/orders.json

# Members
cat data/members.json

# Backup
docker-compose exec telegram-bot cat data/orders.json > orders_backup.json
```

---

## 🔄 UPDATES & MAINTENANCE

### Update Bot:

```bash
# 1. Stop bot
docker-compose down

# 2. Backup data
tar -czf backup.tar.gz data/ logs/

# 3. Update files
# (replace bot.py or other files)

# 4. Rebuild
docker-compose build --no-cache

# 5. Start
docker-compose up -d
```

### Database Backup:

```bash
# Manual backup
cp data/orders.json data/orders_backup.json

# Automated (cron)
0 2 * * * tar -czf /backups/bot_$(date +\%Y\%m\%d).tar.gz /path/to/data/
```

---

## ❓ FAQ

**Q: Do I need a payment gateway?**  
A: No! Direct UPI payment, zero fees.

**Q: How long does approval take?**  
A: Depends on you. Can be instant or a few hours.

**Q: Can users share invite links?**  
A: No! Single-use links become invalid after first use.

**Q: What if I reject by mistake?**  
A: User can create a new order, or you can manually approve later.

**Q: Do I need coding knowledge?**  
A: No! Just edit config.py and run setup.sh.

**Q: Can I change the price?**  
A: Yes! Edit `MEMBERSHIP_PRICE` in config.py.

**Q: How many users can I handle?**  
A: Unlimited! But approval is manual, so depends on your time.

---

## 🎊 YOU'RE READY!

Your semi-automatic bot is now:
- ✅ Accepting UPI payments
- ✅ Generating QR codes
- ✅ Waiting for your approval
- ✅ Creating single-use links
- ✅ Protecting against fraud
- ✅ Logging everything

**Start accepting members! 🚀**

---

## 📞 SUPPORT

### Documentation:
- `README.md` - This file
- `SETUP_GUIDE.md` - Detailed setup
- Inline code comments

### Commands Help:
```bash
# Send to your bot
/start - Get started
/pending - See pending orders (admin)
/approve ORDER_ID - Approve payment (admin)
/stats - View statistics (admin)
```

---

**Version:** 1.0 Semi-Auto  
**No Gateway Fees** | **Manual Verification** | **Single-Use Links**  
**License:** MIT
