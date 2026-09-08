<?php
/**
 * 数据库升级脚本
 *
 * 用于从旧云端升级到新云端时，补充新增的数据库表和索引。
 * 安全幂等：重复执行不会出错，不会丢失已有数据。
 *
 * 使用方法：
 *   1. 停止线上服务（或短暂暂停）
 *   2. 用新云端文件覆盖旧云端
 *   3. 浏览器访问 http://你的域名/migrate_db.php
 *   4. 看到"升级成功"后删除此文件
 *
 * 旧云端已有表（不会重建，保留数据）：
 *   - app_version
 *   - announcement
 *
 * 新增表（CREATE TABLE IF NOT EXISTS，安全创建）：
 *   - stat_event, stat_daily, stat_device, stat_error
 *   - crash_log
 *   - hotfix
 *   - remote_file
 *   - user_feedback
 *   - patch_package
 *   - version_blacklist
 *   - gray_release
 *   - ab_test, ab_test_assignment
 *   - emergency_notice
 *   - remote_config
 */

header('Content-Type: text/html; charset=utf-8');

$dbPath = __DIR__ . '/../data/bilidown.db';

echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>数据库升级</title>';
echo '<style>body{font-family:monospace;max-width:800px;margin:40px auto;padding:20px;line-height:1.6}';
echo '.ok{color:#2d8c2d}.fail{color:#d63333}.warn{color:#e8a200}h2{border-bottom:2px solid #333}</style>';
echo '</head><body>';
echo '<h2>B站视频解析工具 - 云端数据库升级</h2>';

// 检查数据库文件是否存在
if (!file_exists($dbPath)) {
    echo '<p class="fail">[错误] 数据库文件不存在: ' . htmlspecialchars($dbPath) . '</p>';
    echo '<p>请确认 data 目录下有 bilidown.db 文件。如果是全新部署，请先运行 data/init_db.php</p>';
    echo '</body></html>';
    exit;
}

// 检查目录可写
$dataDir = dirname($dbPath);
if (!is_writable($dataDir) || !is_writable($dbPath)) {
    echo '<p class="fail">[错误] 数据库文件或目录不可写: ' . htmlspecialchars($dbPath) . '</p>';
    echo '<p>请赋予写入权限后再试</p>';
    echo '</body></html>';
    exit;
}

