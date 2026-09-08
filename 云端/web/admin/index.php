<?php
// 后台管理主页面
require_once 'auth.php';

// 检查登录
require_admin_login();

// 连接数据库
$dbPath = __DIR__ . '/../../data/bilidown.db';
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

// 处理删除请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'delete' && isset($_POST['id'])) {
    $idToDelete = $_POST['id'];
    $stmt = $pdo->prepare('DELETE FROM user_feedback WHERE id = ?');
    $stmt->execute([$idToDelete]);
    $deleted = $stmt->rowCount() > 0;
    echo json_encode(['success' => $deleted]);
    exit;
}

// 读取反馈数据
$stmt = $pdo->query('SELECT * FROM user_feedback ORDER BY created_at DESC');
$feedbacks = $stmt->fetchAll(PDO::FETCH_ASSOC);

// 统计数据
$totalCount = count($feedbacks);
$bugCount = 0;
$featureCount = 0;
$performanceCount = 0;
$otherCount = 0;

foreach ($feedbacks as $fb) {
    switch ($fb['feedback_type']) {
        case 'bug': $bugCount++; break;
        case 'suggestion':
        case 'feature': $featureCount++; break;
        case 'performance': $performanceCount++; break;
        default: $otherCount++; break;
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>后台管理 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: #f5f7fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* 主容器 */
        .container {
            max-width: 1400px;
            margin: 30px auto;
            padding: 0 30px;
        }
        
        /* 统计卡片 */
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .stat-icon {
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
        }
        
        .stat-icon.total { background: #667eea; }
        .stat-icon.bug { background: #fc8181; }
        .stat-icon.feature { background: #68d391; }
        .stat-icon.performance { background: #fbd38d; }
        .stat-icon.other { background: #a0aec0; }
        
        .stat-info h3 {
            font-size: 28px;
            font-weight: 700;
            color: #333;
            margin-bottom: 5px;
        }
        
        .stat-info p {
            color: #666;
            font-size: 14px;
        }
        
        /* 筛选栏 */
        .filter-bar {
            background: white;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .filter-select {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            font-size: 14px;
            min-width: 150px;
        }
        
        .filter-select:focus {
            border-color: #667eea;
            outline: none;
        }
        
        /* 反馈列表 */
        .feedback-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .feedback-card {
            background: white;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
            position: relative;
        }
        
        .feedback-card.bug { border-left-color: #fc8181; }
        .feedback-card.feature { border-left-color: #68d391; }
        .feedback-card.performance { border-left-color: #fbd38d; }
        .feedback-card.other { border-left-color: #a0aec0; }
        
        .feedback-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
            gap: 15px;
        }
        
        .feedback-title-wrap {
            flex: 1;
        }
        
        .feedback-badge {
            display: inline-block;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .feedback-badge.bug { background: #fff5f5; color: #c53030; }
        .feedback-badge.feature { background: #f0fff4; color: #276749; }
        .feedback-badge.performance { background: #fffaf0; color: #c05621; }
        .feedback-badge.other { background: #f7fafc; color: #4a5568; }
        
        .feedback-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }
        
        .feedback-meta {
            display: flex;
            gap: 20px;
            color: #666;
            font-size: 13px;
        }
        
        .feedback-meta span {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .delete-btn {
            background: none;
            border: none;
            color: #a0aec0;
            font-size: 18px;
            cursor: pointer;
            padding: 5px;
            transition: color 0.3s;
        }
        
        .delete-btn:hover {
            color: #c53030;
        }
        
        .feedback-content {
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 15px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .feedback-images {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
        }
        
        .feedback-image {
            width: 120px;
            height: 120px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
            cursor: pointer;
        }
        
        .feedback-image img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        /* 空状态 */
        .empty-state {
            background: white;
            padding: 60px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .empty-state i {
            font-size: 60px;
            color: #a0aec0;
            margin-bottom: 20px;
        }
        
        .empty-state h3 {
            color: #4a5568;
            margin-bottom: 10px;
        }
        
        .empty-state p {
            color: #718096;
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
        
        /* 响应式 */
        @media (max-width: 992px) {
            .stats-row {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 576px) {
            .stats-row {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 0 15px;
            }
            
            .feedback-header {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <?php $active_page = 'index'; include __DIR__ . '/components/navbar.php'; ?>
    
    <div class="container">
        <!-- 统计卡片 -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon total">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $totalCount; ?></h3>
                    <p>总反馈数</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon bug">
                    <i class="fas fa-bug"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $bugCount; ?></h3>
                    <p>Bug反馈</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon feature">
                    <i class="fas fa-star"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $featureCount; ?></h3>
                    <p>功能建议</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon performance">
                    <i class="fas fa-tachometer-alt"></i>
                </div>
                <div class="stat-info">
                    <h3><?php echo $performanceCount; ?></h3>
                    <p>性能问题</p>
                </div>
            </div>
        </div>
        
        <!-- 筛选栏 -->
        <div class="filter-bar">
            <label for="filterType"><strong>类型筛选：</strong></label>
            <select id="filterType" class="filter-select">
                <option value="all">全部类型</option>
                <option value="bug">Bug</option>
                <option value="suggestion">建议</option>
                <option value="question">问题</option>
                <option value="performance">性能</option>
                <option value="other">其他</option>
            </select>
            <span style="color: #666; margin-left: auto;">
                <i class="fas fa-info-circle"></i> 点击右侧按钮可删除反馈
            </span>
        </div>
        
        <!-- 反馈列表 -->
        <?php if (empty($feedbacks)): ?>
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>暂无反馈</h3>
                <p>还没有用户提交反馈</p>
            </div>
        <?php else: ?>
            <div class="feedback-list" id="feedbackList">
                <?php foreach ($feedbacks as $feedback): ?>
                    <?php
                    $type = $feedback['feedback_type'] ?? 'other';
                    $typeLabels = ['bug' => 'Bug', 'suggestion' => '建议', 'feature' => '建议', 'question' => '问题', 'performance' => '性能', 'other' => '其他'];
                    $typeLabel = $typeLabels[$type] ?? '其他';
                    $files = [];
                    if (!empty($feedback['attachments'])) {
                        $decoded = json_decode($feedback['attachments'], true);
                        if (is_array($decoded)) $files = $decoded;
                    }
                    ?>
                    <div class="feedback-card <?php echo htmlspecialchars($type); ?>" data-type="<?php echo htmlspecialchars($type); ?>" data-id="<?php echo htmlspecialchars($feedback['id']); ?>">
                        <div class="feedback-header">
                            <div class="feedback-title-wrap">
                                <span class="feedback-badge <?php echo htmlspecialchars($type); ?>">
                                    <?php echo $typeLabel; ?>
                                </span>
                                <h2 class="feedback-title"><?php echo htmlspecialchars($feedback['title'] ?: '(无标题)'); ?></h2>
                                <div class="feedback-meta">
                                    <span><i class="fas fa-clock"></i> <?php echo htmlspecialchars($feedback['created_at']); ?></span>
                                    <?php if (!empty($feedback['contact'])): ?>
                                        <span><i class="fas fa-envelope"></i> <?php echo htmlspecialchars($feedback['contact']); ?></span>
                                    <?php endif; ?>
                                    <?php if (!empty($feedback['version'])): ?>
                                        <span><i class="fas fa-code-branch"></i> v<?php echo htmlspecialchars($feedback['version']); ?></span>
                                    <?php endif; ?>
                                    <?php if (!empty($feedback['platform'])): ?>
                                        <span><i class="fas fa-desktop"></i> <?php echo htmlspecialchars($feedback['platform']); ?></span>
                                    <?php endif; ?>
                                    <span><i class="fas fa-circle" style="color:<?php echo $feedback['status']==='pending'?'#e8a200':'#2d8c2d'; ?>"></i> <?php echo htmlspecialchars($feedback['status'] ?: 'pending'); ?></span>
                                </div>
                            </div>
                            <button class="delete-btn" onclick="deleteFeedback('<?php echo htmlspecialchars($feedback['id']); ?>')" title="删除">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        
                        <div class="feedback-content"><?php echo htmlspecialchars($feedback['content'] ?: '(无内容)'); ?></div>
                        
                        <?php if (!empty($files)): ?>
                            <div class="feedback-images">
                                <?php foreach ($files as $file): ?>
                                    <div class="feedback-image" onclick="showImageModal('../<?php echo htmlspecialchars($file); ?>')">
                                        <img src="../<?php echo htmlspecialchars($file); ?>" alt="反馈图片">
                                    </div>
                                <?php endforeach; ?>
                            </div>
                        <?php endif; ?>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </div>
    
    <!-- 图片模态框 -->
    <div class="image-modal" id="imageModal" onclick="closeImageModal()">
        <span class="close-btn" onclick="closeImageModal()">&times;</span>
        <img src="" id="modalImage" alt="大图预览">
    </div>
    
    <script>
        // 筛选功能
        document.getElementById('filterType').addEventListener('change', function() {
            const filter = this.value;
            const cards = document.querySelectorAll('.feedback-card');
            
            cards.forEach(card => {
                if (filter === 'all' || card.dataset.type === filter) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
        
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
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeImageModal();
            }
        });
        
        // 删除反馈
        function deleteFeedback(id) {
            if (!confirm('确定要删除这条反馈吗？删除后无法恢复！')) {
                return;
            }
            
            const formData = new FormData();
            formData.append('action', 'delete');
            formData.append('id', id);
            
            fetch('index.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const card = document.querySelector(`.feedback-card[data-id="${id}"]`);
                    if (card) {
                        card.style.opacity = '0';
                        card.style.transition = 'opacity 0.3s';
                        setTimeout(() => card.remove(), 300);
                    }
                    setTimeout(() => location.reload(), 350);
                } else {
                    alert('删除失败，请稍后重试');
                }
            })
            .catch(error => {
                console.error('删除错误:', error);
                alert('删除失败，请稍后重试');
            });
        }
    </script>
</body>
</html>
