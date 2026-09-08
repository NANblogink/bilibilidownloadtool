<?php
require_once 'auth.php';
require_admin_login();

$dbPath = __DIR__ . '/../../data/bilidown.db';
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// 本地节点的 API_Token（作为导出源让其它节点拉取）
$localToken = defined('API_TOKEN') ? API_TOKEN : '';

// 同步配置存储
$configFile = __DIR__ . '/../../data/sync_config.json';
$config = [];
if (file_exists($configFile)) {
    $config = json_decode(file_get_contents($configFile), true);
    if (!is_array($config)) $config = [];
}

$config['nodes'] = isset($config['nodes']) ? $config['nodes'] : [];

// 允许同步的表及其去重键（不含 id）
$tables = [
    'stat_event'    => ['client_id', 'event_type', 'created_at'],
    'stat_error'    => ['client_id', 'error_type', 'error_message', 'created_at'],
    'crash_log'     => ['client_id', 'crash_type', 'crash_message', 'created_at'],
    'stat_device'   => ['client_id'],
    'user_feedback' => ['client_id', 'title', 'content', 'created_at'],
];

function http_get_json($url, $token) {
    $ch = @curl_init($url);
    if ($ch === false) return null;
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => ['X-API-Token: ' . $token],
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_USERAGENT => 'BiliCloud-Sync/1.0',
    ]);
    $body = curl_exec($ch);
    $err = curl_error($ch);
    curl_close($ch);
    if ($err) return null;
    $json = json_decode($body, true);
    return is_array($json) ? $json : null;
}

// 检查该行在本地是否已存在
function row_exists($pdo, $table, $keys, $row) {
    $where = [];
    $params = [];
    foreach ($keys as $k) {
        $where[] = '"' . $k . '" = ?';
        $params[] = $row[$k] ?? '';
    }
    $sql = 'SELECT 1 FROM "' . $table . '" WHERE ' . implode(' AND ', $where) . ' LIMIT 1';
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    return $stmt->fetchColumn() ? true : false;
}

// 同步单个节点：分页拉取并合并
function sync_node($pdo, $tables, $node) {
    $result = ['ok' => true, 'tables' => [], 'error' => ''];
    $urlBase = rtrim($node['url'], '/');
    $token = $node['token'];
    foreach ($tables as $table => $keys) {
        // stat_device 无 created_at，整体全量拉取；其余表用 (created_at, id) 双游标推进
        $isFull = ($table === 'stat_device');
        $after = isset($node['cursor'][$table]) ? $node['cursor'][$table] : '';
        $inserted = 0;
        $skipped = 0;
        $loops = 0;
        $offset = 0;
        $lastAfter = $after;
        $loopError = '';
        do {
            $url = $urlBase . '/api/v1/sync/index.php?action=export&table=' . rawurlencode($table) . '&after=' . rawurlencode($after) . '&offset=' . ($isFull ? $offset : 0);
            $resp = http_get_json($url, $token);
            if (!$resp || ($resp['code'] ?? 1) !== 0) {
                $loopError = '拉取失败';
                break;
            }
            $rows = $resp['data']['rows'] ?? [];
            $hasMore = (bool)($resp['data']['has_more'] ?? false);
            if (empty($rows)) break;
            foreach ($rows as $row) {
                if (table_upsert($pdo, $table, $keys, $row)) $inserted++; else $skipped++;
            }
            $offset += count($rows);
            $lastAfter = $resp['data']['next_after'] ?? $after;
            $after = $lastAfter;
            $loops++;
            if ($loops > 300) break; // 安全保护
        } while ($hasMore);

        if ($loopError !== '') {
            $result['tables'][$table] = ['inserted' => $inserted, 'skipped' => $skipped, 'error' => $loopError];
        } else {
            $result['tables'][$table] = ['inserted' => $inserted, 'skipped' => $skipped];
            $node['cursor'][$table] = $lastAfter; // 仅成功时推进游标
        }
    }
    $result['node'] = $node;
    return $result;
}

