<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Token');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
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

$pdo->exec('CREATE TABLE IF NOT EXISTS stat_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type VARCHAR(50) NOT NULL,
    platform VARCHAR(10) DEFAULT "windows",
    version VARCHAR(20) DEFAULT "",
    client_id VARCHAR(64) DEFAULT "",
    extra TEXT DEFAULT "",
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_type ON stat_event(event_type)');
$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_created ON stat_event(created_at)');
$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_client ON stat_event(client_id)');

$pdo->exec('CREATE TABLE IF NOT EXISTS stat_daily (
    date DATE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    platform VARCHAR(10) DEFAULT "windows",
    count INT DEFAULT 0,
    unique_count INT DEFAULT 0,
    PRIMARY KEY (date, event_type, platform)
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS stat_device (
    client_id VARCHAR(64) PRIMARY KEY,
    platform VARCHAR(10) DEFAULT "windows",
    version VARCHAR(20) DEFAULT "",
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
)');

try { $pdo->exec('ALTER TABLE stat_device ADD COLUMN version VARCHAR(20) DEFAULT ""'); } catch (\Exception $e) {}

$pdo->exec('CREATE TABLE IF NOT EXISTS stat_error (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(64) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    platform VARCHAR(10) DEFAULT "windows",
    error_type VARCHAR(100) DEFAULT "",
    error_message TEXT,
    stack_trace TEXT,
    extra TEXT DEFAULT "",
    error_line INTEGER DEFAULT 0,
    error_file VARCHAR(500) DEFAULT "",
    ip_address VARCHAR(45) DEFAULT "",
    log_file VARCHAR(500) DEFAULT "",
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_type ON stat_error(error_type)');
$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_created ON stat_error(created_at)');
$pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_client ON stat_error(client_id)');

// 兼容旧数据库：补充新增字段
foreach (['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""', 'log_file' => 'VARCHAR(500) DEFAULT ""'] as $col => $def) {
    try { $pdo->exec("ALTER TABLE stat_error ADD COLUMN $col $def"); } catch (\Exception $e) {}
}

$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

if ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$action && !empty($input['action'])) {
        $action = $input['action'];
    }
}

if ($method === 'POST' && $action === 'report') {
    handleReport($pdo);
    exit;
}

if ($method === 'POST' && $action === 'error') {
    handleErrorReport($pdo);
    exit;
}

if ($method === 'POST' && $action === 'report_error') {
    handleErrorReport($pdo);
    exit;
}

$token = $_SERVER['HTTP_X_API_TOKEN'] ?? $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = preg_replace('/^Bearer\s+/i', '', $token);

$configPath = __DIR__ . '/../../../../data/admin_config.php';
if (file_exists($configPath)) {
    require_once $configPath;
}
$validToken = defined('API_TOKEN') ? API_TOKEN : '';

if ($token !== $validToken) {
    http_response_code(401);
    echo json_encode(['code' => 1, 'message' => '认证失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

switch ($action) {
    case 'device':
        handleDeviceLogs($pdo);
        break;
    case 'overview':
        handleOverview($pdo);
        break;
    case 'trend':
        handleTrend($pdo);
        break;
    case 'recent':
        handleRecent($pdo);
        break;
    case 'errors':
        handleErrors($pdo);
        break;
    case 'retention':
        handleRetention($pdo);
        break;
    default:
        handleOverview($pdo);
}

function handleReport($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        echo json_encode(['code' => 1, 'message' => '无效请求数据'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $eventType = trim($input['event'] ?? '');
    $platform = trim($input['platform'] ?? 'windows');
    $version = trim($input['version'] ?? '');
    $clientId = trim($input['client_id'] ?? '');
    $extra = $input['extra'] ?? '';

    $validEvents = ['install', 'launch', 'parse_video', 'download_video',
                    'live_watch', 'live_record', 'audio_parse', 'emoji_download'];
    if (!in_array($eventType, $validEvents)) {
        echo json_encode(['code' => 1, 'message' => '无效的事件类型'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    if (empty($clientId)) {
        $clientId = md5(($input['machine_id'] ?? '') . ($input['hostname'] ?? '') . time());
    }

    date_default_timezone_set('Asia/Shanghai');
    $today = date('Y-m-d');
    $now = date('Y-m-d H:i:s');

    try {
        $pdo->beginTransaction();

        $stmt = $pdo->prepare('INSERT INTO stat_event (event_type, platform, version, client_id, extra) VALUES (?, ?, ?, ?, ?)');
        $stmt->execute([$eventType, $platform, $version, $clientId, is_string($extra) ? $extra : json_encode($extra, JSON_UNESCAPED_UNICODE)]);

        $stmt = $pdo->prepare('INSERT INTO stat_daily (date, event_type, platform, count, unique_count) VALUES (?, ?, ?, 1, 1) ON CONFLICT(date, event_type, platform) DO UPDATE SET count = count + 1');
        $stmt->execute([$today, $eventType, $platform]);

        $stmt = $pdo->prepare('INSERT INTO stat_device (client_id, platform, version, first_seen, last_seen) VALUES (?, ?, ?, ?, ?) ON CONFLICT(client_id) DO UPDATE SET last_seen = ?, platform = ?, version = ?');
        $stmt->execute([$clientId, $platform, $version, $now, $now, $now, $platform, $version]);

        if ($eventType === 'launch') {
            $stmt = $pdo->prepare('SELECT COUNT(*) FROM stat_daily WHERE date = ? AND event_type = ? AND platform = ?');
            $stmt->execute([$today, 'launch', $platform]);

            $stmt2 = $pdo->prepare('SELECT COUNT(DISTINCT client_id) FROM stat_event WHERE event_type = ? AND platform = ? AND date(created_at) = ?');
            $stmt2->execute(['launch', $platform, $today]);
            $uniqueCount = (int)$stmt2->fetchColumn();

            $stmt3 = $pdo->prepare('UPDATE stat_daily SET unique_count = ? WHERE date = ? AND event_type = ? AND platform = ?');
            $stmt3->execute([$uniqueCount, $today, 'launch', $platform]);
        }

        $pdo->commit();

        echo json_encode(['code' => 0, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        $pdo->rollBack();
        echo json_encode(['code' => 1, 'message' => '上报失败'], JSON_UNESCAPED_UNICODE);
    }
}

function handleOverview($pdo) {
    date_default_timezone_set('Asia/Shanghai');
    $today = date('Y-m-d');

    $totalInstalls = $pdo->query("SELECT COUNT(*) FROM stat_device")->fetchColumn();
    $todayInstalls = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='install' AND date=?");
    $todayInstalls->execute([$today]);
    $todayInstalls = (int)$todayInstalls->fetchColumn();

    $totalLaunches = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='launch'")->fetchColumn();
    $todayLaunches = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='launch' AND date=?");
    $todayLaunches->execute([$today]);
    $todayLaunches = (int)$todayLaunches->fetchColumn();

    $todayActiveUsers = $pdo->prepare("SELECT COUNT(DISTINCT client_id) FROM stat_event WHERE event_type='launch' AND date(created_at)=?");
    $todayActiveUsers->execute([$today]);
    $todayActiveUsers = (int)$todayActiveUsers->fetchColumn();

    $totalParses = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='parse_video'")->fetchColumn();
    $todayParses = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='parse_video' AND date=?");
    $todayParses->execute([$today]);
    $todayParses = (int)$todayParses->fetchColumn();

    $totalDownloads = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='download_video'")->fetchColumn();
    $todayDownloads = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='download_video' AND date=?");
    $todayDownloads->execute([$today]);
    $todayDownloads = (int)$todayDownloads->fetchColumn();

    $platformDist = $pdo->query("SELECT platform, COUNT(*) as count FROM stat_device GROUP BY platform ORDER BY count DESC")->fetchAll(PDO::FETCH_ASSOC);

    $versionDist = $pdo->query("SELECT version, COUNT(*) as count FROM stat_device WHERE version != '' GROUP BY version ORDER BY count DESC LIMIT 10")->fetchAll(PDO::FETCH_ASSOC);

    $totalErrors = $pdo->query("SELECT COUNT(*) FROM stat_error")->fetchColumn();
    $todayErrors = $pdo->prepare("SELECT COUNT(*) FROM stat_error WHERE date(created_at)=?");
    $todayErrors->execute([$today]);
    $todayErrors = (int)$todayErrors->fetchColumn();

    $totalLiveWatch = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_watch'")->fetchColumn();
    $todayLiveWatch = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_watch' AND date=?");
    $todayLiveWatch->execute([$today]);
    $todayLiveWatch = (int)$todayLiveWatch->fetchColumn();

    $totalLiveRecord = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_record'")->fetchColumn();
    $todayLiveRecord = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_record' AND date=?");
    $todayLiveRecord->execute([$today]);
    $todayLiveRecord = (int)$todayLiveRecord->fetchColumn();

    $totalAudioParse = $pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='audio_parse'")->fetchColumn();
    $todayAudioParse = $pdo->prepare("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='audio_parse' AND date=?");
    $todayAudioParse->execute([$today]);
    $todayAudioParse = (int)$todayAudioParse->fetchColumn();

    echo json_encode([
        'code' => 0,
        'data' => [
            'total_installs' => (int)$totalInstalls,
            'today_installs' => $todayInstalls,
            'total_launches' => (int)$totalLaunches,
            'today_launches' => $todayLaunches,
            'today_active_users' => $todayActiveUsers,
            'total_parses' => (int)$totalParses,
            'today_parses' => $todayParses,
            'total_downloads' => (int)$totalDownloads,
            'today_downloads' => $todayDownloads,
            'total_errors' => (int)$totalErrors,
            'today_errors' => $todayErrors,
            'total_live_watch' => (int)$totalLiveWatch,
            'today_live_watch' => $todayLiveWatch,
            'total_live_record' => (int)$totalLiveRecord,
            'today_live_record' => $todayLiveRecord,
            'total_audio_parse' => (int)$totalAudioParse,
            'today_audio_parse' => $todayAudioParse,
            'platform_distribution' => $platformDist,
            'version_distribution' => $versionDist
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleDeviceLogs($pdo) {
    $clientId = trim($_GET['client_id'] ?? $_POST['client_id'] ?? '');
    if (empty($clientId)) {
        echo json_encode(['code' => 1, 'message' => '缺少设备码(client_id)'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $limit = min(5000, max(1, (int)($_GET['limit'] ?? 500)));
    $offset = max(0, (int)($_GET['offset'] ?? 0));

    // 设备信息
    $deviceStmt = $pdo->prepare('SELECT * FROM stat_device WHERE client_id = ?');
    $deviceStmt->execute([$clientId]);
    $device = $deviceStmt->fetch(PDO::FETCH_ASSOC);

    // 错误日志（含行号/文件/IP/日志文件路径）
    $errCountStmt = $pdo->prepare('SELECT COUNT(*) FROM stat_error WHERE client_id = ?');
    $errCountStmt->execute([$clientId]);
    $errorTotal = (int)$errCountStmt->fetchColumn();

    $errStmt = $pdo->prepare('SELECT * FROM stat_error WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $errStmt->execute([$clientId, $limit, $offset]);
    $errors = $errStmt->fetchAll(PDO::FETCH_ASSOC);

    // 事件日志
    $evtCountStmt = $pdo->prepare('SELECT COUNT(*) FROM stat_event WHERE client_id = ?');
    $evtCountStmt->execute([$clientId]);
    $eventTotal = (int)$evtCountStmt->fetchColumn();

    $evtStmt = $pdo->prepare('SELECT * FROM stat_event WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $evtStmt->execute([$clientId, $limit, $offset]);
    $events = $evtStmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => [
            'device' => $device,
            'errors' => ['items' => $errors, 'total' => $errorTotal, 'limit' => $limit, 'offset' => $offset],
            'events' => ['items' => $events, 'total' => $eventTotal, 'limit' => $limit, 'offset' => $offset],
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleTrend($pdo) {
    $days = min(30, max(1, (int)($_GET['days'] ?? 7)));
    $eventType = $_GET['event_type'] ?? 'launch';

    $validTypes = ['install', 'launch', 'parse_video', 'download_video',
                   'live_watch', 'live_record', 'audio_parse', 'emoji_download'];
    if (!in_array($eventType, $validTypes)) {
        $eventType = 'launch';
    }

    $stmt = $pdo->prepare("SELECT date, IFNULL(SUM(count),0) as count, IFNULL(SUM(unique_count),0) as unique_count FROM stat_daily WHERE event_type = ? AND date >= date('now', ?) GROUP BY date ORDER BY date ASC");
    $stmt->execute([$eventType, "-{$days} days"]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => $rows,
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleRecent($pdo) {
    $limit = min(100, max(1, (int)($_GET['limit'] ?? 20)));
    $eventType = $_GET['event_type'] ?? '';

    $sql = 'SELECT * FROM stat_event';
    $params = [];

    if ($eventType && in_array($eventType, ['install', 'launch', 'parse_video', 'download_video',
                                         'live_watch', 'live_record', 'audio_parse', 'emoji_download'])) {
        $sql .= ' WHERE event_type = ?';
        $params[] = $eventType;
    }

    $sql .= ' ORDER BY created_at DESC LIMIT ?';
    $params[] = $limit;

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => $rows,
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleErrorReport($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        echo json_encode(['code' => 1, 'message' => '无效请求数据'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $clientId = trim($input['client_id'] ?? '');
    $version = trim($input['version'] ?? '');
    $platform = trim($input['platform'] ?? 'windows');
    $errorType = trim($input['error_type'] ?? '');
    $errorMessage = $input['error_message'] ?? '';
    $stackTrace = $input['stack_trace'] ?? '';
    $extra = $input['extra'] ?? '';
    $errorLine = (int)($input['error_line'] ?? 0);
    $errorFile = trim($input['error_file'] ?? '');
    $ipAddress = trim($input['ip_address'] ?? ($_SERVER['REMOTE_ADDR'] ?? ($_SERVER['HTTP_X_FORWARDED_FOR'] ?? '')));
    $logContent = $input['log_content'] ?? '';

    // 保存日志文件到 uploads/errorlogs/
    $logFilePath = '';
    if (!empty($logContent)) {
        $uploadDir = __DIR__ . '/../../../uploads/errorlogs/';
        if (!is_dir($uploadDir)) {
            mkdir($uploadDir, 0755, true);
        }
        $safeClientId = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $clientId);
        $fileName = 'error_' . $safeClientId . '_' . date('Ymd_His') . '_' . substr(md5(uniqid()), 0, 6) . '.log';
        $destPath = $uploadDir . $fileName;
        if (file_put_contents($destPath, $logContent) !== false) {
            $logFilePath = 'uploads/errorlogs/' . $fileName;
        }
    }

    try {
        $stmt = $pdo->prepare('INSERT INTO stat_error (client_id, version, platform, error_type, error_message, stack_trace, extra, error_line, error_file, ip_address, log_file) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        $stmt->execute([
            $clientId, $version, $platform, $errorType, $errorMessage, $stackTrace,
            is_string($extra) ? $extra : json_encode($extra, JSON_UNESCAPED_UNICODE),
            $errorLine, $errorFile, $ipAddress, $logFilePath
        ]);
        $errorId = $pdo->lastInsertId();
        echo json_encode(['code' => 0, 'data' => ['id' => $errorId, 'log_file' => $logFilePath], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        echo json_encode(['code' => 1, 'message' => '上报失败: ' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleErrors($pdo) {
    $limit = min(5000, max(1, (int)($_GET['limit'] ?? 500)));
    $offset = max(0, (int)($_GET['offset'] ?? 0));
    $errorType = $_GET['error_type'] ?? '';
    $clientId = $_GET['client_id'] ?? '';
    $version = $_GET['version'] ?? '';
    $dateFrom = $_GET['date_from'] ?? '';
    $dateTo = $_GET['date_to'] ?? '';

    $sql = 'SELECT * FROM stat_error WHERE 1=1';
    $params = [];

    if ($errorType !== '') {
        $sql .= ' AND error_type = ?';
        $params[] = $errorType;
    }
    if ($clientId !== '') {
        $sql .= ' AND client_id = ?';
        $params[] = $clientId;
    }
    if ($version !== '') {
        $sql .= ' AND version = ?';
        $params[] = $version;
    }
    if ($dateFrom !== '') {
        $sql .= ' AND created_at >= ?';
        $params[] = $dateFrom;
    }
    if ($dateTo !== '') {
        $sql .= ' AND created_at <= ?';
        $params[] = $dateTo . ' 23:59:59';
    }

    $countSql = str_replace('SELECT *', 'SELECT COUNT(*) as total', $sql);
    $countStmt = $pdo->prepare($countSql);
    $countStmt->execute($params);
    $total = (int)$countStmt->fetchColumn();

    $sql .= ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
    $params[] = $limit;
    $params[] = $offset;

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'code' => 0,
        'data' => [
            'items' => $rows,
            'total' => $total,
            'limit' => $limit,
            'offset' => $offset,
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleRetention($pdo) {
    $days = min(30, max(1, (int)($_GET['days'] ?? 7)));
    date_default_timezone_set('Asia/Shanghai');
    $today = date('Y-m-d');
    $retentionData = [];

    for ($i = 0; $i < $days; $i++) {
        $day = date('Y-m-d', strtotime("-$i days", strtotime($today)));

        $newUsers = $pdo->prepare("SELECT COUNT(DISTINCT client_id) FROM stat_device WHERE date(first_seen) = ?");
        $newUsers->execute([$day]);
        $newUsersCount = (int)$newUsers->fetchColumn();

        $retained1d = 0;
        $retained3d = 0;
        $retained7d = 0;

        if ($newUsersCount > 0) {
            $day1 = date('Y-m-d', strtotime('+1 day', strtotime($day)));
            $day3 = date('Y-m-d', strtotime('+3 days', strtotime($day)));
            $day7 = date('Y-m-d', strtotime('+7 days', strtotime($day)));

            $stmt1 = $pdo->prepare("SELECT COUNT(DISTINCT e.client_id) FROM stat_event e INNER JOIN stat_device d ON e.client_id = d.client_id WHERE date(d.first_seen) = ? AND date(e.created_at) = ? AND e.event_type = 'launch'");
            $stmt1->execute([$day, $day1]);
            $retained1d = (int)$stmt1->fetchColumn();

            $stmt3 = $pdo->prepare("SELECT COUNT(DISTINCT e.client_id) FROM stat_event e INNER JOIN stat_device d ON e.client_id = d.client_id WHERE date(d.first_seen) = ? AND date(e.created_at) = ? AND e.event_type = 'launch'");
            $stmt3->execute([$day, $day3]);
            $retained3d = (int)$stmt3->fetchColumn();

            $stmt7 = $pdo->prepare("SELECT COUNT(DISTINCT e.client_id) FROM stat_event e INNER JOIN stat_device d ON e.client_id = d.client_id WHERE date(d.first_seen) = ? AND date(e.created_at) = ? AND e.event_type = 'launch'");
            $stmt7->execute([$day, $day7]);
            $retained7d = (int)$stmt7->fetchColumn();
        }

        $retentionData[] = [
            'date' => $day,
            'new_users' => $newUsersCount,
            'retention_1d' => $newUsersCount > 0 ? round($retained1d / $newUsersCount * 100, 2) : 0,
            'retention_3d' => $newUsersCount > 0 ? round($retained3d / $newUsersCount * 100, 2) : 0,
            'retention_7d' => $newUsersCount > 0 ? round($retained7d / $newUsersCount * 100, 2) : 0,
        ];
    }

    echo json_encode([
        'code' => 0,
        'data' => array_reverse($retentionData),
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}