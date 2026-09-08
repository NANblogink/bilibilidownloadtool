<?php
require_once 'auth.php';
require_admin_login();

$pdo = new PDO('sqlite:' . __DIR__ . '/../../data/bilidown.db');
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$pdo->exec('CREATE TABLE IF NOT EXISTS beta_qq_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qq_number VARCHAR(20) NOT NULL UNIQUE,
    remark VARCHAR(100) DEFAULT "",
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)');
$pdo->exec('CREATE TABLE IF NOT EXISTS beta_device_bind (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qq_number VARCHAR(20) NOT NULL UNIQUE,
    client_id VARCHAR(64) NOT NULL UNIQUE,
    platform VARCHAR(10) DEFAULT "",
    version VARCHAR(20) DEFAULT "",
    bind_ip VARCHAR(45) DEFAULT "",
    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
)');

// 处理 POST
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    header('Content-Type: application/json');
    $action = $_POST['action'];

    if ($action === 'add_qq') {
        $qq = trim($_POST['qq'] ?? '');
        $remark = trim($_POST['remark'] ?? '');
        if (empty($qq)) {
            echo json_encode(['success' => false, 'message' => 'QQ号不能为空']);
            exit;
        }
        try {
            $stmt = $pdo->prepare('INSERT OR IGNORE INTO beta_qq_auth (qq_number, remark) VALUES (?, ?)');
            $stmt->execute([$qq, $remark]);
            echo json_encode(['success' => true, 'message' => $stmt->rowCount() > 0 ? '添加成功' : '该QQ号已存在']);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => '添加失败：' . $e->getMessage()]);
        }
        exit;
    }

    if ($action === 'remove_qq') {
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少ID']);
            exit;
        }
        $pdo->prepare('DELETE FROM beta_qq_auth WHERE id = ?')->execute([$id]);
        echo json_encode(['success' => true, 'message' => '已删除']);
        exit;
    }

    if ($action === 'unbind') {
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) {
            echo json_encode(['success' => false, 'message' => '缺少ID']);
            exit;
        }
        $pdo->prepare('DELETE FROM beta_device_bind WHERE id = ?')->execute([$id]);
        echo json_encode(['success' => true, 'message' => '设备已解绑']);
        exit;
    }

    if ($action === 'batch_add_qq') {
        $raw = $_POST['qq_list'] ?? '';
        $lines = array_filter(array_map('trim', explode("\n", $raw)));
        $added = 0;
        $skipped = 0;
        foreach ($lines as $line) {
            if (!preg_match('/^\d{5,12}$/', $line)) {
                $skipped++;
                continue;
            }
            $stmt = $pdo->prepare('INSERT OR IGNORE INTO beta_qq_auth (qq_number, remark) VALUES (?, "")');
            $stmt->execute([$line]);
            if ($stmt->rowCount() > 0) $added++;
            else $skipped++;
        }
        echo json_encode(['success' => true, 'message' => "添加{$added}个，跳过{$skipped}个"]);
        exit;
    }

    echo json_encode(['success' => false, 'message' => '未知操作']);
    exit;
}

