<?php
require_once 'auth.php';
require_admin_login();

$dbPath = __DIR__ . '/../../data/bilidown.db';
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// 自动建表
$pdo->exec("CREATE TABLE IF NOT EXISTS log_pull_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    task_code TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    note TEXT DEFAULT '',
    req_ip TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    claimed_at TEXT,
    finished_at TEXT,
    file_path TEXT DEFAULT ''
)");

$msg = '';
$err = '';
$taskIdCreated = null;
$pullClient = '';

// 创建拉取任务：有效期 TTL 秒，等待在线客户端上来领取
$ttl = 180;
if (($_SERVER['REQUEST_METHOD'] === 'POST') && ($_POST['action'] ?? '') === 'create') {
    $clientId = trim($_POST['client_id'] ?? '');
    $note     = trim($_POST['note'] ?? '');
    if ($clientId === '') {
        $err = '请输入设备码';
    } else {
        $code = bin2hex(random_bytes(8));
        $now = date('Y-m-d H:i:s');
        $exp = date('Y-m-d H:i:s', time() + $ttl);
        $id = time() . rand(100, 999); // 便于查询，也可自增；改用自增
        $stmt = $pdo->prepare("INSERT INTO log_pull_task (client_id, task_code, status, note, req_ip, created_at, expires_at) VALUES (?,?,?,?,?,?,?)");
        $stmt->execute([$clientId, $code, 'pending', $note, $_SERVER['REMOTE_ADDR'] ?? '', $now, $exp]);
        $taskIdCreated = (int)$pdo->lastInsertId();
        $pullClient = $clientId;
        $msg = '已创建拉取任务，正在等待该设备的客户端（最多 ' . $ttl . ' 秒）...';
    }
}

