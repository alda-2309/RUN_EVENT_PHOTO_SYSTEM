import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from config.db import db

def ringkas(coll):
    from bson import ObjectId
    col = db[coll]
    n = col.estimated_document_count()
    print("=== {}: {} docs ===".format(coll, n))

    # jumlah foto unik (photo_id)
    pids = col.distinct('photo_id')
    print("  distinct photo_id:", len(pids))

    # duplikat berdasar (photo_id, ekspresi lain)?
    # kadang faceembedding punya field face_index / crop_index
    sampel = col.find_one({})
    if sampel:
        print("  sample keys:", list(sampel.keys()))

    # cek jumlah doc per photo_id > 1
    pipe = [{'$group': {'_id': '$photo_id', 'n': {'$sum': 1}}},
            {'$match': {'n': {'$gt': 1}}},
            {'$sort': {'n': -1}}, {'$limit': 10}]
    dups = list(col.aggregate(pipe))
    print("  photo_id yg punya >1 embedding (top10):", dups)
    return n

mtcnn = ringkas('photos_faceembedding')
print()
blaze = ringkas('photos_faceembedding_blaze')
print()
foto = db['photos_photoevent'].count_documents({})
foto_blaze = db['photos_photoevent_blaze'].count_documents({})
print("photos_photoevent:", foto, "| photos_photoevent_blaze:", foto_blaze)