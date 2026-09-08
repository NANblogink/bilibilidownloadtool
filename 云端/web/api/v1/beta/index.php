<?php
/**
 * 内测授权管理 API
 *
 * 公开接口：
 *   GET ?action=check&client_id=xxx          检查设备码是否在内测名单（旧版设备码通道）
 *   GET ?action=auth&client_id=xxx&qq=xxx    QQ号授权验证（内测包启动时调用）
 *
 * Token 保护接口（需 X-API-Token 头）：
 *   GET  ?action=qq_list                     获取授权QQ列表
 *   POST action=add_qq    qq, remark         添加授权QQ
 *   POST action=remove_qq  id                删除授权QQ
 *   GET  ?action=bind_list                   获取设备绑定列表
 *   POST action=unbind    id                 解绑设备
 */
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Token');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$configPath = __DIR__ . '/../../../../data/admin_config.php';
if (file_exists($configPath)) {
    require_once $configPath;
}
$validToken = defined('API_TOKEN') ? API_TOKEN : '';

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

// 建表
$pdo->exec('CREATE TABLE IF NOT EXISTS beta_tester (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(64) NOT NULL UNIQUE,
    device_name VARCHAR(100) DEFAULT "",
    platform VARCHAR(10) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS beta_qq_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qq_number VARCHAR(20) NOT NULL UNIQUE,
    remark VARCHAR(100) DEFAULT "",
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS beta_device_bind (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qq_number VARCHAR(20) NOT NULL UNIQUE,
    client_id VARCHAR(64) NOT NULL UNIQUE,
    platform VARCHAR(10) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    bind_ip VARCHAR(45) DEFAULT "",
    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS beta_auth_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(64) DEFAULT "",
    qq_number VARCHAR(20) DEFAULT "",
    ip VARCHAR(45) DEFAULT "",
    success BOOLEAN DEFAULT 0,
    fail_reason VARCHAR(50) DEFAULT "",
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';
$ip = $_SERVER['REMOTE_ADDR'] ?? '';

// ============ 公开接口 ============

// 检查设备码是否在内测名单（旧版设备码通道，供 check/index.php 调用）
if ($method === 'GET' && $action === 'check') {
    $clientId = $_GET['client_id'] ?? '';
    if (empty($clientId)) {
        echo json_encode(['code' => 0, 'data' => ['is_beta_tester' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    // 先查 QQ 绑定表
    $stmt = $pdo->prepare('SELECT id FROM beta_device_bind WHERE client_id = ?');
    $stmt->execute([$clientId]);
    if ($stmt->fetch() !== false) {
        echo json_encode(['code' => 0, 'data' => ['is_beta_tester' => true], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    // 再查旧版设备码表
    $stmt = $pdo->prepare('SELECT id FROM beta_tester WHERE client_id = ?');
    $stmt->execute([$clientId]);
    $isBeta = $stmt->fetch() !== false;
    echo json_encode(['code' => 0, 'data' => ['is_beta_tester' => $isBeta], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
    exit;
}

// QQ号授权验证（内测包启动时调用）
if ($method === 'GET' && $action === 'auth') {
    $clientId = trim($_GET['client_id'] ?? '');
    $qq = trim($_GET['qq'] ?? '');
    $platform = $_GET['platform'] ?? '';
    $version = $_GET['version'] ?? '';

    if (empty($clientId)) {
        echo json_encode(['code' => 0, 'data' => ['authorized' => false, 'reason' => 'no_client_id'], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 1. 防爆破冷却检查
    $failStmt = $pdo->prepare("
        SELECT COUNT(*) as cnt FROM beta_auth_log
        WHERE (client_id = ? OR ip = ?) AND success = 0
          AND created_at > datetime('now', '-1 hour')
    ");
    $failStmt->execute([$clientId, $ip]);
    $failCount = (int)$failStmt->fetchColumn();

    $cooldownSeconds = 0;
    if ($failCount >= 10) $cooldownSeconds = 86400;
    else if ($failCount >= 7) $cooldownSeconds = 1800;
    else if ($failCount >= 4) $cooldownSeconds = 300;

    if ($cooldownSeconds > 0) {
        $lastStmt = $pdo->prepare("
            SELECT created_at FROM beta_auth_log
            WHERE (client_id = ? OR ip = ?) AND success = 0
            ORDER BY created_at DESC LIMIT 1
        ");
        $lastStmt->execute([$clientId, $ip]);
        $lastTime = strtotime($lastStmt->fetchColumn());
        $remaining = $cooldownSeconds - (time() - $lastTime);
        if ($remaining > 0) {
            logAuth($pdo, $clientId, $qq, $ip, 0, 'cooldown');
            echo json_encode([
                'code' => 0,
                'data' => [
                    'authorized' => false,
                    'reason' => 'cooldown',
                    'cooldown_remaining' => $remaining
                ],
                'message' => 'success'
            ], JSON_UNESCAPED_UNICODE);
            exit;
        }
    }

    // 2. 检查该设备码是否已绑定（已绑定直接放行）
    $bindStmt = $pdo->prepare('SELECT * FROM beta_device_bind WHERE client_id = ?');
    $bindStmt->execute([$clientId]);
    $bind = $bindStmt->fetch(PDO::FETCH_ASSOC);
    if ($bind) {
        // 更新活跃时间
        $upd = $pdo->prepare('UPDATE beta_device_bind SET last_active = CURRENT_TIMESTAMP WHERE client_id = ?');
        $upd->execute([$clientId]);
        logAuth($pdo, $clientId, $bind['qq_number'], $ip, 1, '');
        echo json_encode([
            'code' => 0,
            'data' => ['authorized' => true, 'qq_number' => $bind['qq_number'], 'is_new_bind' => false],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 3. 未绑定 → 需要QQ号验证
    if (empty($qq)) {
        echo json_encode([
            'code' => 0,
            'data' => ['authorized' => false, 'reason' => 'need_qq_input'],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 3a. QQ号是否在授权名单
    $qqStmt = $pdo->prepare('SELECT * FROM beta_qq_auth WHERE qq_number = ? AND is_active = 1');
    $qqStmt->execute([$qq]);
    $qqAuth = $qqStmt->fetch(PDO::FETCH_ASSOC);
    if (!$qqAuth) {
        logAuth($pdo, $clientId, $qq, $ip, 0, 'qq_not_authorized');
        echo json_encode([
            'code' => 0,
            'data' => ['authorized' => false, 'reason' => 'qq_not_authorized'],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 3b. QQ号是否已绑定其他设备
    $existStmt = $pdo->prepare('SELECT * FROM beta_device_bind WHERE qq_number = ? AND client_id != ?');
    $existStmt->execute([$qq, $clientId]);
    if ($existStmt->fetch()) {
        logAuth($pdo, $clientId, $qq, $ip, 0, 'qq_already_bound');
        echo json_encode([
            'code' => 0,
            'data' => ['authorized' => false, 'reason' => 'qq_already_bound'],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 4. 绑定
    $insertStmt = $pdo->prepare('
        INSERT OR REPLACE INTO beta_device_bind (qq_number, client_id, platform, version, bind_ip, bound_at, last_active)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ');
    $insertStmt->execute([$qq, $clientId, $platform, $version, $ip]);
    logAuth($pdo, $clientId, $qq, $ip, 1, '');
    echo json_encode([
        'code' => 0,
        'data' => ['authorized' => true, 'qq_number' => $qq, 'is_new_bind' => true],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

// ============ 以下接口需要 Token 认证 ============
$token = $_SERVER['HTTP_X_API_TOKEN'] ?? $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = preg_replace('/^Bearer\s+/i', '', $token);

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

// 授权QQ列表
if ($method === 'GET' && $action === 'qq_list') {
    $rows = $pdo->query('SELECT * FROM beta_qq_auth ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
    exit;
}

// 设备绑定列表
if ($method === 'GET' && $action === 'bind_list') {
    $rows = $pdo->query('SELECT * FROM beta_device_bind ORDER BY bound_at DESC')->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
    exit;
}

// POST 操作
if ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');

    // 添加授权QQ
    if ($postAction === 'add_qq') {
        $qq = trim($input['qq'] ?? '');
        $remark = trim($input['remark'] ?? '');
        if (empty($qq)) {
            echo json_encode(['code' => 1, 'message' => 'QQ号不能为空'], JSON_UNESCAPED_UNICODE);
            exit;
        }
        try {
            $stmt = $pdo->prepare('INSERT OR IGNORE INTO beta_qq_auth (qq_number, remark) VALUES (?, ?)');
            $stmt->execute([$qq, $remark]);
            $affected = $stmt->rowCount();
            echo json_encode([
                'code' => 0,
                'message' => $affected > 0 ? '授权QQ添加成功' : '该QQ号已在授权名单中'
            ], JSON_UNESCAPED_UNICODE);
        } catch (PDOException $e) {
            echo json_encode(['code' => 1, 'message' => '添加失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
        exit;
    }

    // 删除授权QQ
    if ($postAction === 'remove_qq') {
        $id = (int)($input['id'] ?? 0);
        if (!$id) {
            echo json_encode(['code' => 1, 'message' => '缺少ID'], JSON_UNESCAPED_UNICODE);
            exit;
        }
        $stmt = $pdo->prepare('DELETE FROM beta_qq_auth WHERE id = ?');
        $stmt->execute([$id]);
        echo json_encode(['code' => 0, 'message' => '授权QQ已删除'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 解绑设备
    if ($postAction === 'unbind') {
        $id = (int)($input['id'] ?? 0);
        if (!$id) {
            echo json_encode(['code' => 1, 'message' => '缺少设备绑定ID'], JSON_UNESCAPED_UNICODE);
            exit;
        }
        $stmt = $pdo->prepare('DELETE FROM beta_device_bind WHERE id = ?');
        $stmt->execute([$id]);
        echo json_encode(['code' => 0, 'message' => '设备已解绑'], JSON_UNESCAPED_UNICODE);
        exit;
    }
}

echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);

function logAuth($pdo, $clientId, $qq, $ip, $success, $reason) {
    try {
        $stmt = $pdo->prepare('INSERT INTO beta_auth_log (client_id, qq_number, ip, success, fail_reason) VALUES (?, ?, ?, ?, ?)');
        $stmt->execute([$clientId, $qq, $ip, $success ? 1 : 0, $reason]);
    } catch (\Exception $e) {
        // 日志写入失败不影响主流程
    }
}
