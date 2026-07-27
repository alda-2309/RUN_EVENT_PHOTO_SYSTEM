"""Reset password untuk user yang dimigrasi dari SQLite"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from config.db import users_collection
from django.contrib.auth.hashers import make_password

# Reset password untuk user yang ada
new_password = "admin123"

for user in users_collection.find():
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": make_password(new_password)}}
    )
    print(f"  Reset password for {user['username']} -> {new_password}")

print()
print("Done! You can now login with:")
print("  username: bunga10 / password: admin123")
print("  username: bunga13 / password: admin123")
