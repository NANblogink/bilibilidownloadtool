<?php
require_once 'auth.php';
require_admin_login();

$pdo = new PDO('sqlite:' . __DIR__ . '/../../data/bilidown.db');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$pdo->exec('CREATE TABLE IF NOT EXISTS beta_tester (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(64) NOT NULL UNIQUE,
    device_name VARCHAR(100) DEFAULT "",
    platform VARCHAR(10) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');

$apiToken = defined('API_TOKEN') ? API_TOKEN : '';
if (!$apiToken) {
    $configPath = __DIR__ . '/../../data/admin_config.php';
    if (file_exists($configPath)) {
        require_once $configPath;
    }
    $apiToken = defined('API_TOKEN') ? API_TOKEN : '';
}

// 处理 POST 请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    header('Content-Type: application/json');
    $action = $_POST['action'];

    if ($action === 'add') {
        $clientId = trim($_POST['client_id'] ?? '');
        $deviceName = trim($_POST['device_name'] ?? '');
        if (empty($clientId)) {
            echo json_encode(['success' => false, 'message' => '设备码不能为空']);
            exit;
        }
        try {
            $stmt = $pdo->prepare('INSERT OR IGNORE INTO beta_tester (client_id, device_name) VALUES (?, ?)');
            $stmt->execute([$clientId, $deviceName]);
            $affected = $stmt->rowCount();
            if ($affected > 0) {
                echo json_encode(['success' => true, 'message' => '内测设备添加成功']);
            } else {
                echo json_encode(['success' => false, 'message' => '该设备已在内测名单中']);
            }
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '添加失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'remove') {
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少设备ID']);
            exit;
        }
        try {
            $stmt = $pdo->prepare('DELETE FROM beta_tester WHERE id = ?');
            $stmt->execute([$id]);
            echo json_encode(['success' => true, 'message' => '内测设备已移除']);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '移除失败：' . $e->getMessage()]);
        }
        exit;
    }

    echo json_encode(['success' => false, 'message' => '未知操作']);
    exit;
}

$testers = $pdo->query('SELECT * FROM beta_tester ORDER BY added_at DESC')->fetchAll(PDO::FETCH_ASSOC);
$totalCount = count($testers);

