<?php
require_once 'auth.php';
require_admin_login();

$file = $_GET['file'] ?? '';
if ($file === '') {
    http_response_code(400);
    echo '缺少文件参数';
    exit;
}

// 日志文件统一存于 uploads/errorlogs/ 下；仅允许读取该目录内的文件，杜绝路径穿越
$dir = realpath(__DIR__ . '/../../uploads/errorlogs');
$target = $dir !== false ? realpath($dir . DIRECTORY_SEPARATOR . basename($file)) : false;

if (!$dir || !$target || strpos($target, $dir . DIRECTORY_SEPARATOR) !== 0 || !is_file($target)) {
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