// 最近拉取记录
$pullLogs = [];
try { $pullLogs = $pdo->query("SELECT * FROM log_pull_task ORDER BY id DESC LIMIT 30")->fetchAll(PDO::FETCH_ASSOC); } catch (\Exception $e) {}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>远程拉取日志 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 30px; }
        .card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .card h4 { margin-bottom: 18px; color: #333; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .form-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .form-row input { padding: 10px 14px; border: 2px solid #e0e0e0; font-size: 14px; }
        .form-row input:focus { border-color: #00a1d6; outline: none; }
        .btn { padding: 10px 20px; border: none; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; color: #fff; }
        .btn-primary { background: #00a1d6; }
        .btn-ghost { background: #f0f0f0; color: #333; }
        .btn-sm { padding: 6px 12px; font-size: 13px; }
        .msg { background: #e6f7ff; border-left: 4px solid #00a1d6; padding: 12px 16px; margin-bottom: 20px; }
        .msg.err { background: #fff5f5; border-left-color: #e53e3e; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; text-align: left; vertical-align: middle; }
        th { background: #f8f8f8; font-size: 13px; }
        .mono { font-family: Consolas, 'Courier New', monospace; font-size: 12px; word-break: break-all; }
        .st { display: inline-block; padding: 3px 8px; font-size: 12px; }
        .st-pending { background: #fff3cd; color: #997404; }
        .st-in_progress { background: #cfe2ff; color: #084298; }
        .st-completed { background: #d1e7dd; color: #0f5132; }
        .st-expired { background: #e2e3e5; color: #41464b; }
        .st-failed { background: #f8d7da; color: #842029; }
        #pullStatus { margin-top: 15px; font-size: 14px; }
    </style>
</head>
<body>
    <?php $active_page = 'pull'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <?php if ($msg): ?><div class="msg"><?php echo htmlspecialchars($msg); ?></div><?php endif; ?>
        <?php if ($err): ?><div class="msg err"><?php echo htmlspecialchars($err); ?></div><?php endif; ?>

        <div class="card">
            <h4><i class="fas fa-truck-ramp-box"></i> 远程拉取客户端日志</h4>
            <p style="color:#666; margin-bottom:15px;">
                输入设备的<b>设备码</b>，云端下发指令；<b>正在运行</b>且已开启数据采集的客户端会在约 20 秒内收到指令并上传最新日志到服务器。
                <?php echo $ttl; ?> 秒内未响应则判定为离线/未运行。
            </p>
            <form method="POST">
                <input type="hidden" name="action" value="create">
                <div class="form-row">
                    <input type="text" name="client_id" id="pullClientInput" placeholder="设备码（client_id）" style="flex:1; min-width:240px;" value="<?php echo htmlspecialchars($pullClient); ?>">
                    <input type="text" name="note" placeholder="备注（可选）" style="flex:1; min-width:180px;">
                    <button type="submit" class="btn btn-primary" onclick="startPollingSoon()"><i class="fas fa-cloud-arrow-up"></i> 拉取日志</button>
                </div>
            </form>
            <?php if ($taskIdCreated): ?>
                <div id="pullStatus" data-taskid="<?php echo $taskIdCreated; ?>" data-clientid="<?php echo htmlspecialchars($pullClient); ?>">
                    正在等待客户端响应...
                </div>
            <?php endif; ?>
        </div>

        <div class="card">
            <h4><i class="fas fa-history"></i> 最近拉取记录</h4>
            <?php if (empty($pullLogs)): ?>
                <p style="color:#999; text-align:center; padding:20px;">暂无记录</p>
            <?php else: ?>
                <table>
                    <thead>
                        <tr><th>ID</th><th>设备码</th><th>状态</th><th>备注</th><th>创建时间</th><th>完成时间</th><th>日志文件</th></tr>
                    </thead>
                    <tbody>
                        <?php foreach ($pullLogs as $t): ?>
                            <tr>
                                <td><?php echo $t['id']; ?></td>
                                <td class="mono"><?php echo htmlspecialchars($t['client_id']); ?></td>
                                <td><span class="st st-<?php echo htmlspecialchars($t['status']); ?>"><?php echo htmlspecialchars($t['status']); ?></span></td>
                                <td><?php echo htmlspecialchars($t['note'] ?: '-'); ?></td>
                                <td class="mono"><?php echo htmlspecialchars($t['created_at']); ?></td>
                                <td class="mono"><?php echo htmlspecialchars($t['finished_at'] ?: '-'); ?></td>
                                <td>
                                    <?php if ($t['status'] === 'completed' && $t['file_path']): ?>
                                        <a class="btn btn-primary btn-sm" href="pull_view.php?path=<?php echo urlencode(ltrim($t['file_path'], '/')); ?>" target="_blank">查看</a>
                                        <a class="btn btn-ghost btn-sm" href="pull_view.php?path=<?php echo urlencode(ltrim($t['file_path'], '/')); ?>" download>下载</a>
                                    <?php else: ?>-<?php endif; ?>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
    </div>

    <script>
        var API_TOKEN = '<?php echo defined('API_TOKEN') ? API_TOKEN : ''; ?>';

        function startPollingSoon() {
            // 表单正常提交，交由服务端渲染 data-taskid；这里仅在已有任务时轮询
        }

        function pollStatus() {
            var el = document.getElementById('pullStatus');
            if (!el) return;
            var taskId = el.getAttribute('data-taskid');
            var clientId = el.getAttribute('data-clientid');
            if (!taskId) return;
            fetch('/api/v1/pull/index.php?action=status&client_id=' + encodeURIComponent(clientId) + '&task_id=' + encodeURIComponent(taskId), {
                headers: { 'X-API-Token': API_TOKEN }
            }).then(function(r) { return r.json(); })
              .then(function(res) {
                  if (res.code !== 0) { el.textContent = '查询失败：' + (res.message || ''); return; }
                  var st = res.data.status;
                  if (st === 'completed') {
                      el.innerHTML = '<b style="color:#0f5132;">已拉取成功！</b> 日志文件：<a class="btn btn-primary btn-sm" href="pull_view.php?path=' + encodeURIComponent(res.data.file_path) + '" target="_blank">查看</a>';
                      return;
                  }
                  if (st === 'expired') { el.textContent = '已超时：该设备客户端未在线（未收到指令）。请稍后重试。'; return; }
                  if (st === 'failed') { el.textContent = '拉取失败（客户端响应异常）'; return; }
                  el.textContent = '正在等待客户端响应（约20秒内）... ' + new Date().toLocaleTimeString();
                  setTimeout(pollStatus, 3000);
              }).catch(function() {
                  el.textContent = '轮询请求异常，请刷新页面重试';
              });
        }

        if (document.getElementById('pullStatus')) { pollStatus(); }
    </script>
</body>
</html>