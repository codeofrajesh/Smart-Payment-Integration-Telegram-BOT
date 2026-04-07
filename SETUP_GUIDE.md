# 📖 COMPLETE SETUP GUIDE
## Semi-Automatic Telegram Membership Bot

---

## 🎯 WHAT YOU'LL BUILD

A bot that:
- Shows QR codes for UPI payment
- Lets users confirm payment
- Notifies you for manual approval
- Creates single-use invite links
- Grants channel access automatically after your approval
- **Zero payment gateway fees!**

---

## ⏱️ TIME REQUIRED

- **First time:** 30 minutes
- **Already have Docker:** 10 minutes
- **Experienced:** 5 minutes

---

## 📋 PREREQUISITES

### You Need:
1. ✅ Computer/VPS (Linux recommended)
2. ✅ Telegram account
3. ✅ UPI ID (any UPI app)
4. ✅ Basic command line knowledge

### Optional But Recommended:
- VPS for 24/7 operation (DigitalOcean, AWS, Linode)
- Domain name (for better appearance)

---

## 🚀 STEP-BY-STEP SETUP

### STEP 1: INSTALL DOCKER

#### On Ubuntu/Debian:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose -y

# Add your user to docker group
sudo usermod -aG docker $USER

# Logout and login for changes to take effect
# Or run: newgrp docker

# Verify installation
docker --version
docker-compose --version
```

#### On Other Systems:
- **Windows:** Download Docker Desktop from docker.com
- **Mac:** Download Docker Desktop for Mac
- **CentOS/RHEL:** Use `yum install docker docker-compose`

---

### STEP 2: CREATE TELEGRAM BOT

#### 2.1 Open Telegram

On your phone or https://web.telegram.org

#### 2.2 Message @BotFather

Search for: `@BotFather`

#### 2.3 Create Bot

Send these commands:
```
/newbot
```

Follow the prompts:
- **Bot name:** "Premium Membership Bot" (can be anything)
- **Username:** "premium_member_bot" (must end with 'bot')

#### 2.4 Copy Token

You'll receive:
```
Done! Congratulations on your new bot...

Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

Keep your token secure...
```

**COPY THIS TOKEN!** You'll need it in config.py

#### 2.5 Set Bot Commands (Optional)

Send to @BotFather:
```
/setcommands
```

Select your bot, then send:
```
start - Start the bot
pending - View pending orders (admin)
approve - Approve payment (admin)
reject - Reject payment (admin)
stats - View statistics (admin)
members - List all members (admin)
```

---

### STEP 3: GET YOUR ADMIN CHAT ID

#### 3.1 Message @userinfobot

Search for: `@userinfobot` on Telegram

#### 3.2 Get Your ID

Send: `/start`

You'll receive:
```
Your User ID: 123456789
Your Username: @yourname
```

**COPY YOUR USER ID!** You'll need it in config.py

---

### STEP 4: CREATE PREMIUM CHANNEL

#### 4.1 Create Channel

1. Open Telegram
2. Click **New Channel**
3. Enter channel name: "Premium Content"
4. Enter description (optional)
5. **IMPORTANT:** Select "Private channel"

#### 4.2 Add Bot as Admin

1. In channel, click **Subscribers**
2. Click **Add Administrators**
3. Search for your bot (by username)
4. Add it as admin
5. **CRITICAL:** Enable permission "Invite Users via Link"
6. Save

#### 4.3 Get Channel ID

1. In your channel, send any message
2. Forward that message to **@userinfobot**
3. You'll receive:
```
Message from: Premium Content
Chat ID: -1001234567890
```

**COPY THE CHAT ID!** (including the minus sign)

---

### STEP 5: SETUP UPI PAYMENT

#### 5.1 Get Your UPI ID

Open your UPI app (GPay/PhonePe/Paytm):

**Google Pay:**
1. Open GPay
2. Tap your profile photo
3. Tap "UPI ID"
4. Copy your UPI ID (e.g., `yourname@okaxis`)

**PhonePe:**
1. Open PhonePe
2. Tap profile icon
3. Tap "My UPI ID"
4. Copy UPI ID (e.g., `9876543210@ybl`)

**Paytm:**
1. Open Paytm
2. Tap profile
3. Tap "UPI & Linked Bank Accounts"
4. Copy UPI ID (e.g., `9876543210@paytm`)

**Your UPI ID format:** `something@bank`

Examples:
- `yourname@paytm`
- `9876543210@ybl`
- `yourname@okaxis`

**COPY YOUR UPI ID!**

---

### STEP 6: EXTRACT BOT FILES

```bash
# Extract ZIP
unzip SEMI_AUTO_BOT.zip

# Navigate to folder
cd SEMI_AUTO_BOT