// 合并单行到本地；返回 true 表示新增，false 表示已存在
function table_upsert($pdo, $table, $keys, $row) {
    if ($table === 'stat_device') {
        $stmt = $pdo->prepare('SELECT 1 FROM stat_device WHERE client_id = ?');
        $stmt->execute([$row['client_id'] ?? '']);
        if ($stmt->fetchColumn()) {
            $u = $pdo->prepare('UPDATE stat_device SET platform=?, version=?, last_seen=? WHERE client_id=?');
            $u->execute([$row['platform'] ?? '', $row['version'] ?? '', $row['last_seen'] ?? '', $row['client_id'] ?? '']);
            return false;
        }
        $i = $pdo->prepare('INSERT INTO stat_device (client_id, platform, version, first_seen, last_seen) VALUES (?,?,?,?,?)');
        $i->execute([$row['client_id'] ?? '', $row['platform'] ?? '', $row['version'] ?? '', $row['first_seen'] ?? '', $row['last_seen'] ?? '']);
        return true;
    }
    if (row_exists($pdo, $table, $keys, $row)) {
        return false;
    }
    $fields = array_keys($row);
    $safe = [];
    $place = [];
    foreach ($fields as $f) { $safe[] = '"'.$f.'"'; $place[] = '?'; }
    $sql = 'INSERT INTO "'.$table.'" (' . implode(',', $safe) . ') VALUES (' . implode(',', $place) . ')';
    $vals = [];
    foreach ($fields as $f) { $vals[] = $row[$f] ?? ''; }
    try {
        $i = $pdo->prepare($sql);
        $i->execute($vals);
        return true;
    } catch (\Exception $e) {
        return false;
    }
}

// 处理动作
$action = $_POST['action'] ?? ($_GET['action'] ?? '');
$nodeIdx = isset($_POST['node_index']) ? (int)$_POST['node_index'] : -1;
$msg = '';

