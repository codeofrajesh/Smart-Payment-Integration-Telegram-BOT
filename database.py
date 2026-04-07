import json
import logging
from config import MONGO_URI, UPI_ID, MEMBERSHIP_PRICE

logger = logging.getLogger(__name__)

# File Paths
ORDERS_FILE = 'data/orders.json'
MEMBERS_FILE = 'data/members.json'
INVITE_LINKS_FILE = 'data/invite_links.json'
SETTINGS_FILE = 'data/settings.json'
PLANS_FILE = 'data/plans.json'
TRANSLATIONS_FILE = 'data/translations.json'
USERS_FILE = 'data/users.json'

# MongoDB Setup
mongo_client = None
mongo_db = None

if MONGO_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client.get_database()
        logger.info("✅ Connected to MongoDB (Persistent Storage)")
    except Exception as e:
        logger.error(f"❌ MongoDB Connection Failed: {e}")

def load_db(filename, default=None):
    default = default if default is not None else {}
    
    # 1. Try to load from MongoDB first
    if mongo_db is not None:
        try:
            collection = mongo_db['store']
            doc = collection.find_one({"_id": filename})
            
            if doc and 'data' in doc: 
                return doc['data']
            
            # 👇 SEAMLESS AUTO-MIGRATION LOGIC 👇
            # If Mongo is connected but empty, check if we have local JSON files to migrate!
            try:
                with open(filename, 'r') as f: 
                    local_data = json.load(f)
                    # Upload it straight to MongoDB so it's there forever
                    collection.replace_one({"_id": filename}, {"_id": filename, "data": local_data}, upsert=True)
                    logger.info(f"🔄 Successfully migrated {filename} to MongoDB!")
                    return local_data
            except FileNotFoundError:
                return default # No local data exists yet
                
        except Exception as e:
            logger.error(f"MongoDB Load Error: {e}")
            # If Mongo errors out, it drops down to the local file fallback below
            
    # 2. Standard Local Fallback (Used if NO Mongo URI is provided or Mongo crashes)
    try:
        with open(filename, 'r') as f: 
            return json.load(f)
    except FileNotFoundError: 
        return default
    except Exception as e: 
        return default

def save_db(filename, data):
    if mongo_db is not None:
        try:
            collection = mongo_db['store']
            collection.replace_one({"_id": filename}, {"_id": filename, "data": data}, upsert=True)
            return
        except Exception as e: logger.error(f"MongoDB Save Error: {e}")
    try:
        with open(filename, 'w') as f: json.dump(data, f, indent=2, default=str)
    except Exception as e: logger.error(f"Error saving {filename}: {e}")

# Initialize and Export Databases
orders_db = load_db(ORDERS_FILE, {})
members_db = load_db(MEMBERS_FILE, {})
invite_links_db = load_db(INVITE_LINKS_FILE, {})
translations_db = load_db(TRANSLATIONS_FILE, {})
users_db = load_db(USERS_FILE, {})

settings_db = load_db(SETTINGS_FILE, {
    "upi_id": UPI_ID,
    "welcome_msg": "🎉 *Welcome to {bot_name}!* 🎉\n\nGet *Premium Access* today! 🚀\n\n1️⃣ Click Join\n2️⃣ Pay via UPI\n3️⃣ Get Instant Access!",
    "approval_msg": "✅ *PAYMENT APPROVED!*\n\nWelcome to the premium channel! Click below to join:"
})

plans_db = load_db(PLANS_FILE, {
    "plan_1": {"name": "Lifetime Access", "price": MEMBERSHIP_PRICE}
})

if 'cache_translations' not in settings_db:
    settings_db['cache_translations'] = True
    save_db(SETTINGS_FILE, settings_db)