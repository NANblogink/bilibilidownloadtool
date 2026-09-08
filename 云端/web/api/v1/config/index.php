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

$pdo->exec('CREATE TABLE IF NOT EXISTS remote_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    config_type VARCHAR(20) DEFAULT "string",
    description VARCHAR(500) DEFAULT "",
    min_version VARCHAR(20) DEFAULT "",
    max_version VARCHAR(20) DEFAULT "",
    target_platform VARCHAR(20) DEFAULT "all",
    is_active BOOLEAN DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：客户端获取适用于指定版本的配置
if ($method === 'GET' && $action === 'get') {
    handleConfigGet($pdo);
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
        handleConfigList($pdo);
    } else {
        handleConfigList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'set') {
        handleConfigSet($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handleConfigUpdate($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleConfigDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

function versionCompare($v1, $v2) {
    $parts1 = array_map('intval', explode('.', $v1));
    $parts2 = array_map('intval', explode('.', $v2));
    $maxLen = max(count($parts1), count($parts2));
    for ($i = 0; $i < $maxLen; $i++) {
        $p1 = $parts1[$i] ?? 0;
        $p2 = $parts2[$i] ?? 0;
        if ($p1 < $p2) return -1;
        if ($p1 > $p2) return 1;
    }
    return 0;
}

// 公开：获取适用于指定版本的配置
function handleConfigGet($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';

    $sql = 'SELECT * FROM remote_config WHERE is_active = 1';
    $params = [];
    $sql .= ' AND (target_platform = ? OR target_platform = ?)';
    $params[] = 'all';
    $params[] = $platform;
    $sql .= ' ORDER BY config_key';

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $configs = [];
    foreach ($rows as $row) {
        $minVersion = $row['min_version'] ?? '';
        $maxVersion = $row['max_version'] ?? '';
        if (!empty($version) && !empty($minVersion) && versionCompare($version, $minVersion) < 0) {
            continue;
        }
        if (!empty($version) && !empty($maxVersion) && versionCompare($version, $maxVersion) > 0) {
            continue;
        }
        $value = castConfigValue($row['config_value'], $row['config_type']);
        $configs[$row['config_key']] = [
            'value' => $value,
            'type' => $row['config_type'],
            'description' => $row['description']
        ];
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'configs' => $configs,
            'version' => $version,
            'platform' => $platform
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleConfigList($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM remote_config ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleConfigSet($pdo, $input) {
    $configKey = trim($input['config_key'] ?? '');
    $configValue = $input['config_value'] ?? '';
    $configType = $input['config_type'] ?? 'string';
    $description = trim($input['description'] ?? '');
    $minVersion = trim($input['min_version'] ?? '');
    $maxVersion = trim($input['max_version'] ?? '');
    $targetPlatform = $input['target_platform'] ?? 'all';
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($configKey)) {
        echo json_encode(['code' => 1, 'message' => '配置键不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($configType, ['string', 'bool', 'int', 'json'])) {
        echo json_encode(['code' => 1, 'message' => '无效的配置类型'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $storedValue = normalizeConfigValue($configValue, $configType);
    $now = date('Y-m-d H:i:s');

    try {
        $stmt = $pdo->prepare("INSERT INTO remote_config (config_key, config_value, config_type, description, min_version, max_version, target_platform, is_active, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(config_key) DO UPDATE SET config_value = ?, config_type = ?, description = ?, min_version = ?, max_version = ?, target_platform = ?, is_active = ?, updated_at = ?");
        $stmt->execute([
            $configKey, $storedValue, $configType, $description, $minVersion, $maxVersion, $targetPlatform, $isActive, $now, $now,
            $storedValue, $configType, $description, $minVersion, $maxVersion, $targetPlatform, $isActive, $now
        ]);

        $stmt = $pdo->prepare('SELECT * FROM remote_config WHERE config_key = ?');
        $stmt->execute([$configKey]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        echo json_encode(['code' => 0, 'data' => $row, 'message' => '配置保存成功'], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        echo json_encode(['code' => 1, 'message' => '保存失败: ' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleConfigUpdate($pdo, $input) {
    $id = $input['id'] ?? null;
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少配置ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $fields = [];
    $params = [];
    foreach (['config_key', 'config_value', 'config_type', 'description', 'min_version', 'max_version', 'target_platform'] as $key) {
        if (array_key_exists($key, $input)) {
            $val = $input[$key];
            if ($key === 'config_value' && isset($input['config_type'])) {
                $val = normalizeConfigValue($val, $input['config_type']);
            }
            $fields[] = "$key = ?";
            $params[] = $val;
        }
    }
    if (isset($input['is_active'])) {
        $fields[] = 'is_active = ?';
        $params[] = filter_var($input['is_active'], FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    }
    $fields[] = 'updated_at = ?';
    $params[] = date('Y-m-d H:i:s');
    $params[] = $id;

    if (empty($fields)) {
        echo json_encode(['code' => 1, 'message' => '没有需要更新的字段'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("UPDATE remote_config SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '配置更新成功'], JSON_UNESCAPED_UNICODE);
}

function handleConfigDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少配置ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM remote_config WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '配置已删除'], JSON_UNESCAPED_UNICODE);
}

function normalizeConfigValue($value, $type) {
    switch ($type) {
        case 'bool':
            return filter_var($value, FILTER_VALIDATE_BOOLEAN) ? 'true' : 'false';
        case 'int':
            return (string)(int)$value;
        case 'json':
            if (is_array($value)) {
                return json_encode($value, JSON_UNESCAPED_UNICODE);
            }
            return (string)$value;
        default:
            return (string)$value;
    }
}

function castConfigValue($value, $type) {
    switch ($type) {
        case 'bool':
            return filter_var($value, FILTER_VALIDATE_BOOLEAN);
        case 'int':
            return (int)$value;
        case 'json':
            $decoded = json_decode($value, true);
            return $decoded !== null ? $decoded : $value;
        default:
            return (string)$value;
    }
}