# Check files
ls -la
```

You should see:
- `bot.py`
- `config.py`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `setup.sh`
- `README.md`

---

### STEP 7: CONFIGURE BOT

#### 7.1 Open config.py

```bash
nano config.py
```

Or use any text editor.

#### 7.2 Fill in Your Details

Find these lines and replace:

```python
# 1. BOT TOKEN (from @BotFather)
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
# ↑ Paste your bot token here

# 2. ADMIN CHAT ID (from @userinfobot)
ADMIN_CHAT_ID = "123456789"
# ↑ Paste your user ID here

# 3. UPI ID (from your UPI app)
UPI_ID = "9876543210@paytm"
# ↑ Paste your UPI ID here

# 4. CHANNEL ID (from @userinfobot)
PREMIUM_CHANNEL_ID = -1001234567890
# ↑ Paste your channel ID here (with minus sign!)
```

#### 7.3 Optional: Customize

```python
# Change price
MEMBERSHIP_PRICE = 99  # Change to any amount

# Change merchant name
MERCHANT_NAME = "Your Business Name"

# Change link expiry
INVITE_LINK_EXPIRY_HOURS = 24  # Hours before link expires
```

#### 7.4 Save File

- In nano: Press `Ctrl+X`, then `Y`, then `Enter`
- In other editors: Save normally

---

### STEP 8: RUN BOT

#### 8.1 Quick Setup (Automated)

```bash
# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

This will:
1. ✅ Check Docker installation
2. ✅ Create necessary directories
3. ✅ Build Docker image
4. ✅ Start the bot
5. ✅ Show status

#### 8.2 Manual Setup (Alternative)

```bash
# Create directories
mkdir -p data logs

# Build Docker image
docker-compose build

# Start bot
docker-compose up -d

# Check status
docker-compose ps
```

---

### STEP 9: VERIFY BOT IS RUNNING

#### 9.1 Check Docker Status

```bash
docker-compose ps
```

Should show:
```
NAME                    STATUS
semi_auto_membership_bot   Up X seconds
```

#### 9.2 Check Logs

```bash
docker-compose logs -f
```

You should see:
```
🚀 Semi-Automatic Bot Started!
💳 Payment: UPI (No Gateway Fees)
✅ Verification: Manual by Admin
🔒 Links: Single-use with expiry
```

Press `Ctrl+C` to stop viewing logs.

---

### STEP 10: TEST THE BOT

#### 10.1 Start Bot

1. Open Telegram
2. Search for your bot (by username)
3. Send `/start`

You should see welcome message with buttons.

#### 10.2 Test Order Creation

1. Click "🚀 Join Membership"
2. Click "📦 Get Lifetime Access"
3. You should see QR code and payment instructions

#### 10.3 Test Admin Notification

1. Click "✅ I Have Paid"
2. **You** (admin) should receive a notification
3. Notification includes order ID and approve/reject buttons

#### 10.4 Test Approval

1. Check the order ID from notification
2. Send to bot: `/approve ORD1234567890` (use real order ID)
3. Bot should create invite link
4. User should receive the link

#### 10.5 Test Invite Link

1. Click the invite link
2. You should be able to join the channel
3. Try clicking again - link should be invalid

**All working? You're ready! 🎉**

---

## 🔧 ADDITIONAL CONFIGURATION

### Change Bot Messages

Edit `bot.py`:

**Welcome message:** Line ~110
```python
welcome_message = f"""
🎉 **Your custom welcome message here**
"""
```

**Payment message:** Line ~290
```python
payment_message = f"""
💳 **Your custom payment instructions**
"""
```

After editing:
```bash
docker-compose restart
```

### Change Price

Edit `config.py`:
```python
MEMBERSHIP_PRICE = 199  # Change to any amount
```

Restart:
```bash
docker-compose restart
```

---

## 📊 DAILY OPERATIONS

### Morning Routine:

```bash
# Check if bot is running
docker-compose ps

# View today's stats
# (send /stats to your bot on Telegram)

# Check pending orders
# (send /pending to your bot)
```

### When Payment Arrives:

1. You receive Telegram notification
2. Open your UPI app
3. Verify payment received
4. Note the order ID
5. Send to bot: `/approve ORDER_ID`
6. Done!

### End of Day:

```bash
# View statistics
# (send /stats to bot)

# Backup data
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

---

## 🔄 BACKUP & RESTORE

### Daily Backup:

```bash
# Create backup
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/ config.py

# Upload to cloud (optional)
# Use rsync, scp, or cloud storage
```

### Restore from Backup:

```bash
# Stop bot
docker-compose down

# Restore files
tar -xzf backup_20260203.tar.gz

