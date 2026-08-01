import re
from django.test import Client

c = Client()
r = c.get('/galeri/foto/')
print('galeri/foto status:', r.status_code)
html = r.content.decode('utf-8')
opts = re.findall(r'<option value="([^"]+)">([^<]+)</option>', html)
print('Dropdown options:', opts)
