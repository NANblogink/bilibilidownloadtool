<?php
set_time_limit(30);
ini_set('max_execution_time', 30);
ini_set('default_socket_timeout', 15);
ini_set('memory_limit', '256M');

if (!function_exists('str_ends_with')) {
    function str_ends_with($haystack, $needle) {
        $length = strlen($needle);
        if ($length === 0) return true;
        return substr($haystack, -$length) === $needle;
    }
}

if (!function_exists('str_starts_with')) {
    function str_starts_with($haystack, $needle) {
        $length = strlen($needle);
        if ($length === 0) return true;
        return substr($haystack, 0, $length) === $needle;
    }
}

require_once __DIR__ . '/../src/BilibiliParser.php';
require_once __DIR__ . '/../src/DownloadManager.php';
require_once __DIR__ . '/../src/TaskManager.php';
require_once __DIR__ . '/../src/NetworkUtils.php';
require_once __DIR__ . '/../src/ConfigLoader.php';

use BilibiliDownloader\NetworkUtils;

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: SAMEORIGIN');
header('X-XSS-Protection: 1; mode=block');
header('Referrer-Policy: strict-origin-when-cross-origin');
header('Permissions-Policy: accelerometer=(), autoplay=(), camera=(), display-capture=(), encrypted-media=(), fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), sync-xhr=(), usb=()');
header('Content-Security-Policy: default-src \'self\'; script-src \'self\' https://cdn.jsdelivr.net https://cdn.bootcdn.net; style-src \'self\' https://cdn.jsdelivr.net https://cdn.bootcdn.net; img-src \'self\' data: https:; media-src \'self\' https://*.bilivideo.com https://*.bilivideo.cn https://*.hdslb.com blob:; font-src \'self\' https://cdn.jsdelivr.net https://cdn.bootcdn.net; connect-src \'self\' https://api.bilibili.com https://passport.bilibili.com https://upos-sz-mirrorcos.bilivideo.com https://upos-sz-estgoss.bilivideo.com https://api.github.com https://ghproxy.com https://gh.api.99988866.xyz https://g.ioiox.com https://ghproxy.net https://github.com.cnpmjs.org https://hub.fastgit.org;');
header('Strict-Transport-Security: max-age=31536000; includeSubDomains; preload');
header('Connection: close');
header('Keep-Alive: timeout=5, max=100');


global $data;
$contentType = $_SERVER['CONTENT_TYPE'] ?? 'unknown';


if (strpos($contentType, 'application/json') !== false) {
    $rawInput = file_get_contents('php://input');
    $data = json_decode($rawInput, true);
    $action = $data['action'] ?? '';
} else if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $data = $_POST;
    $action = $_POST['action'] ?? '';
} else if ($_SERVER['REQUEST_METHOD'] === 'GET') {

    $data = $_GET;
    $action = $_GET['action'] ?? '';
} else {
    $data = [];
    $action = '';
}


if (empty($action)) {
    $inputInfo = isset($rawInput) ? substr($rawInput, 0, 100) : 'GET请求';
    responseError('action参数未找到，Content-Type: ' . $contentType . ', 输入: ' . $inputInfo);
    exit;
}

switch ($action) {
    case 'test':
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => true,
            'message' => 'API工作正常！限流系统已激活',
            'timestamp' => time(),
            'client_ip' => (isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : 'unknown')
        ]);
        break;
    case 'parse':
        handleParse();
        break;
    case 'download':
        handleDownload();
        break;
    case 'direct_download':
        handleDirectDownload();
        break;
    case 'browser_merge':
        handleBrowserMerge();
        break;
    case 'progress':
        handleProgress();
        break;
    case 'verify_cookie':
        handleVerifyCookie();
        break;
    case 'get_media_urls':
        handleGetMediaUrls();
        break;
    case 'login_with_password':
        handleLoginWithPassword();
        break;
    case 'generate_qr_code':
        handleGenerateQrCode();
        break;
    case 'check_qr_login':
        handleCheckQrLogin();
        break;
    case 'get_captcha':
        handleGetCaptcha();
        break;
    case 'proxy_video':
        handleProxyVideo();
        break;
    case 'redirect_video':
        handleRedirectVideo();
        break;
    case 'get_favorites':
        handleGetFavorites();
        break;
    case 'get_danmaku':
        handleGetDanmaku();
        break;
    case 'get_favorites_list':
        handleGetFavoritesList();
        break;
    case 'get_favorites_content':
        handleGetFavoritesContent();
        break;
    case 'get_user_info':
        handleGetUserInfo();
        break;
    case 'proxy_image':
        handleProxyImage();
        break;
    case 'v1_check':
        handleV1Check();
        break;
    case 'v1_announcement':
        handleV1Announcement();
        break;
    case 'live_info':
        handleLiveInfo();
        break;
    case 'live_stream':
        handleLiveStream();
        break;
    case 'audio_info':
        handleAudioInfo();
        break;
    case 'audio_stream':
        handleAudioStream();
        break;
    case 'emoji_list':
        handleEmojiList();
        break;
    case 'emoji_all':
        handleEmojiAll();
        break;
    case 'emoji_package':
        handleEmojiPackage();
        break;
    default:
        responseError('action参数未找到');
        break;
}

function handleParse() {
    global $data;
    set_time_limit(60);
    ini_set('max_execution_time', 60);
    
    $url = $data['url'] ?? '';
    $cookie = $data['cookie'] ?? '';
    // 清理url值，移除单引号、反引号和空格
    $url = trim($url, "` ' ");
    // 移除所有单引号和反引号
    $url = str_replace(['`', "'"], '', $url);
    if (empty($url)) {
        responseError('请输入视频链接');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        require_once __DIR__ . '/../src/BilibiliParser.php';

        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        if (!empty($cookie)) {
            $parser->setCookies($cookie);
        }

        // 解析视频链接
        $mediaInfo = $parser->parseMediaUrl($url);
        if (!$mediaInfo['type']) {
            responseError($mediaInfo['error']);
            return;
        }

        // 检查是否是UP主主页
        if ($mediaInfo['type'] == 'space') {
            // 获取UP主信息和作品列表
            try {
                $spaceInfo = $parser->getSpaceInfo($mediaInfo['id']);

                // 调试输出
                error_log("UP主信息调试: " . var_export($spaceInfo, true));

                responseSuccess([
                    'type' => 'space',
                    'name' => $spaceInfo['name'] ?? '未知UP主',
                    'videos' => $spaceInfo['archives'] ?? []
                ]);
            } catch (\Exception $e) {
                responseError('获取UP主信息失败: ' . $e->getMessage());
            }
            return;
        }

        // 获取视频详细信息
        try {
            $result = $parser->parseMedia($mediaInfo['type'], $mediaInfo['id']);
            if (!$result['success']) {
                responseError($result['error']);
                return;
            }

            // 移除result中的success字段，因为responseSuccess会添加
            unset($result['success']);
            responseSuccess($result);
        } catch (\Exception $e) {
            responseError('parseMedia失败: ' . $e->getMessage());
        }
    } catch (\Exception $e) {
        responseError('解析失败: ' . $e->getMessage());
    } catch (\Error $e) {
        responseError('解析错误: ' . $e->getMessage());
    } catch (\Throwable $e) {
        responseError('解析异常: ' . $e->getMessage());
    }
}

function handleVerifyCookie() {
    global $data;
    $cookie = $data['cookie'] ?? '';
    if (empty($cookie)) {
        responseError('请输入Cookie');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        require_once __DIR__ . '/../src/BilibiliParser.php';

        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        $saveResult = $parser->setCookies($cookie);
        if (!$saveResult) {
            responseError('Cookie格式错误');
            return;
        }

        // 验证cookie
        list($success, $msg) = $parser->verifyCookie();
        if ($success) {
            // 获取用户信息
            $userInfo = $parser->getUserInfo();
            responseSuccess([
                'msg' => $msg,
                'username' => $userInfo['uname'] ?? '用户'
            ]);
        } else {
            responseError($msg);
        }
    } catch (\Exception $e) {
        responseError('验证失败: ' . $e->getMessage());
    }
}

function handleDownload() {
    $url = $_POST['url'] ?? '';
    $videoInfo = $_POST['video_info'] ?? [];
    $qn = $_POST['qn'] ?? '';
    $savePath = $_POST['save_path'] ?? './downloads';
    $episodes = $_POST['episodes'] ?? [];

    if (empty($url) || empty($videoInfo) || empty($qn) || empty($episodes)) {
        responseError('参数不完整');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $taskManager = new BilibiliDownloader\TaskManager();
        $taskId = uniqid('task_');

        // 异步执行下载任务
        $taskData = [
            'task_id' => $taskId,
            'url' => $url,
            'video_info' => $videoInfo,
            'qn' => $qn,
            'save_path' => $savePath,
            'episodes' => $episodes,
            'status' => 'pending',
            'progress' => 0,
            'start_time' => time()
        ];

        $taskManager->saveTask($taskId, $taskData);

        // 后台执行下载
        exec('php ' . __DIR__ . '/../src/DownloadWorker.php ' . $taskId . ' > NUL 2>&1 &');

        responseSuccess(['task_id' => $taskId]);
    } catch (\Exception $e) {
        responseError('创建下载任务失败: ' . $e->getMessage());
    }
}

