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

$pdo->exec('CREATE TABLE IF NOT EXISTS gray_release (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version VARCHAR(20) NOT NULL,
    platform VARCHAR(20) DEFAULT "all",
    channel VARCHAR(50) DEFAULT "stable",
    rollout_percentage INTEGER DEFAULT 0,
    whitelist TEXT DEFAULT "",
    blacklist TEXT DEFAULT "",
    status VARCHAR(20) DEFAULT "active",
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：检查客户端是否在灰度范围内
if ($method === 'GET' && $action === 'check') {
    handleGrayCheck($pdo);
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
        handleGrayList($pdo);
    } else {
        handleGrayList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create') {
        handleGrayCreate($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handleGrayUpdate($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleGrayDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

// 解析逗号分隔的列表为数据
function parseIdList($raw) {
    if (empty($raw)) return [];
    if (is_array($raw)) return array_map('trim', $raw);
    $parts = explode(',', $raw);
    $result = [];
    foreach ($parts as $p) {
        $p = trim($p);
        if ($p !== '') $result[] = $p;
    }
    return $result;
}

// 公开：检查客户端是否在灰度范围内
// 逻辑：白名单优先，然后黑名单排除，最后按 client_id 哈希值取模判断是否在百分比内
function handleGrayCheck($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';
    $clientId = $_GET['client_id'] ?? '';

    if (empty($version)) {
        echo json_encode(['code' => 1, 'message' => '缺少版本号'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (empty($clientId)) {
        echo json_encode(['code' => 1, 'message' => '缺少客户端ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM gray_release WHERE version = ? AND status = 'active' AND (platform = 'all' OR platform = ?) ORDER BY created_at DESC");
    $stmt->execute([$version, $platform]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    if (empty($rows)) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'in_gray' => false,
                'version' => $version,
                'platform' => $platform,
                'client_id' => $clientId
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    foreach ($rows as $row) {
        $whitelist = parseIdList($row['whitelist'] ?? '');
        $blacklist = parseIdList($row['blacklist'] ?? '');
        $percentage = (int)($row['rollout_percentage'] ?? 0);

        // 黑名单优先排除
        if (in_array($clientId, $blacklist, true)) {
            continue;
        }
        // 白名单直接放行
        if (in_array($clientId, $whitelist, true)) {
            echo json_encode([
                'code' => 0,
                'data' => [
                    'in_gray' => true,
                    'version' => $version,
                    'platform' => $platform,
                    'client_id' => $clientId,
                    'channel' => $row['channel'],
                    'rule_id' => $row['id'],
                    'reason' => 'whitelist'
                ],
                'message' => 'success'
            ], JSON_UNESCAPED_UNICODE);
            exit;
        }

        // 按 client_id 哈希取模判断是否在百分比内
        $hash = crc32($clientId);
        $mod = abs($hash) % 100;
        if ($mod < $percentage) {
            echo json_encode([
                'code' => 0,
                'data' => [
                    'in_gray' => true,
                    'version' => $version,
                    'platform' => $platform,
                    'client_id' => $clientId,
                    'channel' => $row['channel'],
                    'rule_id' => $row['id'],
                    'rollout_percentage' => $percentage,
                    'reason' => 'percentage'
                ],
                'message' => 'success'
            ], JSON_UNESCAPED_UNICODE);
            exit;
        }
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'in_gray' => false,
            'version' => $version,
            'platform' => $platform,
            'client_id' => $clientId
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleGrayList($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM gray_release ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleGrayCreate($pdo, $input) {
    $version = trim($input['version'] ?? '');
    $platform = $input['platform'] ?? 'all';
    $channel = $input['channel'] ?? 'stable';
    $rolloutPercentage = (int)($input['rollout_percentage'] ?? 0);
    $whitelist = is_array($input['whitelist'] ?? null) ? implode(',', $input['whitelist']) : trim($input['whitelist'] ?? '');
    $blacklist = is_array($input['blacklist'] ?? null) ? implode(',', $input['blacklist']) : trim($input['blacklist'] ?? '');
    $status = $input['status'] ?? 'active';

    if (empty($version)) {
        echo json_encode(['code' => 1, 'message' => '版本号不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if ($rolloutPercentage < 0 || $rolloutPercentage > 100) {
        echo json_encode(['code' => 1, 'message' => '灰度百分比必须在0-100之间'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($status, ['paused', 'active', 'completed'])) {
        echo json_encode(['code' => 1, 'message' => '无效的状态'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO gray_release (version, platform, channel, rollout_percentage, whitelist, blacklist, status) VALUES (?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$version, $platform, $channel, $rolloutPercentage, $whitelist, $blacklist, $status]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '灰度规则创建成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '创建失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleGrayUpdate($pdo, $input) {
    $id = $input['id'] ?? null;
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少灰度规则ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $fields = [];
    $params = [];
    foreach (['version', 'platform', 'channel'] as $key) {
        if (array_key_exists($key, $input)) {
            $fields[] = "$key = ?";
            $params[] = $input[$key];
        }
    }
    if (array_key_exists('rollout_percentage', $input)) {
        $pct = (int)$input['rollout_percentage'];
        if ($pct < 0 || $pct > 100) {
            echo json_encode(['code' => 1, 'message' => '灰度百分比必须在0-100之间'], JSON_UNESCAPED_UNICODE);
            return;
        }
        $fields[] = 'rollout_percentage = ?';
        $params[] = $pct;
    }
    if (array_key_exists('whitelist', $input)) {
        $fields[] = 'whitelist = ?';
        $params[] = is_array($input['whitelist']) ? implode(',', $input['whitelist']) : $input['whitelist'];
    }
    if (array_key_exists('blacklist', $input)) {
        $fields[] = 'blacklist = ?';
        $params[] = is_array($input['blacklist']) ? implode(',', $input['blacklist']) : $input['blacklist'];
    }
    if (array_key_exists('status', $input)) {
        if (!in_array($input['status'], ['paused', 'active', 'completed'])) {
            echo json_encode(['code' => 1, 'message' => '无效的状态'], JSON_UNESCAPED_UNICODE);
            return;
        }
        $fields[] = 'status = ?';
        $params[] = $input['status'];
    }
    $params[] = $id;

    if (empty($fields)) {
        echo json_encode(['code' => 1, 'message' => '没有需要更新的字段'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("UPDATE gray_release SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '灰度规则更新成功'], JSON_UNESCAPED_UNICODE);
}

function handleGrayDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少灰度规则ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM gray_release WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '灰度规则已删除'], JSON_UNESCAPED_UNICODE);
}
