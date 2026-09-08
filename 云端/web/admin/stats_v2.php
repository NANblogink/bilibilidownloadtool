<?php
require_once 'auth.php';
require_admin_login();

$dbPath = __DIR__ . '/../../data/bilidown.db';
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

date_default_timezone_set('Asia/Shanghai');
$today = date('Y-m-d');

$totalInstalls = (int)$pdo->query("SELECT COUNT(*) FROM stat_device")->fetchColumn();
$todayInstalls = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='install' AND date='$today'")->fetchColumn();
$totalLaunches = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='launch'")->fetchColumn();
$todayLaunches = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='launch' AND date='$today'")->fetchColumn();
$todayActive = (int)$pdo->query("SELECT COUNT(DISTINCT client_id) FROM stat_event WHERE event_type='launch' AND date(created_at)='$today'")->fetchColumn();
$totalParses = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='parse_video'")->fetchColumn();
$todayParses = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='parse_video' AND date='$today'")->fetchColumn();
$totalDownloads = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='download_video'")->fetchColumn();
$todayDownloads = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='download_video' AND date='$today'")->fetchColumn();

$totalErrors = (int)$pdo->query("SELECT COUNT(*) FROM stat_error")->fetchColumn();
$todayErrors = (int)$pdo->query("SELECT COUNT(*) FROM stat_error WHERE date(created_at)='$today'")->fetchColumn();

$totalLiveWatch = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_watch'")->fetchColumn();
$todayLiveWatch = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_watch' AND date='$today'")->fetchColumn();
$totalLiveRecord = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_record'")->fetchColumn();
$todayLiveRecord = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='live_record' AND date='$today'")->fetchColumn();
$totalAudioParse = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='audio_parse'")->fetchColumn();
$todayAudioParse = (int)$pdo->query("SELECT IFNULL(SUM(count),0) FROM stat_daily WHERE event_type='audio_parse' AND date='$today'")->fetchColumn();

$platformDist = $pdo->query("SELECT platform, COUNT(*) as count FROM stat_device GROUP BY platform ORDER BY count DESC")->fetchAll(PDO::FETCH_ASSOC);
$versionDist = $pdo->query("SELECT version, COUNT(*) as count FROM stat_device WHERE version != '' GROUP BY version ORDER BY count DESC LIMIT 10")->fetchAll(PDO::FETCH_ASSOC);

$errorTypeDist = $pdo->query("SELECT error_type, COUNT(*) as count FROM stat_error GROUP BY error_type ORDER BY count DESC LIMIT 10")->fetchAll(PDO::FETCH_ASSOC);
$errorTypeTotal = (int)$pdo->query("SELECT COUNT(*) FROM stat_error")->fetchColumn();

