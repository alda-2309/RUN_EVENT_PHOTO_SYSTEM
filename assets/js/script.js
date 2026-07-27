// script.js - OCR Validator (Dengan Support Rombongan)
document.addEventListener('DOMContentLoaded', function() {
    // ============================================
    // PREVIEW GAMBAR
    // ============================================
    const imageInput = document.getElementById('imageInput');
    if (imageInput) {
        imageInput.addEventListener('change', function(e) {
            const preview = document.getElementById('imagePreview');
            if (!preview) return;
            preview.innerHTML = '';
            Array.from(e.target.files).forEach(file => {
                const reader = new FileReader();
                reader.onload = function(ev) {
                    const img = document.createElement('img');
                    img.src = ev.target.result;
                    img.alt = file.name;
                    img.title = file.name;
                    preview.appendChild(img);
                };
                reader.readAsDataURL(file);
            });
        });
    }

    // ============================================
    // SUBMIT FORM - DENGAN DETEKSI MODE
    // ============================================
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            const progressContainer = document.getElementById('progressContainer');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const progressPercent = document.getElementById('progressPercent');
            
            // Validasi ground truth
            const groundTruth = document.getElementById('groundTruth');
            if (!groundTruth) {
                alert('⚠️ Harap isi Ground Truth (angka yang benar)!');
                return;
            }
            
            const groundTruthValue = groundTruth.value.trim();
            if (!groundTruthValue) {
                alert('⚠️ Harap isi Ground Truth (angka yang benar)!');
                return;
            }
            
            // Validasi hanya angka dan koma/spasi
            if (!/^[\d\s,;]+$/.test(groundTruthValue)) {
                alert('⚠️ Ground Truth hanya boleh berisi angka! (contoh: 0074 atau 1043, 2024)');
                return;
            }
            
            // Tampilkan progress
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            function updateProgress(percent, message) {
                if (progressBar) {
                    progressBar.style.width = percent + '%';
                    progressBar.textContent = Math.round(percent) + '%';
                }
                if (progressText) {
                    progressText.textContent = message;
                }
                if (progressPercent) {
                    progressPercent.textContent = Math.round(percent) + '%';
                }
            }
            
            updateProgress(0, 'Memulai proses...');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Memproses...';

            const formData = new FormData(this);
            
            // Cek apakah ini mode rombongan
            const isRombongan = window.location.href.includes('rombongan') || 
                               document.querySelector('.mode-card.active .name')?.textContent === 'Rombongan';
            
            try {
                updateProgress(20, 'Mengupload gambar...');
                
                // Tentukan endpoint berdasarkan mode
                let endpoint = 'upload.php';
                if (isRombongan || document.querySelector('form')?.action?.includes('rombongan')) {
                    endpoint = 'upload_rombongan.php';
                }
                
                const response = await fetch(endpoint, {
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
                        
                        // Tampilkan detail hasil jika ada
                        if (result.files && result.files.length > 0) {
                            message += '\n\n📝 Detail:';
                            result.files.forEach((file, i) => {
                                const numbers = file.result?.numbers || file.result?.tesseract?.numbers || '-';
                                const time = file.time || file.result?.tesseract?.time || 0;
                                message += '\n  ' + (i+1) + '. ' + file.file + ' → ' + numbers + ' (' + time.toFixed(2) + 's)';
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
    }

    // ============================================
    // BUAT FOLDER
    // ============================================
    const folderForm = document.getElementById('folderForm');
    if (folderForm) {
        folderForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const nameInput = document.getElementById('folderName');
            const descInput = document.getElementById('folderDesc');
            
            const name = nameInput ? nameInput.value.trim() : '';
            if (!name) {
                alert('Nama folder harus diisi');
                return;
            }
            
            try {
                const response = await fetch('create_folder.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        name: name, 
                        description: descInput ? descInput.value.trim() : '' 
                    })
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
    }
});

// ============================================
// MODAL FUNCTIONS
// ============================================

function showNewFolderModal() {
    const modal = document.getElementById('folderModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeModal() {
    const modal = document.getElementById('folderModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal outside click
window.onclick = function(event) {
    const modal = document.getElementById('folderModal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
};

// ============================================
// LOAD FOLDER RESULTS
// ============================================

async function loadFolder(folderId) {
    const resultsDiv = document.getElementById('resultsContent');
    if (!resultsDiv) return;
    
    resultsDiv.innerHTML = `
        <div class="info-box">
            <i class="fas fa-spinner fa-spin" style="font-size:2rem;"></i>
            <p>Memuat data validasi...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`results.php?folder_id=${folderId}`);
        const data = await response.json();
        
        if (!data.success) {
            resultsDiv.innerHTML = `
                <div class="info-box" style="background:#fde;border-color:#fcc;">
                    <i class="fas fa-exclamation-triangle" style="color:#f44336;font-size:2rem;"></i>
                    <p>Error: ${data.error || 'Gagal memuat data'}</p>
                </div>
            `;
            return;
        }
        
        if (!data.results || data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="info-box">
                    <i class="fas fa-inbox" style="font-size:2rem;"></i>
                    <p>Belum ada hasil validasi di folder ini</p>
                    <p style="font-size:0.9rem; margin-top:0.5rem;">Upload gambar untuk memulai validasi</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // ============================================
        // STATISTIK
        // ============================================
        if (data.stats && Object.keys(data.stats).length > 0) {
            html += `<div class="card"><h3><i class="fas fa-chart-line"></i> Statistik Validasi</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1rem;">`;
            
            Object.keys(data.stats).forEach(engine => {
                const stat = data.stats[engine];
                const label = { tesseract:'Tesseract', easyocr:'EasyOCR', rombongan:'Rombongan' }[engine] || engine;
                const color = { tesseract:'#2b7a9c', easyocr:'#f39c12', rombongan:'#c62828' }[engine] || '#666';
                const isWinner = stat.avg_accuracy > (Object.keys(data.stats).length > 1 ? 
                    Math.max(...Object.values(data.stats).map(s => s.avg_accuracy)) - stat.avg_accuracy : 0);
                
                html += `
                    <div style="border-top:4px solid ${color};background:#f8fafc;padding:1rem;border-radius:12px;">
                        <div style="font-weight:700;font-size:1.1rem;display:flex;justify-content:space-between;">
                            <span>${label}</span>
                            ${isWinner ? '<span style="color:#27ae60;">🏆</span>' : ''}
                        </div>
                        <div style="font-size:0.9rem;color:#4a6a7d;">⚡ Waktu: <strong>${stat.avg_time.toFixed(3)}s</strong></div>
                        <div style="font-size:0.9rem;color:#4a6a7d;">🎯 Akurasi: <strong>${stat.avg_accuracy.toFixed(1)}%</strong></div>
                        <div style="font-size:0.9rem;color:#4a6a7d;">📝 ${stat.count} gambar</div>
                    </div>
                `;
            });
            html += `</div></div>`;
        }
        
        // ============================================
        // DETAIL HASIL
        // ============================================
        html += `<div class="card"><h3><i class="fas fa-images"></i> Detail Validasi (${data.total_images} gambar)</h3>`;
        
        data.results.forEach((item, index) => {
            const hasGroundTruth = item.ground_truth && item.ground_truth.length > 0;
            const imageName = item.image?.image_name || 'gambar';
            const imagePath = item.image?.image_path || '';
            const ocrKeys = Object.keys(item.ocr || {});
            
            html += `
                <div style="background:white;border-radius:20px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 4px 16px rgba(0,0,0,0.04);">
                    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
                        <div>
                            <img src="${imagePath}" style="max-width:150px;max-height:120px;border-radius:12px;object-fit:cover;border:2px solid #e8f0f7;" 
                                 alt="${imageName}" 
                                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'150\' height=\'120\'%3E%3Crect fill=\'%23f0f5fa\' width=\'150\' height=\'120\'/%3E%3Ctext x=\'50%25\' y=\'50%25\' dominant-baseline=\'central\' text-anchor=\'middle\' fill=\'%238aaabe\' font-family=\'sans-serif\' font-size=\'14\'%3EGambar%3C/text%3E%3C/svg%3E'">
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
                                    const label = { tesseract:'Tesseract', easyocr:'EasyOCR', rombongan:'Rombongan' }[engine] || engine;
                                    const color = { tesseract:'#2b7a9c', easyocr:'#f39c12', rombongan:'#c62828' }[engine] || '#666';
                                    const accuracy = parseFloat(ocr.accuracy_score || 0);
                                    const isAccurate = accuracy >= 80;
                                    const text = ocr.ocr_text || '(kosong)';
                                    
                                    return `
                                        <div style="border-top:3px solid ${color};background:#f8fafc;padding:1rem;border-radius:12px;">
                                            <div style="font-weight:700;font-size:1rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                                                <span>${label}</span>
                                                ${accuracy > 0 ? `<span style="padding:2px 12px;border-radius:12px;font-size:0.75rem;font-weight:600;${isAccurate ? 'background:#d5f5e3;color:#27ae60;' : 'background:#fadbd8;color:#e74c3c;'}">${isAccurate ? '✅ Akurat' : '⚠️ Kurang Akurat'}</span>` : ''}
                                            </div>
                                            <div style="background:white;padding:0.5rem;border-radius:8px;font-size:1.3rem;font-weight:700;text-align:center;color:#0a2a3d;word-wrap:break-word;">
                                                ${text}
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
        
    } catch (error) {
        resultsDiv.innerHTML = `
            <div class="info-box" style="background:#fde;border-color:#fcc;">
                <i class="fas fa-exclamation-triangle" style="color:#f44336;font-size:2rem;"></i>
                <p>Error: ${error.message}</p>
                <p style="font-size:0.9rem; margin-top:0.5rem;">Coba refresh halaman atau periksa koneksi.</p>
            </div>
        `;
        console.error('Load folder error:', error);
    }
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

// ============================================
// EXPORT KE GLOBAL
// ============================================

window.showNewFolderModal = showNewFolderModal;
window.closeModal = closeModal;
window.loadFolder = loadFolder;
window.deleteFolder = deleteFolder;

console.log('✅ OCR Validator siap digunakan!');
console.log('📌 Fitur: Multi BIB | Anti Blur | 1 Foto Banyak Orang');