<?php
// export_excel.php - Export hasil ke Excel
require_once 'db_config.php';

// Cek folder_id
$folder_id = isset($_GET['folder_id']) ? intval($_GET['folder_id']) : 0;

if ($folder_id <= 0) {
    die('Folder ID tidak valid');
}

$conn = getDBConnection();

// Ambil data
$images = [];
$stmt = $conn->prepare("SELECT * FROM test_images WHERE folder_id = ? ORDER BY upload_date DESC");
$stmt->bind_param("i", $folder_id);
$stmt->execute();
$result = $stmt->get_result();
while ($row = $result->fetch_assoc()) {
    $images[] = $row;
}
$stmt->close();

// Ambil nama folder
$folder_name = '';
$stmt = $conn->prepare("SELECT folder_name FROM test_folders WHERE id = ?");
$stmt->bind_param("i", $folder_id);
$stmt->execute();
$result = $stmt->get_result();
if ($row = $result->fetch_assoc()) {
    $folder_name = $row['folder_name'];
}
$stmt->close();

// Header Excel
header('Content-Type: application/vnd.ms-excel');
header('Content-Disposition: attachment; filename="statistik_ocr_' . $folder_name . '_' . date('Y-m-d') . '.xls"');

echo '<html>';
echo '<head><meta charset="UTF-8"></head>';
echo '<body>';
echo '<h2>STATISTIK OCR VALIDATOR</h2>';
echo '<p>Folder: ' . $folder_name . '</p>';
echo '<p>Tanggal Export: ' . date('d-m-Y H:i:s') . '</p>';
echo '<hr>';

// ============================================
// TABEL REKAP PER ENGINE
// ============================================
echo '<h3>REKAP PER ENGINE</h3>';
echo '<table border="1" cellpadding="5">';
echo '<tr>';
echo '<th>Engine</th>';
echo '<th>Jumlah Gambar</th>';
echo '<th>Rata-rata Waktu (s)</th>';
echo '<th>Rata-rata Akurasi (%)</th>';
echo '<th>Min Akurasi (%)</th>';
echo '<th>Max Akurasi (%)</th>';
echo '</tr>';

$engines = ['tesseract', 'easyocr'];
$engine_labels = ['tesseract' => 'Tesseract', 'easyocr' => 'EasyOCR'];

foreach ($engines as $engine) {
    $times = [];
    $accuracies = [];
    $count = 0;
    
    foreach ($images as $img) {
        $stmt = $conn->prepare("SELECT processing_time, accuracy_score FROM ocr_results WHERE image_id = ? AND engine = ?");
        $stmt->bind_param("is", $img['id'], $engine);
        $stmt->execute();
        $result = $stmt->get_result();
        if ($row = $result->fetch_assoc()) {
            $times[] = floatval($row['processing_time']);
            $accuracies[] = floatval($row['accuracy_score']);
            $count++;
        }
        $stmt->close();
    }
    
    if ($count > 0) {
        echo '<tr>';
        echo '<td><strong>' . $engine_labels[$engine] . '</strong></td>';
        echo '<td>' . $count . '</td>';
        echo '<td>' . number_format(array_sum($times) / $count, 3) . '</td>';
        echo '<td>' . number_format(array_sum($accuracies) / $count, 1) . '%</td>';
        echo '<td>' . number_format(min($accuracies), 1) . '%</td>';
        echo '<td>' . number_format(max($accuracies), 1) . '%</td>';
        echo '</tr>';
    }
}

echo '</table>';
echo '<br><br>';

// ============================================
// TABEL DETAIL PER GAMBAR
// ============================================
echo '<h3>DETAIL PER GAMBAR</h3>';
echo '<table border="1" cellpadding="5">';
echo '<tr>';
echo '<th>No</th>';
echo '<th>Nama File</th>';
echo '<th>Ground Truth</th>';
echo '<th>Tesseract</th>';
echo '<th>Akurasi Tesseract (%)</th>';
echo '<th>Waktu Tesseract (s)</th>';
echo '<th>EasyOCR</th>';
echo '<th>Akurasi EasyOCR (%)</th>';
echo '<th>Waktu EasyOCR (s)</th>';
echo '</tr>';

$no = 1;
foreach ($images as $img) {
    // Ground truth
    $stmt = $conn->prepare("SELECT true_text FROM ground_truth WHERE image_id = ?");
    $stmt->bind_param("i", $img['id']);
    $stmt->execute();
    $gt_result = $stmt->get_result();
    $ground_truth = $gt_result->fetch_assoc();
    $stmt->close();
    
    $gt_text = $ground_truth['true_text'] ?? '-';
    
    // Tesseract
    $tess_text = '-';
    $tess_acc = '-';
    $tess_time = '-';
    $stmt = $conn->prepare("SELECT ocr_text, accuracy_score, processing_time FROM ocr_results WHERE image_id = ? AND engine = 'tesseract'");
    $stmt->bind_param("i", $img['id']);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($row = $result->fetch_assoc()) {
        $tess_text = $row['ocr_text'] ?: '-';
        $tess_acc = number_format($row['accuracy_score'], 1);
        $tess_time = number_format($row['processing_time'], 3);
    }
    $stmt->close();
    
    // EasyOCR
    $easy_text = '-';
    $easy_acc = '-';
    $easy_time = '-';
    $stmt = $conn->prepare("SELECT ocr_text, accuracy_score, processing_time FROM ocr_results WHERE image_id = ? AND engine = 'easyocr'");
    $stmt->bind_param("i", $img['id']);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($row = $result->fetch_assoc()) {
        $easy_text = $row['ocr_text'] ?: '-';
        $easy_acc = number_format($row['accuracy_score'], 1);
        $easy_time = number_format($row['processing_time'], 3);
    }
    $stmt->close();
    
    echo '<tr>';
    echo '<td>' . $no++ . '</td>';
    echo '<td>' . htmlspecialchars($img['image_name']) . '</td>';
    echo '<td><strong>' . htmlspecialchars($gt_text) . '</strong></td>';
    echo '<td>' . htmlspecialchars($tess_text) . '</td>';
    echo '<td>' . $tess_acc . '%</td>';
    echo '<td>' . $tess_time . '</td>';
    echo '<td>' . htmlspecialchars($easy_text) . '</td>';
    echo '<td>' . $easy_acc . '%</td>';
    echo '<td>' . $easy_time . '</td>';
    echo '</tr>';
}

echo '</table>';
echo '<br>';
echo '<p><em>Dicetak pada: ' . date('d-m-Y H:i:s') . '</em></p>';

echo '</body></html>';
?>