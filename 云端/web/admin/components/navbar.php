<?php
/**
 * 后台公共布局组件（侧边栏 + 顶部导航栏）
 *
 * 用法：在页面 <body> 标签之后设置 $active_page 并 include 此文件
 *   <?php $active_page = 'stats'; include __DIR__ . '/components/navbar.php'; ?>
 *
 * 可选变量：
 *   $active_page  当前菜单高亮 key（对应 $nav_items 的 key）
 *   $page_title  顶部栏显示的页面标题（默认取菜单文字）
 *   $brand_text  自定义品牌文字（默认"后台管理"）
 *   $brand_icon  自定义品牌图标（默认 fas fa-cog）
 */
if (!defined('ADMIN_NAVBAR_LOADED')) {
    define('ADMIN_NAVBAR_LOADED', true);
}

$active     = $active_page ?? '';
$brand      = $brand_text ?? '后台管理';
$brand_icon = $brand_icon ?? 'fas fa-cog';

// 统一菜单项（顺序、链接、图标、文字全站一致）
$nav_items = [
    ['key' => 'index',         'url' => 'index.php',         'icon' => 'fas fa-comments',     'text' => '反馈管理'],
    ['key' => 'versions',      'url' => 'versions.php',      'icon' => 'fas fa-code-branch',  'text' => '版本管理'],
    ['key' => 'beta_auth',     'url' => 'beta_auth.php',     'icon' => 'fas fa-vial',         'text' => '内测授权'],
    ['key' => 'announcements', 'url' => 'announcements.php', 'icon' => 'fas fa-bullhorn',     'text' => '公告管理'],
    ['key' => 'stats',         'url' => 'stats_v2.php',      'icon' => 'fas fa-chart-line',   'text' => '数据统计'],
    ['key' => 'file_manage',   'url' => 'file_manage.php',   'icon' => 'fas fa-file-code',    'text' => '文件管理'],
    ['key' => 'patches',       'url' => 'patches.php',       'icon' => 'fas fa-puzzle-piece', 'text' => '增量包'],
    ['key' => 'ops',           'url' => 'ops.php',           'icon' => 'fas fa-cogs',         'text' => '运维中心'],
    ['key' => 'sync',          'url' => 'sync.php',          'icon' => 'fas fa-exchange-alt', 'text' => '数据同步'],
    ['key' => 'pull',          'url' => 'pull.php',          'icon' => 'fas fa-truck-ramp-box', 'text' => '远程日志'],
];

// 顶部栏页面标题：优先用显式传入，否则取当前菜单的文字
$current_title = $page_title ?? '';
if ($current_title === '') {
    foreach ($nav_items as $item) {
        if ($item['key'] === $active) {
            $current_title = $item['text'];
            break;
        }
    }
}

// 当前管理员用户名（从已加载的配置读取）
$current_admin = '';
if (isset($GLOBALS['admin_config']['admin_username'])) {
    $current_admin = $GLOBALS['admin_config']['admin_username'];
}
?>
<style>
/* ===== 后台布局：固定侧边栏 + 顶部导航栏 ===== */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background: #f5f7fa;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    /* 为固定侧边栏 + 顶部导航预留空间 */
    padding-left: 230px;
    padding-top: 58px;
}

