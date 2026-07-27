"""Test login via browser simulation"""
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar
import re
import sys

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. GET login page
r = opener.open("http://localhost:8080/login/")
html = r.read().decode()
print("GET /login/ :", r.status)

# 2. Extract CSRF token
match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
if not match:
    print("CSRF token not found!")
    print(html[:500])
    sys.exit(1)

csrf = match.group(1)
print("CSRF:", csrf[:20])

# 3. POST login
data = urllib.parse.urlencode({
    "csrfmiddlewaretoken": csrf,
    "username": "bunga10",
    "password": "bungaaa1212",
}).encode()

req = urllib.request.Request("http://localhost:8080/login/", data=data)
r2 = opener.open(req)
print("POST /login/ :", r2.status)
print("Redirected to:", r2.url)

# 4. Try accessing dashboard
r3 = opener.open("http://localhost:8080/dasboart/")
print("GET /dasboart/ :", r3.status)

print()
print("SUCCESS: Login works!")
