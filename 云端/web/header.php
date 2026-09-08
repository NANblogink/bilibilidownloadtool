<?php
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $title ?? 'B站视频下载 - 免费在线B站视频解析下载工具'; ?></title>
    <meta name="description" content="<?php echo $description ?? '免费B站视频下载工具，支持在线解析B站视频、UP主主页、收藏夹，提供4K/1080P多清晰度选择，浏览器直接合成下载，完全免费'; ?>">
    <meta name="keywords" content="<?php echo $keywords ?? 'B站视频下载, B站视频解析, B站下载, B站在线解析, Bilibili视频下载, b站视频怎么下载, b站在线解析下载'; ?>">
    <meta name="robots" content="index, follow">
    <meta name="author" content="寒烟似雪">
    <meta name="theme-color" content="#00a1d6">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta http-equiv="Content-Language" content="zh-CN">
    <meta name="referrer" content="strict-origin-when-cross-origin">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-XSS-Protection" content="1; mode=block">
    <meta http-equiv="Strict-Transport-Security" content="max-age=31536000; includeSubDomains">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://pagead2.googlesyndication.com https://cdn.ampproject.org https://cdn.jsdelivr.net https://cdn.bootcdn.net https://ep2.adtrafficquality.google https://hm.baidu.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.bootcdn.net https://fonts.googleapis.com; img-src 'self' data: https:; media-src 'self' https://*.bilivideo.com https://*.bilivideo.cn https://*.hdslb.com blob:; font-src 'self' https://cdn.bootcdn.net https://fonts.googleapis.com https://fonts.gstatic.com; connect-src *; frame-src https://www.youtube.com https://player.bilibili.com https://googleads.g.doubleclick.net https://ep2.adtrafficquality.google https://www.google.com;">
    <meta property="og:title" content="<?php echo $title ?? 'B站视频下载 - 免费在线B站视频解析下载工具'; ?>">
    <meta property="og:description" content="<?php echo $description ?? '免费B站视频下载工具，支持在线解析B站视频、UP主主页、收藏夹，提供4K/1080P多清晰度选择，浏览器直接合成下载，完全免费'; ?>">
    <meta property="og:url" content="<?php echo $canonical ?? 'https://www.bilidown.cn/'; ?>">
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://www.bilidown.cn/logo.png">
    <meta property="og:site_name" content="bilidown - B站视频解析下载工具">
    <meta property="og:locale" content="zh_CN">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?php echo $title ?? 'B站视频下载 - 免费在线B站视频解析下载工具'; ?>">
    <meta name="twitter:description" content="<?php echo $description ?? '免费B站视频下载工具，支持在线解析B站视频、UP主主页、收藏夹，提供4K/1080P多清晰度选择，浏览器直接合成下载，完全免费'; ?>">
    <meta name="twitter:image" content="https://www.bilidown.cn/logo.png">
    <link rel="canonical" href="<?php echo $canonical ?? '/'; ?>">
    <link rel="apple-touch-icon" href="favicon.ico">
    <link rel="icon" href="favicon.ico" type="image/x-icon">
    <link rel="sitemap" type="application/xml" title="Sitemap" href="sitemap.xml">

    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "B站视频解析下载工具",
        "alternateName": "bilidown",
        "url": "https://www.bilidown.cn/",
        "description": "免费B站视频下载工具，支持在线解析B站视频、UP主主页、收藏夹，提供4K/1080P多清晰度选择，浏览器直接合成下载，完全免费",
        "applicationCategory": "MultimediaApplication",
        "operatingSystem": "Web Browser",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "CNY"
        },
        "author": {
            "@type": "Person",
            "name": "寒烟似雪"
        },
        "inLanguage": "zh-CN",
        "isAccessibleForFree": true,
        "browserRequirements": "Requires JavaScript. Requires HTML5."
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "B站视频下载需要登录账号吗？",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "登录B站账号可以下载会员视频、收藏夹中的视频，以及获取UP主的完整视频列表。如果只下载公开视频，可以不登录。"
                }
            },
            {
                "@type": "Question",
                "name": "B站视频下载速度慢怎么办？",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "下载速度取决于您的网络环境和B站服务器的响应速度。建议在网络环境良好的情况下使用，避免高峰期下载。"
                }
            },
            {
                "@type": "Question",
                "name": "B站下载的视频文件大小有限制吗？",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "由于是在浏览器中合成视频，建议下载1GB以下的视频。较大的视频可能会导致浏览器内存不足或合成失败。"
                }
            },
            {
                "@type": "Question",
                "name": "B站视频解析失败怎么办？",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "解析失败可能是因为：1. 链接格式不正确；2. 视频已被删除或设置为私有；3. 需要登录但未登录；4. B站API限流。建议检查链接格式，登录账号后重试。"
                }
            },
            {
                "@type": "Question",
                "name": "下载B站视频有版权问题吗？",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "本工具仅用于个人学习和研究目的，请勿用于商业用途或侵犯他人版权。下载的视频请在24小时内删除，支持原创内容。"
                }
            }
        ]
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "B站视频解析下载工具",
        "applicationCategory": "MultimediaApplication",
        "operatingSystem": "Windows",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "CNY"
        }
    }
    </script>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Noto+Sans+SC:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">

    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Outfit", "Noto Sans SC", "Microsoft YaHei", -apple-system, sans-serif; background: #1a1f2e; color: #f0f4f8; line-height: 1.6; }
        .navbar { background: rgba(26, 31, 46, 0.85); backdrop-filter: blur(20px) saturate(180%); -webkit-backdrop-filter: blur(20px) saturate(180%); border-bottom: 1px solid rgba(255, 255, 255, 0.08); color: white; }
        .navbar-brand { color: white; font-weight: 700; font-size: 1.25rem; }
        .nav-link { color: rgba(255,255,255,0.65); position: relative; }
        .nav-link::after { content: ''; position: absolute; bottom: 0; left: 50%; width: 0; height: 2px; background: linear-gradient(90deg, #00a1d6, #ff85c0); transform: translateX(-50%); border-radius: 1px; }
        .nav-link:hover, .nav-link.active { color: white; }
        .nav-link:hover::after, .nav-link.active::after { width: 80%; }
        .dropdown-menu { background: rgba(30, 35, 54, 0.95) !important; backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 6px; position: absolute; top: calc(100% + 8px); left: 50%; transform: translateX(-50%); z-index: 1000; display: none; min-width: 12rem; padding: 8px; margin: 0; font-size: 1rem; color: var(--text-color); text-align: left; list-style: none; background-clip: padding-box; box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 30px rgba(0, 161, 214, 0.1); }
        .dropdown-menu.show { display: block; }
        .dropdown-item { display: block; width: 100%; padding: 10px 16px; clear: both; font-weight: 400; color: rgba(255,255,255,0.8) !important; text-align: inherit; text-decoration: none; white-space: nowrap; background: none; border: 0; border-radius: 4px; font-size: 0.9rem; }
        .dropdown-item:hover, .dropdown-item.active { background: rgba(0, 161, 214, 0.15) !important; color: #00a1d6 !important; }
        .hero-section { background: linear-gradient(135deg, #1a1f2e 0%, #1e2d4a 50%, #1a1f2e 100%); color: white; padding: 80px 0; text-align: center; position: relative; overflow: hidden; }
        .hero-section::before { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(ellipse at 30% 50%, rgba(0, 161, 214, 0.08) 0%, transparent 50%), radial-gradient(ellipse at 70% 50%, rgba(255, 133, 192, 0.06) 0%, transparent 50%); }
        .hero-section h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 20px; position: relative; }
        .hero-section p { font-size: 1.25rem; margin-bottom: 30px; position: relative; }
        .hero-section .btn { background: linear-gradient(135deg, #00a1d6, #0086b3); color: white; border: none; padding: 14px 36px; font-size: 1.1rem; font-weight: 600; border-radius: 6px; box-shadow: 0 4px 20px rgba(0, 161, 214, 0.3); position: relative; }
        .hero-section .btn:hover { box-shadow: 0 6px 25px rgba(0, 161, 214, 0.4); }
        .main-content { padding: 60px 0; }
        .card { background: rgba(30, 35, 54, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); backdrop-filter: blur(10px); }
        .card-body { padding: 25px; }
        @media (max-width: 768px) {
            .hero-section { padding: 60px 0; }
            .hero-section h1 { font-size: 2rem; }
            .main-content { padding: 40px 0; }
        }
    </style>

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" media="print" onload="this.media='all'">
    <link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/font-awesome/6.4.0/css/all.min.css" media="print" onload="this.media='all'">

    <style>
        :root {
            --primary: #00a1d6;
            --primary-dark: #0086b3;
            --primary-glow: rgba(0, 161, 214, 0.3);
            --secondary: #ff85c0;
            --secondary-glow: rgba(255, 133, 192, 0.3);
            --dark: #1a1f2e;
            --dark-surface: #1e2336;
            --dark-elevated: #262d42;
            --light: #f7fafc;
            --gray: #9ca8bd;
            --muted: #a8b3c5;
            --success: #00d68f;
            --warning: #ffaa00;
            --danger: #ff4757;
            --border: rgba(255, 255, 255, 0.1);
            --border-hover: rgba(0, 161, 214, 0.4);
            --card-bg: rgba(30, 35, 54, 0.7);
            --card-bg-solid: #1e2336;
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            --shadow-lg: 0 10px 40px rgba(0, 0, 0, 0.4);
            --text-color: #f0f4f8;
            --text-secondary: #b8c4d6;
            --bg-color: #1a1f2e;
            --bg-gradient: linear-gradient(180deg, #1a1f2e 0%, #1e2540 100%);
            --glass-bg: rgba(30, 35, 54, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --radius-sm: 4px;
            --radius-md: 6px;
            --radius-lg: 8px;
            --radius-xl: 12px;
        }

        [data-theme="light"] {
            --primary: #00a1d6;
            --primary-dark: #0086b3;
            --primary-glow: rgba(0, 161, 214, 0.2);
            --secondary: #ff85c0;
            --secondary-glow: rgba(255, 133, 192, 0.2);
            --dark: #1a202c;
            --dark-surface: #f0f4f8;
            --dark-elevated: #ffffff;
            --light: #f7fafc;
            --gray: #718096;
            --muted: #a0aec0;
            --success: #38a169;
            --warning: #dd6b20;
            --danger: #e53e3e;
            --border: rgba(0, 0, 0, 0.08);
            --border-hover: rgba(0, 161, 214, 0.3);
            --card-bg: rgba(255, 255, 255, 0.8);
            --card-bg-solid: #ffffff;
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 40px rgba(0, 0, 0, 0.08);
            --text-color: #1a202c;
            --text-secondary: #718096;
            --bg-color: #f0f4f8;
            --bg-gradient: linear-gradient(180deg, #f0f4f8 0%, #e2e8f0 100%);
            --glass-bg: rgba(255, 255, 255, 0.7);
            --glass-border: rgba(0, 0, 0, 0.06);
        }

        * {
            box-sizing: border-box;
        }

        body {
            background: var(--bg-gradient);
            font-family: "Outfit", "Noto Sans SC", "Microsoft YaHei", -apple-system, sans-serif;
            color: var(--text-color);
            line-height: 1.6;
            overflow-x: hidden;
            min-height: 100vh;
            padding-top: 80px;
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background:
                radial-gradient(ellipse at 20% 0%, rgba(0, 161, 214, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(255, 133, 192, 0.04) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }

        [data-theme="light"] body::before {
            background:
                radial-gradient(ellipse at 20% 0%, rgba(0, 161, 214, 0.05) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(255, 133, 192, 0.04) 0%, transparent 50%);
        }

        .container {
            max-width: 1200px;
            position: relative;
            z-index: 1;
        }

        .navbar {
            background: var(--glass-bg) !important;
            backdrop-filter: blur(24px) saturate(180%);
            -webkit-backdrop-filter: blur(24px) saturate(180%);
            border-bottom: 1px solid var(--glass-border);
            padding: 0.75rem 0;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15);
        }

        .navbar-collapse {
            background: transparent !important;
        }

        .navbar-brand {
            font-weight: 800;
            font-size: 1.25rem;
            color: var(--primary) !important;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            letter-spacing: -0.02em;
        }

        .navbar-brand i {
            font-size: 1.5rem;
        }

        .nav-link {
            font-weight: 500;
            color: var(--text-secondary) !important;
            padding: 0.5rem 1rem !important;
            border-radius: var(--radius-sm);
            position: relative;
        }

        .nav-link::after {
            content: '';
            position: absolute;
            bottom: 2px;
            left: 50%;
            width: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            transform: translateX(-50%);
            border-radius: 1px;
        }

        .nav-link:hover, .nav-link.active {
            color: var(--text-color) !important;
            background: rgba(0, 161, 214, 0.08);
        }

        .nav-link:hover::after, .nav-link.active::after {
            width: 60%;
        }

        @media (max-width: 991px) {
            .navbar-collapse {
                background: var(--card-bg-solid);
                border-top: 1px solid var(--border);
                margin-top: 0.5rem;
                padding: 1rem;
                border-radius: var(--radius-lg);
                box-shadow: var(--shadow-lg);
            }

            .navbar-nav {
                width: 100%;
            }

            .nav-item {
                width: 100%;
            }

            .nav-link {
                display: block;
                width: 100%;
                padding: 0.75rem 1rem !important;
            }

            .nav-link::after { display: none; }
        }

        [data-theme="light"] .navbar {
            background: rgba(255, 255, 255, 0.85) !important;
            border-bottom-color: rgba(0, 0, 0, 0.06);
        }

        [data-theme="light"] .nav-link {
            color: var(--gray) !important;
        }

        [data-theme="light"] .nav-link:hover,
        [data-theme="light"] .nav-link.active {
            color: var(--primary) !important;
            background: rgba(0, 161, 214, 0.06);
        }

        [data-theme="light"] .navbar-collapse {
            background: #ffffff;
            border-top-color: var(--border);
        }

        [data-theme="light"] .dropdown-menu {
            background: rgba(255, 255, 255, 0.98);
            border-color: rgba(0, 0, 0, 0.08);
            box-shadow: 0 20px 60px rgba(0,0,0,0.1), 0 0 30px rgba(0, 161, 214, 0.05);
        }

        [data-theme="light"] .dropdown-item {
            color: var(--text-color);
        }

        [data-theme="light"] .dropdown-item:hover,
        [data-theme="light"] .dropdown-item.active {
            background: rgba(0, 161, 214, 0.08);
            color: var(--primary);
        }

        #toolBar {
            position: fixed;
            right: 20px;
            bottom: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .tool-item {
            position: relative;
        }

        #toolBar button {
            width: 52px;
            height: 52px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            border: none;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 18px;
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        #toolBar button:hover {
            box-shadow: 0 6px 20px var(--primary-glow);
        }

        #toolBar button:active {
        }

        .tool-separator { display: none; }

        #rewardPopup {
            position: fixed;
            right: 82px;
            bottom: 20px;
            background: var(--card-bg-solid);
            color: var(--text-color);
            box-shadow: var(--shadow-lg);
            width: 200px;
            display: none;
            border: 1px solid var(--border);
            z-index: 9999;
            border-radius: var(--radius-lg);
            overflow: hidden;
            animation: popupIn 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }

        #rewardPopup .popup-header {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            padding: 12px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        #rewardPopup .popup-header span {
            font-weight: 600;
            font-size: 14px;
        }

        #rewardPopup .popup-content {
            padding: 12px;
        }

        #rewardPopup img {
            width: 100%;
            height: auto;
            display: block;
            border-radius: var(--radius-sm);
        }

        @media (max-width: 768px) {
            #toolBar {
                right: 12px;
                bottom: 12px;
                gap: 6px;
            }

            #toolBar button {
                width: 46px;
                height: 46px;
                font-size: 16px;
                border-radius: 6px;
            }

            #rewardPopup {
                right: 68px;
                bottom: 12px;
                width: 160px;
            }
        }

        .logo-img {
            filter: brightness(0) invert(1);
        }

        [data-theme="light"] .logo-img {
            filter: none;
        }

        .page-header {
            padding: 3rem 0 2rem;
            background: transparent;
            margin-bottom: 2rem;
            position: relative;
        }

        .page-header h1 {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--text-color);
            text-align: center;
            margin-bottom: 1rem;
            letter-spacing: -0.03em;
        }

        .page-header p {
            font-size: 1.1rem;
            color: var(--text-secondary);
            text-align: center;
            max-width: 600px;
            margin: 0 auto;
        }

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
        }

        [data-theme="light"] body {
            background: var(--bg-gradient);
            color: var(--text-color);
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

        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--dark-surface);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(0, 161, 214, 0.3);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 161, 214, 0.5);
        }

        [data-theme="light"] ::-webkit-scrollbar-track {
            background: #f0f4f8;
        }
        [data-theme="light"] ::-webkit-scrollbar-thumb {
            background: rgba(0, 161, 214, 0.2);
        }
        [data-theme="light"] ::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 161, 214, 0.4);
        }

        @keyframes fadeInUp {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes glowPulse {
            0%, 100% { box-shadow: 0 0 20px var(--primary-glow); }
            50% { box-shadow: 0 0 30px var(--primary-glow); }
        }
    </style>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>

    <script>
        var _hmt = _hmt || [];
        (function() {
            var hm = document.createElement("script");
            hm.src = "https://hm.baidu.com/hm.js?512f6e0987d6a9bdcba34bc2dcb3f0c2";
            var s = document.getElementsByTagName("script")[0];
            s.parentNode.insertBefore(hm, s);
        })();
    </script>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var dropdownElements = document.querySelectorAll('.dropdown-toggle');

            dropdownElements.forEach(function(element) {
                element.addEventListener('click', function(e) {
                    e.preventDefault();
                    var parent = this.closest('.nav-item');
                    var menu = parent.querySelector('.dropdown-menu');

                    document.querySelectorAll('.dropdown-menu').forEach(function(otherMenu) {
                        if (otherMenu !== menu) {
                            otherMenu.classList.remove('show');
                        }
                    });

                    if (menu) {
                        menu.classList.toggle('show');
                    }
                });
            });

            document.addEventListener('click', function(e) {
                if (!e.target.closest('.nav-item')) {
                    document.querySelectorAll('.dropdown-menu').forEach(function(dropdown) {
                        dropdown.classList.remove('show');
                    });
                }
            });

            var navbarToggler = document.getElementById('navbarToggler');
            var navbarCollapse = document.getElementById('navbarCollapse');

            if (navbarToggler && navbarCollapse) {
                navbarToggler.addEventListener('click', function() {
                    navbarCollapse.classList.toggle('show');
                });
            }
        });
    </script>
