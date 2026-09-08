<?php
require_once 'auth.php';
require_admin_login();

$dbPath = __DIR__ . '/../../data/bilidown.db';
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// 确保新字段存在
$migrations = [
    'stat_error' => ['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""', 'log_file' => 'VARCHAR(500) DEFAULT ""'],
    'crash_log' => ['error_line' => 'INTEGER DEFAULT 0', 'error_file' => 'VARCHAR(500) DEFAULT ""', 'ip_address' => 'VARCHAR(45) DEFAULT ""'],
];
foreach ($migrations as $table => $cols) {
    foreach ($cols as $col => $def) {
        try { $pdo->exec("ALTER TABLE $table ADD COLUMN $col $def"); } catch (\Exception $e) {}
    }
}

$clientId = trim($_GET['client_id'] ?? '');
$device = null;
$errors = [];
$crashes = [];
$events = [];
$logFiles = [];
$errorTotal = 0;
$crashTotal = 0;
$eventTotal = 0;

if (!empty($clientId)) {
    $limit = 500;
    $offset = max(0, (int)($_GET['offset'] ?? 0));

    $stmt = $pdo->prepare('SELECT * FROM stat_device WHERE client_id = ?');
    $stmt->execute([$clientId]);
    $device = $stmt->fetch(PDO::FETCH_ASSOC);

    $stmt = $pdo->prepare('SELECT COUNT(*) FROM stat_error WHERE client_id = ?');
    $stmt->execute([$clientId]);
    $errorTotal = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT * FROM stat_error WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $stmt->execute([$clientId, $limit, $offset]);
    $errors = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $stmt = $pdo->prepare('SELECT COUNT(*) FROM crash_log WHERE client_id = ?');
    $stmt->execute([$clientId]);
    $crashTotal = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT * FROM crash_log WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $stmt->execute([$clientId, $limit, $offset]);
    $crashes = $stmt->fetchAll(PDO::FETCH_ASSOC);

    $stmt = $pdo->prepare('SELECT COUNT(*) FROM stat_event WHERE client_id = ?');
    $stmt->execute([$clientId]);
    $eventTotal = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare('SELECT * FROM stat_event WHERE client_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?');
    $stmt->execute([$clientId, $limit, $offset]);
    $events = $stmt->fetchAll(PDO::FETCH_ASSOC);

    foreach ($errors as $err) {
        if (!empty($err['log_file'])) {
            $logPath = __DIR__ . '/../../' . $err['log_file'];
            if (file_exists($logPath)) {
                $logFiles[$err['id']] = file_get_contents($logPath);
            }
        }
    }
}

