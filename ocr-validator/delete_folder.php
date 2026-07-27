<?php
// delete_folder.php
require_once 'db_config.php';
header('Content-Type: application/json');

$input = json_decode(file_get_contents('php://input'), true);
$folder_id = isset($input['folder_id']) ? intval($input['folder_id']) : 0;

if ($folder_id <= 0) {
    echo json_encode(['success' => false, 'error' => 'Folder ID tidak valid']);
    exit;
}

$conn = getDBConnection();
$stmt = $conn->prepare("DELETE FROM test_folders WHERE id = ?");
$stmt->bind_param("i", $folder_id);

if ($stmt->execute()) {
    echo json_encode(['success' => true, 'message' => 'Folder berhasil dihapus']);
} else {
    echo json_encode(['success' => false, 'error' => $conn->error]);
}
$stmt->close();
$conn->close();
?>