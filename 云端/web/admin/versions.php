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

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    header('Content-Type: application/json');
    $action = $_POST['action'];

    if ($action === 'upload_file') {
        if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
            $errMsg = '上传失败';
            if (isset($_FILES['file'])) {
                $errCodes = [
                    UPLOAD_ERR_INI_SIZE => '文件超过服务器大小限制(upload_max_filesize)',
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
        $allowedExts = ['exe', 'dmg', 'deb', 'rpm', 'AppImage', 'zip', '7z', 'tar.gz', 'msi', 'pkg'];
        $originalName = $file['name'];
        $ext = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
        if ($ext === 'gz' && strtolower(pathinfo(basename($originalName, '.gz'), PATHINFO_EXTENSION)) === 'tar') {
            $ext = 'tar.gz';
        }

        $extCheck = $ext;
        if ($ext === 'tar.gz') $extCheck = 'tar';
        if (!in_array($extCheck, array_map('strtolower', $allowedExts)) && !in_array($ext, array_map('strtolower', $allowedExts))) {
            echo json_encode(['success' => false, 'message' => '不支持的文件类型，允许: ' . implode(', ', $allowedExts)]);
            exit;
        }

        $uploadDir = __DIR__ . '/../uploads/versions/';
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
            echo json_encode(['success' => false, 'message' => '文件保存失败，请检查目录权限']);
            exit;
        }

        $downloadUrl = '/uploads/versions/' . $fileName;
        $fileSize = filesize($destPath);

        echo json_encode([
            'success' => true,
            'message' => '文件上传成功',
            'download_url' => $downloadUrl,
            'file_size' => $fileSize,
            'file_name' => $fileName
        ]);
        exit;
    }

    if ($action === 'add') {
        $version = trim($_POST['version'] ?? '');
        $channel = $_POST['channel'] ?? 'stable';
        $platform = $_POST['platform'] ?? 'windows';
        $release_notes = trim($_POST['release_notes'] ?? '');
        $download_url = trim($_POST['download_url'] ?? '');
        $file_size = $_POST['file_size'] ?? null;
        $sha256 = trim($_POST['sha256'] ?? '');
        $min_supported = trim($_POST['min_supported'] ?? '');
        $force_update = isset($_POST['force_update']) ? 1 : 0;
        $is_active = isset($_POST['is_active']) ? 1 : 0;
        $release_date = $_POST['release_date'] ?? date('Y-m-d');

        if ($version === '' || !preg_match('/^\d+\.\d+\.\d+$/', $version)) {
            echo json_encode(['success' => false, 'message' => '版本号格式不正确，需为 x.y.z 格式']);
            exit;
        }
        if ($download_url === '') {
            echo json_encode(['success' => false, 'message' => '下载地址不能为空']);
            exit;
        }
        if (!in_array($channel, ['stable', 'beta'])) {
            echo json_encode(['success' => false, 'message' => '无效的通道']);
            exit;
        }
        if (!in_array($platform, ['windows', 'mac', 'linux'])) {
            echo json_encode(['success' => false, 'message' => '无效的平台']);
            exit;
        }

        try {
            $stmt = $pdo->prepare('INSERT INTO app_version (version, channel, platform, release_notes, download_url, file_size, sha256, min_supported, force_update, is_active, release_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
            $stmt->execute([$version, $channel, $platform, $release_notes, $download_url, $file_size ?: null, $sha256 ?: null, $min_supported ?: null, $force_update, $is_active, $release_date]);
            echo json_encode(['success' => true, 'message' => '版本添加成功']);
        } catch (PDOException $e) {
            if ($e->getCode() == 23000) {
                echo json_encode(['success' => false, 'message' => '该版本号已存在']);
            } else {
                echo json_encode(['success' => false, 'message' => '添加失败：' . $e->getMessage()]);
            }
        }
        exit;
    }

    if ($action === 'edit') {
        $id = $_POST['id'] ?? null;
        $version = trim($_POST['version'] ?? '');
        $channel = $_POST['channel'] ?? 'stable';
        $platform = $_POST['platform'] ?? 'windows';
        $release_notes = trim($_POST['release_notes'] ?? '');
        $download_url = trim($_POST['download_url'] ?? '');
        $file_size = $_POST['file_size'] ?? null;
        $sha256 = trim($_POST['sha256'] ?? '');
        $min_supported = trim($_POST['min_supported'] ?? '');
        $force_update = isset($_POST['force_update']) ? 1 : 0;
        $is_active = isset($_POST['is_active']) ? 1 : 0;
        $release_date = $_POST['release_date'] ?? date('Y-m-d');

        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少版本ID']);
            exit;
        }
        if ($version === '' || !preg_match('/^\d+\.\d+\.\d+$/', $version)) {
            echo json_encode(['success' => false, 'message' => '版本号格式不正确，需为 x.y.z 格式']);
            exit;
        }
        if ($download_url === '') {
            echo json_encode(['success' => false, 'message' => '下载地址不能为空']);
            exit;
        }

        try {
            $stmt = $pdo->prepare('UPDATE app_version SET version=?, channel=?, platform=?, release_notes=?, download_url=?, file_size=?, sha256=?, min_supported=?, force_update=?, is_active=?, release_date=? WHERE id=?');
            $stmt->execute([$version, $channel, $platform, $release_notes, $download_url, $file_size ?: null, $sha256 ?: null, $min_supported ?: null, $force_update, $is_active, $release_date, $id]);
            echo json_encode(['success' => true, 'message' => '版本更新成功']);
        } catch (PDOException $e) {
            if ($e->getCode() == 23000) {
                echo json_encode(['success' => false, 'message' => '该版本号已存在']);
            } else {
                echo json_encode(['success' => false, 'message' => '更新失败：' . $e->getMessage()]);
            }
        }
        exit;
    }

    if ($action === 'delete') {
        $id = $_POST['id'] ?? null;
        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少版本ID']);
            exit;
        }
        try {
            $stmt = $pdo->prepare('DELETE FROM app_version WHERE id=?');
            $stmt->execute([$id]);
            echo json_encode(['success' => true, 'message' => '版本已删除']);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '删除失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'toggle_active') {
        $id = $_POST['id'] ?? null;
        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少版本ID']);
            exit;
        }
        try {
            $stmt = $pdo->prepare('UPDATE app_version SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id=?');
            $stmt->execute([$id]);
            $stmt = $pdo->prepare('SELECT is_active FROM app_version WHERE id=?');
            $stmt->execute([$id]);
            $newState = $stmt->fetchColumn();
            echo json_encode(['success' => true, 'message' => '状态已更新', 'is_active' => (int)$newState]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '操作失败：' . $e->getMessage()]);
        }
        exit;
    }

    echo json_encode(['success' => false, 'message' => '未知操作']);
    exit;
}

