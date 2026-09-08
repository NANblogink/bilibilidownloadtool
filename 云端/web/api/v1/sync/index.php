<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Token');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

// Token 认证（兼容 header 与 query 参数）
$token = $_SERVER['HTTP_X_API_TOKEN'] ?? ($_SERVER['HTTP_AUTHORIZATION'] ?? ($_GET['token'] ?? ''));
$token = preg_replace('/^Bearer\s+/i', '', $token);
$configPath = __DIR__ . '/../../../../data/admin_config.php';
if (file_exists($configPath)) { require_once $configPath; }
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

// 允许同步的表及其字段白名单（不含自增 id，导入时重新分配）
$tables = [
    'stat_event'    => ['event_type', 'platform', 'version', 'client_id', 'extra', 'created_at'],
    'stat_error'    => ['client_id', 'version', 'platform', 'error_type', 'error_message', 'stack_trace', 'extra', 'error_line', 'error_file', 'ip_address', 'log_file', 'created_at'],
    'crash_log'     => ['client_id', 'version', 'platform', 'crash_type', 'crash_message', 'stack_trace', 'system_info', 'log_content', 'error_line', 'error_file', 'ip_address', 'is_resolved', 'created_at'],
    'stat_device'   => ['client_id', 'platform', 'version', 'first_seen', 'last_seen'],
    'user_feedback' => ['client_id', 'version', 'platform', 'feedback_type', 'title', 'content', 'contact', 'system_info', 'attachments', 'status', 'created_at'],
];

$action = $_GET['action'] ?? 'export';
$table  = $_GET['table'] ?? '';

if (!isset($tables[$table])) {
    echo json_encode(['code' => 1, 'message' => '无效的表名'], JSON_UNESCAPED_UNICODE);
    exit;
}

$after  = trim($_GET['after'] ?? '');
$limit  = (int)($_GET['limit'] ?? 1000);
if ($limit <= 0 || $limit > 2000) $limit = 1000;
$offset = max(0, (int)($_GET['offset'] ?? 0));

if ($action === 'export') {
    // stat_device 无 created_at，走全量；其余表用 (created_at, id) 双游标，确保不漏不重
    $hasCreated = in_array('created_at', $tables[$table]);

    $fieldList = [];
    foreach ($tables[$table] as $c) { $fieldList[] = '"' . $c . '"'; }

    $params = [];
    if ($hasCreated) {
        $parts = explode('::', $after);
        $afterDate = $parts[0] ?? '';
        $afterId = (isset($parts[1]) && $parts[1] !== '') ? (int)$parts[1] : 0;
        $sql = 'SELECT id, ' . implode(',', $fieldList) . ' FROM "' . $table . '" WHERE 1=1';
        if ($afterDate !== '') {
            $sql .= ' AND (created_at > ? OR (created_at = ? AND id > ?))';
            array_push($params, $afterDate, $afterDate, $afterId);
        }
        $sql .= ' ORDER BY created_at ASC, id ASC LIMIT ' . $limit . ' OFFSET ' . $offset;
    } else {
        // 全量表（stat_device）
        $sql = 'SELECT id, ' . implode(',', $fieldList) . ' FROM "' . $table . '" ORDER BY id ASC LIMIT ' . $limit . ' OFFSET ' . $offset;
    }

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $all = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // 剥离 id（避免导入时主键冲突），下一游标记录 created_at::id
    $rows = [];
    $nextAfter = '';
    foreach ($all as $r) {
        if ($hasCreated) {
            $nextAfter = ($r['created_at'] ?? '') . '::' . (int)$r['id'];
        } else {
            $nextAfter = 'full';
        }
        unset($r['id']);
        $rows[] = $r;
    }

    $hasMore = count($all) === $limit;

    echo json_encode([
        'code' => 0,
        'data' => [
            'table' => $table,
            'after' => $after,
            'rows' => $rows,
            'count' => count($rows),
            'next_after' => $nextAfter,
            'has_more' => $hasMore,
            'offset' => $offset,
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
} else {
    echo json_encode(['code' => 1, 'message' => '无效操作'], JSON_UNESCAPED_UNICODE);
}