function handleProgress() {
    $taskId = $_POST['task_id'] ?? '';
    if (empty($taskId)) {
        responseError('任务ID不能为空');
        return;
    }

    try {
        $taskManager = new BilibiliDownloader\TaskManager();
        $task = $taskManager->getTask($taskId);

        if (!$task) {
            responseError('任务不存在');
            return;
        }

        responseSuccess([
            'progress' => $task['progress'] ?? 0,
            'status' => $task['status'] ?? '未知'
        ]);
    } catch (\Exception $e) {
        responseError('获取进度失败: ' . $e->getMessage());
    }
}

function handleDirectDownload() {
    global $data;
    $url = $data['url'] ?? '';
    $qn = $data['qn'] ?? 80;
    $cookie = $data['cookie'] ?? '';

    if (empty($url)) {
        responseError('请输入视频链接');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        if (!empty($cookie)) {
            $parser->setCookies($cookie);
        }

        // 解析视频信息
        $mediaInfo = $parser->parseMediaUrl($url);
        if (!$mediaInfo['type']) {
            responseError($mediaInfo['error']);
            return;
        }

        // 获取视频详细信息
        $result = $parser->parseMedia($mediaInfo['type'], $mediaInfo['id']);
        if (!$result['success']) {
            responseError($result['error']);
            return;
        }

        // 获取视频和音频链接 - 智能选择最高可用质量
        $videoUrl = '';
        $audioUrl = $result['audio_url'] ?? '';

        // 如果请求的清晰度存在，直接使用
        if (isset($result['video_urls'][$qn])) {
            $videoUrl = $result['video_urls'][$qn];
        } else {
            // 如果请求的清晰度不存在，选择最高可用的
            $availableQns = array_keys($result['video_urls']);
            rsort($availableQns); // 降序排序
            $highestQn = $availableQns[0];
            $videoUrl = $result['video_urls'][$highestQn];
        }

        if (!$videoUrl) {
            responseError('未获取到视频链接');
            return;
        }

        // 下载视频文件到服务器
        $tempDir = __DIR__ . '/../temp';
        if (!is_dir($tempDir)) {
            mkdir($tempDir, 0777, true);
        }

        $videoPath = $parser->downloadFile($videoUrl, $tempDir, null, 'video', $result['bvid']);
        $audioPath = '';

        if ($audioUrl) {
            $audioPath = $parser->downloadFile($audioUrl, $tempDir, null, 'audio', $result['bvid']);
        }

        // 直接返回文件给用户下载（不合并）
        $outputFilename = $result['title'] . '.mp4';

        if ($audioPath) {
            // 如果有音频，返回视频文件（浏览器端合并）
            header('Content-Description: File Transfer');
            header('Content-Type: video/mp4');
            header('Content-Disposition: attachment; filename=' . urlencode($outputFilename));
            header('Content-Transfer-Encoding: binary');
            header('X-Audio-Path: ' . base64_encode($audioPath));
            header('X-Title: ' . base64_encode($result['title']));
            header('Content-Length: ' . filesize($videoPath));

            ob_clean();
            flush();
            readfile($videoPath);

            // 清理临时文件
            unlink($videoPath);
            unlink($audioPath);

            exit;
        } else {
            // 如果没有音频，直接返回视频文件
            header('Content-Description: File Transfer');
            header('Content-Type: video/mp4');
            header('Content-Disposition: attachment; filename=' . urlencode($outputFilename));
            header('Content-Transfer-Encoding: binary');
            header('Expires: 0');
            header('Cache-Control: must-revalidate');
            header('Pragma: public');
            header('Content-Length: ' . filesize($videoPath));

            ob_clean();
            flush();
            readfile($videoPath);

            // 清理临时文件
            unlink($videoPath);

            exit;
        }

    } catch (\Exception $e) {
        $errorMsg = $e->getMessage();
        // 检查是否是cookie相关的错误
        if (strpos($errorMsg, '权限不足') !== false || strpos($errorMsg, '稿件不可见') !== false) {
            responseError('下载失败: ' . $errorMsg . '，请确保您已登录B站并拥有该视频的访问权限');
        } else {
            responseError('下载失败: ' . $errorMsg);
        }
    }
}

function handleBrowserMerge() {
    global $data;
    $url = $data['url'] ?? '';
    $qn = $data['qn'] ?? 80;
    $cookie = $data['cookie'] ?? '';

    if (empty($url)) {
        responseError('请输入视频链接');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        if (!empty($cookie)) {
            $parser->setCookies($cookie);
        }

        // 解析视频信息
        $mediaInfo = $parser->parseMediaUrl($url);
        if (!$mediaInfo['type']) {
            responseError($mediaInfo['error']);
            return;
        }

        // 获取视频详细信息
        $result = $parser->parseMedia($mediaInfo['type'], $mediaInfo['id']);
        if (!$result['success']) {
            responseError($result['error']);
            return;
        }

        // 获取视频和音频链接 - 智能选择最高可用质量
        $videoUrl = '';
        $audioUrl = $result['audio_url'] ?? '';

        // 如果请求的清晰度存在，直接使用
        if (isset($result['video_urls'][$qn])) {
            $videoUrl = $result['video_urls'][$qn];
        } else {
            // 如果请求的清晰度不存在，选择最高可用的
            $availableQns = array_keys($result['video_urls']);
            rsort($availableQns); // 降序排序
            $highestQn = $availableQns[0];
            $videoUrl = $result['video_urls'][$highestQn];
        }

        if (!$videoUrl) {
            responseError('未获取到视频链接');
            return;
        }

        // 下载视频文件到服务器
        $tempDir = __DIR__ . '/../temp';
        if (!is_dir($tempDir)) {
            mkdir($tempDir, 0777, true);
        }

        $videoPath = $parser->downloadFile($videoUrl, $tempDir, null, 'video', $result['bvid']);
        $audioPath = '';

        if ($audioUrl) {
            $audioPath = $parser->downloadFile($audioUrl, $tempDir, null, 'audio', $result['bvid']);
        }

        // 返回文件路径给浏览器，让浏览器下载并合并
        responseSuccess([
            'video_path' => $videoPath,
            'audio_path' => $audioPath,
            'title' => $result['title'],
            'has_audio' => !empty($audioPath)
        ]);

    } catch (\Exception $e) {
        $errorMsg = $e->getMessage();
        if (strpos($errorMsg, '权限不足') !== false || strpos($errorMsg, '稿件不可见') !== false) {
            responseError('下载失败: ' . $errorMsg . '，请确保您已登录B站并拥有该视频的访问权限');
        } else {
            responseError('下载失败: ' . $errorMsg);
        }
    }
}

// 查找系统中的ffmpeg
function findFFmpeg() {
    // 尝试在系统路径中查找
    $ffmpegPath = exec('where ffmpeg 2>nul') ?: exec('which ffmpeg 2>/dev/null');
    if ($ffmpegPath) {
        return trim($ffmpegPath);
    }

    // 尝试在常见位置查找
    $commonPaths = [
        'C:/ffmpeg/bin/ffmpeg.exe',
        'D:/ffmpeg/bin/ffmpeg.exe',
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg'
    ];

    foreach ($commonPaths as $path) {
        if (file_exists($path)) {
            return $path;
        }
    }

    return false;
}

