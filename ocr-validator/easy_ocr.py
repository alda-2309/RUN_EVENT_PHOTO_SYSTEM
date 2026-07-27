#!/usr/bin/env python3
# easy_ocr.py - EasyOCR CEPAT (dengan caching)

import sys
import json
import time
import os
import re
import warnings
warnings.filterwarnings('ignore')

# ============================================
# GLOBAL READER - LOAD SEKALI SAJA
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

def run_ocr(image_path):
    try:
        if not os.path.exists(image_path):
            return {'error': f'File tidak ditemukan: {image_path}'}
        
        reader = get_reader()
        if reader is None:
            return {'error': 'EasyOCR tidak terinstal'}
        
        # ============================================
        # PARAMETER CEPAT
        # ============================================
        start_time = time.time()
        result = reader.readtext(
            image_path,
            detail=0,          # Hanya teks
            paragraph=False,   # Tidak perlu paragraf
            decoder='greedy',  # LEBIH CEPAT
            beamWidth=1        # Minimal
        )
        processing_time = time.time() - start_time
        
        full_text = ' '.join(result) if result else ''
        numbers_only = ''.join(re.findall(r'\d+', full_text))
        
        if len(numbers_only) > 4:
            numbers_only = numbers_only[-4:]
        
        return {
            'text': full_text.strip(),
            'numbers': numbers_only,
            'time': processing_time,
            'lines': len(result)
        }
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python easy_ocr.py image_path'}))
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = run_ocr(image_path)
    print(json.dumps(result))