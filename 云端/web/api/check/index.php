<?php
/**
 * 旧版兼容路由
 *
 * 旧版安装器(2.0.7及以前)请求的是 /api/check?type=installer&version=x.x.x
 * 新版请求的是 /api/v1/check?type=installer&version=x.x.x
 *
 * 此文件将 /api/check 请求转发到 /api/v1/check，保证旧版客户端兼容
 */
include __DIR__ . '/../v1/check/index.php';
