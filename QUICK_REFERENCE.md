# ⚡ QUICK REFERENCE CARD

## 🚀 Setup (One Time)
```bash
unzip SEMI_AUTO_BOT.zip
cd SEMI_AUTO_BOT
nano config.py  # Fill in credentials
./setup.sh      # Run
```

## 🎛️ Docker Commands
```bash
docker-compose up -d       # Start
docker-compose down        # Stop
docker-compose restart     # Restart
docker-compose logs -f     # View logs
docker-compose ps          # Status
```

## 👨‍💼 Admin Commands (Send to Bot)
```
/pending              # See pending orders
/approve ORDER_ID     # Approve payment
/reject ORDER_ID      # Reject payment
/stats                # View statistics
/members              # List members
```

## 📋 Configuration File Locations
```
config.py             # Main config
data/orders.json      # Order database
data/members.json     # Member database
logs/bot.log          # Bot logs
```

## 🔄 Daily Workflow
```
1. User pays → You get notification
2. Check UPI app → Verify payment
3. /approve ORDER_ID → Send invite link
```

## 🆘 Emergency Commands
```bash
# Bot crashed
docker-compose restart

# View what's wrong
docker-compose logs --tail=50

# Complete reset
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 💾 Backup
```bash
# Quick backup
tar -czf backup.tar.gz data/ logs/ config.py

# Restore
tar -xzf backup.tar.gz
docker-compose restart
```

## 🐛 Common Fixes

**Bot not starting:**
```bash
# Check config
nano config.py
# Verify TELEGRAM_BOT_TOKEN
docker-compose restart
```

**Links not working:**
```
1. Bot is admin in channel? ✅
2. Has "Invite Users" permission? ✅
3. Channel is PRIVATE? ✅
```

**Admin not notified:**
```
1. ADMIN_CHAT_ID correct? ✅
2. You sent /start to bot first? ✅
```

## 📊 Key Files

| File | Purpose |
|------|---------|
| config.py | Your settings |
| data/orders.json | All orders |
| data/members.json | All members |
| logs/bot.log | Activity log |

## ⚙️ Quick Edit

```bash
# Change price
nano config.py
# Edit MEMBERSHIP_PRICE = 99
docker-compose restart

# Change messages
nano bot.py
# Edit welcome_message (line ~110)
docker-compose restart
```

## 🎯 Testing

```bash
# Test mode (₹1)
nano config.py
# Set MEMBERSHIP_PRICE = 1
docker-compose restart
# Test full flow
# Change back to 99
```

---

**Keep this handy for daily operations!**
