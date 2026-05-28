from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient

from api.config import api_settings

# Initialize Async MongoDB client with a 2-second fail-fast timeout
client = AsyncIOMotorClient(api_settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
db = client[api_settings.MONGODB_DB_NAME]
users_collection = db["users"]

# Resilient local development fallback variables
is_mongodb_available = True

IN_MEMORY_USERS: Dict[str, Dict[str, Any]] = {
    "admin@klegally.com": {
        "user_id": "user_admin_01",
        "email": "admin@klegally.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$DxCgiXyby6vTKaz6zDm3XQ$d3PeAjBCfpttTg9WmRKY27lfeFtkXizOecpYoIfc9DU", # Password: AdminPassword123!
        "role": "admin",
        "org_id": "org_klegally",
    },
    "user@klegally.com": {
        "user_id": "user_regular_02",
        "email": "user@klegally.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$DxCgiXyby6vTKaz6zDm3XQ$d3PeAjBCfpttTg9WmRKY27lfeFtkXizOecpYoIfc9DU", # Password: AdminPassword123!
        "role": "user",
        "org_id": "org_klegally",
    }
}


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a user from the MongoDB database by their email.
    Falls back gracefully to the high-fidelity in-memory store if MongoDB is offline.
    """
    global is_mongodb_available
    if not is_mongodb_available:
        return IN_MEMORY_USERS.get(email.lower())

    try:
        user = await users_collection.find_one({"email": email.lower()})
        return user
    except Exception as e:
        is_mongodb_available = False
        print(f"\n[Warning] MongoDB connection failed: {e}")
        print("[System] Falling back automatically to In-Memory backup store for local dev!\n")
        return IN_MEMORY_USERS.get(email.lower())


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a user from the MongoDB database by their unique user_id.
    Falls back gracefully to the high-fidelity in-memory store if MongoDB is offline.
    """
    global is_mongodb_available
    if not is_mongodb_available:
        for user in IN_MEMORY_USERS.values():
            if user["user_id"] == user_id:
                return user
        return None

    try:
        user = await users_collection.find_one({"user_id": user_id})
        return user
    except Exception as e:
        is_mongodb_available = False
        print(f"\n[Warning] MongoDB connection failed: {e}")
        print("[System] Falling back automatically to In-Memory backup store for local dev!\n")
        for user in IN_MEMORY_USERS.values():
            if user["user_id"] == user_id:
                return user
        return None


async def insert_user(new_user: Dict[str, Any]) -> None:
    """
    Inserts a user record into the database, or in-memory backup if offline.
    """
    global is_mongodb_available
    if not is_mongodb_available:
        IN_MEMORY_USERS[new_user["email"].lower()] = new_user
        return

    try:
        await users_collection.insert_one(new_user)
    except Exception as e:
        is_mongodb_available = False
        print(f"\n[Warning] MongoDB connection failed on insert: {e}")
        print("[System] Falling back automatically to In-Memory backup store for local dev!\n")
        IN_MEMORY_USERS[new_user["email"].lower()] = new_user


async def seed_database():
    """
    Seed the database on application startup if it's currently empty.
    Falls back gracefully if MongoDB is not reachable.
    """
    global is_mongodb_available
    try:
        count = await users_collection.count_documents({})
        if count == 0:
            print("Database is empty. Seeding KLegally mock users into MongoDB...")
            seed_users = [
                {
                    "user_id": "user_admin_01",
                    "email": "admin@klegally.com",
                    "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$DxCgiXyby6vTKaz6zDm3XQ$d3PeAjBCfpttTg9WmRKY27lfeFtkXizOecpYoIfc9DU", # Password: AdminPassword123!
                    "role": "admin",
                    "org_id": "org_klegally",
                },
                {
                    "user_id": "user_regular_02",
                    "email": "user@klegally.com",
                    "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$DxCgiXyby6vTKaz6zDm3XQ$d3PeAjBCfpttTg9WmRKY27lfeFtkXizOecpYoIfc9DU", # Password: AdminPassword123!
                    "role": "user",
                    "org_id": "org_klegally",
                }
            ]
            await users_collection.insert_many(seed_users)
            print("MongoDB database seeding complete!")
    except Exception as e:
        is_mongodb_available = False
        print(f"\n[Notice] Skipped seeding: local MongoDB connection not available ({e}).")
        print("[System] API initialized using in-memory store fallback.\n")
