<?php

$dbPath = __DIR__ . '/bilidown.db';

try {
    $pdo = new PDO('sqlite:' . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $pdo->exec('CREATE TABLE IF NOT EXISTS app_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version VARCHAR(20) NOT NULL UNIQUE,
        channel VARCHAR(10) DEFAULT \'stable\',
        platform VARCHAR(10) DEFAULT \'windows\',
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

    $pdo->exec('CREATE TABLE IF NOT EXISTS announcement (
        id VARCHAR(50) PRIMARY KEY,
        type VARCHAR(10) DEFAULT \'info\',
        title VARCHAR(200) NOT NULL,
        content TEXT NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        action_type VARCHAR(10) DEFAULT \'none\',
        action_url VARCHAR(500) DEFAULT \'\',
        dismissible BOOLEAN DEFAULT 1,
        min_version VARCHAR(20) DEFAULT \'\',
        max_version VARCHAR(20) DEFAULT \'\',
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )');

    $stmt = $pdo->prepare('INSERT OR IGNORE INTO app_version (version, channel, platform, release_notes, download_url, is_active, release_date) VALUES (?, ?, ?, ?, ?, ?, ?)');
    $stmt->execute([
        '1.9.0',
        'stable',
        'windows',
        '初始版本',
        'https://www.bilidown.cn/downloads/B站视频解析工具V1.9.0.zip',
        1,
        '2026-04-19'
    ]);

    $stmt = $pdo->prepare('INSERT OR IGNORE INTO app_version (version, channel, platform, release_notes, download_url, file_size, is_active, release_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
    $stmt->execute([
        '2.1.5',
        'stable',
        'windows',
        "修复：\r\n- **番剧解析报错**：修复番剧信息解析时 `json.dumps().decode('utf-8')` 在 Python 3 下抛出 `'str' object has no attribute 'decode'` 错误，导致番剧/影视/课程内容无法解析的问题（4 处 Python 2 遗留代码）\r\n- **合集视频下载内容错误**：修复合集视频（如 290 项的大合集）下载时 CID 获取逻辑错误的问题。原代码将\"合集序号\"误当作\"分P序号\"调用 `_get_cid(page=合集序号)`，导致单分P视频报错 `未找到第N集的CID`，或下载到错误的视频内容。修复后优先使用合集项中已有的 cid，无 cid 时使用 `page=1` 获取单分P视频的 CID，确保每个视频使用各自正确的 cid",
        'https://dl2.edgecos.com/f/fpqTAkXO',
        255240000,
        1,
        '2026-08-18'
    ]);

    $stmt = $pdo->prepare('INSERT OR IGNORE INTO announcement (id, type, title, content, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)');
    $stmt->execute([
        'ann_20260508_001',
        'info',
        '欢迎使用bilidown',
        'B站视频下载工具已上线，欢迎使用！',
        '2026-05-01',
        '2026-12-31'
    ]);

    echo "数据库初始化成功！\n";
    echo "数据库路径：{$dbPath}\n";
    echo "已创建表：app_version, announcement\n";
    echo "已插入示例数据\n";
} catch (PDOException $e) {
    echo "数据库初始化失败：" . $e->getMessage() . "\n";
    exit(1);
}
