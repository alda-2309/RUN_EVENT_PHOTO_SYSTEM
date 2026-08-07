"""
Sinkronisasi collection 'events' & 'event_types' admin agar MENGIKUTI data
foto yang ada di 'photos_photoevent' (event_name & jenis_event).

Keputusan:
  - Event "Ground Truth Tambahan" TIDAK ikut jadi event admin (data uji).
  - Nama event milo di photos ('milo_race_2026') di-update jadi 'Milo Race 2026'
    (nama display), konsisten di semua collection yang menyimpan event_name.
  - events & event_types lama yang salah/sampah dihapus, diganti data valid.
  - map_points/map_routes tetap menunjuk event_id 1 (event pertama = Color Run).

Sebelum menulis, script mem-backup collection yang disentuh ke file JSON.
"""
import json
import os
from datetime import datetime

from pymongo import MongoClient

ATLAS = 'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/?retryWrites=true&w=majority'
DB = 'db_tugasakhir'

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups_events_types')
os.makedirs(BACKUP_DIR, exist_ok=True)

# Collection yang menyimpan event_name (untuk update nama milo)
EVENT_NAME_COLLECTIONS = [
    'photos_photoevent',
    'photos_photoevent_blaze',
    'photos_faceembedding',
    'photos_faceembedding_blaze',
]

# Urutan event admin -> _id 1..n (Color Run tetap id 1 agar map_points/map_routes tidak putus)
# name, jenis_event (dari photos), timestamp (dari photos), location (dari data acara)
EVENT_SOURCE = {
    'Bandung Color Run Festival 2026': {
        'folder': 'colorun',
        'jenis_event': 'color run 5k',
        'timestamp': '2026-05-17 06:00:00',
        'location': 'Laswi Heritage, Bandung',
    },
    'Tiento Run 2026': {
        'folder': 'tientorun',
        'jenis_event': '10k',
        'timestamp': '2026-06-28 06:00:00',
        'location': 'Balai Kota, Bandung',
    },
    'Milo Race 2026': {
        'folder': 'milo_race_2026',
        'jenis_event': '2,5k dan 5k',
        'timestamp': '2026-07-19 05:00:00',
        'location': 'Balai Kota, Bandung',
    },
}

EXCLUDED_EVENT = 'Ground Truth Tambahan'


def backup(db, colls):
    backup_path = os.path.join(BACKUP_DIR, f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    payload = {}
    for col in colls:
        payload[col] = [
            {k: (v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else v)
             for k, v in doc.items()}
            for doc in db[col].find({})
        ]
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
    print(f'[BACKUP] ditulis ke {backup_path}')
    return backup_path


def _parse_ts(s):
    if isinstance(s, datetime):
        return s
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def main():
    client = MongoClient(ATLAS, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=15000)
    db = client[DB]

    # 0. Validasi: semua event di EVENT_SOURCE harus ada di photos
    valid_events = [e for e in db['photos_photoevent'].distinct('event_name')
                    if e and e != EXCLUDED_EVENT]
    print('Event valid di photos_photoevent:', valid_events)

    # Nama mentah di photos -> nama display event (milo_race_2026 -> Milo Race 2026)
    RAW_TO_DISPLAY = {'milo_race_2026': 'Milo Race 2026'}
    display_in_photos = {RAW_TO_DISPLAY.get(e, e) for e in valid_events}
    missing = [name for name in EVENT_SOURCE if name not in display_in_photos]
    if missing:
        print(f'[BATAL] Event berikut tidak ditemukan di photos_photoevent: {missing}')
        client.close()
        return

    # 1. Backup collection yang akan disentuh
    backup(db, ['events', 'event_types', 'map_points', 'map_routes'])

    # 2. Update event_name milo di semua collection foto
    for col in EVENT_NAME_COLLECTIONS:
        res = db[col].update_many(
            {'event_name': 'milo_race_2026'},
            {'$set': {'event_name': 'Milo Race 2026'}},
        )
        print(f'[UPDATE] {col}: {res.modified_count} dokumen milo_race_2026 -> Milo Race 2026')

    # 3. Rebuild events (urut by timestamp -> Color Run id 1)
    events = []
    for idx, (name, info) in enumerate(EVENT_SOURCE.items(), start=1):
        events.append({
            '_id': idx,
            'name': name,
            'event_type': info['jenis_event'],
            'timestamp': _parse_ts(info['timestamp']),
            'location': info['location'],
            'folder': info['folder'],
        })
    db['events'].delete_many({})
    db['events'].insert_many(events)
    print(f'[SYNC] events: {len(events)} event ditulis')

    # 4. Rebuild event_types dari jenis_event yang benar-benar dipakai photos
    jenis_list = sorted(db['photos_photoevent'].distinct('jenis_event'))
    event_types = [
        {'_id': idx, 'name': name, 'order': idx - 1, 'created_at': datetime.utcnow()}
        for idx, name in enumerate(jenis_list, start=1)
    ]
    db['event_types'].delete_many({})
    db['event_types'].insert_many(event_types)
    print(f'[SYNC] event_types: {len(event_types)} jenis ditulis: {jenis_list}')

    # 5. Update counter agar ID berikutnya tidak bentrok
    db['counters'].update_one(
        {'_id': 'events'}, {'$set': {'seq': len(events)}}, upsert=True)
    db['counters'].update_one(
        {'_id': 'event_types'}, {'$set': {'seq': len(event_types)}}, upsert=True)

    # 6. Pastikan map_points/map_routes tetap menunjuk event yang valid (id 1)
    map_events = db['map_points'].distinct('event_id')
    for ev_id in map_events:
        if not db['events'].find_one({'_id': ev_id}):
            res = db['map_points'].update_many({'event_id': ev_id}, {'$set': {'event_id': 1}})
            print(f'[MAP] map_points event_id {ev_id} -> 1 ({res.modified_count} docs)')
    for ev_id in db['map_routes'].distinct('event_id'):
        if not db['events'].find_one({'_id': ev_id}):
            res = db['map_routes'].update_many({'event_id': ev_id}, {'$set': {'event_id': 1}})
            print(f'[MAP] map_routes event_id {ev_id} -> 1 ({res.modified_count} docs)')

    # 7. Verifikasi
    print('\n=== VERIFIKASI ===')
    for e in db['events'].find({}, {'_id': 1, 'name': 1, 'event_type': 1, 'timestamp': 1, 'location': 1, 'folder': 1}).sort('_id', 1):
        print(' ', json.dumps(e, default=str))
    print('event_types:', db['event_types'].distinct('name'))

    client.close()
    print('\n=== DONE ===')


if __name__ == '__main__':
    main()
