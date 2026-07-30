# photos/test_accuracy.py

import os
import sys
import django
import numpy as np

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from photos.models import PhotoEvent, FaceEmbedding
from photos.face_utils import FaceProcessor

def test_accuracy():
    """Test akurasi face recognition"""
    
    processor = FaceProcessor()
    THRESHOLD = 0.50
    
    # Data test: mapping nama subjek ke ID foto mereka
    # Pastikan ID ini sesuai dengan database kamu!
    test_data = {
        'Alya': [1074, 1075, 1077, 1079],
        'Ira': [740, 741, 894, 558],
        'Dida': [448, 739, 738],
        'Fian': [741, 894, 556],
    }
    
    print("\n" + "="*60)
    print("📊 TESTING AKURASI FACE RECOGNITION")
    print(f"Threshold: {THRESHOLD}")
    print("="*60)
    
    results = []
    
    for nama, photo_ids in test_data.items():
        print(f"\n👤 Testing: {nama}")
        print(f"   Foto referensi ID: {photo_ids[0]}")
        print(f"   Total foto subjek: {len(photo_ids)}")
        
        # Ambil embedding dari foto pertama sebagai referensi
        ref_face = FaceEmbedding.objects.filter(photo_id=photo_ids[0]).first()
        
        if not ref_face:
            print(f"   ❌ Data tidak ditemukan untuk ID {photo_ids[0]}")
            continue
        
        ref_embedding = np.frombuffer(ref_face.embedding_data, dtype=np.float32)
        ref_embedding = processor.normalize_embedding(ref_embedding)
        
        # Test semua foto di database
        all_faces = FaceEmbedding.objects.select_related('photo').all()
        true_positive = 0
        false_positive = 0
        false_negative = 0
        true_negative = 0
        
        for face in all_faces:
            db_embedding = np.frombuffer(face.embedding_data, dtype=np.float32)
            db_embedding = processor.normalize_embedding(db_embedding)
            
            similarity, distance = processor.calculate_similarity(ref_embedding, db_embedding)
            
            is_same_person = face.photo_id in photo_ids
            is_match = distance <= THRESHOLD
            
            if is_match and is_same_person:
                true_positive += 1
            elif is_match and not is_same_person:
                false_positive += 1
            elif not is_match and is_same_person:
                false_negative += 1
            elif not is_match and not is_same_person:
                true_negative += 1
        
        total = true_positive + false_positive + false_negative + true_negative
        
        # Hitung metrik
        precision = (true_positive / (true_positive + false_positive)) * 100 if (true_positive + false_positive) > 0 else 0
        recall = (true_positive / (true_positive + false_negative)) * 100 if (true_positive + false_negative) > 0 else 0
        accuracy = ((true_positive + true_negative) / total) * 100 if total > 0 else 0
        
        print(f"   TP={true_positive}, FP={false_positive}, FN={false_negative}, TN={true_negative}")
        print(f"   ✅ Precision: {precision:.2f}%")
        print(f"   ✅ Recall:    {recall:.2f}%")
        print(f"   ✅ Accuracy:  {accuracy:.2f}%")
        
        results.append({
            'nama': nama,
            'tp': true_positive,
            'fp': false_positive,
            'fn': false_negative,
            'tn': true_negative,
            'precision': precision,
            'recall': recall,
            'accuracy': accuracy
        })
    
    # ============================================
    # RINGKASAN
    # ============================================
    print("\n" + "="*60)
    print("📊 RINGKASAN HASIL TESTING")
    print("="*60)
    
    total_precision = 0
    total_recall = 0
    total_accuracy = 0
    
    for r in results:
        print(f"{r['nama']}: Precision={r['precision']:.2f}% | Recall={r['recall']:.2f}% | Accuracy={r['accuracy']:.2f}%")
        total_precision += r['precision']
        total_recall += r['recall']
        total_accuracy += r['accuracy']
    
    if results:
        avg_precision = total_precision / len(results)
        avg_recall = total_recall / len(results)
        avg_accuracy = total_accuracy / len(results)
        
        print("-"*40)
        print(f"📈 RATA-RATA:")
        print(f"   Precision: {avg_precision:.2f}%")
        print(f"   Recall:    {avg_recall:.2f}%")
        print(f"   Accuracy:  {avg_accuracy:.2f}%")
    
    print("="*60)

if __name__ == '__main__':
    test_accuracy()