/* —— 左侧固定侧边栏 —— */
.admin-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 230px;
    background: #15202b;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
}
.admin-sidebar .side-brand {
    height: 58px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    color: #fff;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    text-decoration: none;
}
.admin-sidebar .side-brand i { color: #00a1d6; font-size: 18px; }
.side-nav { flex: 1; padding: 10px 0; }
.side-nav .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 20px;
    color: #a8b6c7;
    text-decoration: none;
    font-size: 14px;
    border-left: 3px solid transparent;
    transition: background 0.15s, color 0.15s;
}
.side-nav .nav-item i { width: 18px; text-align: center; font-size: 14px; }
.side-nav .nav-item:hover { background: rgba(255,255,255,0.05); color: #fff; }
.side-nav .nav-item.active {
    background: #00a1d6;
    color: #fff;
    border-left-color: #fff;
    font-weight: 600;
}
.side-extra { padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.08); }
.side-extra .extra-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 20px;
    color: #a8b6c7;
    text-decoration: none;
    font-size: 14px;
    border-left: 3px solid transparent;
}
.side-extra .extra-item i { width: 18px; text-align: center; }
.side-extra .extra-item:hover { background: rgba(255,255,255,0.05); color: #fff; }

/* —— 顶部导航栏 —— */
.admin-topbar {
    position: fixed;
    top: 0;
    left: 230px;
    right: 0;
    height: 58px;
    background: #fff;
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border-bottom: 1px solid #edf0f4;
}
.admin-topbar .topbar-left { display: flex; align-items: center; gap: 14px; }
.admin-topbar .topbar-burger { display: none; cursor: pointer; color: #333; font-size: 20px; }
.admin-topbar .topbar-title { font-size: 16px; font-weight: 600; color: #1f2933; }
.admin-topbar .topbar-user { display: flex; align-items: center; gap: 18px; }
.admin-topbar .topbar-user .user-badge {
    display: flex; align-items: center; gap: 8px;
    background: #f0f4f8; padding: 6px 14px; color: #334e68;
    font-size: 13px;
}
.admin-topbar .topbar-user .user-badge i { color: #00a1d6; }
.admin-topbar .topbar-home {
    color: #52606d; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;
}
.admin-topbar .topbar-home:hover { color: #00a1d6; }
.admin-topbar .topbar-logout {
    color: #e53e3e; text-decoration: none; font-size: 13px; display: flex; align-items: center; gap: 6px;
}
.admin-topbar .topbar-logout:hover { text-decoration: underline; }

/* —— 侧边栏遮罩（移动端展开时） —— */
.side-mask { display: none; }

/* —— 响应式：窄屏收起侧边栏 —— */
@media (max-width: 992px) {
    body { padding-left: 0; }
    .admin-topbar { left: 0; }
    .admin-topbar .topbar-burger { display: inline-block; }
    .admin-sidebar { transform: translateX(-100%); transition: transform 0.2s ease; }
    body.side-open .admin-sidebar { transform: translateX(0); }
    body.side-open .side-mask {
        display: block;
        position: fixed; inset: 0;
        background: rgba(0,0,0,0.4);
        z-index: 998;
    }
}
</style>
<!-- 侧边栏遮罩 -->
<div class="side-mask" onclick="document.body.classList.remove('side-open')"></div>

<!-- 左侧固定侧边栏 -->
<aside class="admin-sidebar">
    <a href="index.php" class="side-brand">
        <i class="<?php echo htmlspecialchars($brand_icon); ?>"></i>
        <span><?php echo htmlspecialchars($brand); ?></span>
    </a>
    <nav class="side-nav">
        <?php foreach ($nav_items as $item): ?>
            <a href="<?php echo $item['url']; ?>" class="nav-item<?php echo $active === $item['key'] ? ' active' : ''; ?>">
                <i class="<?php echo $item['icon']; ?>"></i>
                <span><?php echo $item['text']; ?></span>
            </a>
        <?php endforeach; ?>
    </nav>
    <div class="side-extra">
        <a href="../index.php" class="extra-item"><i class="fas fa-home"></i><span>返回首页</span></a>
        <a href="logout.php" class="extra-item" style="color:#e8828d;"><i class="fas fa-sign-out-alt"></i><span>退出登录</span></a>
    </div>
</aside>

<!-- 顶部导航栏 -->
<header class="admin-topbar">
    <div class="topbar-left">
        <span class="topbar-burger" onclick="document.body.classList.toggle('side-open')">
            <i class="fas fa-bars"></i>
        </span>
        <span class="topbar-title"><?php echo htmlspecialchars($current_title); ?></span>
    </div>
    <div class="topbar-user">
        <span class="user-badge"><i class="fas fa-user-shield"></i><?php echo htmlspecialchars($current_admin !== '' ? $current_admin : '管理员'); ?></span>
        <a href="../index.php" class="topbar-home"><i class="fas fa-home"></i>返回首页</a>
        <a href="logout.php" class="topbar-logout"><i class="fas fa-sign-out-alt"></i>退出登录</a>
    </div>
</header>