<?php
// index.php - OCR Validator (Dengan Ground Truth per Gambar + Export Excel)
require_once 'db_config.php';
$conn = getDBConnection();

$folders = [];
$result = $conn->query("SELECT * FROM test_folders ORDER BY created_at DESC");
if ($result) {
    while ($row = $result->fetch_assoc()) {
        $folders[] = $row;
    }
}

foreach ($folders as &$folder) {
    $stmt = $conn->prepare("SELECT COUNT(*) as count FROM test_images WHERE folder_id = ?");
    if ($stmt) {
        $stmt->bind_param("i", $folder['id']);
        $stmt->execute();
        $countResult = $stmt->get_result();
        $count = $countResult->fetch_assoc();
        $folder['image_count'] = $count['count'] ?? 0;
        $stmt->close();
    }
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR Validator - Tesseract vs EasyOCR</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="assets/css/style.css">
    <style>
        /* ============================================
           STYLE TAMBAHAN
           ============================================ */
        .header-badges {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .header-badges .badge-item {
            padding: 6px 18px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .badge-item.multi { background: #e0e7ff; color: #3730a3; }
        .badge-item.blur { background: #fef3c7; color: #b45309; }
        .badge-item.people { background: #d1fae5; color: #065f46; }
        .badge-item.speed { background: #dbeafe; color: #1a56db; }
        
        /* Tombol Navigasi */
        .nav-buttons {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 15px 0 10px 0;
        }
        .nav-btn {
            padding: 10px 24px;
            border-radius: 12px;
            border: none;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s;
        }
        .nav-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        .nav-btn.primary {
            background: #0a2a3d;
            color: white;
        }
        .nav-btn.primary:hover {
            background: #1a4055;
        }
        .nav-btn.success {
            background: #27ae60;
            color: white;
        }
        .nav-btn.success:hover {
            background: #219a52;
        }
        .nav-btn.warning {
            background: #f39c12;
            color: white;
        }
        .nav-btn.warning:hover {
            background: #d68910;
        }
        .nav-btn.outline {
            background: transparent;
            color: #0a2a3d;
            border: 2px solid #b6cfdd;
        }
        .nav-btn.outline:hover {
            background: #f0f5fa;
            border-color: #2b7a9c;
        }
        
        .mode-selector {
            display: flex;
            gap: 1.5rem;
            justify-content: center;
            margin: 1.5rem 0;
            flex-wrap: wrap;
        }
        .mode-card {
            background: white;
            border-radius: 16px;
            padding: 1.5rem 2rem;
            border: 3px solid #eef4f8;
            transition: all 0.3s;
            flex: 1;
            min-width: 180px;
            max-width: 280px;
            text-align: center;
            text-decoration: none;
            color: #0a2a3d;
        }
        .mode-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.1);
        }
        .mode-card.active {
            border-color: #27ae60;
            background: #f0fdf4;
        }
        .mode-card .icon {
            font-size: 2.5rem;
            display: block;
            margin-bottom: 0.5rem;
        }
        .mode-card .name {
            font-weight: 700;
            font-size: 1.1rem;
        }
        .mode-card .desc {
            color: #6a8a9d;
            font-size: 0.8rem;
            margin-top: 0.3rem;
        }
        .mode-card .badge {
            display: inline-block;
            padding: 3px 14px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 700;
            margin-top: 0.5rem;
        }
        .badge.tesseract { background: #dbeafe; color: #1a56db; }
        .badge.easyocr { background: #fef3c7; color: #b45309; }
        .badge.both { background: #d1fae5; color: #065f46; }
        .badge.rombongan { background: #fce4ec; color: #c62828; }
        
        .mode-info {
            background: #f8fafc;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid #27ae60;
        }
        .mode-info .title {
            font-weight: 600;
            color: #0a2a3d;
        }
        .mode-info .detail {
            color: #4a6a7d;
            font-size: 0.9rem;
        }
        
        .card {
            background: white;
            border-radius: 24px;
            padding: 2rem;
            box-shadow: 0 8px 30px rgba(0,20,30,0.08);
            margin-bottom: 2rem;
        }
        .card h2 {
            color: #0a2a3d;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .card h2 i {
            color: #27ae60;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        .form-group label {
            display: block;
            font-weight: 600;
            color: #1d3d50;
            margin-bottom: 0.5rem;
        }
        .form-control, select {
            width: 100%;
            padding: 0.8rem 1rem;
            border: 2px solid #dce6ef;
            border-radius: 12px;
            font-size: 1rem;
            background: #fafcfe;
        }
        .form-control:focus, select:focus {
            border-color: #27ae60;
            outline: none;
        }
        .helper-text {
            display: block;
            color: #7a9aad;
            font-size: 0.85rem;
            margin-top: 0.3rem;
        }
        
        .flex-group {
            display: flex;
            gap: 1rem;
            align-items: center;
            flex-wrap: wrap;
        }
        .flex-group select {
            flex: 1;
            min-width: 200px;
        }
        
        .btn-primary {
            background: #0a2a3d;
            color: white;
            padding: 0.8rem 2rem;
            border: none;
            border-radius: 14px;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
        }
        .btn-primary:hover {
            background: #1a4055;
            transform: translateY(-2px);
        }
        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: #e8f0f7;
            color: #0a2a3d;
            padding: 0.8rem 2rem;
            border: none;
            border-radius: 14px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.6rem;
        }
        .btn-secondary:hover {
            background: #d4e2ed;
        }
        
        /* ============================================
           FILE LIST + GROUND TRUTH PER GAMBAR
           ============================================ */
        #fileListContainer {
            display: none;
            margin-top: 1rem;
        }
        .file-gt-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background: #f8fafc;
            border-radius: 8px;
            border: 1px solid #eef4f8;
            transition: all 0.2s;
        }
        .file-gt-item:hover {
            background: #f0f5fa;
            border-color: #b6cfdd;
        }
        .file-gt-item .file-gt-info {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex: 1;
            flex-wrap: wrap;
        }
        .file-gt-item .file-gt-icon {
            color: #2b7a9c;
            font-size: 1.2rem;
        }
        .file-gt-item .file-gt-name {
            font-size: 0.85rem;
            color: #1d3d50;
            font-weight: 500;
            min-width: 180px;
            word-break: break-all;
        }
        .file-gt-item .file-gt-input {
            flex: 1;
            min-width: 150px;
            padding: 0.5rem 0.8rem;
            border: 2px solid #dce6ef;
            border-radius: 8px;
            font-size: 0.9rem;
            background: white;
            transition: all 0.2s;
        }
        .file-gt-item .file-gt-input:focus {
            border-color: #27ae60;
            outline: none;
            box-shadow: 0 0 0 4px rgba(39, 174, 96, 0.1);
        }
        .file-gt-item .file-gt-input::placeholder {
            color: #b6cfdd;
        }
        .file-gt-item .file-gt-remove {
            background: #fee;
            color: #c0392b;
            border: none;
            border-radius: 6px;
            padding: 4px 10px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }
        .file-gt-item .file-gt-remove:hover {
            background: #fdd;
        }
        .file-gt-empty {
            text-align: center;
            color: #8aaabe;
            padding: 1rem;
            font-size: 0.9rem;
        }
        
        #imageInput {
            padding: 1rem;
            border: 2px dashed #b6cfdd;
            border-radius: 12px;
            width: 100%;
            cursor: pointer;
            background: #fafcfe;
        }
        #imageInput:hover {
            border-color: #27ae60;
            background: #f0fdf4;
        }
        
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        .preview-grid img {
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-radius: 12px;
            border: 2px solid #e8f0f7;
        }
        
        #progressContainer {
            display: none;
            margin-top: 1rem;
            padding: 1rem;
            background: #f8fafc;
            border-radius: 12px;
            border: 1px solid #eef4f8;
        }
        #progressContainer .progress-track {
            background: #eef4f8;
            border-radius: 8px;
            height: 24px;
            overflow: hidden;
        }
        #progressContainer .progress-track .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #2b7a9c);
            border-radius: 8px;
            transition: width 0.5s;
            width: 0%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
        }
        #progressContainer .progress-text {
            margin-top: 0.5rem;
            color: #4a6a7d;
            font-size: 0.9rem;
            text-align: center;
        }
        
        .folder-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 1.5rem;
        }
        .folder-card {
            background: white;
            padding: 1.5rem;
            border-radius: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.04);
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid transparent;
        }
        .folder-card:hover {
            border-color: #27ae60;
            transform: translateY(-4px);
        }
        .folder-icon {
            font-size: 2.5rem;
            color: #27ae60;
            margin-bottom: 0.5rem;
        }
        .folder-card h3 {
            margin: 0.5rem 0;
            color: #0a2a3d;
        }
        .folder-card p {
            color: #6a8a9d;
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }
        .folder-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .folder-meta small {
            color: #8aaabe;
            font-size: 0.8rem;
        }
        .badge {
            display: inline-block;
            background: #e8f0f7;
            padding: 0.2rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #0a2a3d;
        }
        .folder-actions {
            display: flex;
            gap: 0.5rem;
            justify-content: flex-end;
        }
        .btn-small {
            padding: 0.4rem 1rem;
            font-size: 0.85rem;
            background: #f0f5fa;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            color: #0a2a3d;
        }
        .btn-small:hover {
            background: #e0eaf2;
        }
        .delete-btn {
            background: #fee;
            color: #c0392b;
        }
        .delete-btn:hover {
            background: #fdd;
        }
        
        .empty-state {
            color: #7a9aad;
            text-align: center;
            padding: 3rem;
            font-size: 1.1rem;
            grid-column: 1 / -1;
        }
        .empty-state i {
            display: block;
            margin-bottom: 1rem;
            font-size: 3rem;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            background: white;
            padding: 2.5rem;
            border-radius: 28px;
            max-width: 500px;
            width: 90%;
            position: relative;
        }
        .modal-content .close {
            position: absolute;
            top: 1rem;
            right: 1.5rem;
            font-size: 2rem;
            cursor: pointer;
            color: #8aaabe;
        }
        .modal-content .close:hover {
            color: #0a2a3d;
        }
        .modal-content h2 {
            color: #0a2a3d;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .modal-content h2 i {
            color: #27ae60;
        }
        
        .results-section {
            margin-top: 2rem;
        }
        .results-section h2 {
            color: #0a2a3d;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .info-box {
            background: #e8f4fa;
            padding: 2rem;
            border-radius: 16px;
            text-align: center;
            color: #1d4b61;
        }
        .info-box i {
            font-size: 2rem;
            display: block;
            margin-bottom: 0.5rem;
        }
        
        header {
            text-align: center;
            margin-bottom: 1.5rem;
        }
        header h1 {
            font-size: 2.5rem;
            color: #0a2a3d;
        }
        header h1 i {
            color: #27ae60;
        }
        .subtitle {
            color: #4a6a7d;
            font-size: 1.1rem;
        }
        
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        /* ============================================
           TOMBOL EXPORT
           ============================================ */
        .export-buttons {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            margin: 1rem 0;
            flex-wrap: wrap;
        }
        .btn-excel {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            background: #27ae60;
            color: white;
            cursor: pointer;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s;
        }
        .btn-excel:hover {
            background: #219a52;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(39, 174, 96, 0.3);
        }
        .btn-excel i {
            font-size: 1rem;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            body { padding: 1rem; }
            header h1 { font-size: 2rem; }
            .mode-selector { flex-direction: column; align-items: center; }
            .mode-card { max-width: 100%; width: 100%; }
            .flex-group { flex-direction: column; }
            .flex-group select { width: 100%; min-width: unset; }
            .folder-grid { grid-template-columns: 1fr 1fr; }
            .modal-content { padding: 1.5rem; }
            .nav-buttons { flex-direction: column; align-items: center; }
            .nav-btn { width: 100%; justify-content: center; }
            .file-gt-item .file-gt-info {
                flex-direction: column;
                align-items: stretch;
            }
            .file-gt-item .file-gt-name {
                min-width: unset;
            }
            .file-gt-item .file-gt-input {
                min-width: unset;
            }
            .export-buttons {
                justify-content: center;
            }
        }
        @media (max-width: 480px) {
            .folder-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1><i class="fas fa-check-circle"></i> OCR Validator</h1>
        <p class="subtitle">🔍 <strong>Tesseract</strong> vs <strong>EasyOCR</strong> — Validasi Akurasi &amp; Kecepatan</p>
        
        <!-- NAVIGASI TOMBOL -->
        <div class="nav-buttons">
            <a href="index.php" class="nav-btn primary">
                <i class="fas fa-home"></i> Beranda
            </a>
            <a href="detect_rombongan.php" class="nav-btn warning">
                <i class="fas fa-users"></i> Deteksi Rombongan
            </a>
            <a href="test_tesseract.php" class="nav-btn outline">
                <i class="fas fa-check-circle"></i> Test Tesseract
            </a>
        </div>
        
        <!-- Badges -->
        <div class="header-badges">
            <span class="badge-item multi"><i class="fas fa-hashtag"></i> Multi BIB</span>
            <span class="badge-item blur"><i class="fas fa-eye"></i> Anti Blur</span>
            <span class="badge-item people"><i class="fas fa-users"></i> 1 Foto Banyak Orang</span>
            <span class="badge-item speed"><i class="fas fa-bolt"></i> Cepat &amp; Akurat</span>
        </div>
    </header>

    <!-- Mode Selector -->
    <div class="mode-selector">
        <a href="?mode=tesseract" class="mode-card <?= ($_GET['mode'] ?? '') === 'tesseract' ? 'active' : '' ?>">
            <span class="icon">🔷</span>
            <div class="name">Tesseract</div>
            <div class="desc">Validasi Tesseract OCR</div>
            <span class="badge tesseract">⚡ Cepat</span>
        </a>
        <a href="?mode=easyocr" class="mode-card <?= ($_GET['mode'] ?? '') === 'easyocr' ? 'active' : '' ?>">
            <span class="icon">📖</span>
            <div class="name">EasyOCR</div>
            <div class="desc">Validasi EasyOCR</div>
            <span class="badge easyocr">🎯 Akurat</span>
        </a>
        <a href="?mode=both" class="mode-card <?= ($_GET['mode'] ?? '') === 'both' ? 'active' : '' ?>">
            <span class="icon">⚔️</span>
            <div class="name">Perbandingan</div>
            <div class="desc">Kedua Engine</div>
            <span class="badge both">📊 Lengkap</span>
        </a>
        <a href="detect_rombongan.php" class="mode-card <?= ($_GET['mode'] ?? '') === 'rombongan' ? 'active' : '' ?>">
            <span class="icon">👥</span>
            <div class="name">Rombongan</div>
            <div class="desc">1 Foto Banyak Orang</div>
            <span class="badge rombongan">👥 Multi BIB</span>
        </a>
    </div>

    <?php
    $selected_mode = $_GET['mode'] ?? 'both';
    $mode_config = [
        'tesseract' => ['label' => 'Tesseract Only', 'icon' => '🔷', 'file' => 'upload.php', 'engine' => 'tesseract'],
        'easyocr' => ['label' => 'EasyOCR Only', 'icon' => '📖', 'file' => 'upload.php', 'engine' => 'easyocr'],
        'both' => ['label' => 'Perbandingan', 'icon' => '⚔️', 'file' => 'upload.php', 'engine' => 'both'],
        'rombongan' => ['label' => 'Deteksi Rombongan', 'icon' => '👥', 'file' => 'upload_rombongan.php', 'engine' => 'rombongan']
    ];
    $config = $mode_config[$selected_mode] ?? $mode_config['both'];
    ?>

    <div class="mode-info">
        <div class="title"><?= $config['icon'] ?> Mode: <?= $config['label'] ?></div>
        <div class="detail">
            <?php if ($selected_mode === 'rombongan'): ?>
                <strong style="color:#c62828;">👥 Khusus 1 foto dengan banyak orang (2-10 BIB)</strong>
            <?php else: ?>
                Upload gambar untuk validasi OCR — <strong>Mendukung Multi BIB &amp; Anti Blur</strong>
            <?php endif; ?>
        </div>
    </div>

    <!-- Upload Section -->
    <section class="upload-section">
        <div class="card">
            <h2><i class="fas fa-upload"></i> 
                <?php if ($selected_mode === 'rombongan'): ?>
                    Upload Gambar Rombongan
                <?php else: ?>
                    Upload Gambar
                <?php endif; ?>
            </h2>
            
            <form id="uploadForm" enctype="multipart/form-data" method="POST" action="<?= $config['file'] ?>">
                <input type="hidden" name="engine_mode" value="<?= $config['engine'] ?>">
                
                <div class="form-group">
                    <label for="folderSelect"><i class="fas fa-folder"></i> Pilih Folder:</label>
                    <div class="flex-group">
                        <select name="folder_id" id="folderSelect" required>
                            <option value="">Pilih folder...</option>
                            <?php foreach ($folders as $folder): ?>
                                <option value="<?= $folder['id'] ?>">
                                    <?= htmlspecialchars($folder['folder_name']) ?> (<?= $folder['image_count'] ?? 0 ?> gambar)
                                </option>
                            <?php endforeach; ?>
                        </select>
                        <button type="button" class="btn-secondary" onclick="showNewFolderModal()">
                            <i class="fas fa-plus"></i> Buat Folder
                        </button>
                    </div>
                </div>

                <!-- Pilih Gambar -->
                <div class="form-group">
                    <label for="imageInput"><i class="fas fa-image"></i> Pilih Gambar (bisa banyak):</label>
                    <input type="file" id="imageInput" name="images[]" accept="image/*" multiple required>
                    <div id="imagePreview" class="preview-grid"></div>
                </div>

                <!-- ============================================ -->
                <!-- GROUND TRUTH PER GAMBAR (Muncul setelah upload) -->
                <!-- ============================================ -->
                <div class="form-group" id="fileListContainer">
                    <label><i class="fas fa-list"></i> Ground Truth per Gambar:</label>
                    <div id="fileList">
                        <div class="file-gt-empty">
                            <i class="fas fa-info-circle"></i> Upload gambar terlebih dahulu
                        </div>
                    </div>
                    <small class="helper-text">
                        <i class="fas fa-info-circle"></i> 
                        Isi nomor BIB yang benar untuk setiap gambar
                    </small>
                </div>

                <button type="submit" class="btn-primary" id="submitBtn">
                    <i class="fas fa-play"></i> 
                    <?php if ($selected_mode === 'rombongan'): ?>
                        Deteksi BIB Rombongan
                    <?php else: ?>
                        Mulai Validasi
                    <?php endif; ?>
                </button>

                <!-- Progress Bar -->
                <div id="progressContainer">
                    <div class="progress-track">
                        <div class="progress-fill" id="progressBar" style="width:0%;">0%</div>
                    </div>
                    <div class="progress-text">
                        <i class="fas fa-spinner fa-spin"></i> 
                        <span id="progressText">Memulai proses...</span>
                        <span class="progress-percent" id="progressPercent">0%</span>
                    </div>
                </div>
            </form>
        </div>
    </section>

    <!-- Folders Section -->
    <section class="folders-section">
        <h2><i class="fas fa-folder-open"></i> Folder Pengujian</h2>
        <div class="folder-grid">
            <?php if (count($folders) > 0): ?>
                <?php foreach ($folders as $folder): ?>
                    <div class="folder-card" onclick="loadFolder(<?= $folder['id'] ?>)">
                        <div class="folder-icon"><i class="fas fa-folder"></i></div>
                        <h3><?= htmlspecialchars($folder['folder_name']) ?></h3>
                        <p><?= htmlspecialchars($folder['description'] ?? '') ?></p>
                        <div class="folder-meta">
                            <small><?= date('d M Y', strtotime($folder['created_at'])) ?></small>
                            <span class="badge"><i class="fas fa-image"></i> <?= $folder['image_count'] ?? 0 ?></span>
                        </div>
                        <div class="folder-actions">
                            <button class="btn-small" onclick="event.stopPropagation(); loadFolder(<?= $folder['id'] ?>)">
                                <i class="fas fa-eye"></i> Lihat Hasil
                            </button>
                            <button class="btn-small delete-btn" onclick="event.stopPropagation(); deleteFolder(<?= $folder['id'] ?>)">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                <?php endforeach; ?>
            <?php else: ?>
                <div class="empty-state">
                    <i class="fas fa-folder-open"></i>
                    <p>Belum ada folder. Buat folder baru!</p>
                </div>
            <?php endif; ?>
        </div>
    </section>

    <!-- Results Section -->
    <section class="results-section" id="resultsSection">
        <h2><i class="fas fa-chart-bar"></i> Hasil Validasi</h2>
        
        <!-- Tombol Export -->
        <div class="export-buttons" id="exportButtons" style="display:none;">
            <button onclick="exportExcel()" class="btn-excel">
                <i class="fas fa-file-excel"></i> Export ke Excel
            </button>
        </div>
        
        <div id="resultsContent">
            <div class="info-box">
                <i class="fas fa-info-circle"></i>
                <p>Pilih folder untuk melihat hasil validasi</p>
            </div>
        </div>
    </section>
</div>

<!-- Modal Buat Folder -->
<div id="folderModal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeModal()">&times;</span>
        <h2><i class="fas fa-folder-plus"></i> Buat Folder Baru</h2>
        <form id="folderForm">
            <div class="form-group">
                <label>Nama Folder:</label>
                <input type="text" id="folderName" required placeholder="Contoh: Test OCR" class="form-control">
            </div>
            <div class="form-group">
                <label>Deskripsi (opsional):</label>
                <textarea id="folderDesc" placeholder="Deskripsi folder" class="form-control" rows="3"></textarea>
            </div>
            <button type="submit" class="btn-primary" style="width:100%;">
                <i class="fas fa-check"></i> Buat Folder
            </button>
        </form>
    </div>
</div>

<script>
// ============================================
// SCRIPT.JS - DI DALAM INDEX.PHP
// ============================================

// ============================================
// PREVIEW GAMBAR + GROUND TRUTH PER GAMBAR
// ============================================
document.getElementById('imageInput').addEventListener('change', function(e) {
    const preview = document.getElementById('imagePreview');
    const fileList = document.getElementById('fileList');
    const fileListContainer = document.getElementById('fileListContainer');
    
    preview.innerHTML = '';
    fileList.innerHTML = '';
    
    const files = Array.from(e.target.files);
    
    if (files.length > 0) {
        fileListContainer.style.display = 'block';
    } else {
        fileListContainer.style.display = 'none';
        return;
    }
    
    files.forEach((file, index) => {
        // Preview gambar
        const reader = new FileReader();
        reader.onload = function(ev) {
            const img = document.createElement('img');
            img.src = ev.target.result;
            img.alt = file.name;
            img.title = file.name;
            preview.appendChild(img);
        };
        reader.readAsDataURL(file);
        
        // Input Ground Truth per gambar
        const item = document.createElement('div');
        item.className = 'file-gt-item';
        item.innerHTML = `
            <div class="file-gt-info">
                <span class="file-gt-icon"><i class="fas fa-file-image"></i></span>
                <span class="file-gt-name">${file.name}</span>
                <input type="text" name="ground_truth[]" 
                       class="file-gt-input" 
                       placeholder="Masukkan nomor BIB (contoh: 0074)" 
                       required>
            </div>
            <button type="button" class="file-gt-remove" onclick="removeFileItem(this)" title="Hapus gambar">
                <i class="fas fa-times"></i>
            </button>
        `;
        fileList.appendChild(item);
    });
});

// Fungsi hapus item (opsional)
function removeFileItem(btn) {
    const item = btn.closest('.file-gt-item');
    const name = item.querySelector('.file-gt-name').textContent;
    if (confirm('Hapus gambar ' + name + '?')) {
        item.remove();
        // Update preview juga (perlu logic tambahan jika mau sinkron)
    }
}

// ============================================
// SUBMIT FORM - VALIDASI GROUND TRUTH PER GAMBAR
// ============================================
document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');
    
    // ============================================
    // VALIDASI GROUND TRUTH PER GAMBAR
    // ============================================
    const groundTruthInputs = document.querySelectorAll('input[name="ground_truth[]"]');
    
    // Cek apakah ada gambar yang diupload
    if (groundTruthInputs.length === 0) {
        alert('⚠️ Silakan upload gambar terlebih dahulu!');
        return;
    }
    
    // Cek apakah semua ground truth terisi
    let allFilled = true;
    let emptyIndex = -1;
    groundTruthInputs.forEach((input, index) => {
        if (!input.value.trim()) {
            allFilled = false;
            emptyIndex = index;
        }
    });
    
    if (!allFilled) {
        alert('⚠️ Harap isi Ground Truth untuk semua gambar! (Gambar ke-' + (emptyIndex + 1) + ' belum diisi)');
        return;
    }
    
    // Validasi hanya angka
    let allValid = true;
    groundTruthInputs.forEach((input) => {
        const value = input.value.trim();
        if (!/^[\d\s,;]+$/.test(value)) {
            allValid = false;
            alert('⚠️ Ground Truth hanya boleh berisi angka! (contoh: 0074 atau 1043, 2024)');
        }
    });
    
    if (!allValid) {
        return;
    }
    
    // Tampilkan progress
    progressContainer.style.display = 'block';
    
    function updateProgress(percent, message) {
        progressBar.style.width = percent + '%';
        progressBar.textContent = Math.round(percent) + '%';
        progressText.textContent = message;
        progressPercent.textContent = Math.round(percent) + '%';
    }
    
    updateProgress(0, 'Memulai proses...');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Memproses...';

    const formData = new FormData(this);
    
    try {
        updateProgress(20, 'Mengupload gambar...');
        const response = await fetch('<?= $config['file'] ?>', {
            method: 'POST',
            body: formData
        });
        
        updateProgress(60, 'Validasi OCR...');
        const result = await response.json();
        
        if (result.success) {
            updateProgress(100, 'Selesai!');
            setTimeout(() => {
                let message = '✅ ' + result.message + 
                             '\n📊 ' + result.files_processed + ' gambar diproses' +
                             '\n⏱️ Total waktu: ' + result.total_time.toFixed(2) + ' detik' +
                             '\n📌 Rata-rata: ' + result.avg_time.toFixed(2) + ' detik/gambar';
                
                // Tampilkan ground truth per gambar
                if (result.files && result.files.length > 0) {
                    message += '\n\n📝 Ground Truth:';
                    result.files.forEach((file, i) => {
                        message += '\n  ' + (i+1) + '. ' + file.file + ' → ' + (file.ground_truth || '-');
                    });
                }
                
                alert(message);
                location.reload();
            }, 500);
        } else {
            alert('❌ Error: ' + result.error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-play"></i> Mulai Validasi';
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-play"></i> Mulai Validasi';
    }
});

// ============================================
// BUAT FOLDER
// ============================================
document.getElementById('folderForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const name = document.getElementById('folderName').value.trim();
    const desc = document.getElementById('folderDesc').value.trim();
    
    if (!name) {
        alert('Nama folder harus diisi');
        return;
    }
    
    try {
        const response = await fetch('create_folder.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc })
        });
        const result = await response.json();
        if (result.success) {
            alert('✅ ' + result.message);
            closeModal();
            location.reload();
        } else {
            alert('❌ ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
});

// ============================================
// MODAL FUNCTIONS
// ============================================
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

// ============================================
// LOAD FOLDER RESULTS + ENABLE EXPORT BUTTON
// ============================================
async function loadFolder(folderId) {
    const resultsDiv = document.getElementById('resultsContent');
    const exportButtons = document.getElementById('exportButtons');
    
    resultsDiv.innerHTML = `
        <div class="info-box">
            <i class="fas fa-spinner fa-spin" style="font-size:2rem;"></i>
            <p>Memuat data validasi...</p>
        </div>
    `;
    
    // Sembunyikan tombol export dulu
    exportButtons.style.display = 'none';
    
    // Simpan folder_id aktif
    let hiddenInput = document.getElementById('activeFolderId');
    if (!hiddenInput) {
        hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.id = 'activeFolderId';
        document.body.appendChild(hiddenInput);
    }
    hiddenInput.value = folderId;
    
    try {
        const response = await fetch(`results.php?folder_id=${folderId}`);
        const data = await response.json();
        
        // Tampilkan tombol export jika ada data
        if (data.success && data.results && data.results.length > 0) {
            exportButtons.style.display = 'flex';
        }
        
        if (data.success && data.results && data.results.length > 0) {
            let html = '';
            
            // Statistik
            if (data.stats) {
                html += `<div class="card"><h3><i class="fas fa-chart-line"></i> Statistik Validasi</h3><div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1rem;">`;
                Object.keys(data.stats).forEach(engine => {
                    const stat = data.stats[engine];
                    const label = { tesseract:'Tesseract', easyocr:'EasyOCR' }[engine] || engine;
                    const color = { tesseract:'#2b7a9c', easyocr:'#f39c12' }[engine] || '#666';
                    html += `
                        <div style="border-top:4px solid ${color};background:#f8fafc;padding:1rem;border-radius:12px;">
                            <div style="font-weight:700;font-size:1.1rem;">${label}</div>
                            <div style="font-size:0.9rem;color:#4a6a7d;">⚡ Waktu: <strong>${stat.avg_time.toFixed(3)}s</strong></div>
                            <div style="font-size:0.9rem;color:#4a6a7d;">🎯 Akurasi: <strong>${stat.avg_accuracy.toFixed(1)}%</strong></div>
                            <div style="font-size:0.9rem;color:#4a6a7d;">📝 ${stat.count} gambar</div>
                        </div>
                    `;
                });
                html += `</div></div>`;
            }
            
            // Detail hasil
            html += `<div class="card"><h3><i class="fas fa-images"></i> Detail Validasi (${data.total_images} gambar)</h3>`;
            
            data.results.forEach((item, index) => {
                const hasGroundTruth = item.ground_truth && item.ground_truth.length > 0;
                const imageName = item.image?.image_name || 'gambar';
                const imagePath = item.image?.image_path || '';
                const ocrKeys = Object.keys(item.ocr);
                
                html += `
                    <div style="background:white;border-radius:20px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 4px 16px rgba(0,0,0,0.04);">
                        <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
                            <div>
                                <img src="${imagePath}" style="max-width:150px;max-height:120px;border-radius:12px;object-fit:cover;border:2px solid #e8f0f7;" alt="${imageName}">
                                <div style="margin-top:0.5rem;font-size:0.8rem;color:#6a8a9d;">
                                    <i class="far fa-file-image"></i> ${imageName}
                                </div>
                            </div>
                            <div style="flex:1;min-width:200px;">
                                <div style="display:flex;justify-content:space-between;flex-wrap:wrap;margin-bottom:0.5rem;">
                                    <strong>#${index + 1}</strong>
                                    ${hasGroundTruth ? `<span class="badge" style="background:#d1fae5;color:#065f46;"><i class="fas fa-check-circle" style="color:#4CAF50;"></i> Ground Truth: "${item.ground_truth}"</span>` : '<span class="badge" style="background:#fdebd0;">⚠️ Tidak ada Ground Truth</span>'}
                                </div>
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1rem;">
                                    ${ocrKeys.map(engine => {
                                        const ocr = item.ocr[engine];
                                        const label = { tesseract:'Tesseract', easyocr:'EasyOCR' }[engine] || engine;
                                        const color = { tesseract:'#2b7a9c', easyocr:'#f39c12' }[engine] || '#666';
                                        const accuracy = parseFloat(ocr.accuracy_score || 0);
                                        const isAccurate = accuracy >= 80;
                                        
                                        return `
                                            <div style="border-top:3px solid ${color};background:#f8fafc;padding:1rem;border-radius:12px;">
                                                <div style="font-weight:700;font-size:1rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                                                    <span>${label}</span>
                                                    ${accuracy > 0 ? `<span style="padding:2px 12px;border-radius:12px;font-size:0.75rem;font-weight:600;${isAccurate ? 'background:#d5f5e3;color:#27ae60;' : 'background:#fadbd8;color:#e74c3c;'}">${isAccurate ? '✅ Akurat' : '⚠️ Kurang Akurat'}</span>` : ''}
                                                </div>
                                                <div style="background:white;padding:0.5rem;border-radius:8px;font-size:1.5rem;font-weight:700;text-align:center;color:#0a2a3d;word-wrap:break-word;">
                                                    ${ocr.ocr_text || '(kosong)'}
                                                </div>
                                                <div style="font-size:0.85rem;color:#4a6a7d;">⏱️ ${parseFloat(ocr.processing_time || 0).toFixed(3)}s</div>
                                                <div style="font-size:0.85rem;color:#4a6a7d;">🎯 ${accuracy.toFixed(1)}%</div>
                                                <div style="font-size:0.85rem;color:#4a6a7d;">📊 ${ocr.character_count || 0} karakter | Error: ${ocr.error_count || 0}</div>
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
            
            resultsDiv.innerHTML = html;
            document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
        } else {
            resultsDiv.innerHTML = `
                <div class="info-box">
                    <i class="fas fa-inbox" style="font-size:2rem;"></i>
                    <p>Belum ada hasil validasi di folder ini</p>
                    <p style="font-size:0.9rem; margin-top:0.5rem;">Upload gambar untuk memulai validasi</p>
                </div>
            `;
            exportButtons.style.display = 'none';
        }
    } catch (error) {
        resultsDiv.innerHTML = `
            <div class="info-box" style="background:#fde;border-color:#fcc;">
                <i class="fas fa-exclamation-triangle" style="color:#f44336;font-size:2rem;"></i>
                <p>Error: ${error.message}</p>
            </div>
        `;
        console.error('Load folder error:', error);
        exportButtons.style.display = 'none';
    }
}

// ============================================
// EXPORT EXCEL
// ============================================
function exportExcel() {
    const folderIdInput = document.getElementById('activeFolderId');
    if (!folderIdInput || !folderIdInput.value) {
        alert('Pilih folder terlebih dahulu!');
        return;
    }
    
    const folderId = folderIdInput.value;
    const url = 'export_excel.php?folder_id=' + folderId;
    window.open(url, '_blank');
}

// ============================================
// DELETE FOLDER
// ============================================
async function deleteFolder(folderId) {
    if (!confirm('Yakin ingin menghapus folder ini? Semua data terkait akan hilang!')) {
        return;
    }
    
    try {
        const response = await fetch('delete_folder.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId })
        });
        const result = await response.json();
        if (result.success) {
            alert('✅ Folder berhasil dihapus');
            location.reload();
        } else {
            alert('❌ ' + (result.error || 'Gagal menghapus folder'));
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

console.log('✅ OCR Validator siap digunakan!');
console.log('📌 Fitur: Ground Truth per Gambar | Multi BIB | Anti Blur | 1 Foto Banyak Orang | Export Excel');
</script>
</body>
</html>