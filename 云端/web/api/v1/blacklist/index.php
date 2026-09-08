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

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

$pdo->exec('CREATE TABLE IF NOT EXISTS version_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version VARCHAR(20) NOT NULL,
    platform VARCHAR(20) DEFAULT "all",
    reason VARCHAR(500) DEFAULT "",
    severity VARCHAR(20) DEFAULT "block",
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：检查版本是否被拉黑
if ($method === 'GET' && $action === 'check') {
    handleBlacklistCheck($pdo);
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
    if ($action === 'list') {
        handleBlacklistList($pdo);
    } else {
        handleBlacklistList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'add') {
        handleBlacklistAdd($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handleBlacklistUpdate($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleBlacklistDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

// 公开：检查版本是否被拉黑
function handleBlacklistCheck($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';

    if (empty($version)) {
        echo json_encode(['code' => 1, 'message' => '缺少版本号'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM version_blacklist WHERE version = ? AND is_active = 1 AND (platform = 'all' OR platform = ?) ORDER BY created_at DESC LIMIT 1");
    $stmt->execute([$version, $platform]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'is_blacklisted' => false,
                'version' => $version,
                'platform' => $platform
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'is_blacklisted' => true,
            'version' => $version,
            'platform' => $platform,
            'severity' => $row['severity'],
            'reason' => $row['reason']
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleBlacklistList($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM version_blacklist ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleBlacklistAdd($pdo, $input) {
    $version = trim($input['version'] ?? '');
    $platform = $input['platform'] ?? 'all';
    $reason = trim($input['reason'] ?? '');
    $severity = $input['severity'] ?? 'block';
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($version)) {
        echo json_encode(['code' => 1, 'message' => '版本号不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($severity, ['warn', 'block', 'critical'])) {
        echo json_encode(['code' => 1, 'message' => '无效的严重级别'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO version_blacklist (version, platform, reason, severity, is_active) VALUES (?, ?, ?, ?, ?)");
        $stmt->execute([$version, $platform, $reason, $severity, $isActive]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '黑名单添加成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '添加失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleBlacklistUpdate($pdo, $input) {
    $id = $input['id'] ?? null;
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少黑名单ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $fields = [];
    $params = [];
    foreach (['version', 'platform', 'reason', 'severity'] as $key) {
        if (array_key_exists($key, $input)) {
            $fields[] = "$key = ?";
            $params[] = $input[$key];
        }
    }
    if (isset($input['is_active'])) {
        $fields[] = 'is_active = ?';
        $params[] = filter_var($input['is_active'], FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    }
    $params[] = $id;

    if (empty($fields)) {
        echo json_encode(['code' => 1, 'message' => '没有需要更新的字段'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("UPDATE version_blacklist SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '黑名单更新成功'], JSON_UNESCAPED_UNICODE);
}

function handleBlacklistDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少黑名单ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM version_blacklist WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '黑名单已删除'], JSON_UNESCAPED_UNICODE);
}