# Start bot
docker-compose up -d
```

### Automated Backup (Cron):

```bash
# Edit crontab
crontab -e

# Add this line (backup daily at 2 AM):
0 2 * * * tar -czf /backups/bot_$(date +\%Y\%m\%d).tar.gz /path/to/SEMI_AUTO_BOT/data/
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: Bot Not Starting

**Error:** `Invalid token`

**Solution:**
```bash
# Check config.py
nano config.py

# Verify TELEGRAM_BOT_TOKEN is correct
# Get new token from @BotFather if needed
```

---

### Issue 2: Admin Not Getting Notifications

**Possible causes:**
- Wrong ADMIN_CHAT_ID
- You haven't started the bot yet

**Solution:**
```bash
# 1. Verify ADMIN_CHAT_ID in config.py
nano config.py

# 2. Get correct ID from @userinfobot
# 3. Update config.py
# 4. Restart bot
docker-compose restart

# 5. Send /start to your bot first!
```

---

### Issue 3: Single-Use Links Not Working

**Error:** "Failed to create invite link"

**Checklist:**
1. ✅ Is bot admin in channel?
2. ✅ Does bot have "Invite Users via Link" permission?
3. ✅ Is channel PRIVATE?
4. ✅ Is PREMIUM_CHANNEL_ID correct?

**Solution:**
```bash
# 1. Go to your Telegram channel
# 2. Check bot is in Administrators list
# 3. Verify "Invite Users via Link" is enabled
# 4. Forward message to @userinfobot
# 5. Verify channel ID matches config.py
# 6. Restart bot
docker-compose restart
```

---

### Issue 4: Docker Not Found

**Error:** `docker: command not found`

**Solution:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Verify
docker --version
```

---

### Issue 5: Permission Denied

**Error:** `permission denied while trying to connect to Docker`

**Solution:**
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Logout and login again
# Or run:
newgrp docker

# Try again
docker-compose ps
```

---

## ✅ FINAL CHECKLIST

Before going live, verify:

**Setup:**
- [ ] Docker installed and working
- [ ] Bot created via @BotFather
- [ ] Bot token copied
- [ ] Admin Chat ID obtained
- [ ] UPI ID configured
- [ ] Premium channel created (PRIVATE)
- [ ] Bot added as admin in channel
- [ ] Bot has "Invite Users" permission
- [ ] Channel ID obtained
- [ ] config.py fully configured
- [ ] Bot built: `docker-compose build`
- [ ] Bot started: `docker-compose up -d`
- [ ] Bot running: `docker-compose ps`

**Testing:**
- [ ] Sent /start to bot
- [ ] Clicked "Join Membership"
- [ ] Saw QR code
- [ ] Clicked "Payment Done"
- [ ] Received admin notification
- [ ] Ran `/approve ORDER_ID`
- [ ] User received invite link
- [ ] Clicked link and joined channel
- [ ] Link became invalid after use

**Optional:**
- [ ] Customized messages
- [ ] Changed price
- [ ] Setup backup script
- [ ] Configured monitoring

**All checked? You're ready to go live! 🚀**

---

## 🎯 GOING LIVE

### Before Accepting Real Payments:

1. **Test with ₹1:**
   ```python
   # In config.py
   MEMBERSHIP_PRICE = 1
   ```
   - Restart bot
   - Complete a real ₹1 transaction
   - Verify full flow works
   - Then change back to ₹99

2. **Prepare your UPI:**
   - Ensure enough balance for testing
   - Enable notifications
   - Keep app handy for quick verification

3. **Set expectations:**
   - Tell users approval time (1 hour typical)
   - Provide admin contact for issues
   - Be available during business hours

4. **Monitor closely:**
   - First week: Check every few hours
   - Keep `/pending` ready
   - Respond to admin notifications quickly

---

## 📞 GETTING HELP

### Self-Help:

1. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

2. **View data:**
   ```bash
   cat data/orders.json
   cat data/members.json
   ```

3. **Restart bot:**
   ```bash
   docker-compose restart
   ```

4. **Rebuild:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Documentation:

- `README.md` - Quick reference
- `SETUP_GUIDE.md` - This file
- Code comments in `bot.py`

---

## 🎊 CONGRATULATIONS!

You now have a fully functional semi-automatic membership bot!

**What you achieved:**
- ✅ Set up Docker environment
- ✅ Created and configured Telegram bot
- ✅ Setup premium channel with permissions
- ✅ Configured UPI payment (zero fees!)
- ✅ Deployed bot with Docker
- ✅ Tested full payment flow
- ✅ Ready to accept members!

**Start accepting payments and growing your community! 🚀**

---

**Questions? Check logs, review this guide, or contact support.**
