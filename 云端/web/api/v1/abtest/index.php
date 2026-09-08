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

$pdo->exec('CREATE TABLE IF NOT EXISTS ab_test (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_key VARCHAR(100) NOT NULL UNIQUE,
    test_name VARCHAR(200) NOT NULL,
    description TEXT,
    variants TEXT,
    weights TEXT,
    min_version VARCHAR(20) DEFAULT "",
    target_platform VARCHAR(20) DEFAULT "all",
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS ab_test_assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_key VARCHAR(100) NOT NULL,
    client_id VARCHAR(200) NOT NULL,
    variant VARCHAR(100) NOT NULL,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_key, client_id)
)');

// 公开接口：获取客户端分配的实验组
if ($method === 'GET' && $action === 'get') {
    handleAbTestGet($pdo);
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
        handleAbTestList($pdo);
    } else {
        handleAbTestList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create') {
        handleAbTestCreate($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true) ?: [];
    $id = (int)($input['id'] ?? 0);
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少ID'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $fields = [];
    $params = [];
    foreach (['test_name', 'description', 'variants', 'weights', 'min_version', 'target_platform'] as $k) {
        if (isset($input[$k])) {
            $fields[] = "$k=:$k";
            $params[":$k"] = $input[$k];
        }
    }
    if (isset($input['is_active'])) {
        $fields[] = 'is_active=:is_active';
        $params[':is_active'] = $input['is_active'] ? 1 : 0;
    }
    if (empty($fields)) {
        echo json_encode(['code' => 1, 'message' => '无更新字段'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $params[':id'] = $id;
    $stmt = $pdo->prepare("UPDATE ab_test SET " . implode(',', $fields) . " WHERE id=:id");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '更新成功'], JSON_UNESCAPED_UNICODE);
    exit;
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleAbTestDelete($pdo, $id);
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

// 按权重随机选择变体
function pickVariantByWeight($variants, $weights) {
    $total = array_sum($weights);
    if ($total <= 0) {
        return $variants[0];
    }
    $rand = mt_rand(1, $total);
    $cumulative = 0;
    foreach ($variants as $i => $variant) {
        $w = $weights[$i] ?? 0;
        $cumulative += $w;
        if ($rand <= $cumulative) {
            return $variant;
        }
    }
    return $variants[count($variants) - 1];
}

// 公开：获取客户端分配的实验组
// 分配逻辑：先查已有分配，没有则按权重随机分配并记录
function handleAbTestGet($pdo) {
    $testKey = $_GET['test_key'] ?? '';
    $clientId = $_GET['client_id'] ?? '';
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';

    if (empty($testKey)) {
        echo json_encode(['code' => 1, 'message' => '缺少实验标识'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (empty($clientId)) {
        echo json_encode(['code' => 1, 'message' => '缺少客户端ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM ab_test WHERE test_key = ? AND is_active = 1");
    $stmt->execute([$testKey]);
    $test = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$test) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'test_key' => $testKey,
                'variant' => null,
                'message' => '实验不存在或未启用'
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    // 版本过滤
    $minVersion = $test['min_version'] ?? '';
    if (!empty($version) && !empty($minVersion) && versionCompare($version, $minVersion) < 0) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'test_key' => $testKey,
                'variant' => null,
                'message' => '版本不满足要求'
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    // 平台过滤
    $targetPlatform = $test['target_platform'] ?? 'all';
    if ($targetPlatform !== 'all' && $targetPlatform !== $platform) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'test_key' => $testKey,
                'variant' => null,
                'message' => '平台不匹配'
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    // 先查已有分配
    $stmt = $pdo->prepare("SELECT variant FROM ab_test_assignment WHERE test_key = ? AND client_id = ?");
    $stmt->execute([$testKey, $clientId]);
    $existing = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($existing) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'test_key' => $testKey,
                'test_name' => $test['test_name'],
                'variant' => $existing['variant'],
                'assigned' => true
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    // 没有则按权重随机分配并记录
    $variants = json_decode($test['variants'] ?? '[]', true);
    if (!is_array($variants) || empty($variants)) {
        echo json_encode(['code' => 1, 'message' => '实验变体配置错误'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $weightsRaw = json_decode($test['weights'] ?? '[]', true);
    $weights = [];
    foreach ($variants as $i => $v) {
        $weights[] = (int)($weightsRaw[$i] ?? 1);
    }

    $selectedVariant = pickVariantByWeight($variants, $weights);

    try {
        $stmt = $pdo->prepare("INSERT INTO ab_test_assignment (test_key, client_id, variant) VALUES (?, ?, ?) ON CONFLICT(test_key, client_id) DO NOTHING");
        $stmt->execute([$testKey, $clientId, $selectedVariant]);
    } catch (\Exception $e) {
        // 忽略并发冲突
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'test_key' => $testKey,
            'test_name' => $test['test_name'],
            'variant' => $selectedVariant,
            'assigned' => false
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleAbTestList($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM ab_test ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // 附带各实验的分配统计
    foreach ($rows as &$row) {
        $stmt = $pdo->prepare("SELECT variant, COUNT(*) as cnt FROM ab_test_assignment WHERE test_key = ? GROUP BY variant");
        $stmt->execute([$row['test_key']]);
        $stats = $stmt->fetchAll(PDO::FETCH_ASSOC);
        $row['assignment_stats'] = $stats;
    }

    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleAbTestCreate($pdo, $input) {
    $testKey = trim($input['test_key'] ?? '');
    $testName = trim($input['test_name'] ?? '');
    $description = trim($input['description'] ?? '');
    $variants = $input['variants'] ?? [];
    $weights = $input['weights'] ?? [];
    $minVersion = trim($input['min_version'] ?? '');
    $targetPlatform = $input['target_platform'] ?? 'all';
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($testKey) || empty($testName)) {
        echo json_encode(['code' => 1, 'message' => '实验标识和名称不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!is_array($variants) || count($variants) < 2) {
        echo json_encode(['code' => 1, 'message' => '至少需要2个变体'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $variantsJson = json_encode($variants, JSON_UNESCAPED_UNICODE);
    // 默认权重为1
    if (empty($weights) || !is_array($weights)) {
        $weights = array_fill(0, count($variants), 1);
    }
    $weightsJson = json_encode($weights, JSON_UNESCAPED_UNICODE);

    try {
        $stmt = $pdo->prepare("INSERT INTO ab_test (test_key, test_name, description, variants, weights, min_version, target_platform, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$testKey, $testName, $description, $variantsJson, $weightsJson, $minVersion, $targetPlatform, $isActive]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '实验创建成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if (strpos($e->getMessage(), 'UNIQUE') !== false) {
            echo json_encode(['code' => 1, 'message' => '该实验标识已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '创建失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handleAbTestDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少实验ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    // 获取 test_key 以清理分配记录
    $stmt = $pdo->prepare('SELECT test_key FROM ab_test WHERE id = ?');
    $stmt->execute([$id]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    $stmt = $pdo->prepare('DELETE FROM ab_test WHERE id = ?');
    $stmt->execute([$id]);

    if ($row) {
        $stmt = $pdo->prepare('DELETE FROM ab_test_assignment WHERE test_key = ?');
        $stmt->execute([$row['test_key']]);
    }

    echo json_encode(['code' => 0, 'message' => '实验已删除'], JSON_UNESCAPED_UNICODE);
}
