<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Token');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

// 确保新字段存在（兼容旧数据库）
$migrations = [
    'stat_error' => ['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""', 'log_file' => 'VARCHAR(500) DEFAULT ""'],
    'crash_log' => ['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""'],
];
foreach ($migrations as $table => $cols) {
    foreach ($cols as $col => $def) {
        try { $pdo->exec("ALTER TABLE $table ADD COLUMN $col $def"); } catch (\Exception $e) {}
    }
}

// Token 认证
$token = $_SERVER['HTTP_X_API_TOKEN'] ?? $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = preg_replace('/^Bearer\s+/i', '', $token);

$configPath = __DIR__ . '/../../../../data/admin_config.php';
if (file_exists($configPath)) {
    require_once $configPath;
}
$validToken = defined('API_TOKEN') ? API_TOKEN : '';

if (empty($validToken)) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => 'API Token未配置'], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($token !== $validToken) {
    http_response_code(401);
    echo json_encode(['code' => 1, 'message' => '认证失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

if ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$action && !empty($input['action'])) {
        $action = $input['action'];
    }
}

$clientId = trim($_GET['client_id'] ?? ($_POST['client_id'] ?? ($input['client_id'] ?? '')));

if (empty($clientId)) {
    echo json_encode(['code' => 1, 'message' => '缺少设备码(client_id)'], JSON_UNESCAPED_UNICODE);
    exit;
}

$limit = min(5000, max(1, (int)($_GET['limit'] ?? 500)));
$offset = max(0, (int)($_GET['offset'] ?? 0));

// 设备信息
$deviceStmt = $pdo->prepare('SELECT * FROM stat_device WHERE client_id = ?');
$deviceStmt->execute([$clientId]);
$device = $deviceStmt->fetch(PDO::FETCH_ASSOC);

// 错误日志
$errCount = $pdo->prepare('SELECT COUNT(*) FROM stat_error WHERE client_id = ?');
$errCount->execute([$clientId]);
$errorTotal = (int)$errCount->fetchColumn();

$errStmt = $pdo->prepare('SELECT * FROM stat_error WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
$errStmt->execute([$clientId, $limit, $offset]);
$errors = $errStmt->fetchAll(PDO::FETCH_ASSOC);

// 崩溃日志
$crashCount = $pdo->prepare('SELECT COUNT(*) FROM crash_log WHERE client_id = ?');
$crashCount->execute([$clientId]);
$crashTotal = (int)$crashCount->fetchColumn();

$crashStmt = $pdo->prepare('SELECT * FROM crash_log WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
$crashStmt->execute([$clientId, $limit, $offset]);
$crashes = $crashStmt->fetchAll(PDO::FETCH_ASSOC);

// 事件日志
$evtCount = $pdo->prepare('SELECT COUNT(*) FROM stat_event WHERE client_id = ?');
$evtCount->execute([$clientId]);
$eventTotal = (int)$evtCount->fetchColumn();

$evtStmt = $pdo->prepare('SELECT * FROM stat_event WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
$evtStmt->execute([$clientId, $limit, $offset]);
$events = $evtStmt->fetchAll(PDO::FETCH_ASSOC);

// 下载日志文件内容（如果存在）
$logFiles = [];
foreach ($errors as $err) {
    if (!empty($err['log_file'])) {
        $logPath = __DIR__ . '/../../../' . $err['log_file'];
        if (file_exists($logPath)) {
            $logFiles[$err['id']] = [
                'error_id' => $err['id'],
                'file_path' => $err['log_file'],
                'content' => file_get_contents($logPath),
                'size' => filesize($logPath),
            ];
        }
    }
}

echo json_encode([
    'code' => 0,
    'data' => [
        'device' => $device,
        'errors' => ['items' => $errors, 'total' => $errorTotal, 'limit' => $limit, 'offset' => $offset],
        'crashes' => ['items' => $crashes, 'total' => $crashTotal, 'limit' => $limit, 'offset' => $offset],
        'events' => ['items' => $events, 'total' => $eventTotal, 'limit' => $limit, 'offset' => $offset],
        'log_files' => $logFiles,
    ],
    'message' => 'success'
], JSON_UNESCAPED_UNICODE);