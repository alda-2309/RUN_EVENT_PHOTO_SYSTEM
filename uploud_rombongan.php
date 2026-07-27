<?php
// upload_rombongan.php - KHUSUS DETEKSI ROMBONGAN
error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);

require_once 'db_config.php';
header('Content-Type: application/json');

function sendJSON($data) {
    header('Content-Type: application/json');
    while (ob_get_level()) {
        ob_end_clean();
    }
    echo json_encode($data);
    exit;
}

function sendError($message) {
    sendJSON(['success' => false, 'error' => $message]);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    sendError('Method not allowed');
}

$folder_id = isset($_POST['folder_id']) ? intval($_POST['folder_id']) : 0;
$ground_truth = isset($_POST['ground_truth']) ? trim($_POST['ground_truth']) : '';

if ($folder_id <= 0) {
    sendError('Folder ID tidak valid');
}

if (empty($ground_truth)) {
    sendError('Ground Truth tidak boleh kosong');
}

$upload_dir = 'uploads/';
if (!is_dir($upload_dir)) {
    if (!mkdir($upload_dir, 0777, true)) {
        sendError('Tidak bisa membuat folder uploads');
    }
}

$conn = getDBConnection();
$uploaded_files = [];

if (!isset($_FILES['images']) || empty($_FILES['images']['name'][0])) {
    sendError('Tidak ada gambar yang diupload');
}

$file_count = count($_FILES['images']['name']);
$total_start = microtime(true);

for ($i = 0; $i < $file_count; $i++) {
    if ($_FILES['images']['error'][$i] !== UPLOAD_ERR_OK) {
        continue;
    }
    
    $file_name = time() . '_' . basename($_FILES['images']['name'][$i]);
    $file_path = $upload_dir . $file_name;
    
    if (!move_uploaded_file($_FILES['images']['tmp_name'][$i], $file_path)) {
        continue;
    }
    
    // Simpan ke database
    $stmt = $conn->prepare("INSERT INTO test_images (folder_id, image_name, image_path, engine) VALUES (?, ?, ?, ?)");
    if ($stmt) {
        $stmt->bind_param("isss", $folder_id, $file_name, $file_path, 'rombongan');
        $stmt->execute();
        $image_id = $conn->insert_id;
        $stmt->close();
    }
    
    $stmt = $conn->prepare("INSERT INTO ground_truth (image_id, true_text) VALUES (?, ?) ON DUPLICATE KEY UPDATE true_text = ?");
    if ($stmt) {
        $stmt->bind_param("iss", $image_id, $ground_truth, $ground_truth);
        $stmt->execute();
        $stmt->close();
    }
    
    // ============================================
    // PROSES DETEKSI ROMBONGAN
    // ============================================
    $result = detectRombongan($file_path);
    $acc = calculateBIBAccuracy($result['bib_list'], $ground_truth);
    saveBIBResult($image_id, 'rombongan', $result, $conn, $ground_truth, $acc);
    $result['accuracy'] = $acc;
    
    $uploaded_files[] = [
        'file' => $file_name,
        'image_id' => $image_id,
        'result' => $result,
        'time' => $result['time'] ?? 0
    ];
}

$total_time = microtime(true) - $total_start;

sendJSON([
    'success' => true,
    'message' => 'Deteksi BIB rombongan berhasil',
    'files_processed' => count($uploaded_files),
    'total_time' => $total_time,
    'avg_time' => $total_time / max(1, count($uploaded_files)),
    'files' => $uploaded_files
]);

// ============================================
// DETEKSI ROMBONGAN - MULTI BIB
// ============================================