// 获取最近有错误的设备列表（用于快速选择）
$recentDevices = $pdo->query("SELECT DISTINCT se.client_id, sd.version, sd.platform, sd.last_seen, COUNT(*) as error_count FROM stat_error se LEFT JOIN stat_device sd ON se.client_id = sd.client_id WHERE se.client_id != '' GROUP BY se.client_id ORDER BY MAX(se.created_at) DESC LIMIT 50")->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>设备日志查询 - 后台管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1600px; margin: 20px auto; padding: 0 20px; }
        .nav { background: #fff; padding: 15px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; gap: 20px; align-items: center; flex-wrap: wrap; }
        .nav a { color: #333; text-decoration: none; padding: 6px 14px; border: 1px solid #ddd; }
        .nav a.active { background: #333; color: #fff; border-color: #333; }
        .nav .logout { margin-left: auto; color: #d33; }

        .search-bar { background: #fff; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .search-bar input { width: 400px; padding: 10px 14px; border: 2px solid #e0e0e0; font-size: 14px; }
        .search-bar input:focus { border-color: #333; outline: none; }
        .search-bar button { padding: 10px 24px; background: #333; color: #fff; border: none; font-size: 14px; cursor: pointer; }

        .device-list { background: #fff; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .device-list h3 { margin-bottom: 12px; font-size: 16px; }
        .device-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; max-height: 300px; overflow-y: auto; }
        .device-chip { padding: 8px 12px; border: 1px solid #e0e0e0; cursor: pointer; font-size: 12px; font-family: monospace; display: flex; justify-content: space-between; }
        .device-chip:hover { background: #f0f0f0; border-color: #333; }
        .device-chip .count { color: #d33; font-weight: 700; }

        .info-card { background: #fff; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .info-card table { width: 100%; border-collapse: collapse; }
        .info-card td { padding: 6px 12px; border-bottom: 1px solid #f0f0f0; }
        .info-card td:first-child { font-weight: 600; width: 120px; color: #666; }

        .section { background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .section-header { padding: 14px 20px; font-weight: 700; font-size: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
        .section-header .badge { background: #333; color: #fff; padding: 2px 10px; font-size: 12px; }

        .log-table { width: 100%; border-collapse: collapse; }
        .log-table th { background: #f8f8f8; padding: 10px 12px; text-align: left; font-size: 12px; font-weight: 600; border-bottom: 2px solid #eee; }
        .log-table td { padding: 8px 12px; font-size: 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
        .log-table tr:hover { background: #fafafa; }
        .log-table .mono { font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; }
        .log-table .error-msg { max-width: 400px; word-break: break-all; }
        .log-table .stack { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
        .log-table .stack:hover { white-space: pre-wrap; }

        .log-content { background: #1e1e1e; color: #d4d4d4; padding: 16px; font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; max-height: 500px; overflow: auto; white-space: pre-wrap; margin: 10px 0; }
    </style>
</head>
<body>
<div class="container">
    <div class="nav">
        <a href="index.php">反馈管理</a>
        <a href="versions.php">版本管理</a>
        <a href="stats.php">数据统计</a>
        <a href="stats_v2.php">统计V2</a>
        <a href="device_logs.php" class="active">设备日志</a>
        <a href="logout.php" class="logout">退出</a>
    </div>

    <div class="search-bar">
        <form method="GET">
            <input type="text" name="client_id" placeholder="输入设备码 (client_id) 查询该设备的所有错误/崩溃/事件日志" value="<?php echo htmlspecialchars($clientId); ?>" style="width: 600px;">
            <button type="submit">查询</button>
        </form>
    </div>

    <?php if (!empty($clientId)): ?>
    <div class="info-card">
        <h3 style="margin-bottom: 12px;">设备信息</h3>
        <table>
            <tr><td>设备码</td><td class="mono"><?php echo htmlspecialchars($clientId); ?></td></tr>
            <tr><td>平台</td><td><?php echo htmlspecialchars($device['platform'] ?? '未知'); ?></td></tr>
            <tr><td>版本</td><td><?php echo htmlspecialchars($device['version'] ?? '未知'); ?></td></tr>
            <tr><td>首次出现</td><td><?php echo htmlspecialchars($device['first_seen'] ?? '未知'); ?></td></tr>
            <tr><td>最近活跃</td><td><?php echo htmlspecialchars($device['last_seen'] ?? '未知'); ?></td></tr>
        </table>
    </div>

    <div class="section">
        <div class="section-header">
            <span>错误日志</span>
            <span class="badge">共 <?php echo $errorTotal; ?> 条</span>
        </div>
        <?php if (empty($errors)): ?>
        <p style="padding: 20px; color: #999;">该设备暂无错误记录</p>
        <?php else: ?>
        <div style="overflow-x: auto;">
        <table class="log-table">
            <thead>
                <tr>
                    <th>ID</th><th>时间</th><th>类型</th><th>错误信息</th>
                    <th>文件</th><th>行号</th><th>IP</th><th>日志文件</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach ($errors as $e): ?>
                <tr>
                    <td><?php echo $e['id']; ?></td>
                    <td style="white-space: nowrap;"><?php echo htmlspecialchars($e['created_at'] ?? ''); ?></td>
                    <td><?php echo htmlspecialchars($e['error_type'] ?? ''); ?></td>
                    <td class="error-msg mono"><?php echo htmlspecialchars(substr($e['error_message'] ?? '', 0, 300)); ?></td>
                    <td class="mono" style="max-width: 200px; word-break: break-all;"><?php echo htmlspecialchars(basename(str_replace('\\', '/', $e['error_file'] ?? ''))); ?></td>
                    <td><?php echo $e['error_line'] ?: '-'; ?></td>
                    <td class="mono"><?php echo htmlspecialchars(substr($e['ip_address'] ?? '', 0, 20)); ?></td>
                    <td><?php if (!empty($e['log_file'])): ?><a href="../<?php echo htmlspecialchars($e['log_file']); ?>" target="_blank" style="color: #333;">下载</a><?php else: ?>-<?php endif; ?></td>
                </tr>
                <?php if (!empty($e['stack_trace'])): ?>
                <tr><td colspan="8" class="mono" style="background: #fafafa; padding: 8px 12px; font-size: 10px; white-space: pre-wrap; max-height: 200px; overflow: auto;"><?php echo htmlspecialchars(substr($e['stack_trace'], 0, 3000)); ?></td></tr>
                <?php endif; ?>
            <?php endforeach; ?>
            </tbody>
        </table>
        </div>
        <?php endif; ?>
    </div>

    <div class="section">
        <div class="section-header">
            <span>崩溃日志</span>
            <span class="badge">共 <?php echo $crashTotal; ?> 条</span>
        </div>
        <?php if (empty($crashes)): ?>
        <p style="padding: 20px; color: #999;">该设备暂无崩溃记录</p>
        <?php else: ?>
        <div style="overflow-x: auto;">
        <table class="log-table">
            <thead>
                <tr>
                    <th>ID</th><th>时间</th><th>类型</th><th>崩溃信息</th>
                    <th>文件</th><th>行号</th><th>IP</th><th>状态</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach ($crashes as $c): ?>
                <tr>
                    <td><?php echo $c['id']; ?></td>
                    <td style="white-space: nowrap;"><?php echo htmlspecialchars($c['created_at'] ?? ''); ?></td>
                    <td><?php echo htmlspecialchars($c['crash_type'] ?? ''); ?></td>
                    <td class="error-msg mono"><?php echo htmlspecialchars(substr($c['crash_message'] ?? '', 0, 300)); ?></td>
                    <td class="mono" style="max-width: 200px; word-break: break-all;"><?php echo htmlspecialchars(basename(str_replace('\\', '/', $c['error_file'] ?? ''))); ?></td>
                    <td><?php echo $c['error_line'] ?: '-'; ?></td>
                    <td class="mono"><?php echo htmlspecialchars(substr($c['ip_address'] ?? '', 0, 20)); ?></td>
                    <td><?php echo $c['is_resolved'] ? '已解决' : '未解决'; ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
        </div>
        <?php endif; ?>
    </div>

    <?php if (!empty($logFiles)): ?>
    <div class="section">
        <div class="section-header"><span>完整日志文件</span></div>
        <?php foreach ($logFiles as $errId => $content): ?>
        <div style="padding: 10px 20px; border-bottom: 1px solid #eee;">
            <strong>错误ID: <?php echo $errId; ?></strong>
            <div class="log-content"><?php echo htmlspecialchars($content); ?></div>
        </div>
        <?php endforeach; ?>
    </div>
    <?php endif; ?>

    <?php else: ?>
    <div class="device-list">
        <h3>最近有错误的设备 (快速选择)</h3>
        <div class="device-grid">
        <?php foreach ($recentDevices as $dev): ?>
            <a href="?client_id=<?php echo urlencode($dev['client_id']); ?>" class="device-chip" style="text-decoration: none; color: inherit;">
                <span class="mono"><?php echo htmlspecialchars(substr($dev['client_id'], 0, 40)); ?>...</span>
                <span>
                    <?php if (!empty($dev['version'])): ?><span style="color: #666;">v<?php echo htmlspecialchars($dev['version']); ?></span><?php endif; ?>
                    <span class="count"><?php echo $dev['error_count']; ?> 错误</span>
                </span>
            </a>
        <?php endforeach; ?>
        </div>
    </div>
    <?php endif; ?>
</div>
</body>
</html>