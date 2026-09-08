<?php

namespace BilibiliDownloader;

use Exception;

class DownloadManager {
    private $parser;
    private $taskManager;
    private $maxThreads;
    private $maxConcurrentTasks;
    private $activeTasks;
    private $taskQueue;
    
    public function __construct(BilibiliParser $parser, ?TaskManager $taskManager = null, $maxThreads = 4, $maxConcurrentTasks = 2) {
        $this->parser = $parser;
        $this->taskManager = $taskManager;
        $this->maxThreads = min($maxThreads, 16);
        $this->maxConcurrentTasks = $maxConcurrentTasks;
        $this->activeTasks = [];
        $this->taskQueue = [];
    }
    
    public function startDownload($downloadParams) {
        $videoInfo = $downloadParams['video_info'] ?? [];
        $selectedQn = $downloadParams['qn'] ?? '';
        $savePath = $downloadParams['save_path'] ?? '';
        $episodes = $downloadParams['episodes'] ?? [];
        
        if (empty($episodes)) {
            return ['success' => false, 'error' => '无选中集数'];
        }
        if (empty($savePath)) {
            return ['success' => false, 'error' => '保存路径未指定'];
        }
        if (empty($selectedQn)) {
            return ['success' => false, 'error' => '未选择清晰度'];
        }
        
        $this->taskQueue[] = $downloadParams;
        $this->processQueue();
        
        return ['success' => true, 'message' => '任务已添加到下载队列'];
    }
    
    private function processQueue() {
        while (count($this->activeTasks) < $this->maxConcurrentTasks && !empty($this->taskQueue)) {
            $downloadParams = array_shift($this->taskQueue);
            $this->executeTask($downloadParams);
        }
    }
    
    private function executeTask($downloadParams) {
        $videoInfo = $downloadParams['video_info'] ?? [];
        $selectedQn = $downloadParams['qn'] ?? '';
        $savePath = $downloadParams['save_path'] ?? '';
        $episodes = $downloadParams['episodes'] ?? [];
        $url = $downloadParams['url'] ?? '';
        
        $taskId = $downloadParams['task_id'] ?? uniqid('task_', true);
        
        $taskInfo = [
            'id' => $taskId,
            'url' => $url,
            'title' => $videoInfo['title'] ?? '未知视频',
            'save_path' => $savePath,
            'progress' => 0,
            'status' => 'downloading',
            'video_info' => $videoInfo,
            'qn' => $selectedQn,
            'episodes' => $episodes,
            'total_episodes' => count($episodes),
            'completed_episodes' => 0,
            'failed_episodes' => 0,
            'is_cancelled' => false,
            'task_start_time' => time(),
            'downloaded_episodes' => []
        ];
        
        $this->activeTasks[$taskId] = $taskInfo;
        
        if ($this->taskManager) {
            $this->taskManager->addTask($taskInfo);
        }
        
        $this->downloadEpisodes($taskId, $episodes, $videoInfo, $selectedQn, $savePath);
    }
    
    private function downloadEpisodes($taskId, $episodes, $videoInfo, $selectedQn, $savePath) {
        $totalEpisodes = count($episodes);
        $completedEpisodes = 0;
        $failedEpisodes = 0;
        
        foreach ($episodes as $idx => $ep) {
            try {
                $this->downloadEpisode($taskId, $idx, $ep, $videoInfo, $selectedQn, $savePath);
                $completedEpisodes++;
            } catch (Exception $e) {
                $failedEpisodes++;
                error_log('下载第' . ($idx+1) . '集失败：' . $e->getMessage());
            }
            
            $progress = ($completedEpisodes + $failedEpisodes) / $totalEpisodes * 100;
            $this->updateTaskProgress($taskId, $progress);
        }
        
        $this->completeTask($taskId, $completedEpisodes, $failedEpisodes);
    }
    
