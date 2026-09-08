<?php

$title = 'B站视频下载 - 免费在线B站视频解析下载工具 | bilidown';
$description = '免费B站视频下载工具，支持在线解析B站视频、UP主主页、收藏夹。提供4K/1080P多清晰度选择，浏览器直接合成下载，无需安装软件。支持BV号解析、番剧下载、批量下载，完全免费。';
$keywords = 'B站视频下载, B站视频解析, B站下载, B站在线解析, Bilibili视频下载, B站视频解析下载, b站视频怎么下载, b站在线解析下载, b站视频解析工具, UP主主页解析, 收藏夹解析, B站4K下载';
$canonical = 'https://www.bilidown.cn/';
$activePage = 'home';

require_once 'header.php';
?>
    

    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "B站视频解析下载工具",
      "url": ".",
      "description": "专业的B站视频解析下载工具，支持解析BV号、UP主主页、收藏夹，提供多清晰度选择和浏览器合成下载功能，完全免费",
      "potentialAction": {
        "@type": "SearchAction",
        "target": ".?url={search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
    </script>
    
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "B站视频解析下载工具",
      "applicationCategory": "Utilities",
      "operatingSystem": "Web",
      "description": "专业的B站视频解析下载工具，支持解析BV号、UP主主页、收藏夹，提供多清晰度选择和浏览器合成下载功能，完全免费",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "CNY",
        "availability": "https://schema.org/InStock"
      },
      "featureList": [
        "支持解析BV号视频",
        "支持解析UP主主页",
        "支持解析收藏夹",
        "多清晰度选择",
        "浏览器合成下载",
        "完全免费"
      ],
      "url": ".",
      "image": "favicon.ico",
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.8",
        "reviewCount": "1000"
      }
    }
    </script>
    
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "寒烟似雪",
      "url": ".",
      "logo": "favicon.ico",
      "contactPoint": [
        {
          "@type": "ContactPoint",
          "telephone": "2273962061",
          "contactType": "customer service",
          "email": "2273962061@qq.com"
        }
      ],
      "sameAs": [
        "https://github.com/NANblogink/bilibilidownloadtool",
        "https://space.bilibili.com/3546841002019157"
      ]
    }
    </script>
    
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "首页",
          "item": "."
        }
      ]
    }
    </script>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    

    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9568438449258885" crossorigin="anonymous"></script>
    

    <script async custom-element="amp-auto-ads" src="https://cdn.ampproject.org/v0/amp-auto-ads-0.1.js"></script>
    
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

        .container {
            max-width: 1200px;
        }

        .navbar {
            background: var(--glass-bg) !important;
            backdrop-filter: blur(24px) saturate(180%);
            -webkit-backdrop-filter: blur(24px) saturate(180%);
            border-bottom: 1px solid var(--glass-border);
            padding: 0.75rem 0;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15);
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

        .hero {
            background: linear-gradient(135deg, #1a1f2e 0%, #1e2d4a 40%, #2a1e30 70%, #1a1f2e 100%);
            padding: 5rem 0;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }

        .hero::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background:
                radial-gradient(ellipse at 25% 50%, rgba(0, 161, 214, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 75% 50%, rgba(255, 133, 192, 0.07) 0%, transparent 50%);
            pointer-events: none;
        }

        .hero::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%2300a1d6' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            pointer-events: none;
        }

        @keyframes heroFloat {
            0%, 100% { transform: translate(0, 0); }
        }

        .hero h1 {
            font-size: 2.5rem;
            font-weight: 900;
            color: white;
            text-align: center;
            margin-bottom: 1.5rem;
            line-height: 1.1;
            position: relative;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, #ffffff 0%, #00a1d6 50%, #ff85c0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .hero p {
            font-size: 1.1rem;
            color: rgba(255,255,255,0.6);
            text-align: center;
            margin-bottom: 2.5rem;
            max-width: 90%;
            margin-left: auto;
            margin-right: auto;
            position: relative;
        }

        .hero .btn {
            font-size: 1rem;
            padding: 1rem 2.5rem;
            font-weight: 600;
            border-radius: var(--radius-md);
            position: relative;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            color: white;
            box-shadow: 0 4px 20px var(--primary-glow);
        }

        .hero .btn:hover {
            box-shadow: 0 6px 25px var(--primary-glow);
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

            .hero {
                padding: 7rem 0;
                margin-bottom: 4rem;
            }

            .hero h1 {
                font-size: 3.5rem;
                margin-bottom: 2rem;
            }

            .hero p {
                font-size: 1.35rem;
                margin-bottom: 3rem;
                max-width: 800px;
            }

            .hero .btn {
                font-size: 1.15rem;
                padding: 1.15rem 3rem;
            }
        }

        .hero-form {
            background: var(--glass-bg) !important;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            color: var(--text-color) !important;
            padding: 2rem;
            box-shadow: var(--shadow-lg);
            margin-top: -3rem;
            position: relative;
            z-index: 10;
            border-radius: var(--radius-lg);
            border: 1px solid var(--glass-border);
        }

        .tool-tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            padding: 4px;
            background: rgba(0,0,0,0.1);
            border-radius: var(--radius-md);
        }

        .tool-tab {
            flex: 1;
            padding: 10px 12px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            border-radius: var(--radius-sm);
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }

        .tool-tab:hover {
            color: var(--text-color);
            background: rgba(0,161,214,0.1);
        }

        .tool-tab.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 2px 10px var(--primary-glow);
        }

        .tool-tab i {
            margin-right: 6px;
        }

        .tool-tab-content {
            display: none;
        }

        .tool-tab-content.active {
            display: block;
        }

        .live-info-card, .audio-info-card {
            background: rgba(0,0,0,0.15);
            padding: 16px;
            border-radius: var(--radius-md);
            display: flex;
            gap: 16px;
            align-items: flex-start;
        }

        .live-info-card img, .audio-info-card img {
            width: 100px;
            height: 100px;
            border-radius: var(--radius-md);
            object-fit: cover;
            flex-shrink: 0;
        }

        .live-info-card .info, .audio-info-card .info {
            flex: 1;
            min-width: 0;
        }

        .live-info-card h4, .audio-info-card h4 {
            margin: 0 0 8px 0;
            font-size: 18px;
            color: var(--text-color);
        }

        .live-info-card .meta, .audio-info-card .meta {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.8;
        }

        .live-status-live {
            display: inline-block;
            padding: 2px 8px;
            background: #ff4757;
            color: white;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 8px;
            animation: pulse 2s infinite;
        }

        .live-status-off {
            display: inline-block;
            padding: 2px 8px;
            background: #666;
            color: white;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 8px;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .emoji-package-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 12px;
        }

        .emoji-package-item {
            background: rgba(0,0,0,0.15);
            padding: 12px;
            border-radius: var(--radius-md);
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .emoji-package-item:hover {
            background: rgba(0,161,214,0.15);
            transform: translateY(-2px);
        }

        .emoji-package-item img {
            width: 48px;
            height: 48px;
            border-radius: 8px;
            margin-bottom: 8px;
        }

        .emoji-package-item .pkg-name {
            font-size: 13px;
            color: var(--text-color);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .emoji-package-item .pkg-count {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .emoji-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 10px;
        }

        .emoji-item {
            background: rgba(0,0,0,0.1);
            padding: 10px;
            border-radius: var(--radius-md);
            text-align: center;
            transition: all 0.2s ease;
            position: relative;
        }

        .emoji-item:hover {
            background: rgba(0,161,214,0.15);
        }

        .emoji-item img {
            width: 40px;
            height: 40px;
            margin-bottom: 6px;
        }

        .emoji-item .emoji-name {
            font-size: 11px;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .emoji-item .download-icon {
            position: absolute;
            top: 4px;
            right: 4px;
            width: 20px;
            height: 20px;
            background: var(--primary);
            color: white;
            border-radius: 50%;
            font-size: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.2s;
        }

        .emoji-item:hover .download-icon {
            opacity: 1;
        }

        .features {
            padding: 4rem 0;
            background: transparent;
        }

        .feature-card {
            padding: 2rem;
            border: 1px solid var(--border) !important;
            margin-bottom: 2rem;
            background: var(--glass-bg) !important;
            backdrop-filter: blur(10px);
            color: var(--text-color) !important;
            border-radius: var(--radius-md);
            position: relative;
            overflow: hidden;
        }

        .feature-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            opacity: 0;
        }

        .feature-card:hover {
            border-color: var(--border-hover) !important;
        }

        .feature-card:hover::before {
            opacity: 1;
        }

        .feature-icon {
            font-size: 2.5rem;
            color: var(--primary) !important;
            margin-bottom: 1rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 64px;
            height: 64px;
            border-radius: var(--radius-md);
            background: rgba(0, 161, 214, 0.1);
        }

        .feature-card h3 {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            color: var(--text-color) !important;
        }

        .feature-card p {
            color: var(--text-secondary) !important;
            font-size: 0.9rem;
            line-height: 1.7;
        }

        .tutorial {
            padding: 4rem 0;
            background: transparent;
        }

        .tutorial-step {
            padding: 2rem;
            border: 1px solid var(--border) !important;
            margin-bottom: 1.5rem;
            background: var(--glass-bg) !important;
            backdrop-filter: blur(10px);
            color: var(--text-color) !important;
            border-radius: var(--radius-md);
            position: relative;
        }

        .tutorial-step:hover {
            border-color: var(--border-hover);
        }

        .step-number {
            font-size: 1.5rem;
            font-weight: 900;
            color: var(--primary) !important;
            margin-bottom: 0.75rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 48px;
            height: 48px;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, rgba(0, 161, 214, 0.15), rgba(255, 133, 192, 0.1));
        }

        .tutorial-step h4, .tutorial-step h3 {
            color: var(--text-color) !important;
            font-weight: 700;
        }

        .tutorial-step p {
            color: var(--text-secondary) !important;
        }

        @media (max-width: 767px) {
            .tutorial-step {
                margin-bottom: 1rem;
            }
        }

        @media (min-width: 768px) {
            .hero-form {
                padding: 3rem;
                margin-top: -5rem;
            }

            .features {
                padding: 6rem 0;
            }

            .feature-card {
                padding: 2.5rem;
                margin-bottom: 0;
            }

            .feature-icon {
                font-size: 2rem;
                margin-bottom: 1.5rem;
                width: 72px;
                height: 72px;
            }

            .feature-card h3 {
                font-size: 1.3rem;
                margin-bottom: 1rem;
            }

            .tutorial {
                padding: 6rem 0;
            }

            .tutorial-step {
                padding: 2.5rem;
                margin-bottom: 2rem;
            }

            .step-number {
                font-size: 1.75rem;
                margin-bottom: 1rem;
                width: 56px;
                height: 56px;
            }
        }

        .faq {
            padding: 4rem 0;
            background: transparent;
        }

        .accordion-item {
            margin-bottom: 0.75rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-md) !important;
            overflow: hidden;
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
        }

        .accordion-header {
            background: transparent;
        }

        .accordion-item .accordion-button {
            font-weight: 600;
            color: var(--primary);
            padding: 1.25rem 1.5rem;
            background-color: transparent !important;
            border-radius: var(--radius-md) !important;
            transition: all 0.3s;
        }

        .accordion-item .accordion-button.collapsed {
            color: var(--text-color);
        }

        .accordion-item .accordion-button:hover {
            background-color: rgba(0, 161, 214, 0.05) !important;
        }

        .accordion-button:focus {
            box-shadow: none;
            border-color: var(--primary);
        }

        .accordion-body {
            background: transparent;
            color: var(--text-secondary);
            padding: 0 1.5rem 1.25rem;
        }

        .input-section {
            margin-bottom: 2rem;
        }

        .input-section label {
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--text-color);
            margin-bottom: 0.75rem;
            letter-spacing: -0.01em;
        }

        .input-group {
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            overflow: hidden;
        }

        .input-group:focus-within {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .input-group .form-control {
            border: none;
            padding: 1rem 1.25rem;
            font-size: 1rem;
            font-weight: 400;
            background: var(--card-bg-solid);
            color: var(--text-color);
        }

        .input-group .form-control:focus {
            box-shadow: none;
        }

        .input-group-text {
            background: var(--card-bg-solid);
            border: none;
            padding: 0 1.25rem;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            font-weight: 600;
            padding: 1rem 2rem;
            border-radius: var(--radius-md);
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        .btn-primary:hover {
            background: linear-gradient(135deg, var(--primary-dark), var(--primary));
            box-shadow: 0 6px 20px var(--primary-glow);
        }

        .btn-outline {
            border: 1px solid var(--border);
            color: var(--text-secondary);
            font-weight: 500;
            padding: 0.75rem 1.5rem;
            border-radius: var(--radius-md);
            background: transparent;
        }

        .btn-outline:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(0, 161, 214, 0.05);
        }

        .login-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.5rem;
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
            margin-bottom: 2rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            flex-wrap: wrap;
            gap: 1rem;
        }

        @media (min-width: 768px) {
            .faq {
                padding: 6rem 0;
            }

            .accordion-item {
                margin-bottom: 1rem;
            }

            .accordion-item .accordion-button {
                padding: 1.5rem 2rem;
            }

            .input-section {
                margin-bottom: 3rem;
            }

            .input-section label {
                font-size: 1.05rem;
                margin-bottom: 1rem;
            }

            .input-group .form-control {
                padding: 1.25rem 1.5rem;
                font-size: 1.05rem;
            }

            .input-group-text {
                padding: 0 1.5rem;
            }

            .btn-primary {
                padding: 1.15rem 2.5rem;
            }

            .btn-outline {
                padding: 1rem 2rem;
            }

            .login-bar {
                padding: 1.5rem 2rem;
                margin-bottom: 2.5rem;
                flex-wrap: nowrap;
                gap: 0;
            }
        }

        .login-bar .status {
            display: flex;
            align-items: center;
            gap: 1rem;
            font-size: 1rem;
            color: var(--text-secondary);
            font-weight: 500;
            flex-wrap: wrap;
        }

        .login-bar .status .actions {
            margin-left: 0.5rem;
            display: flex;
            align-items: center;
        }

        .login-bar .status.logged {
            color: var(--success);
        }

        .login-bar .actions {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        .login-bar button {
            font-weight: 500;
            font-size: 0.875rem;
            padding: 0.5rem 1rem;
            border-radius: var(--radius-sm);
        }

        .cookie-input {
            border: 1px solid var(--border);
            padding: 1rem 1.25rem;
            font-size: 0.875rem;
            resize: none;
            border-radius: var(--radius-md);
            background: var(--card-bg-solid);
            color: var(--text-color);
        }

        .cookie-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .qr-section {
            text-align: center;
            padding: 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
        }

        .qr-section img {
            max-width: 150px;
            box-shadow: var(--shadow);
            border-radius: var(--radius-md);
        }

        .fav-select {
            border: 1px solid var(--border);
            padding: 0.75rem 1.25rem;
            font-size: 0.875rem;
            border-radius: var(--radius-md);
            background: var(--card-bg-solid);
            color: var(--text-color);
        }

        .fav-select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        @media (min-width: 768px) {
            .login-bar .status {
                gap: 0.75rem;
                font-size: 1.05rem;
            }

            .login-bar .actions {
                gap: 1rem;
                flex-wrap: nowrap;
            }

            .login-bar button {
                font-size: 1rem;
                padding: 0.75rem 1.5rem;
            }

            .cookie-input {
                padding: 1.25rem 1.5rem;
                font-size: 1rem;
            }

            .qr-section {
                padding: 2.5rem;
            }

            .qr-section img {
                max-width: 200px;
            }

            .fav-select {
                padding: 1rem 1.5rem;
                font-size: 1rem;
            }
        }

        .form-check-input {
            width: 20px;
            height: 20px;
            border: 2px solid var(--border);
            border-radius: 4px;
        }

        .form-check-input:checked {
            background-color: var(--primary);
            border-color: var(--primary);
        }

        .form-check-input:focus {
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .quality-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 3rem;
        }

        .quality-btn {
            padding: 0.65rem 1.25rem;
            border: 1px solid var(--border);
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-secondary);
            background: var(--glass-bg);
            cursor: pointer;
            border-radius: var(--radius-md);
        }

        .quality-btn:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(0, 161, 214, 0.05);
        }

        .quality-btn.active {
            border-color: var(--primary);
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            box-shadow: 0 4px 15px var(--primary-glow);
        }

        .episode-section {
            margin-top: 3rem;
        }

        .episode-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
        }

        .episode-title {
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--text-color);
        }

        .episode-list {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--border);
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
            border-radius: var(--radius-md);
            scrollbar-width: thin;
            scrollbar-color: var(--primary) transparent;
        }

        .episode-item {
            display: flex;
            align-items: center;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            font-size: 1rem;
        }

        .episode-item:last-child {
            border-bottom: none;
        }

        .episode-item:hover {
            background: rgba(0, 161, 214, 0.05);
        }

        .episode-item input {
            margin-right: 1.25rem;
            width: 20px;
            height: 20px;
            accent-color: var(--primary);
        }

        .episode-item label {
            flex: 1;
            cursor: pointer;
            color: var(--text-color);
            font-weight: 400;
        }

        .episode-item .ep-num {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
        }

        .episode-quality-select {
            margin: 0.75rem 1rem;
            padding: 0.5rem 1rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 0.9rem;
            color: var(--text-color);
            background: var(--card-bg-solid);
            cursor: pointer;
            min-width: 140px;
        }

        .episode-quality-select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .episode-quality-select:hover {
            border-color: var(--primary);
        }

        .download-btn {
            width: 100%;
            padding: 1.25rem;
            font-size: 1.15rem;
            font-weight: 700;
            margin-top: 3rem;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            box-shadow: 0 4px 20px var(--primary-glow);
        }

        .download-btn:hover {
            background: linear-gradient(135deg, var(--primary-dark), var(--primary));
            box-shadow: 0 6px 25px var(--primary-glow);
        }

        .toast-container {
            position: fixed;
            top: 90px;
            right: 20px;
            z-index: 1100;
            max-width: 80%;
        }

        .toast {
            min-width: 200px;
            max-width: 100%;
            background: var(--card-bg-solid);
            box-shadow: var(--shadow-lg);
            border: 1px solid var(--border);
            font-size: 0.85rem;
            border-radius: var(--radius-md);
            overflow: hidden;
        }

        .toast .toast-header {
            background: var(--card-bg-solid);
            border-bottom: 1px solid var(--border);
            padding: 0.5rem 1rem;
            font-size: 0.85rem;
            color: var(--text-color);
        }

        .toast .toast-body {
            padding: 0.75rem 1rem;
            color: var(--text-secondary);
        }

        @media (min-width: 768px) {
            .toast-container {
                top: 100px;
                right: 20px;
                max-width: none;
            }

            .toast {
                min-width: 300px;
                font-size: 0.9rem;
            }

            .toast .toast-header {
                padding: 0.6rem 1.25rem;
                font-size: 0.9rem;
            }

            .toast .toast-body {
                padding: 0.85rem 1.25rem;
            }
        }

        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(26, 31, 46, 0.92);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1050;
            backdrop-filter: blur(12px);
        }

        .spinner {
            width: 60px;
            height: 60px;
            background: url('favicon.ico') no-repeat center center;
            background-size: contain;
            animation: bounce 1s ease-in-out infinite;
            filter: drop-shadow(0 0 20px var(--primary-glow));
        }

        @keyframes bounce {
            0%, 100% {
                transform: translateY(0);
            }
            50% {
                transform: translateY(-20px);
            }
        }

        .loading-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1.5rem;
        }

        .loading-text {
            color: white;
            font-size: 1.15rem;
            font-weight: 500;
        }

        .progress-container {
            width: 320px;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            transition: width 0.3s ease;
            border-radius: 4px;
        }

        .progress-text {
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
            text-align: center;
            font-weight: 500;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .alert {
            border: 1px solid var(--border);
            padding: 1.25rem 1.5rem;
            margin-bottom: 2rem;
            border-radius: var(--radius-md);
            backdrop-filter: blur(10px);
        }

        .alert-info {
            background-color: rgba(0, 161, 214, 0.08);
            color: var(--primary);
            border-color: rgba(0, 161, 214, 0.2);
        }

        .alert-success {
            background-color: rgba(0, 214, 143, 0.08);
            color: var(--success);
            border-color: rgba(0, 214, 143, 0.2);
        }

        .alert-danger {
            background-color: rgba(255, 71, 87, 0.08);
            color: var(--danger);
            border-color: rgba(255, 71, 87, 0.2);
        }

        .footer {
            background: var(--dark-surface);
            color: var(--text-color);
            padding: 4rem 0 2rem;
            margin-top: 6rem;
            border-top: 1px solid var(--border);
        }

        .footer h4 {
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: var(--text-color);
            letter-spacing: -0.02em;
        }

        .footer a {
            color: var(--text-secondary);
            text-decoration: none;
        }

        .footer a:hover {
            color: var(--primary);
        }

        .footer-bottom {
            border-top: 1px solid var(--border);
            padding-top: 2rem;
            margin-top: 2rem;
        }

        .card {
            background-color: var(--card-bg-solid);
            border-color: var(--border);
            color: var(--text-color);
        }

        .card-body {
            color: var(--text-color);
        }

        .card-title {
            color: var(--text-color);
        }

        .list-group-item {
            background-color: var(--card-bg-solid);
            border-color: var(--border);
            color: var(--text-color);
        }

        .list-group-item:hover {
            background-color: var(--glass-bg);
        }

        .list-group-item.active {
            background-color: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        .btn-close {
            filter: invert(1) grayscale(100%) brightness(200%);
        }

        [data-theme="light"] .btn-close {
            filter: none;
        }

        .btn-secondary {
            background-color: var(--secondary);
            border-color: var(--secondary);
            color: white;
        }

        .btn-success {
            color: white;
        }

        .display-4 {
            color: var(--text-color);
        }

        .text-lg {
            color: var(--text-color);
        }

        .lead {
            color: var(--text-secondary);
        }

        .text-muted {
            color: var(--text-secondary) !important;
        }

        .py-12 {
            padding-top: 4rem;
            padding-bottom: 4rem;
        }

        .mb-6 {
            margin-bottom: 2rem;
        }

        .mb-8 {
            margin-bottom: 2.5rem;
        }

        @media (max-width: 768px) {
            body {
                padding-top: 60px;
            }

            .navbar {
                padding: 0.5rem 0;
            }

            .navbar-brand img {
                height: 32px !important;
            }

            .navbar-toggler {
                padding: 0.4rem 0.6rem;
            }

            .hero {
                padding: 3rem 0;
                margin-bottom: 2rem;
            }

            .hero h1 {
                font-size: 2rem;
            }

            .hero p {
                font-size: 1rem;
            }

            .hero-form {
                padding: 1.25rem;
            }

            .feature-card {
                padding: 1.25rem;
                margin-bottom: 1rem;
            }

            .feature-icon {
                font-size: 1.5rem;
                margin-bottom: 0.5rem;
                width: 48px;
                height: 48px;
            }

            .feature-card h3 {
                font-size: 1rem;
            }

            .feature-card p {
                font-size: 0.8rem;
            }

            .container {
                font-size: 0.875rem;
            }

            h2 {
                font-size: 1.5rem;
            }

            h3 {
                font-size: 1rem;
            }

            .btn {
                padding: 0.5rem 1rem;
                font-size: 0.875rem;
            }

            .card {
                padding: 1rem;
            }

            .modal-dialog {
                max-width: 95%;
                margin: 0.5rem auto;
            }

            .modal-content {
                font-size: 0.875rem;
                border-radius: var(--radius-lg) !important;
            }

            .modal-header {
                padding: 1rem 1.25rem;
            }

            .modal-body {
                padding: 1.25rem;
            }

            .modal-footer {
                padding: 0.75rem 1.25rem;
            }

            .form-control, .form-select {
                padding: 0.5rem 0.875rem;
                font-size: 0.875rem;
            }

            .table {
                font-size: 0.75rem;
            }

            .table td, .table th {
                padding: 0.5rem;
            }

            .spinner {
                width: 40px;
                height: 40px;
            }

            .loading-text {
                font-size: 1rem;
            }

            .progress-container {
                width: 90%;
                max-width: 280px;
            }

            .progress-bar {
                height: 6px;
            }

            .video-list-item {
                padding: 0.5rem;
            }

            .video-info {
                font-size: 0.75rem;
            }

            .episode-item {
                padding: 0.75rem 1rem;
                font-size: 0.875rem;
            }

            .episode-item input {
                margin-right: 0.75rem;
                width: 16px;
                height: 16px;
            }

            .episode-item .ep-num {
                font-size: 0.75rem;
            }

            .episode-quality-select {
                margin: 0.5rem 0.5rem;
                padding: 0.3rem 0.6rem;
                font-size: 0.75rem;
                min-width: 100px;
            }

            .input-group {
                flex-wrap: nowrap;
            }

            .input-group .form-control {
                padding: 0.65rem 0.875rem;
                font-size: 0.875rem;
            }

            .input-group-text {
                padding: 0 0.875rem;
                font-size: 0.875rem;
            }

            .input-group .btn {
                padding: 0.65rem 1rem;
                font-size: 0.875rem;
            }

            .input-section label {
                font-size: 0.875rem;
            }
        }
    </style>
</head>
<body>

    <amp-auto-ads type="adsense" data-ad-client="ca-pub-9568438449258885"></amp-auto-ads>

    <a href="https://github.com/NANblogink/bilibilidownloadtool" target="_blank" class="github-corner" aria-label="View source on GitHub" style="position: fixed; top: 0; right: 0; z-index: 100000; display: none; pointer-events: auto;">
        <svg width="80" height="80" viewBox="0 0 250 250" style="fill:#151513; color:#fff; border: 0;" aria-hidden="true">
            <path d="M0,0 L115,115 L130,115 L142,142 L250,250 L250,0 Z"></path>
            <path d="M128.3,109.0 C113.8,99.7 119.0,89.6 119.0,89.6 C122.0,82.7 120.5,78.6 120.5,78.6 C119.2,72.0 123.4,76.3 123.4,76.3 C127.3,80.9 125.5,87.3 125.5,87.3 C122.9,97.6 130.6,101.9 134.4,103.2" fill="currentColor" style="transform-origin: 130px 106px;" class="octo-arm"></path>
            <path d="M115.0,115.0 C114.9,115.1 118.7,116.5 119.8,115.4 L133.7,101.6 C136.9,99.2 139.9,98.4 142.2,98.6 C133.8,88.0 127.5,74.4 143.8,58.0 C148.5,53.4 154.0,51.2 159.7,51.0 C160.3,49.4 163.2,43.6 171.4,40.1 C171.4,40.1 176.1,42.5 178.8,56.2 C183.1,58.6 187.2,61.8 190.9,65.4 C194.5,69.0 197.7,73.2 200.1,77.6 C213.8,80.2 216.3,84.9 216.3,84.9 C212.7,93.1 206.9,96.0 205.4,96.6 C205.1,102.4 203.0,107.8 198.3,112.5 C181.9,128.9 168.3,122.5 157.7,114.1 C157.9,116.9 156.7,120.9 152.7,124.9 L141.0,136.5 C139.8,137.7 141.6,141.9 141.8,141.8 Z" fill="currentColor" class="octo-body"></path>
        </svg>
    </a>
    <style>
        .github-corner:hover .octo-arm {
            animation: octocat-wave 560ms ease-in-out
        }
        @keyframes octocat-wave {
            0%, 100% { transform: rotate(0) }
            20%, 60% { transform: rotate(-25deg) }
            40%, 80% { transform: rotate(10deg) }
        }
        @media (max-width: 500px) {
            .github-corner:hover .octo-arm {
                animation: none
            }
            .github-corner .octo-arm {
                animation: octocat-wave 560ms ease-in-out
            }
        }
        @media (min-width: 1024px) {
            .github-corner {
                display: block !important;
            }
        }
    </style>
    



    
    <style>
        /* 扫光效果动画 */
        @keyframes shine {
            0% {
                left: -100%;
            }
            100% {
                left: 100%;
            }
        }
        
        /* 扫码提示动画 */
        @keyframes scan {
            0% {
                top: -10px;
                opacity: 0;
            }
            50% {
                opacity: 1;
            }
            100% {
                top: 100%;
                opacity: 0;
            }
        }
        
        /* 确保扫光效果在日间模式下也能显示 */
        .logo-container {
            position: relative;
            display: inline-block;
            overflow: hidden;
        }
        
        .logo-shine {
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 20%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.8), transparent);
            transform: rotate(45deg);
            animation: shine 2s infinite;
            z-index: 2;
        }
        
        @media (max-width: 768px) {
            #reward-code {
                display: none !important;
            }
            
            .navbar-collapse {
                background-color: var(--card-bg) !important;
                border-radius: 0 0 10px 10px !important;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1) !important;
                max-height: 50vh !important;
                overflow-y: auto !important;
                margin-top: 0.5rem;
                width: 90% !important;
                margin-left: auto;
                margin-right: auto;
            }
            
            .navbar-nav {
                padding: 0.2rem 0;
            }
            
            .nav-link {
                padding: 0.25rem 0.75rem !important;
                font-size: 0.75rem;
                line-height: 1.2;
            }
            
            .navbar {
                padding: 0.3rem 0 !important;
            }
            
            .navbar-brand img {
                height: 36px !important;
            }
        }
        
        [data-theme="light"] {
            --text-color: #1a202c !important;
            --bg-color: #f0f4f8 !important;
            --card-bg: rgba(255, 255, 255, 0.8) !important;
            --card-bg-solid: #ffffff !important;
            --light: #e2e8f0 !important;
            --border: rgba(0, 0, 0, 0.08) !important;
            --border-hover: rgba(0, 161, 214, 0.3) !important;
            --muted: #a0aec0 !important;
            --glass-bg: rgba(255, 255, 255, 0.7) !important;
            --glass-border: rgba(0, 0, 0, 0.06) !important;
        }

        [data-theme="light"] body {
            background: var(--bg-gradient) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .navbar {
            background: rgba(255, 255, 255, 0.85) !important;
            border-bottom-color: rgba(0, 0, 0, 0.06) !important;
        }

        [data-theme="light"] .nav-link {
            color: var(--gray) !important;
        }

        [data-theme="light"] .nav-link:hover,
        [data-theme="light"] .nav-link.active {
            color: var(--primary) !important;
            background: rgba(0, 161, 214, 0.06);
        }

        [data-theme="light"] .card,
        [data-theme="light"] .modal-content,
        [data-theme="light"] .hero-form,
        [data-theme="light"] .feature-card,
        [data-theme="light"] .tutorial-step,
        [data-theme="light"] .login-bar,
        [data-theme="light"] .qr-section,
        [data-theme="light"] .alert {
            background-color: var(--card-bg) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .form-control,
        [data-theme="light"] .form-select,
        [data-theme="light"] .cookie-input,
        [data-theme="light"] .fav-select {
            background-color: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .form-control::placeholder {
            color: var(--muted) !important;
        }

        [data-theme="light"] .input-group-text {
            background-color: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .btn {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
            border-color: var(--primary) !important;
            color: white !important;
        }

        [data-theme="light"] .btn-outline {
            border-color: var(--border) !important;
            color: var(--text-secondary) !important;
            background-color: transparent !important;
        }

        [data-theme="light"] .btn-outline:hover {
            border-color: var(--primary) !important;
            color: var(--primary) !important;
            background-color: rgba(0, 161, 214, 0.05) !important;
        }

        [data-theme="light"] a {
            color: var(--text-color) !important;
        }

        [data-theme="light"] a:hover {
            color: var(--primary) !important;
        }

        [data-theme="light"] h1,
        [data-theme="light"] h2,
        [data-theme="light"] h3,
        [data-theme="light"] h4,
        [data-theme="light"] h5,
        [data-theme="light"] h6 {
            color: var(--text-color) !important;
        }

        [data-theme="light"] p {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .text-muted,
        [data-theme="light"] .lead {
            color: var(--muted) !important;
        }

        [data-theme="light"] .accordion {
            background-color: transparent !important;
        }

        [data-theme="light"] .accordion-item {
            background-color: var(--card-bg) !important;
            border-color: var(--border) !important;
        }

        [data-theme="light"] .accordion-header {
            background-color: transparent !important;
        }

        [data-theme="light"] .accordion-item .accordion-button {
            color: var(--primary) !important;
            background-color: transparent !important;
        }

        [data-theme="light"] .accordion-item .accordion-button.collapsed {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .accordion-button:hover {
            color: var(--primary) !important;
        }

        [data-theme="light"] .accordion-button:not(.collapsed) {
            color: var(--primary) !important;
            background-color: rgba(0, 161, 214, 0.05) !important;
        }

        [data-theme="light"] .accordion-body {
            background-color: transparent !important;
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .toast {
            background-color: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .toast-header {
            background-color: var(--card-bg-solid) !important;
            border-bottom-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .toast-body {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .modal-header,
        [data-theme="light"] .modal-footer {
            border-color: var(--border) !important;
            background-color: var(--card-bg-solid) !important;
        }

        [data-theme="light"] .card {
            background-color: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .card-body {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .card-title {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .list-group-item {
            background-color: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .list-group-item:hover {
            background-color: var(--glass-bg) !important;
        }

        [data-theme="light"] .list-group-item.active {
            background-color: var(--primary) !important;
            border-color: var(--primary) !important;
            color: white !important;
        }

        [data-theme="light"] .display-4 {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .text-lg {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .lead {
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .text-muted {
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .btn-secondary {
            background-color: var(--secondary) !important;
            border-color: var(--secondary) !important;
            color: white !important;
        }

        [data-theme="light"] .btn-success {
            color: white !important;
        }

        [data-theme="light"] .modal-title {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .modal-body {
            background-color: var(--card-bg-solid) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .dropdown-menu {
            background-color: rgba(255, 255, 255, 0.98) !important;
            border-color: rgba(0, 0, 0, 0.08) !important;
        }

        [data-theme="light"] .dropdown-item {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .dropdown-item:hover {
            background-color: rgba(0, 161, 214, 0.08) !important;
            color: var(--primary) !important;
        }

        [data-theme="light"] .quality-btn {
            background: var(--card-bg) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .quality-btn:hover {
            border-color: var(--primary) !important;
            color: var(--primary) !important;
        }

        [data-theme="light"] .quality-btn.active {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
            border-color: var(--primary) !important;
            color: white !important;
        }

        [data-theme="light"] .episode-list {
            background: var(--card-bg) !important;
            border-color: var(--border) !important;
        }

        [data-theme="light"] .episode-item {
            border-bottom-color: var(--border) !important;
        }

        [data-theme="light"] .episode-item:hover {
            background: rgba(0, 161, 214, 0.05) !important;
        }

        [data-theme="light"] .episode-item label {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .episode-item .ep-num {
            color: var(--muted) !important;
        }

        [data-theme="light"] .episode-quality-select {
            background: var(--card-bg-solid) !important;
            border-color: var(--border) !important;
            color: var(--text-color) !important;
        }

        [data-theme="light"] .footer {
            background: #f0f4f8 !important;
            border-top-color: var(--border) !important;
        }

        [data-theme="light"] .footer a {
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .footer a:hover {
            color: var(--primary) !important;
        }

        [data-theme="light"] .navbar-toggler-icon {
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3e%3cpath stroke='rgba%280, 0, 0, 0.6%29' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e") !important;
        }

        [data-theme="light"] .btn-close {
            filter: none !important;
        }

        [data-theme="light"] #backToTop {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
            color: white !important;
        }

        [data-theme="light"] .hero {
            background: linear-gradient(135deg, #f0f4f8 0%, #e0f0ff 40%, #f5e6f0 70%, #f0f4f8 100%) !important;
        }

        [data-theme="light"] .hero h1 {
            background: linear-gradient(135deg, #1a202c 0%, #00a1d6 50%, #ff85c0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        [data-theme="light"] .hero p {
            color: rgba(0, 0, 0, 0.5) !important;
        }

        [data-theme="light"] .feature-card h3,
        [data-theme="light"] .tutorial-step h4,
        [data-theme="light"] .tutorial-step h3 {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .feature-card p,
        [data-theme="light"] .tutorial-step p {
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .alert {
            background-color: rgba(0, 161, 214, 0.05) !important;
            border-color: rgba(0, 161, 214, 0.15) !important;
            color: var(--primary) !important;
        }

        [data-theme="light"] .alert-success {
            background-color: rgba(56, 161, 105, 0.05) !important;
            border-color: rgba(56, 161, 105, 0.15) !important;
            color: var(--success) !important;
        }

        [data-theme="light"] .alert-danger {
            background-color: rgba(229, 62, 62, 0.05) !important;
            border-color: rgba(229, 62, 62, 0.15) !important;
            color: var(--danger) !important;
        }

        [data-theme="light"] #encryptionModal .modal-header {
            background-color: rgba(221, 107, 32, 0.05) !important;
            border-bottom: 1px solid var(--border) !important;
        }

        [data-theme="light"] #encryptionModal .modal-title {
            color: var(--warning) !important;
        }

        [data-theme="light"] #encryptionModal .modal-body h6 {
            color: var(--danger) !important;
        }

        [data-theme="light"] #encryptionModal .modal-body p {
            color: var(--warning) !important;
        }

        [data-theme="light"] .loading-overlay {
            background: rgba(240, 244, 248, 0.92) !important;
        }

        [data-theme="light"] .loading-text {
            color: var(--text-color) !important;
        }

        [data-theme="light"] .progress-text {
            color: var(--text-secondary) !important;
        }

        [data-theme="light"] .progress-bar {
            background-color: rgba(0, 0, 0, 0.08) !important;
        }

        [data-theme="light"] .speed-eta-container span {
            color: var(--text-secondary) !important;
        }
    </style>




    <section class="hero">
        <div class="container text-center">
            <h1>免费B站视频下载 - 在线解析下载工具</h1>
            <p>免费在线解析下载B站视频，支持4K/1080P多清晰度、UP主主页批量下载、收藏夹解析</p>
            <a href="#tool" class="btn btn-primary btn-lg" style="border-radius: 0;">开始使用</a>
        </div>
    </section>


    <section id="tool" class="py-8">
        <div class="container">
            <div class="hero-form">

                <div class="login-bar" id="loginBar">
                    <div class="status" id="loginStatus">
                        <i class="fas fa-user-circle"></i>
                        <span id="username">未登录</span>
                        <div class="actions" id="logoutActions" style="display: none;">
                            <button class="btn btn-danger" id="logoutBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-sign-out-alt"></i> 注销登录
                            </button>
                        </div>
                    </div>
                    <div class="actions" id="loginActions">
                        <button class="btn btn-outline me-2" id="cookieLoginBtn" style="padding: 8px 16px; border-radius: 0;">
                            <i class="fas fa-cookie-bite"></i> Cookie
                        </button>
                        <button class="btn btn-outline" id="qrLoginBtn" style="padding: 8px 16px; border-radius: 0;">
                            <i class="fas fa-qrcode"></i> 扫码
                        </button>
                    </div>
                </div>

                <div class="tool-tabs">
                    <button class="tool-tab active" data-tab="video"><i class="fas fa-video"></i> 视频解析</button>
                    <button class="tool-tab" data-tab="live"><i class="fas fa-broadcast-tower"></i> 直播解析</button>
                    <button class="tool-tab" data-tab="audio"><i class="fas fa-music"></i> 音频解析</button>
                    <button class="tool-tab" data-tab="emoji"><i class="fas fa-grin-alt"></i> 表情下载</button>
                </div>


                <div id="cookieLoginSection" class="input-section" style="display: none;">
                    <label for="cookieInput">输入Cookie（包含SESSDATA）</label>
                    <textarea class="form-control cookie-input" id="cookieInput" rows="3" placeholder="请粘贴完整的Cookie..."></textarea>
                    <div class="mt-3">
                        <button class="btn btn-primary" id="saveCookieBtn" style="padding: 8px 16px; border-radius: 0;">
                            <i class="fas fa-save"></i> 保存Cookie
                        </button>
                    </div>
                </div>


                <div id="qrLoginSection" class="input-section" style="display: none;">
                    <div class="qr-section">
                        <h4>扫码登录</h4>
                        <p class="text-muted">请使用B站App扫描下方二维码</p>
                        <div style="position: relative; display: inline-block; margin-top: 16px;">
                            <canvas id="qrcode"></canvas>

                            <div style="position: absolute; top: -5px; left: -5px; width: 30px; height: 30px; border-top: 3px solid #00a1d6; border-left: 3px solid #00a1d6;"></div>
                            <div style="position: absolute; top: -5px; right: -5px; width: 30px; height: 30px; border-top: 3px solid #00a1d6; border-right: 3px solid #00a1d6;"></div>
                            <div style="position: absolute; bottom: -5px; left: -5px; width: 30px; height: 30px; border-bottom: 3px solid #00a1d6; border-left: 3px solid #00a1d6;"></div>
                            <div style="position: absolute; bottom: -5px; right: -5px; width: 30px; height: 30px; border-bottom: 3px solid #00a1d6; border-right: 3px solid #00a1d6;"></div>

                            <div style="position: absolute; left: -20px; width: calc(100% + 40px); height: 5px; background: linear-gradient(90deg, transparent, #00a1d6, transparent); animation: scan 2s linear infinite;"></div>
                        </div>
                        <p id="qrStatus" class="mt-3 text-muted">加载中...</p>
                    </div>
                </div>


                <div id="tab-video" class="tool-tab-content active">

                <div class="input-section">
                    <label for="videoUrl">输入链接 (BV/ss/av/UP主空间)</label>
                    <div class="input-group">
                        <input type="text" class="form-control" id="videoUrl" placeholder="例如: https://www.bilibili.com/video/BV1xx411c7mC">
                        <button class="btn btn-primary" id="parseBtn" style="padding: 8px 16px; border-radius: 0;">
                            <i class="fas fa-search"></i> 解析
                        </button>
                    </div>
                </div>


                <div class="input-section">
                    <label for="favSelect">收藏夹</label>
                    <div class="input-group">
                        <select class="form-control fav-select" id="favSelect">
                            <option value="">选择收藏夹</option>
                        </select>
                        <button class="btn btn-outline" id="loadFavBtn" style="padding: 8px 16px; border-radius: 0;">
                            加载收藏夹
                        </button>
                    </div>
                </div>


                <div class="input-section">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="completeMode">
                        <label class="form-check-label" for="completeMode">
                            完全模式（自动全选并下载）
                        </label>
                    </div>
                </div>


                <div id="resultSection" class="mt-6" style="display: none;">

                    <button class="btn btn-outline mb-4" id="backBtn" style="padding: 8px 16px; border-radius: 0;">
                        <i class="fas fa-arrow-left"></i> 返回列表
                    </button>
                    

                    <div id="videoInfo" class="mb-6"></div>


                    <div class="input-section">
                        <label>选择清晰度</label>
                        <div class="quality-grid" id="qualityGrid"></div>
                    </div>


                    <div class="episode-section">
                        <div class="episode-header">
                            <h4 class="episode-title">选择集数</h4>
                            <div>
                                <button class="btn btn-outline me-2" id="selectAllBtn" style="padding: 6px 12px; border-radius: 0;">全选</button>
                                <button class="btn btn-outline" id="selectNoneBtn" style="padding: 6px 12px; border-radius: 0;">取消</button>
                            </div>
                        </div>
                        <div class="episode-list" id="episodeList"></div>
                    </div>


                    <button class="btn btn-primary download-btn" id="downloadBtn" style="padding: 10px 20px; border-radius: 0;">
                        <i class="fas fa-download"></i> 浏览器合成下载
                    </button>
                </div>

                </div>

                <div id="tab-live" class="tool-tab-content">
                    <div class="input-section">
                        <label for="liveRoomId">输入直播间号</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="liveRoomId" placeholder="例如: 22637261 或 live.bilibili.com/22637261">
                            <button class="btn btn-primary" id="liveParseBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-search"></i> 解析
                            </button>
                        </div>
                        <div class="form-text">支持输入直播间号或直播间链接</div>
                    </div>

                    <div id="liveResultSection" class="mt-6" style="display: none;">
                        <div id="liveInfo" class="live-info-card"></div>

                        <div class="input-section mt-4">
                            <label>选择清晰度</label>
                            <div class="quality-grid" id="liveQualityGrid"></div>
                        </div>

                        <div class="input-section">
                            <label>直播流地址</label>
                            <div class="input-group">
                                <input type="text" class="form-control" id="liveStreamUrl" readonly>
                                <button class="btn btn-outline" id="liveCopyBtn" style="padding: 8px 16px; border-radius: 0;">
                                    <i class="fas fa-copy"></i> 复制
                                </button>
                            </div>
                        </div>

                        <button class="btn btn-primary download-btn" id="liveOpenBtn" style="padding: 10px 20px; border-radius: 0;">
                            <i class="fas fa-play"></i> 在新窗口播放
                        </button>
                    </div>
                </div>

                <div id="tab-audio" class="tool-tab-content">
                    <div class="input-section">
                        <label for="audioId">输入音频ID（AU号）</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="audioId" placeholder="例如: AU256029 或 bilibili.com/audio/au256029">
                            <button class="btn btn-primary" id="audioParseBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-search"></i> 解析
                            </button>
                        </div>
                        <div class="form-text">支持输入AU号或音频页面链接</div>
                    </div>

                    <div id="audioResultSection" class="mt-6" style="display: none;">
                        <div id="audioInfo" class="audio-info-card"></div>

                        <div class="input-section mt-4">
                            <label>选择音质</label>
                            <div class="quality-grid" id="audioQualityGrid"></div>
                        </div>

                        <div class="input-section">
                            <label>音频下载地址</label>
                            <div class="input-group">
                                <input type="text" class="form-control" id="audioStreamUrl" readonly>
                                <button class="btn btn-outline" id="audioCopyBtn" style="padding: 8px 16px; border-radius: 0;">
                                    <i class="fas fa-copy"></i> 复制
                                </button>
                            </div>
                        </div>

                        <button class="btn btn-primary download-btn" id="audioDownloadBtn" style="padding: 10px 20px; border-radius: 0;">
                            <i class="fas fa-download"></i> 下载音频
                        </button>
                    </div>
                </div>

                <div id="tab-emoji" class="tool-tab-content">
                    <div class="input-section">
                        <label>表情包</label>
                        <div class="input-group">
                            <select class="form-control" id="emojiBusiness">
                                <option value="reply">评论区</option>
                                <option value="dynamic">动态</option>
                            </select>
                            <button class="btn btn-primary" id="emojiLoadHotBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-fire"></i> 热门表情
                            </button>
                            <button class="btn btn-outline" id="emojiLoadMyBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-user"></i> 我的表情
                            </button>
                        </div>
                        <div class="form-text">热门表情免登录浏览，「我的表情」需登录后查看</div>
                    </div>

                    <div id="emojiPackageList" class="emoji-package-grid" style="display: none;"></div>

                    <div id="emojiDetailSection" class="mt-6" style="display: none;">
                        <button class="btn btn-outline mb-4" id="emojiBackBtn" style="padding: 8px 16px; border-radius: 0;">
                            <i class="fas fa-arrow-left"></i> 返回列表
                        </button>
                        <div id="emojiPackageInfo" class="mb-4"></div>
                        <div class="input-section">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <label style="margin-bottom:0;">表情列表</label>
                                <button class="btn btn-outline btn-sm" id="emojiDownloadAllBtn" style="padding:4px 10px;border-radius:0;font-size:12px;">
                                    <i class="fas fa-download"></i> 打包下载全部
                                </button>
                            </div>
                        </div>
                        <div id="emojiGrid" class="emoji-grid"></div>
                    </div>
                </div>

            </div>
        </div>
    </section>


    <section id="features" class="features">
        <div class="container">
            <div class="text-center mb-8">
                <h2 class="display-4">B站视频解析下载功能特点</h2>
                <p class="lead text-muted">我们的工具提供了丰富的功能，满足您的各种需求</p>
            </div>
            
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-video"></i>
                        </div>
                        <h3>B站视频多格式解析</h3>
                        <p>支持解析BV号、ss号、av号、UP主主页、收藏夹等多种B站链接格式，一键解析下载</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-hdd"></i>
                        </div>
                        <h3>4K/1080P高清下载</h3>
                        <p>提供4K超清、1080P高清、720P、480P等多种清晰度选择，满足不同下载需求</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-desktop"></i>
                        </div>
                        <h3>浏览器在线合成</h3>
                        <p>使用FFmpeg.wasm在浏览器中直接合并视频和音频，无需安装软件，在线完成下载</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-user"></i>
                        </div>
                        <h3>UP主主页批量解析</h3>
                        <p>输入UP主主页链接，一键获取其发布的所有B站视频列表，支持批量解析下载</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-star"></i>
                        </div>
                        <h3>B站收藏夹批量下载</h3>
                        <p>直接解析您的B站收藏夹，批量下载收藏的视频，轻松保存喜欢的B站内容</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <div class="feature-icon">
                            <i class="fas fa-lock"></i>
                        </div>
                        <h3>安全隐私保护</h3>
                        <p>所有B站视频解析和下载操作都在浏览器本地完成，视频数据不会上传到服务器，安全可靠</p>
                    </div>
                </div>
            </div>
        </div>
    </section>


    <section id="tutorial" class="tutorial">
        <div class="container">
            <div class="text-center mb-8">
                <h2 class="display-4">B站视频下载使用教程</h2>
                <p class="lead text-muted">简单几步，轻松下载B站视频</p>
            </div>
            
            <div class="row g-4">
                <div class="col-md-4 d-flex">
                    <div class="tutorial-step flex-grow-1">
                        <div class="step-number">1</div>
                        <h3>粘贴B站视频链接</h3>
                        <p>在输入框中粘贴B站视频链接，支持BV号、ss号、av号、UP主主页链接或收藏夹链接</p>
                    </div>
                </div>
                <div class="col-md-4 d-flex">
                    <div class="tutorial-step flex-grow-1">
                        <div class="step-number">2</div>
                        <h3>登录B站账号（可选）</h3>
                        <p>如果需要下载会员视频或收藏夹，请使用Cookie或扫码登录B站账号</p>
                    </div>
                </div>
                <div class="col-md-4 d-flex">
                    <div class="tutorial-step flex-grow-1">
                        <div class="step-number">3</div>
                        <h3>选择视频清晰度</h3>
                        <p>解析完成后，选择您需要的视频清晰度，支持4K超清、1080P高清等多种清晰度</p>
                    </div>
                </div>
                <div class="col-md-6 d-flex">
                    <div class="tutorial-step flex-grow-1">
                        <div class="step-number">4</div>
                        <h3>选择下载集数</h3>
                        <p>选择您需要下载的视频集数，支持批量选择多集下载</p>
                    </div>
                </div>
                <div class="col-md-6 d-flex">
                    <div class="tutorial-step flex-grow-1">
                        <div class="step-number">5</div>
                        <h3>在线合成下载</h3>
                        <p>点击"浏览器合成下载"按钮，视频在浏览器中自动合成完成后即可下载到本地</p>
                    </div>
                </div>
            </div>
        </div>
    </section>


    <section id="faq" class="faq">
        <div class="container">
            <div class="text-center mb-8">
                <h2 class="display-4">B站视频解析常见问题</h2>
                <p class="lead text-muted">解答您可能遇到的问题</p>
            </div>
            
            <div class="row">
                <div class="col-md-8 offset-md-2">
                    <div class="accordion" id="faqAccordion">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#faq1">
                                    B站视频下载需要登录账号吗？
                                </button>
                            </h2>
                            <div id="faq1" class="accordion-collapse collapse show">
                                <div class="accordion-body">
                                    登录B站账号可以下载会员视频、收藏夹中的视频，以及获取UP主的完整视频列表。如果只下载公开视频，可以不登录。
                                </div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faq2">
                                    B站视频下载速度慢怎么办？
                                </button>
                            </h2>
                            <div id="faq2" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    下载速度取决于您的网络环境和B站服务器的响应速度。建议在网络环境良好的情况下使用，避免高峰期下载。
                                </div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faq3">
                                    B站下载的视频文件大小有限制吗？
                                </button>
                            </h2>
                            <div id="faq3" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    由于是在浏览器中合成视频，建议下载1GB以下的视频。较大的视频可能会导致浏览器内存不足或合成失败。
                                </div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faq4">
                                    B站视频解析失败怎么办？
                                </button>
                            </h2>
                            <div id="faq4" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    解析失败可能是因为：1. 链接格式不正确；2. 视频已被删除或设置为私有；3. 需要登录但未登录；4. B站API限流。建议检查链接格式，登录账号后重试。
                                </div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faq5">
                                    下载B站视频有版权问题吗？
                                </button>
                            </h2>
                            <div id="faq5" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    本工具仅用于个人学习和研究目的，请勿用于商业用途或侵犯他人版权。下载的视频请在24小时内删除，支持原创内容。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>


    <section id="desktop" class="py-12" style="background: var(--card-bg-solid);">
        <div class="container">
            <div class="text-center mb-8">
                <h2 class="display-4">下载B站视频桌面版</h2>
                <p class="lead text-muted">桌面版功能更强大，下载速度更快，支持更多格式</p>
            </div>
            
            <div class="row justify-content-center">
                <div class="col-md-10">

                    <div id="versionInfo" class="alert alert-info mb-6" style="display: none; border-radius: 0; background-color: rgba(0, 161, 214, 0.1); border-color: var(--primary); color: var(--primary);">
                        <strong>最新版本：</strong><span id="latestVersion"></span>
                    </div>
                    

                    <div class="mb-8">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <h3>稳定版</h3>
                            <button class="btn btn-outline" data-bs-toggle="modal" data-bs-target="#nodeSelectModal" style="border-radius: 0; border: 1px solid var(--primary); color: var(--primary); background-color: transparent;">
                                选择加速节点
                            </button>
                        </div>
                        <div class="row g-4" id="stableVersions">

                        </div>
                    </div>
                    

                    <div class="mb-8">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <h3>修复版</h3>
                            <button class="btn btn-outline" data-bs-toggle="modal" data-bs-target="#nodeSelectModal" style="border-radius: 0; border: 1px solid var(--primary); color: var(--primary); background-color: transparent;">
                                选择加速节点
                            </button>
                        </div>
                        <div class="row g-4" id="fixVersions">

                        </div>
                    </div>
                    

                    <div class="card mb-6" style="border-radius: 0;">
                        <div class="card-body">
                            <h3 class="card-title mb-4">其他下载链接</h3>
                            <div class="row g-4">
                                <div class="col-md-4">
                                    <a href="https://github.com/NANblogink/bilibilidownloadtool" target="_blank" class="d-block border p-4" style="border-radius: 0; text-align: center; text-decoration: none; color: var(--text-color); border-color: var(--border); background-color: var(--card-bg-solid);">
                                        <div class="mb-2" style="font-size: 1.5rem; color: var(--primary);">
                                            <i class="fab fa-github"></i>
                                        </div>
                                        <h5>GitHub 源码</h5>
                                    </a>
                                </div>
                                <div class="col-md-4">
                                    <a href="https://pan.quark.cn/s/1cb5afa995b6" target="_blank" class="d-block border p-4" style="border-radius: 0; text-align: center; text-decoration: none; color: var(--text-color); border-color: var(--border); background-color: var(--card-bg-solid); position: relative;">
                                        <div class="mb-2">
                                            <img src="https://image.quark.cn/s/uae/g/3o/broccoli/resource/202602/f6439020-13b4-11f1-9342-3944993de2f6.png" alt="夸克网盘" style="width: 40px; height: 40px; object-fit: contain;">
                                        </div>
                                        <h5>夸克网盘</h5>
                                        <div style="position: absolute; top: 10px; right: 10px; background-color: var(--danger); color: white; font-size: 12px; padding: 2px 8px; border-radius: 0;">
                                            实时更新
                                        </div>
                                    </a>
                                </div>
                                <div class="col-md-4">
                                    <a href="https://www.123912.com/s/WVrQvd-91J6H?pwd=wEGv#" target="_blank" class="d-block border p-4" style="border-radius: 0; text-align: center; text-decoration: none; color: var(--text-color); border-color: var(--border); background-color: var(--card-bg-solid); position: relative;">
                                        <div class="mb-2">
                                            <img src="https://statics.123pan.com/static/favicon.ico" alt="123网盘" style="width: 40px; height: 40px; object-fit: contain;">
                                        </div>
                                        <h5>123网盘</h5>
                                        <div style="position: absolute; top: 10px; right: 10px; background-color: var(--danger); color: white; font-size: 12px; padding: 2px 8px; border-radius: 0;">
                                            实时更新
                                        </div>
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>


    <section id="about" class="py-12" style="background: var(--card-bg-solid);">
        <div class="container">
            <div class="text-center mb-8">
                <h2 class="display-4">关于bilidown B站视频下载工具</h2>
                <p class="lead text-muted">致力于提供免费、优质的B站视频解析下载服务</p>
            </div>
            
            <div class="row">
                <div class="col-md-8 offset-md-2">
                    <p class="text-lg">
                        bilidown是一个免费、开源的B站视频在线解析下载工具，帮助用户方便地下载B站视频用于个人学习和研究，支持4K/1080P高清下载。
                    </p>
                    <p class="text-lg mt-4">
                        本工具使用先进的前端技术，在浏览器中直接合成视频，无需安装软件，所有操作本地完成，保护用户隐私安全。
                    </p>
                </div>
            </div>
        </div>
    </section>


    <div class="toast-container"></div>


    <div class="loading-overlay" id="loadingOverlay" style="display: none;">
        <div class="loading-content">
            <div class="spinner"></div>
            <div class="loading-text" id="loadingText">加载中...</div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                </div>
                <div class="progress-text" id="progressText">0%</div>
            </div>
            <div class="speed-eta-container" style="display: flex; justify-content: space-between; width: 100%; max-width: 400px; margin-top: 10px; font-size: 14px; color: #666;">
                <span id="speedText"></span>
                <span id="etaText"></span>
            </div>
            <button id="cancelDownloadBtn" class="btn btn-danger" style="margin-top: 15px; display: none;">
                <i class="bi bi-x-circle"></i> 取消下载
            </button>
        </div>
    </div>


    <div class="modal fade" id="nodeSelectModal" tabindex="-1" aria-labelledby="nodeSelectModalLabel" aria-hidden="true" style="border-radius: 0;">
        <div class="modal-dialog modal-dialog-centered" style="border-radius: 0;">
            <div class="modal-content" style="border-radius: 0; background-color: var(--card-bg-solid); border-color: var(--border); color: var(--text-color);">
                <div class="modal-header" style="border-radius: 0; border-bottom-color: var(--border); background-color: var(--card-bg-solid);">
                    <h5 class="modal-title" id="nodeSelectModalLabel" style="color: var(--text-color);">选择加速节点</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" style="border-radius: 0;"></button>
                </div>
                <div class="modal-body" style="background-color: var(--card-bg-solid);">
                    <div class="list-group" id="nodeList">
                        <button type="button" class="list-group-item list-group-item-action active" data-node="https://ghproxy.com/" style="border-radius: 0; background-color: var(--primary); border-color: var(--primary); color: white;">
                            <strong>ghproxy 主节点</strong>
                            <small class="d-block text-muted" style="color: rgba(255,255,255,0.8);">最稳定，推荐使用</small>
                        </button>
                        <button type="button" class="list-group-item list-group-item-action" data-node="https://gh.api.99988866.xyz/" style="border-radius: 0; background-color: var(--card-bg-solid); border-color: var(--border); color: var(--text-color);">
                            <strong>gh.api.99988866.xyz</strong>
                            <small class="d-block text-muted" style="color: var(--muted);">备用节点1</small>
                        </button>
                        <button type="button" class="list-group-item list-group-item-action" data-node="https://g.ioiox.com/" style="border-radius: 0; background-color: var(--card-bg-solid); border-color: var(--border); color: var(--text-color);">
                            <strong>g.ioiox.com</strong>
                            <small class="d-block text-muted" style="color: var(--muted);">备用节点2</small>
                        </button>
                        <button type="button" class="list-group-item list-group-item-action" data-node="https://ghproxy.net/" style="border-radius: 0; background-color: var(--card-bg-solid); border-color: var(--border); color: var(--text-color);">
                            <strong>ghproxy.net</strong>
                            <small class="d-block text-muted" style="color: var(--muted);">备用节点3</small>
                        </button>
                        <button type="button" class="list-group-item list-group-item-action" data-node="mirror" style="border-radius: 0; background-color: var(--card-bg-solid); border-color: var(--border); color: var(--text-color);">
                            <strong>镜像站直连</strong>
                            <small class="d-block text-muted" style="color: var(--muted);">使用镜像站直接下载</small>
                        </button>
                    </div>
                </div>
                <div class="modal-footer" style="display: flex; justify-content: space-between; align-items: center; border-top-color: var(--border); background-color: var(--card-bg-solid);">
                    <div class="form-check">
                        <input type="checkbox" class="form-check-input" id="setAsDefaultNode" style="border-radius: 0; border-color: var(--border);">
                        <label class="form-check-label" for="setAsDefaultNode" style="color: var(--text-color);">
                            设为默认节点
                        </label>
                    </div>
                    <div>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" style="border-radius: 0; min-width: 80px; padding: 6px 12px; background-color: var(--secondary); border-color: var(--secondary);">取消</button>
                        <button type="button" class="btn btn-primary" id="confirmNodeBtn" style="border-radius: 0; min-width: 80px; padding: 6px 12px; background-color: var(--primary); border-color: var(--primary);">确认</button>
                    </div>
                </div>
            </div>
        </div>
    </div>


    <div class="modal fade" id="encryptionModal" tabindex="-1" aria-labelledby="encryptionModalLabel" aria-hidden="true" style="border-radius: 0;">
        <div class="modal-dialog modal-dialog-centered" style="border-radius: 0;">
            <div class="modal-content" style="border-radius: 0;">
                <div class="modal-header" style="border-radius: 0; background-color: rgba(255, 243, 205, 0.1); border-bottom: 1px solid var(--border);">
                    <h5 class="modal-title" id="encryptionModalLabel" style="color: var(--warning);"><i class="fas fa-exclamation-triangle me-2"></i>加密视频提示</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" style="border-radius: 0;"></button>
                </div>
                <div class="modal-body" style="text-align: center; padding: 30px; background-color: var(--card-bg-solid);">
                    <div style="font-size: 48px; margin-bottom: 20px; color: var(--warning);"><i class="fas fa-lock"></i></div>
                    <h6 style="color: var(--danger); margin-bottom: 15px;">检测到加密视频</h6>
                    <p style="color: var(--warning); font-size: 14px; line-height: 1.8;">
                        当前视频采用B站DRM加密保护<br>
                        由于浏览器环境限制，无法在此解密<br>
                        请下载桌面版工具进行下载和解密
                    </p>
                    <div style="margin-top: 20px; padding: 15px; background-color: var(--card-bg-solid); border-radius: 0; border: 1px solid var(--border);">
                        <p style="margin: 0; font-size: 13px; color: var(--text-color);">
                            桌面版优势：<br>
                            ✓ 支持完整的视频解密功能<br>
                            ✓ 性能更好，支持更多格式<br>
                            ✓ 可以处理各种加密情况
                        </p>
                    </div>
                </div>
                <div class="modal-footer" style="justify-content: center; border-top: 1px solid var(--border); gap: 10px; background-color: var(--card-bg-solid);">
                    <a href="https://github.com/NANblogink/bilibilidownloadtool/releases/latest" target="_blank" class="btn btn-success" style="border-radius: 0; min-width: 120px; padding: 8px 16px;"><i class="fas fa-download me-2"></i>下载桌面版</a>
                    <button type="button" class="btn btn-primary" data-bs-dismiss="modal" style="border-radius: 0; min-width: 120px; padding: 8px 16px;">我知道了</button>
                </div>
            </div>
        </div>
    </div>


    <!-- 延迟加载非关键JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" defer></script>

    <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js" defer></script>

    <script src="https://cdn.jsdelivr.net/npm/qrcode/build/qrcode.min.js" defer></script>

    <!-- 延迟加载FFmpeg.js，这是最大的文件 -->
    <script src="js/ffmpeg.js" defer></script>

    <script>
        // 全局变量
        let ffmpeg = null;
        let isFFmpegLoaded = false;
        let currentVideoInfo = null;
        let selectedQuality = 80;
        let currentCookies = '';
        let episodeQualities = {};
        let qualityOptions = [];
        let username = '';
        
        let selectedNode = localStorage.getItem('github_accelerate_node') || 'https://ghproxy.com/';
        let encryptionModalShown = false; // 标记加密提示模态框是否已显示
        

        // ===== 工具函数 =====
        function showToast(message, type) {
            type = type || 'success';
            const colors = {
                success: 'var(--success)',
                error: 'var(--danger)',
                danger: 'var(--danger)',
                warning: 'var(--warning)',
                info: 'var(--primary)'
            };
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 10000;
                background: ${colors[type] || colors.success};
                color: white;
                padding: 12px 20px;
                border-radius: 6px;
                margin-bottom: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                min-width: 250px;
                font-size: 14px;
                opacity: 0;
                transform: translateX(100%);
                transition: all 0.3s ease;
            `;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '1';
                toast.style.transform = 'translateX(0)';
            }, 10);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        function showLoading(text) {
            let overlay = document.getElementById('loadingOverlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'loadingOverlay';
                overlay.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 9999;
                    flex-direction: column;
                    gap: 16px;
                `;
                overlay.innerHTML = `
                    <div style="width: 48px; height: 48px; border: 3px solid rgba(255,255,255,0.2); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                    <div id="loadingText" style="color: white; font-size: 16px;">加载中...</div>
                `;
                const style = document.createElement('style');
                style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
                document.head.appendChild(style);
                document.body.appendChild(overlay);
            }
            document.getElementById('loadingText').textContent = text || '加载中...';
            overlay.style.display = 'flex';
        }

        function hideLoading() {
            const overlay = document.getElementById('loadingOverlay');
            if (overlay) overlay.style.display = 'none';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.appendChild(document.createTextNode(text || ''));
            return div.innerHTML;
        }

        // ===== Tab 切换 =====
        function switchTab(tabName) {
            // 切换按钮状态
            document.querySelectorAll('.tool-tab').forEach(btn => {
                btn.classList.remove('active');
            });
            const activeBtn = document.querySelector(`.tool-tab[data-tab="${tabName}"]`);
            if (activeBtn) activeBtn.classList.add('active');

            // 切换内容
            document.querySelectorAll('.tool-tab-content').forEach(content => {
                content.style.display = 'none';
            });
            const tabContent = document.getElementById(`tab-${tabName}`);
            if (tabContent) tabContent.style.display = 'block';
        }

        function proxyImageUrl(url) {
            if (!url) return '';
            if (url.startsWith('data:') || url.startsWith('blob:')) return url;
            return 'api.php?action=proxy_image&url=' + encodeURIComponent(url);
        }

        // 视频流代理 - 支持大文件流式传输和Range请求
        function proxyVideoUrl(url) {
            if (!url) return '';
            if (url.startsWith('data:') || url.startsWith('blob:')) return url;
            return 'api.php?action=proxy_video&url=' + encodeURIComponent(url);
        }

        // 视频直链重定向 - 302重定向到B站CDN，不阻塞服务器
        function redirectVideoUrl(url) {
            if (!url) return '';
            if (url.startsWith('data:') || url.startsWith('blob:')) return url;
            return 'api.php?action=redirect_video&url=' + encodeURIComponent(url);
        }

        // ===== 视频解析 =====
        async function parseVideo() {
            const urlInput = document.getElementById('videoUrl');
            const url = urlInput.value.trim();
            if (!url) {
                showToast('请输入视频链接', 'warning');
                return;
            }

            showLoading('正在解析视频...');
            try {
                const formData = new FormData();
                formData.append('action', 'parse');
                formData.append('url', url);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '解析失败');

                const data = res.data;
                currentVideoInfo = data;
                displayVideoInfo(data);
                hideLoading();
                showToast('解析成功', 'success');
            } catch (err) {
                hideLoading();
                console.error('视频解析失败:', err);
                showToast('解析失败: ' + err.message, 'danger');
            }
        }

        async function parseVideoLink(bvid) {
            const url = 'https://www.bilibili.com/video/' + bvid;
            document.getElementById('videoUrl').value = url;
            switchTab('video');
            await parseVideo();
        }

        function displayVideoInfo(data) {
            // 先找到视频结果区域，如果没有就创建
            let resultSection = document.getElementById('videoResultSection');
            if (!resultSection) {
                resultSection = document.createElement('div');
                resultSection.id = 'videoResultSection';
                resultSection.className = 'mt-6';
                // 插入到输入区域后面
                const tabVideo = document.getElementById('tab-video');
                const inputSection = tabVideo.querySelector('.input-section');
                if (inputSection && inputSection.parentNode) {
                    inputSection.parentNode.insertBefore(resultSection, inputSection.nextSibling);
                } else {
                    tabVideo.appendChild(resultSection);
                }
            }

            const title = data.title || data.name || '未知标题';
            const cover = data.cover || data.pic || '';
            const desc = data.desc || data.description || '';
            const duration = data.duration || '';
            const ownerName = data.author || (data.owner && data.owner.name ? data.owner.name : '') || (data.up && data.up.name ? data.up.name : '');
            const episodes = data.collection || data.episodes || data.pages || [data];
            const qualities = data.qualities || data.quality_list || data.accept_quality || [];
            // video_urls 可能是字典 {80: "url"} 或数组 ["url"] 或 [{url: "url"}]
            // 保留原始字典格式以便按清晰度查找
            let videoUrlMap = {};
            if (data.video_urls && typeof data.video_urls === 'object' && !Array.isArray(data.video_urls)) {
                videoUrlMap = data.video_urls;
            } else if (Array.isArray(data.video_urls)) {
                data.video_urls.forEach((u, i) => {
                    if (typeof u === 'string') videoUrlMap[i] = u;
                    else if (u && u.url) videoUrlMap[u.qn || i] = u.url;
                });
            }
            currentVideoUrlMap = videoUrlMap;
            let videoUrls = Object.values(videoUrlMap);
            const audioUrl = data.audio_url || '';
            currentAudioUrl = audioUrl;
            const flvQns = data.flv_qns || [];
            currentFlvQns = flvQns;

            let html = `
                <div class="audio-info-card" style="margin-bottom: 20px;">
                    ${cover ? `<img src="${proxyImageUrl(cover)}" alt="${escapeHtml(title)}" onerror="this.style.display='none'">` : ''}
                    <div class="info">
                        <h4>${escapeHtml(title)}</h4>
                        <div class="meta">
                            ${ownerName ? `<div><i class="fas fa-user"></i> ${escapeHtml(ownerName)}</div>` : ''}
                            ${duration ? `<div><i class="fas fa-clock"></i> ${escapeHtml(String(duration))}</div>` : ''}
                            ${episodes.length > 1 ? `<div><i class="fas fa-list"></i> 共 ${episodes.length} 集</div>` : ''}
                        </div>
                        ${desc ? `<p style="margin-top: 8px; color: var(--text-secondary); font-size: 14px;">${escapeHtml(String(desc).substring(0, 100))}${desc.length > 100 ? '...' : ''}</p>` : ''}
                    </div>
                </div>
            `;

            // 清晰度选择（放在预览前面）
            if (qualities.length > 0) {
                html += `
                    <div class="input-section" style="margin-bottom: 12px;">
                        <label>选择清晰度</label>
                        <select class="form-control" id="videoQuality" onchange="switchVideoQuality()">
                            ${qualities.map(q => {
                                const qn = Array.isArray(q) ? q[0] : (q.qn || q.id || '');
                                const desc = Array.isArray(q) ? q[1] : (q.desc || q.quality || q.name || '');
                                return `<option value="${qn}">${escapeHtml(String(desc))}</option>`;
                            }).join('')}
                        </select>
                    </div>
                `;
            }

            // 视频预览（用解析出来的直链播放）
            const defaultQn = qualities.length > 0 ? (Array.isArray(qualities[0]) ? qualities[0][0] : (qualities[0].qn || qualities[0].id || '')) : '';
            const previewUrl = (defaultQn && videoUrlMap[defaultQn]) ? videoUrlMap[defaultQn] : (videoUrls.length > 0 ? videoUrls[0] : '');
            if (previewUrl) {
                html += `
                    <div class="input-section" style="margin-bottom: 20px;">
                        <label><i class="fas fa-play-circle"></i> 视频预览</label>
                        <div style="border-radius: 8px; overflow: hidden; border: 1px solid var(--border); background: #000; position: relative;">
                            <video id="videoPreviewPlayer" controls style="width: 100%; max-height: 450px; display: block;"></video>
                            <div id="videoPreviewLoading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white; text-align: center; pointer-events: none;">
                                <i class="fas fa-spinner fa-spin" style="font-size: 24px;"></i>
                                <div style="margin-top: 8px; font-size: 13px;">正在加载视频...</div>
                            </div>
                        </div>
                    </div>
                `;
            }


            // 视频列表
            if (episodes.length > 0) {
                html += `
                    <div class="input-section">
                        <label>视频列表 (${episodes.length})</label>
                        <div style="max-height: 300px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px; padding: 8px;">
                            ${episodes.map((ep, idx) => `
                                <div style="display: flex; align-items: center; padding: 8px; border-bottom: 1px solid var(--border); cursor: pointer;"
                                     onmouseover="this.style.background='rgba(0,161,214,0.05)'"
                                     onmouseout="this.style.background='transparent'"
                                     onclick="selectEpisode(${idx})">
                                    <input type="checkbox" class="episode-checkbox" data-idx="${idx}" style="margin-right: 10px;" ${episodes.length === 1 ? 'checked' : ''}>
                                    <span style="flex: 1;">${idx + 1}. ${escapeHtml(ep.title || ep.part || ep.ep_title || `第${idx + 1}集`)}</span>
                                    ${ep.duration_str ? `<span style="color: var(--text-secondary); font-size: 12px;">${escapeHtml(ep.duration_str)}</span>` : (ep.duration ? `<span style="color: var(--text-secondary); font-size: 12px;">${escapeHtml(String(ep.duration))}</span>` : '')}
                                </div>
                            `).join('')}
                        </div>
                        <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-primary" id="videoDownloadBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-download"></i> 下载视频
                            </button>
                            <button class="btn btn-outline" id="videoCopyUrlBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-copy"></i> 复制直链
                            </button>
                        </div>
                    </div>
                `;
            }

            resultSection.innerHTML = html;

            // 异步加载视频预览（fetch+blob方式，避免PHP单线程Range请求阻塞）
            if (previewUrl) {
                loadVideoPreview(previewUrl);
            }

            // 绑定下载按钮
            const downloadBtn = document.getElementById('videoDownloadBtn');
            if (downloadBtn) {
                downloadBtn.addEventListener('click', async function() {
                    // 获取用户选择的清晰度
                    const qualitySelect = document.getElementById('videoQuality');
                    const selectedQn = qualitySelect ? qualitySelect.value : '';
                    // 按清晰度查找URL，找不到就用第一个
                    let downloadUrl = '';
                    if (selectedQn && currentVideoUrlMap[selectedQn]) {
                        downloadUrl = currentVideoUrlMap[selectedQn];
                    } else if (videoUrls.length > 0) {
                        downloadUrl = videoUrls[0];
                    }
                    if (!downloadUrl) {
                        showToast('没有可用的下载地址，可能需要登录', 'warning');
                        return;
                    }
                    // 构造文件名
                    const safeTitle = title.replace(/[\\/:*?"<>|]/g, '_').substring(0, 80);
                    const fileName = `${safeTitle}.mp4`;
                    downloadBtn.disabled = true;
                    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 下载中...';
                    try {
                        const selectedQnNum = parseInt(selectedQn);
                        const isFlvFormat = currentFlvQns.includes(selectedQnNum);
                        
                        if (isFlvFormat) {
                            // FLV/MP4格式（音视频一体），直接下载
                            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 下载中...';
                            const proxyUrl = proxyVideoUrl(downloadUrl);
                            const resp = await fetch(proxyUrl);
                            if (!resp.ok) throw new Error('下载失败: ' + resp.status);
                            const blob = await resp.blob();
                            const blobUrl = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = blobUrl;
                            a.download = fileName;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(blobUrl);
                            showToast('下载完成: ' + fileName, 'success');
                        } else if (currentAudioUrl && isFFmpegLoaded && ffmpeg) {
                            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 下载视频中...';
                            // 同时下载视频和音频流
                            const [videoResp, audioResp] = await Promise.all([
                                fetch(proxyVideoUrl(downloadUrl)),
                                fetch(proxyVideoUrl(currentAudioUrl))
                            ]);
                            if (!videoResp.ok) throw new Error('视频下载失败: ' + videoResp.status);
                            if (!audioResp.ok) throw new Error('音频下载失败: ' + audioResp.status);
                            const videoBlob = await videoResp.blob();
                            const audioBlob = await audioResp.blob();
                            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 合并音视频中...';
                            // 用ffmpeg.wasm合并
                            const videoFile = await videoBlob.arrayBuffer();
                            const audioFile = await audioBlob.arrayBuffer();
                            await ffmpeg.writeFile('video.m4s', new Uint8Array(videoFile));
                            await ffmpeg.writeFile('audio.m4s', new Uint8Array(audioFile));
                            await ffmpeg.exec(['-i', 'video.m4s', '-i', 'audio.m4s', '-c', 'copy', 'output.mp4']);
                            const data = await ffmpeg.readFile('output.mp4');
                            // 创建下载链接
                            const blobUrl = URL.createObjectURL(new Blob([data.buffer], { type: 'video/mp4' }));
                            const a = document.createElement('a');
                            a.href = blobUrl;
                            a.download = fileName;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(blobUrl);
                            // 清理临时文件
                            try { await ffmpeg.deleteFile('video.m4s'); } catch(e) {}
                            try { await ffmpeg.deleteFile('audio.m4s'); } catch(e) {}
                            try { await ffmpeg.deleteFile('output.mp4'); } catch(e) {}
                            showToast('下载完成（已合并音视频）: ' + fileName, 'success');
                        } else {
                            // 没有音频流或ffmpeg未加载，只下载视频流
                            const proxyUrl = proxyVideoUrl(downloadUrl);
                            const resp = await fetch(proxyUrl);
                            if (!resp.ok) throw new Error('下载失败: ' + resp.status);
                            const blob = await resp.blob();
                            const blobUrl = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = blobUrl;
                            a.download = fileName;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(blobUrl);
                            showToast('下载完成' + (currentAudioUrl ? '（仅视频，无音频）' : '') + ': ' + fileName, 'success');
                        }
                    } catch (e) {
                        showToast('下载失败: ' + e.message + '，正在尝试直接下载...', 'warning');
                        try {
                            const a = document.createElement('a');
                            a.href = proxyVideoUrl(downloadUrl);
                            a.download = fileName;
                            a.target = '_self';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        } catch(e2) {
                            window.open(proxyVideoUrl(downloadUrl), '_blank');
                        }
                    } finally {
                        downloadBtn.disabled = false;
                        downloadBtn.innerHTML = '<i class="fas fa-download"></i> 下载视频';
                    }
                });
            }

            // 绑定复制直链按钮
            const copyBtn = document.getElementById('videoCopyUrlBtn');
            if (copyBtn) {
                copyBtn.addEventListener('click', function() {
                    const qualitySelect = document.getElementById('videoQuality');
                    const selectedQn = qualitySelect ? qualitySelect.value : '';
                    let url = '';
                    if (selectedQn && currentVideoUrlMap[selectedQn]) {
                        url = currentVideoUrlMap[selectedQn];
                    } else if (videoUrls.length > 0) {
                        url = videoUrls[0];
                    }
                    if (!url) {
                        showToast('没有可用的直链', 'warning');
                        return;
                    }
                    navigator.clipboard.writeText(url).then(() => showToast('已复制直链到剪贴板', 'success'));
                });
            }
        }

        function formatDuration(seconds) {
            seconds = parseInt(seconds) || 0;
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = seconds % 60;
            if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            return `${m}:${String(s).padStart(2, '0')}`;
        }

        function selectEpisode(idx) {
            const checkbox = document.querySelector(`.episode-checkbox[data-idx="${idx}"]`);
            if (checkbox) checkbox.checked = !checkbox.checked;
        }

        // 切换清晰度时切换预览视频源
        let currentVideoUrlMap = {};
        let currentVideoBlobUrl = '';
        let currentAudioUrl = '';
        let currentFlvQns = [];
        // 用fetch+blob加载视频预览，避免PHP单线程服务器的Range请求阻塞
        function loadVideoPreview(url) {
            const player = document.getElementById('videoPreviewPlayer');
            const loadingHint = document.getElementById('videoPreviewLoading');
            if (!player) return;
            // 显示加载提示
            if (loadingHint) {
                loadingHint.style.display = 'block';
                loadingHint.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size: 24px;"></i><div style="margin-top: 8px; font-size: 13px;">正在加载视频...</div>';
            }
            // 释放旧的blob URL
            if (currentVideoBlobUrl) {
                URL.revokeObjectURL(currentVideoBlobUrl);
                currentVideoBlobUrl = '';
            }
            fetch(proxyVideoUrl(url)).then(resp => {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.blob();
            }).then(blob => {
                currentVideoBlobUrl = URL.createObjectURL(blob);
                player.src = currentVideoBlobUrl;
                player.play().catch(() => {});
                if (loadingHint) loadingHint.style.display = 'none';
            }).catch(e => {
                if (loadingHint) {
                    loadingHint.innerHTML = '<i class="fas fa-exclamation-triangle" style="font-size: 24px; color: #ff4757;"></i><div style="margin-top: 8px; font-size: 13px;">加载失败: ' + escapeHtml(e.message) + '</div>';
                }
            });
        }
        function switchVideoQuality() {
            const select = document.getElementById('videoQuality');
            if (!select) return;
            const qn = select.value;
            const url = currentVideoUrlMap[qn] || Object.values(currentVideoUrlMap)[0] || '';
            if (!url) return;
            loadVideoPreview(url);
        }

        // ===== 直播解析 =====
        async function parseLive() {
            const urlInput = document.getElementById('liveRoomId');
            let val = urlInput.value.trim();
            if (!val) {
                showToast('请输入直播间链接或房间号', 'warning');
                return;
            }

            // 从链接中提取房间号
            let roomId = val;
            const match = val.match(/live\.bilibili\.com\/(\d+)/);
            if (match) {
                roomId = match[1];
            } else if (/^\d+$/.test(val)) {
                roomId = val;
            } else {
                // 尝试提取末尾的数字
                const numMatch = val.match(/(\d+)$/);
                if (numMatch) {
                    roomId = numMatch[1];
                } else {
                    showToast('无法识别直播间号，请输入数字房间号或直播链接', 'warning');
                    return;
                }
            }

            showLoading('正在解析直播间...');
            try {
                // 1. 获取直播间基本信息
                const formData = new FormData();
                formData.append('action', 'live_info');
                formData.append('room_id', roomId);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '解析失败');

                const data = res.data;

                // 2. 获取直播流信息（清晰度列表、流地址）
                if (data.live_status === 1) { // 仅直播中才获取流
                    const streamFormData = new FormData();
                    streamFormData.append('action', 'live_stream');
                    streamFormData.append('room_id', roomId);
                    if (currentCookies) streamFormData.append('cookie', currentCookies);

                    const streamResp = await fetch('api.php', { method: 'POST', body: streamFormData });
                    const streamRes = await streamResp.json();

                    if (streamRes.success && streamRes.data) {
                        // 合并流数据到 info 数据中
                        data.quality_list = streamRes.data.quality_list || [];
                        data.stream_url = streamRes.data.stream_url || '';
                        data.durl = streamRes.data.durl || [];
                        data.accept_quality = streamRes.data.accept_quality || [];
                    }
                } else {
                    data.quality_list = [];
                    data.stream_url = '';
                }

                displayLiveInfo(data);
                hideLoading();
                showToast('解析成功', 'success');
            } catch (err) {
                hideLoading();
                console.error('直播解析失败:', err);
                showToast('解析失败: ' + err.message, 'danger');
            }
        }

        function displayLiveInfo(data) {
            let resultSection = document.getElementById('liveResultSection');
            if (!resultSection) {
                resultSection = document.createElement('div');
                resultSection.id = 'liveResultSection';
                resultSection.className = 'mt-6';
                const tabLive = document.getElementById('tab-live');
                const inputSection = tabLive.querySelector('.input-section');
                if (inputSection && inputSection.parentNode) {
                    inputSection.parentNode.insertBefore(resultSection, inputSection.nextSibling);
                } else {
                    tabLive.appendChild(resultSection);
                }
            }

            const title = data.title || '直播间';
            const cover = data.cover || data.cover_from_user || '';
            const uname = data.uname || data.name || '';
            const status = data.live_status === 1 ? '直播中' : '未开播';
            const statusColor = data.live_status === 1 ? 'var(--success)' : 'var(--danger)';
            const qualityList = data.quality_list || data.quality || [];
            const currentQuality = data.current_quality || (qualityList[0] ? qualityList[0].qn : 0);
            const streamUrl = data.stream_url || data.url || '';

            let html = `
                <div class="audio-info-card" style="margin-bottom: 20px;">
                    ${cover ? `<img src="${cover}" alt="${escapeHtml(title)}" onerror="this.style.display='none'">` : ''}
                    <div class="info">
                        <h4>${escapeHtml(title)}</h4>
                        <div class="meta">
                            ${uname ? `<div><i class="fas fa-user"></i> ${escapeHtml(uname)}</div>` : ''}
                            <div><i class="fas fa-circle" style="color: ${statusColor}; font-size: 8px;"></i> ${status}</div>
                        </div>
                    </div>
                </div>
            `;

            if (qualityList.length > 0) {
                html += `
                    <div class="input-section">
                        <label>选择清晰度</label>
                        <select class="form-control" id="liveQuality">
                            ${qualityList.map(q => `
                                <option value="${q.qn || q.id || ''}" ${(q.qn || q.id) == currentQuality ? 'selected' : ''}>${q.desc || q.name || q.quality || ''}</option>
                            `).join('')}
                        </select>
                    </div>
                `;
            }

            if (streamUrl) {
                html += `
                    <div class="input-section">
                        <label>直播流地址</label>
                        <input type="text" class="form-control" id="liveStreamUrl" value="${escapeHtml(streamUrl)}" readonly>
                        <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-primary" id="livePlayBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-play"></i> 在线播放
                            </button>
                            <button class="btn btn-outline" id="liveCopyBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-copy"></i> 复制链接
                            </button>
                        </div>
                    </div>
                `;
            }

            resultSection.innerHTML = html;

            // 绑定事件
            const copyBtn = document.getElementById('liveCopyBtn');
            if (copyBtn) {
                copyBtn.addEventListener('click', function() {
                    const url = document.getElementById('liveStreamUrl').value;
                    if (url) {
                        navigator.clipboard.writeText(url).then(() => showToast('已复制到剪贴板', 'success'));
                    }
                });
            }

            const playBtn = document.getElementById('livePlayBtn');
            if (playBtn) {
                playBtn.addEventListener('click', function() {
                    const url = document.getElementById('liveStreamUrl').value;
                    if (url) {
                        showToast('即将打开直播流...', 'info');
                        window.open(url, '_blank');
                    }
                });
            }
        }

        // ===== 音频解析 =====
        async function parseAudio() {
            const auIdInput = document.getElementById('audioId');
            const auId = auIdInput.value.trim();
            if (!auId) {
                showToast('请输入音频ID或链接', 'warning');
                return;
            }

            showLoading('正在解析音频...');
            try {
                const formData = new FormData();
                formData.append('action', 'audio_info');
                formData.append('au_id', auId);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '解析失败');

                const data = res.data;
                displayAudioInfo(data);
                hideLoading();
                showToast('解析成功', 'success');
            } catch (err) {
                hideLoading();
                console.error('音频解析失败:', err);
                showToast('解析失败: ' + err.message, 'danger');
            }
        }

        function displayAudioInfo(data) {
            let resultSection = document.getElementById('audioResultSection');
            if (!resultSection) {
                resultSection = document.createElement('div');
                resultSection.id = 'audioResultSection';
                resultSection.className = 'mt-6';
                const tabAudio = document.getElementById('tab-audio');
                const inputSection = tabAudio.querySelector('.input-section');
                if (inputSection && inputSection.parentNode) {
                    inputSection.parentNode.insertBefore(resultSection, inputSection.nextSibling);
                } else {
                    tabAudio.appendChild(resultSection);
                }
            }

            const title = data.title || data.name || '未知音频';
            const cover = data.cover || data.pic || data.album_pic || '';
            const artist = data.artist || data.uname || '';
            const duration = data.duration || 0;
            const streamUrl = data.stream_url || data.url || data.audio_url || '';
            const quality = data.quality || '';

            let html = `
                <div class="audio-info-card" style="margin-bottom: 20px;">
                    ${cover ? `<img src="${cover}" alt="${escapeHtml(title)}" onerror="this.style.display='none'">` : ''}
                    <div class="info">
                        <h4>${escapeHtml(title)}</h4>
                        <div class="meta">
                            ${artist ? `<div><i class="fas fa-user"></i> ${escapeHtml(artist)}</div>` : ''}
                            ${duration ? `<div><i class="fas fa-clock"></i> ${formatDuration(duration)}</div>` : ''}
                            ${quality ? `<div><span class="badge-tag badge-block">${escapeHtml(quality)}</span></div>` : ''}
                        </div>
                    </div>
                </div>
            `;

            if (streamUrl) {
                html += `
                    <div class="input-section">
                        <label>音频下载</label>
                        <input type="text" class="form-control" id="audioStreamUrl" value="${escapeHtml(streamUrl)}" readonly>
                        <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <button class="btn btn-primary" id="audioDownloadBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-download"></i> 下载音频
                            </button>
                            <button class="btn btn-outline" id="audioCopyBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-copy"></i> 复制链接
                            </button>
                            <button class="btn btn-outline" id="audioPlayBtn" style="padding: 8px 16px; border-radius: 0;">
                                <i class="fas fa-play"></i> 在线播放
                            </button>
                        </div>
                    </div>
                `;
            }

            resultSection.innerHTML = html;

            // 绑定事件
            const copyBtn = document.getElementById('audioCopyBtn');
            if (copyBtn) {
                copyBtn.addEventListener('click', function() {
                    const url = document.getElementById('audioStreamUrl').value;
                    if (url) {
                        navigator.clipboard.writeText(url).then(() => showToast('已复制到剪贴板', 'success'));
                    }
                });
            }

            const downloadBtn = document.getElementById('audioDownloadBtn');
            if (downloadBtn) {
                downloadBtn.addEventListener('click', function() {
                    const url = document.getElementById('audioStreamUrl').value;
                    if (url) window.open(url, '_blank');
                });
            }

            const playBtn = document.getElementById('audioPlayBtn');
            if (playBtn) {
                playBtn.addEventListener('click', function() {
                    const url = document.getElementById('audioStreamUrl').value;
                    if (url) {
                        showToast('即将播放音频...', 'info');
                        window.open(url, '_blank');
                    }
                });
            }
        }

        // ===== 初始化 =====
        function init() {
            bindEvents();
            loadSavedCookie();
            checkFFmpegLoad();
            initNodeSelection();
            checkLatestVersion();

            // 默认显示视频Tab
            switchTab('video');

            // 监听Tab切换
            document.querySelectorAll('.tool-tab').forEach(btn => {
                btn.addEventListener('click', function() {
                    const tab = this.getAttribute('data-tab');
                    switchTab(tab);
                });
            });

            console.log('页面加载完成');
        }

        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', init);

        // 检查GitHub最新版本
        async function checkLatestVersion() {
            const cacheKey = 'github_release_cache';
            const cacheData = localStorage.getItem(cacheKey);
            const now = new Date().getTime();
            
            // 检查缓存是否存在且未过期（24小时）
            if (cacheData) {
                const { data, timestamp } = JSON.parse(cacheData);
                if (now - timestamp < 24 * 60 * 60 * 1000) {
                    // 缓存有效，使用缓存数据
                    updateDownloadLinks(data);
                    return;
                }
            }
            
            // 缓存过期或不存在，需要刷新
            try {
                const response = await fetch('https://api.github.com/repos/NANblogink/bilibilidownloadtool/releases/latest');
                if (!response.ok) {
                    if (response.status === 403) {
                        throw new Error('GitHub API 速率限制，请稍后再试');
                    }
                    throw new Error('API 请求失败');
                }
                
                const data = await response.json();
                const latestVersion = data.tag_name;
                const assets = data.assets || [];
                
                // 保存到缓存
                localStorage.setItem(cacheKey, JSON.stringify({
                    data: {
                        version: latestVersion,
                        assets: assets
                    },
                    timestamp: now
                }));
                
                // 更新下载链接
                updateDownloadLinks({ version: latestVersion, assets: assets });
            } catch (error) {
                console.error('检查版本失败:', error);
                // 如果API调用失败，使用默认版本数据
                if (!cacheData) {
                    // 没有缓存，使用默认数据
                    const defaultData = {
                        version: 'V1.9',
                        assets: [
                            {
                                name: 'V1.9.2026.4.18.exe',
                                size: 213 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.9.2026.4.18.exe',
                                created_at: '2026-04-18T00:00:00Z'
                            },
                            {
                                name: 'V1.9.exe',
                                size: 213 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.9.exe',
                                created_at: '2026-04-12T00:00:00Z'
                            },
                            {
                                name: 'V1.8.exe',
                                size: 213 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.8.exe',
                                created_at: '2026-04-01T00:00:00Z'
                            },
                            {
                                name: 'V1.6.exe',
                                size: 210 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.6.exe',
                                created_at: '2026-03-15T00:00:00Z'
                            },
                            {
                                name: 'V1.5fix.exe',
                                size: 136 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.5fix.exe',
                                created_at: '2026-03-08T00:00:00Z'
                            },
                            {
                                name: 'V1.3.exe',
                                size: 151 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.3.exe',
                                created_at: '2026-02-27T00:00:00Z'
                            },
                            {
                                name: 'V1.9.fix.exe',
                                size: 213 * 1024 * 1024,
                                browser_download_url: 'https://github.com/NANblogink/bilibilidownloadtool/releases/download/windows/V1.9.fix.exe',
                                created_at: '2026-04-16T00:00:00Z'
                            }
                        ]
                    };
                    updateDownloadLinks(defaultData);
                }
            }
        }
        
        // 更新下载链接
        function updateDownloadLinks(data) {
            if (!data) return;
            
            const { version, assets } = data;
            
            // 显示版本信息
            if (version) {
                document.getElementById('latestVersion').textContent = version;
                document.getElementById('versionInfo').style.display = 'block';
            }
            
            // 分类版本
            const stableVersions = [];
            const fixVersions = [];
            
            if (assets && assets.length > 0) {
                assets.forEach(asset => {
                    if (asset.name.endsWith('.exe')) {
                        const assetInfo = {
                            name: asset.name,
                            size: formatFileSize(asset.size || (213 * 1024 * 1024)),
                            url: asset.browser_download_url || asset.url,
                            created_at: asset.created_at
                        };
                        
                        if (asset.name.includes('fix')) {
                            fixVersions.push(assetInfo);
                        } else {
                            stableVersions.push(assetInfo);
                        }
                    }
                });
                
                // 按日期排序（最新的在前）
                stableVersions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                fixVersions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                
                // 渲染版本列表
                renderVersionList('stableVersions', stableVersions);
                renderVersionList('fixVersions', fixVersions);
            }
        }
        
        // 渲染版本列表
        function renderVersionList(containerId, versions) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            if (versions.length === 0) {
                container.textContent = '暂无版本';
            container.className = 'text-muted text-center';
                return;
            }
            
            container.innerHTML = '';
            
            versions.forEach(version => {
                const card = document.createElement('div');
                card.className = 'col-md-4';
                
                const cardContent = document.createElement('div');
                cardContent.className = 'border p-4';
                cardContent.style.borderRadius = '0';
                cardContent.style.backgroundColor = 'var(--card-bg)';
                cardContent.style.marginBottom = '20px';
                cardContent.style.borderColor = 'var(--border)';
                cardContent.style.color = 'var(--text-color)';
                
                const h4 = document.createElement('h4');
                h4.style.color = 'var(--text-color)';
                h4.textContent = version.name;
                cardContent.appendChild(h4);
                
                const sizeP = document.createElement('p');
                sizeP.style.color = 'var(--muted)';
                sizeP.textContent = '大小: ' + version.size;
                cardContent.appendChild(sizeP);
                
                const dateP = document.createElement('p');
                dateP.style.color = 'var(--muted)';
                dateP.textContent = '日期: ' + new Date(version.created_at).toLocaleDateString();
                cardContent.appendChild(dateP);
                
                const div = document.createElement('div');
                div.className = 'mt-3';
                div.style.display = 'flex';
                div.style.gap = '10px';
                
                const directLink = document.createElement('a');
                directLink.href = version.url;
                directLink.target = '_blank';
                directLink.className = 'btn btn-primary';
                directLink.style.borderRadius = '0';
                directLink.style.flex = '1';
                directLink.style.textAlign = 'center';
                directLink.style.padding = '8px 0';
                directLink.style.backgroundColor = 'var(--primary)';
                directLink.style.borderColor = 'var(--primary)';
                directLink.style.color = 'white';
                directLink.textContent = '直接下载';
                div.appendChild(directLink);
                
                const accelerateBtn = document.createElement('button');
                accelerateBtn.className = 'btn btn-outline';
                accelerateBtn.style.borderRadius = '0';
                accelerateBtn.style.flex = '1';
                accelerateBtn.style.textAlign = 'center';
                accelerateBtn.style.padding = '8px 0';
                accelerateBtn.style.border = '1px solid var(--primary)';
                accelerateBtn.style.color = 'var(--primary)';
                accelerateBtn.style.backgroundColor = 'transparent';
                accelerateBtn.textContent = '加速下载';
                accelerateBtn.onclick = function() {
                    showNodeSelector(version.url, version.name);
                };
                div.appendChild(accelerateBtn);
                
                cardContent.appendChild(div);
                card.appendChild(cardContent);
                container.appendChild(card);
            });
        }
        
        // 格式化文件大小
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        // 显示节点选择器
        let pendingDownloadUrl = '';
        let pendingDownloadName = '';
        
        function showNodeSelector(url, name) {
            pendingDownloadUrl = url;
            pendingDownloadName = name;
            const modal = new bootstrap.Modal(document.getElementById('nodeSelectModal'));
            modal.show();
        }
        
        function showEncryptionModal() {
            const modal = new bootstrap.Modal(document.getElementById('encryptionModal'));
            modal.show();
            
            // 监听模态框关闭事件，重置标志
            const encryptionModal = document.getElementById('encryptionModal');
            encryptionModal.addEventListener('hidden.bs.modal', function () {
                encryptionModalShown = false;
            });
        }
        
        // 修改确认按钮逻辑
        function initNodeSelection() {
            const nodeModal = document.getElementById('nodeSelectModal');
            const confirmBtn = document.getElementById('confirmNodeBtn');
            const nodeList = document.getElementById('nodeList');
            
            // 更新选中状态
            const updateActiveState = () => {
                const buttons = nodeList.querySelectorAll('.list-group-item');
                buttons.forEach(btn => {
                    if (btn.dataset.node === selectedNode) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            };
            
            // 点击节点选项
            nodeList.addEventListener('click', (e) => {
                const btn = e.target.closest('.list-group-item');
                if (btn) {
                    const buttons = nodeList.querySelectorAll('.list-group-item');
                    buttons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                }
            });
            
            // 确认选择
            confirmBtn.addEventListener('click', () => {
                const activeBtn = nodeList.querySelector('.list-group-item.active');
                const setAsDefault = document.getElementById('setAsDefaultNode').checked;
                
                if (activeBtn) {
                    const selectedValue = activeBtn.dataset.node;
                    
                    // 如果勾选了"设为默认"，保存节点选择
                    if (setAsDefault) {
                        localStorage.setItem('github_accelerate_node', selectedValue);
                    }
                    
                    // 如果有待下载的URL，直接跳转
                    if (pendingDownloadUrl) {
                        let finalUrl;
                        if (selectedValue === 'mirror') {
                            finalUrl = pendingDownloadUrl.replace('https://github.com', 'https://github.com.cnpmjs.org');
                        } else {
                            finalUrl = selectedValue + pendingDownloadUrl;
                        }
                        window.open(finalUrl, '_blank');
                        pendingDownloadUrl = '';
                        pendingDownloadName = '';
                    } else {
                        // 否则重新渲染版本列表
                        const cacheData = localStorage.getItem('github_release_cache');
                        if (cacheData) {
                            const { data } = JSON.parse(cacheData);
                            updateDownloadLinks(data);
                        }
                    }
                    // 关闭模态框
                    bootstrap.Modal.getInstance(nodeModal).hide();
                }
            });
            
            // 初始化显示
            updateActiveState();
        }
        
        // 控制台刷新版本
        window.refreshVersion = function() {
            console.log('刷新版本...');
            // 清除缓存
            localStorage.removeItem('github_release_cache');
            // 重新检查版本
            checkLatestVersion();
            console.log('版本刷新完成');
        };
        
        // 加载收藏夹内容
        function loadFavoriteContent(favId) {
            // 检查是否已登录
            if (!currentCookies || currentCookies.trim() === '') {
                showToast('请先登录后再查看收藏夹', 'warning');
                hideLoading();
                return;
            }
            
            showLoading('正在加载收藏夹内容...');
            updateProgress(10, '正在加载收藏夹内容...', null, null, null, null, true, '加载中...');
            
            const cleanCookie = currentCookies ? currentCookies.replace(/[\r\n]/g, '') : '';
            
            updateProgress(30, '正在获取数据...', null, null, null, null, true, '获取中...');
            
            axios.post('api.php', {
                action: 'get_favorites_content',
                fav_id: favId,
                cookie: cleanCookie
            })
            .then(response => {
                updateProgress(80, '正在处理数据...', null, null, null, null, true, '处理中...');
                
                console.log('收藏夹内容API返回:', response.data);
                
                if (response.data.success) {
                    const videos = response.data.data;
                    
                    // 显示结果区域
                    document.getElementById('resultSection').style.display = 'block';
                    
                    // 清空之前的结果
                    document.getElementById('videoInfo').textContent = '';
                    document.getElementById('qualityGrid').textContent = '';
                    document.getElementById('episodeList').textContent = '';
                    document.getElementById('downloadBtn').style.display = 'none';
                    
                    // 显示视频列表
                    const videoInfo = document.getElementById('videoInfo');
                    
                    if (videos.length === 0) {
                        const emptyDiv = document.createElement('div');
                        emptyDiv.className = 'text-center text-muted';
                        emptyDiv.textContent = '收藏夹为空';
                        videoInfo.appendChild(emptyDiv);
                        updateProgress(100, '加载完成', null, null, null, null, true, '完成！');
                        hideLoading();
                        showToast('收藏夹为空', 'info');
                        return;
                    }
                    
                    // 显示视频列表
                    const h4 = document.createElement('h4');
                    h4.className = 'mb-4';
                    h4.textContent = '收藏夹视频列表 (' + videos.length + '个视频)';
                    videoInfo.appendChild(h4);
                    
                    const container = document.createElement('div');
                    container.className = 'video-list-container';
                    container.style.maxHeight = '400px';
                    container.style.overflowY = 'auto';
                    // 自定义滚动条样式
                    container.style.scrollbarWidth = 'thin';
                    container.style.scrollbarColor = 'var(--primary) var(--card-bg)';
                    // 为WebKit浏览器添加滚动条样式
                    container.style.WebkitOverflowScrolling = 'touch';
                    
                    // 使用卡片网格布局
                    container.style.display = 'grid';
                    container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(250px, 1fr))';
                    container.style.gap = '10px';
                    container.style.maxHeight = '500px';
                    
                    videos.forEach((video, index) => {
                        const card = document.createElement('div');
                        card.className = 'card';
                        card.style.borderRadius = '0';
                        card.style.overflow = 'hidden';
                        card.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                        card.style.display = 'flex';
                        card.style.flexDirection = 'column';
                        
                        if (video.cover) {
                            const coverUrl = video.cover;
                            if (coverUrl) {
                                let imgSrc = coverUrl;
                                
                                // 检查是否是需要代理的图片URL
                                if (coverUrl.includes('i1.hdslb.com') || coverUrl.includes('i0.hdslb.com') || coverUrl.includes('i2.hdslb.com') || coverUrl.includes('i3.hdslb.com')) {
                                    // 使用代理服务加载图片
                                    imgSrc = `api.php?action=proxy_image&url=${encodeURIComponent(coverUrl)}&cookie=${encodeURIComponent(currentCookies)}`;
                                }
                                
                                const coverImg = document.createElement('img');
                                coverImg.src = imgSrc;
                                coverImg.alt = video.title;
                                coverImg.style.width = '100%';
                                coverImg.style.height = '140px';
                                coverImg.style.objectFit = 'cover';
                                coverImg.style.borderRadius = '0';
                                card.appendChild(coverImg);
                            }
                        }
                        
                        const cardBody = document.createElement('div');
                        cardBody.className = 'card-body';
                        cardBody.style.padding = '10px';
                        cardBody.style.flex = '1';
                        cardBody.style.display = 'flex';
                        cardBody.style.flexDirection = 'column';
                        
                        const cardTitle = document.createElement('h6');
                        cardTitle.className = 'card-title';
                        cardTitle.style.margin = '0 0 5px 0';
                        cardTitle.style.fontSize = '13px';
                        cardTitle.style.fontWeight = '600';
                        cardTitle.style.overflow = 'hidden';
                        cardTitle.style.textOverflow = 'ellipsis';
                        cardTitle.style.display = '-webkit-box';
                        cardTitle.style.webkitLineClamp = '2';
                        cardTitle.style.webkitBoxOrient = 'vertical';
                        cardTitle.textContent = video.title;
                        cardBody.appendChild(cardTitle);
                        
                        const cardText = document.createElement('p');
                        cardText.className = 'card-text text-muted';
                        cardText.style.margin = '0 0 8px 0';
                        cardText.style.fontSize = '11px';
                        cardText.textContent = 'UP主: ' + video.owner.name;
                        cardBody.appendChild(cardText);
                        
                        // 为按钮创建一个容器，确保按钮始终在底部
                        const buttonContainer = document.createElement('div');
                        buttonContainer.style.marginTop = 'auto';
                        
                        const button = document.createElement('button');
                        button.className = 'btn btn-primary btn-sm';
                        button.style.width = '100%';
                        button.style.borderRadius = '0';
                        button.style.fontSize = '11px';
                        button.style.padding = '4px 8px';
                        button.textContent = '解析视频';
                        button.onclick = function() {
                            parseVideoLink(video.bvid);
                        };
                        buttonContainer.appendChild(button);
                        cardBody.appendChild(buttonContainer);
                        
                        card.appendChild(cardBody);
                        container.appendChild(card);
                    });
                    
                    videoInfo.appendChild(container);
                    
                    updateProgress(100, '加载完成');
                    hideLoading();
                    showToast(`收藏夹包含 ${videos.length} 个视频`, 'success');
                } else {
                    hideLoading();
                    showToast('获取收藏夹内容失败: ' + response.data.message, 'danger');
                }
            })
            .catch(error => {
                hideLoading();
                console.error('加载收藏夹内容失败:', error);
                showToast('加载收藏夹内容失败: ' + error.message, 'danger');
            });
        }
        
        // 页面加载完成 - 优先处理首屏内容
        document.addEventListener('DOMContentLoaded', function() {
            console.log('页面加载完成');
            
            // 绑定事件（优先级最高）
            bindEvents();
            
            // 加载保存的Cookie（优先级高）
            loadSavedCookie();
            
            // 初始化节点选择（优先级高）
            initNodeSelection();
            
            // 延迟加载非首屏内容
            setTimeout(() => {
                // 检查FFmpeg WASM加载
                checkFFmpegLoad();
                
                // 只有已登录才自动加载收藏夹
                if (currentCookies && currentCookies.trim() !== '') {
                    loadFavorites();
                }
            }, 1000);
        });
        
        // 检查FFmpeg加载
        function checkFFmpegLoad() {
            console.log('检查FFmpegWASM加载:', typeof FFmpegWASM);
            
            if (typeof FFmpegWASM !== 'undefined' && FFmpegWASM.FFmpeg) {
                ffmpeg = new FFmpegWASM.FFmpeg();
                console.log('检查FFmpeg实例:', ffmpeg);
                loadFFmpeg();
            } else {
                console.warn('FFmpeg未加载');
            }
        }
        
        // 加载FFmpeg
        async function loadFFmpeg() {
            try {
                console.log('开始加载FFmpeg...');
                await ffmpeg.load();
                isFFmpegLoaded = true;
                console.log('FFmpeg加载成功');
            } catch (error) {
                console.error('FFmpeg加载失败:', error);
                showToast('FFmpeg加载失败，将使用直接下载模式', 'warning');
            }
        }
        
        // 加载保存的Cookie
        function loadSavedCookie() {
            const savedCookie = localStorage.getItem('bilibili_cookie');
            const savedUsername = localStorage.getItem('bilibili_username');
            if (savedCookie) {
                currentCookies = savedCookie;
                document.getElementById('cookieInput').value = savedCookie;
                if (savedUsername) {
                    updateLoginStatus(true, savedUsername);
                } else {
                    updateLoginStatus(true);
                    getUsername();
                }
                console.log('已加载保存的Cookie');
            }
        }
        
        // 更新登录状态
        function updateLoginStatus(logged, user = '') {
            const loginStatus = document.getElementById('loginStatus');
            const usernameEl = document.getElementById('username');
            const loginActions = document.getElementById('loginActions');
            const logoutActions = document.getElementById('logoutActions');
            
            if (logged) {
                loginStatus.classList.add('logged');
                if (user) {
                    username = user;
                    usernameEl.textContent = user;
                } else {
                    usernameEl.textContent = '已登录';
                }
                loginActions.style.display = 'none';
                logoutActions.style.display = 'flex';
            } else {
                loginStatus.classList.remove('logged');
                username = '';
                usernameEl.textContent = '未登录';
                loginActions.style.display = 'flex';
                logoutActions.style.display = 'none';
            }
        }
        
        // 获取用户名
        async function getUsername() {
            try {
                const cleanCookie = currentCookies ? currentCookies.replace(/[\r\n]/g, '') : '';
                const response = await axios.post('api.php', {
                    action: 'get_user_info',
                    cookie: cleanCookie
                });
                
                if (response.data.success && response.data.data) {
                    updateLoginStatus(true, response.data.data.name || '已登录');
                    if (response.data.data.name) {
                        localStorage.setItem('bilibili_username', response.data.data.name);
                    }
                } else {
                    updateLoginStatus(true, '已登录');
                }
            } catch (error) {
                console.error('获取用户信息失败:', error);
                updateLoginStatus(true, '已登录');
            }
        }
        
        // 注销登录
        function logout() {
            currentCookies = '';
            username = '';
            localStorage.removeItem('bilibili_cookie');
            localStorage.removeItem('bilibili_username');
            updateLoginStatus(false);
            document.getElementById('cookieInput').value = '';
            document.getElementById('cookieLoginSection').style.display = 'none';
            document.getElementById('qrLoginSection').style.display = 'none';
            showToast('已注销登录', 'info');
        }

        async function saveCookie() {
            const cookieInput = document.getElementById('cookieInput');
            const cookie = cookieInput.value.trim();
            if (!cookie) {
                showToast('请输入Cookie', 'warning');
                return;
            }
            showLoading('验证Cookie中...');
            try {
                const cleanCookie = cookie.replace(/[\r\n]/g, '');
                const formData = new FormData();
                formData.append('action', 'get_user_info');
                formData.append('cookie', cleanCookie);
                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();
                if (!res.success) throw new Error(res.error || 'Cookie验证失败');
                currentCookies = cleanCookie;
                localStorage.setItem('bilibili_cookie', cleanCookie);
                const name = res.data ? (res.data.name || res.data.uname || '已登录') : '已登录';
                localStorage.setItem('bilibili_username', name);
                updateLoginStatus(true, name);
                document.getElementById('cookieLoginSection').style.display = 'none';
                hideLoading();
                showToast('登录成功', 'success');
            } catch (err) {
                hideLoading();
                console.error('Cookie登录失败:', err);
                showToast('登录失败: ' + err.message, 'danger');
            }
        }

        let qrCodeKey = '';
        let qrPollTimer = null;

        async function generateQRCode() {
            const qrCanvas = document.getElementById('qrcode');
            const qrStatus = document.getElementById('qrStatus');
            if (!qrCanvas) return;
            showLoading('生成二维码...');
            try {
                const formData = new FormData();
                formData.append('action', 'generate_qr_code');
                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();
                if (!res.success) throw new Error(res.error || '生成二维码失败');
                qrCodeKey = res.data.qr_code_key || res.data.qrcode_key || '';
                const url = res.data.qr_code_url || res.data.qrcode_url || res.data.auth_url || '';
                if (qrCanvas && url) {
                    const ctx = qrCanvas.getContext('2d');
                    const img = new Image();
                    img.crossOrigin = 'anonymous';
                    img.onload = function() {
                        qrCanvas.width = img.width;
                        qrCanvas.height = img.height;
                        ctx.drawImage(img, 0, 0);
                    };
                    img.onerror = function() {
                        qrCanvas.style.display = 'none';
                        const parent = qrCanvas.parentNode;
                        const imgEl = document.createElement('img');
                        imgEl.src = url;
                        imgEl.style.width = '200px';
                        imgEl.style.height = '200px';
                        parent.insertBefore(imgEl, qrCanvas);
                    };
                    img.src = proxyImageUrl(url);
                }
                if (qrStatus) qrStatus.textContent = '请使用B站APP扫码登录';
                hideLoading();
                startQRPolling();
            } catch (err) {
                hideLoading();
                console.error('生成二维码失败:', err);
                if (qrStatus) qrStatus.textContent = '生成失败: ' + err.message;
            }
        }

        function startQRPolling() {
            if (qrPollTimer) clearInterval(qrPollTimer);
            qrPollTimer = setInterval(async () => {
                if (!qrCodeKey) return;
                try {
                    const formData = new FormData();
                    formData.append('action', 'check_qr_login');
                    formData.append('qr_code_key', qrCodeKey);
                    const resp = await fetch('api.php', { method: 'POST', body: formData });
                    const res = await resp.json();
                    const qrStatus = document.getElementById('qrStatus');
                    if (res.success && res.data) {
                        const code = res.data.code || 86101;
                        if (code === 0 || res.data.cookie) {
                            clearInterval(qrPollTimer);
                            qrPollTimer = null;
                            const cookie = res.data.cookie || '';
                            if (cookie) {
                                currentCookies = cookie;
                                localStorage.setItem('bilibili_cookie', cookie);
                                const name = res.data.name || '已登录';
                                localStorage.setItem('bilibili_username', name);
                                updateLoginStatus(true, name);
                                document.getElementById('qrLoginSection').style.display = 'none';
                                showToast('登录成功', 'success');
                            }
                        } else if (code === 86038 || code === 86090) {
                            if (qrStatus) qrStatus.textContent = '二维码已过期，请刷新';
                            clearInterval(qrPollTimer);
                            qrPollTimer = null;
                        } else if (code === 86090 || res.data.message === '已扫描') {
                            if (qrStatus) qrStatus.textContent = '已扫描，请在手机上确认';
                        }
                    }
                } catch (e) {
                    console.error('轮询二维码状态失败:', e);
                }
            }, 3000);
        }

        async function loadFavorites() {
            if (!currentCookies) {
                showToast('请先登录后再加载收藏夹', 'warning');
                return;
            }
            showLoading('加载收藏夹...');
            try {
                const formData = new FormData();
                formData.append('action', 'get_favorites_list');
                if (currentCookies) formData.append('cookie', currentCookies);
                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();
                if (!res.success) throw new Error(res.error || '加载失败');
                const favList = res.data.list || res.data || [];
                const select = document.getElementById('favSelect');
                if (select) {
                    select.innerHTML = '<option value="">选择收藏夹</option>';
                    favList.forEach(fav => {
                        const opt = document.createElement('option');
                        opt.value = fav.id || fav.media_id || '';
                        opt.textContent = fav.title || fav.name || '';
                        select.appendChild(opt);
                    });
                }
                hideLoading();
                showToast(`加载成功，共 ${favList.length} 个收藏夹`, 'success');
            } catch (err) {
                hideLoading();
                console.error('加载收藏夹失败:', err);
                showToast('加载失败: ' + err.message, 'danger');
            }
        }

        let currentFavVideos = [];

        async function loadFavoritesContent(favId) {
            if (!favId) return;
            if (!currentCookies) {
                showToast('请先登录', 'warning');
                return;
            }
            showLoading('加载收藏夹内容...');
            try {
                const formData = new FormData();
                formData.append('action', 'get_favorites_content');
                formData.append('fav_id', favId);
                if (currentCookies) formData.append('cookie', currentCookies);
                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();
                if (!res.success) throw new Error(res.error || '加载失败');
                currentFavVideos = res.data || [];
                displayFavoritesContent(currentFavVideos);
                hideLoading();
                showToast(`加载成功，共 ${currentFavVideos.length} 个视频`, 'success');
            } catch (err) {
                hideLoading();
                console.error('加载收藏夹内容失败:', err);
                showToast('加载失败: ' + err.message, 'danger');
            }
        }

        function displayFavoritesContent(videos) {
            let resultSection = document.getElementById('videoResultSection');
            if (!resultSection) {
                resultSection = document.createElement('div');
                resultSection.id = 'videoResultSection';
                resultSection.className = 'mt-6';
                const tabVideo = document.getElementById('tab-video');
                const inputSection = tabVideo.querySelector('.input-section');
                if (inputSection && inputSection.parentNode) {
                    inputSection.parentNode.insertBefore(resultSection, inputSection.nextSibling);
                } else {
                    tabVideo.appendChild(resultSection);
                }
            }

            let html = `
                <div class="input-section">
                    <label>收藏夹视频列表 (${videos.length})</label>
                    <div style="max-height: 400px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px; padding: 8px;">
                        ${videos.map((v, idx) => `
                            <div style="display: flex; align-items: center; padding: 8px; border-bottom: 1px solid var(--border); cursor: pointer;"
                                 onmouseover="this.style.background='rgba(0,161,214,0.05)'"
                                 onmouseout="this.style.background='transparent'"
                                 onclick="parseFavVideo(${idx})">
                                <input type="checkbox" class="fav-checkbox" data-idx="${idx}" style="margin-right: 10px;" onclick="event.stopPropagation()">
                                ${v.cover ? `<img src="${proxyImageUrl(v.cover)}" style="width: 80px; height: 50px; object-fit: cover; border-radius: 4px; margin-right: 10px;" onerror="this.style.display='none'">` : ''}
                                <div style="flex: 1; min-width: 0;">
                                    <div style="font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(v.title || '未命名视频')}</div>
                                    <div style="color: var(--text-secondary); font-size: 12px; margin-top: 4px;">
                                        ${v.owner && v.owner.name ? `<i class="fas fa-user"></i> ${escapeHtml(v.owner.name)}` : ''}
                                        ${v.duration ? ` &nbsp; <i class="fas fa-clock"></i> ${formatDuration(v.duration)}` : ''}
                                        ${v.bvid ? ` &nbsp; <span style="color: var(--primary);">${v.bvid}</span>` : ''}
                                    </div>
                                </div>
                                <button class="btn btn-primary btn-sm" style="padding: 4px 12px; font-size: 12px; margin-left: 10px;"
                                        onclick="event.stopPropagation(); parseFavVideo(${idx})">
                                    <i class="fas fa-play"></i> 解析
                                </button>
                            </div>
                        `).join('')}
                    </div>
                    <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                        <button class="btn btn-outline" onclick="selectAllFav()" style="padding: 6px 14px; font-size: 13px;">
                            <i class="fas fa-check-double"></i> 全选
                        </button>
                        <button class="btn btn-outline" onclick="selectNoneFav()" style="padding: 6px 14px; font-size: 13px;">
                            <i class="fas fa-times"></i> 取消全选
                        </button>
                        <button class="btn btn-primary" onclick="batchParseFav()" style="padding: 6px 14px; font-size: 13px;">
                            <i class="fas fa-play-circle"></i> 批量解析选中
                        </button>
                    </div>
                </div>
            `;

            resultSection.innerHTML = html;
        }

        function selectAllFav() {
            document.querySelectorAll('.fav-checkbox').forEach(cb => cb.checked = true);
        }

        function selectNoneFav() {
            document.querySelectorAll('.fav-checkbox').forEach(cb => cb.checked = false);
        }

        async function parseFavVideo(idx) {
            const video = currentFavVideos[idx];
            if (!video) return;
            const bvid = video.bvid || '';
            if (!bvid) {
                showToast('无法解析该视频', 'warning');
                return;
            }
            document.getElementById('videoUrl').value = 'https://www.bilibili.com/video/' + bvid;
            await parseVideo();
            // 在视频详情上方添加返回收藏夹按钮
            const resultSection = document.getElementById('videoResultSection');
            if (resultSection) {
                const backDiv = document.createElement('div');
                backDiv.style.cssText = 'margin-bottom: 12px;';
                backDiv.innerHTML = `<button class="btn btn-outline" onclick="restoreFavList()" style="padding: 6px 14px; font-size: 13px;"><i class="fas fa-arrow-left"></i> 返回收藏夹列表</button>`;
                resultSection.insertBefore(backDiv, resultSection.firstChild);
            }
        }

        function restoreFavList() {
            currentVideoInfo = null;
            if (currentFavVideos.length > 0) {
                displayFavoritesContent(currentFavVideos);
            }
        }

        async function batchParseFav() {
            const checkboxes = document.querySelectorAll('.fav-checkbox:checked');
            if (checkboxes.length === 0) {
                showToast('请先选择要解析的视频', 'warning');
                return;
            }
            showToast(`已选择 ${checkboxes.length} 个视频，将依次解析`, 'info');
        }

        function selectAllEpisodes() {
            const checkboxes = document.querySelectorAll('#episodeList input[type="checkbox"]');
            checkboxes.forEach(cb => cb.checked = true);
            updateSelectedCount();
        }

        function selectNoneEpisodes() {
            const checkboxes = document.querySelectorAll('#episodeList input[type="checkbox"]');
            checkboxes.forEach(cb => cb.checked = false);
            updateSelectedCount();
        }

        function updateSelectedCount() {
            const checkboxes = document.querySelectorAll('#episodeList input[type="checkbox"]');
            const checked = document.querySelectorAll('#episodeList input[type="checkbox"]:checked');
            const countEl = document.getElementById('selectedCount');
            if (countEl) countEl.textContent = `${checked.length}/${checkboxes.length}`;
        }

        async function startDownload() {
            if (!currentVideoInfo) {
                showToast('请先解析视频', 'warning');
                return;
            }
            showToast('开始下载，视频将在浏览器中合成', 'info');
        }

        function goBackToList() {
            currentVideoInfo = null;
            const resultSection = document.getElementById('videoResultSection');
            if (resultSection) {
                if (currentFavVideos.length > 0) {
                    displayFavoritesContent(currentFavVideos);
                } else {
                    resultSection.innerHTML = '';
                }
            }
        }
        
        // 绑定事件
        function bindEvents() {

            // Tab切换
            document.querySelectorAll('.tool-tab').forEach(tab => {
                tab.addEventListener('click', function() {
                    const target = this.getAttribute('data-tab');
                    document.querySelectorAll('.tool-tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tool-tab-content').forEach(c => c.classList.remove('active'));
                    this.classList.add('active');
                    const content = document.getElementById('tab-' + target);
                    if (content) content.classList.add('active');
                });
            });
            
            // 解析按钮
            const parseBtn = document.getElementById('parseBtn');
            if (parseBtn) parseBtn.addEventListener('click', parseVideo);
            
            // Cookie登录按钮
            const cookieLoginBtn = document.getElementById('cookieLoginBtn');
            if (cookieLoginBtn) cookieLoginBtn.addEventListener('click', function() {
                document.getElementById('cookieLoginSection').style.display = 'block';
                document.getElementById('qrLoginSection').style.display = 'none';
            });
            
            // 扫码登录按钮
            const qrLoginBtn = document.getElementById('qrLoginBtn');
            if (qrLoginBtn) qrLoginBtn.addEventListener('click', function() {
                document.getElementById('qrLoginSection').style.display = 'block';
                document.getElementById('cookieLoginSection').style.display = 'none';
                generateQRCode();
            });
            
            // 保存Cookie按钮
            const saveCookieBtn = document.getElementById('saveCookieBtn');
            if (saveCookieBtn) saveCookieBtn.addEventListener('click', saveCookie);
            
            // 注销按钮
            const logoutBtn = document.getElementById('logoutBtn');
            if (logoutBtn) logoutBtn.addEventListener('click', logout);
            
            // 加载收藏夹按钮
            const loadFavBtn = document.getElementById('loadFavBtn');
            if (loadFavBtn) loadFavBtn.addEventListener('click', loadFavorites);

            // 收藏夹选择
            const favSelect = document.getElementById('favSelect');
            if (favSelect) favSelect.addEventListener('change', function() {
                const favId = this.value;
                if (favId) {
                    loadFavoritesContent(favId);
                }
            });
            
            // 全选按钮
            const selectAllBtn = document.getElementById('selectAllBtn');
            if (selectAllBtn) selectAllBtn.addEventListener('click', selectAllEpisodes);
            
            // 取消按钮
            const selectNoneBtn = document.getElementById('selectNoneBtn');
            if (selectNoneBtn) selectNoneBtn.addEventListener('click', selectNoneEpisodes);
            
            // 下载按钮
            const downloadBtn = document.getElementById('downloadBtn');
            if (downloadBtn) downloadBtn.addEventListener('click', startDownload);
            
            // 返回按钮
            const backBtn = document.getElementById('backBtn');
            if (backBtn) backBtn.addEventListener('click', goBackToList);

            // ===== 直播解析 =====
            const liveParseBtn = document.getElementById('liveParseBtn');
            if (liveParseBtn) liveParseBtn.addEventListener('click', parseLive);
            const liveCopyBtn = document.getElementById('liveCopyBtn');
            if (liveCopyBtn) liveCopyBtn.addEventListener('click', function() {
                const url = document.getElementById('liveStreamUrl').value;
                if (url) {
                    navigator.clipboard.writeText(url).then(() => showToast('已复制到剪贴板', 'success'));
                }
            });
            const liveOpenBtn = document.getElementById('liveOpenBtn');
            if (liveOpenBtn) liveOpenBtn.addEventListener('click', function() {
                const url = document.getElementById('liveStreamUrl').value;
                if (url) window.open(url, '_blank');
            });
            const liveRoomInput = document.getElementById('liveRoomId');
            if (liveRoomInput) liveRoomInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') parseLive();
            });

            // ===== 音频解析 =====
            const audioParseBtn = document.getElementById('audioParseBtn');
            if (audioParseBtn) audioParseBtn.addEventListener('click', parseAudio);
            const audioCopyBtn = document.getElementById('audioCopyBtn');
            if (audioCopyBtn) audioCopyBtn.addEventListener('click', function() {
                const url = document.getElementById('audioStreamUrl').value;
                if (url) {
                    navigator.clipboard.writeText(url).then(() => showToast('已复制到剪贴板', 'success'));
                }
            });
            const audioDownloadBtn = document.getElementById('audioDownloadBtn');
            if (audioDownloadBtn) audioDownloadBtn.addEventListener('click', function() {
                const url = document.getElementById('audioStreamUrl').value;
                if (url) window.open(url, '_blank');
            });
            const audioIdInput = document.getElementById('audioId');
            if (audioIdInput) audioIdInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') parseAudio();
            });

            // ===== 表情下载 =====
            const emojiLoadHotBtn = document.getElementById('emojiLoadHotBtn');
            if (emojiLoadHotBtn) emojiLoadHotBtn.addEventListener('click', loadEmojiHot);
            const emojiLoadMyBtn = document.getElementById('emojiLoadMyBtn');
            if (emojiLoadMyBtn) emojiLoadMyBtn.addEventListener('click', loadEmojiList);
            const emojiBackBtn = document.getElementById('emojiBackBtn');
            if (emojiBackBtn) emojiBackBtn.addEventListener('click', function() {
                document.getElementById('emojiDetailSection').style.display = 'none';
                document.getElementById('emojiPackageList').style.display = 'grid';
            });
            const emojiDownloadAllBtn = document.getElementById('emojiDownloadAllBtn');
            if (emojiDownloadAllBtn) emojiDownloadAllBtn.addEventListener('click', downloadAllEmoji);
        }

        // ===== 表情下载 =====
        let currentEmojiPackages = [];
        let currentEmojiDetail = null;

        async function loadEmojiHot() {
            const business = document.getElementById('emojiBusiness').value;
            showLoading('加载热门表情包...');
            try {
                const hotIds = '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30';
                const formData = new FormData();
                formData.append('action', 'emoji_package');
                formData.append('package_ids', hotIds);
                formData.append('business', business);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '加载失败');

                currentEmojiPackages = res.data.packages || [];
                displayEmojiPackages(currentEmojiPackages);
                hideLoading();
                showToast('加载成功', 'success');
            } catch (err) {
                hideLoading();
                console.error('加载热门表情包失败:', err);
                showToast('加载失败: ' + err.message, 'danger');
            }
        }

        async function loadEmojiList() {
            const business = document.getElementById('emojiBusiness').value;
            showLoading('加载我的表情包...');
            try {
                const formData = new FormData();
                formData.append('action', 'emoji_list');
                formData.append('business', business);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '加载失败');

                currentEmojiPackages = res.data.packages || [];
                displayEmojiPackages(currentEmojiPackages);
                hideLoading();
                if (!currentEmojiPackages.length) {
                    showToast('暂无表情包，请先登录或查看热门表情', 'warning');
                }
            } catch (err) {
                hideLoading();
                console.error('加载表情包列表失败:', err);
                showToast('加载失败: ' + err.message, 'danger');
            }
        }

        function displayEmojiPackages(packages) {
            const container = document.getElementById('emojiPackageList');
            if (!packages.length) {
                container.innerHTML = '<div class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 20px;">暂无表情包数据</div>';
                container.style.display = 'block';
                return;
            }

            container.innerHTML = packages.map(pkg => `
                <div class="emoji-package-item" onclick="loadEmojiPackage(${pkg.package_id || pkg.id})">
                    <img src="${proxyImageUrl(pkg.icon || pkg.url || '')}" alt="${escapeHtml(pkg.name || '')}" onerror="this.style.display='none'">
                    <div class="pkg-name">${escapeHtml(pkg.name || '')}</div>
                    <div class="pkg-count">${pkg.emote_count || 0} 个表情</div>
                    ${pkg.type_text ? `<div class="pkg-count" style="color:var(--primary);">${escapeHtml(pkg.type_text)}</div>` : ''}
                </div>
            `).join('');
            container.style.display = 'grid';
            document.getElementById('emojiDetailSection').style.display = 'none';
        }

        async function loadEmojiPackage(packageId) {
            const business = document.getElementById('emojiBusiness').value;
            showLoading('加载表情包详情...');
            try {
                const formData = new FormData();
                formData.append('action', 'emoji_package');
                formData.append('package_ids', packageId);
                formData.append('business', business);
                if (currentCookies) formData.append('cookie', currentCookies);

                const resp = await fetch('api.php', { method: 'POST', body: formData });
                const res = await resp.json();

                if (!res.success) throw new Error(res.error || '加载失败');

                const packages = res.data.packages || [];
                if (!packages.length) throw new Error('未找到该表情包');

                currentEmojiDetail = packages[0];
                displayEmojiDetail(packages[0]);
                document.getElementById('emojiPackageList').style.display = 'none';
                document.getElementById('emojiDetailSection').style.display = 'block';
                hideLoading();
            } catch (err) {
                hideLoading();
                console.error('加载表情包详情失败:', err);
                showToast('加载失败: ' + err.message, 'danger');
            }
        }

        function displayEmojiDetail(pkg) {
            document.getElementById('emojiPackageInfo').innerHTML = `
                <div class="audio-info-card">
                    <img src="${proxyImageUrl(pkg.icon || pkg.url || '')}" alt="${escapeHtml(pkg.name || '')}" onerror="this.style.display='none'">
                    <div class="info">
                        <h4>${escapeHtml(pkg.name || '')}</h4>
                        <div class="meta">
                            <div><i class="fas fa-grin-alt"></i> 共 ${pkg.emote_count || 0} 个表情
                            ${pkg.type_text ? ` &nbsp; <span class="badge-tag badge-block">${escapeHtml(pkg.type_text)}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            const emoticons = pkg.emoticons || pkg.emote || [];
            document.getElementById('emojiGrid').innerHTML = emoticons.map((em, idx) => `
                <div class="emoji-item" title="${escapeHtml(em.name || em.text || '')}">
                    <img src="${proxyImageUrl(em.url || '')}" alt="${escapeHtml(em.name || '')}" loading="lazy">
                    <div class="emoji-name">${escapeHtml(em.name || em.text || '')}</div>
                    <a class="download-icon" href="${proxyImageUrl(em.url || '')}" download="${escapeHtml(em.name || 'emoji')}.png" title="下载">
                        <i class="fas fa-download"></i>
                    </a>
                </div>
            `).join('');
        }

        function downloadAllEmoji() {
            if (!currentEmojiDetail) return;
            const emoticons = currentEmojiDetail.emoticons || currentEmojiDetail.emote || [];
            if (!emoticons.length) return;
            showToast('开始批量下载，请允许浏览器下载多个文件', 'info');
            emoticons.forEach((em, idx) => {
                setTimeout(() => {
                    const a = document.createElement('a');
                    a.href = proxyImageUrl(em.url || '');
                    a.download = (em.name || em.text || 'emoji') + '.png';
                    a.target = '_blank';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }, idx * 300);
            });
        }

    </script>

<?php require_once 'footer.php'; ?>