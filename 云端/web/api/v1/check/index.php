<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');

$version = $_GET['version'] ?? '';
$platform = $_GET['platform'] ?? 'windows';
$channel = $_GET['channel'] ?? 'stable';
$clientId = $_GET['client_id'] ?? '';

if (empty($version)) {
    echo json_encode(['code' => 1, 'data' => null, 'message' => '缺少version参数'], JSON_UNESCAPED_UNICODE);
    exit;
}

try {
    $dbPath = __DIR__ . '/../../../../data/bilidown.db';
    if (!file_exists($dbPath)) {
        echo json_encode(['code' => 0, 'data' => ['has_update' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // 检查设备是否在内测名单中，是则自动切换到 beta 通道
    if (!empty($clientId)) {
        try {
            $pdo->exec('CREATE TABLE IF NOT EXISTS beta_tester (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id VARCHAR(64) NOT NULL UNIQUE,
                device_name VARCHAR(100) DEFAULT "",
                platform VARCHAR(10) DEFAULT "",
                version VARCHAR(20) DEFAULT "",
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )');
            $betaStmt = $pdo->prepare('SELECT id FROM beta_tester WHERE client_id = ?');
            $betaStmt->execute([$clientId]);
            if ($betaStmt->fetch() !== false) {
                $channel = 'beta';
            }
        } catch (\Throwable $e) {
            // 查询失败不影响正常流程
        }
    }

    $type = $_GET['type'] ?? '';

    // 安装程序请求：不比较版本，直接返回指定版本的安装包下载地址
    if ($type === 'installer') {
        $sql = "SELECT * FROM app_version WHERE version = :version AND platform = :platform AND channel = :channel AND is_active = 1 ORDER BY created_at DESC LIMIT 1";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([':version' => $version, ':platform' => $platform, ':channel' => $channel]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            echo json_encode(['code' => 1, 'data' => null, 'message' => '未找到该版本的安装包'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        $downloadUrl = $row['download_url'] ?? '';
        if (!empty($downloadUrl) && $downloadUrl[0] === '/') {
            $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
            $downloadUrl = $scheme . '://' . $host . $downloadUrl;
        }

        echo json_encode([
            'code' => 0,
            'data' => [
                'has_update' => true,
                'latest_version' => $row['version'],
                'download_url' => $downloadUrl,
                'file_size' => isset($row['file_size']) ? (int)$row['file_size'] : 0,
                'sha256' => $row['sha256'] ?? '',
                'release_date' => $row['release_date'] ?? ''
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $sql = "SELECT * FROM app_version WHERE is_active = 1 AND platform = :platform AND channel = :channel ORDER BY created_at DESC LIMIT 1";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([':platform' => $platform, ':channel' => $channel]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$row) {
        echo json_encode(['code' => 0, 'data' => ['has_update' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $hasUpdate = versionCompare($version, $row['version']) < 0;

    if (!$hasUpdate) {
        echo json_encode(['code' => 0, 'data' => ['has_update' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $forceUpdate = (bool)$row['force_update'];
    if (!empty($row['min_supported']) && versionCompare($version, $row['min_supported']) < 0) {
        $forceUpdate = true;
    }

    $downloadUrl = $row['download_url'] ?? '';
    if (!empty($downloadUrl) && $downloadUrl[0] === '/') {
        $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
        $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
        $downloadUrl = $scheme . '://' . $host . $downloadUrl;
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'has_update' => true,
            'latest_version' => $row['version'],
            'min_supported_version' => $row['min_supported'] ?? '',
            'force_update' => $forceUpdate,
            'release_notes' => $row['release_notes'] ?? '',
            'download_url' => $downloadUrl,
            'file_size' => isset($row['file_size']) ? (int)$row['file_size'] : 0,
            'sha256' => $row['sha256'] ?? '',
            'release_date' => $row['release_date'] ?? ''
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
    exit;

} catch (\Throwable $e) {
    echo json_encode(['code' => 1, 'data' => null, 'message' => '服务器内部错误'], JSON_UNESCAPED_UNICODE);
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
