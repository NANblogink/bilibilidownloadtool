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

$apiToken = defined('API_TOKEN') ? API_TOKEN : '';

$files = $pdo->query("SELECT * FROM remote_file WHERE is_active = 1 ORDER BY file_path")->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>远程文件管理 - B站视频解析下载工具</title>
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
        .file-table { width: 100%; border-collapse: collapse; }
        .file-table th { background: #f7fafc; padding: 12px 15px; text-align: left; color: #333; font-weight: 600; border-bottom: 2px solid #e2e8f0; }
        .file-table td { padding: 12px 15px; border-bottom: 1px solid #f0f0f0; }
        .file-table tr:hover { background: #f7fafc; }
        .file-path { font-family: 'Consolas', monospace; font-size: 13px; color: #2d3748; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .badge-all { background: #e6fffa; color: #234e52; }
        .badge-win { background: #ebf8ff; color: #2a4365; }
        .badge-mac { background: #faf5ff; color: #553c9a; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
        .modal.show { display: flex; }
        .modal-content { background: white; padding: 30px; border-radius: 12px; width: 90%; max-width: 600px; max-height: 80vh; overflow-y: auto; }
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
        .form-group textarea { min-height: 200px; font-family: 'Consolas', monospace; font-size: 13px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .action-btns { display: flex; gap: 8px; }
        .action-btns .btn { padding: 5px 12px; font-size: 12px; }
        .empty-state { text-align: center; padding: 40px; color: #999; }
        @media (max-width: 768px) {
            .container { padding: 0 15px; }
            .form-row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <?php $active_page = 'file_manage'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h4 style="margin-bottom: 0;"><i class="fas fa-folder-open"></i> 远程文件列表</h4>
                <button class="btn btn-primary" onclick="openModal()"><i class="fas fa-plus"></i> 新建文件</button>
            </div>

            <?php if (empty($files)): ?>
                <div class="empty-state">
                    <i class="fas fa-folder-open" style="font-size: 48px; margin-bottom: 15px; color: #ccc;"></i>
                    <p>暂无远程文件</p>
                </div>
            <?php else: ?>
                <table class="file-table">
                    <thead>
                        <tr>
                            <th>文件路径</th>
                            <th>大小</th>
                            <th>目标平台</th>
                            <th>版本限制</th>
                            <th>更新时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($files as $f): ?>
                            <tr>
                                <td class="file-path"><?php echo htmlspecialchars($f['file_path']); ?></td>
                                <td><?php echo number_format($f['file_size']); ?> B</td>
                                <td>
                                    <span class="badge badge-<?php echo $f['target_platform'] === 'all' ? 'all' : 'win'; ?>">
                                        <?php echo htmlspecialchars($f['target_platform']); ?>
                                    </span>
                                </td>
                                <td style="font-size: 12px; color: #666;">
                                    <?php if ($f['min_version']): ?>≥ V<?php echo htmlspecialchars($f['min_version']); ?><?php endif; ?>
                                    <?php if ($f['min_version'] && $f['max_version']): ?> ~ <?php endif; ?>
                                    <?php if ($f['max_version']): ?>≤ V<?php echo htmlspecialchars($f['max_version']); ?><?php endif; ?>
                                    <?php if (!$f['min_version'] && !$f['max_version']): ?>无限制<?php endif; ?>
                                </td>
                                <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($f['updated_at']); ?></td>
                                <td>
                                    <div class="action-btns">
                                        <button class="btn btn-primary" onclick="editFile(<?php echo $f['id']; ?>)">编辑</button>
                                        <button class="btn btn-danger" onclick="deleteFile(<?php echo $f['id']; ?>)">删除</button>
                                    </div>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
    </div>

    <div id="fileModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h5 id="modalTitle">新建文件</h5>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="form-group">
                <label>文件路径</label>
                <input type="text" id="filePath" placeholder="例如: config/theme.json">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>目标平台</label>
                    <select id="targetPlatform">
                        <option value="all">全部平台</option>
                        <option value="windows">Windows</option>
                        <option value="macos">macOS</option>
                        <option value="linux">Linux</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>最低版本</label>
                    <input type="text" id="minVersion" placeholder="如 2.0.0 (留空不限制)">
                </div>
            </div>
            <div class="form-group">
                <label>最高版本</label>
                <input type="text" id="maxVersion" placeholder="如 2.1.0 (留空不限制)">
            </div>
            <div class="form-group">
                <label>文件内容</label>
                <textarea id="fileContent" placeholder="文件内容..."></textarea>
            </div>
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button class="btn" style="background: #e2e8f0;" onclick="closeModal()">取消</button>
                <button class="btn btn-success" onclick="saveFile()">保存</button>
            </div>
        </div>
    </div>

    <script>
        const API_TOKEN = '<?php echo $apiToken; ?>';
        let editingId = null;
        let fileCache = {};

        function openModal() {
            editingId = null;
            document.getElementById('modalTitle').textContent = '新建文件';
            document.getElementById('filePath').value = '';
            document.getElementById('filePath').disabled = false;
            document.getElementById('targetPlatform').value = 'all';
            document.getElementById('minVersion').value = '';
            document.getElementById('maxVersion').value = '';
            document.getElementById('fileContent').value = '';
            document.getElementById('fileModal').classList.add('show');
        }

        function closeModal() {
            document.getElementById('fileModal').classList.remove('show');
        }

        function editFile(id) {
            fetch('/api/v1/file_manage?action=read&id=' + id, {
                headers: { 'X-API-Token': API_TOKEN }
            })
            .then(r => r.json())
            .then(result => {
                if (result.code !== 0) { alert('加载失败: ' + result.message); return; }
                const f = result.data;
                editingId = f.id;
                document.getElementById('modalTitle').textContent = '编辑文件';
                document.getElementById('filePath').value = f.file_path;
                document.getElementById('filePath').disabled = true;
                document.getElementById('targetPlatform').value = f.target_platform;
                document.getElementById('minVersion').value = f.min_version || '';
                document.getElementById('maxVersion').value = f.max_version || '';
                document.getElementById('fileContent').value = f.file_content || '';
                document.getElementById('fileModal').classList.add('show');
            });
        }

        function saveFile() {
            const filePath = document.getElementById('filePath').value.trim();
            const fileContent = document.getElementById('fileContent').value;
            const targetPlatform = document.getElementById('targetPlatform').value;
            const minVersion = document.getElementById('minVersion').value.trim();
            const maxVersion = document.getElementById('maxVersion').value.trim();

            if (!filePath) { alert('请输入文件路径'); return; }

            const body = JSON.stringify({
                action: 'write',
                file_path: filePath,
                file_content: fileContent,
                target_platform: targetPlatform,
                min_version: minVersion,
                max_version: maxVersion
            });

            fetch('/api/v1/file_manage', {
                method: 'POST',
                headers: { 'X-API-Token': API_TOKEN, 'Content-Type': 'application/json' },
                body: body
            })
            .then(r => r.json())
            .then(result => {
                if (result.code === 0) {
                    alert('保存成功');
                    closeModal();
                    location.reload();
                } else {
                    alert('保存失败: ' + result.message);
                }
            });
        }

        function deleteFile(id) {
            if (!confirm('确定删除此文件吗？')) return;
            fetch('/api/v1/file_manage?id=' + id, {
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

        document.getElementById('fileModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    </script>
</body>
</html>
