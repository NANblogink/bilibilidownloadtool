<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Token');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
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

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

$pdo->exec('CREATE TABLE IF NOT EXISTS crash_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(200) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    platform VARCHAR(20) DEFAULT "",
    crash_type VARCHAR(100) DEFAULT "",
    crash_message TEXT,
    stack_trace TEXT,
    system_info TEXT,
    log_content TEXT,
    error_line INTEGER DEFAULT 0,
    error_file VARCHAR(500) DEFAULT "",
    ip_address VARCHAR(45) DEFAULT "",
    is_resolved BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 兼容旧数据库：补充新增字段
foreach (['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""'] as $col => $def) {
    try { $pdo->exec("ALTER TABLE crash_log ADD COLUMN $col $def"); } catch (\Exception $e) {}
}

// 公开接口：上报崩溃 / 上传详细日志文件
if ($method === 'POST' && in_array($action, ['report', 'upload_log'], true)) {
    if ($action === 'report') {
        handleCrashReport($pdo);
    } else {
        handleCrashUploadLog($pdo);
    }
    exit;
}

// 以下接口需要 Token 认证
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

if ($method === 'GET') {
    if ($action === 'stats') {
        handleCrashStats($pdo);
    } elseif ($action === 'device') {
        handleCrashDeviceLogs($pdo);
    } elseif ($action === 'list') {
        handleCrashList($pdo);
    } else {
        handleCrashList($pdo);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    $putAction = $action ?: ($input['action'] ?? '');
    if ($putAction === 'resolve') {
        handleCrashResolve($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleCrashDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

// 公开：上报崩溃
function handleCrashReport($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;

    $clientId = trim($input['client_id'] ?? '');
    $version = trim($input['version'] ?? '');
    $platform = trim($input['platform'] ?? '');
    $crashType = trim($input['crash_type'] ?? '');
    $crashMessage = trim($input['crash_message'] ?? '');
    $stackTrace = $input['stack_trace'] ?? '';
    $systemInfo = $input['system_info'] ?? '';
    $errorLine = (int)($input['error_line'] ?? 0);
    $errorFile = trim($input['error_file'] ?? '');
    $ipAddress = trim($input['ip_address'] ?? ($_SERVER['REMOTE_ADDR'] ?? ($_SERVER['HTTP_X_FORWARDED_FOR'] ?? '')));

    if (!is_string($stackTrace)) {
        $stackTrace = json_encode($stackTrace, JSON_UNESCAPED_UNICODE);
    }
    if (!is_string($systemInfo)) {
        $systemInfo = json_encode($systemInfo, JSON_UNESCAPED_UNICODE);
    }

    if (empty($crashType) && empty($crashMessage)) {
        echo json_encode(['code' => 1, 'message' => '缺少崩溃类型或信息'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO crash_log (client_id, version, platform, crash_type, crash_message, stack_trace, system_info, error_line, error_file, ip_address, is_resolved) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)");
        $stmt->execute([$clientId, $version, $platform, $crashType, $crashMessage, $stackTrace, $systemInfo, $errorLine, $errorFile, $ipAddress]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '崩溃上报成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '上报失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

// 公开：上传详细日志文件
function handleCrashUploadLog($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = [];

    $crashId = $_POST['crash_id'] ?? $_GET['crash_id'] ?? ($input['crash_id'] ?? '');

    if (empty($crashId)) {
        echo json_encode(['code' => 1, 'message' => '缺少崩溃记录ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $hasFile = isset($_FILES['file']) && $_FILES['file']['error'] === UPLOAD_ERR_OK;
    $logContent = $input['log_content'] ?? '';

    if (!$hasFile && empty($logContent)) {
        $errMsg = '上传失败';
        if (isset($_FILES['file'])) {
            $errCodes = [
                UPLOAD_ERR_INI_SIZE => '文件超过服务器大小限制',
                UPLOAD_ERR_FORM_SIZE => '文件超过表单大小限制',
                UPLOAD_ERR_PARTIAL => '文件上传不完整',
                UPLOAD_ERR_NO_FILE => '未选择文件',
            ];
            $errMsg = $errCodes[$_FILES['file']['error']] ?? $errMsg;
        }
        echo json_encode(['code' => 1, 'message' => $errMsg], JSON_UNESCAPED_UNICODE);
        return;
    }

    $uploadDir = __DIR__ . '/../../../uploads/crashlogs/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0755, true);
    }

    $safeCrashId = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $crashId);
    $fileName = 'crash_' . $safeCrashId . '.log';
    $counter = 1;
    while (file_exists($uploadDir . $fileName)) {
        $fileName = 'crash_' . $safeCrashId . '_' . $counter . '.log';
        $counter++;
    }

    $destPath = $uploadDir . $fileName;

    if ($hasFile) {
        $file = $_FILES['file'];
        $allowedExts = ['log', 'txt', 'json', 'zip'];
        $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
        if (!in_array($ext, $allowedExts)) {
            echo json_encode(['code' => 1, 'message' => '不支持的文件类型'], JSON_UNESCAPED_UNICODE);
            return;
        }
        if (!move_uploaded_file($file['tmp_name'], $destPath)) {
            echo json_encode(['code' => 1, 'message' => '文件保存失败'], JSON_UNESCAPED_UNICODE);
            return;
        }
        $logContent = file_get_contents($destPath);
    } else {
        if (file_put_contents($destPath, $logContent) === false) {
            echo json_encode(['code' => 1, 'message' => '文件保存失败'], JSON_UNESCAPED_UNICODE);
            return;
        }
    }

    // 限制日志大小，避免数据库过大
    if (strlen($logContent) > 1024 * 1024) {
        $logContent = substr($logContent, 0, 1024 * 1024) . "\n...[truncated]";
    }

    // 将日志内容写入数据库
    $stmt = $pdo->prepare('UPDATE crash_log SET log_content = ? WHERE id = ?');
    $stmt->execute([$logContent, $crashId]);

    echo json_encode([
        'code' => 0,
        'data' => [
            'crash_id' => $crashId,
            'file_name' => $fileName,
            'file_size' => filesize($destPath)
        ],
        'message' => '日志上传成功'
    ], JSON_UNESCAPED_UNICODE);
}

function handleCrashList($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? '';
    $isResolved = $_GET['is_resolved'] ?? '';
    $clientId = $_GET['client_id'] ?? '';
    $limit = (int)($_GET['limit'] ?? 500);
    if ($limit <= 0 || $limit > 5000) $limit = 500;
    $offset = max(0, (int)($_GET['offset'] ?? 0));

    $sql = 'SELECT * FROM crash_log WHERE 1=1';
    $params = [];
    $countParams = [];
    if ($version !== '') {
        $sql .= ' AND version = ?';
        $params[] = $version;
        $countParams[] = $version;
    }
    if ($platform !== '') {
        $sql .= ' AND platform = ?';
        $params[] = $platform;
        $countParams[] = $platform;
    }
    if ($isResolved !== '') {
        $sql .= ' AND is_resolved = ?';
        $params[] = filter_var($isResolved, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
        $countParams[] = filter_var($isResolved, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    }
    if ($clientId !== '') {
        $sql .= ' AND client_id = ?';
        $params[] = $clientId;
        $countParams[] = $clientId;
    }

    $countSql = str_replace('SELECT *', 'SELECT COUNT(*) as total', $sql);
    $countStmt = $pdo->prepare($countSql);
    $countStmt->execute($countParams);
    $total = (int)$countStmt->fetchColumn();

    $sql .= ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
    $params[] = $limit;
    $params[] = $offset;

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => ['items' => $rows, 'total' => $total, 'limit' => $limit, 'offset' => $offset],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleCrashStats($pdo) {
    $stats = [];

    // 总数
    $stmt = $pdo->query('SELECT COUNT(*) as total FROM crash_log');
    $stats['total'] = (int)$stmt->fetchColumn();

    // 未解决数
    $stmt = $pdo->query('SELECT COUNT(*) as unresolved FROM crash_log WHERE is_resolved = 0');
    $stats['unresolved'] = (int)$stmt->fetchColumn();

    // 已解决数
    $stmt = $pdo->query('SELECT COUNT(*) as resolved FROM crash_log WHERE is_resolved = 1');
    $stats['resolved'] = (int)$stmt->fetchColumn();

    // 按版本统计
    $stmt = $pdo->query('SELECT version, COUNT(*) as cnt FROM crash_log GROUP BY version ORDER BY cnt DESC');
    $stats['by_version'] = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // 按平台统计
    $stmt = $pdo->query('SELECT platform, COUNT(*) as cnt FROM crash_log GROUP BY platform ORDER BY cnt DESC');
    $stats['by_platform'] = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // 按崩溃类型统计
    $stmt = $pdo->query('SELECT crash_type, COUNT(*) as cnt FROM crash_log GROUP BY crash_type ORDER BY cnt DESC LIMIT 20');
    $stats['by_type'] = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['code' => 0, 'data' => $stats, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleCrashResolve($pdo, $input) {
    $id = $input['id'] ?? null;
    $isResolved = filter_var($input['is_resolved'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少崩溃记录ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare('UPDATE crash_log SET is_resolved = ? WHERE id = ?');
    $stmt->execute([$isResolved, $id]);
    echo json_encode(['code' => 0, 'message' => $isResolved ? '已标记为已解决' : '已标记为未解决'], JSON_UNESCAPED_UNICODE);
}

function handleCrashDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少崩溃记录ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM crash_log WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '崩溃记录已删除'], JSON_UNESCAPED_UNICODE);
}

function handleCrashDeviceLogs($pdo) {
    $clientId = trim($_GET['client_id'] ?? $_POST['client_id'] ?? '');
    if (empty($clientId)) {
        echo json_encode(['code' => 1, 'message' => '缺少设备码(client_id)'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $limit = min(5000, max(1, (int)($_GET['limit'] ?? 500)));
    $offset = max(0, (int)($_GET['offset'] ?? 0));

    $countStmt = $pdo->prepare('SELECT COUNT(*) FROM crash_log WHERE client_id = ?');
    $countStmt->execute([$clientId]);
    $total = (int)$countStmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT * FROM crash_log WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $stmt->execute([$clientId, $limit, $offset]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => ['items' => $rows, 'total' => $total, 'limit' => $limit, 'offset' => $offset],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}
