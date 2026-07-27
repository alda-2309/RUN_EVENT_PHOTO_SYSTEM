<?php
// upload.php - FIXED (Ground Truth per Gambar)
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
$engine_mode = isset($_POST['engine_mode']) ? $_POST['engine_mode'] : 'both';

// ============================================
// GROUND TRUTH PER GAMBAR (ARRAY)
// ============================================
$ground_truths = isset($_POST['ground_truth']) ? $_POST['ground_truth'] : [];

if ($folder_id <= 0) {
    sendError('Folder ID tidak valid');
}

// ============================================
// VALIDASI GROUND TRUTH PER GAMBAR
// ============================================
// Cek apakah ada file yang diupload
if (!isset($_FILES['images']) || empty($_FILES['images']['name'][0])) {
    sendError('Tidak ada gambar yang diupload');
}

// Cek apakah jumlah ground truth sesuai dengan jumlah gambar
$file_count = count($_FILES['images']['name']);
if (count($ground_truths) !== $file_count) {
    sendError('Jumlah Ground Truth tidak sesuai dengan jumlah gambar');
}

// Cek apakah semua ground truth terisi
foreach ($ground_truths as $gt) {
    if (empty(trim($gt))) {
        sendError('Semua Ground Truth harus diisi');
    }
}

$upload_dir = 'uploads/';
if (!is_dir($upload_dir)) {
    if (!mkdir($upload_dir, 0777, true)) {
        sendError('Tidak bisa membuat folder uploads');
    }
}

$conn = getDBConnection();
$uploaded_files = [];

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
    
    // ============================================
    // AMBIL GROUND TRUTH UNTUK GAMBAR INI
    // ============================================
    $ground_truth = isset($ground_truths[$i]) ? trim($ground_truths[$i]) : '';
    
    // ============================================
    // SIMPAN KE DATABASE
    // ============================================
    $stmt = $conn->prepare("INSERT INTO test_images (folder_id, image_name, image_path, engine) VALUES (?, ?, ?, ?)");
    if ($stmt) {
        $stmt->bind_param("isss", $folder_id, $file_name, $file_path, $engine_mode);
        $stmt->execute();
        $image_id = $conn->insert_id;
        $stmt->close();
    }
    
    // Simpan ground truth per gambar
    $stmt = $conn->prepare("INSERT INTO ground_truth (image_id, true_text) VALUES (?, ?) ON DUPLICATE KEY UPDATE true_text = ?");
    if ($stmt) {
        $stmt->bind_param("iss", $image_id, $ground_truth, $ground_truth);
        $stmt->execute();
        $stmt->close();
    }
    
    // ============================================
    // PROSES OCR
    // ============================================
    $result = [];
    
    if ($engine_mode === 'tesseract' || $engine_mode === 'both') {
        $result['tesseract'] = runTesseractBIB($file_path);
        $acc = calculateBIBAccuracy($result['tesseract']['bib_list'], $ground_truth);
        saveBIBResult($image_id, 'tesseract', $result['tesseract'], $conn, $ground_truth, $acc);
        $result['tesseract']['accuracy'] = $acc;
    }
    
    if ($engine_mode === 'easyocr' || $engine_mode === 'both') {
        $result['easyocr'] = runEasyOCRBIB($file_path);
        $acc = calculateBIBAccuracy($result['easyocr']['bib_list'], $ground_truth);
        saveBIBResult($image_id, 'easyocr', $result['easyocr'], $conn, $ground_truth, $acc);
        $result['easyocr']['accuracy'] = $acc;
    }
    
    $uploaded_files[] = [
        'file' => $file_name,
        'image_id' => $image_id,
        'ground_truth' => $ground_truth,
        'result' => $result,
        'time' => $result['time'] ?? 0
    ];
}

$total_time = microtime(true) - $total_start;

sendJSON([
    'success' => true,
    'message' => 'Upload dan validasi BIB berhasil',
    'files_processed' => count($uploaded_files),
    'total_time' => $total_time,
    'avg_time' => $total_time / max(1, count($uploaded_files)),
    'files' => $uploaded_files
]);

// ============================================
// FUNGSI TESSERACT BIB
// ============================================

