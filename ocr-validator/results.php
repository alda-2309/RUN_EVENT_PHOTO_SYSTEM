<?php
// results.php - Hasil Validasi dengan Statistik per Gambar
require_once 'db_config.php';
header('Content-Type: application/json');

$folder_id = isset($_GET['folder_id']) ? intval($_GET['folder_id']) : 0;

if ($folder_id <= 0) {
    echo json_encode(['success' => false, 'error' => 'Folder ID tidak valid']);
    exit;
}

$conn = getDBConnection();

// Ambil data folder
$folder_name = '';
$stmt = $conn->prepare("SELECT folder_name FROM test_folders WHERE id = ?");
$stmt->bind_param("i", $folder_id);
$stmt->execute();
$result = $stmt->get_result();
if ($row = $result->fetch_assoc()) {
    $folder_name = $row['folder_name'];
}
$stmt->close();

// Ambil semua gambar dalam folder
$images = [];
$stmt = $conn->prepare("SELECT * FROM test_images WHERE folder_id = ? ORDER BY upload_date DESC");
$stmt->bind_param("i", $folder_id);
$stmt->execute();
$result = $stmt->get_result();
while ($row = $result->fetch_assoc()) {
    $images[] = $row;
}
$stmt->close();

$results = [];
$per_image_stats = [];

foreach ($images as $img) {
    // Ground truth
    $stmt = $conn->prepare("SELECT true_text FROM ground_truth WHERE image_id = ?");
    $stmt->bind_param("i", $img['id']);
    $stmt->execute();
    $gt_result = $stmt->get_result();
    $ground_truth = $gt_result->fetch_assoc();
    $stmt->close();
    
    // Hasil OCR
    $stmt = $conn->prepare("SELECT * FROM ocr_results WHERE image_id = ?");
    $stmt->bind_param("i", $img['id']);
    $stmt->execute();
    $result = $stmt->get_result();
    $ocr_data = [];
    while ($row = $result->fetch_assoc()) {
        $ocr_data[$row['engine']] = $row;
    }
    $stmt->close();
    
    // Simpan data per gambar untuk export
    $image_stat = [
        'image_name' => $img['image_name'],
        'image_path' => $img['image_path'],
        'ground_truth' => $ground_truth['true_text'] ?? '',
        'tesseract' => null,
        'easyocr' => null
    ];
    
    if (isset($ocr_data['tesseract'])) {
        $image_stat['tesseract'] = [
            'ocr_text' => $ocr_data['tesseract']['ocr_text'] ?? '',
            'processing_time' => floatval($ocr_data['tesseract']['processing_time'] ?? 0),
            'accuracy_score' => floatval($ocr_data['tesseract']['accuracy_score'] ?? 0),
            'character_count' => intval($ocr_data['tesseract']['character_count'] ?? 0),
            'error_count' => intval($ocr_data['tesseract']['error_count'] ?? 0)
        ];
    }
    
    if (isset($ocr_data['easyocr'])) {
        $image_stat['easyocr'] = [
            'ocr_text' => $ocr_data['easyocr']['ocr_text'] ?? '',
            'processing_time' => floatval($ocr_data['easyocr']['processing_time'] ?? 0),
            'accuracy_score' => floatval($ocr_data['easyocr']['accuracy_score'] ?? 0),
            'character_count' => intval($ocr_data['easyocr']['character_count'] ?? 0),
            'error_count' => intval($ocr_data['easyocr']['error_count'] ?? 0)
        ];
    }
    
    $per_image_stats[] = $image_stat;
    
    $results[] = [
        'image' => $img,
        'ground_truth' => $ground_truth['true_text'] ?? '',
        'ocr' => $ocr_data
    ];
}

// Statistik per engine
$stats = [];
$engines = ['tesseract', 'easyocr'];
foreach ($engines as $engine) {
    $times = [];
    $accuracies = [];
    $error_counts = [];
    $char_counts = [];
    
    foreach ($results as $item) {
        if (isset($item['ocr'][$engine])) {
            $times[] = floatval($item['ocr'][$engine]['processing_time']);
            $accuracies[] = floatval($item['ocr'][$engine]['accuracy_score']);
            $error_counts[] = intval($item['ocr'][$engine]['error_count']);
            $char_counts[] = intval($item['ocr'][$engine]['character_count']);
        }
    }
    
    if (count($times) > 0) {
        $stats[$engine] = [
            'avg_time' => array_sum($times) / count($times),
            'avg_accuracy' => array_sum($accuracies) / count($accuracies),
            'count' => count($times),
            'min_accuracy' => min($accuracies),
            'max_accuracy' => max($accuracies),
            'min_time' => min($times),
            'max_time' => max($times),
            'total_error' => array_sum($error_counts),
            'total_char' => array_sum($char_counts)
        ];
    }
}

// Kirim response
echo json_encode([
    'success' => true,
    'results' => $results,
    'stats' => $stats,
    'total_images' => count($images),
    'folder_name' => $folder_name,
    'per_image_stats' => $per_image_stats  // Data detail per gambar untuk export
]);
?>