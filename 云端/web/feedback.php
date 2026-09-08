<?php
$title = '问题反馈 - B站视频下载工具bilidown';
$description = '提交B站视频下载工具使用问题反馈，帮助我们改进B站视频解析下载体验，您的反馈对我们很重要';
$keywords = 'B站视频下载反馈, bilidown反馈, 问题反馈, B站下载问题, 视频解析问题';
$canonical = 'https://www.bilidown.cn/feedback.php';
$activePage = 'feedback';

// 连接数据库
$dbPath = __DIR__ . '/../data/bilidown.db';
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// 确保反馈表存在
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

// 允许的图片类型
global $allowedTypes, $maxFileSize, $maxFiles, $uploadDir;
$allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
$maxFileSize = 5 * 1024 * 1024; // 5MB
$maxFiles = 5;
$uploadDir = __DIR__ . '/uploads/';

// 创建上传目录
if (!file_exists($uploadDir)) {
    mkdir($uploadDir, 0755, true);
}

// 处理删除请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete']) && isset($_POST['id'])) {
    $idToDelete = $_POST['id'];
    $stmt = $pdo->prepare('SELECT attachments FROM user_feedback WHERE id = ?');
    $stmt->execute([$idToDelete]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    if ($row && !empty($row['attachments'])) {
        $files = json_decode($row['attachments'], true);
        if (is_array($files)) {
            foreach ($files as $file) {
                $filePath = __DIR__ . '/' . $file;
                if (file_exists($filePath)) {
                    @unlink($filePath);
                }
            }
        }
    }
    $stmt = $pdo->prepare('DELETE FROM user_feedback WHERE id = ?');
    $stmt->execute([$idToDelete]);
    echo json_encode(['success' => $stmt->rowCount() > 0]);
    exit;
}

