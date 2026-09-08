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

$pdo->exec('CREATE TABLE IF NOT EXISTS remote_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path VARCHAR(500) NOT NULL UNIQUE,
    file_content TEXT,
    file_size BIGINT DEFAULT 0,
    sha256 VARCHAR(64),
    is_active BOOLEAN DEFAULT 1,
    min_version VARCHAR(20) DEFAULT "",
    max_version VARCHAR(20) DEFAULT "",
    target_platform VARCHAR(20) DEFAULT "all",
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 公开接口：获取文件列表 / 读取文件内容
if ($method === 'GET' && $action === 'list') {
    handleFileList($pdo);
    exit;
}

if ($method === 'GET' && $action === 'read') {
    handleFileRead($pdo);
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
        handleFileList($pdo);
    } elseif ($action === 'read') {
        handleFileRead($pdo);
    } else {
        handleFileList($pdo);
    }
} elseif ($method === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) $input = $_POST;
    $postAction = $action ?: ($input['action'] ?? '');
    if ($postAction === 'create' || $postAction === 'write') {
        handleFileWrite($pdo, $input);
    } elseif ($postAction === 'delete') {
        handleFileDeleteByPath($pdo, $input);
    } else {
        echo json_encode(['code' => 1, 'message' => '未知操作'], JSON_UNESCAPED_UNICODE);
    }
} elseif ($method === 'PUT') {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) parse_str(file_get_contents('php://input'), $input);
    handleFileWrite($pdo, $input);
} elseif ($method === 'DELETE') {
    $id = $_GET['id'] ?? '';
    handleFileDelete($pdo, $id);
} else {
    http_response_code(405);
    echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

function handleFileList($pdo) {
    $path = $_GET['path'] ?? '';
    $platform = $_GET['platform'] ?? '';

    $sql = 'SELECT * FROM remote_file WHERE is_active = 1';
    $params = [];

    if ($path) {
        $sql .= ' AND file_path LIKE ?';
        $params[] = $path . '%';
    }
    if ($platform && $platform !== 'all') {
        $sql .= " AND (target_platform = 'all' OR target_platform = ?)";
        $params[] = $platform;
    }
    $sql .= ' ORDER BY file_path';

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $files = [];
    $dirs = [];
    foreach ($rows as $row) {
        $fp = $row['file_path'];
        if (strpos($fp, '/') !== false) {
            $dirName = substr($fp, 0, strrpos($fp, '/'));
            if ($dirName && !in_array($dirName, $dirs)) {
                $dirs[] = $dirName;
            }
        }
        $files[] = $row;
    }
    sort($dirs);

    echo json_encode([
        'code' => 0,
        'data' => [
            'files' => $files,
            'directories' => $dirs
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleFileRead($pdo) {
    $id = $_GET['id'] ?? '';
    $filePath = $_GET['path'] ?? '';

    if ($id) {
        $stmt = $pdo->prepare('SELECT * FROM remote_file WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
    } elseif ($filePath) {
        $stmt = $pdo->prepare('SELECT * FROM remote_file WHERE file_path = ?');
        $stmt->execute([$filePath]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
    } else {
        echo json_encode(['code' => 1, 'message' => '请指定文件ID或路径'], JSON_UNESCAPED_UNICODE);
        return;
    }

    if (!$row) {
        echo json_encode(['code' => 1, 'message' => '文件不存在'], JSON_UNESCAPED_UNICODE);
        return;
    }

    echo json_encode(['code' => 0, 'data' => $row, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function handleFileWrite($pdo, $input) {
    $filePath = trim($input['file_path'] ?? '');
    $fileContent = $input['file_content'] ?? '';
    $minVersion = trim($input['min_version'] ?? '');
    $maxVersion = trim($input['max_version'] ?? '');
    $targetPlatform = $input['target_platform'] ?? 'all';

    if (empty($filePath)) {
        echo json_encode(['code' => 1, 'message' => '文件路径不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    if (strpos($filePath, '/') === 0 || strpos($filePath, '..') !== false) {
        echo json_encode(['code' => 1, 'message' => '无效的文件路径'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $contentBytes = strlen($fileContent);
    $contentSha256 = hash('sha256', $fileContent);
    $now = date('Y-m-d H:i:s');

    try {
        $stmt = $pdo->prepare("INSERT INTO remote_file (file_path, file_content, file_size, sha256, min_version, max_version, target_platform, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(file_path) DO UPDATE SET file_content = ?, file_size = ?, sha256 = ?, min_version = ?, max_version = ?, target_platform = ?, updated_at = ?");
        $stmt->execute([
            $filePath, $fileContent, $contentBytes, $contentSha256,
            $minVersion, $maxVersion, $targetPlatform, $now, $now,
            $fileContent, $contentBytes, $contentSha256,
            $minVersion, $maxVersion, $targetPlatform, $now
        ]);

        $stmt = $pdo->prepare('SELECT * FROM remote_file WHERE file_path = ?');
        $stmt->execute([$filePath]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        echo json_encode(['code' => 0, 'data' => $row, 'message' => '文件保存成功'], JSON_UNESCAPED_UNICODE);
    } catch (\Exception $e) {
        echo json_encode(['code' => 1, 'message' => '保存失败: ' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleFileDelete($pdo, $id) {
    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少文件ID'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('UPDATE remote_file SET is_active = 0 WHERE id = ?');
    $stmt->execute([$id]);
    echo json_encode(['code' => 0, 'message' => '文件已删除'], JSON_UNESCAPED_UNICODE);
}

function handleFileDeleteByPath($pdo, $input) {
    $filePath = $input['file_path'] ?? '';
    if (empty($filePath)) {
        echo json_encode(['code' => 1, 'message' => '文件路径不能为空'], JSON_UNESCAPED_UNICODE);
        return;
    }
    $stmt = $pdo->prepare('UPDATE remote_file SET is_active = 0 WHERE file_path = ?');
    $stmt->execute([$filePath]);
    echo json_encode(['code' => 0, 'message' => '文件已删除'], JSON_UNESCAPED_UNICODE);
}
