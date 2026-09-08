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

$pdo->exec('CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(200) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    platform VARCHAR(20) DEFAULT "",
    feedback_type VARCHAR(20) DEFAULT "other",
    title VARCHAR(200) DEFAULT "",
    content TEXT,
    contact VARCHAR(200) DEFAULT "",
    system_info TEXT,
    attachments TEXT DEFAULT "",
    status VARCHAR(20) DEFAULT "pending",
    admin_reply TEXT,
    replied_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：提交反馈
if ($method === 'POST' && $action === 'submit') {
    handleFeedbackSubmit($pdo);
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
        handleFeedbackStats($pdo);
    } elseif ($action === 'list') {
        handleFeedbackList($pdo);
    } else {
        handleFeedbackList($pdo);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    $putAction = $action ?: ($input['action'] ?? '');
    if ($putAction === 'reply') {
        handleFeedbackReply($pdo, $input);
    } elseif ($putAction === 'status') {
        handleFeedbackStatus($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleFeedbackDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

// 公开：提交反馈
function handleFeedbackSubmit($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;

    $clientId = trim($input['client_id'] ?? '');
    $version = trim($input['version'] ?? '');
    $platform = trim($input['platform'] ?? '');
    $feedbackType = $input['feedback_type'] ?? 'other';
    $title = trim($input['title'] ?? '');
    $content = trim($input['content'] ?? '');
    $contact = trim($input['contact'] ?? '');
    $systemInfo = $input['system_info'] ?? '';
    $attachments = $input['attachments'] ?? '';

    if (empty($title) && empty($content)) {
        echo json_encode(['code' => 1, 'message' => '标题或内容不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($feedbackType, ['bug', 'suggestion', 'question', 'other'])) {
        echo json_encode(['code' => 1, 'message' => '无效的反馈类型'], JSON_UNESCAPED_UNICODE);
        return;
    }

    if (!is_string($systemInfo)) {
        $systemInfo = json_encode($systemInfo, JSON_UNESCAPED_UNICODE);
    }
    if (!is_string($attachments)) {
        $attachments = json_encode($attachments, JSON_UNESCAPED_UNICODE);
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO user_feedback (client_id, version, platform, feedback_type, title, content, contact, system_info, attachments, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')");
        $stmt->execute([$clientId, $version, $platform, $feedbackType, $title, $content, $contact, $systemInfo, $attachments]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '反馈提交成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '提交失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleFeedbackList($pdo) {
    $status = $_GET['status'] ?? '';
    $type = $_GET['type'] ?? '';
    $limit = (int)($_GET['limit'] ?? 100);
    if ($limit <= 0 || $limit > 1000) $limit = 100;

    $sql = 'SELECT * FROM user_feedback WHERE 1=1';
    $params = [];
    if ($status !== '') {
        $sql .= ' AND status = ?';
        $params[] = $status;
    }
    if ($type !== '') {
        $sql .= ' AND feedback_type = ?';
        $params[] = $type;
    }
    $sql .= ' ORDER BY created_at DESC LIMIT ' . $limit;

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleFeedbackStats($pdo) {
    $stats = [];

    $stmt = $pdo->query('SELECT COUNT(*) as total FROM user_feedback');
    $stats['total'] = (int)$stmt->fetchColumn();

    $stmt = $pdo->query('SELECT COUNT(*) as pending FROM user_feedback WHERE status = "pending"');
    $stats['pending'] = (int)$stmt->fetchColumn();

    $stmt = $pdo->query('SELECT COUNT(*) as replied FROM user_feedback WHERE status = "replied"');
    $stats['replied'] = (int)$stmt->fetchColumn();

    $stmt = $pdo->query('SELECT COUNT(*) as resolved FROM user_feedback WHERE status = "resolved"');
    $stats['resolved'] = (int)$stmt->fetchColumn();

    $stmt = $pdo->query('SELECT COUNT(*) as closed FROM user_feedback WHERE status = "closed"');
    $stats['closed'] = (int)$stmt->fetchColumn();

    // 按类型统计
    $stmt = $pdo->query('SELECT feedback_type, COUNT(*) as cnt FROM user_feedback GROUP BY feedback_type ORDER BY cnt DESC');
    $stats['by_type'] = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // 按版本统计
    $stmt = $pdo->query('SELECT version, COUNT(*) as cnt FROM user_feedback GROUP BY version ORDER BY cnt DESC LIMIT 20');
    $stats['by_version'] = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['code' => 0, 'data' => $stats, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleFeedbackReply($pdo, $input) {
    $id = $input['id'] ?? null;
    $adminReply = trim($input['admin_reply'] ?? '');

    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少反馈ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (empty($adminReply)) {
        echo json_encode(['code' => 1, 'message' => '回复内容不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $now = date('Y-m-d H:i:s');
    $stmt = $pdo->prepare("UPDATE user_feedback SET admin_reply = ?, replied_at = ?, status = 'replied' WHERE id = ?");
    $stmt->execute([$adminReply, $now, $id]);
    echo json_encode(['code' => 0, 'message' => '回复成功'], JSON_UNESCAPED_UNICODE);
}

function handleFeedbackStatus($pdo, $input) {
    $id = $input['id'] ?? null;
    $status = $input['status'] ?? '';

    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少反馈ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (!in_array($status, ['pending', 'replied', 'resolved', 'closed'])) {
        echo json_encode(['code' => 1, 'message' => '无效的状态'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare('UPDATE user_feedback SET status = ? WHERE id = ?');
    $stmt->execute([$status, $id]);
    echo json_encode(['code' => 0, 'message' => '状态更新成功'], JSON_UNESCAPED_UNICODE);
}

function handleFeedbackDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少反馈ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM user_feedback WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '反馈已删除'], JSON_UNESCAPED_UNICODE);
}
