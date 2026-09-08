<?php
require_once __DIR__ . '/BilibiliParser.php';
require_once __DIR__ . '/DownloadManager.php';
require_once __DIR__ . '/TaskManager.php';
require_once __DIR__ . '/ConfigLoader.php';

if ($argc < 2) {
    echo "Usage: php DownloadWorker.php <task_id>\n";
    exit(1);
}

$taskId = $argv[1];

$taskManager = new BilibiliDownloader\TaskManager();
$task = $taskManager->getTask($taskId);

if (!$task) {
    echo "Task not found: $taskId\n";
    exit(1);
}

// 更新任务状态为开始
$taskManager->updateTaskStatus($taskId, 'downloading', '', ['progress' => 0]);

try {
    $config = new BilibiliDownloader\ConfigLoader();
    $parser = new BilibiliDownloader\BilibiliParser($config);
    $downloadManager = new BilibiliDownloader\DownloadManager($parser, $taskManager);
    
    $url = $task['url'];
    $videoInfo = $task['video_info'];
    $qn = $task['qn'];
    $savePath = $task['save_path'];
    $episodes = $task['episodes'];
    
    $totalEpisodes = count($episodes);
    $currentEpisode = 0;
    
    foreach ($episodes as $episode) {
        $currentEpisode++;
        $episodeProgress = ($currentEpisode - 1) / $totalEpisodes * 100;
        
        $taskManager->updateTaskStatus($taskId, "正在下载第 $currentEpisode 集", '', ['progress' => (int)$episodeProgress]);
        
        if ($videoInfo['is_bangumi']) {
            // 下载番剧集数
            $cid = $episode['cid'];
            $bvid = $videoInfo['bvid'];
            $aid = $videoInfo['aid'];
            $epId = $episode['ep_id'];
            
            $parser->downloadBangumiEpisode($bvid, $aid, $cid, $qn, $savePath, $epId, function($progress) use ($taskManager, $taskId, $totalEpisodes, $currentEpisode) {
                $overallProgress = ($currentEpisode - 1) / $totalEpisodes * 100 + ($progress / 100) * (100 / $totalEpisodes);
                $taskManager->updateTaskStatus($taskId, "正在下载第 $currentEpisode 集: $progress%", '', ['progress' => (int)$overallProgress]);
            });
        } else if ($videoInfo['is_cheese']) {
            // 下载课程集数
            $cid = $episode['cid'];
            $bvid = $videoInfo['bvid'];
            $aid = $videoInfo['aid'];
            $epId = $episode['ep_id'];
            
            $parser->downloadBangumiEpisode($bvid, $aid, $cid, $qn, $savePath, $epId, function($progress) use ($taskManager, $taskId, $totalEpisodes, $currentEpisode) {
                $overallProgress = ($currentEpisode - 1) / $totalEpisodes * 100 + ($progress / 100) * (100 / $totalEpisodes);
                $taskManager->updateTaskStatus($taskId, "正在下载第 $currentEpisode 集: $progress%", '', ['progress' => (int)$overallProgress]);
            });
        } else if ($videoInfo['is_collection']) {
            // 下载合集中的视频
            $page = $episode['page'];
            $bvid = $videoInfo['bvid'];
            $aid = $videoInfo['aid'];
            $cid = $episode['cid'];
            
            $parser->downloadVideo($bvid, $aid, $cid, $qn, $savePath, $page, function($progress) use ($taskManager, $taskId, $totalEpisodes, $currentEpisode) {
                $overallProgress = ($currentEpisode - 1) / $totalEpisodes * 100 + ($progress / 100) * (100 / $totalEpisodes);
                $taskManager->updateTaskStatus($taskId, "正在下载第 $currentEpisode 集: $progress%", '', ['progress' => (int)$overallProgress]);
            });
        } else {
            // 下载单个视频
            $bvid = $videoInfo['bvid'];
            $aid = $videoInfo['aid'];
            $cid = $videoInfo['cid'];
            
            $parser->downloadVideo($bvid, $aid, $cid, $qn, $savePath, 1, function($progress) use ($taskManager, $taskId) {
                $taskManager->updateTaskStatus($taskId, "正在下载: $progress%", '', ['progress' => (int)$progress]);
            });
        }
    }
    
    // 下载完成
$taskManager->updateTaskStatus($taskId, '下载完成', '', ['progress' => 100, 'end_time' => time()]);
    
} catch (Exception $e) {
    $taskManager->updateTaskStatus($taskId, '下载失败: ' . $e->getMessage(), '', ['progress' => 0, 'end_time' => time()]);
    echo "Error: " . $e->getMessage() . "\n";
}
?>