    private function downloadEpisode($taskId, $epIndex, $epInfo, $videoInfo, $selectedQn, $savePath) {
        $bvid = $epInfo['bvid'] ?? $videoInfo['bvid'] ?? '';
        $cid = $epInfo['cid'] ?? '';
        
        if ($videoInfo['is_bangumi']) {
            $playInfo = $this->parser->getBangumiEpisodePlayinfo($bvid, $cid, $selectedQn);
        } elseif ($videoInfo['is_cheese']) {
            $seasonId = $epInfo['season_id'] ?? $videoInfo['season_id'] ?? '';
            $epId = $epInfo['ep_id'] ?? '';
            $playInfo = $this->parser->getPlayInfo('cheese', $bvid, $cid, $videoInfo['is_tv_mode'] ?? false, $seasonId, $epId);
        } else {
            $playInfo = $this->parser->getPlayInfo($videoInfo['type'], $bvid, $cid, $videoInfo['is_tv_mode'] ?? false);
        }
        
        if (!$playInfo['success']) {
            throw new Exception($playInfo['error']);
        }
        
        $videoUrls = $playInfo['video_urls'];
        $audioUrl = $playInfo['audio_url'];
        
        if (!isset($videoUrls[$selectedQn])) {
            $selectedQn = array_keys($videoUrls)[0];
        }
        
        $videoUrl = $videoUrls[$selectedQn];
        
        $epTitle = $this->getEpisodeTitle($epInfo, $videoInfo);
        $cleanTitle = str_replace('正片_', '', $epTitle);
        $outputPath = $savePath . '/' . $this->sanitizeFilename($cleanTitle) . '.mp4';
        
        $videoPath = $this->parser->downloadFile($videoUrl, $savePath, function($progress) use ($taskId, $epIndex) {
            $this->updateEpisodeProgress($taskId, $epIndex, $progress);
        }, 'video', $bvid);
        
        $audioPath = null;
        if ($audioUrl) {
            $audioPath = $this->parser->downloadFile($audioUrl, $savePath, function($progress) use ($taskId, $epIndex) {
                $this->updateEpisodeProgress($taskId, $epIndex, 50 + $progress / 2);
            }, 'audio', $bvid);
        }
        
        $this->parser->mergeMedia($videoPath, $audioPath, $outputPath);
    }
    
    private function getEpisodeTitle($epInfo, $videoInfo) {
        if ($videoInfo['is_bangumi'] && isset($videoInfo['bangumi_info'])) {
            $season = $videoInfo['bangumi_info']['season_title'] ?? '未知季度';
            $epIdx = $epInfo['ep_index'] ?? '未知集';
            $epTitle = $epInfo['ep_title'] ?? $epInfo['title'] ?? $epInfo['name'] ?? '';
            return "{$season}_{$epIdx}_{$epTitle}";
        } else {
            $page = $epInfo['page'] ?? 0;
            $epTitle = $epInfo['title'] ?? $epInfo['ep_title'] ?? $epInfo['name'] ?? '';
            return "第{$page}集_{$epTitle}";
        }
    }
    
    private function sanitizeFilename($filename) {
        return preg_replace('/[\/\\:*?"<>|]/', '_', $filename);
    }
    
    private function updateTaskProgress($taskId, $progress) {
        if (isset($this->activeTasks[$taskId])) {
            $this->activeTasks[$taskId]['progress'] = $progress;
            if ($this->taskManager) {
                $this->taskManager->updateTaskProgress($taskId, $progress);
            }
        }
    }
    
    private function updateEpisodeProgress($taskId, $epIndex, $progress) {
        // 这里可以添加进度更新逻辑，比如发送到前端或日志
    }
    
    private function completeTask($taskId, $completedEpisodes, $failedEpisodes) {
        if (isset($this->activeTasks[$taskId])) {
            $taskInfo = $this->activeTasks[$taskId];
            $taskInfo['completed_episodes'] = $completedEpisodes;
            $taskInfo['failed_episodes'] = $failedEpisodes;
            $taskInfo['status'] = $failedEpisodes > 0 ? 'failed' : 'completed';
            $taskInfo['duration'] = time() - $taskInfo['task_start_time'] . '秒';
            
            if ($this->taskManager) {
                $this->taskManager->updateTaskStatus($taskId, $taskInfo['status'], 
                    $failedEpisodes > 0 ? "部分失败：成功{$completedEpisodes}集，失败{$failedEpisodes}集" : "成功{$completedEpisodes}集",
                    [
                        'duration' => $taskInfo['duration'],
                        'progress' => 100,
                        'completed_episodes' => $completedEpisodes,
                        'failed_episodes' => $failedEpisodes
                    ]
                );
            }
            
            unset($this->activeTasks[$taskId]);
            $this->processQueue();
        }
    }
    
    public function cancelTask($taskId) {
        if (isset($this->activeTasks[$taskId])) {
            $this->activeTasks[$taskId]['is_cancelled'] = true;
            if ($this->taskManager) {
                $this->taskManager->updateTaskStatus($taskId, 'cancelled', '任务已取消');
            }
            unset($this->activeTasks[$taskId]);
            $this->processQueue();
        }
    }
    
    public function cancelAll() {
        foreach (array_keys($this->activeTasks) as $taskId) {
            $this->cancelTask($taskId);
        }
        $this->taskQueue = [];
    }
    
    public function getActiveTasks() {
        return $this->activeTasks;
    }
    
    public function getTaskQueue() {
        return $this->taskQueue;
    }
}
?>