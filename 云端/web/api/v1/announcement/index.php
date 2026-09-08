<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');

$version = $_GET['version'] ?? '';
$platform = $_GET['platform'] ?? '';

try {
    $dbPath = __DIR__ . '/../../../../data/bilidown.db';
    if (!file_exists($dbPath)) {
        echo json_encode(['code' => 0, 'data' => ['has_announcement' => false, 'announcements' => []], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    date_default_timezone_set('Asia/Shanghai');
    $now = date('Y-m-d H:i:s');

    $stmt = $pdo->prepare('SELECT * FROM announcement WHERE is_active = 1 AND start_time <= :now AND end_time >= :now ORDER BY created_at DESC');
    $stmt->execute([':now' => $now]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $announcements = [];
    foreach ($rows as $row) {
        $minVersion = $row['min_version'] ?? '';
        $maxVersion = $row['max_version'] ?? '';

        if (!empty($version) && !empty($minVersion) && versionCompare($version, $minVersion) < 0) {
            continue;
        }
        if (!empty($version) && !empty($maxVersion) && versionCompare($version, $maxVersion) > 0) {
            continue;
        }

        $startTime = '';
        if (!empty($row['start_time'])) {
            $ts = strtotime($row['start_time']);
            if ($ts !== false) {
                $startTime = date('Y-m-d\TH:i:sP', $ts);
            }
        }

        $endTime = '';
        if (!empty($row['end_time'])) {
            $ts = strtotime($row['end_time']);
            if ($ts !== false) {
                $endTime = date('Y-m-d\TH:i:sP', $ts);
            }
        }

        $actionUrl = $row['action_url'] ?? '';
        if (!empty($actionUrl) && $actionUrl[0] === '/') {
            $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
            $actionUrl = $scheme . '://' . $host . $actionUrl;
        }

        $announcements[] = [
            'id' => $row['id'],
            'type' => $row['type'] ?? 'info',
            'title' => $row['title'] ?? '',
            'content' => $row['content'] ?? '',
            'start_time' => $startTime,
            'end_time' => $endTime,
            'action' => [
                'type' => $row['action_type'] ?? 'none',
                'url' => $actionUrl
            ],
            'dismissible' => isset($row['dismissible']) ? (bool)$row['dismissible'] : true,
            'min_version' => $minVersion,
            'max_version' => $maxVersion
        ];
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'has_announcement' => !empty($announcements),
            'announcements' => $announcements
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
    exit;

} catch (\Exception $e) {
    echo json_encode([
        'code' => 1,
        'data' => null,
        'message' => '服务器内部错误'
    ], JSON_UNESCAPED_UNICODE);
    exit;
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
