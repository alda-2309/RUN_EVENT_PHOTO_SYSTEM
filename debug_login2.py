import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth.hashers import check_password, identify_hasher

# Original hash from SQLite
password_hash = "pbkdf2_sha256$1200000$jl58th5hV1rlF2gWyEstpC$BS+wgSGQ+mCKrJIoUHEbXiWtOfuaui9CBfvZ57HisFU="
plaintext = "bungaaa1212"

print("Testing password verification...")
print(f"Hash: {password_hash}")

# Try identify hasher
try:
    hasher = identify_hasher(password_hash)
    print(f"Hasher algorithm: {hasher.algorithm}")
except Exception as e:
    print(f"Hasher identification failed: {e}")

# Try check_password
result = check_password(plaintext, password_hash)
print(f"check_password result: {result}")

# Try with setter
from django.contrib.auth.hashers import make_password
new_hash = make_password(plaintext)
print(f"New hash: {new_hash}")

result2 = check_password(plaintext, new_hash)
print(f"New hash verify: {result2}")
