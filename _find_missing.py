#!/usr/bin/env python3
"""
Script untuk compare backup vs database dan cari record yang hilang
Cuma ambil ID aja biar hemat
"""
from pymongo import MongoClient
import json

# MongoDB connection
MONGO_URI = 'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
MONGO_DB_NAME = 'db_tugasakhir'
COLLECTION_NAME = 'photos_photoevent'
BACKUP_FILE = 'backup/mongo_backup_20260802_085514/atlas/photos_photoevent.json'

def main():
    try:
        # Load backup IDs only
        print("Loading backup file...")
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        backup_ids = set(record['id'] for record in backup_data)
        print(f"Backup contains {len(backup_ids)} records")
        print(f"ID range: {min(backup_ids)} - {max(backup_ids)}")
        
        # Connect to MongoDB and get current IDs only
        print("\nConnecting to MongoDB Atlas...")
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Get only IDs from database (efficient query)
        db_records = list(collection.find({}, {'id': 1, '_id': 0}))
        db_ids = set(record['id'] for record in db_records)
        print(f"Database contains {len(db_ids)} records")
        print(f"ID range: {min(db_ids)} - {max(db_ids)}")
        
        # Find missing IDs
        missing_ids = backup_ids - db_ids
        extra_ids = db_ids - backup_ids
        
        print("\n" + "="*60)
        if missing_ids:
            print(f"[FOUND] {len(missing_ids)} record(s) MISSING from database:")
            missing_list = sorted(list(missing_ids))
            print(f"Missing IDs: {missing_list}")
            
            # Show details of missing records
            print("\nDetails of missing records:")
            for record_id in missing_list[:10]:  # Show first 10 only
                record = next(r for r in backup_data if r['id'] == record_id)
                print(f"\n  ID: {record_id}")
                print(f"  Event: {record['event_name']}")
                print(f"  Image: {record['image']}")
        else:
            print("[OK] No missing records. Database matches backup.")
        
        if extra_ids:
            print(f"\n[INFO] {len(extra_ids)} record(s) in database but NOT in backup:")
            print(f"Extra IDs: {sorted(list(extra_ids))[:20]}")  # Show first 20
        
        print("="*60)
        
        client.close()
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
