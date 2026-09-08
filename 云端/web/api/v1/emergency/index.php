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

$pdo->exec('CREATE TABLE IF NOT EXISTS emergency_notice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id VARCHAR(100) NOT NULL UNIQUE,
    level VARCHAR(20) DEFAULT "info",
    title VARCHAR(200) NOT NULL,
    content TEXT,
    action_text VARCHAR(100) DEFAULT "",
    action_url VARCHAR(500) DEFAULT "",
    min_version VARCHAR(20) DEFAULT "",
    max_version VARCHAR(20) DEFAULT "",
    target_platform VARCHAR(20) DEFAULT "all",
    is_active BOOLEAN DEFAULT 1,
    start_time DATETIME,
    end_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：获取适用的紧急公告
if ($method === 'GET' && $action === 'list') {
    handleEmergencyList($pdo);
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
    if ($action === 'all') {
        handleEmergencyAll($pdo);
    } else {
        handleEmergencyAll($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create') {
        handleEmergencyCreate($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handleEmergencyUpdate($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleEmergencyDelete($pdo, $id);
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

function normalizeDatetime($val) {
    if (empty($val)) return null;
    $val = str_replace('T', ' ', $val);
    if (preg_match('/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/', $val)) {
        $val .= ':00';
    }
    return $val;
}

// 公开：获取适用的紧急公告
function handleEmergencyList($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';

    date_default_timezone_set('Asia/Shanghai');
    $now = date('Y-m-d H:i:s');

    $stmt = $pdo->prepare("SELECT * FROM emergency_notice WHERE is_active = 1 AND (target_platform = 'all' OR target_platform = ?) ORDER BY FIELD(level, 'critical', 'warning', 'maintenance', 'info'), created_at DESC");
    $stmt->execute([$platform]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $notices = [];
    foreach ($rows as $row) {
        $minVersion = $row['min_version'] ?? '';
        $maxVersion = $row['max_version'] ?? '';
        if (!empty($version) && !empty($minVersion) && versionCompare($version, $minVersion) < 0) {
            continue;
        }
        if (!empty($version) && !empty($maxVersion) && versionCompare($version, $maxVersion) > 0) {
            continue;
        }

        // 时间过滤
        $startTime = $row['start_time'] ?? null;
        $endTime = $row['end_time'] ?? null;
        if (!empty($startTime) && $startTime > $now) {
            continue;
        }
        if (!empty($endTime) && $endTime < $now) {
            continue;
        }

        $actionUrl = $row['action_url'] ?? '';
        if (!empty($actionUrl) && $actionUrl[0] === '/') {
            $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
            $actionUrl = $scheme . '://' . $host . $actionUrl;
        }

        $notices[] = [
            'notice_id' => $row['notice_id'],
            'level' => $row['level'],
            'title' => $row['title'],
            'content' => $row['content'],
            'action_text' => $row['action_text'],
            'action_url' => $actionUrl,
            'start_time' => $startTime,
            'end_time' => $endTime
        ];
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'has_notice' => !empty($notices),
            'notices' => $notices
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleEmergencyAll($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM emergency_notice ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleEmergencyCreate($pdo, $input) {
    $noticeId = trim($input['notice_id'] ?? '');
    $level = $input['level'] ?? 'info';
    $title = trim($input['title'] ?? '');
    $content = trim($input['content'] ?? '');
    $actionText = trim($input['action_text'] ?? '');
    $actionUrl = trim($input['action_url'] ?? '');
    $minVersion = trim($input['min_version'] ?? '');
    $maxVersion = trim($input['max_version'] ?? '');
    $targetPlatform = $input['target_platform'] ?? 'all';
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $startTime = normalizeDatetime($input['start_time'] ?? '');
    $endTime = normalizeDatetime($input['end_time'] ?? '');

    if (empty($noticeId) || empty($title)) {
        echo json_encode(['code' => 1, 'message' => '公告ID和标题不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($level, ['info', 'warning', 'critical', 'maintenance'])) {
        echo json_encode(['code' => 1, 'message' => '无效的公告级别'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO emergency_notice (notice_id, level, title, content, action_text, action_url, min_version, max_version, target_platform, is_active, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$noticeId, $level, $title, $content, $actionText, $actionUrl, $minVersion, $maxVersion, $targetPlatform, $isActive, $startTime, $endTime]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '紧急公告创建成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if (strpos($e->getMessage(), 'UNIQUE') !== false) {
            echo json_encode(['code' => 1, 'message' => '该公告ID已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '创建失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handleEmergencyUpdate($pdo, $input) {
    $id = $input['id'] ?? null;
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少公告ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $fields = [];
    $params = [];
    foreach (['notice_id', 'level', 'title', 'content', 'action_text', 'action_url', 'min_version', 'max_version', 'target_platform'] as $key) {
        if (array_key_exists($key, $input)) {
            $fields[] = "$key = ?";
            $params[] = $input[$key];
        }
    }
    if (array_key_exists('start_time', $input)) {
        $fields[] = 'start_time = ?';
        $params[] = normalizeDatetime($input['start_time']);
    }
    if (array_key_exists('end_time', $input)) {
        $fields[] = 'end_time = ?';
        $params[] = normalizeDatetime($input['end_time']);
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

    $stmt = $pdo->prepare("UPDATE emergency_notice SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '紧急公告更新成功'], JSON_UNESCAPED_UNICODE);
}

function handleEmergencyDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少公告ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM emergency_notice WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '紧急公告已删除'], JSON_UNESCAPED_UNICODE);
}
