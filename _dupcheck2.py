import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from config.db import db

def recup(x):
    return str(sorted(x.items())) if isinstance(x, dict) else str(x)

mt = db['photos_faceembedding']

# 1. Berapa banyak photo_id yang punya >1 embedding?
pipe = [{'$group': {'_id': '$photo_id', 'n': {'$sum': 1}}},
        {'$group': {'_id': None, 'multi': {'$sum': 1}, 'single': {'$sum': {'$cond': [{'$eq': ['$n', 1]}, 1, 0]}}}}]
agg = list(mt.aggregate(pipe))
print("photo_id dengan >1 embedding / ==1:", agg)

# 2. Periksa bbox duplikat persis pada satu foto contoh 578
docs = list(mt.find({'photo_id': 578}).limit(30))
print("foto 578 punya {} embedding".format(len(docs)))
bboxes = [(d.get('bbox_json'), d.get('face_image')) for d in docs]
uniq = set()
for b, f in bboxes:
    uniq.add((recup(b), f))
print("  unik (bbox,face_image):", len(uniq))
print("  contoh bbox:", bboxes[:2])