if ($action === 'add_node') {
    $name = trim($_POST['node_name'] ?? '');
    $url = trim($_POST['node_url'] ?? '');
    $token = trim($_POST['node_token'] ?? '');
    if ($name !== '' && $url !== '') {
        $config['nodes'][] = ['name' => $name, 'url' => $url, 'token' => $token, 'cursor' => []];
        file_put_contents($configFile, json_encode($config, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        $msg = '节点已添加';
    } else {
        $msg = '节点名称和地址不能为空';
    }
} elseif ($action === 'delete_node' && $nodeIdx >= 0 && isset($config['nodes'][$nodeIdx])) {
    array_splice($config['nodes'], $nodeIdx, 1);
    file_put_contents($configFile, json_encode($config, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $msg = '节点已删除';
} elseif ($action === 'sync_one' && $nodeIdx >= 0 && isset($config['nodes'][$nodeIdx])) {
    // 深度复制节点，避免引用冲突
    $node = $config['nodes'][$nodeIdx];
    $res = sync_node($pdo, $tables, $node);
    $config['nodes'][$nodeIdx] = $res['node'];
    file_put_contents($configFile, json_encode($config, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $lastResult = $res;
    $msg = '同步完成';
} elseif ($action === 'sync_all') {
    $total = ['inserted' => 0, 'skipped' => 0];
    foreach ($config['nodes'] as $i => $node) {
        $res = sync_node($pdo, $tables, $node);
        $config['nodes'][$i] = $res['node'];
        foreach ($res['tables'] as $t => $info) {
            $total['inserted'] += isset($info['inserted']) ? $info['inserted'] : 0;
            $total['skipped'] += isset($info['skipped']) ? $info['skipped'] : 0;
        }
        if (isset($lastResult)) { } else { $lastResult = $res; }
    }
    file_put_contents($configFile, json_encode($config, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $msg = '全部同步完成：新增 ' . $total['inserted'] . ' 条，跳过(已存在) ' . $total['skipped'] . ' 条';
}

// 获取各表本地总数（用于展示）
$countMap = [];
foreach (array_keys($tables) as $t) {
    try { $countMap[$t] = (int)$pdo->query("SELECT COUNT(*) FROM \"$t\"")->fetchColumn(); } catch (\Exception $e) { $countMap[$t] = 0; }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据同步 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 30px; }
        .card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .card h4 { margin-bottom: 18px; color: #333; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .form-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
        .form-row input { padding: 10px 14px; border: 2px solid #e0e0e0; font-size: 14px; }
        .form-row input:focus { border-color: #00a1d6; outline: none; }
        .btn { padding: 10px 20px; border: none; font-size: 14px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-primary { background: #00a1d6; color: white; }
        .btn-danger { background: #e53e3e; color: white; }
        .btn-ghost { background: #f0f0f0; color: #333; }
        .btn-sm { padding: 6px 12px; font-size: 13px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; text-align: left; vertical-align: top; }
        th { background: #f8f8f8; font-size: 13px; }
        .mono { font-family: Consolas, 'Courier New', monospace; font-size: 12px; word-break: break-all; }
        .badge { display: inline-block; padding: 3px 8px; background: #e6f7ff; color: #00a1d6; border-radius: 4px; font-size: 12px; }
        .msg { background: #e6f7ff; border-left: 4px solid #00a1d6; padding: 12px 16px; margin-bottom: 20px; }
        .msg.err { background: #fff5f5; border-left-color: #e53e3e; }
        .local-token { background: #fafafa; padding: 12px; border: 1px dashed #e0e0e0; word-break: break-all; }
        .cursor-list { font-size: 12px; color: #666; margin-top: 6px; }
    </style>
</head>
<body>
    <?php $active_page = 'sync'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <?php if ($msg): ?>
            <div class="msg"><?php echo htmlspecialchars($msg); ?></div>
        <?php endif; ?>

        <div class="card">
            <h4><i class="fas fa-sync-alt"></i> 本节点（作为数据源）</h4>
            <p style="color:#666; margin-bottom:10px;">其它节点可通过下面的接口拉取本节点增量数据（需要本节点 API Token）：</p>
            <div class="local-token">GET <span class="mono">https://你的域名/api/v1/sync/index.php?action=export&table=[表名]&after=[上次时间]&token=<?php echo htmlspecialchars($localToken); ?></div>
            <div class="cursor-list" style="margin-top:10px;">本节点各表数据量：<?php foreach ($countMap as $t=>$c) { echo htmlspecialchars($t) . ': <b>' . (int)$c . '</b> &nbsp;'; } ?></div>
        </div>

        <div class="card">
            <h4><i class="fas fa-server"></i> 远端节点管理</h4>
            <form method="POST">
                <input type="hidden" name="action" value="add_node">
                <div class="form-row">
                    <input type="text" name="node_name" placeholder="节点名称（如：华东节点）" style="flex:1; min-width:160px;">
                    <input type="text" name="node_url" placeholder="节点地址 https://xxx.com" style="flex:2; min-width:260px;">
                    <input type="text" name="node_token" placeholder="该节点 API Token" style="flex:1; min-width:160px;">
                    <button type="submit" class="btn btn-primary">添加节点</button>
                </div>
            </form>

            <?php if (empty($config['nodes'])): ?>
                <p style="color:#999;">尚未添加任何远端节点</p>
            <?php else: ?>
                <table>
                    <thead>
                        <tr><th>名称</th><th>地址</th><th>各表同步游标</th><th style="width:200px;">操作</th></tr>
                    </thead>
                    <tbody>
                        <?php foreach ($config['nodes'] as $i => $node): ?>
                            <tr>
                                <td><b><?php echo htmlspecialchars($node['name']); ?></b></td>
                                <td class="mono"><?php echo htmlspecialchars($node['url']); ?></td>
                                <td>
                                    <?php if (empty($node['cursor'])): ?>
                                        <span style="color:#999;">未同步过</span>
                                    <?php else: ?>
                                        <?php foreach ($node['cursor'] as $t => $a): ?>
                                            <div class="cursor-list"><?php echo htmlspecialchars($t); ?>: <?php echo htmlspecialchars($a ?: '从头'); ?></div>
                                        <?php endforeach; ?>
                                    <?php endif; ?>
                                </td>
                                <td>
                                    <form method="POST" style="display:inline-block;">
                                        <input type="hidden" name="action" value="sync_one">
                                        <input type="hidden" name="node_index" value="<?php echo $i; ?>">
                                        <button type="submit" class="btn btn-primary btn-sm"><i class="fas fa-download"></i> 同步</button>
                                    </form>
                                    <form method="POST" style="display:inline-block; margin-left:6px;">
                                        <input type="hidden" name="action" value="delete_node">
                                        <input type="hidden" name="node_index" value="<?php echo $i; ?>">
                                        <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('确认删除该节点？不会删除已同步的数据')"><i class="fas fa-trash"></i> 删除</button>
                                    </form>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
                <form method="POST" style="margin-top:15px;">
                    <input type="hidden" name="action" value="sync_all">
                    <button type="submit" class="btn btn-primary"><i class="fas fa-cloud-download-alt"></i> 一键同步所有节点数据</button>
                </form>
            <?php endif; ?>
        </div>
    </div>
</body>
</html>