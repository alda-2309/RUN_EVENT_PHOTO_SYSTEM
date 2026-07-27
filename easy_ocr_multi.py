#!/usr/bin/env python3
# easy_ocr_multi.py - EasyOCR Multi BIB (Blur + Banyak Orang)

import sys
import json
import time
import os
import re
import warnings
warnings.filterwarnings('ignore')

# ============================================
# GLOBAL READER - CACHE
# ============================================
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
            _reader = easyocr.Reader(['en', 'id'], gpu=False, verbose=False)
        except ImportError:
            return None
    return _reader

def preprocess_image(image_path):
    """Preprocessing untuk gambar blur"""
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Resize jika terlalu kecil
        height, width = img.shape[:2]
        if height < 600 or width < 600:
            scale = max(600/height, 600/width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Sharpening untuk mengurangi blur
        kernel = np.array([[-1,-1,-1],
                           [-1, 9,-1],
                           [-1,-1,-1]])
        sharpened = cv2.filter2D(img, -1, kernel)
        
        # Contrast enhancement
        lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        enhanced = cv2.merge((l, a, b))
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        # Simpan sementara
        temp_path = sys_get_temp_dir() + '/easy_multi_' + str(time.time()) + '.png'
        cv2.imwrite(temp_path, enhanced)
        return temp_path
    except Exception as e:
        return image_path

def extract_all_bibs(text):
    """Ekstrak semua angka 2-4 digit"""
    numbers = re.findall(r'\b\d{2,4}\b', text)
    return numbers

def run_ocr(image_path):
    try:
        if not os.path.exists(image_path):
            return {'error': f'File tidak ditemukan: {image_path}'}
        
        # Preprocessing untuk blur
        processed_path = preprocess_image(image_path)
        
        reader = get_reader()
        if reader is None:
            return {'error': 'EasyOCR tidak terinstal'}
        
        # OCR dengan parameter cepat
        start_time = time.time()
        result = reader.readtext(
            processed_path,
            detail=0,
            paragraph=False,
            decoder='greedy',
            beamWidth=1
        )
        processing_time = time.time() - start_time
        
        # Cleanup
        if processed_path != image_path and os.path.exists(processed_path):
            os.remove(processed_path)
        
        full_text = ' '.join(result) if result else ''
        bib_numbers = extract_all_bibs(full_text)
        
        # Hapus duplikat
        unique_bibs = list(set(bib_numbers))
        sorted_bibs = sorted(unique_bibs)
        
        return {
            'text': full_text.strip(),
            'bib_numbers': sorted_bibs,
            'bib_count': len(sorted_bibs),
            'time': processing_time,
            'lines': len(result)
        }
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python easy_ocr_multi.py image_path'}))
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = run_ocr(image_path)
    print(json.dumps(result))