function handleGetMediaUrls() {
    global $data;
    set_time_limit(60);
    ini_set('max_execution_time', 60);
    
    $url = $data['url'] ?? '';
    $qn = $data['qn'] ?? 80;
    $cookie = $data['cookie'] ?? '';
    $mediaType = $data['media_type'] ?? '';
    $seasonId = $data['season_id'] ?? '';
    $epId = $data['ep_id'] ?? '';

    if (empty($url)) {
        responseError('请输入视频链接');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        if (!empty($cookie)) {
            $parser->setCookies($cookie);
        }

        // 解析视频信息
        $mediaInfo = $parser->parseMediaUrl($url);
        if (!$mediaInfo['type']) {
            responseError($mediaInfo['error']);
            return;
        }

        // 如果是课程类型，使用传递的类型
        if (!empty($mediaType) && $mediaType === 'cheese') {
            $mediaInfo['type'] = 'cheese';
        }

        // 获取视频详细信息
        $result = $parser->parseMedia($mediaInfo['type'], $mediaInfo['id'], false, $qn);
        if (!$result['success']) {
            responseError($result['error']);
            return;
        }

        // 获取视频和音频链接 - 智能选择最高可用质量
        $videoUrl = '';
        $audioUrl = $result['audio_url'] ?? '';
        $usedQn = 0;
        $usedQualityName = '';

        // 如果请求的清晰度存在，直接使用
        if (isset($result['video_urls'][$qn])) {
            $videoUrl = $result['video_urls'][$qn];
            $usedQn = $qn;
        } else {
            // 如果请求的清晰度不存在，选择最高可用的
            $availableQns = array_keys($result['video_urls']);
            rsort($availableQns); // 降序排序
            $usedQn = $availableQns[0];
            $videoUrl = $result['video_urls'][$usedQn];
        }

        // 查找实际使用的清晰度名称
        foreach ($result['qualities'] as $quality) {
            if ($quality[0] == $usedQn) {
                $usedQualityName = $quality[1];
                break;
            }
        }

        if (!$videoUrl) {
            responseError('未获取到视频链接');
            return;
        }

        responseSuccess([
            'video_url' => $videoUrl,
            'audio_url' => $audioUrl,
            'title' => $result['title'],
            'cover' => $result['cover'] ?? '',
            'used_qn' => $usedQn,
            'used_quality_name' => $usedQualityName,
            'requested_qn' => $qn,
            'available_qualities' => $result['qualities'],
            'key_id' => $result['key_id'] ?? ''
        ]);

    } catch (\Exception $e) {
        $errorMsg = $e->getMessage();
        // 检查是否是cookie相关的错误
        if (strpos($errorMsg, '权限不足') !== false || strpos($errorMsg, '稿件不可见') !== false) {
            responseError('获取媒体链接失败: ' . $errorMsg . '，请确保您已登录B站并拥有该视频的访问权限');
        } else {
            responseError('获取媒体链接失败: ' . $errorMsg);
        }
    }
}

function handleLoginWithPassword() {
    global $data;
    $username = $data['username'] ?? '';
    $password = $data['password'] ?? '';
    $geetestChallenge = $data['geetest_challenge'] ?? '';
    $geetestValidate = $data['geetest_validate'] ?? '';
    $geetestSeccode = $data['geetest_seccode'] ?? '';
    $token = $data['token'] ?? '';

    if (empty($username) || empty($password)) {
        responseError('请输入用户名和密码');
        return;
    }

    if (empty($geetestChallenge) || empty($geetestValidate) || empty($geetestSeccode)) {
        responseError('请先完成验证码验证');
        return;
    }

    try {
        // 1. 先获取公钥和盐值
        $keyUrl = 'https://passport.bilibili.com/x/passport-login/web/key';
        $headers = [
            'Referer' => 'https://passport.bilibili.com/login',
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ];

        list($success, $result) = BilibiliDownloader\NetworkUtils::request($keyUrl, $headers, [], [], 'GET');
        if (!$success) {
            throw new \Exception('获取公钥失败：' . $result['error']);
        }

        $keyData = json_decode($result['content'], true);
        if ($keyData['code'] != 0) {
            throw new \Exception('获取公钥失败：' . ($keyData['message'] ?? '未知错误'));
        }

        $hash = $keyData['data']['hash'];
        $publicKey = $keyData['data']['key'];

        // 2. 加密密码
        $encryptedPassword = encryptPassword($hash . $password, $publicKey);

        // 使用前端传来的token
        if (empty($token)) {
            throw new \Exception('缺少验证码token');
        }

        // 4. 登录请求URL
        $loginUrl = 'https://passport.bilibili.com/x/passport-login/web/login';

        // 5. 构建登录参数
        $params = [
            'username' => $username,
            'password' => $encryptedPassword,
            'keep' => '0',
            'token' => $token,
            'challenge' => $geetestChallenge,
            'validate' => $geetestValidate,
            'seccode' => $geetestSeccode . '|jordan'
        ];

        // 6. 发送登录请求
        list($success, $result) = BilibiliDownloader\NetworkUtils::request($loginUrl, $headers, [], $params, 'POST');
        if (!$success) {
            throw new \Exception('登录请求失败：' . $result['error']);
        }

        // 调试：输出登录响应
        file_put_contents('login_debug.txt', json_encode([
            'url' => $loginUrl,
            'params' => $params,
            'response_code' => $result['code'],
            'response_headers' => $result['headers'],
            'response_content' => $result['content']
        ], JSON_PRETTY_PRINT));

        if ($result['code'] != 200) {
            throw new \Exception('登录请求失败，HTTP状态码：' . $result['code']);
        }

        $responseData = json_decode($result['content'], true);
        if ($responseData['code'] != 0) {
            throw new \Exception('登录失败：' . ($responseData['message'] ?? '未知错误'));
        }

        // 检查是否需要手机号验证
        if (isset($responseData['data']['status']) && $responseData['data']['status'] == 2) {
            throw new \Exception('登录环境存在风险，需要手机号验证：' . $responseData['data']['message'] . '，请使用其他登录方式或在浏览器中登录B站后使用Cookie登录');
        }

        // 5. 提取Cookie
        $cookies = [];
        if (isset($result['headers']['Set-Cookie'])) {
            foreach ($result['headers']['Set-Cookie'] as $cookie) {
                if (preg_match('/(SESSDATA|buvid3|bili_jct)=([^;]+);/', $cookie, $matches)) {
                    $cookies[$matches[1]] = $matches[2];
                }
            }
        }

        if (empty($cookies)) {
            throw new \Exception('未获取到登录Cookie');
        }

        // 6. 验证登录状态
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);
        $parser->setCookies($cookies);
        list($valid, $msg) = $parser->verifyCookie();

        if (!$valid) {
            throw new \Exception('登录验证失败：' . $msg);
        }

        // 获取用户信息
        $userInfo = $parser->getUserInfo();

        // 7. 构建Cookie字符串
        $cookieString = '';
        foreach ($cookies as $key => $value) {
            $cookieString .= "{$key}={$value}; ";
        }
        $cookieString = rtrim($cookieString, '; ');

        responseSuccess([
            'msg' => $msg,
            'cookie' => $cookieString,
            'username' => $userInfo['uname'] ?? '用户'
        ]);

    } catch (\Exception $e) {
        responseError('登录失败：' . $e->getMessage());
    }
}

function handleGenerateQrCode() {
    try {
        // 实现生成二维码逻辑

        // 1. 获取二维码
        $url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate';
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer' => 'https://passport.bilibili.com/login'
        ];

        // 使用GET方法
        list($success, $result) = BilibiliDownloader\NetworkUtils::request($url, $headers, [], [], 'GET');
        if (!$success) {
            throw new \Exception('获取二维码失败：' . $result['error']);
        }

        // 调试：输出完整响应
        file_put_contents('qr_debug.txt', json_encode($result, JSON_PRETTY_PRINT));

        $data = json_decode($result['content'], true);
        if (!$data) {
            throw new \Exception('获取二维码失败：返回数据格式错误，原始数据：' . $result['content']);
        }

        // 输出完整数据结构
        $fullData = json_encode($data, JSON_PRETTY_PRINT);
        file_put_contents('qr_data.txt', $fullData);

        if (isset($data['code']) && $data['code'] != 0) {
            throw new \Exception('获取二维码失败：' . ($data['message'] ?? '未知错误') . '，完整数据：' . $fullData);
        }

        // 检查返回的数据结构
        if (!isset($data['data'])) {
            throw new \Exception('获取二维码失败：返回数据结构不正确，完整数据：' . $fullData);
        }

        // 尝试所有可能的字段名
        $qrCodeKey = $data['data']['qrcode_key'] ?? $data['data']['key'] ?? $data['data']['qrcodeKey'] ?? $data['data']['qr_key'] ?? '';
        $authUrl = $data['data']['url'] ?? $data['data']['auth_url'] ?? $data['data']['qr_url'] ?? $data['data']['qrcode_url'] ?? $data['data']['authUrl'] ?? '';

        if (empty($qrCodeKey)) {
            throw new \Exception('获取二维码key失败，返回数据：' . json_encode($data['data']));
        }

        if (empty($authUrl)) {
            throw new \Exception('获取二维码URL失败，返回数据：' . json_encode($data['data']));
        }

        // 生成二维码图片URL
        $qrCodeUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' . urlencode($authUrl);

        responseSuccess([
            'qr_code_key' => $qrCodeKey,
            'auth_url' => $authUrl,
            'qr_code_url' => $qrCodeUrl
        ]);

    } catch (\Exception $e) {
        responseError('生成二维码失败：' . $e->getMessage());
    }
}

