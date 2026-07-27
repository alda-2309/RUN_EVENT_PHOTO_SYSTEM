<?php
// create_folder.php
require_once 'db_config.php';
header('Content-Type: application/json');

$input = json_decode(file_get_contents('php://input'), true);
$name = trim($input['name'] ?? '');
$description = trim($input['description'] ?? '');

if (empty($name)) {
    echo json_encode(['success' => false, 'error' => 'Nama folder harus diisi']);
    exit;
}

$conn = getDBConnection();
$stmt = $conn->prepare("INSERT INTO test_folders (folder_name, description) VALUES (?, ?)");
$stmt->bind_param("ss", $name, $description);

if ($stmt->execute()) {
    echo json_encode(['success' => true, 'folder_id' => $conn->insert_id, 'message' => 'Folder berhasil dibuat']);
} else {
    echo json_encode(['success' => false, 'error' => $conn->error]);
}
$stmt->close();
$conn->close();
?>