</head>
<body>
    <div id="toolBar">
        <div class="tool-item">
            <button id="rewardBtn">
                <i class="fas fa-wallet"></i>
            </button>
            <div id="rewardPopup">
                <div class="popup-header">
                    <span>赞助我</span>
                </div>
                <div class="popup-content">
                    <img src="code.jpg" alt="赏赞码">
                </div>
            </div>
        </div>

        <button id="themeToggle">
            <i class="fas fa-sun"></i>
        </button>

        <button id="backToTop" style="display: none;">
            <i class="fas fa-arrow-up"></i>
        </button>
    </div>

    <nav class="navbar navbar-expand-lg fixed-top">
        <div class="container">
            <a class="navbar-brand" href="/">
                <div class="logo-container">
                    <img src="logo.png" alt="bilidown - B站视频下载工具" style="height: 48px; position: relative; z-index: 1;" class="logo-img">
                    <div class="logo-shine"></div>
                </div>
            </a>
            <button class="navbar-toggler" type="button" id="navbarToggler">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarCollapse">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link <?php echo $activePage == 'home' ? 'active' : ''; ?>" href="/">B站下载</a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="featuresDropdown">功能</a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/#features">功能介绍</a></li>
                            <li><a class="dropdown-item" href="/#tutorial">下载教程</a></li>
                            <li><a class="dropdown-item" href="/#faq">常见问题</a></li>
                            <li><a class="dropdown-item" href="/#desktop">桌面版下载</a></li>
                        </ul>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="supportDropdown">支持</a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/#about">关于我们</a></li>
                            <li><a class="dropdown-item <?php echo $activePage == 'articles' ? 'active' : ''; ?>" href="articles.php">使用指南</a></li>
                            <li><a class="dropdown-item <?php echo $activePage == 'feedback' ? 'active' : ''; ?>" href="feedback.php">问题反馈</a></li>
                        </ul>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="legalDropdown">法律</a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item <?php echo $activePage == 'privacy' ? 'active' : ''; ?>" href="privacy.php">隐私政策</a></li>
                            <li><a class="dropdown-item <?php echo $activePage == 'terms' ? 'active' : ''; ?>" href="terms.php">服务条款</a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