try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // 自动备份数据库
    $backupPath = $dbPath . '.backup_' . date('Ymd_His');
    if (!copy($dbPath, $backupPath)) {
        echo '<p class="warn">[警告] 数据库备份失败，继续升级...</p>';
    } else {
        echo '<p class="ok">[备份] 数据库已备份到: ' . htmlspecialchars(basename($backupPath)) . '</p>';
    }

    $log = [];

    // ============================================================
    // 1. 确保旧表存在（全新部署场景，不会重建已有表）
    // ============================================================
    echo '<h3>1. 检查基础表</h3>';

    $pdo->exec('CREATE TABLE IF NOT EXISTS app_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version VARCHAR(20) NOT NULL UNIQUE,
        channel VARCHAR(10) DEFAULT "stable",
        platform VARCHAR(10) DEFAULT "windows",
        release_notes TEXT,
        download_url VARCHAR(500) NOT NULL,
        file_size BIGINT,
        sha256 VARCHAR(64),
        min_supported VARCHAR(20),
        force_update BOOLEAN DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        release_date DATE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $log[] = 'app_version 表已就绪';

    $pdo->exec('CREATE TABLE IF NOT EXISTS announcement (
        id VARCHAR(50) PRIMARY KEY,
        type VARCHAR(10) DEFAULT "info",
        title VARCHAR(200) NOT NULL,
        content TEXT NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        action_type VARCHAR(10) DEFAULT "none",
        action_url VARCHAR(500) DEFAULT "",
        dismissible BOOLEAN DEFAULT 1,
        min_version VARCHAR(20) DEFAULT "",
        max_version VARCHAR(20) DEFAULT "",
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $log[] = 'announcement 表已就绪';

    foreach ($log as $msg) {
        echo '<p class="ok">[OK] ' . htmlspecialchars($msg) . '</p>';
    }

    // ============================================================
    // 2. 创建新增表
    // ============================================================
    echo '<h3>2. 创建新增表</h3>';
    $newTables = [];

    // --- 统计相关表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS stat_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type VARCHAR(50) NOT NULL,
        platform VARCHAR(10) DEFAULT "windows",
        version VARCHAR(20) DEFAULT "",
        client_id VARCHAR(64) DEFAULT "",
        extra TEXT DEFAULT "",
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'stat_event';

    $pdo->exec('CREATE TABLE IF NOT EXISTS stat_daily (
        date DATE NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        platform VARCHAR(10) DEFAULT "windows",
        count INT DEFAULT 0,
        unique_count INT DEFAULT 0,
        PRIMARY KEY (date, event_type, platform)
    )');
    $newTables[] = 'stat_daily';

    $pdo->exec('CREATE TABLE IF NOT EXISTS stat_device (
        client_id VARCHAR(64) PRIMARY KEY,
        platform VARCHAR(10) DEFAULT "windows",
        version VARCHAR(20) DEFAULT "",
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'stat_device';

    // stat_device 的 version 字段兼容（旧版表可能没有此字段）
    try {
        $pdo->exec('ALTER TABLE stat_device ADD COLUMN version VARCHAR(20) DEFAULT ""');
        echo '<p class="ok">[OK] stat_device 新增 version 字段</p>';
    } catch (\Exception $e) {
        // 字段已存在，忽略
    }

    $pdo->exec('CREATE TABLE IF NOT EXISTS stat_error (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id VARCHAR(64) DEFAULT "",
        version VARCHAR(20) DEFAULT "",
        platform VARCHAR(10) DEFAULT "windows",
        error_type VARCHAR(100) DEFAULT "",
        error_message TEXT,
        stack_trace TEXT,
        extra TEXT DEFAULT "",
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'stat_error';

    // 统计表索引
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_type ON stat_event(event_type)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_created ON stat_event(created_at)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_event_client ON stat_event(client_id)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_type ON stat_error(error_type)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_created ON stat_error(created_at)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_stat_error_client ON stat_error(client_id)');

    // --- stat_error 新增字段：详细的错误上下文（行号/文件/IP/日志文件路径） ---
    $statErrorNewCols = [
        "error_line" => "INTEGER DEFAULT 0",
        "error_file" => "VARCHAR(500) DEFAULT ''",
        "ip_address" => "VARCHAR(45) DEFAULT ''",
        "log_file"   => "VARCHAR(500) DEFAULT ''",
    ];
    foreach ($statErrorNewCols as $col => $def) {
        try {
            $pdo->exec("ALTER TABLE stat_error ADD COLUMN $col $def");
            echo '<p class="ok">[OK] stat_error 新增字段: ' . htmlspecialchars($col) . '</p>';
        } catch (\Exception $e) {
            // 字段已存在，忽略
        }
    }

    // --- crash_log 新增字段：详细的崩溃上下文 ---
    $crashNewCols = [
        "error_line" => "INTEGER DEFAULT 0",
        "error_file" => "VARCHAR(500) DEFAULT ''",
        "ip_address" => "VARCHAR(45) DEFAULT ''",
    ];
    foreach ($crashNewCols as $col => $def) {
        try {
            $pdo->exec("ALTER TABLE crash_log ADD COLUMN $col $def");
            echo '<p class="ok">[OK] crash_log 新增字段: ' . htmlspecialchars($col) . '</p>';
        } catch (\Exception $e) {
            // 字段已存在，忽略
        }
    }

    // --- 崩溃日志表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS crash_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id VARCHAR(200) DEFAULT "",
        version VARCHAR(20) DEFAULT "",
        platform VARCHAR(20) DEFAULT "",
        crash_type VARCHAR(100) DEFAULT "",
        crash_message TEXT,
        stack_trace TEXT,
        system_info TEXT,
        log_content TEXT,
        is_resolved BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'crash_log';

    // --- 热修复表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS hotfix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotfix_id VARCHAR(100) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT,
        file_path VARCHAR(500) DEFAULT "",
        file_size BIGINT DEFAULT 0,
        sha256 VARCHAR(64) DEFAULT "",
        target_version VARCHAR(20) DEFAULT "",
        target_platform VARCHAR(20) DEFAULT "all",
        is_active BOOLEAN DEFAULT 1,
        is_rollback BOOLEAN DEFAULT 0,
        applied_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'hotfix';

    // --- 远程文件管理表 ---
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
    $newTables[] = 'remote_file';

    // --- 用户反馈表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS user_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id VARCHAR(200) DEFAULT "",
        version VARCHAR(20) DEFAULT "",
        platform VARCHAR(20) DEFAULT "",
        feedback_type VARCHAR(20) DEFAULT "other",
        title VARCHAR(200) DEFAULT "",
        content TEXT,
        contact VARCHAR(200) DEFAULT "",
        system_info TEXT,
        attachments TEXT DEFAULT "",
        status VARCHAR(20) DEFAULT "pending",
        admin_reply TEXT,
        replied_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'user_feedback';

    // --- 增量更新包表 ---
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
    $newTables[] = 'patch_package';

    // --- 版本黑名单表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS version_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version VARCHAR(20) NOT NULL,
        platform VARCHAR(20) DEFAULT "all",
        reason VARCHAR(500) DEFAULT "",
        severity VARCHAR(20) DEFAULT "block",
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'version_blacklist';

    // --- 灰度发布表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS gray_release (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version VARCHAR(20) NOT NULL,
        platform VARCHAR(20) DEFAULT "all",
        channel VARCHAR(50) DEFAULT "stable",
        rollout_percentage INTEGER DEFAULT 0,
        whitelist TEXT DEFAULT "",
        blacklist TEXT DEFAULT "",
        status VARCHAR(20) DEFAULT "active",
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'gray_release';

    // --- AB测试表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS ab_test (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_key VARCHAR(100) NOT NULL UNIQUE,
        test_name VARCHAR(200) NOT NULL,
        description TEXT,
        variants TEXT,
        weights TEXT,
        min_version VARCHAR(20) DEFAULT "",
        target_platform VARCHAR(20) DEFAULT "all",
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'ab_test';

    $pdo->exec('CREATE TABLE IF NOT EXISTS ab_test_assignment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_key VARCHAR(100) NOT NULL,
        client_id VARCHAR(200) NOT NULL,
        variant VARCHAR(100) NOT NULL,
        assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(test_key, client_id)
    )');
    $newTables[] = 'ab_test_assignment';

    // --- 紧急公告表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS emergency_notice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_id VARCHAR(100) NOT NULL UNIQUE,
        level VARCHAR(20) DEFAULT "info",
        title VARCHAR(200) NOT NULL,
        content TEXT,
        action_text VARCHAR(100) DEFAULT "",
        action_url VARCHAR(500) DEFAULT "",
        min_version VARCHAR(20) DEFAULT "",
        max_version VARCHAR(20) DEFAULT "",
        target_platform VARCHAR(20) DEFAULT "all",
        is_active BOOLEAN DEFAULT 1,
        start_time DATETIME,
        end_time DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'emergency_notice';

    // --- 远程配置表 ---
    $pdo->exec('CREATE TABLE IF NOT EXISTS remote_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key VARCHAR(100) NOT NULL UNIQUE,
        config_value TEXT,
        config_type VARCHAR(20) DEFAULT "string",
        description VARCHAR(500) DEFAULT "",
        min_version VARCHAR(20) DEFAULT "",
        max_version VARCHAR(20) DEFAULT "",
        target_platform VARCHAR(20) DEFAULT "all",
        is_active BOOLEAN DEFAULT 1,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');
    $newTables[] = 'remote_config';

    foreach ($newTables as $table) {
        echo '<p class="ok">[OK] ' . htmlspecialchars($table) . ' 表已创建/已存在</p>';
    }

    // ============================================================
    // 3. 创建上传目录
    // ============================================================
    echo '<h3>3. 检查上传目录</h3>';
    $uploadDirs = [
        __DIR__ . '/../uploads/versions',
        __DIR__ . '/../uploads/patches',
        __DIR__ . '/../uploads/hotfixes',
        __DIR__ . '/../uploads/crashlogs',
        __DIR__ . '/../uploads/feedback',
    ];
    foreach ($uploadDirs as $dir) {
        if (!is_dir($dir)) {
            if (@mkdir($dir, 0755, true)) {
                echo '<p class="ok">[OK] 创建目录: ' . htmlspecialchars(str_replace('\\', '/', str_replace(__DIR__ . '/..', '', $dir))) . '</p>';
            } else {
                echo '<p class="warn">[警告] 无法创建目录: ' . htmlspecialchars($dir) . '</p>';
            }
        } else {
            echo '<p class="ok">[OK] 目录已存在: ' . htmlspecialchars(str_replace('\\', '/', str_replace(__DIR__ . '/..', '', $dir))) . '</p>';
        }
    }

    // ============================================================
    // 4. 检查管理后台配置
    // ============================================================
    echo '<h3>4. 检查管理配置</h3>';
    $configPath = __DIR__ . '/../data/admin_config.php';
    if (file_exists($configPath)) {
        echo '<p class="ok">[OK] 管理配置文件已存在: data/admin_config.php</p>';
    } else {
        echo '<p class="warn">[警告] 管理配置文件不存在: data/admin_config.php</p>';
        echo '<p>管理后台（/admin/）和需要Token认证的API将无法使用，请通过管理后台首次访问来生成配置。</p>';
    }

    // ============================================================
    // 5. 补充版本数据（INSERT OR IGNORE，安全幂等）
    // ============================================================
    echo '<h3>5. 补充版本数据</h3>';

    $seedVersions = [
        [
            'version' => '2.1.5',
            'channel' => 'stable',
            'platform' => 'windows',
            'release_notes' => "修复：\r\n- **番剧解析报错**：修复番剧信息解析时 `json.dumps().decode('utf-8')` 在 Python 3 下抛出 `'str' object has no attribute 'decode'` 错误，导致番剧/影视/课程内容无法解析的问题（4 处 Python 2 遗留代码）\r\n- **合集视频下载内容错误**：修复合集视频（如 290 项的大合集）下载时 CID 获取逻辑错误的问题。原代码将\"合集序号\"误当作\"分P序号\"调用 `_get_cid(page=合集序号)`，导致单分P视频报错 `未找到第N集的CID`，或下载到错误的视频内容。修复后优先使用合集项中已有的 cid，无 cid 时使用 `page=1` 获取单分P视频的 CID，确保每个视频使用各自正确的 cid",
            'download_url' => 'https://dl2.edgecos.com/f/fpqTAkXO',
            'file_size' => 255240000,
            'is_active' => 1,
            'release_date' => '2026-08-18'
        ],
    ];

    foreach ($seedVersions as $v) {
        $check = $pdo->prepare('SELECT id FROM app_version WHERE version = ? AND platform = ? AND channel = ?');
        $check->execute([$v['version'], $v['platform'], $v['channel']]);
        if ($check->fetch() !== false) {
            echo '<p class="ok">[跳过] 版本 ' . htmlspecialchars($v['version']) . ' (' . $v['platform'] . '/' . $v['channel'] . ') 已存在</p>';
        } else {
            $stmt = $pdo->prepare('INSERT OR IGNORE INTO app_version (version, channel, platform, release_notes, download_url, file_size, is_active, release_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
            $stmt->execute([
                $v['version'], $v['channel'], $v['platform'], $v['release_notes'],
                $v['download_url'], $v['file_size'], $v['is_active'], $v['release_date']
            ]);
            echo '<p class="ok">[新增] 版本 ' . htmlspecialchars($v['version']) . ' (' . $v['platform'] . '/' . $v['channel'] . ') 已添加</p>';
        }
    }

    // ============================================================
    // 6. 验证表结构
    // ============================================================
    echo '<h3>6. 验证数据库表</h3>';
    $allTables = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")->fetchAll(PDO::FETCH_COLUMN);
    $allIndexes = $pdo->query("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name")->fetchAll(PDO::FETCH_COLUMN);

    echo '<p>数据库共有 <b>' . count($allTables) . '</b> 个表:</p>';
    echo '<ul>';
    foreach ($allTables as $t) {
        $count = $pdo->query("SELECT COUNT(*) FROM \"$t\"")->fetchColumn();
        echo '<li>' . htmlspecialchars($t) . ' (' . $count . ' 条记录)</li>';
    }
    echo '</ul>';

    if (!empty($allIndexes)) {
        echo '<p>索引 (' . count($allIndexes) . ' 个): ' . htmlspecialchars(implode(', ', $allIndexes)) . '</p>';
    }

    // ============================================================
    // 完成
    // ============================================================
    echo '<h3 style="color:#2d8c2d">升级完成!</h3>';
    echo '<p>数据库已成功升级到新版本，所有新增表和索引已就绪。</p>';
    echo '<p class="warn"><b>重要：</b>请立即删除此文件 (migrate_db.php) 以防止被未授权访问！</p>';
    echo '<p>备份数据库: ' . htmlspecialchars(basename($backupPath)) . '</p>';

} catch (PDOException $e) {
    echo '<p class="fail">[错误] 数据库操作失败: ' . htmlspecialchars($e->getMessage()) . '</p>';
} catch (\Exception $e) {
    echo '<p class="fail">[错误] ' . htmlspecialchars($e->getMessage()) . '</p>';
}

echo '</body></html>';