// 处理AJAX表单提交
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'submit_feedback') {
    try {
        // XSS防护函数
        function sanitize_input($data) {
            $data = trim($data);
            $data = stripslashes($data);
            $data = htmlspecialchars($data, ENT_QUOTES, 'UTF-8');
            return $data;
        }

        // 验证图片文件
        function validate_image($file) {
            global $allowedTypes, $maxFileSize;
            
            if ($file['size'] > $maxFileSize) {
                throw new Exception('文件大小不能超过5MB');
            }
            
            $finfo = new finfo(FILEINFO_MIME_TYPE);
            $fileType = $finfo->file($file['tmp_name']);
            
            if (!in_array($fileType, $allowedTypes)) {
                throw new Exception('只允许上传图片文件');
            }
            
            if (!getimagesize($file['tmp_name'])) {
                throw new Exception('文件不是有效的图片');
            }
            
            return $fileType;
        }

        // 获取表单数据
        $feedbackType = sanitize_input($_POST['feedbackType'] ?? '');
        $feedbackTitle = sanitize_input($_POST['feedbackTitle'] ?? '');
        $feedbackDescription = sanitize_input($_POST['feedbackDescription'] ?? '');
        $contactInfo = sanitize_input($_POST['contactInfo'] ?? '');
        $browserInfo = sanitize_input($_POST['browserInfo'] ?? '');
        $ipAddress = sanitize_input($_POST['ipAddress'] ?? '');

        if (empty($feedbackType) || empty($feedbackTitle) || empty($feedbackDescription)) {
            throw new Exception('请填写完整的表单信息');
        }

        // 处理文件上传
        $uploadedFiles = [];
        if (isset($_FILES['fileUpload']) && !empty($_FILES['fileUpload']['name'][0])) {
            $fileCount = count($_FILES['fileUpload']['name']);
            
            if ($fileCount > $maxFiles) {
                throw new Exception("最多只能上传{$maxFiles}张图片");
            }

            for ($i = 0; $i < $fileCount; $i++) {
                if ($_FILES['fileUpload']['error'][$i] !== UPLOAD_ERR_OK) {
                    continue;
                }

                $file = [
                    'name' => $_FILES['fileUpload']['name'][$i],
                    'tmp_name' => $_FILES['fileUpload']['tmp_name'][$i],
                    'size' => $_FILES['fileUpload']['size'][$i],
                    'type' => $_FILES['fileUpload']['type'][$i],
                    'error' => $_FILES['fileUpload']['error'][$i]
                ];

                $fileType = validate_image($file);

                $extension = str_replace('image/', '', $fileType);
                $uniqueName = uniqid() . '_' . time() . '.' . $extension;
                $filePath = $uploadDir . $uniqueName;

                if (move_uploaded_file($file['tmp_name'], $filePath)) {
                    $uploadedFiles[] = 'uploads/' . $uniqueName;
                }
            }
        }

        // 保存到数据库
        $systemInfo = json_encode(['browser' => $browserInfo, 'ip' => $ipAddress], JSON_UNESCAPED_UNICODE);
        $attachmentsJson = json_encode($uploadedFiles, JSON_UNESCAPED_UNICODE);

        $stmt = $pdo->prepare("INSERT INTO user_feedback (client_id, version, platform, feedback_type, title, content, contact, system_info, attachments, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')");
        $stmt->execute(['', '', 'web', $feedbackType, $feedbackTitle, $feedbackDescription, $contactInfo, $systemInfo, $attachmentsJson]);
        $feedbackId = $pdo->lastInsertId();

        // 设置cookie标记用户自己的反馈
        if (!isset($_COOKIE['my_feedbacks'])) {
            $myFeedbacks = [];
        } else {
            $myFeedbacks = json_decode($_COOKIE['my_feedbacks'], true) ?: [];
        }
        $myFeedbacks[] = $feedbackId;
        setcookie('my_feedbacks', json_encode($myFeedbacks), time() + (365 * 24 * 60 * 60), '/');

        echo json_encode([
            'success' => true,
            'feedback' => [
                'id' => $feedbackId,
                'type' => $feedbackType,
                'title' => $feedbackTitle,
                'description' => $feedbackDescription,
                'date' => date('Y-m-d H:i:s'),
                'files' => $uploadedFiles
            ]
        ]);

    } catch (Exception $e) {
        echo json_encode([
            'success' => false,
            'message' => $e->getMessage()
        ]);
    }
    exit;
}

// 读取反馈数据
$stmt = $pdo->query('SELECT * FROM user_feedback ORDER BY created_at DESC');
$feedbacks = $stmt->fetchAll(PDO::FETCH_ASSOC);

// 获取用户自己的反馈ID列表
$myFeedbacks = [];
if (isset($_COOKIE['my_feedbacks'])) {
    $myFeedbacks = json_decode($_COOKIE['my_feedbacks'], true) ?: [];
}

require_once 'header.php';
?>