function handleCheckQrLogin() {
    global $data;
    $qrCodeKey = $data['qr_code_key'] ?? '';

    if (empty($qrCodeKey)) {
        responseError('请提供二维码key');
        return;
    }

    try {
        // 实现检查二维码登录状态逻辑

        // 1. 检查登录状态
        $url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=' . urlencode($qrCodeKey);
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer' => 'https://passport.bilibili.com/login'
        ];

        list($success, $result) = NetworkUtils::request($url, $headers, [], [], 'GET');
        if (!$success) {
            throw new \Exception('检查登录状态失败：' . $result['error']);
        }

        // 调试：输出响应头
        file_put_contents('qr_poll_debug.txt', json_encode([
            'url' => $url,
            'response_code' => $result['code'],
            'response_headers' => $result['headers'],
            'response_content' => $result['content']
        ], JSON_PRETTY_PRINT));

        $data = json_decode($result['content'], true);

        if ($data['code'] == 0) {
            $code = $data['data']['code'] ?? 0;
            $message = $data['data']['message'] ?? '';

            if ($code == 0) {
                // 登录成功

                // 提取Cookie
                $cookies = [];

                // 从响应体的data.url字段中提取Cookie
                if (isset($data['data']['url'])) {
                    $url = $data['data']['url'];
                    // 解析URL中的查询参数
                    $parseUrl = parse_url($url);
                    if (isset($parseUrl['query'])) {
                        parse_str($parseUrl['query'], $params);
                        // 提取需要的Cookie
                        if (isset($params['SESSDATA'])) {
                            $cookies['SESSDATA'] = $params['SESSDATA'];
                        }
                        if (isset($params['bili_jct'])) {
                            $cookies['bili_jct'] = $params['bili_jct'];
                        }
                        if (isset($params['DedeUserID'])) {
                            $cookies['DedeUserID'] = $params['DedeUserID'];
                        }
                        if (isset($params['DedeUserID__ckMd5'])) {
                            $cookies['DedeUserID__ckMd5'] = $params['DedeUserID__ckMd5'];
                        }
                    }
                }

                // 如果从URL中提取失败，尝试从响应头中提取
                if (empty($cookies) && isset($result['headers']['Set-Cookie'])) {
                    foreach ($result['headers']['Set-Cookie'] as $cookie) {
                        if (preg_match('/(SESSDATA|buvid3|bili_jct)=([^;]+);/', $cookie, $matches)) {
                            $cookies[$matches[1]] = $matches[2];
                        }
                    }
                }

                if (empty($cookies)) {
                    throw new \Exception('未获取到登录Cookie');
                }

                // 构建Cookie字符串
                $cookieString = '';
                foreach ($cookies as $key => $value) {
                    $cookieString .= "{$key}={$value}; ";
                }
                $cookieString = rtrim($cookieString, '; ');

                // 验证登录状态
                $config = new BilibiliDownloader\ConfigLoader();
                $parser = new BilibiliDownloader\BilibiliParser($config);
                $parser->setCookies($cookies);
                list($valid, $msg) = $parser->verifyCookie();

                if (!$valid) {
                    throw new \Exception('登录验证失败：' . $msg);
                }

                // 获取用户信息
                $userInfo = $parser->getUserInfo();

                responseSuccess([
                    'code' => 0,
                    'message' => $message,
                    'cookie' => $cookieString,
                    'username' => $userInfo['uname'] ?? '用户'
                ]);
            } else if ($code == 86038) {
                // 二维码已失效
                responseSuccess([
                    'code' => 86038,
                    'message' => $message
                ]);
            } else if ($code == 86101) {
                // 未扫码
                responseSuccess([
                    'code' => 86101,
                    'message' => $message
                ]);
            } else if ($code == 86090) {
                // 已扫描，等待确认
                responseSuccess([
                    'code' => 86090,
                    'message' => $message
                ]);
            } else {
                // 其他状态
                responseSuccess([
                    'code' => $code,
                    'message' => $message
                ]);
            }
        } else {
            throw new \Exception('登录失败：' . ($data['message'] ?? '未知错误'));
        }

    } catch (\Exception $e) {
        responseError('检查登录状态失败：' . $e->getMessage());
    }
}

function handleGetCaptcha() {
    try {
        $captchaUrl = 'https://passport.bilibili.com/x/passport-login/captcha?source=main_web';
        $headers = [
            'Referer' => 'https://passport.bilibili.com/login',
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ];

        list($success, $result) = BilibiliDownloader\NetworkUtils::request($captchaUrl, $headers, [], [], 'GET');
        if (!$success) {
            throw new \Exception('获取验证码失败：' . $result['error']);
        }

        $captchaData = json_decode($result['content'], true);
        if ($captchaData['code'] != 0) {
            throw new \Exception('获取验证码失败：' . ($captchaData['message'] ?? '未知错误'));
        }

        if (isset($captchaData['data']['geetest'])) {
            responseSuccess([
                'gt' => $captchaData['data']['geetest']['gt'],
                'challenge' => $captchaData['data']['geetest']['challenge'],
                'token' => $captchaData['data']['token']
            ]);
        } else {
            throw new \Exception('获取验证码失败：未获取到极验验证码');
        }

    } catch (\Exception $e) {
        responseError('获取验证码失败：' . $e->getMessage());
    }
}

function encryptPassword($password, $publicKey) {
    // 清理公钥格式
    $publicKey = str_replace('-----BEGIN PUBLIC KEY-----', '', $publicKey);
    $publicKey = str_replace('-----END PUBLIC KEY-----', '', $publicKey);
    $publicKey = str_replace("\n", '', $publicKey);
    $publicKey = str_replace("\r", '', $publicKey);
    $publicKey = trim($publicKey);

    // 重新格式化公钥
    $formattedKey = "-----BEGIN PUBLIC KEY-----\n";
    $formattedKey .= chunk_split($publicKey, 64, "\n");
    $formattedKey .= "-----END PUBLIC KEY-----\n";

    // 使用RSA加密
    $encrypted = '';
    openssl_public_encrypt($password, $encrypted, $formattedKey, OPENSSL_PKCS1_PADDING);

    // Base64编码
    return base64_encode($encrypted);
}

function handleLiveInfo() {
    global $data;
    $roomId = trim($data['room_id'] ?? '');
    $cookie = $data['cookie'] ?? '';

    if (empty($roomId)) {
        responseError('请输入直播间号');
        return;
    }

    if (!preg_match('/^\d+$/', $roomId)) {
        responseError('直播间号格式错误');
        return;
    }

    try {
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://live.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
            'Accept-Language' => 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin' => 'https://live.bilibili.com',
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ['&' => '&', '=' => '=']), $cookies);
        }

        $url = 'https://api.live.bilibili.com/room/v1/Room/get_info?room_id=' . $roomId;
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], 'GET', 15);
        if (!$success) {
            throw new \Exception($resp['error'] ?? '请求失败');
        }

        $result = json_decode($resp['content'], true);
        if (!$result || !isset($result['code'])) {
            responseError('获取直播间信息失败');
            return;
        }

        if ($result['code'] != 0) {
            responseError($result['message'] ?? '获取直播间信息失败');
            return;
        }

        $roomData = $result['data'] ?? [];
        $uid = $roomData['uid'] ?? 0;

        $userUrl = 'https://api.live.bilibili.com/live_user/v1/Master/info?uid=' . $uid;
        list($userSuccess, $userResp) = NetworkUtils::request($userUrl, $headers, $cookies, [], 'GET', 15);
        $userResult = $userSuccess ? json_decode($userResp['content'], true) : null;
        $userInfo = ($userResult && isset($userResult['code']) && $userResult['code'] == 0) ? ($userResult['data'] ?? []) : [];

        $statusMap = [0 => '未开播', 1 => '直播中', 2 => '轮播中'];
        $liveStatus = $roomData['live_status'] ?? 0;

        responseSuccess([
            'room_id' => $roomData['room_id'] ?? $roomId,
            'short_id' => $roomData['short_id'] ?? 0,
            'title' => $roomData['title'] ?? '',
            'cover' => $roomData['user_cover'] ?? ($roomData['keyframe'] ?? ''),
            'background' => $roomData['background'] ?? '',
            'area_name' => $roomData['area_name'] ?? '',
            'parent_area_name' => $roomData['parent_area_name'] ?? '',
            'live_status' => $liveStatus,
            'live_status_text' => $statusMap[$liveStatus] ?? '未知',
            'online' => $roomData['online'] ?? 0,
            'attention' => $roomData['attention'] ?? 0,
            'uid' => $uid,
            'uname' => $userInfo['info']['uname'] ?? ($roomData['uname'] ?? ''),
            'avatar' => $userInfo['info']['face'] ?? '',
            'description' => $roomData['description'] ?? '',
            'tags' => $roomData['tags'] ?? '',
        ]);
    } catch (\Exception $e) {
        responseError('获取直播间信息失败: ' . $e->getMessage());
    }
}

