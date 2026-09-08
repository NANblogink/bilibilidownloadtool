<?php
// 后台认证逻辑

// 设置session保存路径到项目本地目录，避免依赖服务器默认路径
$sessionPath = __DIR__ . '/../../data/sessions';
if (!is_dir($sessionPath)) {
    @mkdir($sessionPath, 0755, true);
}
session_save_path($sessionPath);
ini_set('session.gc_probability', 1);
ini_set('session.gc_divisor', 1000);
ini_set('session.gc_maxlifetime', 86400);

session_start();

require_once __DIR__ . '/../../data/admin_config.php';
$config = $GLOBALS['admin_config'];

// 检查是否已登录
function is_admin_logged_in() {
    return isset($_SESSION['admin_logged_in']) && $_SESSION['admin_logged_in'] === true;
}

// 登录
function admin_login($username, $password) {
    global $config;
    
    // 密码验证
    $storedUsername = $config['admin_username'];
    $storedPassword = $config['admin_password'];
    
    if ($username === $storedUsername && $password === $storedPassword) {
        $_SESSION['admin_logged_in'] = true;
        $_SESSION['admin_login_time'] = time();
        return true;
    }
    return false;
}

// 登出
function admin_logout() {
    session_unset();
    session_destroy();
}

// 检查会话是否过期
function check_session_expire() {
    global $config;
    if (isset($_SESSION['admin_login_time']) && (time() - $_SESSION['admin_login_time']) > $config['session_expire']) {
        admin_logout();
        return true;
    }
    return false;
}

// 认证检查，如果未登录则跳转到登录页
function require_admin_login() {
    if (!is_admin_logged_in()) {
        header('Location: login.php');
        exit;
    }
    if (check_session_expire()) {
        header('Location: login.php?expired=1');
        exit;
    }
}
