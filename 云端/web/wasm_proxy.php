<?php

header('Cross-Origin-Opener-Policy: same-origin');
header('Cross-Origin-Embedder-Policy: require-corp');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');


if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit;
}


$file = $_GET['file'] ?? '';
$allowedFiles = [
    '814.ffmpeg.js' => 'https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/umd/814.ffmpeg.js',
    'ffmpeg-core.js' => 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd/ffmpeg-core.js',
    'ffmpeg-core.wasm' => 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd/ffmpeg-core.wasm',
    'ffmpeg-core.worker.js' => 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd/ffmpeg-core.worker.js',
];

if (isset($allowedFiles[$file])) {
    $content = file_get_contents($allowedFiles[$file]);
    $contentType = 'application/javascript';
    if (strpos($file, '.wasm') !== false) {
        $contentType = 'application/wasm';
    }
    header('Content-Type: ' . $contentType);
    echo $content;
    exit;
}

echo 'Invalid file request';
?>