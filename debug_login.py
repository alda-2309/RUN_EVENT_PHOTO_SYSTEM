"""Debug login"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from config.db import authenticate_user, users_collection
from django.contrib.auth.hashers import check_password

# Check users in MongoDB
print("=== Users in MongoDB ===")
for u in users_collection.find():
    print(f"  id={u['_id']} username={u['username']}")
    print(f"  password hash: {u['password'][:50]}...")

# Test authenticate
print()
print("=== Test authenticate_user ===")
result = authenticate_user("bunga10", "bungaaa1212")
if result:
    print("AUTH OK:", result["username"])
else:
    print("AUTH FAILED")
    
    # Debug: check password directly
    user = users_collection.find_one({"username": "bunga10"})
    if user:
        pw_check = check_password("bungaaa1212", user["password"])
        print(f"Direct password check: {pw_check}")
        
        # The password was stored as-is from SQLite (Django hash format pbkdf2_sha256)
        # check_password should work with it
    else:
        print("User not found")
