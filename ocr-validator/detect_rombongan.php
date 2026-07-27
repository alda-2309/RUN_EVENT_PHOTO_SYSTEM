<?php
// detect_rombongan.php - Halaman Deteksi Rombongan
require_once 'db_config.php';
$conn = getDBConnection();

$folders = [];
$result = $conn->query("SELECT * FROM test_folders ORDER BY created_at DESC");
if ($result) {
    while ($row = $result->fetch_assoc()) {
        $folders[] = $row;
    }
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Deteksi BIB Rombongan</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Segoe UI',sans-serif; background:#f5f7fa; padding:2rem; }
        .container { max-width:1000px; margin:0 auto; }
        .card { background:white; border-radius:24px; padding:2rem; margin-bottom:1.5rem; box-shadow:0 8px 30px rgba(0,20,30,0.08); }
        h1 { color:#0a2a3d; margin-bottom:0.5rem; }
        h1 i { color:#f39c12; }
        .subtitle { color:#4a6a7d; margin-bottom:1.5rem; }
        .badge-group {
            display:flex; gap:1rem; flex-wrap:wrap; margin-bottom:1rem;
        }
        .badge-group .badge {
            padding:4px 16px; border-radius:20px; font-size:0.8rem; font-weight:600;
        }
        .badge.blue { background:#dbeafe; color:#1a56db; }
        .badge.green { background:#d1fae5; color:#065f46; }
        .badge.orange { background:#fef3c7; color:#b45309; }
        .badge.red { background:#fee; color:#c0392b; }
        .form-group { margin-bottom:1.5rem; }
        .form-group label { display:block; font-weight:600; color:#1d3d50; margin-bottom:0.5rem; }
        .form-control, select { width:100%; padding:0.8rem 1rem; border:2px solid #dce6ef; border-radius:12px; font-size:1rem; background:#fafcfe; }
        .form-control:focus, select:focus { border-color:#f39c12; outline:none; }
        .flex-group { display:flex; gap:1rem; align-items:center; flex-wrap:wrap; }
        .flex-group select { flex:1; min-width:200px; }
        .btn-primary { background:#0a2a3d; color:white; padding:0.8rem 2rem; border:none; border-radius:14px; font-weight:600; font-size:1rem; cursor:pointer; transition:all 0.2s; width:100%; display:flex; align-items:center; justify-content:center; gap:0.6rem; }
        .btn-primary:hover { background:#1a4055; transform:translateY(-2px); }
        .btn-secondary { background:#e8f0f7; color:#0a2a3d; padding:0.8rem 2rem; border:none; border-radius:14px; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; gap:0.6rem; }
        .btn-secondary:hover { background:#d4e2ed; }
        #imageInput { padding:1rem; border:2px dashed #b6cfdd; border-radius:12px; width:100%; cursor:pointer; background:#fafcfe; }
        #imageInput:hover { border-color:#f39c12; background:#fefce8; }
        .preview-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:1rem; margin-top:1rem; }
        .preview-grid img { width:100%; height:120px; object-fit:cover; border-radius:12px; border:2px solid #e8f0f7; }
        .info-box { background:#fefce8; padding:1rem; border-radius:12px; border-left:4px solid #f39c12; margin-bottom:1rem; }
        .info-box strong { color:#b45309; }
        .result-box { background:#2d2d2d; color:#f8f8f8; padding:2rem; border-radius:12px; text-align:center; }
        .result-box .bib-item { display:inline-block; background:#1a3a2a; padding:0.5rem 1.5rem; border-radius:12px; font-size:2rem; font-weight:700; color:#4CAF50; margin:0.3rem; border:2px solid #4CAF50; }
        .result-box .time { color:#8aaabe; margin-top:0.5rem; }
        .result-box .count { color:#f39c12; font-size:0.9rem; }
        @media (max-width:768px) { body { padding:1rem; } .flex-group { flex-direction:column; } }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <h1><i class="fas fa-users"></i> Deteksi BIB Rombongan</h1>
        <p class="subtitle">Khusus untuk 1 foto dengan banyak orang (2-10 BIB)</p>
        
        <div class="badge-group">
            <span class="badge blue"><i class="fas fa-hashtag"></i> Multi BIB</span>
            <span class="badge green"><i class="fas fa-eye"></i> Anti Blur</span>
            <span class="badge orange"><i class="fas fa-users"></i> 1 Foto Banyak Orang</span>
            <span class="badge red"><i class="fas fa-bolt"></i> Tesseract + EasyOCR</span>
        </div>
        
        <div class="info-box">
            <strong>💡 Tips:</strong>
            <ul style="margin-left:1.5rem; margin-top:0.5rem; color:#4a6a7d;">
                <li>Foto dengan resolusi tinggi (minimal 1080p)</li>
                <li>Pastikan BIB terlihat jelas (tidak tertutup)</li>
                <li>Ground Truth pisahkan dengan koma: <strong>1043, 2024, 3001</strong></li>
            </ul>
        </div>
        
        <form id="uploadForm" enctype="multipart/form-data" method="POST" action="upload_rombongan.php">
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

            <div class="form-group">
                <label for="groundTruth"><i class="fas fa-pen"></i> Ground Truth (pisahkan dengan koma):</label>
                <input type="text" id="groundTruth" name="ground_truth" 
                       placeholder="Contoh: 1043, 2024, 3001" 
                       class="form-control" required>
                <small style="color:#7a9aad;">Masukkan semua BIB yang ada di gambar, pisahkan dengan koma</small>
            </div>

            <div class="form-group">
                <label for="imageInput"><i class="fas fa-image"></i> Pilih Gambar (bisa banyak):</label>
                <input type="file" id="imageInput" name="images[]" accept="image/*" multiple required>
                <div id="imagePreview" class="preview-grid"></div>
            </div>

            <button type="submit" class="btn-primary" id="submitBtn">
                <i class="fas fa-play"></i> Deteksi BIB Rombongan
            </button>
        </form>
    </div>
</div>

<script>
document.getElementById('imageInput').addEventListener('change', function(e) {
    const preview = document.getElementById('imagePreview');
    preview.innerHTML = '';
    Array.from(e.target.files).forEach(file => {
        const reader = new FileReader();
        reader.onload = function(ev) {
            const img = document.createElement('img');
            img.src = ev.target.result;
            img.alt = file.name;
            preview.appendChild(img);
        };
        reader.readAsDataURL(file);
    });
});

document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    
    const groundTruth = document.getElementById('groundTruth').value.trim();
    if (!groundTruth) {
        alert('⚠️ Isi Ground Truth!');
        return;
    }
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mendeteksi...';
    
    const formData = new FormData(this);
    
    try {
        const response = await fetch('upload_rombongan.php', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (result.success) {
            alert('✅ ' + result.message + '\n📊 ' + result.files_processed + ' gambar\n⏱️ ' + result.total_time.toFixed(2) + ' detik');
            location.reload();
        } else {
            alert('❌ Error: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
    
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fas fa-play"></i> Deteksi BIB Rombongan';
});

function showNewFolderModal() {
    document.getElementById('folderModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('folderModal').style.display = 'none';
}
</script>

<!-- Modal Buat Folder -->
<div id="folderModal" class="modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);justify-content:center;align-items:center;z-index:1000;">
    <div class="modal-content" style="background:white;padding:2.5rem;border-radius:28px;max-width:500px;width:90%;position:relative;">
        <span class="close" onclick="closeModal()" style="position:absolute;top:1rem;right:1.5rem;font-size:2rem;cursor:pointer;color:#8aaabe;">&times;</span>
        <h2><i class="fas fa-folder-plus"></i> Buat Folder Baru</h2>
        <form id="folderForm">
            <div class="form-group">
                <label>Nama Folder:</label>
                <input type="text" id="folderName" required placeholder="Contoh: Test Rombongan" class="form-control">
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
</script>
</body>
</html>