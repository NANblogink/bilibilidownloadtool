<?php
require_once 'auth.php';
require_admin_login();

$pdo = new PDO('sqlite:' . __DIR__ . '/../../data/bilidown.db');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$pdo->exec('CREATE TABLE IF NOT EXISTS app_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version VARCHAR(20) NOT NULL UNIQUE,
    channel VARCHAR(10) DEFAULT \'stable\',
    platform VARCHAR(10) DEFAULT \'windows\',
    release_notes TEXT,
    download_url VARCHAR(500) NOT NULL,
    file_size BIGINT,
    sha256 VARCHAR(64),
    min_supported VARCHAR(20),
    force_update BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    release_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$pdo->exec('CREATE TABLE IF NOT EXISTS announcement (
    id VARCHAR(50) PRIMARY KEY,
    type VARCHAR(10) DEFAULT \'info\',
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    action_type VARCHAR(10) DEFAULT \'none\',
    action_url VARCHAR(500) DEFAULT \'\',
    dismissible BOOLEAN DEFAULT 1,
    min_version VARCHAR(20) DEFAULT \'\',
    max_version VARCHAR(20) DEFAULT \'\',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

function normalizeDatetime($val) {
    if (empty($val)) return '';
    $val = str_replace('T', ' ', $val);
    if (preg_match('/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/', $val)) {
        $val .= ':00';
    }
    return $val;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');
    $action = $_POST['action'] ?? '';

    if ($action === 'upload_file') {
        if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
            $errMsg = '上传失败';
            if (isset($_FILES['file'])) {
                $errCodes = [
                    UPLOAD_ERR_INI_SIZE => '文件超过服务器大小限制',
                    UPLOAD_ERR_FORM_SIZE => '文件超过表单大小限制',
                    UPLOAD_ERR_PARTIAL => '文件上传不完整',
                    UPLOAD_ERR_NO_FILE => '未选择文件',
                    UPLOAD_ERR_NO_TMP_DIR => '服务器缺少临时目录',
                    UPLOAD_ERR_CANT_WRITE => '服务器写入失败',
                ];
                $errMsg = $errCodes[$_FILES['file']['error']] ?? $errMsg;
            }
            echo json_encode(['success' => false, 'message' => $errMsg]);
            exit;
        }

        $file = $_FILES['file'];
        $allowedExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'pdf', 'zip', 'html', 'htm'];
        $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
        if (!in_array($ext, $allowedExts)) {
            echo json_encode(['success' => false, 'message' => '不支持的文件类型，允许: ' . implode(', ', $allowedExts)]);
            exit;
        }

        $uploadDir = __DIR__ . '/../uploads/announcements/';
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
            echo json_encode(['success' => false, 'message' => '文件保存失败，请检查目录权限']);
            exit;
        }

        $actionUrl = '/uploads/announcements/' . $fileName;
        echo json_encode(['success' => true, 'message' => '上传成功', 'action_url' => $actionUrl, 'file_name' => $fileName]);
        exit;
    }

    if ($action === 'add') {
        $id = trim($_POST['id'] ?? '');
        $type = $_POST['type'] ?? 'info';
        $title = trim($_POST['title'] ?? '');
        $content = trim($_POST['content'] ?? '');
        $start_time = normalizeDatetime($_POST['start_time'] ?? '');
        $end_time = normalizeDatetime($_POST['end_time'] ?? '');
        $action_type = $_POST['action_type'] ?? 'none';
        $action_url = trim($_POST['action_url'] ?? '');
        $dismissible = isset($_POST['dismissible']) ? 1 : 0;
        $min_version = trim($_POST['min_version'] ?? '');
        $max_version = trim($_POST['max_version'] ?? '');
        $is_active = isset($_POST['is_active']) ? 1 : 0;

        if ($id === '' || $title === '' || $content === '' || $start_time === '' || $end_time === '') {
            echo json_encode(['success' => false, 'message' => '请填写所有必填字段']);
            exit;
        }

        try {
            $stmt = $pdo->prepare('INSERT INTO announcement (id, type, title, content, start_time, end_time, action_type, action_url, dismissible, min_version, max_version, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
            $stmt->execute([$id, $type, $title, $content, $start_time, $end_time, $action_type, $action_url, $dismissible, $min_version, $max_version, $is_active]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '添加失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'edit') {
        $id = trim($_POST['id'] ?? '');
        $type = $_POST['type'] ?? 'info';
        $title = trim($_POST['title'] ?? '');
        $content = trim($_POST['content'] ?? '');
        $start_time = normalizeDatetime($_POST['start_time'] ?? '');
        $end_time = normalizeDatetime($_POST['end_time'] ?? '');
        $action_type = $_POST['action_type'] ?? 'none';
        $action_url = trim($_POST['action_url'] ?? '');
        $dismissible = isset($_POST['dismissible']) ? 1 : 0;
        $min_version = trim($_POST['min_version'] ?? '');
        $max_version = trim($_POST['max_version'] ?? '');
        $is_active = isset($_POST['is_active']) ? 1 : 0;

        if ($id === '' || $title === '' || $content === '' || $start_time === '' || $end_time === '') {
            echo json_encode(['success' => false, 'message' => '请填写所有必填字段']);
            exit;
        }

        try {
            $stmt = $pdo->prepare('UPDATE announcement SET type=?, title=?, content=?, start_time=?, end_time=?, action_type=?, action_url=?, dismissible=?, min_version=?, max_version=?, is_active=? WHERE id=?');
            $stmt->execute([$type, $title, $content, $start_time, $end_time, $action_type, $action_url, $dismissible, $min_version, $max_version, $is_active, $id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '编辑失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'delete') {
        $id = $_POST['id'] ?? '';
        try {
            $stmt = $pdo->prepare('DELETE FROM announcement WHERE id=?');
            $stmt->execute([$id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '删除失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'toggle_active') {
        $id = $_POST['id'] ?? '';
        try {
            $stmt = $pdo->prepare('UPDATE announcement SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id=?');
            $stmt->execute([$id]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '操作失败：' . $e->getMessage()]);
        }
        exit;
    }

    echo json_encode(['success' => false, 'message' => '未知操作']);
    exit;
}

$announcements = $pdo->query('SELECT * FROM announcement ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
$now = time();
$totalCount = count($announcements);
$activeCount = 0;
$expiredCount = 0;
$currentCount = 0;

foreach ($announcements as $ann) {
    if (!$ann['is_active']) continue;
    $start = strtotime($ann['start_time']);
    $end = strtotime($ann['end_time']);
    if ($end < $now) {
        $expiredCount++;
    } elseif ($start <= $now && $end >= $now) {
        $currentCount++;
    }
    $activeCount++;
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>公告管理 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #f5f7fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .container {
            max-width: 1400px;
            margin: 30px auto;
            padding: 0 30px;
        }

        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .stat-icon {
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
        }

        .stat-icon.total { background: #667eea; }
        .stat-icon.active { background: #48bb78; }
        .stat-icon.current { background: #00a1d6; }
        .stat-icon.expired { background: #a0aec0; }

        .stat-info h3 {
            font-size: 28px;
            font-weight: 700;
            color: #333;
            margin-bottom: 5px;
        }

        .stat-info p {
            color: #666;
            font-size: 14px;
        }

        .toolbar {
            background: white;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }

        .toolbar-left {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }

        .filter-select {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            font-size: 14px;
            min-width: 150px;
        }

        .filter-select:focus {
            border-color: #667eea;
            outline: none;
        }

        .btn-add {
            background: #00a1d6;
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background 0.3s;
        }

        .btn-add:hover {
            background: #0088b2;
        }

        .announcement-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .announcement-card {
            background: white;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
            position: relative;
        }

        .announcement-card.type-info { border-left-color: #2b6cb0; }
        .announcement-card.type-warning { border-left-color: #c05621; }
        .announcement-card.type-error { border-left-color: #c53030; }
        .announcement-card.is-expired {
            border-left-color: #a0aec0;
            opacity: 0.7;
        }

        .announcement-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
            gap: 15px;
        }

        .announcement-title-wrap {
            flex: 1;
        }

        .announcement-badges {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }

        .badge-type {
            display: inline-block;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-type.info { background: #ebf8ff; color: #2b6cb0; }
        .badge-type.warning { background: #fffaf0; color: #c05621; }
        .badge-type.error { background: #fff5f5; color: #c53030; }

        .badge-status {
            display: inline-block;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-status.active { background: #f0fff4; color: #276749; }
        .badge-status.inactive { background: #f7fafc; color: #718096; }
        .badge-status.current { background: #ebf8ff; color: #2b6cb0; }
        .badge-status.expired { background: #f7fafc; color: #a0aec0; }

        .announcement-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }

        .announcement-id {
            font-size: 12px;
            color: #a0aec0;
            font-family: monospace;
        }

        .announcement-content {
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 15px;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .announcement-meta {
            display: flex;
            gap: 20px;
            color: #666;
            font-size: 13px;
            flex-wrap: wrap;
        }

        .announcement-meta span {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .announcement-actions {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .btn-action {
            background: none;
            border: 1px solid #e0e0e0;
            color: #666;
            padding: 6px 12px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .btn-action:hover {
            border-color: #00a1d6;
            color: #00a1d6;
        }

        .btn-action.btn-toggle.active {
            border-color: #48bb78;
            color: #48bb78;
        }

        .btn-action.btn-delete:hover {
            border-color: #c53030;
            color: #c53030;
        }

        .empty-state {
            background: white;
            padding: 60px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .empty-state i {
            font-size: 60px;
            color: #a0aec0;
            margin-bottom: 20px;
        }

        .empty-state h3 {
            color: #4a5568;
            margin-bottom: 10px;
        }

        .empty-state p {
            color: #718096;
        }

        .modal .form-label {
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }

        .modal .form-control, .modal .form-select {
            border: 2px solid #e0e0e0;
            font-size: 14px;
        }

        .modal .form-control:focus, .modal .form-select:focus {
            border-color: #00a1d6;
            box-shadow: 0 0 0 0.2rem rgba(0,161,214,0.15);
        }

        .modal .form-check-input:checked {
            background-color: #00a1d6;
            border-color: #00a1d6;
        }

        .modal-header {
            background: #00a1d6;
            color: white;
        }

        .modal-header .btn-close {
            filter: brightness(0) invert(1);
        }

        .btn-save {
            background: #00a1d6;
            color: white;
            border: none;
            padding: 8px 24px;
        }

        .btn-save:hover {
            background: #0088b2;
            color: white;
        }

        .action-url-group {
            display: none;
        }

        .action-url-group.show {
            display: block;
        }

        @media (max-width: 992px) {
            .stats-row {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 576px) {
            .stats-row {
                grid-template-columns: 1fr;
            }

            .container {
                padding: 0 15px;
            }

            .announcement-header {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <?php $active_page = 'announcements'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon total">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $totalCount; ?></h3>
                    <p>总公告数</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon active">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $activeCount; ?></h3>
                    <p>已激活</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon current">
                    <i class="fas fa-play-circle"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $currentCount; ?></h3>
                    <p>生效中</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon expired">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $expiredCount; ?></h3>
                    <p>已过期</p>
                </div>
            </div>
        </div>

        <div class="toolbar">
            <div class="toolbar-left">
                <label for="filterType"><strong>类型筛选：</strong></label>
                <select id="filterType" class="filter-select">
                    <option value="all">全部类型</option>
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                </select>
                <label for="filterStatus"><strong>状态：</strong></label>
                <select id="filterStatus" class="filter-select">
                    <option value="all">全部状态</option>
                    <option value="current">生效中</option>
                    <option value="expired">已过期</option>
                    <option value="inactive">未激活</option>
                </select>
            </div>
            <button class="btn-add" data-bs-toggle="modal" data-bs-target="#announcementModal" onclick="openAddModal()">
                <i class="fas fa-plus"></i> 添加公告
            </button>
        </div>

        <?php if (empty($announcements)): ?>
            <div class="empty-state">
                <i class="fas fa-bullhorn"></i>
                <h3>暂无公告</h3>
                <p>点击上方"添加公告"按钮创建第一条公告</p>
            </div>
        <?php else: ?>
            <div class="announcement-list" id="announcementList">
                <?php foreach ($announcements as $ann):
                    $start = strtotime($ann['start_time']);
                    $end = strtotime($ann['end_time']);
                    $isExpired = $end < $now;
                    $isCurrent = $ann['is_active'] && $start <= $now && $end >= $now;
                    $statusClass = 'inactive';
                    $statusLabel = '未激活';
                    if ($isExpired && $ann['is_active']) {
                        $statusClass = 'expired';
                        $statusLabel = '已过期';
                    } elseif ($isCurrent) {
                        $statusClass = 'current';
                        $statusLabel = '生效中';
                    } elseif ($ann['is_active']) {
                        $statusClass = 'active';
                        $statusLabel = '已激活';
                    }
                    $cardClass = 'type-' . $ann['type'];
                    if ($isExpired) $cardClass .= ' is-expired';
                ?>
                    <div class="announcement-card <?php echo $cardClass; ?>"
                         data-type="<?php echo htmlspecialchars($ann['type']); ?>"
                         data-status="<?php echo $statusClass; ?>"
                         data-id="<?php echo htmlspecialchars($ann['id']); ?>">
                        <div class="announcement-header">
                            <div class="announcement-title-wrap">
                                <div class="announcement-badges">
                                    <span class="badge-type <?php echo htmlspecialchars($ann['type']); ?>">
                                        <?php echo strtoupper(htmlspecialchars($ann['type'])); ?>
                                    </span>
                                    <span class="badge-status <?php echo $statusClass; ?>">
                                        <?php echo $statusLabel; ?>
                                    </span>
                                    <?php if ($ann['dismissible']): ?>
                                        <span class="badge-status inactive">可关闭</span>
                                    <?php endif; ?>
                                </div>
                                <h2 class="announcement-title"><?php echo htmlspecialchars($ann['title']); ?></h2>
                                <span class="announcement-id"><?php echo htmlspecialchars($ann['id']); ?></span>
                            </div>
                            <div class="announcement-actions">
                                <button class="btn-action btn-toggle <?php echo $ann['is_active'] ? 'active' : ''; ?>"
                                        onclick="toggleActive('<?php echo htmlspecialchars($ann['id']); ?>')"
                                        title="<?php echo $ann['is_active'] ? '停用' : '激活'; ?>">
                                    <i class="fas fa-power-off"></i>
                                    <?php echo $ann['is_active'] ? '停用' : '激活'; ?>
                                </button>
                                <button class="btn-action" onclick="openEditModal('<?php echo htmlspecialchars($ann['id']); ?>')" title="编辑">
                                    <i class="fas fa-edit"></i> 编辑
                                </button>
                                <button class="btn-action btn-delete" onclick="deleteAnnouncement('<?php echo htmlspecialchars($ann['id']); ?>')" title="删除">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="announcement-content"><?php echo htmlspecialchars($ann['content']); ?></div>
                        <div class="announcement-meta">
                            <span><i class="fas fa-calendar-alt"></i> <?php echo htmlspecialchars($ann['start_time']); ?> ~ <?php echo htmlspecialchars($ann['end_time']); ?></span>
                            <?php if ($ann['action_type'] !== 'none'): ?>
                                <span><i class="fas fa-external-link-alt"></i> 动作: <?php echo htmlspecialchars($ann['action_type']); ?><?php if ($ann['action_url']): ?> (<?php echo htmlspecialchars($ann['action_url']); ?>)<?php endif; ?></span>
                            <?php endif; ?>
                            <?php if ($ann['min_version']): ?>
                                <span><i class="fas fa-arrow-down"></i> 最低版本: <?php echo htmlspecialchars($ann['min_version']); ?></span>
                            <?php endif; ?>
                            <?php if ($ann['max_version']): ?>
                                <span><i class="fas fa-arrow-up"></i> 最高版本: <?php echo htmlspecialchars($ann['max_version']); ?></span>
                            <?php endif; ?>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </div>

    <div class="modal fade" id="announcementModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="modalTitle">添加公告</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <form id="announcementForm" enctype="multipart/form-data">
                    <div class="modal-body">
                        <input type="hidden" id="formAction" value="add">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="formId" class="form-label">公告ID <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="formId" name="id" placeholder="如 ann_20260508_001" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="formType" class="form-label">类型 <span class="text-danger">*</span></label>
                                <select class="form-select" id="formType" name="type" required>
                                    <option value="info">info</option>
                                    <option value="warning">warning</option>
                                    <option value="error">error</option>
                                </select>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="formTitle" class="form-label">标题 <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="formTitle" name="title" required>
                        </div>
                        <div class="mb-3">
                            <label for="formContent" class="form-label">内容 <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="formContent" name="content" rows="4" required></textarea>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="formStartTime" class="form-label">开始时间 <span class="text-danger">*</span></label>
                                <input type="datetime-local" class="form-control" id="formStartTime" name="start_time" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="formEndTime" class="form-label">结束时间 <span class="text-danger">*</span></label>
                                <input type="datetime-local" class="form-control" id="formEndTime" name="end_time" required>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="formActionType" class="form-label">动作类型</label>
                                <select class="form-select" id="formActionType" name="action_type">
                                    <option value="none">none</option>
                                    <option value="update">update</option>
                                    <option value="url">url</option>
                                </select>
                            </div>
                            <div class="col-md-6 mb-3 action-url-group" id="actionUrlGroup">
                                <label for="formActionUrl" class="form-label">动作URL</label>
                                <div class="btn-group btn-group-sm mb-2" role="group">
                                    <input type="radio" class="btn-check" name="actionUrlMode" id="actionModeUrl" value="url" checked>
                                    <label class="btn btn-outline-primary" for="actionModeUrl"><i class="fas fa-link"></i> URL</label>
                                    <input type="radio" class="btn-check" name="actionUrlMode" id="actionModeUpload" value="upload">
                                    <label class="btn btn-outline-primary" for="actionModeUpload"><i class="fas fa-upload"></i> 上传</label>
                                </div>
                                <div id="actionUrlInput">
                                    <input type="text" class="form-control" id="formActionUrl" name="action_url">
                                </div>
                                <div id="actionUploadInput" class="d-none">
                                    <input type="file" class="form-control form-control-sm" id="formActionFile" accept=".jpg,.jpeg,.png,.gif,.webp,.svg,.pdf,.zip,.html,.htm">
                                    <div class="progress mt-1 d-none" id="actionUploadProgress" style="height:6px;">
                                        <div class="progress-bar progress-bar-striped progress-bar-animated" id="actionUploadProgressBar" style="width:0%"></div>
                                    </div>
                                    <div class="form-text" id="actionUploadStatus"></div>
                                </div>
                                <input type="hidden" id="formActionUrlHidden" name="action_url">
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="formMinVersion" class="form-label">最低版本</label>
                                <input type="text" class="form-control" id="formMinVersion" name="min_version" placeholder="可选">
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="formMaxVersion" class="form-label">最高版本</label>
                                <input type="text" class="form-control" id="formMaxVersion" name="max_version" placeholder="可选">
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <div class="form-check mt-2">
                                    <input class="form-check-input" type="checkbox" id="formDismissible" name="dismissible" value="1" checked>
                                    <label class="form-check-label" for="formDismissible">可关闭</label>
                                </div>
                            </div>
                            <div class="col-md-6 mb-3">
                                <div class="form-check mt-2">
                                    <input class="form-check-input" type="checkbox" id="formIsActive" name="is_active" value="1" checked>
                                    <label class="form-check-label" for="formIsActive">激活</label>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="submit" class="btn btn-save">保存</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const announcements = <?php echo json_encode($announcements); ?>;
        let uploadedActionUrl = '';

        document.getElementById('formActionType').addEventListener('change', function() {
            const group = document.getElementById('actionUrlGroup');
            if (this.value === 'url') {
                group.classList.add('show');
            } else {
                group.classList.remove('show');
            }
        });

        document.querySelectorAll('input[name="actionUrlMode"]').forEach(function(radio) {
            radio.addEventListener('change', function() {
                var isUpload = this.value === 'upload';
                document.getElementById('actionUrlInput').classList.toggle('d-none', isUpload);
                document.getElementById('actionUploadInput').classList.toggle('d-none', !isUpload);
            });
        });

        document.getElementById('formActionFile').addEventListener('change', function() {
            if (this.files.length > 0) {
                uploadActionFile(this.files[0]);
            }
        });

        function uploadActionFile(file) {
            var progressDiv = document.getElementById('actionUploadProgress');
            var progressBar = document.getElementById('actionUploadProgressBar');
            var statusDiv = document.getElementById('actionUploadStatus');

            progressDiv.classList.remove('d-none');
            progressBar.style.width = '0%';
            statusDiv.textContent = '正在上传 ' + file.name + '...';

            var formData = new FormData();
            formData.append('action', 'upload_file');
            formData.append('file', file);

            var xhr = new XMLHttpRequest();
            xhr.open('POST', 'announcements.php', true);

            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    var pct = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = pct + '%';
                }
            });

            xhr.addEventListener('load', function() {
                try {
                    var data = JSON.parse(xhr.responseText);
                    if (data.success) {
                        uploadedActionUrl = data.action_url;
                        document.getElementById('formActionUrlHidden').value = data.action_url;
                        progressBar.style.width = '100%';
                        progressBar.classList.remove('progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        statusDiv.textContent = '上传成功: ' + data.file_name;
                        statusDiv.style.color = '#276749';
                    } else {
                        progressBar.classList.add('bg-danger');
                        progressBar.classList.remove('progress-bar-animated');
                        statusDiv.textContent = data.message || '上传失败';
                        statusDiv.style.color = '#c53030';
                    }
                } catch (e) {
                    progressBar.classList.add('bg-danger');
                    statusDiv.textContent = '上传响应解析失败';
                    statusDiv.style.color = '#c53030';
                }
            });

            xhr.addEventListener('error', function() {
                progressBar.classList.add('bg-danger');
                progressBar.classList.remove('progress-bar-animated');
                statusDiv.textContent = '网络错误，上传失败';
                statusDiv.style.color = '#c53030';
            });

            xhr.send(formData);
        }

        document.getElementById('filterType').addEventListener('change', filterAnnouncements);
        document.getElementById('filterStatus').addEventListener('change', filterAnnouncements);

        function filterAnnouncements() {
            const typeFilter = document.getElementById('filterType').value;
            const statusFilter = document.getElementById('filterStatus').value;
            const cards = document.querySelectorAll('.announcement-card');

            cards.forEach(card => {
                const typeMatch = typeFilter === 'all' || card.dataset.type === typeFilter;
                const statusMatch = statusFilter === 'all' || card.dataset.status === statusFilter;
                card.style.display = (typeMatch && statusMatch) ? 'block' : 'none';
            });
        }

        function openAddModal() {
            document.getElementById('modalTitle').textContent = '添加公告';
            document.getElementById('formAction').value = 'add';
            document.getElementById('announcementForm').reset();
            document.getElementById('formId').readOnly = false;
            document.getElementById('formDismissible').checked = true;
            document.getElementById('formIsActive').checked = true;
            document.getElementById('actionUrlGroup').classList.remove('show');
            uploadedActionUrl = '';
            document.getElementById('formActionUrlHidden').value = '';
            document.getElementById('actionModeUrl').checked = true;
            document.getElementById('actionUrlInput').classList.remove('d-none');
            document.getElementById('actionUploadInput').classList.add('d-none');
            document.getElementById('actionUploadProgress').classList.add('d-none');
            document.getElementById('actionUploadStatus').textContent = '';
        }

        function openEditModal(id) {
            const ann = announcements.find(a => a.id === id);
            if (!ann) return;

            document.getElementById('modalTitle').textContent = '编辑公告';
            document.getElementById('formAction').value = 'edit';
            document.getElementById('formId').value = ann.id;
            document.getElementById('formId').readOnly = true;
            document.getElementById('formType').value = ann.type;
            document.getElementById('formTitle').value = ann.title;
            document.getElementById('formContent').value = ann.content;
            document.getElementById('formStartTime').value = ann.start_time ? ann.start_time.replace(' ', 'T') : '';
            document.getElementById('formEndTime').value = ann.end_time ? ann.end_time.replace(' ', 'T') : '';
            document.getElementById('formActionType').value = ann.action_type || 'none';
            document.getElementById('formActionUrl').value = ann.action_url || '';
            document.getElementById('formActionUrlHidden').value = ann.action_url || '';
            if (ann.action_url && ann.action_url.startsWith('/uploads/')) {
                document.getElementById('actionModeUpload').checked = true;
                document.getElementById('actionUrlInput').classList.add('d-none');
                document.getElementById('actionUploadInput').classList.remove('d-none');
                uploadedActionUrl = ann.action_url;
                document.getElementById('actionUploadStatus').textContent = '已上传: ' + ann.action_url;
                document.getElementById('actionUploadStatus').style.color = '#276749';
            } else {
                document.getElementById('actionModeUrl').checked = true;
                document.getElementById('actionUrlInput').classList.remove('d-none');
                document.getElementById('actionUploadInput').classList.add('d-none');
                uploadedActionUrl = '';
            }
            document.getElementById('actionUploadProgress').classList.add('d-none');
            document.getElementById('formMinVersion').value = ann.min_version || '';
            document.getElementById('formMaxVersion').value = ann.max_version || '';
            document.getElementById('formDismissible').checked = ann.dismissible == 1;
            document.getElementById('formIsActive').checked = ann.is_active == 1;

            if (ann.action_type === 'url') {
                document.getElementById('actionUrlGroup').classList.add('show');
            } else {
                document.getElementById('actionUrlGroup').classList.remove('show');
            }

            new bootstrap.Modal(document.getElementById('announcementModal')).show();
        }

        document.getElementById('announcementForm').addEventListener('submit', function(e) {
            e.preventDefault();

            var actionType = document.getElementById('formActionType').value;
            if (actionType === 'url') {
                var mode = document.querySelector('input[name="actionUrlMode"]:checked');
                if (mode && mode.value === 'upload') {
                    document.getElementById('formActionUrlHidden').value = uploadedActionUrl;
                } else {
                    document.getElementById('formActionUrlHidden').value = document.getElementById('formActionUrl').value.trim();
                }
            }

            const formData = new FormData(this);
            formData.append('action', document.getElementById('formAction').value);
            formData.set('action_url', document.getElementById('formActionUrlHidden').value);

            fetch('announcements.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert(data.message || '操作失败');
                }
            })
            .catch(error => {
                console.error('请求错误:', error);
                alert('操作失败，请稍后重试');
            });
        });

        function toggleActive(id) {
            const formData = new FormData();
            formData.append('action', 'toggle_active');
            formData.append('id', id);

            fetch('announcements.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert(data.message || '操作失败');
                }
            })
            .catch(error => {
                console.error('请求错误:', error);
                alert('操作失败，请稍后重试');
            });
        }

        function deleteAnnouncement(id) {
            if (!confirm('确定要删除此公告吗？删除后无法恢复！')) return;

            const formData = new FormData();
            formData.append('action', 'delete');
            formData.append('id', id);

            fetch('announcements.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const card = document.querySelector(`.announcement-card[data-id="${id}"]`);
                    if (card) {
                        card.style.opacity = '0';
                        card.style.transition = 'opacity 0.3s';
                        setTimeout(() => card.remove(), 300);
                    }
                    setTimeout(() => location.reload(), 350);
                } else {
                    alert(data.message || '删除失败');
                }
            })
            .catch(error => {
                console.error('请求错误:', error);
                alert('删除失败，请稍后重试');
            });
        }
    </script>
</body>
</html>