function runTesseractBIB($image_path) {
    $tesseract_path = 'C:\Program Files\Tesseract-OCR\tesseract.exe';
    $start_time = microtime(true);
    
    if (!file_exists($tesseract_path)) {
        return ['bib_list' => ['TESSERACT_TIDAK_DITEMUKAN'], 'numbers' => 'TESSERACT_TIDAK_DITEMUKAN', 'time' => 0];
    }
    
    // Preprocessing ringan
    $processed_path = $image_path;
    $temp_processed = null;
    
    $convert_check = shell_exec('convert --version 2>&1');
    if (strpos($convert_check, 'ImageMagick') !== false) {
        $temp_processed = sys_get_temp_dir() . '/tess_bib_' . uniqid() . '.png';
        $cmd = "convert " . escapeshellarg($image_path) . 
               " -resize 1500x" .
               " -contrast -contrast" .
               " -enhance" .
               " -sharpen 0x2" .
               " " . escapeshellarg($temp_processed) . " 2>&1";
        exec($cmd, $out, $rc);
        
        if ($rc === 0 && file_exists($temp_processed)) {
            $processed_path = $temp_processed;
        }
    }
    
    // Multiple parameter
    $param_combinations = [
        ['name' => 'PSM8_White', 'params' => '--psm 8 -c tessedit_char_whitelist=0123456789 -c classify_enable_learning=0'],
        ['name' => 'PSM7_White', 'params' => '--psm 7 -c tessedit_char_whitelist=0123456789'],
        ['name' => 'PSM6_White', 'params' => '--psm 6 -c tessedit_char_whitelist=0123456789'],
    ];
    
    $all_bibs = [];
    $all_texts = [];
    $best_result = '';
    
    foreach ($param_combinations as $param) {
        $temp_output = sys_get_temp_dir() . '/tesseract_' . uniqid();
        $command = '"' . $tesseract_path . '" ' . 
                   escapeshellarg($processed_path) . ' ' . 
                   escapeshellarg($temp_output) . 
                   ' ' . $param['params'] . ' 2>&1';
        
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
        
        $result_text = trim($result_text);
        if (!empty($result_text)) {
            $all_texts[] = $result_text;
            preg_match_all('/\b\d{2,4}\b/', $result_text, $matches);
            foreach ($matches[0] as $num) {
                $all_bibs[] = $num;
            }
            if (strlen($result_text) > strlen($best_result)) {
                $best_result = $result_text;
            }
        }
    }
    
    if ($temp_processed && file_exists($temp_processed)) {
        unlink($temp_processed);
    }
    
    $unique_bibs = array_unique($all_bibs);
    $filtered_bibs = array_filter($unique_bibs, function($bib) {
        $len = strlen($bib);
        return $len >= 2 && $len <= 4;
    });
    sort($filtered_bibs);
    
    if (empty($filtered_bibs) && !empty($best_result)) {
        preg_match_all('/\d+/', $best_result, $all_numbers);
        if (!empty($all_numbers[0])) {
            foreach ($all_numbers[0] as $num) {
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
        'text' => implode(' ', $all_texts),
        'time' => microtime(true) - $start_time
    ];
}

// ============================================
// FUNGSI EASYOCR BIB
// ============================================

function runEasyOCRBIB($image_path) {
    $python_script = __DIR__ . '/easy_ocr_bib.py';
    $start_time = microtime(true);
    
    if (!file_exists($python_script)) {
        return ['bib_list' => ['EASYOCR_TIDAK_TERSEDIA'], 'numbers' => 'EASYOCR_TIDAK_TERSEDIA', 'time' => 0];
    }
    
    $command = "python " . escapeshellarg($python_script) . " " . escapeshellarg($image_path) . " 2>&1";
    $output = shell_exec($command);
    $time = microtime(true) - $start_time;
    
    $result = json_decode($output, true);
    
    if ($result && isset($result['bib_numbers']) && !isset($result['error'])) {
        $bib_list = $result['bib_numbers'] ?? [];
        if (empty($bib_list)) {
            $bib_list = ['TIDAK_TERDETEKSI'];
        }
        $numbers_string = implode(', ', $bib_list);
        
        return [
            'bib_list' => $bib_list,
            'bib_count' => count($bib_list),
            'numbers' => $numbers_string,
            'text' => $result['text'] ?? '',
            'time' => $time,
            'confidence' => $result['confidence'] ?? 0
        ];
    }
    
    return [
        'bib_list' => ['EASYOCR_GAGAL'],
        'numbers' => 'EASYOCR_GAGAL',
        'time' => $time
    ];
}

// ============================================
// FUNGSI BANTUAN
// ============================================

function calculateBIBAccuracy($bib_list, $ground_truth) {
    if (empty($bib_list) || empty($ground_truth)) {
        return 0;
    }
    
    $bib_list = array_filter($bib_list, function($bib) {
        return $bib !== 'TIDAK_TERDETEKSI' && 
               $bib !== 'EASYOCR_GAGAL' && 
               $bib !== 'EASYOCR_TIDAK_TERSEDIA' && 
               $bib !== 'TESSERACT_TIDAK_DITEMUKAN';
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