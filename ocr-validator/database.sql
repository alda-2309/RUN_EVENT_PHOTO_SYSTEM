-- Buat database
CREATE DATABASE IF NOT EXISTS ocr_validator;
USE ocr_validator;

CREATE TABLE test_folders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    folder_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE test_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    folder_id INT,
    image_name VARCHAR(255) NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    engine VARCHAR(20) DEFAULT 'tesseract',
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES test_folders(id) ON DELETE CASCADE
);

CREATE TABLE ground_truth (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT UNIQUE,
    true_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES test_images(id) ON DELETE CASCADE
);

CREATE TABLE ocr_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT,
    engine VARCHAR(20) NOT NULL,
    ocr_text TEXT,
    processing_time FLOAT,
    accuracy_score FLOAT,
    character_count INT,
    error_count INT,
    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES test_images(id) ON DELETE CASCADE
);

INSERT INTO test_folders (folder_name, description) VALUES 
('Test Tesseract', 'Folder untuk pengujian Tesseract'),
('Test EasyOCR', 'Folder untuk pengujian EasyOCR'),
('Test Perbandingan', 'Folder untuk perbandingan kedua engine');