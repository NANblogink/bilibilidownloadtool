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

$token = $_SERVER['HTTP_X_API_TOKEN'] ?? $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = preg_replace('/^Bearer\s+/i', '', $token);

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

$pdo->exec('CREATE TABLE IF NOT EXISTS patch_package (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_version VARCHAR(20) NOT NULL,
    to_version VARCHAR(20) NOT NULL,
    platform VARCHAR(10) DEFAULT "windows",
    patch_url VARCHAR(500) NOT NULL,
    patch_size BIGINT,
    patch_sha256 VARCHAR(64),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_version, to_version, platform)
)');

// 公开接口：检查增量更新 / 获取增量包列表 / 下载增量包
if ($method === 'GET' && $action === 'check') {
    handlePatchCheck($pdo);
    exit;
}

if ($method === 'GET' && $action === 'list') {
    handlePatchList($pdo);
    exit;
}

if ($method === 'GET' && $action === 'download') {
    $id = (int)($_GET['id'] ?? 0);
    handleDownload($pdo, $id);
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
    switch ($action) {
        default:
            handlePatchList($pdo);
            break;
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create') {
        handlePatchCreate($pdo, $input);
    } elseif ($postAction === 'generate') {
        handlePatchGenerate($pdo, $input);
    } elseif ($postAction === 'upload') {
        handlePatchUpload($pdo);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handlePatchUpdate($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handlePatchDelete($pdo, $id);
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

function handlePatchCheck($pdo) {
    $fromVersion = $_GET['from_version'] ?? '';
    $platform = $_GET['platform'] ?? 'windows';

    if (empty($fromVersion)) {
        echo json_encode(['code' => 1, 'message' => '缺少当前版本号'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM app_version WHERE is_active = 1 AND platform = ? ORDER BY created_at DESC LIMIT 1");
    $stmt->execute([$platform]);
    $latestRow = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$latestRow) {
        echo json_encode(['code' => 0, 'data' => ['has_patch' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $toVersion = $latestRow['version'];
    if (versionCompare($fromVersion, $toVersion) >= 0) {
        echo json_encode(['code' => 0, 'data' => ['has_patch' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM patch_package WHERE from_version = ? AND to_version = ? AND platform = ? AND is_active = 1");
    $stmt->execute([$fromVersion, $toVersion, $platform]);
    $patchRow = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$patchRow) {
        echo json_encode([
            'code' => 0,
            'data' => [
                'has_patch' => false,
                'has_full_update' => true,
                'latest_version' => $toVersion
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    $patchUrl = $patchRow['patch_url'] ?? '';
    if (!empty($patchUrl) && $patchUrl[0] === '/') {
        $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
        $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
        $patchUrl = $scheme . '://' . $host . $patchUrl;
    }

    $downloadUrl = $latestRow['download_url'] ?? '';
    if (!empty($downloadUrl) && $downloadUrl[0] === '/') {
        $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
        $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
        $downloadUrl = $scheme . '://' . $host . $downloadUrl;
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'has_patch' => true,
            'from_version' => $fromVersion,
            'to_version' => $toVersion,
            'patch_url' => $patchUrl,
            'patch_size' => isset($patchRow['patch_size']) ? (int)$patchRow['patch_size'] : 0,
            'patch_sha256' => $patchRow['patch_sha256'] ?? '',
            'full_update_url' => $downloadUrl,
            'full_update_size' => isset($latestRow['file_size']) ? (int)$latestRow['file_size'] : 0,
            'full_update_sha256' => $latestRow['sha256'] ?? '',
            'release_notes' => $latestRow['release_notes'] ?? ''
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handlePatchList($pdo) {
    $platform = $_GET['platform'] ?? '';
    $sql = 'SELECT * FROM patch_package WHERE 1=1';
    $params = [];
    if ($platform) {
        $sql .= ' AND platform = ?';
        $params[] = $platform;
    }
    $sql .= ' ORDER BY created_at DESC';
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleDownload($pdo, $id) {
    $stmt = $pdo->prepare("SELECT * FROM patch_package WHERE id=?");
    $stmt->execute([$id]);
    $patch = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$patch) { echo json_encode(['code' => 1, 'message' => '增量包不存在'], JSON_UNESCAPED_UNICODE); exit; }
    $filePath = __DIR__ . '/../../../../' . ltrim($patch['patch_url'], '/');
    if (!file_exists($filePath)) { echo json_encode(['code' => 1, 'message' => '文件不存在'], JSON_UNESCAPED_UNICODE); exit; }
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . basename($filePath) . '"');
    header('Content-Length: ' . filesize($filePath));
    readfile($filePath);
    exit;
}

function handlePatchCreate($pdo, $input) {
    $fromVersion = trim($input['from_version'] ?? '');
    $toVersion = trim($input['to_version'] ?? '');
    $platform = $input['platform'] ?? 'windows';
    $patchUrl = trim($input['patch_url'] ?? '');
    $patchSize = $input['patch_size'] ?? null;
    $patchSha256 = trim($input['patch_sha256'] ?? '');
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($fromVersion) || empty($toVersion)) {
        echo json_encode(['code' => 1, 'message' => '版本号不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (empty($patchUrl)) {
        echo json_encode(['code' => 1, 'message' => '补丁地址不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO patch_package (from_version, to_version, platform, patch_url, patch_size, patch_sha256, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$fromVersion, $toVersion, $platform, $patchUrl, $patchSize, $patchSha256, $isActive]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '增量包添加成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if ($e->getCode() == 23000) {
            echo json_encode(['code' => 1, 'message' => '该增量包已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '添加失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handlePatchGenerate($pdo, $input) {
    $fromVersion = trim($input['from_version'] ?? '');
    $toVersion = trim($input['to_version'] ?? '');
    $platform = $input['platform'] ?? 'windows';

    if (empty($fromVersion) || empty($toVersion)) {
        echo json_encode(['code' => 1, 'message' => '版本号不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $uploadDir = __DIR__ . '/../../../uploads/patches/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0755, true);
    }

    $patchFilename = 'patch_' . $fromVersion . '_' . $toVersion . '_' . $platform . '.zip';
    $patchPath = $uploadDir . $patchFilename;

    $zip = new ZipArchive();
    if ($zip->open($patchPath, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
        echo json_encode(['code' => 1, 'message' => '创建增量包失败'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $patchInfo = "From: {$fromVersion}\nTo: {$toVersion}\nPlatform: {$platform}\nGenerated: " . date('Y-m-d H:i:s') . "\n";
    $zip->addFromString('patch_info.txt', $patchInfo);
    $zip->addFromString('manifest.json', json_encode([
        'from_version' => $fromVersion,
        'to_version' => $toVersion,
        'platform' => $platform,
        'generated_at' => date('Y-m-d H:i:s'),
        'files' => []
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $zip->close();

    $patchSize = filesize($patchPath);
    $patchSha256 = hash_file('sha256', $patchPath);
    $patchUrl = '/uploads/patches/' . $patchFilename;

    try {
        $stmt = $pdo->prepare("INSERT OR REPLACE INTO patch_package (from_version, to_version, platform, patch_url, patch_size, patch_sha256, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)");
        $stmt->execute([$fromVersion, $toVersion, $platform, $patchUrl, $patchSize, $patchSha256]);

        $stmt = $pdo->prepare("SELECT * FROM patch_package WHERE from_version = ? AND to_version = ? AND platform = ?");
        $stmt->execute([$fromVersion, $toVersion, $platform]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        echo json_encode(['code' => 0, 'data' => $row, 'message' => '增量包生成成功'], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        echo json_encode(['code' => 1, 'message' => '生成失败: ' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handlePatchUpload($pdo) {
    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        $errMsg = '上传失败';
        if (isset($_FILES['file'])) {
            $errCodes = [
                UPLOAD_ERR_INI_SIZE => '文件超过服务器大小限制',
                UPLOAD_ERR_FORM_SIZE => '文件超过表单大小限制',
                UPLOAD_ERR_PARTIAL => '文件上传不完整',
                UPLOAD_ERR_NO_FILE => '未选择文件',
            ];
            $errMsg = $errCodes[$_FILES['file']['error']] ?? $errMsg;
        }
        echo json_encode(['code' => 1, 'message' => $errMsg], JSON_UNESCAPED_UNICODE);
        return;
    }

    $file = $_FILES['file'];
    $allowedExts = ['zip', 'patch', 'diff', '7z'];
    $originalName = $file['name'];
    $ext = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
    if (!in_array($ext, $allowedExts)) {
        echo json_encode(['code' => 1, 'message' => '不支持的文件类型'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $uploadDir = __DIR__ . '/../../../uploads/patches/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0755, true);
    }

    $safeName = preg_replace('/[^a-zA-Z0-9_\-.]/', '_', pathinfo($originalName, PATHINFO_FILENAME));
    $fileName = $safeName . '.' . $ext;
    $counter = 1;
    while (file_exists($uploadDir . $fileName)) {
        $fileName = $safeName . '_' . $counter . '.' . $ext;
        $counter++;
    }

    $destPath = $uploadDir . $fileName;
    if (!move_uploaded_file($file['tmp_name'], $destPath)) {
        echo json_encode(['code' => 1, 'message' => '文件保存失败'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $patchUrl = '/uploads/patches/' . $fileName;
    $patchSize = filesize($destPath);
    $patchSha256 = hash_file('sha256', $destPath);

    echo json_encode([
        'code' => 0,
        'data' => [
            'patch_url' => $patchUrl,
            'patch_size' => $patchSize,
            'patch_sha256' => $patchSha256,
            'file_name' => $fileName
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handlePatchUpdate($pdo, $input) {
    $id = $input['id'] ?? null;
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少ID'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $fields = [];
    $params = [];
    foreach (['from_version', 'to_version', 'platform', 'patch_url', 'patch_size', 'patch_sha256'] as $key) {
        if (isset($input[$key])) {
            $fields[] = "$key = ?";
            $params[] = $input[$key];
        }
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

    $stmt = $pdo->prepare("UPDATE patch_package SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '更新成功'], JSON_UNESCAPED_UNICODE);
}

function handlePatchDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM patch_package WHERE id=?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '增量包已删除'], JSON_UNESCAPED_UNICODE);
}
