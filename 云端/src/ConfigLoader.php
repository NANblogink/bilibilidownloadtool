<?php

namespace BilibiliDownloader;

class ConfigLoader {
    private $apiConfig;
    private $appConfig;
    
    public function __construct() {
        $this->loadConfigs();
    }
    
    private function loadConfigs() {
        $apiConfigPath = __DIR__ . '/../config/api_config.json';
        $appConfigPath = __DIR__ . '/../config/app_config.json';
        
        if (file_exists($apiConfigPath)) {
            $this->apiConfig = json_decode(file_get_contents($apiConfigPath), true);
        } else {
            $this->apiConfig = [];
        }
        
        if (file_exists($appConfigPath)) {
            $this->appConfig = json_decode(file_get_contents($appConfigPath), true);
        } else {
            $this->appConfig = [];
        }
    }
    
    public function getApiUrl($key, $params = []) {
        if (!isset($this->apiConfig[$key])) {
            return null;
        }
        
        $url = $this->apiConfig[$key];
        foreach ($params as $param => $value) {
            $url = str_replace('{' . $param . '}', $value, $url);
        }
        
        return $url;
    }
    
    public function getAppSetting($key, $default = null) {
        return $this->appConfig[$key] ?? $default;
    }
    
    public function getQualityMap() {
        return $this->appConfig['quality_map'] ?? [];
    }
    
    public function getDefaultHeaders() {
        return [
            'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept' => 'application/json, text/plain, */*',
            'Accept-Language' => 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding' => 'gzip, deflate, br',
            'Connection' => 'keep-alive',
            'Origin' => 'https://www.bilibili.com'
        ];
    }
    
    public function getHeaders() {
        return [
            'User-Agent' => $this->appConfig['user_agent'] ?? 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer' => 'https://www.bilibili.com/',
            'Accept' => 'application/json, text/plain, */*',
            'Accept-Language' => 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection' => 'keep-alive',
            'Origin' => 'https://www.bilibili.com',
            'Pragma' => 'no-cache',
            'Cache-Control' => 'no-cache'
        ];
    }
}
?>