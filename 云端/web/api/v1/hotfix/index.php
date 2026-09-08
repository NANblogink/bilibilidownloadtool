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

$pdo->exec('CREATE TABLE IF NOT EXISTS hotfix (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hotfix_id VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    file_path VARCHAR(500) DEFAULT "",
    file_size BIGINT DEFAULT 0,
    sha256 VARCHAR(64) DEFAULT "",
    target_version VARCHAR(20) DEFAULT "",
    target_platform VARCHAR(20) DEFAULT "all",
    is_active BOOLEAN DEFAULT 1,
    is_rollback BOOLEAN DEFAULT 0,
    applied_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：检查是否有热修复 / 下载热修复
if ($method === 'GET' && $action === 'check') {
    handleHotfixCheck($pdo);
    exit;
}

if ($method === 'GET' && $action === 'download') {
    $hotfixId = $_GET['id'] ?? '';
    handleHotfixDownload($pdo, $hotfixId);
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
        handleHotfixList($pdo);
    } else {
        handleHotfixList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create') {
        handleHotfixCreate($pdo, $input);
    } elseif ($postAction === 'upload') {
        handleHotfixUpload($pdo);
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
    foreach (['title', 'description', 'target_version', 'target_platform'] as $k) {
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
    $stmt = $pdo->prepare("UPDATE hotfix SET " . implode(',', $fields) . " WHERE id=:id");
    $stmt->execute($params);
    echo json_encode(['code' => 0, 'message' => '更新成功'], JSON_UNESCAPED_UNICODE);
    exit;
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleHotfixDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

// 公开：检查是否有热修复
function handleHotfixCheck($pdo) {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'all';

    if (empty($version)) {
        echo json_encode(['code' => 1, 'message' => '缺少版本号'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $stmt = $pdo->prepare("SELECT * FROM hotfix WHERE is_active = 1 AND target_version = ? AND (target_platform = 'all' OR target_platform = ?) ORDER BY is_rollback ASC, created_at DESC");
    $stmt->execute([$version, $platform]);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    if (empty($rows)) {
        echo json_encode([
            'code' => 0,
            'data' => ['has_hotfix' => false],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        return;
    }

    $hotfixes = [];
    foreach ($rows as $row) {
        $filePath = $row['file_path'] ?? '';
        if (!empty($filePath) && $filePath[0] === '/') {
            $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
            $filePath = $scheme . '://' . $host . $filePath;
        }
        $hotfixes[] = [
            'hotfix_id' => $row['hotfix_id'],
            'title' => $row['title'],
            'description' => $row['description'],
            'file_path' => $filePath,
            'file_size' => isset($row['file_size']) ? (int)$row['file_size'] : 0,
            'sha256' => $row['sha256'] ?? '',
            'target_version' => $row['target_version'],
            'target_platform' => $row['target_platform'],
            'is_rollback' => isset($row['is_rollback']) ? (bool)$row['is_rollback'] : false
        ];
    }

    echo json_encode([
        'code' => 0,
        'data' => [
            'has_hotfix' => true,
            'hotfixes' => $hotfixes
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleHotfixList($pdo) {
    $stmt = $pdo->prepare('SELECT * FROM hotfix ORDER BY created_at DESC');
    $stmt->execute();
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleHotfixCreate($pdo, $input) {
    $hotfixId = trim($input['hotfix_id'] ?? '');
    $title = trim($input['title'] ?? '');
    $description = trim($input['description'] ?? '');
    $filePath = trim($input['file_path'] ?? '');
    $fileSize = $input['file_size'] ?? 0;
    $sha256 = trim($input['sha256'] ?? '');
    $targetVersion = trim($input['target_version'] ?? '');
    $targetPlatform = $input['target_platform'] ?? 'all';
    $isActive = filter_var($input['is_active'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $isRollback = filter_var($input['is_rollback'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($hotfixId) || empty($title)) {
        echo json_encode(['code' => 1, 'message' => '热修复ID和标题不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO hotfix (hotfix_id, title, description, file_path, file_size, sha256, target_version, target_platform, is_active, is_rollback) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$hotfixId, $title, $description, $filePath, $fileSize, $sha256, $targetVersion, $targetPlatform, $isActive, $isRollback]);
        echo json_encode(['code' => 0, 'data' => ['id' => $pdo->lastInsertId()], 'message' => '热修复创建成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if (strpos($e->getMessage(), 'UNIQUE') !== false) {
            echo json_encode(['code' => 1, 'message' => '该热修复ID已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '创建失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handleHotfixUpload($pdo) {
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
    $allowedExts = ['zip', 'patch', 'dll', 'exe', 'json', 'bin'];
    $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, $allowedExts)) {
        echo json_encode(['code' => 1, 'message' => '不支持的文件类型'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $uploadDir = __DIR__ . '/../../../uploads/hotfixes/';
    if (!is_dir($uploadDir)) {
        mkdir($uploadDir, 0755, true);
    }

    $safeName = preg_replace('/[^a-zA-Z0-9_\-.]/', '_', pathinfo($file['name'], PATHINFO_FILENAME));
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

    $filePath = '/uploads/hotfixes/' . $fileName;
    $fileSize = filesize($destPath);
    $sha256 = hash_file('sha256', $destPath);

    echo json_encode([
        'code' => 0,
        'data' => [
            'file_path' => $filePath,
            'file_size' => $fileSize,
            'sha256' => $sha256,
            'file_name' => $fileName
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleHotfixDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少热修复ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('DELETE FROM hotfix WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '热修复已删除'], JSON_UNESCAPED_UNICODE);
}

function handleHotfixDownload($pdo, $hotfixId) {
    if (empty($hotfixId)) {
        echo json_encode(['code' => 1, 'message' => '缺少热修复ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare("SELECT * FROM hotfix WHERE hotfix_id = ? AND is_active = 1");
    $stmt->execute([$hotfixId]);
    $hotfix = $stmt->fetch(PDO::FETCH_ASSOC);
    if (!$hotfix) {
        echo json_encode(['code' => 1, 'message' => '热修复不存在'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $filePath = $hotfix['file_path'] ?? '';
    if (empty($filePath)) {
        echo json_encode(['code' => 1, 'message' => '热修复文件不存在'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $fullPath = __DIR__ . '/../../../' . ltrim($filePath, '/');
    if (!file_exists($fullPath)) {
        echo json_encode(['code' => 1, 'message' => '热修复文件不存在'], JSON_UNESCAPED_UNICODE);
        return;
    }
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . basename($fullPath) . '"');
    header('Content-Length: ' . filesize($fullPath));
    readfile($fullPath);
    exit;
}
