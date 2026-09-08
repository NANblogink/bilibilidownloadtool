<?php

class ConnectionLimiterNoRedis {
    private $storageDir;
    private $maxConnections = 5;
    private $rateLimit = 30;
    private $timeWindow = 60;
    private $connectionTimeout = 30;
    private $blockDuration = 300;
    private $gcProbability = 10;

    public function __construct() {
        $this->storageDir = __DIR__ . '/../tmp/conn_limit';
        if (!is_dir($this->storageDir)) {
            mkdir($this->storageDir, 0700, true);
        }

        if (mt_rand(1, 100) <= $this->gcProbability) {
            $this->cleanup();
        }
    }

    public function getClientIP() {
        $ip = '0.0.0.0';
        if (!empty($_SERVER['HTTP_CF_CONNECTING_IP'])) {
            $ip = $_SERVER['HTTP_CF_CONNECTING_IP'];
        } elseif (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
            $ips = explode(',', $_SERVER['HTTP_X_FORWARDED_FOR']);
            $ip = trim($ips[0]);
        } elseif (!empty($_SERVER['REMOTE_ADDR'])) {
            $ip = $_SERVER['REMOTE_ADDR'];
        }
        return $ip;
    }

    private function getFilePath($type, $ip) {
        $sanitizedIp = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $ip);
        return $this->storageDir . '/' . $type . '_' . $sanitizedIp . '.json';
    }

    public function isBlocked($ip) {
        $filePath = $this->getFilePath('block', $ip);
        if (!file_exists($filePath)) return false;

        $data = json_decode(file_get_contents($filePath), true);
        if (!$data) return false;

        if (time() > $data['expire']) {
            unlink($filePath);
            return false;
        }

        return true;
    }

    public function blockIP($ip) {
        $filePath = $this->getFilePath('block', $ip);
        $data = [
            'ip' => $ip,
            'timestamp' => time(),
            'expire' => time() + $this->blockDuration
        ];
        file_put_contents($filePath, json_encode($data));
        return true;
    }

    public function checkRateLimit($ip) {
        $filePath = $this->getFilePath('rate', $ip);
        $now = time();
        $windowStart = $now - $this->timeWindow;

        $count = 0;
        if (file_exists($filePath)) {
            $data = json_decode(file_get_contents($filePath), true);
            if ($data && $data['window_start'] >= $windowStart) {
                $count = $data['count'];
            }
        }

        $count++;

        if ($count > $this->rateLimit) {
            $this->blockIP($ip);
            return false;
        }

        file_put_contents($filePath, json_encode([
            'count' => $count,
            'window_start' => $now - ($now % $this->timeWindow)
        ]));

        return true;
    }

    public function checkConnectionLimit($ip) {
        $filePath = $this->getFilePath('conn', $ip);
        $count = 0;

        if (file_exists($filePath)) {
            $data = json_decode(file_get_contents($filePath), true);
            if ($data && time() < $data['expire']) {
                $count = $data['count'];
            }
        }

        $count++;

        if ($count > $this->maxConnections) {
            $this->blockIP($ip);
            return false;
        }

        file_put_contents($filePath, json_encode([
            'count' => $count,
            'expire' => time() + $this->connectionTimeout
        ]));

        return true;
    }

    public function releaseConnection($ip) {
        $filePath = $this->getFilePath('conn', $ip);

        if (file_exists($filePath)) {
            $data = json_decode(file_get_contents($filePath), true);
            if ($data && $data['count'] > 0) {
                $data['count']--;
                if ($data['count'] <= 0) {
                    unlink($filePath);
                } else {
                    file_put_contents($filePath, json_encode($data));
                }
            }
        }
    }

    private function cleanup() {
        $files = glob($this->storageDir . '/*.json');
        $now = time();

        foreach ($files as $file) {
            $data = json_decode(file_get_contents($file), true);
            if ($data && isset($data['expire']) && $now > $data['expire']) {
                unlink($file);
            }
        }
    }

    public function check() {
        $ip = $this->getClientIP();

        if ($this->isBlocked($ip)) {
            $this->showLimitPage($ip, 'IP已被临时封禁', 'Too many requests from your IP, please try again later');
        }

        if (!$this->checkRateLimit($ip)) {
            $this->showLimitPage($ip, '请求频率异常', 'Rate limit exceeded, too many requests per minute');
        }

        if (!$this->checkConnectionLimit($ip)) {
            $this->showLimitPage($ip, '并发连接数异常', 'Connection limit exceeded, too many concurrent connections');
        }

        return $ip;
    }

    private function showLimitPage($ip, $title, $message) {
        $timestamp = date('Y-m-d H:i:s');
        $retryAfter = ceil($this->blockDuration / 60);

        echo '<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>访问受限 - 安全防护</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-width: 600px;
            width: 100%;
        }
        .header {
            background: #cc0000;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 36px;
            margin-bottom: 8px;
        }
        .header .subtitle {
            font-size: 18px;
            opacity: 0.95;
        }
        .content {
            padding: 30px;
        }
        .alert {
            background: #cc0000;
            color: white;
            padding: 20px;
            margin-bottom: 25px;
            text-align: center;
            font-size: 20px;
            font-weight: 600;
        }
        .info-grid {
            margin-bottom: 25px;
        }
        .info-item {
            background: #f8f9fa;
            padding: 12px 15px;
            margin-bottom: 10px;
            border-left: 3px solid #cc0000;
        }
        .info-item .label {
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 3px;
        }
        .info-item .value {
            color: #333;
            font-size: 15px;
            font-weight: 600;
            word-break: break-all;
        }
        .footer {
            background: #f8f9fa;
            padding: 15px 30px;
            text-align: center;
            color: #666;
            font-size: 13px;
        }
        .countdown {
            background: #333;
            color: white;
            padding: 20px;
            text-align: center;
            margin-top: 20px;
        }
        .countdown .time {
            font-size: 48px;
            font-weight: 700;
        }
        .countdown .unit {
            font-size: 14px;
            opacity: 0.9;
        }
        @media (max-width: 480px) {
            .header { padding: 25px 20px; }
            .header h1 { font-size: 28px; }
            .content { padding: 25px 20px; }
            .alert { font-size: 16px; padding: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ 流量异常</h1>
            <div class="subtitle">检测到异常访问行为</div>
        </div>

        <div class="content">
            <div class="alert">
                🚫 ' . htmlspecialchars($title) . '
            </div>

            <div class="info-grid">
                <div class="info-item">
                    <div class="label">您的 IP 地址</div>
                    <div class="value">' . htmlspecialchars($ip) . '</div>
                </div>
                <div class="info-item">
                    <div class="label">检测时间</div>
                    <div class="value">' . htmlspecialchars($timestamp) . '</div>
                </div>
                <div class="info-item">
                    <div class="label">请求状态</div>
                    <div class="value">临时限制中</div>
                </div>
                <div class="info-item">
                    <div class="label">限制原因</div>
                    <div class="value">' . htmlspecialchars($message) . '</div>
                </div>
            </div>

            <div class="countdown">
                <div>请等待</div>
                <div class="time" id="countdown">' . $retryAfter . '</div>
                <div class="unit">分钟后重试</div>
            </div>
        </div>

        <div class="footer">
            <p>💡 提示：如果这是误判，请稍后重试</p>
            <p style="margin-top: 8px;">系统安全防护 - Bilibili下载器</p>
        </div>
    </div>

    <script>
        let seconds = ' . $this->blockDuration . ';
        const countdownEl = document.getElementById("countdown");

        const updateCountdown = () => {
            const mins = Math.floor(seconds / 60);
            if (mins > 0) {
                countdownEl.textContent = mins;
            } else {
                countdownEl.textContent = seconds;
                document.querySelector(".countdown .unit").textContent = "秒后重试";
            }
            seconds--;

            if (seconds < 0) {
                location.reload();
            }
        };

        setInterval(updateCountdown, 1000);
    </script>
</body>
</html>';
        exit;
    }
}


