<?php

class GlobalBlockChecker {
    private $storageDir;
    private $blockDuration = 300;

    public function __construct() {
        $this->storageDir = __DIR__ . '/../tmp/conn_limit';
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

    private function getFilePath($ip) {
        $sanitizedIp = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $ip);
        return $this->storageDir . '/block_' . $sanitizedIp . '.json';
    }

    public function isBlocked() {
        $ip = $this->getClientIP();
        $filePath = $this->getFilePath($ip);

        if (!file_exists($filePath)) return false;

        $data = json_decode(file_get_contents($filePath), true);
        if (!$data) return false;

        if (time() > $data['expire']) {
            unlink($filePath);
            return false;
        }

        return [
            'blocked' => true,
            'ip' => $ip,
            'remaining' => $data['expire'] - time()
        ];
    }

    public function blockIP($ip = null) {
        if ($ip === null) {
            $ip = $this->getClientIP();
        }

        $filePath = $this->getFilePath($ip);
        $data = [
            'ip' => $ip,
            'timestamp' => time(),
            'expire' => time() + $this->blockDuration
        ];
        file_put_contents($filePath, json_encode($data));
        return true;
    }

    public function unblockIP($ip) {
        $filePath = $this->getFilePath($ip);
        if (file_exists($filePath)) {
            unlink($filePath);
            return true;
        }
        return false;
    }
}


