<?php
require_once 'auth.php';
require_admin_login();

// 参数：path = 相对 file_path，形如 uploads/pulled_logs/<client>/<fname>
$rel = $_GET['path'] ?? '';
if ($rel === '') {
    http_response_code(400);
    echo '缺少文件参数';
    exit;
}

// 目录限定：仅允许 uploads/pulled_logs/ 下的文件，杜绝路径穿越
$allowedRoot = realpath(__DIR__ . '/../../uploads/pulled_logs');
$normalized = str_replace('\\', '/', $rel);
// 剥离到相对 pulled_logs 的段
if (preg_match('#(?:^|/)uploads/pulled_logs/(.+)$#', $normalized, $m)) {
    $sub = $m[1];
} else {
    $sub = ltrim($rel, '/');
}
$sub = str_replace('\\', '/', $sub);

$target = $allowedRoot !== false ? realpath($allowedRoot . DIRECTORY_SEPARATOR . $sub) : false;

if (!$allowedRoot || !$target || strpos($target, $allowedRoot . DIRECTORY_SEPARATOR) !== 0 || !is_file($target)) {
    http_response_code(404);
    echo '日志文件不存在或已被删除';
    exit;
}

$content = @file_get_contents($target);
if ($content === false) {
    http_response_code(500);
    echo '读取文件失败';
    exit;
}

header('Content-Type: text/plain; charset=utf-8');
header('Content-Disposition: inline; filename="' . basename($target) . '"');
header('X-Content-Type-Options: nosniff');
echo $content;