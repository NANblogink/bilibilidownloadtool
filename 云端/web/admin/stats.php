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

$platformDist = $pdo->query("SELECT platform, COUNT(*) as count FROM stat_device GROUP BY platform ORDER BY count DESC")->fetchAll(PDO::FETCH_ASSOC);
$versionDist = $pdo->query("SELECT version, COUNT(*) as count FROM stat_device WHERE version != '' GROUP BY version ORDER BY count DESC LIMIT 10")->fetchAll(PDO::FETCH_ASSOC);
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
        .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; }
        .stat-icon { width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; font-size: 28px; color: white; }
        .stat-icon.install { background: #667eea; }
        .stat-icon.launch { background: #48bb78; }
        .stat-icon.parse { background: #ed8936; }
        .stat-icon.download { background: #e53e3e; }
        .stat-icon.active { background: #9f7aea; }
        .stat-icon.platform { background: #38b2ac; }
        .stat-info h3 { font-size: 28px; font-weight: 700; color: #333; margin-bottom: 5px; }
        .stat-info p { color: #666; font-size: 14px; }
        .stat-info .today { font-size: 12px; color: #999; margin-top: 2px; }
        .section { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .section h4 { margin-bottom: 20px; color: #333; font-weight: 600; }
        .chart-container { position: relative; height: 300px; }
        canvas { width: 100% !important; height: 100% !important; }
        .dist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .dist-list { list-style: none; padding: 0; }
        .dist-list li { display: flex; justify-content: space-between; padding: 10px 15px; border-bottom: 1px solid #f0f0f0; }
        .dist-list li:last-child { border-bottom: none; }
        .dist-list .label { color: #333; font-weight: 500; }
        .dist-list .value { color: #667eea; font-weight: 600; }
        .trend-controls { display: flex; gap: 10px; margin-bottom: 15px; align-items: center; }
        .trend-controls select, .trend-controls button { padding: 8px 15px; border: 2px solid #e0e0e0; font-size: 14px; }
        .trend-controls select:focus { border-color: #667eea; outline: none; }
        .trend-controls button { background: #667eea; color: white; border: none; cursor: pointer; }
        .trend-controls button:hover { background: #5a67d8; }
        @media (max-width: 992px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .dist-grid { grid-template-columns: 1fr; } }
        @media (max-width: 576px) { .stats-row { grid-template-columns: 1fr; } .container { padding: 0 15px; } }
    </style>
</head>
<body>
    <?php $active_page = 'stats'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
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
                <div class="stat-icon platform"><i class="fas fa-desktop"></i></div>
                <div class="stat-info">
                    <h3><?php echo number_format($totalInstalls); ?></h3>
                    <p>设备总数</p>
                    <div class="today"><?php echo count($platformDist); ?> 个平台</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h4><i class="fas fa-chart-area"></i> 趋势图</h4>
            <div class="trend-controls">
                <label>事件类型：</label>
                <select id="trendEventType">
                    <option value="launch">启动次数</option>
                    <option value="install">安装次数</option>
                    <option value="parse_video">解析次数</option>
                    <option value="download_video">下载次数</option>
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

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
    <script>
        let trendChart = null;

        function loadTrend() {
            var eventType = document.getElementById('trendEventType').value;
            var days = document.getElementById('trendDays').value;

            fetch('/api/v1/stats?action=trend&event_type=' + eventType + '&days=' + days, {
                headers: { 'X-API-Token': '<?php echo defined("API_TOKEN") ? API_TOKEN : ""; ?>' }
            })
            .then(function(r) { return r.json(); })
            .then(function(result) {
                if (result.code !== 0) return;
                var data = result.data;
                var labels = data.map(function(d) { return d.date; });
                var counts = data.map(function(d) { return parseInt(d.count); });
                var uniqueCounts = data.map(function(d) { return parseInt(d.unique_count); });

                var typeLabels = { launch: '启动次数', install: '安装次数', parse_video: '解析次数', download_video: '下载次数' };
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

        loadTrend();
    </script>
</body>
</html>