$qqList = $pdo->query('SELECT * FROM beta_qq_auth ORDER BY created_at DESC')->fetchAll(PDO::FETCH_ASSOC);
$bindList = $pdo->query('SELECT * FROM beta_device_bind ORDER BY bound_at DESC')->fetchAll(PDO::FETCH_ASSOC);
$qqCount = count($qqList);
$bindCount = count($bindList);
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>内测授权管理 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 30px; }
        .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; border-radius: 8px; }
        .stat-icon { width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; font-size: 28px; color: white; border-radius: 12px; }
        .stat-icon.qq { background: #00a1d6; }
        .stat-icon.bind { background: #48bb78; }
        .stat-icon.log { background: #ed8936; }
        .stat-info h3 { font-size: 28px; font-weight: 700; color: #333; margin-bottom: 5px; }
        .stat-info p { color: #666; font-size: 14px; }
        .tab-card { background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        .tab-header { display: flex; border-bottom: 2px solid #e2e8f0; }
        .tab-btn { padding: 15px 30px; border: none; background: none; font-size: 15px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.3s; }
        .tab-btn.active { color: #00a1d6; border-bottom-color: #00a1d6; }
        .tab-content { padding: 25px; }
        .tab-pane { display: none; }
        .tab-pane.active { display: block; }
        .table th { background: #f8f9fa; font-weight: 600; color: #333; padding: 12px; border-bottom: 2px solid #dee2e6; white-space: nowrap; }
        .table td { padding: 12px; vertical-align: middle; border-bottom: 1px solid #e9ecef; }
        .device-code { font-family: 'Consolas', monospace; font-size: 12px; color: #4a5568; word-break: break-all; max-width: 200px; }
        .badge-qq { background: #ebf8ff; color: #2a4365; padding: 4px 10px; border-radius: 4px; font-weight: 600; }
        .badge-platform { background: #e2e8f0; color: #4a5568; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
        .btn-primary { background: #00a1d6; border: none; }
        .btn-primary:hover { background: #0088b4; }
        .empty-state { padding: 60px; text-align: center; }
        .empty-state i { font-size: 60px; color: #a0aec0; margin-bottom: 20px; }
        .modal-header { background: #00a1d6; color: white; }
        .modal-header .btn-close { filter: brightness(0) invert(1); }
        .form-label { font-weight: 600; color: #333; margin-bottom: 6px; }
        .form-control:focus, .form-select:focus { border-color: #00a1d6; box-shadow: 0 0 0 0.2rem rgba(0,161,214,0.25); }
        .copy-btn { background: none; border: none; color: #00a1d6; cursor: pointer; font-size: 13px; padding: 2px 6px; }
        .copy-btn:hover { color: #0088b4; }
        .info-box { background: #ebf8ff; border: 1px solid #bee3f8; border-radius: 8px; padding: 20px; margin-top: 20px; }
        .info-box h6 { color: #2a4365; font-weight: 600; margin-bottom: 10px; }
        .info-box ul { color: #555; line-height: 1.8; padding-left: 20px; margin: 0; }
        @media (max-width: 768px) { .stats-row { grid-template-columns: 1fr; } .container { padding: 0 15px; } }
    </style>
</head>
<body>
    <?php $active_page = 'beta_auth'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon qq"><i class="fas fa-user-check"></i></div>
                <div class="stat-info">
                    <h3><?php echo $qqCount; ?></h3>
                    <p>授权QQ号</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon bind"><i class="fas fa-mobile-alt"></i></div>
                <div class="stat-info">
                    <h3><?php echo $bindCount; ?></h3>
                    <p>已绑定设备</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon log"><i class="fas fa-shield-alt"></i></div>
                <div class="stat-info">
                    <h3><?php echo $qqCount - $bindCount > 0 ? $qqCount - $bindCount : 0; ?></h3>
                    <p>未绑定QQ号</p>
                </div>
            </div>
        </div>

        <div class="tab-card">
            <div class="tab-header">
                <button class="tab-btn active" onclick="switchTab('qq')"><i class="fas fa-user-check"></i> 授权QQ号管理</button>
                <button class="tab-btn" onclick="switchTab('bind')"><i class="fas fa-mobile-alt"></i> 设备绑定管理</button>
            </div>
            <div class="tab-content">
                <!-- Tab: 授权QQ -->
                <div class="tab-pane active" id="tab-qq">
                    <div class="d-flex justify-content-between mb-3">
                        <h5 style="font-weight: 600;">授权QQ号列表</h5>
                        <div>
                            <button class="btn btn-outline-primary btn-sm me-2" onclick="openBatchModal()"><i class="fas fa-list"></i> 批量导入</button>
                            <button class="btn btn-primary btn-sm" onclick="openAddQqModal()"><i class="fas fa-plus"></i> 添加QQ号</button>
                        </div>
                    </div>
                    <?php if (empty($qqList)): ?>
                        <div class="empty-state">
                            <i class="fas fa-user-plus"></i>
                            <h5 class="text-muted">暂无授权QQ号</h5>
                            <p class="text-muted">添加QQ号后，内测包用户输入对应QQ号即可绑定设备</p>
                        </div>
                    <?php else: ?>
                        <div class="table-responsive">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>QQ号</th>
                                        <th>备注</th>
                                        <th>状态</th>
                                        <th>添加时间</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($qqList as $q): ?>
                                    <tr>
                                        <td><?php echo $q['id']; ?></td>
                                        <td><span class="badge-qq"><?php echo htmlspecialchars($q['qq_number']); ?></span></td>
                                        <td><?php echo htmlspecialchars($q['remark'] ?: '-'); ?></td>
                                        <td>
                                            <?php if ($q['is_active']): ?>
                                                <span class="badge bg-success">启用</span>
                                            <?php else: ?>
                                                <span class="badge bg-secondary">禁用</span>
                                            <?php endif; ?>
                                        </td>
                                        <td style="font-size: 13px; color: #666;"><?php echo htmlspecialchars($q['created_at']); ?></td>
                                        <td>
                                            <button class="btn btn-sm btn-outline-danger" onclick="removeQq(<?php echo $q['id']; ?>)">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php endif; ?>
                </div>

                <!-- Tab: 设备绑定 -->
                <div class="tab-pane" id="tab-bind">
                    <div class="d-flex justify-content-between mb-3">
                        <h5 style="font-weight: 600;">已绑定设备列表</h5>
                    </div>
                    <?php if (empty($bindList)): ?>
                        <div class="empty-state">
                            <i class="fas fa-mobile-alt"></i>
                            <h5 class="text-muted">暂无绑定设备</h5>
                            <p class="text-muted">内测包用户输入QQ号验证后，设备将显示在此处</p>
                        </div>
                    <?php else: ?>
                        <div class="table-responsive">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>QQ号</th>
                                        <th>设备码 (client_id)</th>
                                        <th>平台</th>
                                        <th>版本</th>
                                        <th>绑定IP</th>
                                        <th>绑定时间</th>
                                        <th>最后活跃</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($bindList as $b): ?>
                                    <tr>
                                        <td><?php echo $b['id']; ?></td>
                                        <td><span class="badge-qq"><?php echo htmlspecialchars($b['qq_number']); ?></span></td>
                                        <td>
                                            <span class="device-code"><?php echo htmlspecialchars($b['client_id']); ?></span>
                                            <button class="copy-btn" onclick="copyText('<?php echo htmlspecialchars($b['client_id']); ?>')">
                                                <i class="fas fa-copy"></i>
                                            </button>
                                        </td>
                                        <td><span class="badge-platform"><?php echo htmlspecialchars($b['platform'] ?: '-'); ?></span></td>
                                        <td><?php echo htmlspecialchars($b['version'] ?: '-'); ?></td>
                                        <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($b['bind_ip'] ?: '-'); ?></td>
                                        <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($b['bound_at']); ?></td>
                                        <td style="font-size: 12px; color: #666;"><?php echo htmlspecialchars($b['last_active']); ?></td>
                                        <td>
                                            <button class="btn btn-sm btn-outline-warning" onclick="unbindDevice(<?php echo $b['id']; ?>, '<?php echo htmlspecialchars($b['qq_number']); ?>')">
                                                <i class="fas fa-unlink"></i> 解绑
                                            </button>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>

        <div class="info-box">
            <h6><i class="fas fa-info-circle"></i> 内测授权说明</h6>
            <ul>
                <li><strong>正式包</strong>：无需QQ授权，直接使用，检查更新走 stable 通道</li>
                <li><strong>内测包</strong>：首次启动需输入授权QQ号，绑定设备码后才能使用</li>
                <li><strong>一Q一机</strong>：每个QQ号只能绑定一台设备，设备码绑定后不再弹窗</li>
                <li><strong>防爆破</strong>：连续验证失败4次起进入冷却（5分钟~24小时逐级递增）</li>
                <li><strong>解绑</strong>：在「设备绑定管理」解绑后，该设备需重新输入QQ号</li>
                <li>内测包检查更新走 beta 通道，仅推送 beta 版本</li>
            </ul>
        </div>
    </div>

    <!-- 添加QQ号 Modal -->
    <div class="modal fade" id="addQqModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">添加授权QQ号</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form id="addQqForm">
                    <div class="modal-body">
                        <input type="hidden" name="action" value="add_qq">
                        <div class="mb-3">
                            <label class="form-label">QQ号 <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" name="qq" pattern="\d{5,12}" placeholder="输入QQ号" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">备注</label>
                            <input type="text" class="form-control" name="remark" placeholder="例如：测试员A">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="submit" class="btn btn-primary">添加</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- 批量导入 Modal -->
    <div class="modal fade" id="batchModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">批量导入QQ号</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form id="batchForm">
                    <div class="modal-body">
                        <input type="hidden" name="action" value="batch_add_qq">
                        <div class="mb-3">
                            <label class="form-label">QQ号列表（每行一个）</label>
                            <textarea class="form-control" name="qq_list" rows="10" placeholder="123456789&#10;987654321&#10;..." required></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="submit" class="btn btn-primary">批量导入</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }

        const addQqModal = new bootstrap.Modal(document.getElementById('addQqModal'));
        const batchModal = new bootstrap.Modal(document.getElementById('batchModal'));

        function openAddQqModal() {
            document.getElementById('addQqForm').reset();
            addQqModal.show();
        }

        function openBatchModal() {
            document.getElementById('batchForm').reset();
            batchModal.show();
        }

        document.getElementById('addQqForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('beta_auth.php', { method: 'POST', body: new FormData(this) })
            .then(r => r.json())
            .then(data => {
                if (data.success) { addQqModal.hide(); location.reload(); }
                else alert(data.message);
            });
        });

        document.getElementById('batchForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('beta_auth.php', { method: 'POST', body: new FormData(this) })
            .then(r => r.json())
            .then(data => {
                if (data.success) { batchModal.hide(); alert(data.message); location.reload(); }
                else alert(data.message);
            });
        });

        function removeQq(id) {
            if (!confirm('确定删除此授权QQ号吗？')) return;
            var fd = new FormData();
            fd.append('action', 'remove_qq');
            fd.append('id', id);
            fetch('beta_auth.php', { method: 'POST', body: fd })
            .then(r => r.json())
            .then(data => {
                if (data.success) location.reload();
                else alert(data.message);
            });
        }

        function unbindDevice(id, qq) {
            if (!confirm('确定解绑QQ ' + qq + ' 的设备吗？\n解绑后该设备需重新输入QQ号验证。')) return;
            var fd = new FormData();
            fd.append('action', 'unbind');
            fd.append('id', id);
            fetch('beta_auth.php', { method: 'POST', body: fd })
            .then(r => r.json())
            .then(data => {
                if (data.success) location.reload();
                else alert(data.message);
            });
        }

        function copyText(text) {
            navigator.clipboard.writeText(text).then(function() {
                var btn = event.target.closest('.copy-btn');
                var orig = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(function() { btn.innerHTML = orig; }, 1000);
            });
        }
    </script>
</body>
</html>
