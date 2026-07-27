<?php
// detect_bib_chest.php - Deteksi BIB Fokus Area Dada sampai Perut Bawah
error_reporting(E_ALL);
ini_set('display_errors', 1);

require_once 'db_config.php';
$conn = getDBConnection();

// Ambil folder
$folders = [];
$result = $conn->query("SELECT * FROM test_folders ORDER BY created_at DESC");
if ($result) {
    while ($row = $result->fetch_assoc()) {
        $folders[] = $row;
    }
}

// Proses upload dan deteksi
$result_data = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['image'])) {
    $upload_dir = 'uploads/';
    if (!is_dir($upload_dir)) mkdir($upload_dir, 0777, true);
    
    $file_name = 'bib_' . time() . '_' . basename($_FILES['image']['name']);
    $file_path = $upload_dir . $file_name;
    
    if (move_uploaded_file($_FILES['image']['tmp_name'], $file_path)) {
        $result_data = detectBIBOnChest($file_path);
        $result_data['image_path'] = $file_path;
        $result_data['output_image'] = $result_data['output_path'] ?? null;
    }
}

// ============================================
// FUNGSI DETEKSI BIB - FOKUS AREA DADA SAMPAI PERUT
// ============================================

function detectBIBOnChest($image_path) {
    $tesseract_path = 'C:\Program Files\Tesseract-OCR\tesseract.exe';
    $output_path = str_replace('.', '_chest.', $image_path);
    
    if (!file_exists($tesseract_path)) {
        return ['bib_list' => [], 'numbers' => '', 'time' => 0, 'error' => 'Tesseract tidak ditemukan'];
    }
    
    $start_time = microtime(true);
    
    // ============================================
    // STEP 1: BACA GAMBAR
    // ============================================
    $image_info = getimagesize($image_path);
    $mime_type = $image_info['mime'];
    
    switch ($mime_type) {
        case 'image/jpeg':
            $img = imagecreatefromjpeg($image_path);
            break;
        case 'image/png':
            $img = imagecreatefrompng($image_path);
            break;
        case 'image/gif':
            $img = imagecreatefromgif($image_path);
            break;
        default:
            $img = imagecreatefromjpeg($image_path);
    }
    
    $width = imagesx($img);
    $height = imagesy($img);
    
    // ============================================
    // STEP 2: CROP AREA DADA SAMPAI PERUT BAWAH
    // ============================================
    // Area dada: 10% - 70% dari tinggi gambar
    $chest_x = intval($width * 0.05);
    $chest_y = intval($height * 0.08);
    $chest_w = intval($width * 0.90);
    $chest_h = intval($height * 0.65);
    
    // Crop gambar ke area dada
    $chest_img = imagecrop($img, ['x' => $chest_x, 'y' => $chest_y, 'width' => $chest_w, 'height' => $chest_h]);
    
    if ($chest_img === false) {
        return ['bib_list' => [], 'numbers' => '', 'time' => 0, 'error' => 'Gagal crop area dada'];
    }
    
    // Simpan area crop sementara
    $temp_crop = sys_get_temp_dir() . '/chest_crop_' . uniqid() . '.jpg';
    imagejpeg($chest_img, $temp_crop, 90);
    imagedestroy($chest_img);
    
    // ============================================
    // STEP 3: DETEKSI BIB PADA AREA CROP
    // ============================================
    $params = '--psm 6 -c tessedit_char_whitelist=0123456789';
    $temp_output = sys_get_temp_dir() . '/tesseract_' . uniqid();
    $command = '"' . $tesseract_path . '" ' . 
               escapeshellarg($temp_crop) . ' ' . 
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
    
    // Hapus file crop sementara
    if (file_exists($temp_crop)) {
        unlink($temp_crop);
    }
    
    // Ekstrak angka 2-5 digit
    preg_match_all('/\d+/', $result_text, $matches);
    $all_numbers = $matches[0] ?? [];
    $bib_numbers = array_filter($all_numbers, function($num) {
        $len = strlen($num);
        return $len >= 2 && $len <= 5;
    });
    $bib_numbers = array_values($bib_numbers);
    
    // ============================================
    // STEP 4: GAMBAR KOTAK DI GAMBAR ASLI
    // ============================================
    // Warna
    $red = imagecolorallocate($img, 255, 0, 0);
    $dark_red = imagecolorallocate($img, 200, 0, 0);
    $white = imagecolorallocate($img, 255, 255, 255);
    $green = imagecolorallocate($img, 0, 255, 0);
    $yellow = imagecolorallocate($img, 255, 255, 0);
    $black = imagecolorallocate($img, 0, 0, 0);
    $blue = imagecolorallocate($img, 0, 100, 255);
    $transparent_blue = imagecolorallocatealpha($img, 0, 100, 255, 40);
    
    // ============================================
    // STEP 5: GAMBAR AREA DETEKSI
    // ============================================
    // Area deteksi (dada sampai perut bawah)
    $detect_x = $chest_x;
    $detect_y = $chest_y;
    $detect_w = $chest_w;
    $detect_h = $chest_h;
    
    // Kotak area deteksi (transparan biru)
    imagefilledrectangle($img, $detect_x, $detect_y, $detect_x + $detect_w, $detect_y + $detect_h, $transparent_blue);
    imagerectangle($img, $detect_x, $detect_y, $detect_x + $detect_w, $detect_y + $detect_h, $blue);
    
    // Label area deteksi
    $label_area = "AREA DETEKSI BIB (Dada - Perut Bawah)";
    imagefilledrectangle($img, $detect_x, $detect_y - 20, $detect_x + 300, $detect_y, $black);
    imagestring($img, 3, $detect_x + 5, $detect_y - 18, $label_area, $white);
    
    // ============================================
    // STEP 6: GAMBAR BIB
    // ============================================
    $boxes = [];
    
    if (!empty($bib_numbers)) {
        // Tentukan posisi BIB (di tengah area dada)
        $bib_x = intval($width * 0.20);
        $bib_y = intval($height * 0.20);
        $bib_w = intval($width * 0.60);
        $bib_h = intval($height * 0.20);
        
        // Kotak BIB dengan efek glow
        for ($i = 5; $i > 0; $i--) {
            $glow_color = imagecolorallocatealpha($img, 255, 0, 0, 20 * (6 - $i));
            imagerectangle($img, 
                $bib_x - $i, $bib_y - $i, 
                $bib_x + $bib_w + $i, $bib_y + $bib_h + $i, 
                $glow_color
            );
        }
        
        // Kotak utama (tebal)
        imagerectangle($img, $bib_x, $bib_y, $bib_x + $bib_w, $bib_y + $bib_h, $red);
        for ($i = 1; $i <= 4; $i++) {
            imagerectangle($img, $bib_x - $i, $bib_y - $i, $bib_x + $bib_w + $i, $bib_y + $bib_h + $i, $red);
        }
        
        // Label BIB
        $label = 'BIB: ' . implode(', ', $bib_numbers);
        $label_width = imagefontwidth(5) * strlen($label) + 20;
        $label_height = 30;
        $label_x = $bib_x + ($bib_w - $label_width) / 2;
        $label_y = $bib_y - $label_height - 5;
        
        imagefilledrectangle($img, $label_x - 5, $label_y - 5, $label_x + $label_width + 5, $label_y + $label_height + 5, $black);
        imagerectangle($img, $label_x - 5, $label_y - 5, $label_x + $label_width + 5, $label_y + $label_height + 5, $red);
        imagestring($img, 5, $label_x + 10, $label_y + 3, $label, $white);
        
        // Tampilkan nomor BIB
        if (count($bib_numbers) == 1) {
            $bib_text = $bib_numbers[0];
            $text_width = imagefontwidth(5) * strlen($bib_text);
            $text_x = $bib_x + ($bib_w - $text_width) / 2;
            $text_y = $bib_y + ($bib_h - 20) / 2;
            
            imagefilledrectangle($img, $text_x - 10, $text_y - 5, $text_x + $text_width + 10, $text_y + 25, $white);
            imagestring($img, 5, $text_x, $text_y, $bib_text, $red);
            
            $boxes[] = [
                'x' => $bib_x,
                'y' => $bib_y,
                'w' => $bib_w,
                'h' => $bib_h,
                'bib' => $bib_numbers
            ];
            
        } else if (count($bib_numbers) > 1) {
            $per_bib_width = intval($bib_w / count($bib_numbers));
            foreach ($bib_numbers as $idx => $bib) {
                $x_pos = $bib_x + ($idx * $per_bib_width);
                $x_pos_end = $x_pos + $per_bib_width - 5;
                
                imagerectangle($img, $x_pos, $bib_y, $x_pos_end, $bib_y + $bib_h, $red);
                
                $bib_text = $bib;
                $font_size = 4;
                $text_width = imagefontwidth($font_size) * strlen($bib_text);
                $text_x = $x_pos + ($per_bib_width - $text_width) / 2;
                $text_y = $bib_y + ($bib_h - 16) / 2;
                
                imagefilledrectangle($img, $text_x - 5, $text_y - 3, $text_x + $text_width + 5, $text_y + 20, $white);
                imagestring($img, $font_size, $text_x, $text_y, $bib_text, $red);
                
                $boxes[] = [
                    'x' => $x_pos,
                    'y' => $bib_y,
                    'w' => $per_bib_width,
                    'h' => $bib_h,
                    'bib' => [$bib]
                ];
            }
        }
        
        // Informasi
        $info_text = '✅ ' . count($bib_numbers) . ' BIB Terdeteksi di Area Dada';
        imagefilledrectangle($img, 5, $height - 50, 350, $height - 5, $black);
        imagestring($img, 3, 10, $height - 45, $info_text, $green);
        
        $time_text = '⏱️ ' . number_format(microtime(true) - $start_time, 3) . 's';
        imagestring($img, 3, 10, $height - 30, $time_text, $white);
        
        $area_text = '📍 Area: Dada - Perut Bawah (8-73% dari tinggi)';
        imagestring($img, 2, 10, $height - 15, $area_text, $blue);
        
    } else {
        // Tidak ada BIB
        imagefilledrectangle($img, intval($width/2) - 180, intval($height/2) - 30, intval($width/2) + 180, intval($height/2) + 30, $black);
        imagerectangle($img, intval($width/2) - 180, intval($height/2) - 30, intval($width/2) + 180, intval($height/2) + 30, $red);
        imagestring($img, 5, intval($width/2) - 120, intval($height/2) - 10, '❌ TIDAK ADA BIB DI AREA DADA', $red);
        imagestring($img, 3, intval($width/2) - 100, intval($height/2) + 25, 'Coba gambar yang lebih jelas', $white);
    }
    
    // ============================================
    // STEP 7: SIMPAN GAMBAR
    // ============================================
    switch ($mime_type) {
        case 'image/jpeg':
            imagejpeg($img, $output_path, 95);
            break;
        case 'image/png':
            imagepng($img, $output_path);
            break;
        case 'image/gif':
            imagegif($img, $output_path);
            break;
        default:
            imagejpeg($img, $output_path, 95);
    }
    
    imagedestroy($img);
    
    return [
        'bib_list' => $bib_numbers,
        'bib_count' => count($bib_numbers),
        'numbers' => implode(', ', $bib_numbers),
        'text' => $result_text,
        'time' => microtime(true) - $start_time,
        'output_path' => $output_path,
        'boxes' => $boxes
    ];
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deteksi BIB - Area Dada</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #f5f7fa; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 24px; padding: 2rem; margin-bottom: 1.5rem; box-shadow: 0 8px 30px rgba(0,20,30,0.08); }
        h1 { color: #0a2a3d; margin-bottom: 0.5rem; }
        h1 i { color: #e74c3c; }
        .subtitle { color: #4a6a7d; margin-bottom: 1.5rem; }
        .form-group { margin-bottom: 1.5rem; }
        .form-group label { display: block; font-weight: 600; color: #1d3d50; margin-bottom: 0.5rem; }
        input[type="file"] { padding: 1rem; border: 2px dashed #b6cfdd; border-radius: 12px; width: 100%; cursor: pointer; background: #fafcfe; }
        input[type="file"]:hover { border-color: #e74c3c; background: #fef4f4; }
        .btn-primary { background: #0a2a3d; color: white; padding: 0.8rem 2rem; border: none; border-radius: 14px; font-weight: 600; font-size: 1rem; cursor: pointer; transition: all 0.2s; width: 100%; display: flex; align-items: center; justify-content: center; gap: 0.6rem; }
        .btn-primary:hover { background: #1a4055; transform: translateY(-2px); }
        .result-box { background: #2d2d2d; color: #f8f8f8; padding: 2rem; border-radius: 12px; margin-top: 1rem; }
        .result-box .bib-number { font-size: 3rem; font-weight: 700; color: #4CAF50; }
        .result-box .bib-number.not-found { color: #e74c3c; }
        .result-box .time { color: #8aaabe; margin-top: 0.5rem; }
        .image-container { text-align: center; margin: 1rem 0; }
        .image-container img { max-width: 100%; max-height: 600px; border-radius: 12px; border: 2px solid #eef4f8; box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
        .legend { display: flex; gap: 1.5rem; justify-content: center; flex-wrap: wrap; margin-top: 1rem; }
        .legend-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; color: #4a6a7d; }
        .legend-item .box { display: inline-block; width: 20px; height: 15px; border: 2px solid; border-radius: 3px; }
        .legend-item .box.detect { border-color: #0064ff; background: rgba(0,100,255,0.2); }
        .legend-item .box.bib { border-color: #e74c3c; background: rgba(231,76,60,0.2); }
        .back-link { color: #2b7a9c; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
        .back-link:hover { text-decoration: underline; }
        .badge { display: inline-block; padding: 4px 16px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
        .badge.success { background: #d5f5e3; color: #27ae60; }
        .badge.fail { background: #fadbd8; color: #e74c3c; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; padding: 2.5rem; border-radius: 28px; max-width: 500px; width: 90%; position: relative; }
        .modal-content .close { position: absolute; top: 1rem; right: 1.5rem; font-size: 2rem; cursor: pointer; color: #8aaabe; }
        @media (max-width: 768px) { body { padding: 1rem; } .result-box .bib-number { font-size: 2rem; } .legend { flex-direction: column; align-items: center; } }
    </style>
</head>
<body>
<div class="container">
    <a href="index.php" class="back-link">← Kembali ke Beranda</a>
    
    <div class="card">
        <h1>
            <i class="fas fa-chevron-circle-down" style="color:#0064ff;"></i>
            Deteksi BIB Area Dada
            <i class="fas fa-square" style="color:#e74c3c;"></i>
        </h1>
        <p class="subtitle">
            <span style="background:#0064ff20; padding:4px 12px; border-radius:12px; border:1px solid #0064ff;">
                🟦 Area Dada - Perut Bawah (8-73%)
            </span>
            →
            <span style="background:#e74c3c20; padding:4px 12px; border-radius:12px; border:1px solid #e74c3c;">
                🟥 BIB Terdeteksi
            </span>
        </p>
        
        <form method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label>Pilih Gambar:</label>
                <input type="file" name="image" accept="image/*" required>
            </div>
            
            <button type="submit" class="btn-primary">
                <i class="fas fa-search"></i> Deteksi BIB
            </button>
        </form>
    </div>

    <?php if ($result_data): ?>
    <div class="card">
        <h2>📊 Hasil Deteksi</h2>
        
        <?php if (isset($result_data['output_path']) && file_exists($result_data['output_path'])): ?>
        <div class="image-container">
            <img src="<?= $result_data['output_path'] ?>" alt="Hasil Deteksi BIB">
            
            <div class="legend">
                <span class="legend-item">
                    <span class="box detect"></span>
                    Area Deteksi (Dada - Perut Bawah)
                </span>
                <span class="legend-item">
                    <span class="box bib"></span>
                    BIB Terdeteksi
                </span>
                <span class="legend-item">
                    <span style="color:#0064ff;">📍</span>
                    Nomor di area dada dibaca sebagai BIB
                </span>
            </div>
        </div>
        <?php endif; ?>
        
        <div class="result-box">
            <div class="bib-number <?= !empty($result_data['bib_list']) ? '' : 'not-found' ?>">
                <?= !empty($result_data['bib_list']) ? implode(', ', $result_data['bib_list']) : 'TIDAK TERDETEKSI' ?>
            </div>
            <div class="time">📊 Jumlah BIB: <strong><?= $result_data['bib_count'] ?? 0 ?></strong></div>
            <div class="time">⏱️ Waktu Deteksi: <strong><?= number_format($result_data['time'] ?? 0, 3) ?></strong> detik</div>
            <?php if (!empty($result_data['bib_list'])): ?>
                <div class="time" style="margin-top:0.5rem;">
                    <span class="badge success">✅ Terdeteksi</span>
                    <span style="color:#8aaabe; margin-left:1rem;">Jumlah: <?= $result_data['bib_count'] ?> BIB</span>
                </div>
            <?php else: ?>
                <div class="time" style="margin-top:0.5rem;">
                    <span class="badge fail">❌ Tidak Terdeteksi</span>
                </div>
            <?php endif; ?>
        </div>
        
        <?php if (!empty($result_data['bib_list'])): ?>
        <div style="margin-top:1rem; padding:1rem; background:#f8fafc; border-radius:12px;">
            <h4>📝 Detail BIB Terdeteksi:</h4>
            <ul style="margin-left:1.5rem; margin-top:0.5rem;">
                <?php foreach ($result_data['bib_list'] as $index => $bib): ?>
                    <li><strong>BIB <?= $index + 1 ?>:</strong> <?= $bib ?></li>
                <?php endforeach; ?>
            </ul>
        </div>
        <?php endif; ?>
    </div>
    <?php endif; ?>
</div>

<!-- Modal -->
<div id="folderModal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeModal()">&times;</span>
        <h2><i class="fas fa-folder-plus"></i> Buat Folder Baru</h2>
        <form id="folderForm">
            <div class="form-group">
                <label>Nama Folder:</label>
                <input type="text" id="folderName" required placeholder="Contoh: Test OCR" style="width:100%;padding:0.8rem 1rem;border:2px solid #dce6ef;border-radius:12px;font-size:1rem;">
            </div>
            <div class="form-group">
                <label>Deskripsi (opsional):</label>
                <textarea id="folderDesc" placeholder="Deskripsi folder" style="width:100%;padding:0.8rem 1rem;border:2px solid #dce6ef;border-radius:12px;font-size:1rem;min-height:80px;" rows="3"></textarea>
            </div>
            <button type="submit" class="btn-primary" style="width:100%;">
                <i class="fas fa-check"></i> Buat Folder
            </button>
        </form>
    </div>
</div>

<script>
document.getElementById('folderForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const name = document.getElementById('folderName').value.trim();
    if (!name) { alert('Nama folder harus diisi'); return; }
    
    try {
        const response = await fetch('create_folder.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: document.getElementById('folderDesc').value.trim() })
        });
        const result = await response.json();
        if (result.success) { alert('✅ ' + result.message); closeModal(); location.reload(); }
        else { alert('❌ ' + result.error); }
    } catch (error) { alert('❌ Error: ' + error.message); }
});

function showNewFolderModal() {
    document.getElementById('folderModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('folderModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('folderModal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
};
</script>
</body>
</html>