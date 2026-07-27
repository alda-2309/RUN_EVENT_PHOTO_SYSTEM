#!/usr/bin/env python3
# easy_ocr_bib.py - EasyOCR CEPAT (Fokus BIB)

import sys
import json
import time
import os
import re
import warnings
warnings.filterwarnings('ignore')

# ============================================
# GLOBAL READER - CACHE (LOAD SEKALI)
# ============================================
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
            # Load model sekali, cache selamanya
            _reader = easyocr.Reader(['en', 'id'], gpu=False, verbose=False)
        except ImportError:
            return None
    return _reader

def extract_bib_numbers(text):
    """Ekstrak angka 2-4 digit (BIB)"""
    numbers = re.findall(r'\b\d{2,4}\b', text)
    return numbers

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
        bib_numbers = extract_bib_numbers(full_text)
        
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
        print(json.dumps({'error': 'Usage: python easy_ocr_bib.py image_path'}))
        sys.exit(1)
    
    image_path = sys.argv[1]
    result = run_ocr(image_path)
    print(json.dumps(result))
    