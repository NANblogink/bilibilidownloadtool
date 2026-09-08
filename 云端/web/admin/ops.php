<?php
require_once 'auth.php';
require_admin_login();

date_default_timezone_set('Asia/Shanghai');

// 直接查询数据库以填充顶部统计卡片
$dbPath = __DIR__ . '/../../data/bilidown.db';
try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // 确保表存在
    $pdo->exec('CREATE TABLE IF NOT EXISTS remote_config (id INTEGER PRIMARY KEY AUTOINCREMENT, config_key VARCHAR(100), config_value TEXT, config_type VARCHAR(20) DEFAULT "string", description VARCHAR(500) DEFAULT "", min_version VARCHAR(20) DEFAULT "", max_version VARCHAR(20) DEFAULT "", target_platform VARCHAR(20) DEFAULT "all", is_active BOOLEAN DEFAULT 1, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS version_blacklist (id INTEGER PRIMARY KEY AUTOINCREMENT, version VARCHAR(20), platform VARCHAR(20) DEFAULT "all", reason VARCHAR(500), severity VARCHAR(20) DEFAULT "block", is_active BOOLEAN DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS crash_log (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id VARCHAR(200), version VARCHAR(20), platform VARCHAR(20), crash_type VARCHAR(100), crash_message TEXT, stack_trace TEXT, system_info TEXT, log_content TEXT, is_resolved BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS user_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id VARCHAR(200), version VARCHAR(20), platform VARCHAR(20), feedback_type VARCHAR(20) DEFAULT "other", title VARCHAR(200), content TEXT, contact VARCHAR(200), system_info TEXT, attachments TEXT, status VARCHAR(20) DEFAULT "pending", admin_reply TEXT, replied_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)');

    $configCount = (int)$pdo->query('SELECT COUNT(*) FROM remote_config')->fetchColumn();
    $blacklistCount = (int)$pdo->query('SELECT COUNT(*) FROM version_blacklist')->fetchColumn();
    $unresolvedCrashes = (int)$pdo->query('SELECT COUNT(*) FROM crash_log WHERE is_resolved = 0')->fetchColumn();
    $pendingFeedback = (int)$pdo->query('SELECT COUNT(*) FROM user_feedback WHERE status = "pending"')->fetchColumn();
} catch (\Exception $e) {
    $configCount = 0;
    $blacklistCount = 0;
    $unresolvedCrashes = 0;
    $pendingFeedback = 0;
}

