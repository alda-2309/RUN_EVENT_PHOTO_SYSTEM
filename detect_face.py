#!/usr/bin/env python3
# detect_face.py - Deteksi wajah dengan OpenCV

import sys
import json
import cv2
import os

def detect_faces(image_path):
    try:
        # Baca gambar
        img = cv2.imread(image_path)
        if img is None:
            return {'error': 'Gambar tidak ditemukan', 'faces': []}
        
        # Konversi ke grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Load Haar Cascade untuk deteksi wajah
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Deteksi wajah
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # Format hasil
        face_list = []
        for (x, y, w, h) in faces:
            face_list.append({
                'x': int(x),
                'y': int(y),
                'w': int(w),
                'h': int(h)
            })
        
        return {
            'faces': face_list,
            'count': len(face_list)
        }
        
    except Exception as e:
        return {'error': str(e), 'faces': []}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python detect_face.py image_path'}))
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = detect_faces(image_path)
    print(json.dumps(result))