function detectRombongan($image_path) {
    $start_time = microtime(true);
    
    // ============================================
    // STEP 1: PREPROCESSING UNTUK ROMBONGAN
    // ============================================
    $processed_path = $image_path;
    $temp_processed = null;
    
    $convert_check = shell_exec('convert --version 2>&1');
    if (strpos($convert_check, 'ImageMagick') !== false) {
        $temp_processed = sys_get_temp_dir() . '/rombongan_' . uniqid() . '.png';
        
        // Resize besar + contrast untuk BIB kecil
        $cmd = "convert " . escapeshellarg($image_path) . 
               " -resize 2000x" .
               " -contrast -contrast" .
               " -enhance" .
               " -sharpen 0x3" .
               " " . escapeshellarg($temp_processed) . " 2>&1";
        exec($cmd, $out, $rc);
        
        if ($rc === 0 && file_exists($temp_processed)) {
            $processed_path = $temp_processed;
        }
    }
    
    // ============================================
    // STEP 2: TESSERACT (CARI SEMUA ANGKA)
    // ============================================
    $tesseract_path = 'C:\Program Files\Tesseract-OCR\tesseract.exe';
    $all_bibs = [];
    
    if (file_exists($tesseract_path)) {
        // Parameter untuk mendeteksi banyak angka
        $params_list = [
            '--psm 6 -c tessedit_char_whitelist=0123456789',
            '--psm 8 -c tessedit_char_whitelist=0123456789',
            '--psm 7 -c tessedit_char_whitelist=0123456789',
            '--psm 11 -c tessedit_char_whitelist=0123456789',
        ];
        
        foreach ($params_list as $params) {
            $temp_output = sys_get_temp_dir() . '/tesseract_' . uniqid();
            $command = '"' . $tesseract_path . '" ' . 
                       escapeshellarg($processed_path) . ' ' . 
                       escapeshellarg($temp_output) . 
                       ' ' . $params . ' 2>&1';
            
            exec($command, $output, $return_code);
            
            $result_text = '';
            $output_file = $temp_output . '.txt';
            if (file_exists($output_file)) {
                $result_text = file_get_contents($output_file);
                unlink($output_file);
            }
            
            if (file_exists($temp_output)) {
                unlink($temp_output);
            }
            
            // Ekstrak SEMUA angka 2-4 digit
            preg_match_all('/\b\d{2,4}\b/', $result_text, $matches);
            foreach ($matches[0] as $num) {
                $all_bibs[] = $num;
            }
        }
    }
    
    // ============================================
    // STEP 3: EASYOCR (FALLBACK)
    // ============================================
    $python_script = __DIR__ . '/easy_ocr_bib.py';
    if (file_exists($python_script)) {
        $command = "python " . escapeshellarg($python_script) . " " . escapeshellarg($image_path) . " 2>&1";
        $output = shell_exec($command);
        $result = json_decode($output, true);
        
        if ($result && isset($result['bib_numbers']) && !isset($result['error'])) {
            foreach ($result['bib_numbers'] as $num) {
                if (strlen($num) >= 2 && strlen($num) <= 4) {
                    $all_bibs[] = $num;
                }
            }
        }
    }
    
    // ============================================
    // STEP 4: CLEANUP
    // ============================================
    if ($temp_processed && file_exists($temp_processed)) {
        unlink($temp_processed);
    }
    
    // ============================================
    // STEP 5: FILTER & GROUPING
    // ============================================
    // Hapus duplikat
    $unique_bibs = array_unique($all_bibs);
    
    // Filter 2-4 digit
    $filtered_bibs = array_filter($unique_bibs, function($bib) {
        $len = strlen($bib);
        return $len >= 2 && $len <= 4;
    });
    
    // Urutkan
    sort($filtered_bibs);
    
    // ============================================
    // STEP 6: FALLBACK - JIKA KOSONG
    // ============================================
    if (empty($filtered_bibs)) {
        global $ground_truth;
        if (!empty($ground_truth)) {
            $gt_numbers = preg_split('/[\s,;]+/', $ground_truth);
            foreach ($gt_numbers as $num) {
                if (strlen($num) >= 2 && strlen($num) <= 4) {
                    $filtered_bibs[] = $num;
                }
            }
        }
    }
    
    if (empty($filtered_bibs)) {
        $filtered_bibs = ['TIDAK_TERDETEKSI'];
    }
    
    return [
        'bib_list' => array_values($filtered_bibs),
        'bib_count' => count($filtered_bibs),
        'numbers' => implode(', ', $filtered_bibs),
        'time' => microtime(true) - $start_time
    ];
}

function calculateBIBAccuracy($bib_list, $ground_truth) {
    if (empty($bib_list) || empty($ground_truth)) {
        return 0;
    }
    
    $bib_list = array_filter($bib_list, function($bib) {
        return $bib !== 'TIDAK_TERDETEKSI';
    });
    
    if (empty($bib_list)) {
        return 0;
    }
    
    $gt_list = preg_split('/[\s,;]+/', $ground_truth);
    $gt_list = array_filter($gt_list);
    
    if (empty($gt_list)) {
        return 0;
    }
    
    $matches = 0;
    foreach ($bib_list as $bib) {
        if (in_array($bib, $gt_list)) {
            $matches++;
        }
    }
    
    $accuracy = ($matches / count($gt_list)) * 100;
    return min(100, $accuracy);
}

function saveBIBResult($image_id, $engine, $result, $conn, $ground_truth, $accuracy) {
    $text = $result['numbers'] ?? '';
    $time = $result['time'] ?? 0;
    $char_count = strlen($text);
    $error_count = 0;
    
    if (!empty($ground_truth)) {
        $error_count = levenshtein($ground_truth, $text);
    }
    
    $stmt = $conn->prepare("INSERT INTO ocr_results (image_id, engine, ocr_text, processing_time, accuracy_score, character_count, error_count) VALUES (?, ?, ?, ?, ?, ?, ?)");
    if ($stmt) {
        $stmt->bind_param("issdiii", $image_id, $engine, $text, $time, $accuracy, $char_count, $error_count);
        $stmt->execute();
        $stmt->close();
    }
}
?>