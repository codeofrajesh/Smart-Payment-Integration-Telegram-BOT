
import os
from dotenv import load_dotenv
load_dotenv()
# Helper to get env variable or fallback
def get_env(key, default=None):
    return os.environ.get(key, default)

# ============================================================
# TELEGRAM BOT SETTINGS
# ============================================================

# Bot Token (Get from Heroku Config Vars or fallback to hardcoded)
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", "8488665198:AAHpk_3lzzgrjmnruyooqPANitDfQrGSlpE")

# Bot Name
BOT_NAME = get_env("BOT_NAME", "Premium Membership Bot")

# ============================================================
# ADMIN SETTINGS
# ============================================================

# Admin Username
ADMIN_USERNAME = get_env("ADMIN_USERNAME", "@grandfather009")

# Admin Chat ID
ADMIN_CHAT_ID = get_env("ADMIN_CHAT_ID", "8187329376")

# ============================================================
# PAYMENT SETTINGS
# ============================================================

# Membership price
MEMBERSHIP_PRICE = int(get_env("MEMBERSHIP_PRICE", 109))

# UPI ID
UPI_ID = get_env("UPI_ID", "aniruddha12@fam")

# Merchant Name
MERCHANT_NAME = get_env("MERCHANT_NAME", "Premium Membership")

# ============================================================
# CHANNEL SETTINGS
# ============================================================

# Premium channel ID (ensure it's an integer)
PREMIUM_CHANNEL_ID = int(get_env("PREMIUM_CHANNEL_ID", -1002019773776))

# Fallback invite link
PREMIUM_CHANNEL_LINK = get_env("PREMIUM_CHANNEL_LINK", "https://t.me/+ElNqgNA939BlMDU1")

# ============================================================
# INVITE LINK SETTINGS
# ============================================================

# Link expiry time
INVITE_LINK_EXPIRY_HOURS = int(get_env("INVITE_LINK_EXPIRY_HOURS", 24))

# ============================================================
# DATABASE SETTINGS
# ============================================================

# MongoDB URI (Required for Heroku to save data persistently)
MONGO_URI = get_env("MONGO_URI", None)