<style>
        /* 页面标题 */
        .page-header {
            padding: 3rem 0 2rem;
            background: var(--card-bg);
            margin-bottom: 2rem;
        }
        
        .page-header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--text-color);
            text-align: center;
            margin-bottom: 1rem;
        }
        
        .page-header p {
            font-size: 1.1rem;
            color: var(--muted);
            text-align: center;
            max-width: 600px;
            margin: 0 auto;
        }
        
        /* 表单区域 */
        .feedback-form {
            background: var(--card-bg);
            padding: 2rem;
            box-shadow: var(--shadow);
            margin-bottom: 2rem;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-label {
            font-weight: 600;
            color: var(--text-color);
            margin-bottom: 0.5rem;
            display: block;
        }
        
        .form-control {
            border: 2px solid var(--border);
            padding: 0.75rem 1rem;
            font-size: 1rem;
            background: var(--card-bg);
            color: var(--text-color);
            transition: border-color 0.2s;
        }
        
        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(0, 161, 214, 0.1);
        }
        
        .form-control::placeholder {
            color: var(--muted);
        }
        
        textarea.form-control {
            resize: vertical;
            min-height: 150px;
        }
        
        .form-select {
            border: 2px solid var(--border);
            padding: 0.75rem 1rem;
            font-size: 1rem;
            background: var(--card-bg);
            color: var(--text-color);
            transition: border-color 0.2s;
        }
        
        .form-select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(0, 161, 214, 0.1);
        }
        
        /* 文件上传 */
        .file-upload {
            border: 2px dashed var(--border);
            padding: 2rem;
            text-align: center;
            transition: border-color 0.2s;
            background: var(--card-bg);
        }
        
        .file-upload:hover {
            border-color: var(--primary);
        }
        
        .file-upload input[type="file"] {
            display: none;
        }
        
        .file-upload label {
            cursor: pointer;
            color: var(--primary);
            font-weight: 600;
        }
        
        .file-upload label:hover {
            text-decoration: underline;
        }
        
        .file-info {
            margin-top: 1rem;
            font-size: 0.9rem;
            color: var(--muted);
        }
        
        .file-preview {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
        
        .file-preview-item {
            position: relative;
            width: 80px;
            height: 80px;
            overflow: hidden;
            border: 1px solid var(--border);
        }
        
        .file-preview-item img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .file-preview-item .remove-btn {
            position: absolute;
            top: 5px;
            right: 5px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: rgba(220, 53, 69, 0.9);
            color: white;
            border: none;
            cursor: pointer;
            font-size: 12px;
            line-height: 20px;
            text-align: center;
        }
        
        /* 按钮样式 */
        .btn-primary {
            background: var(--primary);
            border: none;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        
        .btn-primary:hover {
            background: var(--primary-dark);
        }
        
        /* 响应式设计 */
        @media (min-width: 768px) {
            .navbar {
                padding: 1rem 0;
            }
            
            .navbar-brand {
                font-size: 1.5rem;
                gap: 0.75rem;
            }
            
            .navbar-brand i {
                font-size: 1.75rem;
            }
            
            .page-header {
                padding: 4rem 0 3rem;
                margin-bottom: 3rem;
            }
            
            .page-header h1 {
                font-size: 3rem;
                margin-bottom: 1.5rem;
            }
            
            .feedback-form {
                padding: 3rem;
                margin-bottom: 3rem;
            }
        }
        
        @media (max-width: 767px) {
            body {
                padding-top: 60px;
            }
            
            .page-header {
                padding: 2rem 0 1.5rem;
            }
            
            .page-header h1 {
                font-size: 2rem;
            }
            
            .feedback-form {
                padding: 1.5rem;
            }
            
            .file-upload {
                padding: 1.5rem;
            }
        }
        
        [data-theme="light"] body {
            background: var(--bg-gradient) !important;
            color: var(--text-color) !important;
        }
        
        [data-theme="light"] .navbar {
            background: rgba(255, 255, 255, 0.85) !important;
            border-bottom-color: rgba(0, 0, 0, 0.06) !important;
        }
        
        [data-theme="light"] .nav-link {
            color: var(--gray) !important;
        }
        
        [data-theme="light"] .nav-link:hover,
        [data-theme="light"] .nav-link.active {
            color: var(--primary) !important;
            background: rgba(0, 161, 214, 0.06);
        }
        
        [data-theme="light"] .page-header {
            background: transparent;
        }
        
        [data-theme="light"] .page-header h1 {
            color: var(--text-color);
        }
        
        [data-theme="light"] .page-header p {
            color: var(--text-secondary);
        }
        
        [data-theme="light"] .feedback-form {
            background: var(--card-bg);
        }
        
        [data-theme="light"] .form-label {
            color: var(--text-color);
        }
        
        [data-theme="light"] .form-control,
        [data-theme="light"] .form-select {
            background: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }
        
        [data-theme="light"] .form-control::placeholder {
            color: var(--muted) !important;
        }
        
        [data-theme="light"] .file-upload {
            border-color: var(--border);
            background: var(--card-bg);
        }
        
        [data-theme="light"] .file-upload:hover {
            border-color: var(--primary);
        }
        
        [data-theme="light"] .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
            border-color: var(--primary) !important;
        }
        
        [data-theme="light"] .btn-primary:hover {
            background: linear-gradient(135deg, var(--primary-dark), var(--primary)) !important;
        }
        
        /* 成功/错误提示 */
        .success-message {
            background: rgba(56, 161, 105, 0.1);
            border: 1px solid rgba(56, 161, 105, 0.3);
            padding: 1rem;
            margin-bottom: 1.5rem;
            color: var(--success);
            text-align: center;
        }
        
        .error-message {
            background: rgba(220, 53, 69, 0.1);
            border: 1px solid rgba(220, 53, 69, 0.3);
            padding: 1rem;
            margin-bottom: 1.5rem;
            color: var(--danger);
            text-align: center;
        }
        
        /* 评论区 */
        .comments-section {
            margin-top: 3rem;
        }
        
        .comments-section h2 {
            margin-bottom: 2rem;
            color: var(--text-color);
            font-weight: 700;
            font-size: 1.5rem;
        }
        
        .comment-card {
            background: var(--card-bg);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow);
            border-left: 4px solid var(--primary);
            position: relative;
        }
        
        .comment-card .delete-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: transparent;
            border: none;
            color: var(--muted);
            cursor: pointer;
            font-size: 1.2rem;
            padding: 5px;
            transition: color 0.2s;
        }
        
        .comment-card .delete-btn:hover {
            color: var(--danger);
        }
        
        .comment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .comment-type {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .comment-type.bug {
            background: rgba(220, 53, 69, 0.1);
            color: var(--danger);
        }
        
        .comment-type.feature {
            background: rgba(56, 161, 105, 0.1);
            color: var(--success);
        }
        
        .comment-type.performance {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
        }
        
        .comment-type.other {
            background: rgba(107, 114, 128, 0.1);
            color: var(--muted);
        }
        
        .comment-date {
            color: var(--muted);
            font-size: 0.9rem;
        }
        
        .comment-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-color);
            margin-bottom: 0.75rem;
        }
        
        .comment-content {
            color: var(--text-color);
            line-height: 1.6;
            margin-bottom: 1rem;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .comment-images {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 1rem;
        }
        
        .comment-image {
            width: 100px;
            height: 100px;
            overflow: hidden;
            border: 1px solid var(--border);
            cursor: pointer;
        }
        
        .comment-image img {
            width: 100%;
            height: 100px;
            object-fit: cover;
        }
        
        /* 图片模态框 */
        .image-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 10000;
            justify-content: center;
            align-items: center;
        }
        
        .image-modal.active {
            display: flex;
        }
        
        .image-modal img {
            max-width: 90%;
            max-height: 90%;
        }
        
        .image-modal .close-btn {
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 40px;
            color: white;
            cursor: pointer;
            z-index: 10001;
        }
        
        /* 页脚 */
        .footer {
            background: var(--card-bg);
            color: var(--text-color);
            padding: 2rem 0;
            margin-top: 3rem;
            border-top: 1px solid var(--border);
        }
        
        .footer p {
            text-align: center;
            color: var(--muted);
            margin: 0;
        }
        
        /* 工具条 */
        #toolBar {
            position: fixed;
            right: 20px;
            bottom: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        .tool-item {
            position: relative;
        }
        
        #toolBar button {
            width: 60px;
            height: 60px;
            background: var(--primary);
            color: white;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 20px;
        }
        
        #toolBar button:hover {
            background: var(--primary-dark);
        }
        
        .tool-separator {
            height: 1px;
            background: rgba(255,255,255,0.2);
            width: 100%;
        }
        
        #rewardPopup {
            position: fixed;
            right: 90px;
            bottom: 20px;
            background: var(--card-bg);
            color: var(--text-color);
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            width: 200px;
            display: none;
            border: 2px solid var(--primary);
            z-index: 9999;
        }
        
        #rewardPopup .popup-header {
            background: var(--primary);
            color: white;
            padding: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        #rewardPopup .popup-header span {
            font-weight: 600;
            font-size: 16px;
        }
        
        #rewardPopup .popup-content {
            padding: 0;
        }
        
        #rewardPopup img {
            width: 100%;
            height: auto;
            display: block;
        }
        
        /* 响应式工具条 */
        @media (max-width: 768px) {
            #toolBar {
                right: 10px;
                bottom: 10px;
            }
            
            #toolBar button {
                width: 50px;
                height: 50px;
                font-size: 16px;
            }
            
            #rewardPopup {
                right: 70px;
                bottom: 10px;
                width: 150px;
            }
        }