$apiToken = defined('API_TOKEN') ? API_TOKEN : '';
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据统计 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1400px; margin: 30px auto; padding: 0 30px; }
        .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; border-radius: 8px; }
        .stat-icon { width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: white; border-radius: 8px; flex-shrink: 0; }
        .stat-icon.install { background: #667eea; }
        .stat-icon.launch { background: #48bb78; }
        .stat-icon.parse { background: #ed8936; }
        .stat-icon.download { background: #e53e3e; }
        .stat-icon.active { background: #9f7aea; }
        .stat-icon.platform { background: #38b2ac; }
        .stat-icon.error { background: #e53e3e; }
        .stat-icon.live { background: #f56565; }
        .stat-icon.audio { background: #9f7aea; }
        .stat-info h3 { font-size: 24px; font-weight: 700; color: #333; margin-bottom: 3px; }
        .stat-info p { color: #666; font-size: 13px; margin-bottom: 0; }
        .stat-info .today { font-size: 11px; color: #999; margin-top: 2px; }
        .section { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; border-radius: 8px; }
        .section h4 { margin-bottom: 20px; color: #333; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .chart-container { position: relative; height: 300px; }
        canvas { width: 100% !important; height: 100% !important; }
        .dist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .dist-list { list-style: none; padding: 0; }
        .dist-list li { display: flex; justify-content: space-between; padding: 10px 15px; border-bottom: 1px solid #f0f0f0; }
        .dist-list li:last-child { border-bottom: none; }
        .dist-list .label { color: #333; font-weight: 500; }
        .dist-list .value { color: #667eea; font-weight: 600; }
        .trend-controls { display: flex; gap: 10px; margin-bottom: 15px; align-items: center; flex-wrap: wrap; }
        .trend-controls select, .trend-controls button { padding: 8px 15px; border: 2px solid #e0e0e0; font-size: 14px; border-radius: 6px; }
        .trend-controls select:focus { border-color: #667eea; outline: none; }
        .trend-controls button { background: #667eea; color: white; border: none; cursor: pointer; }
        .trend-controls button:hover { background: #5a67d8; }
        .tabs { display: flex; gap: 5px; margin-bottom: 20px; border-bottom: 2px solid #e0e0e0; }
        .tab { padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; color: #666; font-weight: 500; }
        .tab.active { color: #667eea; border-bottom-color: #667eea; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .error-table { width: 100%; font-size: 13px; }
        .error-table th { background: #f7fafc; padding: 10px; text-align: left; color: #333; font-weight: 600; }
        .error-table td { padding: 10px; border-bottom: 1px solid #f0f0f0; }
        .error-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; background: #fed7d7; color: #c53030; }
        .nav-badge { background: #e53e3e; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin-left: 5px; }
        .type-dist { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 10px; width: 100%; }
        .type-item { display: flex; align-items: center; gap: 8px; line-height: 2; }
        .error-table.fullwidth { width: 100%; }
        .error-table .mono-cell { font-family: Consolas, 'Courier New', monospace; font-size: 12px; word-break: break-all; }
        .error-table .msg-cell { white-space: pre-wrap; word-break: break-all; font-size: 12px; }
        .error-table .log-link { color: #667eea; text-decoration: none; }
        .error-table .log-link:hover { text-decoration: underline; }
        .err-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; }
        .err-toolbar input { padding: 8px 12px; border: 2px solid #e0e0e0; font-size: 13px; width: 300px; }
        .err-toolbar input:focus { border-color: #667eea; outline: none; }
        .err-toolbar button { padding: 8px 16px; border: none; background: #667eea; color: #fff; font-size: 13px; cursor: pointer; }
        .err-toolbar button.btn-reset { background: #f0f0f0; color: #333; }
        .err-toolbar-right { display: flex; gap: 8px; }
        .pagination { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 15px; align-items: center; }
        .pagination button { padding: 7px 13px; border: 1px solid #e0e0e0; background: #fff; color: #333; cursor: pointer; font-size: 13px; }
        .pagination button.active { background: #667eea; border-color: #667eea; color: #fff; }
        .pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
        .pagination .pg-dot { padding: 7px 4px; color: #999; }
        .log-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center; }
        .log-modal-box { background: #1e1e1e; width: 85%; max-width: 1100px; max-height: 85vh; display: flex; flex-direction: column; }
        .log-modal-head { background: #2d2d2d; color: #fff; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }
        .log-modal-head button { background: #555; color: #fff; border: none; padding: 6px 14px; cursor: pointer; }
        .log-modal-body { margin: 0; padding: 16px; flex: 1; overflow: auto; color: #d4d4d4; font-family: Consolas, 'Courier New', monospace; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
        @media (max-width: 1200px) { .stats-row { grid-template-columns: repeat(3, 1fr); } .dist-grid { grid-template-columns: 1fr; } }
        @media (max-width: 768px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .container { padding: 0 15px; } }
    </style>
</head>
<body>
    <?php $active_page = 'stats'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="switchTab('overview')"><i class="fas fa-tachometer-alt"></i> 总览</div>
            <div class="tab" onclick="switchTab('trend')"><i class="fas fa-chart-area"></i> 趋势分析</div>
            <div class="tab" onclick="switchTab('retention')"><i class="fas fa-users"></i> 用户留存</div>
            <div class="tab" onclick="switchTab('errors')"><i class="fas fa-bug"></i> 错误日志 <?php if ($todayErrors > 0) echo '<span class="nav-badge">' . $todayErrors . '</span>'; ?></div>
        </div>

        <div id="tab-overview" class="tab-content active">
            <div class="stats-row">
                <div class="stat-card">
                    <div class="stat-icon install"><i class="fas fa-download"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalInstalls); ?></h3>
                        <p>总安装数</p>
                        <div class="today">今日 +<?php echo number_format($todayInstalls); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon launch"><i class="fas fa-rocket"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalLaunches); ?></h3>
                        <p>总启动次数</p>
                        <div class="today">今日 +<?php echo number_format($todayLaunches); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon active"><i class="fas fa-users"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($todayActive); ?></h3>
                        <p>今日活跃用户</p>
                        <div class="today">DAU</div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon parse"><i class="fas fa-search"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalParses); ?></h3>
                        <p>总解析次数</p>
                        <div class="today">今日 +<?php echo number_format($todayParses); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon download"><i class="fas fa-file-video"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalDownloads); ?></h3>
                        <p>总下载次数</p>
                        <div class="today">今日 +<?php echo number_format($todayDownloads); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon live"><i class="fas fa-broadcast-tower"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalLiveWatch); ?></h3>
                        <p>直播观看</p>
                        <div class="today">今日 +<?php echo number_format($todayLiveWatch); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon audio"><i class="fas fa-music"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalAudioParse); ?></h3>
                        <p>音乐解析</p>
                        <div class="today">今日 +<?php echo number_format($todayAudioParse); ?></div>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon error"><i class="fas fa-exclamation-triangle"></i></div>
                    <div class="stat-info">
                        <h3><?php echo number_format($totalErrors); ?></h3>
                        <p>错误总数</p>
                        <div class="today">今日 +<?php echo number_format($todayErrors); ?></div>
                    </div>
                </div>
            </div>

            <div class="dist-grid">
                <div class="section">
                    <h4><i class="fas fa-laptop"></i> 平台分布</h4>
                    <?php if (empty($platformDist)): ?>
                        <p style="color: #999; text-align: center; padding: 20px;">暂无数据</p>
                    <?php else: ?>
                        <ul class="dist-list">
                            <?php foreach ($platformDist as $item): ?>
                                <li>
                                    <span class="label"><?php echo htmlspecialchars($item['platform']); ?></span>
                                    <span class="value"><?php echo number_format($item['count']); ?> 台</span>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    <?php endif; ?>
                </div>
                <div class="section">
                    <h4><i class="fas fa-tags"></i> 版本分布 (Top 10)</h4>
                    <?php if (empty($versionDist)): ?>
                        <p style="color: #999; text-align: center; padding: 20px;">暂无数据</p>
                    <?php else: ?>
                        <ul class="dist-list">
                            <?php foreach ($versionDist as $item): ?>
                                <li>
                                    <span class="label">V<?php echo htmlspecialchars($item['version']); ?></span>
                                    <span class="value"><?php echo number_format($item['count']); ?> 台</span>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    <?php endif; ?>
                </div>
            </div>
        </div>

        <div id="tab-trend" class="tab-content">
            <div class="section">
                <h4><i class="fas fa-chart-area"></i> 趋势图</h4>
                <div class="trend-controls">
                    <label>事件类型：</label>
                    <select id="trendEventType">
                        <option value="launch">启动次数</option>
                        <option value="install">安装次数</option>
                        <option value="parse_video">解析次数</option>
                        <option value="download_video">下载次数</option>
                        <option value="live_watch">直播观看</option>
                        <option value="live_record">直播录制</option>
                        <option value="audio_parse">音乐解析</option>
                    </select>
                    <label>时间范围：</label>
                    <select id="trendDays">
                        <option value="7">近7天</option>
                        <option value="14">近14天</option>
                        <option value="30" selected>近30天</option>
                    </select>
                    <button onclick="loadTrend()">查询</button>
                </div>
                <div class="chart-container">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
        </div>

        <div id="tab-retention" class="tab-content">
            <div class="section">
                <h4><i class="fas fa-chart-line"></i> 用户留存</h4>
                <div class="trend-controls">
                    <label>时间范围：</label>
                    <select id="retentionDays">
                        <option value="7">近7天</option>
                        <option value="14">近14天</option>
                        <option value="30" selected>近30天</option>
                    </select>
                    <button onclick="loadRetention()">查询</button>
                </div>
                <div class="chart-container">
                    <canvas id="retentionChart"></canvas>
                </div>
            </div>
        </div>

        <div id="tab-errors" class="tab-content">
            <div class="section">
                <h4><i class="fas fa-exclamation-circle"></i> 错误类型分布</h4>
                <?php if (empty($errorTypeDist)): ?>
                    <p style="color: #999; text-align: center; padding: 20px;">暂无数据</p>
                <?php else: ?>
                    <ul class="type-dist">
                        <?php foreach ($errorTypeDist as $item): ?>
                            <li class="type-item">
                                <span class="error-badge"><?php echo htmlspecialchars($item['error_type'] ?: 'unknown'); ?></span>
                                <span class="value"><?php echo number_format($item['count']); ?> 次</span>
                            </li>
                        <?php endforeach; ?>
                    </ul>
                <?php endif; ?>
            </div>
            <div class="section">
                <h4><i class="fas fa-list"></i> 错误日志</h4>
                <div class="err-toolbar">
                    <div style="color:#666;">
                        每页 <b>50</b> 条 &nbsp;<span id="errTotalLabel" style="color:#999;"></span>
                    </div>
                    <div class="err-toolbar-right">
                        <input type="text" id="errClientSearch" placeholder="输入设备码，回车查询该设备的所有错误" onkeydown="if(event.key==='Enter')searchErrors()">
                        <button onclick="searchErrors()"><i class="fas fa-search"></i> 查询设备</button>
                        <button class="btn-reset" onclick="resetErrors()">重置</button>
                    </div>
                </div>
                <div style="max-height: 600px; overflow-y: auto;">
                    <table class="error-table fullwidth">
                        <thead>
                            <tr>
                                <th>时间</th>
                                <th>类型</th>
                                <th>版本</th>
                                <th>设备码</th>
                                <th>IP</th>
                                <th>文件</th>
                                <th>行号</th>
                                <th>错误信息</th>
                                <th>日志</th>
                            </tr>
                        </thead>
                        <tbody id="errTbody">
                            <tr><td colspan="9" style="text-align:center;color:#999;padding:30px;">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
                <div id="errPagination" class="pagination"></div>
            </div>
        </div>

        <div class="log-modal" id="logModal" style="display:none;">
            <div class="log-modal-box">
                <div class="log-modal-head">
                    <span id="logModalTitle">查看日志</span>
                    <button onclick="closeLogModal()">关闭</button>
                </div>
                <pre class="log-modal-body" id="logModalBody">加载中...</pre>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
    <script>
        const API_TOKEN = '<?php echo $apiToken; ?>';
        let trendChart = null;
        let retentionChart = null;

        function switchTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.closest('.tab').classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
            if (name === 'trend' && !trendChart) loadTrend();
            if (name === 'retention' && !retentionChart) loadRetention();
            if (name === 'errors' && !errState.loaded) { errState.loaded = true; loadErrors(1); }
        }

        function loadTrend() {
            var eventType = document.getElementById('trendEventType').value;
            var days = document.getElementById('trendDays').value;

            fetch('/api/v1/stats?action=trend&event_type=' + eventType + '&days=' + days, {
                headers: { 'X-API-Token': API_TOKEN }
            })
            .then(function(r) { return r.json(); })
            .then(function(result) {
                if (result.code !== 0) return;
                var data = result.data;
                var labels = data.map(function(d) { return d.date; });
                var counts = data.map(function(d) { return parseInt(d.count); });
                var uniqueCounts = data.map(function(d) { return parseInt(d.unique_count); });

                var typeLabels = {
                    launch: '启动次数', install: '安装次数', parse_video: '解析次数',
                    download_video: '下载次数', live_watch: '直播观看',
                    live_record: '直播录制', audio_parse: '音乐解析'
                };
                var label = typeLabels[eventType] || eventType;

                if (trendChart) trendChart.destroy();

                var datasets = [{
                    label: label,
                    data: counts,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102,126,234,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }];

                if (eventType === 'launch' && uniqueCounts.some(function(v) { return v > 0; })) {
                    datasets.push({
                        label: '独立用户数',
                        data: uniqueCounts,
                        borderColor: '#48bb78',
                        backgroundColor: 'rgba(72,187,120,0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    });
                }

                trendChart = new Chart(document.getElementById('trendChart'), {
                    type: 'line',
                    data: { labels: labels, datasets: datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: {
                            y: { beginAtZero: true, ticks: { stepSize: 1 } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            });
        }

        function loadRetention() {
            var days = document.getElementById('retentionDays').value;

            fetch('/api/v1/stats?action=retention&days=' + days, {
                headers: { 'X-API-Token': API_TOKEN }
            })
            .then(function(r) { return r.json(); })
            .then(function(result) {
                if (result.code !== 0) return;
                var data = result.data;
                var labels = data.map(function(d) { return d.date; });
                var r1 = data.map(function(d) { return d.retention_1d; });
                var r3 = data.map(function(d) { return d.retention_3d; });
                var r7 = data.map(function(d) { return d.retention_7d; });

                if (retentionChart) retentionChart.destroy();

                retentionChart = new Chart(document.getElementById('retentionChart'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: '次日留存 (%)',
                                data: r1,
                                borderColor: '#667eea',
                                backgroundColor: 'rgba(102,126,234,0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: 4
                            },
                            {
                                label: '3日留存 (%)',
                                data: r3,
                                borderColor: '#48bb78',
                                backgroundColor: 'rgba(72,187,120,0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: 4
                            },
                            {
                                label: '7日留存 (%)',
                                data: r7,
                                borderColor: '#ed8936',
                                backgroundColor: 'rgba(237,137,54,0.1)',
                                fill: false,
                                tension: 0.3,
                                pointRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: {
                            y: { beginAtZero: true, max: 100, title: { display: true, text: '留存率 (%)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            });
        }
    // ===== 错误日志分页 / 查询 / 模态框 =====
        var errState = { page: 1, per: 50, loaded: false, client: '' };

        function loadErrors(page) {
            if (!page) page = errState.page;
            errState.page = page;
            var off = (page - 1) * errState.per;
            var url = '/api/v1/stats?action=errors&limit=' + errState.per + '&offset=' + off;
            if (errState.client) url += '&client_id=' + encodeURIComponent(errState.client);
            var tb = document.getElementById('errTbody');
            var label = document.getElementById('errTotalLabel');
            tb.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#999;padding:30px;">加载中...</td></tr>';
            if (label) label.textContent = '';
            fetch(url, { headers: { 'X-API-Token': API_TOKEN } })
                .then(function(r) { return r.json(); })
                .then(function(res) {
                    if (res.code !== 0) {
                        tb.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#e53e3e;padding:20px;">加载失败</td></tr>';
                        return;
                    }
                    renderErrors(res.data.items || [], res.data.total || 0, page);
                })
                .catch(function() {
                    tb.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#e53e3e;padding:20px;">请求异常</td></tr>';
                });
        }

        function renderErrors(items, total, page) {
            var tb = document.getElementById('errTbody');
            var label = document.getElementById('errTotalLabel');
            if (label) label.textContent = '共 ' + total + ' 条';
            if (!items.length) {
                tb.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#999;padding:30px;">暂无错误日志</td></tr>';
                document.getElementById('errPagination').innerHTML = '';
                return;
            }
            var html = '';
            items.forEach(function(it) {
                var t = it.created_at || '';
                var typ = it.error_type || 'unknown';
                var ver = it.version || '-';
                var cid = it.client_id || '-';
                var ip = it.ip || '-';
                var file = it.file || '-';
                var line = it.line || '';
                var msg = it.error_message || it.message || '';
                var hasLog = it.log_path || it.log_file ? 1 : 0;
                html += '<tr>' +
                    '<td>' + esc(t) + '</td>' +
                    '<td><span class="error-badge">' + esc(typ) + '</span></td>' +
                    '<td>' + esc(ver) + '</td>' +
                    '<td>' + esc(cid) + '</td>' +
                    '<td>' + esc(ip) + '</td>' +
                    '<td>' + esc(file) + '</td>' +
                    '<td>' + esc(line) + '</td>' +
                    '<td style="max-width:480px;word-break:break-all;">' + esc(msg) + '</td>' +
                    '<td>' + (hasLog ? '<a href="#" onclick="openLogModal(\'' + esc(it.log_path || it.log_file) + '\');return false;">查看</a>' : '-') + '</td>' +
                    '</tr>';
            });
            tb.innerHTML = html;
            document.getElementById('errPagination').innerHTML = buildPager(total, errState.per, page);
        }

        function esc(s) {
            if (s === null || s === undefined) return '-';
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function buildPager(total, per, page) {
            var pages = Math.max(1, Math.ceil(total / per));
            if (pages <= 1) return '';
            var h = '';
            h += '<button class="pg-btn" onclick="loadErrors(' + (page - 1) + ')" ' + (page <= 1 ? 'disabled' : '') + '>上一页</button>';
            var from = Math.max(1, page - 3);
            var to = Math.min(pages, page + 3);
            for (var i = from; i <= to; i++) {
                h += '<button class="pg-btn' + (i === page ? ' active' : '') + '" onclick="loadErrors(' + i + ')">' + i + '</button>';
            }
            h += '<button class="pg-btn" onclick="loadErrors(' + (page + 1) + ')" ' + (page >= pages ? 'disabled' : '') + '>下一页</button>';
            return h;
        }

        function searchErrors() {
            var input = document.getElementById('errClientSearch');
            errState.client = (input && input.value ? input.value.trim() : '');
            errState.page = 1;
            errState.loaded = true;
            loadErrors(1);
        }

        function resetErrors() {
            errState.client = '';
            var input = document.getElementById('errClientSearch');
            if (input) input.value = '';
            errState.page = 1;
            loadErrors(1);
        }

        function openLogModal(path) {
            var modal = document.getElementById('logModal');
            var title = document.getElementById('logModalTitle');
            var body = document.getElementById('logModalBody');
            modal.style.display = 'flex';
            title.textContent = '查看日志';
            body.textContent = '加载中...';
            var url = path.indexOf('http') === 0 ? path : 'log_view.php?file=' + encodeURIComponent(path);
            fetch(url, { headers: { 'X-API-Token': API_TOKEN } })
                .then(function(r) {
                    if (!r.ok) { body.textContent = '读取失败 (HTTP ' + r.status + ')'; return null; }
                    return r.text();
                })
                .then(function(text) {
                    if (text !== null) body.textContent = text;
                })
                .catch(function() { body.textContent = '读取日志失败'; });
        }

        function closeLogModal() {
            document.getElementById('logModal').style.display = 'none';
        }
    </script>
</body>
</html>
