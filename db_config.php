<?php
// db_config.php - OCR Validator
error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);

define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_NAME', 'ocr_validator');

function getDBConnection() {
    try {
        $conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
        if ($conn->connect_error) {
            throw new Exception('Koneksi gagal: ' . $conn->connect_error);
        }
        return $conn;
    } catch (Exception $e) {
        die('Error database: ' . $e->getMessage());
    }
}

function sanitize($input) {
    return htmlspecialchars(strip_tags(trim($input)));
}
?>