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

$dbPath = __DIR__ . '/../../../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    http_response_code(500);
    echo json_encode(['code' => 1, 'message' => '数据库连接失败'], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($action === 'upload') {
    handleUpload($pdo);
    exit;
}

switch ($method) {
    case 'POST':
        handleCreate($pdo);
        break;
    case 'PUT':
        handleUpdate($pdo);
        break;
    case 'DELETE':
        handleDelete($pdo);
        break;
    case 'GET':
        handleList($pdo);
        break;
    default:
        http_response_code(405);
        echo json_encode(['code' => 1, 'message' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
}

function handleUpload($pdo) {
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
        exit;
    }

    $file = $_FILES['file'];
    $allowedExts = ['exe', 'dmg', 'deb', 'rpm', 'AppImage', 'zip', '7z', 'tar.gz', 'msi', 'pkg'];
    $originalName = $file['name'];
    $ext = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
    if ($ext === 'gz' && strtolower(pathinfo(basename($originalName, '.gz'), PATHINFO_EXTENSION)) === 'tar') {
        $ext = 'tar.gz';
    }

    $extCheck = $ext;
    if ($ext === 'tar.gz') $extCheck = 'tar';
    if (!in_array($extCheck, array_map('strtolower', $allowedExts)) && !in_array($ext, array_map('strtolower', $allowedExts))) {
        echo json_encode(['code' => 1, 'message' => '不支持的文件类型'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $uploadDir = __DIR__ . '/../../../uploads/versions/';
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
        exit;
    }

    $downloadUrl = '/uploads/versions/' . $fileName;
    $fileSize = filesize($destPath);
    $sha256 = hash_file('sha256', $destPath);

    echo json_encode([
        'code' => 0,
        'data' => [
            'download_url' => $downloadUrl,
            'file_size' => $fileSize,
            'sha256' => $sha256,
            'file_name' => $fileName
        ],
        'message' => 'success'
    ], JSON_UNESCAPED_UNICODE);
}

function handleCreate($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        $input = $_POST;
    }

    $version = trim($input['version'] ?? '');
    $channel = $input['channel'] ?? 'stable';
    $platform = $input['platform'] ?? 'windows';
    $releaseNotes = trim($input['release_notes'] ?? '');
    $downloadUrl = trim($input['download_url'] ?? '');
    $fileSize = $input['file_size'] ?? null;
    $sha256 = trim($input['sha256'] ?? '');
    $minSupported = trim($input['min_supported'] ?? '');
    $forceUpdate = filter_var($input['force_update'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $isActive = filter_var($input['is_active'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $releaseDate = $input['release_date'] ?? date('Y-m-d');

    if (empty($version) || !preg_match('/^\d+\.\d+\.\d+$/', $version)) {
        echo json_encode(['code' => 1, 'message' => '版本号格式不正确，需为 x.y.z 格式'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (empty($downloadUrl)) {
        echo json_encode(['code' => 1, 'message' => '下载地址不能为空'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (!in_array($channel, ['stable', 'beta'])) {
        echo json_encode(['code' => 1, 'message' => '无效的通道'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (!in_array($platform, ['windows', 'mac', 'linux'])) {
        echo json_encode(['code' => 1, 'message' => '无效的平台'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('INSERT INTO app_version (version, channel, platform, release_notes, download_url, file_size, sha256, min_supported, force_update, is_active, release_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        $stmt->execute([$version, $channel, $platform, $releaseNotes, $downloadUrl, $fileSize ?: null, $sha256 ?: null, $minSupported ?: null, $forceUpdate, $isActive, $releaseDate]);
        echo json_encode(['code' => 0, 'message' => '版本添加成功', 'data' => ['id' => $pdo->lastInsertId()]], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if ($e->getCode() == 23000) {
            echo json_encode(['code' => 1, 'message' => '该版本号已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '添加失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handleUpdate($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        parse_str(file_get_contents('php://input'), $input);
    }

    $id = $input['id'] ?? null;
    $version = trim($input['version'] ?? '');
    $channel = $input['channel'] ?? 'stable';
    $platform = $input['platform'] ?? 'windows';
    $releaseNotes = trim($input['release_notes'] ?? '');
    $downloadUrl = trim($input['download_url'] ?? '');
    $fileSize = $input['file_size'] ?? null;
    $sha256 = trim($input['sha256'] ?? '');
    $minSupported = trim($input['min_supported'] ?? '');
    $forceUpdate = filter_var($input['force_update'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $isActive = filter_var($input['is_active'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $releaseDate = $input['release_date'] ?? date('Y-m-d');

    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少版本ID'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (empty($version) || !preg_match('/^\d+\.\d+\.\d+$/', $version)) {
        echo json_encode(['code' => 1, 'message' => '版本号格式不正确'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (empty($downloadUrl)) {
        echo json_encode(['code' => 1, 'message' => '下载地址不能为空'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('UPDATE app_version SET version=?, channel=?, platform=?, release_notes=?, download_url=?, file_size=?, sha256=?, min_supported=?, force_update=?, is_active=?, release_date=? WHERE id=?');
        $stmt->execute([$version, $channel, $platform, $releaseNotes, $downloadUrl, $fileSize ?: null, $sha256 ?: null, $minSupported ?: null, $forceUpdate, $isActive, $releaseDate, $id]);
        echo json_encode(['code' => 0, 'message' => '版本更新成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if ($e->getCode() == 23000) {
            echo json_encode(['code' => 1, 'message' => '该版本号已存在'], JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['code' => 1, 'message' => '更新失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
        }
    }
}

function handleDelete($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        parse_str(file_get_contents('php://input'), $input);
    }
    $id = $input['id'] ?? $_GET['id'] ?? null;

    if (!$id) {
        echo json_encode(['code' => 1, 'message' => '缺少版本ID'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('DELETE FROM app_version WHERE id=?');
        $stmt->execute([$id]);
        echo json_encode(['code' => 0, 'message' => '版本已删除'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '删除失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleList($pdo) {
    $platform = $_GET['platform'] ?? null;
    $channel = $_GET['channel'] ?? null;

    $sql = 'SELECT * FROM app_version WHERE 1=1';
    $params = [];

    if ($platform) {
        $sql .= ' AND platform = :platform';
        $params[':platform'] = $platform;
    }
    if ($channel) {
        $sql .= ' AND channel = :channel';
        $params[':channel'] = $channel;
    }

    $sql .= ' ORDER BY created_at DESC';

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}
