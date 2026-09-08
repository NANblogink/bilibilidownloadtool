<?php

class ConnectionLimiter {
    private $redis;
    private $maxConnections = 5;
    private $rateLimit = 30;
    private $timeWindow = 60;
    private $connectionTimeout = 30;
    private $blockDuration = 300;
    private $useRedis = true;
    
    public function __construct() {
        try {
            $this->redis = new Redis();
            $this->redis->connect('127.0.0.1', 6379, 1);
        } catch (Exception $e) {
            $this->useRedis = false;
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
    
    public function isBlocked($ip) {
        if (!$this->useRedis) return false;
        
        $blockKey = "blocked:{$ip}";
        return $this->redis->exists($blockKey);
    }
    
    public function blockIP($ip) {
        if (!$this->useRedis) return false;
        
        $blockKey = "blocked:{$ip}";
        $this->redis->setex($blockKey, $this->blockDuration, '1');
        return true;
    }
    
    public function checkRateLimit($ip) {
        if (!$this->useRedis) return true;
        
        $rateKey = "rate:{$ip}";
        $current = $this->redis->incr($rateKey);
        
        if ($current === 1) {
            $this->redis->expire($rateKey, $this->timeWindow);
        }
        
        if ($current > $this->rateLimit) {
            $this->blockIP($ip);
            return false;
        }
        
        return true;
    }
    
    public function checkConnectionLimit($ip) {
        if (!$this->useRedis) return true;
        
        $connKey = "conn:{$ip}";
        $current = $this->redis->incr($connKey);
        
        if ($current === 1) {
            $this->redis->expire($connKey, $this->connectionTimeout);
        }
        
        if ($current > $this->maxConnections) {
            $this->redis->decr($connKey);
            $this->blockIP($ip);
            return false;
        }
        
        return true;
    }
    
    public function releaseConnection($ip) {
        if (!$this->useRedis) return;
        
        $connKey = "conn:{$ip}";
        $this->redis->decr($connKey);
    }
    
    public function check() {
        $ip = $this->getClientIP();
        
        if ($this->isBlocked($ip)) {
            http_response_code(429);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode([
                'success' => false,
                'message' => 'Too many requests, please try again later',
                'retry_after' => $this->blockDuration
            ]);
            exit;
        }
        
        if (!$this->checkRateLimit($ip)) {
            http_response_code(429);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode([
                'success' => false,
                'message' => 'Rate limit exceeded, please try again later',
                'retry_after' => $this->blockDuration
            ]);
            exit;
        }
        
        if (!$this->checkConnectionLimit($ip)) {
            http_response_code(429);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode([
                'success' => false,
                'message' => 'Connection limit exceeded, please try again later',
                'retry_after' => $this->blockDuration
            ]);
            exit;
        }
        
        return $ip;
    }
}

$limiter = new ConnectionLimiter();
$clientIP = $limiter->check();
