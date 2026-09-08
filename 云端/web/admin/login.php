<?php
// 登录页面
require_once 'auth.php';

// 如果已登录，跳转到管理页面
if (is_admin_logged_in()) {
    header('Location: index.php');
    exit;
}

$error = '';

// 处理登录请求
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    
    if (admin_login($username, $password)) {
        header('Location: index.php');
        exit;
    } else {
        $error = '用户名或密码错误';
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>后台登录 - B站视频解析下载工具</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #00a1d6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .login-box {
            background: white;
            padding: 40px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            width: 100%;
            max-width: 400px;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-header h1 {
            font-size: 24px;
            color: #333;
            margin-bottom: 10px;
        }
        
        .login-header p {
            color: #666;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-label {
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            display: block;
        }
        
        .form-control {
            border: 2px solid #e0e0e0;
            padding: 12px 15px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        .form-control:focus {
            border-color: #00a1d6;
            box-shadow: none;
        }
        
        .btn-login {
            background: #00a1d6;
            border: none;
            color: white;
            padding: 12px;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            transition: background-color 0.3s;
        }
        
        .btn-login:hover {
            background: #0086b3;
        }
        
        .error-message {
            background: #fff5f5;
            border: 1px solid #fc8181;
            color: #c53030;
            padding: 12px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .expired-message {
            background: #fffaf0;
            border: 1px solid #fbd38d;
            color: #c05621;
            padding: 12px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .success-message {
            background: #f0fff4;
            border: 1px solid #68d391;
            color: #276749;
            padding: 12px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .back-link {
            text-align: center;
            margin-top: 20px;
        }
        
        .back-link a {
            color: #00a1d6;
            text-decoration: none;
        }
        
        .back-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <div class="login-header">
            <h1><i class="fas fa-lock"></i> 后台管理</h1>
            <p>B站视频解析下载工具</p>
        </div>
        
        <?php if (isset($_GET['expired'])): ?>
            <div class="expired-message">
                <i class="fas fa-clock"></i> 会话已过期，请重新登录
            </div>
        <?php endif; ?>
        
        <?php if (isset($_GET['logged_out'])): ?>
            <div class="success-message">
                <i class="fas fa-check-circle"></i> 已安全退出登录
            </div>
        <?php endif; ?>
        
        <?php if ($error): ?>
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> <?php echo htmlspecialchars($error); ?>
            </div>
        <?php endif; ?>
        
        <form method="POST">
            <div class="form-group">
                <label for="username" class="form-label">用户名</label>
                <input type="text" class="form-control" id="username" name="username" placeholder="请输入用户名" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password" class="form-label">密码</label>
                <input type="password" class="form-control" id="password" name="password" placeholder="请输入密码" required>
            </div>
            
            <button type="submit" class="btn-login">
                <i class="fas fa-sign-in-alt"></i> 登录
            </button>
        </form>
        
        <div class="back-link">
            <a href="../index.php"><i class="fas fa-arrow-left"></i> 返回首页</a>
        </div>
    </div>
</body>
</html>