// 统计已上报设备信息（从 stat_device 表关联）
$deviceStats = [];
try {
    $stmt = $pdo->query('SELECT client_id, platform, version, last_seen FROM stat_device');
    foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $d) {
        $deviceStats[$d['client_id']] = $d;
    }
} catch (\Exception $e) {
    // stat_device 表可能不存在
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>内测设备管理 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 30px; }
        .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; }
        .stat-icon { width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; font-size: 28px; color: white; }
        .stat-icon.total { background: #667eea; }
        .stat-icon.beta { background: #fbd38d; }
        .stat-icon.active { background: #48bb78; }
        .stat-info h3 { font-size: 28px; font-weight: 700; color: #333; margin-bottom: 5px; }
        .stat-info p { color: #666; font-size: 14px; }
        .content-card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .content-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .content-header h2 { font-size: 20px; font-weight: 600; color: #333; }
        .btn-add { background: #00a1d6; color: white; border: none; padding: 10px 20px; font-size: 14px; cursor: pointer; transition: background 0.3s; }
        .btn-add:hover { background: #0088b4; color: white; }
        .tester-table { width: 100%; }
        .tester-table th { background: #f8f9fa; font-weight: 600; color: #333; padding: 12px; border-bottom: 2px solid #dee2e6; white-space: nowrap; }
        .tester-table td { padding: 12px; vertical-align: middle; border-bottom: 1px solid #e9ecef; }
        .device-code { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #4a5568; word-break: break-all; }
        .badge-platform { padding: 4px 10px; font-size: 12px; font-weight: 600; background: #e2e8f0; color: #4a5568; }
        .empty-state { padding: 60px; text-align: center; }
        .empty-state i { font-size: 60px; color: #a0aec0; margin-bottom: 20px; }
        .empty-state h3 { color: #4a5568; margin-bottom: 10px; }
        .empty-state p { color: #718096; }
        .modal-header { background: #00a1d6; color: white; }
        .modal-header .btn-close { filter: brightness(0) invert(1); }
        .form-label { font-weight: 600; color: #333; margin-bottom: 6px; }
        .form-control:focus, .form-select:focus { border-color: #00a1d6; box-shadow: 0 0 0 0.2rem rgba(0,161,214,0.25); }
        .copy-btn { background: none; border: none; color: #00a1d6; cursor: pointer; font-size: 13px; padding: 2px 6px; }
        .copy-btn:hover { color: #0088b4; }
        @media (max-width: 768px) { .stats-row { grid-template-columns: 1fr; } .container { padding: 0 15px; } }
    </style>
</head>
<body>
    <?php $active_page = 'beta_testers'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon total"><i class="fas fa-users"></i></div>
                <div class="stat-info">
                    <h3><?php echo $totalCount; ?></h3>
                    <p>内测设备总数</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon beta"><i class="fas fa-flask"></i></div>
                <div class="stat-info">
                    <h3><?php
                        $activeCount = 0;
                        foreach ($testers as $t) {
                            if (isset($deviceStats[$t['client_id']])) $activeCount++;
                        }
                        echo $activeCount;
                    ?></h3>
                    <p>已活跃设备</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon active"><i class="fas fa-mobile-alt"></i></div>
                <div class="stat-info">
                    <h3><?php echo $totalCount - $activeCount; ?></h3>
                    <p>未上报设备</p>
                </div>
            </div>
        </div>

        <div class="content-card">
            <div class="content-header">
                <h2><i class="fas fa-vial"></i> 内测设备列表</h2>
                <button class="btn btn-add" onclick="openAddModal()">
                    <i class="fas fa-plus"></i> 添加内测设备
                </button>
            </div>

            <?php if (empty($testers)): ?>
                <div class="empty-state">
                    <i class="fas fa-user-plus"></i>
                    <h3>暂无内测设备</h3>
                    <p>添加设备码后，对应设备将能收到 beta 通道的版本推送</p>
                </div>
            <?php else: ?>
                <div class="table-responsive">
                    <table class="tester-table table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>设备码 (client_id)</th>
                                <th>设备名称</th>
                                <th>平台</th>
                                <th>客户端版本</th>
                                <th>最后活跃</th>
                                <th>加入时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($testers as $t): ?>
                            <tr data-id="<?php echo $t['id']; ?>">
                                <td><?php echo $t['id']; ?></td>
                                <td>
                                    <span class="device-code"><?php echo htmlspecialchars($t['client_id']); ?></span>
                                    <button class="copy-btn" onclick="copyText('<?php echo htmlspecialchars($t['client_id']); ?>')">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </td>
                                <td><?php echo htmlspecialchars($t['device_name'] ?: '-'); ?></td>
                                <td>
                                    <?php
                                        $plat = $deviceStats[$t['client_id']]['platform'] ?? $t['platform'] ?? '';
                                        echo $plat ? '<span class="badge-platform">' . htmlspecialchars($plat) . '</span>' : '-';
                                    ?>
                                </td>
                                <td><?php
                                    $ver = $deviceStats[$t['client_id']]['version'] ?? $t['version'] ?? '';
                                    echo $ver ? htmlspecialchars($ver) : '-';
                                ?></td>
                                <td style="font-size: 12px; color: #666;"><?php
                                    $lastSeen = $deviceStats[$t['client_id']]['last_seen'] ?? '';
                                    echo $lastSeen ? htmlspecialchars($lastSeen) : '-';
                                ?></td>
                                <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($t['added_at']); ?></td>
                                <td>
                                    <button class="btn btn-sm btn-outline-danger" onclick="removeTester(<?php echo $t['id']; ?>)">
                                        <i class="fas fa-trash"></i> 移除
                                    </button>
                                </td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </div>

        <div class="content-card mt-4">
            <h2 style="font-size: 18px; font-weight: 600; color: #333; margin-bottom: 15px;">
                <i class="fas fa-info-circle"></i> 内测推送说明
            </h2>
            <ul style="color: #555; line-height: 1.8; padding-left: 20px;">
                <li><strong>正式推送</strong>：在「版本管理」页面添加版本时选择 <code>stable</code> 通道，所有用户都能收到更新</li>
                <li><strong>内测推送</strong>：在「版本管理」页面添加版本时选择 <code>beta</code> 通道，仅本页面的内测设备能收到更新</li>
                <li><strong>设备码</strong>：即客户端的 <code>client_id</code>，可在「数据统计」页面查看已上报的设备列表</li>
                <li>客户端检查更新时会自动附带设备码，服务端据此判断是否返回 beta 版本</li>
            </ul>
        </div>
    </div>

    <div class="modal fade" id="addModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">添加内测设备</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form id="addForm">
                    <div class="modal-body">
                        <input type="hidden" name="action" value="add">
                        <div class="mb-3">
                            <label class="form-label">设备码 (client_id) <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" name="client_id" id="inputClientId" placeholder="粘贴设备的 client_id" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">设备名称/备注</label>
                            <input type="text" class="form-control" name="device_name" id="inputDeviceName" placeholder="例如：测试机A">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="submit" class="btn btn-add">添加</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let addModal;
        document.addEventListener('DOMContentLoaded', function() {
            addModal = new bootstrap.Modal(document.getElementById('addModal'));
        });

        function openAddModal() {
            document.getElementById('addForm').reset();
            addModal.show();
        }

        document.getElementById('addForm').addEventListener('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            fetch('beta_testers.php', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    addModal.hide();
                    location.reload();
                } else {
                    alert(data.message || '操作失败');
                }
            })
            .catch(() => alert('请求失败，请稍后重试'));
        });

        function removeTester(id) {
            if (!confirm('确定要移除该内测设备吗？移除后该设备将不再收到 beta 版本推送。')) return;
            var formData = new FormData();
            formData.append('action', 'remove');
            formData.append('id', id);
            fetch('beta_testers.php', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert(data.message || '移除失败');
                }
            })
            .catch(() => alert('请求失败，请稍后重试'));
        }

        function copyText(text) {
            navigator.clipboard.writeText(text).then(function() {
                var btn = event.target.closest('.copy-btn');
                var original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(function() { btn.innerHTML = original; }, 1000);
            });
        }
    </script>
</body>
</html>