$apiToken = defined('API_TOKEN') ? API_TOKEN : '';
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>运维中心 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f5f7fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1400px; margin: 30px auto; padding: 0 30px; }
        .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 15px; border-radius: 8px; }
        .stat-icon { width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: white; border-radius: 8px; flex-shrink: 0; }
        .stat-icon.config { background: #667eea; }
        .stat-icon.blacklist { background: #e53e3e; }
        .stat-icon.crash { background: #ed8936; }
        .stat-icon.feedback { background: #48bb78; }
        .stat-info h3 { font-size: 24px; font-weight: 700; color: #333; margin-bottom: 3px; }
        .stat-info p { color: #666; font-size: 13px; margin-bottom: 0; }
        .section { background: white; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; border-radius: 8px; }
        .section h4 { margin-bottom: 20px; color: #333; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .tabs { display: flex; gap: 5px; margin-bottom: 20px; border-bottom: 2px solid #e0e0e0; flex-wrap: wrap; }
        .tab { padding: 10px 18px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; color: #666; font-weight: 500; font-size: 14px; }
        .tab:hover { color: #00a1d6; }
        .tab.active { color: #00a1d6; border-bottom-color: #00a1d6; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .data-table { width: 100%; font-size: 13px; }
        .data-table th { background: #f7fafc; padding: 10px; text-align: left; color: #333; font-weight: 600; white-space: nowrap; }
        .data-table td { padding: 10px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; word-break: break-word; }
        .data-table tr:hover { background: #fafafa; }
        .badge-tag { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; display: inline-block; }
        .badge-active { background: #f0fff4; color: #276749; }
        .badge-inactive { background: #f7fafc; color: #718096; }
        .badge-string { background: #ebf8ff; color: #2b6cb0; }
        .badge-bool { background: #fffaf0; color: #c05621; }
        .badge-int { background: #f0fff4; color: #276749; }
        .badge-json { background: #faf5ff; color: #6b46c1; }
        .badge-warn { background: #fffaf0; color: #c05621; }
        .badge-block { background: #fff5f5; color: #c53030; }
        .badge-critical { background: #fed7d7; color: #822727; }
        .badge-info { background: #e6fffa; color: #234e52; }
        .badge-warning { background: #fffaf0; color: #c05621; }
        .badge-maintenance { background: #ebf8ff; color: #2b6cb0; }
        .badge-pending { background: #fffaf0; color: #c05621; }
        .badge-replied { background: #ebf8ff; color: #2b6cb0; }
        .badge-resolved { background: #f0fff4; color: #276749; }
        .badge-closed { background: #f7fafc; color: #718096; }
        .toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        .toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .filter-select { padding: 8px 12px; border: 2px solid #e0e0e0; font-size: 14px; border-radius: 6px; }
        .filter-select:focus { border-color: #00a1d6; outline: none; }
        .btn-add { background: #00a1d6; color: white; border: none; padding: 8px 18px; font-size: 14px; cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 8px; transition: background 0.3s; }
        .btn-add:hover { background: #0088b2; }
        .btn-action { background: none; border: 1px solid #e0e0e0; color: #666; padding: 5px 10px; font-size: 12px; cursor: pointer; transition: all 0.3s; display: inline-flex; align-items: center; gap: 4px; border-radius: 4px; margin-right: 4px; margin-bottom: 4px; }
        .btn-action:hover { border-color: #00a1d6; color: #00a1d6; }
        .btn-action.btn-delete:hover { border-color: #c53030; color: #c53030; }
        .btn-action.btn-toggle.active { border-color: #48bb78; color: #48bb78; }
        .empty-tip { color: #999; text-align: center; padding: 30px; }
        .modal-body label { font-weight: 500; margin-bottom: 5px; display: block; font-size: 14px; color: #333; }
        .modal-body .form-control, .modal-body .form-select { margin-bottom: 12px; }
        .modal-body .form-text { font-size: 12px; color: #999; margin-top: -8px; margin-bottom: 12px; }
        .stats-mini { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stats-mini .stat-card { padding: 15px; }
        .stats-mini .stat-info h3 { font-size: 20px; }
        .stats-mini .stat-info p { font-size: 12px; }
        .stats-mini .stat-icon { width: 40px; height: 40px; font-size: 18px; }
        .toast-container { position: fixed; top: 80px; right: 20px; z-index: 9999; }
        .word-break-all { word-break: break-all; }
        .text-mono { font-family: monospace; font-size: 12px; }
        .truncate { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        @media (max-width: 1200px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .stats-mini { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 768px) { .container { padding: 0 15px; } .stats-row { grid-template-columns: 1fr; } .stats-mini { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <?php $active_page = 'ops'; include __DIR__ . '/components/navbar.php'; ?>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon config"><i class="fas fa-sliders-h"></i></div>
                <div class="stat-info">
                    <h3 id="stat-config"><?php echo number_format($configCount); ?></h3>
                    <p>远程配置项</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon blacklist"><i class="fas fa-ban"></i></div>
                <div class="stat-info">
                    <h3 id="stat-blacklist"><?php echo number_format($blacklistCount); ?></h3>
                    <p>版本黑名单</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon crash"><i class="fas fa-bug"></i></div>
                <div class="stat-info">
                    <h3 id="stat-crash"><?php echo number_format($unresolvedCrashes); ?></h3>
                    <p>未解决崩溃</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon feedback"><i class="fas fa-inbox"></i></div>
                <div class="stat-info">
                    <h3 id="stat-feedback"><?php echo number_format($pendingFeedback); ?></h3>
                    <p>待处理反馈</p>
                </div>
            </div>
        </div>

        <div class="tabs">
            <div class="tab active" data-tab="config"><i class="fas fa-sliders-h"></i> 远程配置</div>
            <div class="tab" data-tab="blacklist"><i class="fas fa-ban"></i> 版本黑名单</div>
            <div class="tab" data-tab="hotfix"><i class="fas fa-wrench"></i> 热修复</div>
            <div class="tab" data-tab="gray"><i class="fas fa-random"></i> 灰度发布</div>
            <div class="tab" data-tab="abtest"><i class="fas fa-flask"></i> A/B测试</div>
            <div class="tab" data-tab="emergency"><i class="fas fa-exclamation-circle"></i> 紧急公告</div>
            <div class="tab" data-tab="crash"><i class="fas fa-bug"></i> 崩溃日志</div>
            <div class="tab" data-tab="feedback"><i class="fas fa-inbox"></i> 用户反馈</div>
        </div>

        <!-- ===== 远程配置 ===== -->
        <div id="tab-config" class="tab-content active">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-sliders-h"></i> 远程配置项</h4>
                    </div>
                    <button class="btn-add" onclick="openConfigModal()"><i class="fas fa-plus"></i> 新增配置</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Key</th>
                                <th>Value</th>
                                <th>类型</th>
                                <th>说明</th>
                                <th>版本范围</th>
                                <th>平台</th>
                                <th>状态</th>
                                <th>更新时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="config-tbody">
                            <tr><td colspan="10" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 版本黑名单 ===== -->
        <div id="tab-blacklist" class="tab-content">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-ban"></i> 版本黑名单</h4>
                    </div>
                    <button class="btn-add" onclick="openBlacklistModal()"><i class="fas fa-plus"></i> 新增黑名单</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>版本</th>
                                <th>平台</th>
                                <th>原因</th>
                                <th>严重级别</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="blacklist-tbody">
                            <tr><td colspan="8" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 热修复 ===== -->
        <div id="tab-hotfix" class="tab-content">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-wrench"></i> 热修复列表</h4>
                    </div>
                    <button class="btn-add" onclick="openHotfixModal()"><i class="fas fa-plus"></i> 上传热修复</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Hotfix ID</th>
                                <th>标题</th>
                                <th>说明</th>
                                <th>文件路径</th>
                                <th>大小</th>
                                <th>SHA256</th>
                                <th>目标版本</th>
                                <th>平台</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="hotfix-tbody">
                            <tr><td colspan="12" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 灰度发布 ===== -->
        <div id="tab-gray" class="tab-content">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-random"></i> 灰度发布规则</h4>
                    </div>
                    <button class="btn-add" onclick="openGrayModal()"><i class="fas fa-plus"></i> 创建灰度规则</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>版本</th>
                                <th>平台</th>
                                <th>通道</th>
                                <th>百分比</th>
                                <th>白名单</th>
                                <th>黑名单</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="gray-tbody">
                            <tr><td colspan="10" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== A/B 测试 ===== -->
        <div id="tab-abtest" class="tab-content">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-flask"></i> A/B 测试实验</h4>
                    </div>
                    <button class="btn-add" onclick="openAbTestModal()"><i class="fas fa-plus"></i> 创建实验</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Test Key</th>
                                <th>实验名称</th>
                                <th>变体</th>
                                <th>权重</th>
                                <th>最低版本</th>
                                <th>平台</th>
                                <th>分配统计</th>
                                <th>状态</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="abtest-tbody">
                            <tr><td colspan="11" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 紧急公告 ===== -->
        <div id="tab-emergency" class="tab-content">
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-exclamation-circle"></i> 紧急公告</h4>
                    </div>
                    <button class="btn-add" onclick="openEmergencyModal()"><i class="fas fa-plus"></i> 创建公告</button>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>公告ID</th>
                                <th>级别</th>
                                <th>标题</th>
                                <th>内容</th>
                                <th>动作</th>
                                <th>版本范围</th>
                                <th>平台</th>
                                <th>生效时间</th>
                                <th>状态</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="emergency-tbody">
                            <tr><td colspan="11" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 崩溃日志 ===== -->
        <div id="tab-crash" class="tab-content">
            <div class="stats-mini">
                <div class="stat-card">
                    <div class="stat-icon config"><i class="fas fa-bug"></i></div>
                    <div class="stat-info">
                        <h3 id="crash-stat-total">0</h3>
                        <p>崩溃总数</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon crash"><i class="fas fa-exclamation-triangle"></i></div>
                    <div class="stat-info">
                        <h3 id="crash-stat-unresolved">0</h3>
                        <p>未解决</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon feedback"><i class="fas fa-check-circle"></i></div>
                    <div class="stat-info">
                        <h3 id="crash-stat-resolved">0</h3>
                        <p>已解决</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon blacklist"><i class="fas fa-layer-group"></i></div>
                    <div class="stat-info">
                        <h3 id="crash-stat-types">0</h3>
                        <p>类型数</p>
                    </div>
                </div>
            </div>
            <div class="section">
                <h4><i class="fas fa-layer-group"></i> 崩溃类型分布</h4>
                <div id="crash-type-dist"></div>
            </div>
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-list"></i> 崩溃日志列表</h4>
                        <select class="filter-select" id="crash-filter-resolved">
                            <option value="">全部状态</option>
                            <option value="0">未解决</option>
                            <option value="1">已解决</option>
                        </select>
                        <input type="text" class="filter-select" id="crash-filter-version" placeholder="版本号" style="width:120px;">
                        <select class="filter-select" id="crash-filter-platform">
                            <option value="">全部平台</option>
                            <option value="windows">windows</option>
                            <option value="mac">mac</option>
                            <option value="linux">linux</option>
                            <option value="android">android</option>
                            <option value="ios">ios</option>
                        </select>
                    </div>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>时间</th>
                                <th>客户端</th>
                                <th>版本</th>
                                <th>平台</th>
                                <th>类型</th>
                                <th>信息</th>
                                <th>状态</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="crash-tbody">
                            <tr><td colspan="9" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ===== 用户反馈 ===== -->
        <div id="tab-feedback" class="tab-content">
            <div class="stats-mini">
                <div class="stat-card">
                    <div class="stat-icon config"><i class="fas fa-inbox"></i></div>
                    <div class="stat-info">
                        <h3 id="fb-stat-total">0</h3>
                        <p>反馈总数</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon crash"><i class="fas fa-clock"></i></div>
                    <div class="stat-info">
                        <h3 id="fb-stat-pending">0</h3>
                        <p>待处理</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon feedback"><i class="fas fa-reply"></i></div>
                    <div class="stat-info">
                        <h3 id="fb-stat-replied">0</h3>
                        <p>已回复</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon blacklist"><i class="fas fa-check"></i></div>
                    <div class="stat-info">
                        <h3 id="fb-stat-resolved">0</h3>
                        <p>已解决</p>
                    </div>
                </div>
            </div>
            <div class="section">
                <div class="toolbar">
                    <div class="toolbar-left">
                        <h4 style="margin:0;"><i class="fas fa-list"></i> 用户反馈列表</h4>
                        <select class="filter-select" id="fb-filter-status">
                            <option value="">全部状态</option>
                            <option value="pending">待处理</option>
                            <option value="replied">已回复</option>
                            <option value="resolved">已解决</option>
                            <option value="closed">已关闭</option>
                        </select>
                        <select class="filter-select" id="fb-filter-type">
                            <option value="">全部类型</option>
                            <option value="bug">Bug</option>
                            <option value="suggestion">建议</option>
                            <option value="question">问题</option>
                            <option value="other">其他</option>
                        </select>
                    </div>
                </div>
                <div style="overflow-x:auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>时间</th>
                                <th>类型</th>
                                <th>标题</th>
                                <th>内容</th>
                                <th>联系方式</th>
                                <th>版本/平台</th>
                                <th>状态</th>
                                <th>回复</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="feedback-tbody">
                            <tr><td colspan="10" class="empty-tip">加载中...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 远程配置 Modal ===== -->
    <div class="modal fade" id="configModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-sliders-h"></i> <span id="config-modal-title">新增配置</span></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="config-id">
                    <div class="row">
                        <div class="col-md-6">
                            <label>配置键 (Key) <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="config-key" placeholder="如: feature_x_enabled">
                        </div>
                        <div class="col-md-6">
                            <label>配置类型</label>
                            <select class="form-select" id="config-type">
                                <option value="string">string</option>
                                <option value="bool">bool</option>
                                <option value="int">int</option>
                                <option value="json">json</option>
                            </select>
                        </div>
                    </div>
                    <label>配置值 (Value) <span class="text-danger">*</span></label>
                    <textarea class="form-control" id="config-value" rows="3" placeholder="bool 类型填 true/false；json 类型填 JSON 字符串"></textarea>
                    <label>描述说明</label>
                    <input type="text" class="form-control" id="config-description" placeholder="配置说明">
                    <div class="row">
                        <div class="col-md-4">
                            <label>最低版本</label>
                            <input type="text" class="form-control" id="config-min-version" placeholder="如: 2.0.0">
                        </div>
                        <div class="col-md-4">
                            <label>最高版本</label>
                            <input type="text" class="form-control" id="config-max-version" placeholder="如: 2.5.0">
                        </div>
                        <div class="col-md-4">
                            <label>目标平台</label>
                            <select class="form-select" id="config-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-check mt-2">
                        <input type="checkbox" class="form-check-input" id="config-active" checked>
                        <label class="form-check-label" for="config-active">启用</label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveConfig()">保存</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 版本黑名单 Modal ===== -->
    <div class="modal fade" id="blacklistModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-ban"></i> 新增黑名单</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <label>版本号 <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="bl-version" placeholder="如: 2.0.5">
                    <div class="row">
                        <div class="col-md-6">
                            <label>平台</label>
                            <select class="form-select" id="bl-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label>严重级别</label>
                            <select class="form-select" id="bl-severity">
                                <option value="warn">warn (警告)</option>
                                <option value="block">block (阻止)</option>
                                <option value="critical">critical (严重)</option>
                            </select>
                        </div>
                    </div>
                    <label>原因</label>
                    <textarea class="form-control" id="bl-reason" rows="3" placeholder="拉黑原因说明"></textarea>
                    <div class="form-check mt-2">
                        <input type="checkbox" class="form-check-input" id="bl-active" checked>
                        <label class="form-check-label" for="bl-active">启用</label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveBlacklist()">保存</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 热修复 Modal ===== -->
    <div class="modal fade" id="hotfixModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-wrench"></i> <span id="hf-modal-title">上传热修复</span></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="hf-edit-id">
                    <div class="row">
                        <div class="col-md-6">
                            <label>Hotfix ID <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="hf-id" placeholder="如: fix_2_0_6_crash">
                        </div>
                        <div class="col-md-6">
                            <label>标题 <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="hf-title" placeholder="热修复标题">
                        </div>
                    </div>
                    <label>描述</label>
                    <textarea class="form-control" id="hf-description" rows="2" placeholder="修复说明"></textarea>
                    <div id="hf-file-row">
                        <label>修复文件</label>
                        <input type="file" class="form-control" id="hf-file">
                        <div class="form-text">支持 zip/patch/dll/exe/json/bin 格式。上传后自动计算大小和SHA256。</div>
                        <div id="hf-upload-result" style="display:none;" class="alert alert-info mt-2"></div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <label>目标版本</label>
                            <input type="text" class="form-control" id="hf-target-version" placeholder="如: 2.0.6">
                        </div>
                        <div class="col-md-6">
                            <label>目标平台</label>
                            <select class="form-select" id="hf-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                    </div>
                    <div id="hf-active-row" style="display:none;" class="form-check mt-3">
                        <input type="checkbox" class="form-check-input" id="hf-active" checked>
                        <label class="form-check-label" for="hf-active">启用</label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveHotfix()">保存</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 灰度发布 Modal ===== -->
    <div class="modal fade" id="grayModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-random"></i> 创建灰度规则</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col-md-4">
                            <label>版本号 <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="gy-version" placeholder="如: 2.1.0">
                        </div>
                        <div class="col-md-4">
                            <label>平台</label>
                            <select class="form-select" id="gy-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label>通道</label>
                            <select class="form-select" id="gy-channel">
                                <option value="stable">stable</option>
                                <option value="beta">beta</option>
                                <option value="alpha">alpha</option>
                            </select>
                        </div>
                    </div>
                    <label>灰度百分比 (0-100)</label>
                    <input type="number" class="form-control" id="gy-percentage" min="0" max="100" value="0">
                    <label>白名单 (client_id 逗号分隔)</label>
                    <input type="text" class="form-control" id="gy-whitelist" placeholder="client1,client2,client3">
                    <label>黑名单 (client_id 逗号分隔)</label>
                    <input type="text" class="form-control" id="gy-blacklist" placeholder="client1,client2">
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveGray()">创建</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 灰度百分比调整 Modal ===== -->
    <div class="modal fade" id="grayPctModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-sliders-h"></i> 调整灰度百分比</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="gy-pct-id">
                    <label>新百分比 (0-100)</label>
                    <input type="number" class="form-control" id="gy-pct-value" min="0" max="100">
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveGrayPct()">保存</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== A/B 测试 Modal ===== -->
    <div class="modal fade" id="abtestModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-flask"></i> <span id="ab-modal-title">创建 A/B 实验</span></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="ab-edit-id">
                    <div class="row">
                        <div class="col-md-6">
                            <label>实验标识 (test_key) <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="ab-key" placeholder="如: new_ui_layout">
                        </div>
                        <div class="col-md-6">
                            <label>实验名称 <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="ab-name" placeholder="实验名称">
                        </div>
                    </div>
                    <label>描述</label>
                    <input type="text" class="form-control" id="ab-description" placeholder="实验描述">
                    <label>变体 (逗号分隔，至少2个) <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="ab-variants" placeholder="control,variant_a,variant_b">
                    <label>权重 (逗号分隔，对应变体)</label>
                    <input type="text" class="form-control" id="ab-weights" placeholder="1,1,1 或 50,30,20">
                    <div class="form-text">未填写时默认每个变体权重为1。</div>
                    <div class="row">
                        <div class="col-md-6">
                            <label>最低版本</label>
                            <input type="text" class="form-control" id="ab-min-version" placeholder="如: 2.0.0">
                        </div>
                        <div class="col-md-6">
                            <label>目标平台</label>
                            <select class="form-select" id="ab-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-check mt-3">
                        <input type="checkbox" class="form-check-input" id="ab-active" checked>
                        <label class="form-check-label" for="ab-active">启用</label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveAbTest()">保存</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 紧急公告 Modal ===== -->
    <div class="modal fade" id="emergencyModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-exclamation-circle"></i> 创建紧急公告</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col-md-6">
                            <label>公告ID <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="em-id" placeholder="如: notice_2026_001">
                        </div>
                        <div class="col-md-6">
                            <label>级别</label>
                            <select class="form-select" id="em-level">
                                <option value="info">info (绿色提示)</option>
                                <option value="warning">warning (橙色警告)</option>
                                <option value="critical">critical (红色严重)</option>
                                <option value="maintenance">maintenance (蓝色维护)</option>
                            </select>
                        </div>
                    </div>
                    <label>标题 <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="em-title" placeholder="公告标题">
                    <label>内容</label>
                    <textarea class="form-control" id="em-content" rows="3" placeholder="公告详细内容"></textarea>
                    <div class="row">
                        <div class="col-md-6">
                            <label>动作文字</label>
                            <input type="text" class="form-control" id="em-action-text" placeholder="如: 立即更新">
                        </div>
                        <div class="col-md-6">
                            <label>动作链接</label>
                            <input type="text" class="form-control" id="em-action-url" placeholder="如: /download.php 或 https://...">
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-4">
                            <label>最低版本</label>
                            <input type="text" class="form-control" id="em-min-version" placeholder="如: 2.0.0">
                        </div>
                        <div class="col-md-4">
                            <label>最高版本</label>
                            <input type="text" class="form-control" id="em-max-version" placeholder="如: 2.5.0">
                        </div>
                        <div class="col-md-4">
                            <label>目标平台</label>
                            <select class="form-select" id="em-platform">
                                <option value="all">all</option>
                                <option value="windows">windows</option>
                                <option value="mac">mac</option>
                                <option value="linux">linux</option>
                            </select>
                        </div>
                    </div>
                    <label>结束时间</label>
                    <input type="datetime-local" class="form-control" id="em-end-time">
                    <div class="form-text">留空表示长期生效。</div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveEmergency()">创建</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ===== 用户反馈回复 Modal ===== -->
    <div class="modal fade" id="feedbackReplyModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-reply"></i> 回复反馈</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="fb-id">
                    <div id="fb-detail" class="mb-3" style="background:#f7fafc;padding:15px;border-radius:6px;font-size:13px;"></div>
                    <label>回复内容 <span class="text-danger">*</span></label>
                    <textarea class="form-control" id="fb-reply" rows="4" placeholder="请输入回复内容"></textarea>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveFeedbackReply()">提交回复</button>
                </div>
            </div>
        </div>
    </div>

    <!-- 崩溃详情 Modal -->
    <div class="modal fade" id="crashDetailModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-bug"></i> 崩溃详情</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="crash-detail" style="font-size:13px;"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                </div>
            </div>
        </div>
    </div>

    <div class="toast-container" id="toastContainer"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API_TOKEN = '<?php echo $apiToken; ?>';
        const API_BASE = '/api/v1/';
        const HEADERS = { 'Content-Type': 'application/json', 'X-API-Token': API_TOKEN };

        // ===== 通用工具 =====
        function showToast(message, type) {
            type = type || 'success';
            const colors = { success: '#48bb78', error: '#e53e3e', warning: '#ed8936', info: '#00a1d6' };
            const toast = document.createElement('div');
            toast.style.css = 'background:' + (colors[type] || colors.success) + ';color:white;padding:12px 20px;border-radius:6px;margin-bottom:10px;box-shadow:0 4px 12px rgba(0,0,0,0.2);min-width:250px;font-size:14px;';
            toast.textContent = message;
            document.getElementById('toastContainer').appendChild(toast);
            setTimeout(function() {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.3s';
                setTimeout(function() { toast.remove(); }, 300);
            }, 3000);
        }

        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str).replace(/[&<>"']/g, function(c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        function truncate(str, len) {
            if (!str) return '';
            str = String(str);
            return str.length > len ? str.substring(0, len) + '...' : str;
        }

        function debounce(func, wait) {
            let timeout;
            return function() {
                const ctx = this, args = arguments;
                clearTimeout(timeout);
                timeout = setTimeout(function() { func.apply(ctx, args); }, wait);
            };
        }

        function apiGet(url) {
            return fetch(API_BASE + url, { headers: { 'X-API-Token': API_TOKEN } })
                .then(function(r) { return r.json(); });
        }

        function apiPost(url, body) {
            return fetch(API_BASE + url, {
                method: 'POST',
                headers: HEADERS,
                body: JSON.stringify(body)
            }).then(function(r) { return r.json(); });
        }

        function apiPut(url, body) {
            return fetch(API_BASE + url, {
                method: 'PUT',
                headers: HEADERS,
                body: JSON.stringify(body)
            }).then(function(r) { return r.json(); });
        }

        function apiDelete(url) {
            return fetch(API_BASE + url, {
                method: 'DELETE',
                headers: { 'X-API-Token': API_TOKEN }
            }).then(function(r) { return r.json(); });
        }

        function confirmDelete(msg, callback) {
            if (confirm(msg || '确认删除？此操作不可恢复。')) {
                callback();
            }
        }

        // ===== Tab 切换 =====
        document.querySelectorAll('.tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
                document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
                onTabSwitched(tab.dataset.tab);
            });
        });

        function onTabSwitched(name) {
            switch (name) {
                case 'config': loadConfig(); break;
                case 'blacklist': loadBlacklist(); break;
                case 'hotfix': loadHotfix(); break;
                case 'gray': loadGray(); break;
                case 'abtest': loadAbTest(); break;
                case 'emergency': loadEmergency(); break;
                case 'crash': loadCrashStats(); loadCrashList(); break;
                case 'feedback': loadFeedbackStats(); loadFeedback(); break;
            }
        }

        // ===== 远程配置 =====
        let configModal = null;
        function loadConfig() {
            apiGet('config').then(function(res) {
                const tbody = document.getElementById('config-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="10" class="empty-tip">暂无配置项</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td class="text-mono">' + escapeHtml(r.config_key) + '</td>' +
                        '<td class="truncate text-mono" title="' + escapeHtml(r.config_value) + '">' + escapeHtml(truncate(r.config_value, 60)) + '</td>' +
                        '<td><span class="badge-tag badge-' + r.config_type + '">' + r.config_type + '</span></td>' +
                        '<td class="truncate" title="' + escapeHtml(r.description) + '">' + escapeHtml(r.description || '-') + '</td>' +
                        '<td>' + (r.min_version || '-') + ' ~ ' + (r.max_version || '-') + '</td>' +
                        '<td>' + escapeHtml(r.target_platform) + '</td>' +
                        '<td><span class="badge-tag ' + (r.is_active == 1 ? 'badge-active' : 'badge-inactive') + '">' + (r.is_active == 1 ? '启用' : '停用') + '</span></td>' +
                        '<td>' + escapeHtml(r.updated_at) + '</td>' +
                        '<td>' +
                            '<button class="btn-action" onclick="editConfig(' + r.id + ')"><i class="fas fa-edit"></i> 编辑</button>' +
                            '<button class="btn-action btn-toggle ' + (r.is_active == 1 ? 'active' : '') + '" onclick="toggleConfig(' + r.id + ',' + (r.is_active == 1 ? 0 : 1) + ')"><i class="fas fa-power-off"></i> ' + (r.is_active == 1 ? '停用' : '启用') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteConfig(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('config-tbody').innerHTML = '<tr><td colspan="10" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openConfigModal() {
            document.getElementById('config-modal-title').textContent = '新增配置';
            ['config-id','config-key','config-value','config-description','config-min-version','config-max-version'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('config-type').value = 'string';
            document.getElementById('config-platform').value = 'all';
            document.getElementById('config-active').checked = true;
            if (!configModal) configModal = new bootstrap.Modal(document.getElementById('configModal'));
            configModal.show();
        }

        function editConfig(id) {
            apiGet('config').then(function(res) {
                if (res.code !== 0) return;
                const r = res.data.find(function(x) { return x.id == id; });
                if (!r) { showToast('未找到配置', 'error'); return; }
                document.getElementById('config-modal-title').textContent = '编辑配置 #' + id;
                document.getElementById('config-id').value = r.id;
                document.getElementById('config-key').value = r.config_key;
                document.getElementById('config-value').value = r.config_value;
                document.getElementById('config-type').value = r.config_type;
                document.getElementById('config-description').value = r.description || '';
                document.getElementById('config-min-version').value = r.min_version || '';
                document.getElementById('config-max-version').value = r.max_version || '';
                document.getElementById('config-platform').value = r.target_platform || 'all';
                document.getElementById('config-active').checked = r.is_active == 1;
                if (!configModal) configModal = new bootstrap.Modal(document.getElementById('configModal'));
                configModal.show();
            });
        }

        function saveConfig() {
            const id = document.getElementById('config-id').value;
            const payload = {
                config_key: document.getElementById('config-key').value.trim(),
                config_value: document.getElementById('config-value').value,
                config_type: document.getElementById('config-type').value,
                description: document.getElementById('config-description').value.trim(),
                min_version: document.getElementById('config-min-version').value.trim(),
                max_version: document.getElementById('config-max-version').value.trim(),
                target_platform: document.getElementById('config-platform').value,
                is_active: document.getElementById('config-active').checked
            };
            if (!payload.config_key) { showToast('配置键不能为空', 'error'); return; }
            let p;
            if (id) {
                payload.id = parseInt(id);
                p = apiPut('config', payload);
            } else {
                payload.action = 'set';
                p = apiPost('config', payload);
            }
            p.then(function(res) {
                if (res.code === 0) {
                    showToast('保存成功', 'success');
                    configModal.hide();
                    loadConfig();
                    refreshTopStats();
                } else {
                    showToast(res.message || '保存失败', 'error');
                }
            });
        }

        function toggleConfig(id, isActive) {
            apiPut('config', { id: id, is_active: !!isActive }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadConfig(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteConfig(id) {
            confirmDelete('确认删除该配置项？', function() {
                apiDelete('config?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadConfig(); refreshTopStats(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 版本黑名单 =====
        let blacklistModal = null;
        function loadBlacklist() {
            apiGet('blacklist').then(function(res) {
                const tbody = document.getElementById('blacklist-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="8" class="empty-tip">暂无黑名单</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td><strong>' + escapeHtml(r.version) + '</strong></td>' +
                        '<td>' + escapeHtml(r.platform) + '</td>' +
                        '<td class="truncate" title="' + escapeHtml(r.reason) + '">' + escapeHtml(r.reason || '-') + '</td>' +
                        '<td><span class="badge-tag badge-' + r.severity + '">' + r.severity + '</span></td>' +
                        '<td><span class="badge-tag ' + (r.is_active == 1 ? 'badge-active' : 'badge-inactive') + '">' + (r.is_active == 1 ? '启用' : '停用') + '</span></td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td>' +
                            '<button class="btn-action btn-toggle ' + (r.is_active == 1 ? 'active' : '') + '" onclick="toggleBlacklist(' + r.id + ',' + (r.is_active == 1 ? 0 : 1) + ')"><i class="fas fa-power-off"></i> ' + (r.is_active == 1 ? '停用' : '启用') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteBlacklist(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('blacklist-tbody').innerHTML = '<tr><td colspan="8" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openBlacklistModal() {
            ['bl-version','bl-reason'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('bl-platform').value = 'all';
            document.getElementById('bl-severity').value = 'block';
            document.getElementById('bl-active').checked = true;
            if (!blacklistModal) blacklistModal = new bootstrap.Modal(document.getElementById('blacklistModal'));
            blacklistModal.show();
        }

        function saveBlacklist() {
            const payload = {
                action: 'add',
                version: document.getElementById('bl-version').value.trim(),
                platform: document.getElementById('bl-platform').value,
                reason: document.getElementById('bl-reason').value.trim(),
                severity: document.getElementById('bl-severity').value,
                is_active: document.getElementById('bl-active').checked
            };
            if (!payload.version) { showToast('版本号不能为空', 'error'); return; }
            apiPost('blacklist', payload).then(function(res) {
                if (res.code === 0) {
                    showToast('添加成功', 'success');
                    blacklistModal.hide();
                    loadBlacklist();
                    refreshTopStats();
                } else {
                    showToast(res.message || '添加失败', 'error');
                }
            });
        }

        function toggleBlacklist(id, isActive) {
            apiPut('blacklist', { id: id, is_active: !!isActive }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadBlacklist(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteBlacklist(id) {
            confirmDelete('确认删除该黑名单？', function() {
                apiDelete('blacklist?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadBlacklist(); refreshTopStats(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 热修复 =====
        let hotfixModal = null;
        function loadHotfix() {
            apiGet('hotfix').then(function(res) {
                const tbody = document.getElementById('hotfix-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="12" class="empty-tip">暂无热修复</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    const sizeKb = r.file_size ? (parseInt(r.file_size) / 1024).toFixed(1) + ' KB' : '-';
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td class="text-mono">' + escapeHtml(r.hotfix_id) + '</td>' +
                        '<td>' + escapeHtml(r.title) + '</td>' +
                        '<td class="truncate" title="' + escapeHtml(r.description) + '">' + escapeHtml(r.description || '-') + '</td>' +
                        '<td class="truncate text-mono"><a href="' + escapeHtml(r.file_path) + '" target="_blank">' + escapeHtml(truncate(r.file_path, 30)) + '</a></td>' +
                        '<td>' + sizeKb + '</td>' +
                        '<td class="text-mono" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;" title="' + escapeHtml(r.sha256) + '">' + escapeHtml(truncate(r.sha256, 16)) + '</td>' +
                        '<td>' + escapeHtml(r.target_version || '-') + '</td>' +
                        '<td>' + escapeHtml(r.target_platform) + '</td>' +
                        '<td><span class="badge-tag ' + (r.is_active == 1 ? 'badge-active' : 'badge-inactive') + '">' + (r.is_active == 1 ? '启用' : '停用') + '</span></td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td>' +
                            '<button class="btn-action" onclick="editHotfix(' + r.id + ')"><i class="fas fa-edit"></i> 编辑</button>' +
                            '<button class="btn-action btn-toggle ' + (r.is_active == 1 ? 'active' : '') + '" onclick="toggleHotfix(' + r.id + ',' + (r.is_active == 1 ? 0 : 1) + ')"><i class="fas fa-power-off"></i> ' + (r.is_active == 1 ? '停用' : '启用') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteHotfix(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('hotfix-tbody').innerHTML = '<tr><td colspan="12" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openHotfixModal() {
            document.getElementById('hf-edit-id').value = '';
            ['hf-id','hf-title','hf-description','hf-target-version'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('hf-file').value = '';
            document.getElementById('hf-platform').value = 'all';
            document.getElementById('hf-active').checked = true;
            document.getElementById('hf-upload-result').style.display = 'none';
            document.getElementById('hf-upload-result').innerHTML = '';
            document.getElementById('hf-modal-title').textContent = '上传热修复';
            document.getElementById('hf-file-row').style.display = 'block';
            document.getElementById('hf-active-row').style.display = 'none';
            if (!hotfixModal) hotfixModal = new bootstrap.Modal(document.getElementById('hotfixModal'));
            hotfixModal.show();
        }

        function editHotfix(id) {
            apiGet('hotfix').then(function(res) {
                if (res.code !== 0) return;
                const r = res.data.find(function(x) { return x.id == id; });
                if (!r) { showToast('未找到热修复', 'error'); return; }
                document.getElementById('hf-edit-id').value = r.id;
                document.getElementById('hf-id').value = r.hotfix_id;
                document.getElementById('hf-title').value = r.title;
                document.getElementById('hf-description').value = r.description || '';
                document.getElementById('hf-target-version').value = r.target_version || '';
                document.getElementById('hf-platform').value = r.target_platform || 'all';
                document.getElementById('hf-active').checked = r.is_active == 1;
                document.getElementById('hf-modal-title').textContent = '编辑热修复 #' + r.id;
                document.getElementById('hf-file-row').style.display = 'none';
                document.getElementById('hf-active-row').style.display = 'block';
                document.getElementById('hf-upload-result').style.display = 'none';
                if (!hotfixModal) hotfixModal = new bootstrap.Modal(document.getElementById('hotfixModal'));
                hotfixModal.show();
            });
        }

        function toggleHotfix(id, isActive) {
            apiPut('hotfix', { id: id, is_active: !!isActive }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadHotfix(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        let uploadedHotfixInfo = null;
        document.getElementById('hf-file').addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;
            uploadedHotfixInfo = null;
            const result = document.getElementById('hf-upload-result');
            result.style.display = 'block';
            result.className = 'alert alert-info mt-2';
            result.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';

            const formData = new FormData();
            formData.append('file', file);

            fetch(API_BASE + 'hotfix?action=upload', {
                method: 'POST',
                headers: { 'X-API-Token': API_TOKEN },
                body: formData
            }).then(function(r) { return r.json(); }).then(function(res) {
                if (res.code === 0) {
                    uploadedHotfixInfo = res.data;
                    result.className = 'alert alert-success mt-2';
                    result.innerHTML = '<i class="fas fa-check"></i> 上传成功<br>路径: ' + res.data.file_path + '<br>大小: ' + (res.data.file_size / 1024).toFixed(1) + ' KB<br>SHA256: ' + res.data.sha256;
                } else {
                    result.className = 'alert alert-danger mt-2';
                    result.innerHTML = '<i class="fas fa-times"></i> ' + (res.message || '上传失败');
                }
            }).catch(function(err) {
                result.className = 'alert alert-danger mt-2';
                result.innerHTML = '<i class="fas fa-times"></i> 上传失败: ' + err.message;
            });
        });

        function saveHotfix() {
            const editId = document.getElementById('hf-edit-id').value;
            const payload = {
                hotfix_id: document.getElementById('hf-id').value.trim(),
                title: document.getElementById('hf-title').value.trim(),
                description: document.getElementById('hf-description').value.trim(),
                target_version: document.getElementById('hf-target-version').value.trim(),
                target_platform: document.getElementById('hf-platform').value,
                is_active: document.getElementById('hf-active').checked
            };
            if (editId) {
                payload.id = parseInt(editId);
            } else {
                payload.action = 'create';
                if (uploadedHotfixInfo) {
                    payload.file_path = uploadedHotfixInfo.file_path;
                    payload.file_size = uploadedHotfixInfo.file_size;
                    payload.sha256 = uploadedHotfixInfo.sha256;
                }
            }
            if (!payload.hotfix_id || !payload.title) { showToast('Hotfix ID 和标题不能为空', 'error'); return; }
            const p = editId ? apiPut('hotfix', payload) : apiPost('hotfix', payload);
            p.then(function(res) {
                if (res.code === 0) {
                    showToast(editId ? '更新成功' : '创建成功', 'success');
                    hotfixModal.hide();
                    uploadedHotfixInfo = null;
                    loadHotfix();
                } else {
                    showToast(res.message || (editId ? '更新失败' : '创建失败'), 'error');
                }
            });
        }

        function deleteHotfix(id) {
            confirmDelete('确认删除该热修复？', function() {
                apiDelete('hotfix?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadHotfix(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 灰度发布 =====
        let grayModal = null, grayPctModal = null;
        function loadGray() {
            apiGet('gray').then(function(res) {
                const tbody = document.getElementById('gray-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="10" class="empty-tip">暂无灰度规则</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    const statusBadge = r.status === 'active' ? 'badge-active' : (r.status === 'paused' ? 'badge-inactive' : 'badge-resolved');
                    const statusText = r.status === 'active' ? '运行中' : (r.status === 'paused' ? '已暂停' : '已完成');
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td><strong>' + escapeHtml(r.version) + '</strong></td>' +
                        '<td>' + escapeHtml(r.platform) + '</td>' +
                        '<td>' + escapeHtml(r.channel) + '</td>' +
                        '<td><strong>' + r.rollout_percentage + '%</strong></td>' +
                        '<td class="truncate text-mono" title="' + escapeHtml(r.whitelist) + '">' + escapeHtml(r.whitelist || '-') + '</td>' +
                        '<td class="truncate text-mono" title="' + escapeHtml(r.blacklist) + '">' + escapeHtml(r.blacklist || '-') + '</td>' +
                        '<td><span class="badge-tag ' + statusBadge + '">' + statusText + '</span></td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td>' +
                            (r.status === 'active' ?
                                '<button class="btn-action" onclick="updateGrayStatus(' + r.id + ',\'paused\')"><i class="fas fa-pause"></i> 暂停</button>' :
                                '<button class="btn-action btn-toggle active" onclick="updateGrayStatus(' + r.id + ',\'active\')"><i class="fas fa-play"></i> 恢复</button>') +
                            '<button class="btn-action" onclick="openGrayPctModal(' + r.id + ',' + r.rollout_percentage + ')"><i class="fas fa-sliders-h"></i> 调整</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteGray(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('gray-tbody').innerHTML = '<tr><td colspan="10" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openGrayModal() {
            ['gy-version','gy-whitelist','gy-blacklist'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('gy-platform').value = 'all';
            document.getElementById('gy-channel').value = 'stable';
            document.getElementById('gy-percentage').value = '0';
            if (!grayModal) grayModal = new bootstrap.Modal(document.getElementById('grayModal'));
            grayModal.show();
        }

        function saveGray() {
            const payload = {
                action: 'create',
                version: document.getElementById('gy-version').value.trim(),
                platform: document.getElementById('gy-platform').value,
                channel: document.getElementById('gy-channel').value,
                rollout_percentage: parseInt(document.getElementById('gy-percentage').value) || 0,
                whitelist: document.getElementById('gy-whitelist').value.trim(),
                blacklist: document.getElementById('gy-blacklist').value.trim()
            };
            if (!payload.version) { showToast('版本号不能为空', 'error'); return; }
            apiPost('gray', payload).then(function(res) {
                if (res.code === 0) { showToast('创建成功', 'success'); grayModal.hide(); loadGray(); }
                else { showToast(res.message || '创建失败', 'error'); }
            });
        }

        function updateGrayStatus(id, status) {
            apiPut('gray', { id: id, status: status }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadGray(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function openGrayPctModal(id, pct) {
            document.getElementById('gy-pct-id').value = id;
            document.getElementById('gy-pct-value').value = pct;
            if (!grayPctModal) grayPctModal = new bootstrap.Modal(document.getElementById('grayPctModal'));
            grayPctModal.show();
        }

        function saveGrayPct() {
            const id = parseInt(document.getElementById('gy-pct-id').value);
            const pct = parseInt(document.getElementById('gy-pct-value').value);
            if (isNaN(pct) || pct < 0 || pct > 100) { showToast('百分比必须在 0-100 之间', 'error'); return; }
            apiPut('gray', { id: id, rollout_percentage: pct }).then(function(res) {
                if (res.code === 0) { showToast('百分比已更新', 'success'); grayPctModal.hide(); loadGray(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteGray(id) {
            confirmDelete('确认删除该灰度规则？', function() {
                apiDelete('gray?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadGray(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== A/B 测试 =====
        let abtestModal = null;
        function loadAbTest() {
            apiGet('abtest').then(function(res) {
                const tbody = document.getElementById('abtest-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="11" class="empty-tip">暂无实验</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    let variants = [], weights = [];
                    try { variants = JSON.parse(r.variants || '[]'); } catch (e) {}
                    try { weights = JSON.parse(r.weights || '[]'); } catch (e) {}
                    let stats = '-';
                    if (r.assignment_stats && r.assignment_stats.length) {
                        stats = r.assignment_stats.map(function(s) {
                            return '<span class="badge-tag badge-info">' + escapeHtml(s.variant) + ': ' + s.cnt + '</span>';
                        }).join(' ');
                    }
                    const variantStr = variants.map(function(v, i) {
                        return escapeHtml(v) + ' <span class="text-muted">(' + (weights[i] || 1) + ')</span>';
                    }).join(', ');
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td class="text-mono">' + escapeHtml(r.test_key) + '</td>' +
                        '<td>' + escapeHtml(r.test_name) + '</td>' +
                        '<td>' + variantStr + '</td>' +
                        '<td>' + (weights.length ? weights.join(', ') : '-') + '</td>' +
                        '<td>' + escapeHtml(r.min_version || '-') + '</td>' +
                        '<td>' + escapeHtml(r.target_platform) + '</td>' +
                        '<td>' + stats + '</td>' +
                        '<td><span class="badge-tag ' + (r.is_active == 1 ? 'badge-active' : 'badge-inactive') + '">' + (r.is_active == 1 ? '启用' : '停用') + '</span></td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td>' +
                            '<button class="btn-action" onclick="editAbTest(' + r.id + ')"><i class="fas fa-edit"></i> 编辑</button>' +
                            '<button class="btn-action btn-toggle ' + (r.is_active == 1 ? 'active' : '') + '" onclick="toggleAbTest(' + r.id + ',' + (r.is_active == 1 ? 0 : 1) + ')"><i class="fas fa-power-off"></i> ' + (r.is_active == 1 ? '停用' : '启用') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteAbTest(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('abtest-tbody').innerHTML = '<tr><td colspan="11" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openAbTestModal() {
            document.getElementById('ab-edit-id').value = '';
            ['ab-key','ab-name','ab-description','ab-variants','ab-weights','ab-min-version'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('ab-platform').value = 'all';
            document.getElementById('ab-active').checked = true;
            document.getElementById('ab-modal-title').textContent = '创建 A/B 实验';
            if (!abtestModal) abtestModal = new bootstrap.Modal(document.getElementById('abtestModal'));
            abtestModal.show();
        }

        function editAbTest(id) {
            apiGet('abtest').then(function(res) {
                if (res.code !== 0) return;
                const r = res.data.find(function(x) { return x.id == id; });
                if (!r) { showToast('未找到实验', 'error'); return; }
                document.getElementById('ab-edit-id').value = r.id;
                document.getElementById('ab-key').value = r.test_key;
                document.getElementById('ab-name').value = r.test_name || '';
                document.getElementById('ab-description').value = r.description || '';
                try {
                    const variants = JSON.parse(r.variants || '[]');
                    document.getElementById('ab-variants').value = variants.join(',');
                } catch(e) {
                    document.getElementById('ab-variants').value = r.variants || '';
                }
                document.getElementById('ab-weights').value = r.weights || '';
                document.getElementById('ab-min-version').value = r.min_version || '';
                document.getElementById('ab-platform').value = r.target_platform || 'all';
                document.getElementById('ab-active').checked = r.is_active == 1;
                document.getElementById('ab-modal-title').textContent = '编辑实验 #' + r.id;
                if (!abtestModal) abtestModal = new bootstrap.Modal(document.getElementById('abtestModal'));
                abtestModal.show();
            });
        }

        function toggleAbTest(id, isActive) {
            apiPut('abtest', { id: id, is_active: !!isActive }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadAbTest(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function saveAbTest() {
            const editId = document.getElementById('ab-edit-id').value;
            const variantsRaw = document.getElementById('ab-variants').value.trim();
            const weightsRaw = document.getElementById('ab-weights').value.trim();
            const variants = variantsRaw ? variantsRaw.split(',').map(function(s) { return s.trim(); }).filter(Boolean) : [];
            const weights = weightsRaw ? weightsRaw.split(',').map(function(s) { return parseInt(s.trim()) || 1; }) : [];

            const payload = {
                test_key: document.getElementById('ab-key').value.trim(),
                test_name: document.getElementById('ab-name').value.trim(),
                description: document.getElementById('ab-description').value.trim(),
                variants: variants,
                weights: weights,
                min_version: document.getElementById('ab-min-version').value.trim(),
                target_platform: document.getElementById('ab-platform').value,
                is_active: document.getElementById('ab-active').checked
            };
            if (!payload.test_key || !payload.test_name) { showToast('实验标识和名称不能为空', 'error'); return; }
            if (variants.length < 2) { showToast('至少需要2个变体', 'error'); return; }

            const p = editId ? apiPut('abtest', Object.assign({ id: parseInt(editId) }, payload))
                             : apiPost('abtest', Object.assign({ action: 'create' }, payload));
            p.then(function(res) {
                if (res.code === 0) {
                    showToast(editId ? '更新成功' : '创建成功', 'success');
                    abtestModal.hide();
                    loadAbTest();
                } else {
                    showToast(res.message || (editId ? '更新失败' : '创建失败'), 'error');
                }
            });
        }

        function deleteAbTest(id) {
            confirmDelete('确认删除该实验？（关联的分配记录也会被清除）', function() {
                apiDelete('abtest?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadAbTest(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 紧急公告 =====
        let emergencyModal = null;
        function loadEmergency() {
            apiGet('emergency?action=all').then(function(res) {
                const tbody = document.getElementById('emergency-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="11" class="empty-tip">暂无公告</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    const levelBadge = '<span class="badge-tag badge-' + r.level + '">' + r.level + '</span>';
                    const actionStr = r.action_text ? escapeHtml(r.action_text) + ' → ' + escapeHtml(truncate(r.action_url, 30)) : '-';
                    const versionRange = (r.min_version || 'any') + ' ~ ' + (r.max_version || 'any');
                    const timeRange = (r.start_time || 'now') + ' ~ ' + (r.end_time || '永久');
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td class="text-mono">' + escapeHtml(r.notice_id) + '</td>' +
                        '<td>' + levelBadge + '</td>' +
                        '<td>' + escapeHtml(r.title) + '</td>' +
                        '<td class="truncate" title="' + escapeHtml(r.content) + '">' + escapeHtml(truncate(r.content, 50)) + '</td>' +
                        '<td class="truncate" title="' + escapeHtml(r.action_url) + '">' + actionStr + '</td>' +
                        '<td>' + versionRange + '</td>' +
                        '<td>' + escapeHtml(r.target_platform) + '</td>' +
                        '<td>' + timeRange + '</td>' +
                        '<td><span class="badge-tag ' + (r.is_active == 1 ? 'badge-active' : 'badge-inactive') + '">' + (r.is_active == 1 ? '启用' : '停用') + '</span></td>' +
                        '<td>' +
                            '<button class="btn-action btn-toggle ' + (r.is_active == 1 ? 'active' : '') + '" onclick="toggleEmergency(' + r.id + ',' + (r.is_active == 1 ? 0 : 1) + ')"><i class="fas fa-power-off"></i> ' + (r.is_active == 1 ? '停用' : '启用') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteEmergency(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('emergency-tbody').innerHTML = '<tr><td colspan="11" class="empty-tip">加载失败</td></tr>';
            });
        }

        function openEmergencyModal() {
            ['em-id','em-title','em-content','em-action-text','em-action-url','em-min-version','em-max-version','em-end-time'].forEach(function(id) { document.getElementById(id).value = ''; });
            document.getElementById('em-level').value = 'info';
            document.getElementById('em-platform').value = 'all';
            if (!emergencyModal) emergencyModal = new bootstrap.Modal(document.getElementById('emergencyModal'));
            emergencyModal.show();
        }

        function saveEmergency() {
            const payload = {
                action: 'create',
                notice_id: document.getElementById('em-id').value.trim(),
                level: document.getElementById('em-level').value,
                title: document.getElementById('em-title').value.trim(),
                content: document.getElementById('em-content').value.trim(),
                action_text: document.getElementById('em-action-text').value.trim(),
                action_url: document.getElementById('em-action-url').value.trim(),
                min_version: document.getElementById('em-min-version').value.trim(),
                max_version: document.getElementById('em-max-version').value.trim(),
                target_platform: document.getElementById('em-platform').value,
                end_time: document.getElementById('em-end-time').value,
                is_active: true
            };
            if (!payload.notice_id || !payload.title) { showToast('公告ID和标题不能为空', 'error'); return; }
            apiPost('emergency', payload).then(function(res) {
                if (res.code === 0) { showToast('创建成功', 'success'); emergencyModal.hide(); loadEmergency(); }
                else { showToast(res.message || '创建失败', 'error'); }
            });
        }

        function toggleEmergency(id, isActive) {
            apiPut('emergency', { id: id, is_active: !!isActive }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadEmergency(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteEmergency(id) {
            confirmDelete('确认删除该公告？', function() {
                apiDelete('emergency?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadEmergency(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 崩溃日志 =====
        function loadCrashStats() {
            apiGet('crash?action=stats').then(function(res) {
                if (res.code !== 0) return;
                const d = res.data;
                document.getElementById('crash-stat-total').textContent = d.total || 0;
                document.getElementById('crash-stat-unresolved').textContent = d.unresolved || 0;
                document.getElementById('crash-stat-resolved').textContent = d.resolved || 0;
                document.getElementById('crash-stat-types').textContent = (d.by_type || []).length;

                const dist = document.getElementById('crash-type-dist');
                if (!d.by_type || !d.by_type.length) {
                    dist.innerHTML = '<p class="empty-tip">暂无数据</p>';
                } else {
                    const max = d.by_type[0].cnt || 1;
                    dist.innerHTML = d.by_type.map(function(item) {
                        const pct = Math.max(5, (item.cnt / max * 100));
                        return '<div style="margin-bottom:8px;">' +
                            '<div style="display:flex;justify-content:space-between;margin-bottom:3px;font-size:13px;">' +
                                '<span class="text-mono">' + escapeHtml(item.crash_type || 'unknown') + '</span>' +
                                '<span class="text-muted">' + item.cnt + ' 次</span>' +
                            '</div>' +
                            '<div style="background:#f0f0f0;height:8px;border-radius:4px;"><div style="background:#00a1d6;height:8px;border-radius:4px;width:' + pct + '%;"></div></div>' +
                        '</div>';
                    }).join('');
                }
            });
        }

        function loadCrashList() {
            const isResolved = document.getElementById('crash-filter-resolved').value;
            const version = document.getElementById('crash-filter-version').value.trim();
            const platform = document.getElementById('crash-filter-platform').value;
            let url = 'crash?limit=100';
            if (isResolved !== '') url += '&is_resolved=' + isResolved;
            if (version) url += '&version=' + encodeURIComponent(version);
            if (platform) url += '&platform=' + encodeURIComponent(platform);
            apiGet(url).then(function(res) {
                const tbody = document.getElementById('crash-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="9" class="empty-tip">暂无崩溃日志</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td class="text-mono truncate" title="' + escapeHtml(r.client_id) + '">' + escapeHtml(truncate(r.client_id, 12)) + '</td>' +
                        '<td>' + escapeHtml(r.version || '-') + '</td>' +
                        '<td>' + escapeHtml(r.platform || '-') + '</td>' +
                        '<td><span class="badge-tag badge-block">' + escapeHtml(r.crash_type || 'unknown') + '</span></td>' +
                        '<td class="truncate" title="' + escapeHtml(r.crash_message) + '">' + escapeHtml(truncate(r.crash_message, 50)) + '</td>' +
                        '<td><span class="badge-tag ' + (r.is_resolved == 1 ? 'badge-resolved' : 'badge-pending') + '">' + (r.is_resolved == 1 ? '已解决' : '未解决') + '</span></td>' +
                        '<td>' +
                            '<button class="btn-action" onclick="viewCrash(' + r.id + ')"><i class="fas fa-eye"></i> 详情</button>' +
                            '<button class="btn-action btn-toggle ' + (r.is_resolved == 1 ? 'active' : '') + '" onclick="toggleCrashResolve(' + r.id + ',' + (r.is_resolved == 1 ? 0 : 1) + ')"><i class="fas fa-check"></i> ' + (r.is_resolved == 1 ? '标记未解决' : '标记已解决') + '</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteCrash(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('crash-tbody').innerHTML = '<tr><td colspan="9" class="empty-tip">加载失败</td></tr>';
            });
        }

        document.getElementById('crash-filter-resolved').addEventListener('change', loadCrashList);
        document.getElementById('crash-filter-version').addEventListener('input', debounce(loadCrashList, 500));
        document.getElementById('crash-filter-platform').addEventListener('change', loadCrashList);

        let crashDetailModal = null;
        function viewCrash(id) {
            apiGet('crash').then(function(res) {
                if (res.code !== 0) return;
                const r = res.data.find(function(x) { return x.id == id; });
                if (!r) { showToast('未找到记录', 'error'); return; }
                let html = '<table class="table table-sm"><tbody>';
                html += '<tr><th style="width:120px;">ID</th><td>' + r.id + '</td></tr>';
                html += '<tr><th>时间</th><td>' + escapeHtml(r.created_at) + '</td></tr>';
                html += '<tr><th>客户端ID</th><td class="text-mono">' + escapeHtml(r.client_id || '-') + '</td></tr>';
                html += '<tr><th>版本/平台</th><td>' + escapeHtml(r.version || '-') + ' / ' + escapeHtml(r.platform || '-') + '</td></tr>';
                html += '<tr><th>类型</th><td><span class="badge-tag badge-block">' + escapeHtml(r.crash_type || 'unknown') + '</span></td></tr>';
                html += '<tr><th>状态</th><td><span class="badge-tag ' + (r.is_resolved == 1 ? 'badge-resolved' : 'badge-pending') + '">' + (r.is_resolved == 1 ? '已解决' : '未解决') + '</span></td></tr>';
                html += '<tr><th>崩溃信息</th><td>' + escapeHtml(r.crash_message || '-') + '</td></tr>';
                html += '<tr><th>系统信息</th><td><pre style="white-space:pre-wrap;max-height:200px;overflow:auto;background:#f7fafc;padding:10px;border-radius:4px;font-size:12px;">' + escapeHtml(r.system_info || '-') + '</pre></td></tr>';
                if (r.stack_trace) {
                    html += '<tr><th>堆栈跟踪</th><td><pre style="white-space:pre-wrap;max-height:300px;overflow:auto;background:#fff5f5;padding:10px;border-radius:4px;font-size:12px;color:#c53030;">' + escapeHtml(r.stack_trace) + '</pre></td></tr>';
                }
                if (r.log_content) {
                    html += '<tr><th>日志内容</th><td><pre style="white-space:pre-wrap;max-height:300px;overflow:auto;background:#f7fafc;padding:10px;border-radius:4px;font-size:12px;">' + escapeHtml(r.log_content) + '</pre></td></tr>';
                }
                html += '</tbody></table>';
                document.getElementById('crash-detail').innerHTML = html;
                if (!crashDetailModal) crashDetailModal = new bootstrap.Modal(document.getElementById('crashDetailModal'));
                crashDetailModal.show();
            });
        }

        function toggleCrashResolve(id, isResolved) {
            apiPut('crash?action=resolve', { id: id, is_resolved: !!isResolved }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadCrashList(); loadCrashStats(); refreshTopStats(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteCrash(id) {
            confirmDelete('确认删除该崩溃记录？', function() {
                apiDelete('crash?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadCrashList(); loadCrashStats(); refreshTopStats(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 用户反馈 =====
        function loadFeedbackStats() {
            apiGet('feedback?action=stats').then(function(res) {
                if (res.code !== 0) return;
                const d = res.data;
                document.getElementById('fb-stat-total').textContent = d.total || 0;
                document.getElementById('fb-stat-pending').textContent = d.pending || 0;
                document.getElementById('fb-stat-replied').textContent = d.replied || 0;
                document.getElementById('fb-stat-resolved').textContent = d.resolved || 0;
            });
        }

        function loadFeedback() {
            const status = document.getElementById('fb-filter-status').value;
            const type = document.getElementById('fb-filter-type').value;
            let url = 'feedback?limit=100';
            if (status) url += '&status=' + status;
            if (type) url += '&type=' + type;
            apiGet(url).then(function(res) {
                const tbody = document.getElementById('feedback-tbody');
                if (res.code !== 0 || !res.data || !res.data.length) {
                    tbody.innerHTML = '<tr><td colspan="10" class="empty-tip">暂无反馈</td></tr>';
                    return;
                }
                tbody.innerHTML = res.data.map(function(r) {
                    const typeBadge = { bug: 'badge-block', suggestion: 'badge-info', question: 'badge-warning', other: 'badge-inactive' }[r.feedback_type] || 'badge-inactive';
                    const statusBadge = { pending: 'badge-pending', replied: 'badge-replied', resolved: 'badge-resolved', closed: 'badge-closed' }[r.status] || 'badge-inactive';
                    return '<tr>' +
                        '<td>' + r.id + '</td>' +
                        '<td>' + escapeHtml(r.created_at) + '</td>' +
                        '<td><span class="badge-tag ' + typeBadge + '">' + escapeHtml(r.feedback_type) + '</span></td>' +
                        '<td>' + escapeHtml(r.title || '-') + '</td>' +
                        '<td class="truncate" title="' + escapeHtml(r.content) + '">' + escapeHtml(truncate(r.content, 50)) + '</td>' +
                        '<td>' + escapeHtml(r.contact || '-') + '</td>' +
                        '<td>' + escapeHtml(r.version || '-') + ' / ' + escapeHtml(r.platform || '-') + '</td>' +
                        '<td><span class="badge-tag ' + statusBadge + '">' + escapeHtml(r.status) + '</span></td>' +
                        '<td class="truncate" title="' + escapeHtml(r.admin_reply) + '">' + escapeHtml(truncate(r.admin_reply, 30) || '-') + '</td>' +
                        '<td>' +
                            '<button class="btn-action" onclick="openFeedbackReply(' + r.id + ')"><i class="fas fa-reply"></i> 回复</button>' +
                            '<button class="btn-action" onclick="updateFeedbackStatus(' + r.id + ',\'resolved\')"><i class="fas fa-check"></i> 已解决</button>' +
                            '<button class="btn-action" onclick="updateFeedbackStatus(' + r.id + ',\'closed\')"><i class="fas fa-times-circle"></i> 关闭</button>' +
                            '<button class="btn-action btn-delete" onclick="deleteFeedback(' + r.id + ')"><i class="fas fa-trash"></i> 删除</button>' +
                        '</td>' +
                        '</tr>';
                }).join('');
            }).catch(function() {
                document.getElementById('feedback-tbody').innerHTML = '<tr><td colspan="10" class="empty-tip">加载失败</td></tr>';
            });
        }

        document.getElementById('fb-filter-status').addEventListener('change', loadFeedback);
        document.getElementById('fb-filter-type').addEventListener('change', loadFeedback);

        let feedbackReplyModal = null;
        function openFeedbackReply(id) {
            apiGet('feedback').then(function(res) {
                if (res.code !== 0) return;
                const r = res.data.find(function(x) { return x.id == id; });
                if (!r) { showToast('未找到反馈', 'error'); return; }
                document.getElementById('fb-id').value = r.id;
                const detail = document.getElementById('fb-detail');
                detail.innerHTML =
                    '<strong>#' + r.id + ' [' + escapeHtml(r.feedback_type) + '] ' + escapeHtml(r.title || '') + '</strong><br>' +
                    '<strong>时间:</strong> ' + escapeHtml(r.created_at) + '<br>' +
                    '<strong>版本/平台:</strong> ' + escapeHtml(r.version || '-') + ' / ' + escapeHtml(r.platform || '-') + '<br>' +
                    '<strong>联系方式:</strong> ' + escapeHtml(r.contact || '-') + '<br>' +
                    '<strong>内容:</strong><br>' + escapeHtml(r.content || '-').replace(/\n/g, '<br>');
                document.getElementById('fb-reply').value = r.admin_reply || '';
                if (!feedbackReplyModal) feedbackReplyModal = new bootstrap.Modal(document.getElementById('feedbackReplyModal'));
                feedbackReplyModal.show();
            });
        }

        function saveFeedbackReply() {
            const id = parseInt(document.getElementById('fb-id').value);
            const reply = document.getElementById('fb-reply').value.trim();
            if (!reply) { showToast('回复内容不能为空', 'error'); return; }
            apiPut('feedback?action=reply', { id: id, admin_reply: reply }).then(function(res) {
                if (res.code === 0) { showToast('回复成功', 'success'); feedbackReplyModal.hide(); loadFeedback(); loadFeedbackStats(); refreshTopStats(); }
                else { showToast(res.message || '回复失败', 'error'); }
            });
        }

        function updateFeedbackStatus(id, status) {
            apiPut('feedback?action=status', { id: id, status: status }).then(function(res) {
                if (res.code === 0) { showToast('状态已更新', 'success'); loadFeedback(); loadFeedbackStats(); refreshTopStats(); }
                else { showToast(res.message || '更新失败', 'error'); }
            });
        }

        function deleteFeedback(id) {
            confirmDelete('确认删除该反馈？', function() {
                apiDelete('feedback?id=' + id).then(function(res) {
                    if (res.code === 0) { showToast('已删除', 'success'); loadFeedback(); loadFeedbackStats(); refreshTopStats(); }
                    else { showToast(res.message || '删除失败', 'error'); }
                });
            });
        }

        // ===== 顶部统计卡片刷新 =====
        function refreshTopStats() {
            apiGet('config').then(function(res) {
                if (res.code === 0 && res.data) {
                    document.getElementById('stat-config').textContent = res.data.length;
                }
            });
            apiGet('blacklist').then(function(res) {
                if (res.code === 0 && res.data) {
                    document.getElementById('stat-blacklist').textContent = res.data.length;
                }
            });
            apiGet('crash?action=stats').then(function(res) {
                if (res.code === 0 && res.data) {
                    document.getElementById('stat-crash').textContent = res.data.unresolved || 0;
                }
            });
            apiGet('feedback?action=stats').then(function(res) {
                if (res.code === 0 && res.data) {
                    document.getElementById('stat-feedback').textContent = res.data.pending || 0;
                }
            });
        }

        // ===== 初始化 =====
        loadConfig();
        refreshTopStats();
    </script>
</body>
</html>
