#!/usr/bin/env python3
"""
Script untuk restore record id 1 yang kehapus ke MongoDB Atlas
"""
from pymongo import MongoClient

# MongoDB connection
MONGO_URI = 'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
MONGO_DB_NAME = 'db_tugasakhir'
COLLECTION_NAME = 'photos_photoevent'

# Data yang akan direstore
restore_data = {
    "_id": "6a6ad69719f4e4f2a43ce9f0",
    "id": 1,
    "event_name": "Bandung Color Run Festival 2026",
    "image": "lomba_lari/colorun/ColorRun_Fest(1).jpg",
    "bib_number": "0183, 05901, 0900, 133, 20, 2026, 212, CO1DR, E9L9E, FS7AI, LH4",
    "uploaded_at": None,
    "ocr_raw_text": "CULOR LOLOR 20 2026 0183 FESTAL 212 PUNC20267 0900 FS7AI E9L9E 05901 QEK JOLF 2026 LH4 BAUGZ CO1DR 133",
    "ocr_updated_at": 1785505923.111201
}

def main():
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB Atlas...")
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Check if record already exists
        existing = collection.find_one({"id": 1})
        if existing:
            print("[WARNING] Record with id=1 already exists!")
            print(f"Existing record: {existing}")
            response = input("Do you want to replace it? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled.")
                return
            
            # Delete existing record
            collection.delete_one({"id": 1})
            print("Deleted existing record.")
        
        # Insert the restored record
        result = collection.insert_one(restore_data)
        print(f"[SUCCESS] Restored record with id=1")
        print(f"MongoDB _id: {result.inserted_id}")
        print(f"Event: {restore_data['event_name']}")
        print(f"Image: {restore_data['image']}")
        
        # Verify
        verify = collection.find_one({"id": 1})
        print(f"\n[SUCCESS] Verification: Record exists in database")
        print(f"ID: {verify['id']}")
        print(f"Event: {verify['event_name']}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
