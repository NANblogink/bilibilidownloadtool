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
    $allowedExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'pdf', 'zip', 'html', 'htm'];
    $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, $allowedExts)) {
        echo json_encode(['code' => 1, 'message' => '不支持的文件类型'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $uploadDir = __DIR__ . '/../../../uploads/announcements/';
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
        exit;
    }

    $actionUrl = '/uploads/announcements/' . $fileName;

    echo json_encode([
        'code' => 0,
        'data' => [
            'action_url' => $actionUrl,
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

    $id = trim($input['id'] ?? '');
    $type = $input['type'] ?? 'info';
    $title = trim($input['title'] ?? '');
    $content = trim($input['content'] ?? '');
    $startTime = normalizeDatetime($input['start_time'] ?? '');
    $endTime = normalizeDatetime($input['end_time'] ?? '');
    $actionType = $input['action_type'] ?? 'none';
    $actionUrl = trim($input['action_url'] ?? '');
    $dismissible = filter_var($input['dismissible'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $minVersion = trim($input['min_version'] ?? '');
    $maxVersion = trim($input['max_version'] ?? '');
    $isActive = filter_var($input['is_active'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($id) || empty($title) || empty($content) || empty($startTime) || empty($endTime)) {
        echo json_encode(['code' => 1, 'message' => '请填写所有必填字段'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (!in_array($type, ['info', 'warning', 'error'])) {
        echo json_encode(['code' => 1, 'message' => '无效的公告类型'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (!in_array($actionType, ['none', 'update', 'url'])) {
        echo json_encode(['code' => 1, 'message' => '无效的动作类型'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('INSERT INTO announcement (id, type, title, content, start_time, end_time, action_type, action_url, dismissible, min_version, max_version, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        $stmt->execute([$id, $type, $title, $content, $startTime, $endTime, $actionType, $actionUrl, $dismissible, $minVersion, $maxVersion, $isActive]);
        echo json_encode(['code' => 0, 'message' => '公告添加成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        if (strpos($e->getMessage(), 'UNIQUE constraint') !== false || strpos($e->getMessage(), 'PRIMARY KEY') !== false) {
            echo json_encode(['code' => 1, 'message' => '该公告ID已存在'], JSON_UNESCAPED_UNICODE);
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

    $id = trim($input['id'] ?? '');
    $type = $input['type'] ?? 'info';
    $title = trim($input['title'] ?? '');
    $content = trim($input['content'] ?? '');
    $startTime = normalizeDatetime($input['start_time'] ?? '');
    $endTime = normalizeDatetime($input['end_time'] ?? '');
    $actionType = $input['action_type'] ?? 'none';
    $actionUrl = trim($input['action_url'] ?? '');
    $dismissible = filter_var($input['dismissible'] ?? true, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;
    $minVersion = trim($input['min_version'] ?? '');
    $maxVersion = trim($input['max_version'] ?? '');
    $isActive = filter_var($input['is_active'] ?? false, FILTER_VALIDATE_BOOLEAN) ? 1 : 0;

    if (empty($id) || empty($title) || empty($content) || empty($startTime) || empty($endTime)) {
        echo json_encode(['code' => 1, 'message' => '请填写所有必填字段'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('UPDATE announcement SET type=?, title=?, content=?, start_time=?, end_time=?, action_type=?, action_url=?, dismissible=?, min_version=?, max_version=?, is_active=? WHERE id=?');
        $stmt->execute([$type, $title, $content, $startTime, $endTime, $actionType, $actionUrl, $dismissible, $minVersion, $maxVersion, $isActive, $id]);
        echo json_encode(['code' => 0, 'message' => '公告更新成功'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '更新失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleDelete($pdo) {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input) {
        parse_str(file_get_contents('php://input'), $input);
    }
    $id = $input['id'] ?? $_GET['id'] ?? null;

    if (empty($id)) {
        echo json_encode(['code' => 1, 'message' => '缺少公告ID'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $stmt = $pdo->prepare('DELETE FROM announcement WHERE id=?');
        $stmt->execute([$id]);
        echo json_encode(['code' => 0, 'message' => '公告已删除'], JSON_UNESCAPED_UNICODE);
    } catch (PDOException $e) {
        echo json_encode(['code' => 1, 'message' => '删除失败：' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
}

function handleList($pdo) {
    $type = $_GET['type'] ?? null;
    $isActive = $_GET['is_active'] ?? null;

    $sql = 'SELECT * FROM announcement WHERE 1=1';
    $params = [];

    if ($type) {
        $sql .= ' AND type = :type';
        $params[':type'] = $type;
    }
    if ($isActive !== null) {
        $sql .= ' AND is_active = :is_active';
        $params[':is_active'] = (int)$isActive;
    }

    $sql .= ' ORDER BY created_at DESC';

    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['code' => 0, 'data' => $rows, 'message' => 'success'], JSON_UNESCAPED_UNICODE);
}

function normalizeDatetime($val) {
    if (empty($val)) return '';
    $val = str_replace('T', ' ', $val);
    if (preg_match('/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/', $val)) {
        $val .= ':00';
    }
    return $val;
}
