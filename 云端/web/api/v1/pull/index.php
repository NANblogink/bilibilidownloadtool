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

// 自动建表（幂等），免去额外迁移脚本
$pdo->exec("CREATE TABLE IF NOT EXISTS log_pull_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    task_code TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    note TEXT DEFAULT '',
    req_ip TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    claimed_at TEXT,
    finished_at TEXT,
    file_path TEXT DEFAULT ''
)");

// 上传目录
$uploadRoot = __DIR__ . '/../../../../uploads/pulled_logs';
if (!is_dir($uploadRoot)) { @mkdir($uploadRoot, 0755, true); }

function json_out($arr) { echo json_encode($arr, JSON_UNESCAPED_UNICODE); exit; }
function now_str() { return date('Y-m-d H:i:s'); }

$action = $_GET['action'] ?? ($_POST['action'] ?? '');

if ($action === 'pending') {
    // 客户端轮询：是否有待执行/进行中的拉取任务
    $clientId = trim($_GET['client_id'] ?? ($_POST['client_id'] ?? ''));
    if ($clientId === '') { json_out(['code' => 1, 'message' => '缺少client_id']); }
    $now = now_str();

    // 清理已过期的未完成任务
    $pdo->prepare("UPDATE log_pull_task SET status='expired' WHERE status IN ('pending','in_progress') AND expires_at < ?")->execute([$now]);

    $stmt = $pdo->prepare("SELECT * FROM log_pull_task WHERE client_id=? AND status IN ('pending','in_progress') ORDER BY id DESC LIMIT 1");
    $stmt->execute([$clientId]);
    $task = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$task) { json_out(['code' => 0, 'data' => ['task' => null]]); }

    // 抢占该任务，防止客户端多实例重复上传
    $pdo->prepare("UPDATE log_pull_task SET status='in_progress', claimed_at=?, req_ip=? WHERE id=?")->execute([$now, $_SERVER['REMOTE_ADDR'] ?? '', $task['id']]);

    json_out(['code' => 0, 'data' => ['task' => [
        'id' => (int)$task['id'],
        'task_code' => $task['task_code'],
        'expires_at' => $task['expires_at'],
        'note' => $task['note'],
    ]]]);
}

if ($action === 'status') {
    // 后台轮询查询结果
    $clientId = trim($_GET['client_id'] ?? ($_POST['client_id'] ?? ''));
    $taskId   = trim($_GET['task_id'] ?? ($_POST['task_id'] ?? ''));
    if ($clientId === '' || $taskId === '') { json_out(['code' => 1, 'message' => '参数缺失']); }
    $stmt = $pdo->prepare("SELECT * FROM log_pull_task WHERE id=? AND client_id=?");
    $stmt->execute([(int)$taskId, $clientId]);
    $task = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$task) { json_out(['code' => 1, 'message' => '任务不存在']); }
    json_out(['code' => 0, 'data' => ['status' => $task['status'], 'file_path' => $task['file_path'], 'finished_at' => $task['finished_at']]]);
}

if ($action === 'upload') {
    // 客户端上传日志文件
    $clientId = trim($_POST['client_id'] ?? '');
    $taskId   = (int)($_POST['task_id'] ?? 0);
    $code     = trim($_POST['code'] ?? '');
    if ($clientId === '' || $taskId <= 0 || $code === '') { json_out(['code' => 1, 'message' => '参数缺失']); }

    $stmt = $pdo->prepare("SELECT * FROM log_pull_task WHERE id=? AND client_id=?");
    $stmt->execute([$taskId, $clientId]);
    $task = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$task) { json_out(['code' => 1, 'message' => '任务不存在']); }
    if ($task['task_code'] !== $code) { json_out(['code' => 1, 'message' => '校验码不匹配']); }
    if (!in_array($task['status'], ['pending', 'in_progress'])) { json_out(['code' => 1, 'message' => '任务状态不可上传']); }

    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        // 允许无文件情况下标记失败，便于定位
        $pdo->prepare("UPDATE log_pull_task SET status='failed', finished_at=? WHERE id=?")->execute([now_str(), $taskId]);
        json_out(['code' => 1, 'message' => '未收到日志文件']);
    }

    $clientDir = $uploadRoot . '/' . preg_replace('/[^A-Za-z0-9_\-]/', '', $clientId);
    if (!is_dir($clientDir)) { @mkdir($clientDir, 0755, true); }
    $fname = $taskId . '_' . date('Ymd_His') . '.log';
    $dest = $clientDir . '/' . $fname;
    if (!move_uploaded_file($_FILES['file']['tmp_name'], $dest)) { json_out(['code' => 1, 'message' => '保存文件失败']); }

    $rel = 'uploads/pulled_logs/' . basename($clientDir) . '/' . $fname;
    $pdo->prepare("UPDATE log_pull_task SET status='completed', file_path=?, finished_at=? WHERE id=?")->execute([$rel, now_str(), $taskId]);

    json_out(['code' => 0, 'data' => ['file_path' => $rel], 'message' => '已收到日志']);
}

json_out(['code' => 1, 'message' => '无效操作']);