function handleLiveStream() {
    global $data;
    $roomId = trim($data['room_id'] ?? '');
    $cookie = $data['cookie'] ?? '';
    $qn = isset($data['qn']) ? intval($data['qn']) : 10000;

    if (empty($roomId)) {
        responseError('请输入直播间号');
        return;
    }

    try {
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://live.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ['&' => '&', '=' => '=']), $cookies);
        }

        $url = 'https://api.live.bilibili.com/room/v1/Room/playUrl';
        $params = [
            'cid' => $roomId,
            'platform' => 'web',
            'qn' => $qn,
        ];
        $url .= '?' . http_build_query($params);
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], 'GET', 15);
        if (!$success) {
            throw new \Exception($resp['error'] ?? '请求失败');
        }

        $result = json_decode($resp['content'], true);
        if (!$result || !isset($result['code'])) {
            responseError('获取直播流失败');
            return;
        }

        if ($result['code'] != 0) {
            responseError($result['message'] ?? '获取直播流失败');
            return;
        }

        $streamData = $result['data'] ?? [];
        $qualityDescMap = [
            80 => '流畅',
            150 => '高清',
            250 => '超清',
            400 => '蓝光',
            10000 => '原画',
            20000 => '4K',
            25000 => '默认',
            30000 => '杜比',
        ];

        $qualityList = [];
        if (isset($streamData['quality_description']) && is_array($streamData['quality_description'])) {
            foreach ($streamData['quality_description'] as $q) {
                $qnVal = $q['qn'] ?? 0;
                $qualityList[] = [
                    'qn' => $qnVal,
                    'desc' => $qualityDescMap[$qnVal] ?? ($q['desc'] ?? '未知'),
                ];
            }
        }

        $durl = $streamData['durl'] ?? [];
        $streamUrl = !empty($durl) ? ($durl[0]['url'] ?? '') : '';

        responseSuccess([
            'current_qn' => $streamData['current_qn'] ?? $qn,
            'quality_list' => $qualityList,
            'stream_url' => $streamUrl,
            'durl' => $durl,
            'accept_quality' => $streamData['accept_quality'] ?? [],
        ]);
    } catch (\Exception $e) {
        responseError('获取直播流失败: ' . $e->getMessage());
    }
}

function handleAudioInfo() {
    global $data;
    $auId = trim($data['au_id'] ?? '');
    $cookie = $data['cookie'] ?? '';

    if (empty($auId)) {
        responseError('请输入音频ID（AU号）');
        return;
    }

    $auId = preg_replace('/[^0-9]/', '', $auId);
    if (empty($auId)) {
        responseError('音频ID格式错误');
        return;
    }

    try {
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://www.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ['&' => '&', '=' => '=']), $cookies);
        }

        $url = 'https://www.bilibili.com/audio/music-service-c/web/song/info?sid=' . $auId;
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], 'GET', 15);
        if (!$success) {
            throw new \Exception($resp['error'] ?? '请求失败');
        }

        $result = json_decode($resp['content'], true);
        if (!$result || !isset($result['code'])) {
            responseError('获取音频信息失败');
            return;
        }

        if ($result['code'] != 0) {
            responseError($result['message'] ?? '获取音频信息失败');
            return;
        }

        $songData = $result['data'] ?? [];
        $qualityMap = [
            0 => ['desc' => '流畅 128K', 'bitrate' => 128],
            1 => ['desc' => '标准 192K', 'bitrate' => 192],
            2 => ['desc' => '高品质 320K', 'bitrate' => 320],
            3 => ['desc' => '无损 FLAC', 'bitrate' => -1],
        ];

        $availableQualities = [];
        if (isset($songData['type']) && is_array($songData['type'])) {
            foreach ($songData['type'] as $t) {
                $typeVal = intval($t);
                if (isset($qualityMap[$typeVal])) {
                    $availableQualities[] = [
                        'type' => $typeVal,
                        'desc' => $qualityMap[$typeVal]['desc'],
                        'bitrate' => $qualityMap[$typeVal]['bitrate'],
                    ];
                }
            }
        }

        $members = [];
        if (isset($songData['members']) && is_array($songData['members'])) {
            $memberTypeMap = [
                1 => '歌手', 2 => '作词', 3 => '作曲', 4 => '编曲',
                5 => '后期/混音', 7 => '封面制作', 8 => '音源',
                9 => '调音', 10 => '演奏', 11 => '乐器', 127 => 'UP主',
            ];
            foreach ($songData['members'] as $m) {
                $typeId = intval($m['type'] ?? 0);
                $members[] = [
                    'type' => $typeId,
                    'type_text' => $memberTypeMap[$typeId] ?? '未知',
                    'name' => $m['name'] ?? '',
                    'mid' => $m['mid'] ?? 0,
                ];
            }
        }

        responseSuccess([
            'id' => $songData['id'] ?? $auId,
            'title' => $songData['title'] ?? '',
            'cover' => $songData['cover'] ?? '',
            'intro' => $songData['intro'] ?? '',
            'duration' => $songData['duration'] ?? 0,
            'play_count' => $songData['statistic']['play'] ?? 0,
            'collect_count' => $songData['statistic']['collect'] ?? 0,
            'comment_count' => $songData['statistic']['comment'] ?? 0,
            'share_count' => $songData['statistic']['share'] ?? 0,
            'qualities' => $availableQualities,
            'members' => $members,
            'lyric' => $songData['lyric'] ?? '',
            'album' => $songData['album'] ?? '',
            'songlist' => $songData['songlist'] ?? [],
            'uploader' => [
                'mid' => $songData['mid'] ?? 0,
                'name' => $songData['author'] ?? '',
                'avatar' => $songData['up_face'] ?? '',
            ],
            'ctime' => $songData['ctime'] ?? 0,
            'passtime' => $songData['passtime'] ?? 0,
        ]);
    } catch (\Exception $e) {
        responseError('获取音频信息失败: ' . $e->getMessage());
    }
}

function handleAudioStream() {
    global $data;
    $auId = trim($data['au_id'] ?? '');
    $quality = isset($data['quality']) ? intval($data['quality']) : 2;
    $cookie = $data['cookie'] ?? '';

    if (empty($auId)) {
        responseError('请输入音频ID（AU号）');
        return;
    }

    $auId = preg_replace('/[^0-9]/', '', $auId);
    if (empty($auId)) {
        responseError('音频ID格式错误');
        return;
    }

    try {
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://www.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ['&' => '&', '=' => '=']), $cookies);
        }

        $url = 'https://api.bilibili.com/audio/music-service-c/url';
        $params = [
            'mid' => '',
            'mobi_app' => 'web',
            'songid' => $auId,
            'quality' => $quality,
            'privilege' => 2,
            'platform' => 'web',
        ];
        $url .= '?' . http_build_query($params);
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], 'GET', 15);
        if (!$success) {
            throw new \Exception($resp['error'] ?? '请求失败');
        }

        $result = json_decode($resp['content'], true);
        if (!$result || !isset($result['code'])) {
            responseError('获取音频流失败');
            return;
        }

        if ($result['code'] != 0) {
            responseError($result['message'] ?? '获取音频流失败');
            return;
        }

        $dataField = $result['data'] ?? [];
        $qualityType = $dataField['type'] ?? -1;
        $qualityTypeMap = [
            -1 => '试听片段',
            0 => '128K',
            1 => '192K',
            2 => '320K',
            3 => 'FLAC',
        ];

        responseSuccess([
            'url' => $dataField['url'] ?? '',
            'size' => $dataField['size'] ?? 0,
            'duration' => $dataField['duration'] ?? 0,
            'type' => $qualityType,
            'type_text' => $qualityTypeMap[$qualityType] ?? '未知',
            'md5' => $dataField['md5'] ?? '',
            'format' => $dataField['format'] ?? 'mp3',
        ]);
    } catch (\Exception $e) {
        responseError('获取音频流失败: ' . $e->getMessage());
    }
}


function emoji_format_package($pkg) {
    if (!is_array($pkg)) return null;
    $typeMap = [1 => "普通", 2 => "会员专属", 3 => "购买所得", 4 => "颜文字"];
    $typeId = intval($pkg["type"] ?? 1);
    $flags = $pkg["flags"] ?? [];
    $meta = $pkg["meta"] ?? [];
    $emoteList = [];
    $emotes = $pkg["emote"] ?? ($pkg["emotes"] ?? []);
    if (is_array($emotes)) {
        foreach ($emotes as $em) {
            $emMeta = $em["meta"] ?? [];
            $emoteList[] = [
                "id" => intval($em["id"] ?? 0),
                "package_id" => intval($em["package_id"] ?? ($pkg["id"] ?? 0)),
                "text" => $em["text"] ?? "",
                "name" => $em["text"] ?? "",
                "url" => $em["url"] ?? "",
                "type" => intval($em["type"] ?? 1),
                "alias" => $emMeta["alias"] ?? "",
                "size" => intval($emMeta["size"] ?? 1),
                "mtime" => intval($em["mtime"] ?? 0),
            ];
        }
    }
    return [
        "id" => intval($pkg["id"] ?? 0),
        "package_id" => intval($pkg["package_id"] ?? ($pkg["id"] ?? 0)),
        "name" => $pkg["text"] ?? ($pkg["name"] ?? ""),
        "text" => $pkg["text"] ?? "",
        "url" => $pkg["url"] ?? "",
        "icon" => $pkg["url"] ?? "",
        "type" => $typeId,
        "type_text" => $typeMap[$typeId] ?? "未知",
        "emote_count" => !empty($emoteList) ? count($emoteList) : intval($pkg["emote_count"] ?? 0),
        "mtime" => intval($pkg["mtime"] ?? 0),
        "expire_at" => intval($pkg["expire_at"] ?? 0),
        "is_activated" => intval($pkg["is_activated"] ?? 1),
        "added" => !empty($flags["added"]),
        "flags" => $flags,
        "meta" => $meta,
        "emote" => $emoteList,
        "emoticons" => $emoteList,
    ];
}