</style>
</head>
<body>

    <!-- 页面标题 -->
    <section class="page-header">
        <div class="container">
            <h1>问题反馈</h1>
            <p>如果您在使用过程中遇到任何问题或有任何建议，欢迎提交反馈</p>
        </div>
    </section>

    <!-- 反馈表单 -->
    <section class="container">
        <div class="feedback-form">
            <div id="messageContainer"></div>
            
            <form id="feedbackForm">
                <input type="hidden" name="action" value="submit_feedback">
                <div class="form-group">
                    <label for="feedbackType" class="form-label">问题类型</label>
                    <select class="form-select" id="feedbackType" name="feedbackType" required>
                        <option value="">请选择问题类型</option>
                        <option value="bug">功能Bug</option>
                        <option value="feature">功能建议</option>
                        <option value="performance">性能问题</option>
                        <option value="other">其他问题</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="feedbackTitle" class="form-label">问题标题</label>
                    <input type="text" class="form-control" id="feedbackTitle" name="feedbackTitle" placeholder="请简要描述问题" required>
                </div>
                
                <div class="form-group">
                    <label for="feedbackDescription" class="form-label">问题描述</label>
                    <textarea class="form-control" id="feedbackDescription" name="feedbackDescription" placeholder="请详细描述您遇到的问题，包括操作步骤、错误信息等" required></textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">上传截图（可选，最多5张）</label>
                    <div class="file-upload">
                        <input type="file" id="fileUpload" name="fileUpload[]" accept="image/*" multiple>
                        <label for="fileUpload">
                            <i class="fas fa-upload"></i> 点击或拖拽图片到此处上传
                        </label>
                        <div class="file-info" id="fileInfo">
                            支持上传JPG、PNG、GIF、WEBP格式（单个文件最大5MB）
                        </div>
                        <div class="file-preview" id="filePreview"></div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="contactInfo" class="form-label">联系方式（可选）</label>
                    <input type="text" class="form-control" id="contactInfo" name="contactInfo" placeholder="请留下您的邮箱或QQ，以便我们联系您">
                </div>
                
                <div class="form-group">
                    <label for="browserInfo" class="form-label">浏览器信息</label>
                    <input type="text" class="form-control" id="browserInfo" name="browserInfo" value="<?php echo htmlspecialchars($_SERVER['HTTP_USER_AGENT'] ?? ''); ?>" readonly>
                </div>
                
                <div class="form-group">
                    <label for="ipAddress" class="form-label">IP地址</label>
                    <input type="text" class="form-control" id="ipAddress" name="ipAddress" value="<?php echo htmlspecialchars($_SERVER['REMOTE_ADDR'] ?? ''); ?>" readonly>
                </div>
                
                <div class="text-center">
                    <button type="submit" class="btn btn-primary">提交反馈</button>
                </div>
            </form>
        </div>
    </section>

    <!-- 评论区 -->
    <section class="container comments-section" id="commentsSection">
        <h2><i class="fas fa-comments"></i> 最新反馈</h2>
        
        <?php if (empty($feedbacks)): ?>
            <div class="text-center text-muted py-5" id="emptyMessage">
                <i class="fas fa-inbox fa-3x mb-3"></i>
                <p>暂无反馈，成为第一个反馈者吧！</p>
            </div>
        <?php else: ?>
            <?php foreach ($feedbacks as $feedback): ?>
                <?php
                $type = $feedback['feedback_type'] ?? 'other';
                $typeLabels = ['bug' => 'Bug', 'feature' => '建议', 'suggestion' => '建议', 'question' => '问题', 'performance' => '性能', 'other' => '其他'];
                $files = [];
                if (!empty($feedback['attachments'])) {
                    $decoded = json_decode($feedback['attachments'], true);
                    if (is_array($decoded)) $files = $decoded;
                }
                ?>
                <div class="comment-card" data-id="<?php echo htmlspecialchars($feedback['id']); ?>">
                    <?php if (in_array($feedback['id'], $myFeedbacks)): ?>
                        <button class="delete-btn" onclick="deleteFeedback('<?php echo htmlspecialchars($feedback['id']); ?>')">
                            <i class="fas fa-times"></i>
                        </button>
                    <?php endif; ?>
                    <div class="comment-header">
                        <span class="comment-type <?php echo htmlspecialchars($type); ?>">
                            <?php echo $typeLabels[$type] ?? '其他'; ?>
                        </span>
                        <span class="comment-date"><?php echo htmlspecialchars($feedback['created_at']); ?></span>
                    </div>
                    <h3 class="comment-title"><?php echo htmlspecialchars($feedback['title'] ?: '(无标题)'); ?></h3>
                    <div class="comment-content"><?php echo htmlspecialchars($feedback['content'] ?: '(无内容)'); ?></div>
                    
                    <?php if (!empty($files)): ?>
                        <div class="comment-images">
                            <?php foreach ($files as $file): ?>
                                <div class="comment-image" onclick="showImageModal('<?php echo htmlspecialchars($file); ?>')">
                                    <img src="<?php echo htmlspecialchars($file); ?>" alt="反馈图片">
                                </div>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        <?php endif; ?>
    </section>

    <!-- 图片模态框 -->
    <div class="image-modal" id="imageModal" onclick="closeImageModal()">
        <span class="close-btn" onclick="closeImageModal()">&times;</span>
        <img src="" id="modalImage" alt="大图预览">
    </div>



    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        let selectedFiles = [];
        const myFeedbacks = <?php echo json_encode($myFeedbacks); ?>;
        
        document.addEventListener('DOMContentLoaded', function() {
            const fileUpload = document.getElementById('fileUpload');
            const fileInfo = document.getElementById('fileInfo');
            const filePreview = document.getElementById('filePreview');
            
            // 文件选择事件
            fileUpload.addEventListener('change', function(e) {
                handleFiles(e.target.files);
            });
            
            // 拖拽上传
            const fileUploadArea = document.querySelector('.file-upload');
            
            fileUploadArea.addEventListener('dragover', function(e) {
                e.preventDefault();
                fileUploadArea.style.borderColor = 'var(--primary)';
                fileUploadArea.style.background = 'rgba(0, 161, 214, 0.05)';
            });
            
            fileUploadArea.addEventListener('dragleave', function() {
                fileUploadArea.style.borderColor = 'var(--border)';
                fileUploadArea.style.background = 'var(--card-bg)';
            });
            
            fileUploadArea.addEventListener('drop', function(e) {
                e.preventDefault();
                fileUploadArea.style.borderColor = 'var(--border)';
                fileUploadArea.style.background = 'var(--card-bg)';
                
                if (e.dataTransfer.files.length > 0) {
                    handleFiles(e.dataTransfer.files);
                }
            });
            
            // 处理文件
            function handleFiles(files) {
                for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    
                    // 检查文件数量
                    if (selectedFiles.length >= <?php echo $maxFiles; ?>) {
                        alert(`最多只能上传<?php echo $maxFiles; ?>张图片`);
                        break;
                    }
                    
                    // 检查文件大小
                    if (file.size > <?php echo $maxFileSize; ?>) {
                        alert('文件大小不能超过5MB');
                        continue;
                    }
                    
                    // 检查文件类型
                    if (!file.type.startsWith('image/')) {
                        alert('只允许上传图片文件');
                        continue;
                    }
                    
                    // 添加到选中文件
                    if (selectedFiles.find(f => f.name === file.name) === undefined) {
                        selectedFiles.push(file);
                        updatePreview();
                    }
                }
            }
            
            // 更新预览
            function updatePreview() {
                filePreview.innerHTML = '';
                
                selectedFiles.forEach((file, index) => {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const item = document.createElement('div');
                        item.className = 'file-preview-item';
                        item.innerHTML = `
                            <img src="${e.target.result}" alt="${file.name}">
                            <button class="remove-btn" onclick="removeFile(${index})">&times;</button>
                        `;
                        filePreview.appendChild(item);
                    };
                    reader.readAsDataURL(file);
                });
                
                // 更新文件信息
                if (selectedFiles.length > 0) {
                    let info = `已选择 ${selectedFiles.length} 张图片`;
                    const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
                    if (totalSize > 0) {
                        info += ` (${(totalSize / 1024).toFixed(2)} KB)`;
                    }
                    fileInfo.textContent = info;
                } else {
                    fileInfo.textContent = '支持上传JPG、PNG、GIF、WEBP格式（单个文件最大5MB）';
                }
                
                // 同步到input
                const dataTransfer = new DataTransfer();
                selectedFiles.forEach(file => dataTransfer.items.add(file));
                fileUpload.files = dataTransfer.files;
            }
            
            // 移除文件
            window.removeFile = function(index) {
                selectedFiles.splice(index, 1);
                updatePreview();
            };
            
            // AJAX表单提交
            document.getElementById('feedbackForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const feedbackType = document.getElementById('feedbackType').value;
                const feedbackTitle = document.getElementById('feedbackTitle').value;
                const feedbackDescription = document.getElementById('feedbackDescription').value;
                
                if (!feedbackType) {
                    alert('请选择问题类型');
                    return;
                }
                
                if (!feedbackTitle) {
                    alert('请填写问题标题');
                    return;
                }
                
                if (!feedbackDescription) {
                    alert('请填写问题描述');
                    return;
                }
                
                // 创建FormData
                const formData = new FormData(this);
                
                // 显示加载状态
                const submitBtn = this.querySelector('button[type="submit"]');
                const originalText = submitBtn.textContent;
                submitBtn.textContent = '提交中...';
                submitBtn.disabled = true;
                
                // AJAX提交
                fetch('feedback.php', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 显示成功消息
                        showMessage('反馈提交成功！', 'success');
                        
                        // 重置表单
                        this.reset();
                        selectedFiles = [];
                        updatePreview();
                        
                        // 添加新反馈到页面顶部
                        addFeedbackToPage(data.feedback);
                        
                        // 更新myFeedbacks
                        myFeedbacks.push(data.feedback.id);
                    } else {
                        showMessage(data.message || '提交失败，请稍后重试', 'error');
                    }
                })
                .catch(error => {
                    console.error('提交错误:', error);
                    showMessage('提交失败，请稍后重试', 'error');
                })
                .finally(() => {
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                });
            });
        });
        
        // 显示消息
        function showMessage(message, type) {
            const container = document.getElementById('messageContainer');
            const className = type === 'success' ? 'success-message' : 'error-message';
            const iconClass = type === 'success' ? 'check-circle' : 'exclamation-circle';
            
            container.innerHTML = `
                <div class="${className}">
                    <i class="fas fa-${iconClass}"></i> ${message}
                </div>
            `;
            
            // 3秒后自动隐藏
            setTimeout(() => {
                container.innerHTML = '';
            }, 3000);
        }
        
        // 添加反馈到页面
        function addFeedbackToPage(feedback) {
            const container = document.getElementById('commentsSection');
            
            // 移除空消息
            const emptyMessage = document.getElementById('emptyMessage');
            if (emptyMessage) {
                emptyMessage.remove();
            }
            
            // 创建反馈卡片
            const typeLabels = {'bug': 'Bug', 'feature': '建议', 'performance': '性能', 'other': '其他'};
            let imagesHTML = '';
            
            if (feedback.files && feedback.files.length > 0) {
                imagesHTML = '<div class="comment-images">';
                feedback.files.forEach(file => {
                    imagesHTML += `
                        <div class="comment-image" onclick="showImageModal('${file}')">
                            <img src="${file}" alt="反馈图片">
                        </div>
                    `;
                });
                imagesHTML += '</div>';
            }
            
            const cardHTML = `
                <div class="comment-card" data-id="${feedback.id}">
                    <button class="delete-btn" onclick="deleteFeedback('${feedback.id}')">
                        <i class="fas fa-times"></i>
                    </button>
                    <div class="comment-header">
                        <span class="comment-type ${feedback.type}">${typeLabels[feedback.type]}</span>
                        <span class="comment-date">${feedback.date}</span>
                    </div>
                    <h3 class="comment-title">${feedback.title}</h3>
                    <div class="comment-content">${feedback.description}</div>
                    ${imagesHTML}
                </div>
            `;
            
            // 插入到第一个卡片之前
            const firstCard = container.querySelector('.comment-card');
            if (firstCard) {
                firstCard.insertAdjacentHTML('beforebegin', cardHTML);
            } else {
                // 如果没有卡片，添加到标题之后
                const title = container.querySelector('h2');
                title.insertAdjacentHTML('afterend', cardHTML);
            }
        }
        
        // 图片模态框
        function showImageModal(src) {
            const modal = document.getElementById('imageModal');
            const modalImage = document.getElementById('modalImage');
            modalImage.src = src;
            modal.classList.add('active');
        }
        
        function closeImageModal() {
            const modal = document.getElementById('imageModal');
            modal.classList.remove('active');
        }
        
        // ESC键关闭模态框
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeImageModal();
            }
        });
        
        // 删除反馈
        window.deleteFeedback = function(id) {
            if (!confirm('确定要删除这条反馈吗？')) {
                return;
            }
            
            const formData = new FormData();
            formData.append('delete', '1');
            formData.append('id', id);
            
            fetch('feedback.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 从DOM中移除
                    const card = document.querySelector(`.comment-card[data-id="${id}"]`);
                    if (card) {
                        card.style.opacity = '0';
                        card.style.transition = 'opacity 0.3s';
                        setTimeout(() => card.remove(), 300);
                    }
                    
                    // 检查是否还有反馈
                    const remainingCards = document.querySelectorAll('.comment-card');
                    if (remainingCards.length === 0) {
                        const section = document.getElementById('commentsSection');
                        section.innerHTML = `
                            <h2><i class="fas fa-comments"></i> 最新反馈</h2>
                            <div class="text-center text-muted py-5" id="emptyMessage">
                                <i class="fas fa-inbox fa-3x mb-3"></i>
                                <p>暂无反馈，成为第一个反馈者吧！</p>
                            </div>
                        `;
                    }
                } else {
                    alert('删除失败，请稍后重试');
                }
            })
            .catch(error => {
                console.error('删除错误:', error);
                alert('删除失败，请稍后重试');
            });
        };
    </script>

<?php require_once 'footer.php'; ?>
</html>
