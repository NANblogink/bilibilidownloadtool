<?php
// 后台管理系统配置

// API Token（用于API认证）
if (!defined('API_TOKEN')) {
    define('API_TOKEN', 'bilidown_api_token_2026_secure_key_x9k2m3n4p5q6');
}

// 加密函数
if (!function_exists('encrypt')) {
    function encrypt($data) {
        $key = 'bilibili_downloader_key_2024';
        $iv = 'bilibili_iv_123456';
        $encrypted = openssl_encrypt($data, 'AES-256-CBC', $key, 0, $iv);
        return base64_encode($encrypted);
    }
}

// 解密函数
if (!function_exists('decrypt')) {
    function decrypt($data) {
        $key = 'bilibili_downloader_key_2024';
        $iv = 'bilibili_iv_123456';
        $encrypted = base64_decode($data);
        $decrypted = openssl_decrypt($encrypted, 'AES-256-CBC', $key, 0, $iv);
        return $decrypted;
    }
}

// 配置数据（用于后台登录验证）
$GLOBALS['admin_config'] = [
    'admin_username' => 'diligozh',
    'admin_password' => 'diligomm',
    'session_expire' => 3600 * 24
];
