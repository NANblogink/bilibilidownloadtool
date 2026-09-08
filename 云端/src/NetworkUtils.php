<?php

namespace BilibiliDownloader;

class NetworkUtils {
    public static function request($url, $headers = [], $cookies = [], $params = [], $method = 'GET', $timeout = 15) {
        $ch = curl_init();
        
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true); // 启用跟随重定向
        curl_setopt($ch, CURLOPT_AUTOREFERER, true);
        curl_setopt($ch, CURLOPT_HEADER, true); // 包含响应头
        curl_setopt($ch, CURLOPT_COOKIEFILE, ''); // 启用Cookie存储
        curl_setopt($ch, CURLOPT_COOKIEJAR, ''); // 启用Cookie存储
        
        // 设置请求方法
        if (strtoupper($method) === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            
            // 检查是否需要发送 JSON 格式数据
            $isJson = false;
            foreach ($headers as $key => $value) {
                if (strtolower($key) === 'content-type' && strpos(strtolower($value), 'application/json') !== false) {
                    $isJson = true;
                    break;
                }
            }
            
            if ($isJson) {
                curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($params));
            } else {
                curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params));
            }
        }
        
        if (!empty($headers)) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, self::formatHeaders($headers));
        } else {
            // 添加默认请求头
            $defaultHeaders = [
                'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer' => 'https://www.bilibili.com/',
                'Accept' => 'application/json, text/plain, */*',
                'Accept-Language' => 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection' => 'keep-alive',
                'Origin' => 'https://www.bilibili.com'
            ];
            curl_setopt($ch, CURLOPT_HTTPHEADER, self::formatHeaders($defaultHeaders));
        }
        
        // 使用传入的cookies
        $allCookies = $cookies;
        
        if (!empty($allCookies)) {
            curl_setopt($ch, CURLOPT_COOKIE, self::formatCookies($allCookies));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        
        // 分离响应头和响应体
        $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $headers = substr($response, 0, $headerSize);
        $content = substr($response, $headerSize);
        
        // 解析响应头
        $parsedHeaders = [];
        $headerLines = explode("\r\n", $headers);
        foreach ($headerLines as $line) {
            if (strpos($line, ':') !== false) {
                list($key, $value) = explode(':', $line, 2);
                $key = trim($key);
                $value = trim($value);
                if ($key === 'Set-Cookie') {
                    if (!isset($parsedHeaders[$key])) {
                        $parsedHeaders[$key] = [];
                    }
                    $parsedHeaders[$key][] = $value;
                } else {
                    $parsedHeaders[$key] = $value;
                }
            }
        }
        
        
        
        if ($error || $response === false) {
            $errorMsg = $error ? $error : '请求执行失败';
            return [false, ['error' => $errorMsg . '，URL: ' . $url]];
        }
        
        return [true, ['code' => $httpCode, 'content' => $content, 'headers' => $parsedHeaders]];
    }
    

    
    public static function post($url, $data = [], $headers = [], $cookies = [], $timeout = 15) {
        $ch = curl_init();
        
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));
        
        if (!empty($headers)) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, self::formatHeaders($headers));
        }
        
        // 使用传入的cookies
        $allCookies = $cookies;
        
        if (!empty($allCookies)) {
            curl_setopt($ch, CURLOPT_COOKIE, self::formatCookies($allCookies));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        
        
        
        if ($error) {
            return [false, ['error' => $error]];
        }
        
        return [true, ['code' => $httpCode, 'content' => $response]];
    }
    
    public static function downloadFile($url, $savePath, $headers = [], $cookies = [], $progressCallback = null) {
        $ch = curl_init();
        $fp = fopen($savePath, 'wb');
        
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, function($ch, $data) use ($fp, $progressCallback) {
            $written = fwrite($fp, $data);
            if ($progressCallback) {
                $sizeDownloaded = ftell($fp);
                $sizeTotal = curl_getinfo($ch, CURLINFO_CONTENT_LENGTH_DOWNLOAD);
                if ($sizeTotal > 0) {
                    $progress = min(100, (int)($sizeDownloaded / $sizeTotal * 100));
                    $progressCallback($progress, $sizeDownloaded);
                }
            }
            return $written;
        });
        
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        
        if (!empty($headers)) {
            curl_setopt($ch, CURLOPT_HTTPHEADER, self::formatHeaders($headers));
        }
        
        // 使用传入的cookies
        $allCookies = $cookies;
        
        if (!empty($allCookies)) {
            curl_setopt($ch, CURLOPT_COOKIE, self::formatCookies($allCookies));
        }
        
        $response = curl_exec($ch);
        $error = curl_error($ch);
        
        fclose($fp);
        
        
        if ($error) {
            return [false, $error];
        }
        
        return [true, $savePath];
    }
    
    private static function formatHeaders($headers) {
        $formatted = [];
        foreach ($headers as $key => $value) {
            $formatted[] = "$key: $value";
        }
        return $formatted;
    }
    
    private static function formatCookies($cookies) {
        $formatted = [];
        foreach ($cookies as $key => $value) {
            $formatted[] = "$key=$value";
        }
        return implode('; ', $formatted);
    }
}
?>