function handleEmojiAll() {
    global $data;
    $cookie = $data["cookie"] ?? "";
    $business = $data["business"] ?? "reply";
    try {
        $headers = [
            "User-Agent" => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Referer" => "https://www.bilibili.com/",
            "Accept" => "application/json, text/plain, */*",
        ];
        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ["&" => "&", "=" => "="]), $cookies);
        }
        $url = "https://api.bilibili.com/x/emote/setting/panel";
        $params = ["business" => $business];
        $url .= "?" . http_build_query($params);
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], "GET", 15);
        if (!$success) throw new \Exception($resp["error"] ?? "请求失败");
        $result = json_decode($resp["content"], true);
        if (!$result || !isset($result["code"])) { responseError("获取全部表情包失败"); return; }
        if ($result["code"] != 0) { responseError($result["message"] ?? "获取全部表情包失败"); return; }
        $dataField = $result["data"] ?? [];
        $userPackages = $dataField["user_panel_packages"] ?? [];
        $allPackages = $dataField["all_packages"] ?? [];
        $userList = [];
        foreach ($userPackages as $pkg) { $f = emoji_format_package($pkg); if ($f) $userList[] = $f; }
        $allList = [];
        foreach ($allPackages as $pkg) { $f = emoji_format_package($pkg); if ($f) $allList[] = $f; }
        responseSuccess(["user_packages" => $userList, "all_packages" => $allList, "business" => $business]);
    } catch (\Exception $e) {
        responseError("获取全部表情包失败: " . $e->getMessage());
    }
}

function handleEmojiList() {
    global $data;
    $cookie = $data['cookie'] ?? '';
    $business = $data['business'] ?? 'reply';

    try {
        $headers = [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://www.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ['&' => '&', '=' => '=']), $cookies);
        }

        $url = 'https://api.bilibili.com/x/emote/user/panel/web';
        $params = [
            'business' => $business,
        ];
        $url .= '?' . http_build_query($params);
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], 'GET', 15);
        if (!$success) {
            throw new \Exception($resp['error'] ?? '请求失败');
        }

        $result = json_decode($resp['content'], true);
        if (!$result || !isset($result['code'])) {
            responseError('获取表情包列表失败');
            return;
        }

        if ($result['code'] != 0) {
            responseError($result['message'] ?? '获取表情包列表失败');
            return;
        }

        $dataField = $result['data'] ?? [];
        $packages = $dataField['packages'] ?? [];
        $typeMap = [
            1 => '普通',
            2 => '会员专属',
            3 => '购买所得',
            4 => '颜文字',
        ];

        $packageList = [];
        foreach ($packages as $pkg) {
            $typeId = intval($pkg['type'] ?? 0);
            $packageList[] = [
                'id' => intval($pkg['id'] ?? 0),
                'package_id' => intval($pkg['package_id'] ?? ($pkg['id'] ?? 0)),
                'name' => $pkg['text'] ?? ($pkg['name'] ?? ''),
                'url' => $pkg['url'] ?? '',
                'type' => $typeId,
                'type_text' => $typeMap[$typeId] ?? '未知',
                'emote_count' => intval($pkg['emote_count'] ?? 0),
                'expire_at' => intval($pkg['expire_at'] ?? 0),
                'is_activated' => intval($pkg['is_activated'] ?? 1),
                'icon' => $pkg['icon'] ?? ($pkg['url'] ?? ''),
            ];
        }

        responseSuccess([
            'packages' => $packageList,
            'business' => $business,
        ]);
    } catch (\Exception $e) {
        responseError('获取表情包列表失败: ' . $e->getMessage());
    }
}

function handleEmojiPackage() {
    global $data;
    $packageIds = $data["package_ids"] ?? ($data["package_id"] ?? "");
    $cookie = $data["cookie"] ?? "";
    $business = $data["business"] ?? "reply";

    if (empty($packageIds)) {
        responseError("请输入表情包ID");
        return;
    }

    if (is_array($packageIds)) {
        $idsStr = implode(",", array_map("intval", $packageIds));
    } else {
        $idsStr = preg_replace("/[^0-9,]/", "", $packageIds);
    }
    if (empty($idsStr)) {
        responseError("表情包ID格式错误");
        return;
    }

    try {
        $headers = [
            "User-Agent" => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Referer" => "https://www.bilibili.com/",
            "Accept" => "application/json, text/plain, */*",
        ];

        $cookies = [];
        if (!empty($cookie)) {
            parse_str(strtr($cookie, ["&" => "&", "=" => "="]), $cookies);
        }

        $url = "https://api.bilibili.com/x/emote/package";
        $params = [
            "business" => $business,
            "ids" => $idsStr,
        ];
        $url .= "?" . http_build_query($params);
        list($success, $resp) = NetworkUtils::request($url, $headers, $cookies, [], "GET", 15);
        if (!$success) throw new \Exception($resp["error"] ?? "请求失败");

        $result = json_decode($resp["content"], true);
        if (!$result || !isset($result["code"])) {
            responseError("获取表情包详情失败");
            return;
        }
        if ($result["code"] != 0) {
            responseError($result["message"] ?? "获取表情包详情失败");
            return;
        }

        $packages = $result["data"]["packages"] ?? [];
        $packageList = [];
        foreach ($packages as $pkg) {
            $f = emoji_format_package($pkg);
            if ($f) $packageList[] = $f;
        }

        responseSuccess([
            "packages" => $packageList,
            "count" => count($packageList),
        ]);
    } catch (\Exception $e) {
        responseError("获取表情包详情失败: " . $e->getMessage());
    }
}

function responseSuccess($data) {
    echo json_encode([
        'success' => true,
        'data' => $data
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

function responseError($error) {
    echo json_encode([
        'success' => false,
        'error' => $error
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * 检查IP地址是否为内网地址
 * @param string $ip IP地址
 * @return bool
 */
function isInternalIP($ip) {
    $ipLong = ip2long($ip);
    if ($ipLong === false) {
        return false;
    }
    
    // 内网IP地址范围
    $internalRanges = [
        // 10.0.0.0 - 10.255.255.255
        ['start' => ip2long('10.0.0.0'), 'end' => ip2long('10.255.255.255')],
        // 172.16.0.0 - 172.31.255.255
        ['start' => ip2long('172.16.0.0'), 'end' => ip2long('172.31.255.255')],
        // 192.168.0.0 - 192.168.255.255
        ['start' => ip2long('192.168.0.0'), 'end' => ip2long('192.168.255.255')],
        // 127.0.0.0 - 127.255.255.255
        ['start' => ip2long('127.0.0.0'), 'end' => ip2long('127.255.255.255')],
        // 169.254.0.0 - 169.254.255.255 (APIPA)
        ['start' => ip2long('169.254.0.0'), 'end' => ip2long('169.254.255.255')],
        // 100.64.0.0 - 100.127.255.255 (CGNAT)
        ['start' => ip2long('100.64.0.0'), 'end' => ip2long('100.127.255.255')],
        // ::1 (IPv6 localhost)
        ['ipv6' => '::1'],
        // fe80::/10 (IPv6 link-local)
        ['ipv6' => 'fe80::'],
    ];
    
    foreach ($internalRanges as $range) {
        if (isset($range['start']) && isset($range['end'])) {
            if ($ipLong >= $range['start'] && $ipLong <= $range['end']) {
                return true;
            }
        } elseif (isset($range['ipv6'])) {
            // IPv6检查
            if (str_starts_with($ip, $range['ipv6'])) {
                return true;
            }
        }
    }
    
    return false;
}

function handleRedirectVideo() {
    global $data;
    
    $url = $data['url'] ?? '';
    $cookie = $data['cookie'] ?? '';

    if (empty($url)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '请提供视频URL']);
        exit;
    }

    $url = trim($url);
    $url = str_replace(['`', "'", '"'], '', $url);

    $parsedUrl = parse_url($url);
    if ($parsedUrl === false) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '无效的URL格式']);
        exit;
    }

    $allowedProtocols = ['http', 'https'];
    if (!isset($parsedUrl['scheme']) || !in_array(strtolower($parsedUrl['scheme']), $allowedProtocols)) {
        http_response_code(403);
        echo json_encode(['success' => false, 'error' => '不支持的协议']);
        exit;
    }

    if (!isset($parsedUrl['host'])) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '无效的域名']);
        exit;
    }

    $host = strtolower($parsedUrl['host']);

    if (filter_var($host, FILTER_VALIDATE_IP)) {
        if (isInternalIP($host)) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '不允许访问内网地址']);
            exit;
        }
    } else {
        $allowedDomains = [
            'bilibili.com',
            'bilivideo.com',
            'hdslb.com',
            'mcdn.bilivideo.cn',
            'bilibili.co',
            'bilibili.tv'
        ];
        
        $isAllowed = false;
        foreach ($allowedDomains as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                $isAllowed = true;
                break;
            }
        }

        if (!$isAllowed) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '不允许访问该域名']);
            exit;
        }
    }

    if (strpos($url, '..') !== false || strpos($url, '../') !== false) {
        http_response_code(403);
        echo json_encode(['success' => false, 'error' => '检测到路径遍历攻击']);
        exit;
    }

    $bypassPatterns = ['@localhost', '@127.0.0.1', ':///', 'file://', 'gopher://', 'ftp://', 'dict://', 'ldap://'];
    foreach ($bypassPatterns as $pattern) {
        if (strpos($url, $pattern) !== false) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '检测到恶意URL模式']);
            exit;
        }
    }

    header('Referrer-Policy: no-referrer');
    header('Location: ' . $url, true, 302);
    exit;
}

