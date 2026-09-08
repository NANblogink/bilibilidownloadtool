<?php
require_once 'auth.php';
require_admin_login();

$dbPath = __DIR__ . '/../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (\Exception $e) {
    die('数据库连接失败: ' . $e->getMessage());
}

// 统一使用 api/v1/patch/index.php 的表结构
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

$apiToken = defined('API_TOKEN') ? API_TOKEN : '';
if (!$apiToken) {
    $configPath = __DIR__ . '/../../data/admin_config.php';
    if (file_exists($configPath)) {
        require_once $configPath;
    }
    $apiToken = defined('API_TOKEN') ? API_TOKEN : '';
}

$patches = $pdo->query("SELECT * FROM patch_package WHERE is_active = 1 ORDER BY created_at DESC")->fetchAll(PDO::FETCH_ASSOC);

// 修正版本排序：用 created_at 而非字符串版本号
$versions = $pdo->query("SELECT version FROM app_version WHERE is_active = 1 ORDER BY created_at DESC")->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>增量包管理 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 30px; }
        .section { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; border-radius: 8px; }
        .section h4 { margin-bottom: 20px; color: #333; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .btn { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.3s; }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5a67d8; }
        .btn-danger { background: #e53e3e; color: white; }
        .btn-danger:hover { background: #c53030; }
        .btn-success { background: #48bb78; color: white; }
        .btn-success:hover { background: #38a169; }
        .patch-table { width: 100%; border-collapse: collapse; }
        .patch-table th { background: #f7fafc; padding: 12px 15px; text-align: left; color: #333; font-weight: 600; border-bottom: 2px solid #e2e8f0; }
        .patch-table td { padding: 12px 15px; border-bottom: 1px solid #f0f0f0; }
        .patch-table tr:hover { background: #f7fafc; }
        .version-badge { background: #edf2f7; color: #2d3748; padding: 4px 10px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 13px; font-weight: 500; }
        .arrow-icon { color: #667eea; margin: 0 8px; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .badge-win { background: #ebf8ff; color: #2a4365; }
        .badge-mac { background: #faf5ff; color: #553c9a; }
        .size-text { font-family: 'Consolas', monospace; font-size: 13px; color: #4a5568; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
        .modal.show { display: flex; }
        .modal-content { background: white; padding: 30px; border-radius: 12px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h5 { margin: 0; font-size: 18px; font-weight: 600; }
        .close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #999; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 500; color: #333; font-size: 14px; }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%; padding: 10px 12px; border: 2px solid #e2e8f0; border-radius: 6px;
            font-size: 14px; transition: border-color 0.3s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            border-color: #667eea; outline: none;
        }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .action-btns { display: flex; gap: 8px; }
        .action-btns .btn { padding: 5px 12px; font-size: 12px; }
        .empty-state { text-align: center; padding: 40px; color: #999; }
        .file-drop { border: 2px dashed #cbd5e0; border-radius: 8px; padding: 30px; text-align: center; cursor: pointer; transition: all 0.3s; }
        .file-drop:hover { border-color: #667eea; background: #f7fafc; }
        .file-drop i { font-size: 32px; color: #a0aec0; margin-bottom: 10px; }
        .file-drop p { color: #718096; margin: 0; }
        .file-name { margin-top: 10px; color: #2d3748; font-weight: 500; }
        @media (max-width: 768px) {
            .container { padding: 0 15px; }
            .form-row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <?php $active_page = 'patches'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h4 style="margin-bottom: 0;"><i class="fas fa-list"></i> 增量包列表</h4>
                <button class="btn btn-primary" onclick="openModal()"><i class="fas fa-plus"></i> 上传增量包</button>
            </div>

            <?php if (empty($patches)): ?>
                <div class="empty-state">
                    <i class="fas fa-box-open" style="font-size: 48px; margin-bottom: 15px; color: #ccc;"></i>
                    <p>暂无增量包</p>
                </div>
            <?php else: ?>
                <table class="patch-table">
                    <thead>
                        <tr>
                            <th>版本升级</th>
                            <th>平台</th>
                            <th>文件名</th>
                            <th>大小</th>
                            <th>创建时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($patches as $p): ?>
                            <tr>
                                <td>
                                    <span class="version-badge">V<?php echo htmlspecialchars($p['from_version']); ?></span>
                                    <i class="fas fa-arrow-right arrow-icon"></i>
                                    <span class="version-badge" style="background: #c6f6d5; color: #22543d;">V<?php echo htmlspecialchars($p['to_version']); ?></span>
                                </td>
                                <td>
                                    <span class="badge badge-<?php echo $p['platform'] === 'windows' ? 'win' : 'mac'; ?>">
                                        <?php echo htmlspecialchars($p['platform']); ?>
                                    </span>
                                </td>
                                <td style="font-family: 'Consolas', monospace; font-size: 12px; color: #4a5568;">
                                    <?php echo htmlspecialchars(basename($p['patch_url'] ?? '')); ?>
                                </td>
                                <td class="size-text"><?php echo formatSize($p['patch_size'] ?? 0); ?></td>
                                <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($p['created_at']); ?></td>
                                <td>
                                    <div class="action-btns">
                                        <button class="btn btn-primary" onclick="downloadPatch(<?php echo $p['id']; ?>)">下载</button>
                                        <button class="btn btn-danger" onclick="deletePatch(<?php echo $p['id']; ?>)">删除</button>
                                    </div>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
    </div>

    <div id="patchModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h5>上传增量包</h5>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>源版本</label>
                    <select id="fromVersion">
                        <?php foreach ($versions as $v): ?>
                            <option value="<?php echo htmlspecialchars($v['version']); ?>">V<?php echo htmlspecialchars($v['version']); ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="form-group">
                    <label>目标版本</label>
                    <select id="toVersion">
                        <?php foreach ($versions as $v): ?>
                            <option value="<?php echo htmlspecialchars($v['version']); ?>">V<?php echo htmlspecialchars($v['version']); ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label>平台</label>
                <select id="platform">
                    <option value="windows">Windows</option>
                    <option value="macos">macOS</option>
                    <option value="linux">Linux</option>
                </select>
            </div>
            <div class="form-group">
                <label>增量包文件 (zip)</label>
                <div class="file-drop" onclick="document.getElementById('fileInput').click()">
                    <i class="fas fa-cloud-upload-alt"></i>
                    <p>点击选择文件或拖拽到此处</p>
                    <div id="fileNameDisplay" class="file-name"></div>
                </div>
                <input type="file" id="fileInput" accept=".zip" style="display: none;" onchange="handleFileSelect(this)">
            </div>
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button class="btn" style="background: #e2e8f0;" onclick="closeModal()">取消</button>
                <button class="btn btn-success" onclick="uploadPatch()">上传</button>
            </div>
        </div>
    </div>

    <script>
        const API_TOKEN = '<?php echo $apiToken; ?>';
        let selectedFile = null;

        function openModal() {
            selectedFile = null;
            document.getElementById('fileNameDisplay').textContent = '';
            document.getElementById('patchModal').classList.add('show');
        }

        function closeModal() {
            document.getElementById('patchModal').classList.remove('show');
        }

        function handleFileSelect(input) {
            if (input.files.length > 0) {
                selectedFile = input.files[0];
                document.getElementById('fileNameDisplay').textContent =
                    selectedFile.name + ' (' + formatBytes(selectedFile.size) + ')';
            }
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function uploadPatch() {
            if (!selectedFile) { alert('请选择增量包文件'); return; }

            const formData = new FormData();
            formData.append('action', 'upload');
            formData.append('from_version', document.getElementById('fromVersion').value);
            formData.append('to_version', document.getElementById('toVersion').value);
            formData.append('platform', document.getElementById('platform').value);
            formData.append('file', selectedFile);

            fetch('/api/v1/patch', {
                method: 'POST',
                headers: { 'X-API-Token': API_TOKEN },
                body: formData
            })
            .then(r => r.json())
            .then(result => {
                if (result.code === 0) {
                    alert('上传成功');
                    closeModal();
                    location.reload();
                } else {
                    alert('上传失败: ' + result.message);
                }
            });
        }

        function downloadPatch(id) {
            window.open('/api/v1/patch?action=download&id=' + id, '_blank');
        }

        function deletePatch(id) {
            if (!confirm('确定删除此增量包吗？')) return;
            fetch('/api/v1/patch?id=' + id, {
                method: 'DELETE',
                headers: { 'X-API-Token': API_TOKEN }
            })
            .then(r => r.json())
            .then(result => {
                if (result.code === 0) {
                    alert('删除成功');
                    location.reload();
                } else {
                    alert('删除失败: ' + result.message);
                }
            });
        }

        document.getElementById('patchModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    </script>
</body>
</html>
<?php
function formatSize($bytes) {
    if ($bytes === 0 || $bytes === null) return '0 B';
    $units = ['B', 'KB', 'MB', 'GB'];
    $i = floor(log($bytes, 1024));
    return round($bytes / pow(1024, $i), 2) . ' ' . $units[$i];
}
?>
