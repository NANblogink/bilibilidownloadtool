<?php
// 登出页面
require_once 'auth.php';

admin_logout();

header('Location: login.php?logged_out=1');
exit;