function handleProxyVideo() {
    global $data;
    
    set_time_limit(0);
    ini_set('max_execution_time', 0);
    ini_set('default_socket_timeout', 3600);
    
    $url = $data['url'] ?? '';
    $cookie = $data['cookie'] ?? '';

    if (empty($url)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '请提供视频URL']);
        exit;
    }

    // ========== 安全检查 ==========
    // 1. 清理URL，移除可能的恶意字符
    $url = trim($url);
    $url = str_replace(['`', "'", '"'], '', $url);

    // 2. 解析URL
    $parsedUrl = parse_url($url);
    if ($parsedUrl === false) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '无效的URL格式']);
        exit;
    }

    // 3. 只允许HTTP和HTTPS协议
    $allowedProtocols = ['http', 'https'];
    if (!isset($parsedUrl['scheme']) || !in_array(strtolower($parsedUrl['scheme']), $allowedProtocols)) {
        http_response_code(403);
        echo json_encode(['success' => false, 'error' => '不支持的协议，仅允许HTTP/HTTPS']);
        exit;
    }

    // 4. 检查host是否存在
    if (!isset($parsedUrl['host'])) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '无效的域名']);
        exit;
    }

    $host = strtolower($parsedUrl['host']);

    // 5. 检查是否为IP地址形式
    if (filter_var($host, FILTER_VALIDATE_IP)) {
        // 阻止访问内网IP地址
        if (isInternalIP($host)) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '不允许访问内网地址']);
            exit;
        }
    } else {
        // 6. 检查是否为本地域名
        $localDomains = ['localhost', 'localhost.localdomain', 'local', 'example.com', 'test.com'];
        if (in_array($host, $localDomains)) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '不允许访问本地域名']);
            exit;
        }

        // 7. 检查是否包含本地域名后缀
        $localSuffixes = ['.local', '.localhost', '.internal', '.lan', '.home', '.corp'];
        foreach ($localSuffixes as $suffix) {
            if (str_ends_with($host, $suffix)) {
                http_response_code(403);
                echo json_encode(['success' => false, 'error' => '不允许访问本地域名']);
                exit;
            }
        }

        // 8. 只允许特定的域名（B站相关域名）
        $allowedDomains = [
            'bilibili.com',
            'bilivideo.com',
            'hdslb.com',
            'mcdn.bilivideo.cn',
            'bilibili.co',
            'bilibili.tv'
        ];
        
        $isAllowed = false;
        foreach ($allowedDomains as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                $isAllowed = true;
                break;
            }
        }

        if (!$isAllowed) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '不允许访问该域名']);
            exit;
        }
    }

    // 9. 检查是否包含路径遍历攻击
    if (strpos($url, '..') !== false || strpos($url, '../') !== false) {
        http_response_code(403);
        echo json_encode(['success' => false, 'error' => '检测到路径遍历攻击']);
        exit;
    }

    // 10. 检查是否包含特殊协议绕过
    $bypassPatterns = ['@localhost', '@127.0.0.1', ':///', 'file://', 'gopher://', 'ftp://', 'dict://', 'ldap://'];
    foreach ($bypassPatterns as $pattern) {
        if (strpos($url, $pattern) !== false) {
            http_response_code(403);
            echo json_encode(['success' => false, 'error' => '检测到恶意URL模式']);
            exit;
        }
    }
    // ========== 安全检查结束 ==========

    try {
        $headers = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept: */*',
            'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding: identity',
            'Connection: keep-alive',
            'Referer: https://www.bilibili.com/',
            'Origin: https://www.bilibili.com',
            'Sec-Fetch-Dest: video',
            'Sec-Fetch-Mode: no-cors',
            'Sec-Fetch-Site: cross-site',
            'Pragma: no-cache',
            'Cache-Control: no-cache'
        ];

        if (!empty($cookie)) {
            $headers[] = 'Cookie: ' . $cookie;
        }

        $rangeStart = null;
        $rangeEnd = null;
        $rangeHeader = $_SERVER['HTTP_RANGE'] ?? '';
        if (!empty($rangeHeader) && preg_match('/bytes=(\d+)-(\d*)/', $rangeHeader, $matches)) {
            $rangeStart = intval($matches[1]);
            $rangeEnd = !empty($matches[2]) ? intval($matches[2]) : null;
            $headers[] = 'Range: bytes=' . $rangeStart . '-' . ($rangeEnd !== null ? $rangeEnd : '');
        }

        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Authorization, Range');
        header('Access-Control-Expose-Headers: Content-Range, Content-Length, Accept-Ranges');

        if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
            http_response_code(204);
            exit;
        }

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 3600);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 30);
        curl_setopt($ch, CURLOPT_HEADER, false);
        curl_setopt($ch, CURLOPT_BUFFERSIZE, 128 * 1024);
        curl_setopt($ch, CURLOPT_NOPROGRESS, true);

        $responseHeaders = [];
        curl_setopt($ch, CURLOPT_HEADERFUNCTION, function($curl, $header) use (&$responseHeaders) {
            $len = strlen($header);
            $header = explode(':', $header, 2);
            if (count($header) < 2) {
                return $len;
            }
            $name = strtolower(trim($header[0]));
            $value = trim($header[1]);
            $responseHeaders[$name] = $value;
            return $len;
        });

        while (ob_get_level() > 0) {
            ob_end_clean();
        }
        if (function_exists('apache_setenv')) {
            @apache_setenv('no-gzip', '1');
        }
        ini_set('zlib.output_compression', '0');
        @ini_set('output_buffering', '0');
        @ini_set('implicit_flush', '1');
        ob_implicit_flush(true);

        $headersSent = false;
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, function($curl, $data) use (&$responseHeaders, &$headersSent) {
            if (!$headersSent) {
                $headersSent = true;
                $httpCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
                
                header('Content-Type: ' . ($responseHeaders['content-type'] ?? 'application/octet-stream'));
                header('Accept-Ranges: bytes');
                if (isset($responseHeaders['content-range'])) {
                    header('Content-Range: ' . $responseHeaders['content-range']);
                }
                if (isset($responseHeaders['content-length'])) {
                    header('Content-Length: ' . $responseHeaders['content-length']);
                }
                
                if ($httpCode == 206) {
                    http_response_code(206);
                } else {
                    http_response_code(200);
                }
            }
            
            echo $data;
            if (ob_get_level()) {
                ob_flush();
            }
            flush();
            return strlen($data);
        });

        $success = curl_exec($ch);

        if (!$success) {
            $error = curl_error($ch);
            curl_close($ch);
            http_response_code(502);
            echo json_encode(['success' => false, 'error' => '获取视频内容失败：' . $error]);
            exit;
        }
        
        curl_close($ch);

        exit;

    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => '代理视频失败：' . $e->getMessage()]);
        exit;
    }
}

function handleGetFavorites() {
    global $data;
    $mediaId = $data['media_id'] ?? '';
    $page = $data['page'] ?? 1;
    $getAll = $data['get_all'] ?? false;
    $cookie = $data['cookie'] ?? '';

    if (empty($mediaId)) {
        responseError('请提供收藏夹ID');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        if (!empty($cookie)) {
            $parser->setCookies($cookie);
        }

        // 获取收藏夹内容
        $favorites = $parser->getFavorites($mediaId, $page, $getAll);
        responseSuccess($favorites);

    } catch (\Exception $e) {
        responseError('获取收藏夹内容失败: ' . $e->getMessage());
    }
}

function handleGetDanmaku() {
    global $data;
    $cid = $data['cid'] ?? '';

    if (empty($cid)) {
        responseError('请提供弹幕CID');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 获取弹幕
        $danmaku = $parser->getDanmaku($cid);
        responseSuccess($danmaku);

    } catch (\Exception $e) {
        responseError('获取弹幕失败: ' . $e->getMessage());
    }
}

function handleGetFavoritesList() {
    global $data;
    $cookie = $data['cookie'] ?? '';

    if (empty($cookie)) {
        responseError('请先登录');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        $parser->setCookies($cookie);

        // 获取收藏夹列表
        $favoritesList = $parser->getUserFavoritesList();
        responseSuccess($favoritesList);

    } catch (\Exception $e) {
        responseError('获取收藏夹列表失败: ' . $e->getMessage());
    }
}

function handleGetFavoritesContent() {
    global $data;
    $favId = $data['fav_id'] ?? '';
    $cookie = $data['cookie'] ?? '';


    file_put_contents('fav_debug.txt', json_encode([
        'fav_id' => $favId,
        'cookie' => $cookie,
        'data' => $data
    ], JSON_PRETTY_PRINT));

    if (empty($favId)) {
        responseError('请指定收藏夹ID');
        return;
    }

    if (empty($cookie)) {
        responseError('请先登录');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        $parser->setCookies($cookie);

        // 获取收藏夹内容
        $favoritesContent = $parser->getFavoritesContent($favId);
        responseSuccess($favoritesContent);

    } catch (\Exception $e) {

        file_put_contents('fav_error.txt', $e->getMessage());
        responseError('获取收藏夹内容失败: ' . $e->getMessage());
    }
}

function handleGetUserInfo() {
    global $data;
    $cookie = $data['cookie'] ?? '';

    if (empty($cookie)) {
        responseError('请先登录');
        return;
    }

    try {
        require_once __DIR__ . '/../src/ConfigLoader.php';
        $config = new BilibiliDownloader\ConfigLoader();
        $parser = new BilibiliDownloader\BilibiliParser($config);

        // 设置cookie
        $parser->setCookies($cookie);

        // 获取用户信息
        $userInfo = $parser->getUserInfo();
        responseSuccess($userInfo);

    } catch (\Exception $e) {
        responseError('获取用户信息失败: ' . $e->getMessage());
    }
}

function handleProxyImage() {
    global $data;
    $url = $data['url'] ?? '';
    $cookie = $data['cookie'] ?? '';

    if (empty($url)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'error' => '请提供图片URL']);
        exit;
    }

    try {
        // 构建请求头
        $headers = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer: https://www.bilibili.com/',
            'Origin: https://www.bilibili.com'
        ];

        // 添加cookie
        if (!empty($cookie)) {
            $headers[] = 'Cookie: ' . $cookie;
        }

        // 使用cURL获取图片
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);

        // 获取响应头
        $responseHeaders = [];
        curl_setopt($ch, CURLOPT_HEADERFUNCTION, function($curl, $header) use (&$responseHeaders) {
            $len = strlen($header);
            $header = explode(':', $header, 2);
            if (count($header) < 2) {
                return $len;
            }
            $responseHeaders[strtolower(trim($header[0]))] = trim($header[1]);
            return $len;
        });

        // 执行请求
        $content = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        if (curl_errno($ch)) {
            $error = curl_error($ch);
            
            http_response_code(502);
            echo json_encode(['success' => false, 'error' => '获取图片失败：' . $error]);
            exit;
        }

        

        if ($httpCode != 200) {
            http_response_code(404);
            echo json_encode(['success' => false, 'error' => '图片不存在或无法访问']);
            exit;
        }

        // 设置响应头
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Authorization');

        // 设置Content-Type
        if (isset($responseHeaders['content-type'])) {
            header('Content-Type: ' . $responseHeaders['content-type']);
        } else {
            // 尝试根据URL后缀推断Content-Type
            $pathinfo = pathinfo($url);
            $extension = strtolower($pathinfo['extension'] ?? '');
            switch ($extension) {
                case 'jpg':
                case 'jpeg':
                    header('Content-Type: image/jpeg');
                    break;
                case 'png':
                    header('Content-Type: image/png');
                    break;
                case 'gif':
                    header('Content-Type: image/gif');
                    break;
                case 'webp':
                    header('Content-Type: image/webp');
                    break;
                default:
                    header('Content-Type: image/jpeg');
                    break;
            }
        }

        // 输出图片内容
        echo $content;
        exit;

    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => '代理图片失败：' . $e->getMessage()]);
        exit;
    }
}

function handleV1Check() {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? 'windows';
    $channel = $_GET['channel'] ?? 'stable';

    if (empty($version)) {
        echo json_encode(['code' => 1, 'data' => null, 'message' => '缺少version参数'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    try {
        $dbPath = __DIR__ . '/../data/bilidown.db';
        $pdo = new PDO('sqlite:' . $dbPath);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        $stmt = $pdo->prepare('SELECT * FROM app_version WHERE platform = :platform AND channel = :channel AND is_active = 1 ORDER BY created_at DESC LIMIT 1');
        $stmt->execute([':platform' => $platform, ':channel' => $channel]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);

        if (!$row) {
            echo json_encode(['code' => 0, 'data' => ['has_update' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        $hasUpdate = versionCompare($version, $row['version']) < 0;

        if (!$hasUpdate) {
            echo json_encode(['code' => 0, 'data' => ['has_update' => false], 'message' => 'success'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        $forceUpdate = (bool)$row['force_update'];
        if (!empty($row['min_supported']) && versionCompare($version, $row['min_supported']) < 0) {
            $forceUpdate = true;
        }

        $downloadUrl = $row['download_url'] ?? '';
        if (!empty($downloadUrl) && $downloadUrl[0] === '/') {
            $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
            $downloadUrl = $scheme . '://' . $host . $downloadUrl;
        }

        echo json_encode([
            'code' => 0,
            'data' => [
                'has_update' => true,
                'latest_version' => $row['version'],
                'min_supported_version' => $row['min_supported'] ?? '',
                'force_update' => $forceUpdate,
                'release_notes' => $row['release_notes'] ?? '',
                'download_url' => $downloadUrl,
                'file_size' => isset($row['file_size']) ? (int)$row['file_size'] : 0,
                'sha256' => $row['sha256'] ?? '',
                'release_date' => $row['release_date'] ?? ''
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    } catch (\Exception $e) {
        echo json_encode(['code' => 1, 'data' => null, 'message' => '服务器内部错误'], JSON_UNESCAPED_UNICODE);
        exit;
    }
}

function handleV1Announcement() {
    $version = $_GET['version'] ?? '';
    $platform = $_GET['platform'] ?? '';

    try {
        $dbPath = __DIR__ . '/../data/bilidown.db';
        $pdo = new PDO('sqlite:' . $dbPath);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        date_default_timezone_set('Asia/Shanghai');
        $now = date('Y-m-d H:i:s');

        $stmt = $pdo->prepare('SELECT * FROM announcement WHERE is_active = 1 AND start_time <= :now AND end_time >= :now ORDER BY created_at DESC');
        $stmt->execute([':now' => $now]);
        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

        $announcements = [];
        foreach ($rows as $row) {
            $minVersion = $row['min_version'] ?? '';
            $maxVersion = $row['max_version'] ?? '';

            if (!empty($version) && !empty($minVersion) && versionCompare($version, $minVersion) < 0) {
                continue;
            }
            if (!empty($version) && !empty($maxVersion) && versionCompare($version, $maxVersion) > 0) {
                continue;
            }

            $startTime = '';
            if (!empty($row['start_time'])) {
                $ts = strtotime($row['start_time']);
                if ($ts !== false) {
                    $startTime = date('Y-m-d\TH:i:sP', $ts);
                }
            }

            $endTime = '';
            if (!empty($row['end_time'])) {
                $ts = strtotime($row['end_time']);
                if ($ts !== false) {
                    $endTime = date('Y-m-d\TH:i:sP', $ts);
                }
            }

            $actionUrl = $row['action_url'] ?? '';
            if (!empty($actionUrl) && $actionUrl[0] === '/') {
                $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
                $host = $_SERVER['HTTP_HOST'] ?? 'www.bilidown.cn';
                $actionUrl = $scheme . '://' . $host . $actionUrl;
            }

            $announcements[] = [
                'id' => $row['id'],
                'type' => $row['type'] ?? 'info',
                'title' => $row['title'] ?? '',
                'content' => $row['content'] ?? '',
                'start_time' => $startTime,
                'end_time' => $endTime,
                'action' => [
                    'type' => $row['action_type'] ?? 'none',
                    'url' => $actionUrl
                ],
                'dismissible' => isset($row['dismissible']) ? (bool)$row['dismissible'] : true,
                'min_version' => $minVersion,
                'max_version' => $maxVersion
            ];
        }

        echo json_encode([
            'code' => 0,
            'data' => [
                'has_announcement' => !empty($announcements),
                'announcements' => $announcements
            ],
            'message' => 'success'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    } catch (\Exception $e) {
        echo json_encode([
            'code' => 1,
            'data' => null,
            'message' => '服务器内部错误'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
}

function versionCompare($v1, $v2) {
    $parts1 = array_map('intval', explode('.', $v1));
    $parts2 = array_map('intval', explode('.', $v2));
    $maxLen = max(count($parts1), count($parts2));

    for ($i = 0; $i < $maxLen; $i++) {
        $p1 = $parts1[$i] ?? 0;
        $p2 = $parts2[$i] ?? 0;

        if ($p1 < $p2) {
            return -1;
        }
        if ($p1 > $p2) {
            return 1;
        }
    }

    return 0;
}

?>