$versions = $pdo->query('SELECT * FROM app_version ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
$totalCount = count($versions);
$stableCount = 0;
$betaCount = 0;
$activeCount = 0;
foreach ($versions as $v) {
    if ($v['channel'] === 'stable') $stableCount++;
    if ($v['channel'] === 'beta') $betaCount++;
    if ($v['is_active']) $activeCount++;
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>版本管理 - B站视频解析下载工具</title>
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
        .stat-icon.stable { background: #68d391; }
        .stat-icon.beta { background: #fbd38d; }
        .stat-icon.active { background: #00a1d6; }

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

        .content-card {
            background: white;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .content-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .content-header h2 {
            font-size: 20px;
            font-weight: 600;
            color: #333;
        }

        .btn-add {
            background: #00a1d6;
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .btn-add:hover {
            background: #0088b4;
            color: white;
        }

        .version-table {
            width: 100%;
        }

        .version-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
            padding: 12px;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
        }

        .version-table td {
            padding: 12px;
            vertical-align: middle;
            border-bottom: 1px solid #e9ecef;
        }

        .badge-channel {
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-stable {
            background: #d4edda;
            color: #155724;
        }

        .badge-beta {
            background: #fff3cd;
            color: #856404;
        }

        .badge-platform {
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            background: #e2e8f0;
            color: #4a5568;
        }

        .badge-yes {
            background: #fee2e2;
            color: #991b1b;
        }

        .badge-no {
            background: #f0f0f0;
            color: #999;
        }

        .toggle-btn {
            cursor: pointer;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            border: none;
            transition: all 0.3s;
        }

        .toggle-btn.active {
            background: #d4edda;
            color: #155724;
        }

        .toggle-btn.inactive {
            background: #f8d7da;
            color: #721c24;
        }

        .action-btns {
            display: flex;
            gap: 8px;
        }

        .action-btns .btn {
            padding: 5px 10px;
            font-size: 13px;
        }

        .modal-header {
            background: #00a1d6;
            color: white;
        }

        .modal-header .btn-close {
            filter: brightness(0) invert(1);
        }

        .form-label {
            font-weight: 600;
            color: #333;
            margin-bottom: 6px;
        }

        .form-control:focus, .form-select:focus {
            border-color: #00a1d6;
            box-shadow: 0 0 0 0.2rem rgba(0,161,214,0.25);
        }

        .form-check-input:checked {
            background-color: #00a1d6;
            border-color: #00a1d6;
        }

        .empty-state {
            padding: 60px;
            text-align: center;
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
        }
    </style>
</head>
<body>
    <?php $active_page = 'versions'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon total">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $totalCount; ?></h3>
                    <p>总版本数</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon stable">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $stableCount; ?></h3>
                    <p>Stable</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon beta">
                    <i class="fas fa-flask"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $betaCount; ?></h3>
                    <p>Beta</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon active">
                    <i class="fas fa-toggle-on"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $activeCount; ?></h3>
                    <p>已激活</p>
                </div>
            </div>
        </div>

        <div class="content-card">
            <div class="content-header">
                <h2><i class="fas fa-code-branch"></i> 版本列表</h2>
                <button class="btn btn-add" onclick="openAddModal()">
                    <i class="fas fa-plus"></i> 添加版本
                </button>
            </div>

            <?php if (empty($versions)): ?>
                <div class="empty-state">
                    <i class="fas fa-box-open"></i>
                    <h3>暂无版本记录</h3>
                    <p>点击上方"添加版本"按钮发布新版本</p>
                </div>
            <?php else: ?>
                <div class="table-responsive">
                    <table class="version-table table">
                        <thead>
                            <tr>
                                <th>版本号</th>
                                <th>通道</th>
                                <th>平台</th>
                                <th>强制更新</th>
                                <th>状态</th>
                                <th>发布日期</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($versions as $v): ?>
                            <tr data-id="<?php echo $v['id']; ?>">
                                <td><strong><?php echo htmlspecialchars($v['version']); ?></strong></td>
                                <td><span class="badge-channel badge-<?php echo $v['channel']; ?>"><?php echo $v['channel']; ?></span></td>
                                <td><span class="badge-platform"><?php echo htmlspecialchars($v['platform']); ?></span></td>
                                <td><span class="badge-channel <?php echo $v['force_update'] ? 'badge-yes' : 'badge-no'; ?>"><?php echo $v['force_update'] ? '是' : '否'; ?></span></td>
                                <td>
                                    <button class="toggle-btn <?php echo $v['is_active'] ? 'active' : 'inactive'; ?>" onclick="toggleActive(<?php echo $v['id']; ?>)">
                                        <?php echo $v['is_active'] ? '已激活' : '未激活'; ?>
                                    </button>
                                </td>
                                <td><?php echo htmlspecialchars($v['release_date'] ?? ''); ?></td>
                                <td>
                                    <div class="action-btns">
                                        <button class="btn btn-sm btn-outline-primary" onclick="openEditModal(<?php echo $v['id']; ?>)">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        <button class="btn btn-sm btn-outline-danger" onclick="deleteVersion(<?php echo $v['id']; ?>)">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </div>
    </div>

    <div class="modal fade" id="versionModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="modalTitle">添加版本</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form id="versionForm" enctype="multipart/form-data">
                    <div class="modal-body">
                        <input type="hidden" name="action" id="formAction" value="add">
                        <input type="hidden" name="id" id="formId" value="">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">版本号 <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" name="version" id="formVersion" placeholder="例如: 1.9.0" required pattern="\d+\.\d+\.\d+">
                            </div>
                            <div class="col-md-3 mb-3">
                                <label class="form-label">通道</label>
                                <select class="form-select" name="channel" id="formChannel">
                                    <option value="stable">stable</option>
                                    <option value="beta">beta</option>
                                </select>
                            </div>
                            <div class="col-md-3 mb-3">
                                <label class="form-label">平台</label>
                                <select class="form-select" name="platform" id="formPlatform">
                                    <option value="windows">windows</option>
                                    <option value="mac">mac</option>
                                    <option value="linux">linux</option>
                                </select>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">更新日志</label>
                            <textarea class="form-control" name="release_notes" id="formReleaseNotes" rows="3"></textarea>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">下载文件 <span class="text-danger">*</span></label>
                            <div class="btn-group mb-2" role="group">
                                <input type="radio" class="btn-check" name="urlMode" id="modeUpload" value="upload" checked>
                                <label class="btn btn-outline-primary btn-sm" for="modeUpload"><i class="fas fa-upload"></i> 上传文件</label>
                                <input type="radio" class="btn-check" name="urlMode" id="modeUrl" value="url">
                                <label class="btn btn-outline-primary btn-sm" for="modeUrl"><i class="fas fa-link"></i> 填写URL</label>
                            </div>
                            <div id="uploadSection">
                                <input type="file" class="form-control" id="formFile" accept=".exe,.dmg,.deb,.rpm,.AppImage,.zip,.7z,.msi,.pkg,.tar.gz">
                                <div class="progress mt-2 d-none" id="uploadProgress">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" id="uploadProgressBar" role="progressbar" style="width: 0%">0%</div>
                                </div>
                                <div class="form-text mt-1" id="uploadStatus"></div>
                            </div>
                            <div id="urlSection" class="d-none">
                                <input type="url" class="form-control" name="download_url" id="formDownloadUrl" placeholder="https://...">
                            </div>
                            <input type="hidden" name="download_url" id="formDownloadUrlHidden">
                        </div>
                        <div class="row">
                            <div class="col-md-4 mb-3">
                                <label class="form-label">文件大小 (字节)</label>
                                <input type="number" class="form-control" name="file_size" id="formFileSize" min="0">
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">最低支持版本</label>
                                <input type="text" class="form-control" name="min_supported" id="formMinSupported" placeholder="例如: 1.0.0">
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">发布日期</label>
                                <input type="date" class="form-control" name="release_date" id="formReleaseDate">
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">SHA256校验值</label>
                            <input type="text" class="form-control" name="sha256" id="formSha256" placeholder="64位十六进制字符串" maxlength="64">
                        </div>
                        <div class="d-flex gap-4">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" name="force_update" id="formForceUpdate" value="1">
                                <label class="form-check-label" for="formForceUpdate">强制更新</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" name="is_active" id="formIsActive" value="1" checked>
                                <label class="form-check-label" for="formIsActive">激活</label>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="submit" class="btn btn-add" id="submitBtn">添加</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const versionData = <?php echo json_encode($versions); ?>;
        let versionModal;
        let uploadedUrl = '';
        let uploadedSize = 0;

        document.addEventListener('DOMContentLoaded', function() {
            versionModal = new bootstrap.Modal(document.getElementById('versionModal'));
            document.getElementById('formReleaseDate').value = new Date().toISOString().split('T')[0];

            document.querySelectorAll('input[name="urlMode"]').forEach(function(radio) {
                radio.addEventListener('change', function() {
                    var isUpload = this.value === 'upload';
                    document.getElementById('uploadSection').classList.toggle('d-none', !isUpload);
                    document.getElementById('urlSection').classList.toggle('d-none', isUpload);
                });
            });

            document.getElementById('formFile').addEventListener('change', function() {
                if (this.files.length > 0) {
                    uploadFile(this.files[0]);
                }
            });
        });

        function uploadFile(file) {
            var progressDiv = document.getElementById('uploadProgress');
            var progressBar = document.getElementById('uploadProgressBar');
            var statusDiv = document.getElementById('uploadStatus');

            progressDiv.classList.remove('d-none');
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            statusDiv.textContent = '正在上传 ' + file.name + '...';

            var formData = new FormData();
            formData.append('action', 'upload_file');
            formData.append('file', file);

            var xhr = new XMLHttpRequest();
            xhr.open('POST', 'versions.php', true);

            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    var pct = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = pct + '%';
                    progressBar.textContent = pct + '%';
                }
            });

            xhr.addEventListener('load', function() {
                try {
                    var data = JSON.parse(xhr.responseText);
                    if (data.success) {
                        uploadedUrl = data.download_url;
                        uploadedSize = data.file_size;
                        document.getElementById('formDownloadUrlHidden').value = data.download_url;
                        document.getElementById('formFileSize').value = data.file_size;
                        progressBar.style.width = '100%';
                        progressBar.textContent = '100%';
                        progressBar.classList.remove('progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        statusDiv.textContent = '上传成功: ' + data.file_name + ' (' + formatSize(data.file_size) + ')';
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

        function formatSize(bytes) {
            if (bytes === 0) return '0 B';
            var units = ['B', 'KB', 'MB', 'GB'];
            var i = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
        }

        function openAddModal() {
            document.getElementById('modalTitle').textContent = '添加版本';
            document.getElementById('formAction').value = 'add';
            document.getElementById('formId').value = '';
            document.getElementById('submitBtn').textContent = '添加';
            document.getElementById('versionForm').reset();
            document.getElementById('formReleaseDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('formIsActive').checked = true;
            uploadedUrl = '';
            uploadedSize = 0;
            document.getElementById('formDownloadUrlHidden').value = '';
            document.getElementById('uploadProgress').classList.add('d-none');
            document.getElementById('uploadStatus').textContent = '';
            document.getElementById('modeUpload').checked = true;
            document.getElementById('uploadSection').classList.remove('d-none');
            document.getElementById('urlSection').classList.add('d-none');
            versionModal.show();
        }

        function openEditModal(id) {
            const v = versionData.find(item => item.id == id);
            if (!v) return;

            document.getElementById('modalTitle').textContent = '编辑版本';
            document.getElementById('formAction').value = 'edit';
            document.getElementById('formId').value = v.id;
            document.getElementById('submitBtn').textContent = '保存';
            document.getElementById('formVersion').value = v.version;
            document.getElementById('formChannel').value = v.channel;
            document.getElementById('formPlatform').value = v.platform;
            document.getElementById('formReleaseNotes').value = v.release_notes || '';
            document.getElementById('formFileSize').value = v.file_size || '';
            document.getElementById('formSha256').value = v.sha256 || '';
            document.getElementById('formMinSupported').value = v.min_supported || '';
            document.getElementById('formForceUpdate').checked = v.force_update == 1;
            document.getElementById('formIsActive').checked = v.is_active == 1;
            document.getElementById('formReleaseDate').value = v.release_date || '';

            if (v.download_url && v.download_url.startsWith('/uploads/')) {
                document.getElementById('modeUpload').checked = true;
                document.getElementById('uploadSection').classList.remove('d-none');
                document.getElementById('urlSection').classList.add('d-none');
                document.getElementById('formDownloadUrlHidden').value = v.download_url;
                uploadedUrl = v.download_url;
                uploadedSize = v.file_size || 0;
                document.getElementById('uploadStatus').textContent = '已上传: ' + v.download_url + (v.file_size ? ' (' + formatSize(v.file_size) + ')' : '');
                document.getElementById('uploadStatus').style.color = '#276749';
            } else {
                document.getElementById('modeUrl').checked = true;
                document.getElementById('uploadSection').classList.add('d-none');
                document.getElementById('urlSection').classList.remove('d-none');
                document.getElementById('formDownloadUrl').value = v.download_url || '';
                document.getElementById('formDownloadUrlHidden').value = v.download_url || '';
            }
            document.getElementById('uploadProgress').classList.add('d-none');
            versionModal.show();
        }

        document.getElementById('versionForm').addEventListener('submit', function(e) {
            e.preventDefault();

            var mode = document.querySelector('input[name="urlMode"]:checked').value;
            if (mode === 'upload') {
                document.getElementById('formDownloadUrlHidden').value = uploadedUrl;
                if (!uploadedUrl) {
                    alert('请先上传文件');
                    return;
                }
            } else {
                var urlVal = document.getElementById('formDownloadUrl').value.trim();
                document.getElementById('formDownloadUrlHidden').value = urlVal;
                if (!urlVal) {
                    alert('请填写下载URL');
                    return;
                }
            }

            var formData = new FormData(this);
            formData.set('download_url', document.getElementById('formDownloadUrlHidden').value);

            fetch('versions.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    versionModal.hide();
                    location.reload();
                } else {
                    alert(data.message || '操作失败');
                }
            })
            .catch(error => {
                alert('请求失败，请稍后重试');
            });
        });

        function toggleActive(id) {
            const formData = new FormData();
            formData.append('action', 'toggle_active');
            formData.append('id', id);

            fetch('versions.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const row = document.querySelector('tr[data-id="' + id + '"]');
                    if (row) {
                        const btn = row.querySelector('.toggle-btn');
                        if (data.is_active) {
                            btn.textContent = '已激活';
                            btn.className = 'toggle-btn active';
                        } else {
                            btn.textContent = '未激活';
                            btn.className = 'toggle-btn inactive';
                        }
                    }
                } else {
                    alert(data.message || '操作失败');
                }
            })
            .catch(error => {
                alert('请求失败，请稍后重试');
            });
        }

        function deleteVersion(id) {
            if (!confirm('确定要删除此版本吗？删除后无法恢复！')) return;

            const formData = new FormData();
            formData.append('action', 'delete');
            formData.append('id', id);

            fetch('versions.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const row = document.querySelector('tr[data-id="' + id + '"]');
                    if (row) {
                        row.style.opacity = '0';
                        row.style.transition = 'opacity 0.3s';
                        setTimeout(() => location.reload(), 300);
                    }
                } else {
                    alert(data.message || '删除失败');
                }
            })
            .catch(error => {
                alert('请求失败，请稍后重试');
            });
        }
    </script>
</body>
</html>
