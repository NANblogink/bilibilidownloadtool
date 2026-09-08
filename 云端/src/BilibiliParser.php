<?php

namespace BilibiliDownloader;

class BilibiliParser {
    private $config;
    private $cookies;
    private $csrfToken;
    private $headers;
    
    public function __construct(ConfigLoader $config) {
        $this->config = $config;
        $this->headers = $config->getHeaders();
        $this->cookies = [];
        $this->csrfToken = '';
    }
    
    public function setCookies($cookies) {
        try {
            if (is_string($cookies)) {
                // 尝试解析JSON
                $parsed = json_decode($cookies, true);
                if (json_last_error() === JSON_ERROR_NONE) {
                    $cookies = $parsed;
                } else {
                    // 解析普通Cookie字符串
                    $cookies = $this->parseCookieText($cookies);
                }
            }
            
            if (is_array($cookies)) {
                // 检查是否是Cookie对象数组
                if (isset($cookies[0]) && is_array($cookies[0]) && isset($cookies[0]['name']) && isset($cookies[0]['value'])) {
                    $cookieDict = [];
                    foreach ($cookies as $item) {
                        if (isset($item['name']) && isset($item['value'])) {
                            $cookieDict[$item['name']] = $item['value'];
                        }
                    }
                    $cookies = $cookieDict;
                }
            }
            
            if (!is_array($cookies)) {
                return false;
            }
            
            if (empty($cookies)) {
                return false;
            }
            
            $this->cookies = $cookies;
            $this->csrfToken = $cookies['bili_jct'] ?? '';
            
            return true;
        } catch (\Exception $e) {
            return false;
        }
    }
    
    private function parseCookieText($cookieText) {
        $cookieDict = [];
        $pairs = explode(';', $cookieText);
        foreach ($pairs as $pair) {
            $pair = trim($pair);
            if (strpos($pair, '=') !== false) {
                list($key, $value) = explode('=', $pair, 2);
                $cookieDict[trim($key)] = trim($value);
            }
        }
        return $cookieDict;
    }
    
    public function parseMediaUrl($url) {
        $bvMatch = [];
        if (preg_match('/(BV[0-9A-Za-z]{10})/', $url, $bvMatch)) {
            return ['type' => 'video', 'id' => $bvMatch[1], 'error' => ''];
        }
        
        $cheeseMatch = [];
        if (preg_match('/cheese\/play\/ss(\d+)/i', $url, $cheeseMatch)) {
            return ['type' => 'cheese', 'id' => $cheeseMatch[1], 'error' => ''];
        }
        
        // 匹配cheese的ep格式链接
        $cheeseEpMatch = [];
        if (preg_match('/cheese\/play\/ep(\d+)/i', $url, $cheeseEpMatch)) {
            return ['type' => 'cheese', 'id' => $cheeseEpMatch[1], 'error' => ''];
        }
        
        $ssMatch = [];
        if (preg_match('/ss(\d+)/i', $url, $ssMatch)) {
            return ['type' => 'bangumi', 'id' => $ssMatch[1], 'error' => ''];
        }
        
        // 匹配番剧的ep格式链接（如 bangumi/play/ep249469）
        $bangumiEpMatch = [];
        if (preg_match('/bangumi\/play\/ep(\d+)/i', $url, $bangumiEpMatch)) {
            return ['type' => 'bangumi_ep', 'id' => $bangumiEpMatch[1], 'error' => ''];
        }
        
        $avMatch = [];
        if (preg_match('/av(\d+)/i', $url, $avMatch)) {
            return ['type' => 'av', 'id' => $avMatch[1], 'error' => ''];
        }
        
        $spaceMatch = [];
        if (preg_match('/space\.bilibili\.com\/(\d+)/i', $url, $spaceMatch)) {
            return ['type' => 'space', 'id' => $spaceMatch[1], 'error' => ''];
        }
        
        return ['type' => null, 'id' => null, 'error' => '未识别的链接格式（支持BV/ss/av号/ep号/课程链接/UP主空间）'];
    }
    
    public function parseMedia($mediaType, $mediaId, $isTvMode = false, $qn = 10000) {
        try {
            $bvid = null;
            $title = '';
            $cid = '';
            $cover = '';
            $collection = [];
            $bangumiInfo = null;
            $cheeseInfo = null;
            $seasonId = null;
            $epId = null;
            
            if ($mediaType == 'av') {
                $avData = $this->getAvInfo($mediaId);
                $mediaType = 'video';
                $bvid = $avData['bvid'];
                $cid = $avData['cid'];
                $title = $this->sanitizeFilename($avData['title']);
                $collection = $this->getCollectionInfo($bvid);
            }
            
            if ($mediaType == 'video') {
                if (!$bvid) {
                    $bvid = $mediaId;
                }
                if (!$cid) {
                    $cid = $this->getCid($mediaType, $bvid);
                }
                if (!$title || !$collection) {
                    $videoInfo = $this->getVideoMainInfo($bvid);
                    if (!$title) {
                        $title = $this->sanitizeFilename($videoInfo['title']);
                    }
                    if (!$cover) {
                        $cover = $videoInfo['pic'] ?? '';
                    }
                    if (!$collection && isset($videoInfo['pages'])) {
                        foreach ($videoInfo['pages'] as $page) {
                            $duration = $page['duration'] ?? 0;
                            $collection[] = [
                                'page' => $page['page'] ?? 0,
                                'cid' => $page['cid'] ?? 0,
                                'title' => $this->sanitizeFilename($page['part'] ?? "第{$page['page']}集"),
                                'duration' => $duration,
                                'duration_str' => $this->formatDuration($duration)
                            ];
                        }
                    } elseif (!$collection) {
                        $collection = $this->getCollectionInfo($bvid);
                    }
                }
            } elseif ($mediaType == 'bangumi') {
                $bangumiFullInfo = $this->getBangumiFullInfo($mediaId);
                $bangumiInfo = $bangumiFullInfo;
                $seasonTitle = $bangumiFullInfo['season_title'];
                $firstEp = $bangumiFullInfo['episodes'][0];
                $bvid = $firstEp['bvid'];
                $cid = $firstEp['cid'];
                $epId = $firstEp['ep_id'] ?? '';
                $firstEpTitle = $firstEp['ep_title'] ?? '第1集';
                $title = $this->sanitizeFilename($seasonTitle);
                $cover = $bangumiFullInfo['cover'] ?? '';
                // 确保返回完整的剧集信息
                $collection = $bangumiFullInfo['episodes'];
            } elseif ($mediaType == 'cheese') {
                $cheeseFullInfo = $this->getCheeseFullInfo($mediaId);
                $cheeseInfo = $cheeseFullInfo;
                $seasonTitle = $cheeseFullInfo['season_title'];
                $firstEp = $cheeseFullInfo['episodes'][0];
                $bvid = $firstEp['bvid'];
                $cid = $firstEp['cid'];
                $seasonId = $firstEp['season_id'] ?? $mediaId;
                $epId = $firstEp['ep_id'] ?? '';
                $firstEpTitle = $firstEp['ep_title'] ?? '第1集';
                $title = $this->sanitizeFilename($seasonTitle);
                $cover = $cheeseFullInfo['cover'] ?? '';
                // 确保返回完整的剧集信息
                $collection = $cheeseFullInfo['episodes'];
            } elseif ($mediaType == 'bangumi_ep') {
                // 处理番剧ep格式链接
                $epInfo = $this->getEpInfo($mediaId);
                $bvid = $epInfo['bvid'];
                $cid = $epInfo['cid'];
                $epId = $epInfo['ep_id'];
                $seasonId = $epInfo['season_id'];
                $title = $this->sanitizeFilename($epInfo['title']);
                $cover = $epInfo['cover'] ?? '';
                // 获取番剧的完整信息
                $bangumiFullInfo = $this->getBangumiFullInfo($seasonId);
                $bangumiInfo = $bangumiFullInfo;
                $collection = $bangumiFullInfo['episodes'];
            }
            
            if ($mediaType == 'cheese' || $mediaType == 'bangumi_ep') {
                $playInfo = $this->getPlayInfo($mediaType, $bvid, $cid, $isTvMode, $seasonId, $epId, $qn);
            } else {
                $playInfo = $this->getPlayInfo($mediaType, $bvid, $cid, $isTvMode, null, null, $qn);
            }
            
            if (!$playInfo['success']) {
                throw new \Exception($playInfo['error']);
            }
            
            if ($mediaType == 'cheese' && $cheeseInfo) {
                $episodes = $cheeseInfo['episodes'];
                $checkCount = min(3, count($episodes));
                $hasPermission = false;
                
                for ($i = 0; $i < $checkCount; $i++) {
                    $ep = $episodes[$i];
                    try {
                        $epBvid = $ep['bvid'] ?? '';
                        $epCid = $ep['cid'] ?? '';
                        $epSeasonId = $ep['season_id'] ?? $mediaId;
                        $epEpId = $ep['ep_id'] ?? '';
                        $epPlayInfo = $this->getPlayInfo('cheese', $epBvid, $epCid, $isTvMode, $epSeasonId, $epEpId);
                        if ($epPlayInfo['success']) {
                            $hasPermission = true;
                            break;
                        }
                    } catch (\Exception $e) {
                        // 忽略错误，继续检查
                    }
                }
                
                foreach ($episodes as &$ep) {
                    $ep['permission_denied'] = !$hasPermission;
                    $ep['title'] = $ep['ep_title'] ?? $ep['title'] ?? "第{$ep['ep_index']}集";
                    if (!$hasPermission) {
                        $ep['title'] .= "（权限不足）";
                    }
                }
            } elseif (($mediaType == 'bangumi' || $mediaType == 'bangumi_ep') && $bangumiInfo) {
                $episodes = $bangumiInfo['episodes'];
                $checkCount = min(3, count($episodes));
                $hasPermission = false;
                
                for ($i = 0; $i < $checkCount; $i++) {
                    $ep = $episodes[$i];
                    try {
                        $epBvid = $ep['bvid'] ?? '';
                        $epCid = $ep['cid'] ?? '';
                        $epPlayInfo = $this->getPlayInfo('bangumi', $epBvid, $epCid, $isTvMode);
                        if ($epPlayInfo['success']) {
                            $hasPermission = true;
                            break;
                        }
                    } catch (\Exception $e) {
                        // 忽略错误，继续检查
                    }
                }
                
                foreach ($episodes as &$ep) {
                    $ep['permission_denied'] = !$hasPermission;
                    $ep['title'] = $ep['ep_title'] ?? $ep['title'] ?? "第{$ep['ep_index']}集";
                    if (!$hasPermission) {
                        $ep['title'] .= "（权限不足）";
                    }
                }
            } elseif ($mediaType == 'video' && $collection) {
                foreach ($collection as &$ep) {
                    $ep['permission_denied'] = false;
                    $ep['title'] = $ep['title'] ?? "第{$ep['page']}集";
                }
            }
            
            // 获取视频详细信息，包括UP主和时长
            $author = '未知UP主';
            $duration = '未知时长';
            $description = '';
            
            try {
                $videoInfo = $this->getVideoMainInfo($bvid);
                if ($videoInfo) {
                    // 提取UP主信息
                    if (isset($videoInfo['owner'])) {
                        if (is_array($videoInfo['owner'])) {
                            $author = $videoInfo['owner']['name'] ?? '未知UP主';
                        }
                    }
                    
                    // 提取时长信息
                    if (isset($videoInfo['duration'])) {
                        $duration = $this->formatDuration($videoInfo['duration']);
                    }
                    
                    // 提取视频描述
                    if (isset($videoInfo['desc'])) {
                        $description = $videoInfo['desc'];
                    }
                }
            } catch (\Exception $e) {
                // 如果获取视频详细信息失败，使用默认值
            }
            
            return [
                'success' => true,
                'type' => $mediaType,
                'title' => $title,
                'cover' => $cover,
                'bvid' => $bvid,
                'cid' => $cid,
                'author' => $author,
                'duration' => $duration,
                'description' => $description,
                'qualities' => $playInfo['qualities'],
                'video_urls' => $playInfo['video_urls'],
                'audio_url' => $playInfo['audio_url'],
                'flv_qns' => $playInfo['flv_qns'] ?? [],
                'is_tv_mode' => $isTvMode,
                'is_vip' => $playInfo['is_vip'],
                'has_hevc' => $playInfo['has_hevc'],
                'collection' => $collection,
                'is_collection' => count($collection) > 1,
                'bangumi_info' => $bangumiInfo,
                'cheese_info' => $cheeseInfo,
                'is_bangumi' => $mediaType == 'bangumi',
                'is_cheese' => $mediaType == 'cheese',
                'key_id' => $playInfo['key_id'] ?? ''
            ];
        } catch (\Exception $e) {
            return [
                'success' => false,
                'error' => $e->getMessage()
            ];
        }
    }
    
    private function getAvInfo($aid) {
        $url = $this->config->getApiUrl('av_info_api', ['aid' => $aid]);
        if (!$url) {
            throw new \Exception('API配置错误');
        }
        
        list($success, $result) = NetworkUtils::request($url, $this->headers, $this->cookies);
        if (!$success) {
            throw new \Exception('av号信息获取失败：' . $result['error']);
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            throw new \Exception('av号信息获取失败：' . ($data['message'] ?? '未知错误'));
        }
        
        if (isset($data['data'])) {
            return $data['data'];
        } elseif (isset($data['result'])) {
            return $data['result'];
        } else {
            throw new \Exception('API返回格式错误');
        }
    }
    
    private function getBangumiFullInfo($ssid) {
        $url = $this->config->getApiUrl('bangumi_section_api', ['ssid' => $ssid]);
        if (!$url) {
            throw new \Exception('API配置错误');
        }
        
        $fullUrl = $url;
        
        list($success, $result) = NetworkUtils::request($fullUrl, $this->headers, $this->cookies);
        if (!$success) {
            throw new \Exception('番剧API请求失败：' . $result['error']);
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            throw new \Exception('番剧API错误：' . ($data['message'] ?? '未知错误') . '，响应内容：' . substr($result['content'], 0, 200));
        }
        
        $resultData = $data['result'] ?? $data['data'] ?? [];
        $episodes = [];
        
        // 尝试从不同位置获取剧集信息，符合API文档结构
        if (isset($resultData['episodes'])) {
            $episodes = $resultData['episodes'];
        } elseif (isset($resultData['main_section']['episodes'])) {
            $episodes = $resultData['main_section']['episodes'];
        } elseif (isset($resultData['sections'])) {
            foreach ($resultData['sections'] as $section) {
                if (isset($section['episodes']) && $section['episodes']) {
                    $episodes = $section['episodes'];
                    break;
                }
            }
        } elseif (isset($resultData['ep_list'])) {
            $episodes = $resultData['ep_list'];
        }
        
        if (!$episodes) {
            throw new \Exception('API未返回剧集数据，返回结构：' . json_encode(array_keys($resultData)));
        }
        
        $seasonTitle = '未知番剧';
        if (isset($resultData['title'])) {
            $seasonTitle = $resultData['title'];
        } elseif (isset($resultData['main_section']['title'])) {
            $seasonTitle = $resultData['main_section']['title'];
        } elseif (isset($resultData['season_title'])) {
            $seasonTitle = $resultData['season_title'];
        }
        $seasonTitle = $this->sanitizeFilename($seasonTitle);
        $seasonId = $ssid;
        
        $bangumiEpisodes = [];
        foreach ($episodes as $idx => $ep) {
            $epType = $ep['type_name'] ?? '';
            $epNum = $ep['ep'] ?? $ep['index'] ?? ($idx + 1);
            
            if (in_array($epType, ['SP', 'OVA', '剧场版'])) {
                $epIndex = "{$epType}{$epNum}";
            } else {
                $epIndex = "第{$epNum}集";
            }
            
            $titleCandidates = [
                $ep['long_title'] ?? '',
                $ep['sub_title'] ?? '',
                $ep['title'] ?? '',
                $ep['part'] ?? '',
                "第{$epNum}集"
            ];
            
            $actualTitle = '';
            foreach ($titleCandidates as $t) {
                if ($t) {
                    $actualTitle = $t;
                    break;
                }
            }
            
            $actualTitle = str_replace('正片', '', $actualTitle);
            $actualTitle = str_replace('_', ' ', $actualTitle);
            $actualTitle = trim($actualTitle);
            if (!$actualTitle) {
                $actualTitle = "第{$epNum}集";
            }
            
            $bvid = $ep['bvid'] ?? $ep['aid'] ?? '';
            if (!$bvid) {
                $bvid = "ep{$ep['id']}";
            }
            
            $bangumiEpisodes[] = [
                'ep_id' => $ep['id'] ?? '',
                'bvid' => $bvid,
                'cid' => $ep['cid'] ?? '',
                'ep_index' => $epIndex,
                'ep_title' => $this->sanitizeFilename($actualTitle),
                'duration' => $ep['duration'] ?? 0,
                'duration_str' => $this->formatDuration($ep['duration'] ?? 0)
            ];
        }
        
        return [
            'success' => true,
            'season_title' => $seasonTitle,
            'season_id' => $seasonId,
            'total_episodes' => count($bangumiEpisodes),
            'episodes' => $bangumiEpisodes
        ];
    }
    
    private function getEpInfo($epId) {
        // 通过ep_id获取番剧ep信息 - 使用正确的API
        $epUrl = "https://api.bilibili.com/pgc/view/web/season?ep_id={$epId}";
        $headers = $this->headers;
        $headers['Referer'] = 'https://www.bilibili.com/bangumi/play/ep' . $epId;

        list($success, $result) = NetworkUtils::request($epUrl, $headers, $this->cookies);
        if (!$success) {
            throw new \Exception('获取番剧EP信息失败：' . $result['error']);
        }

        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            throw new \Exception('番剧EP API错误：' . ($data['message'] ?? '未知错误') . '，响应：' . substr($result['content'], 0, 500));
        }

        // API返回的数据在 result 字段中
        $epData = $data['result'] ?? $data['data'] ?? [];

        // 从season信息中提取当前ep的信息
        $currentEp = null;
        $episodes = $epData['episodes'] ?? [];

        // 尝试找到匹配的ep
        foreach ($episodes as $ep) {
            $epIdField = $ep['id'] ?? null;
            $epEpIdField = $ep['ep_id'] ?? null;
            if ($epIdField == $epId || $epEpIdField == $epId) {
                $currentEp = $ep;
                break;
            }
        }

        if (!$currentEp && !empty($episodes)) {
            $currentEp = $episodes[0];
        }

        if (!$currentEp) {
            throw new \Exception('未找到对应的剧集信息，API返回：' . substr($result['content'], 0, 200));
        }

        return [
            'bvid' => $currentEp['bvid'] ?? '',
            'cid' => $currentEp['cid'] ?? '',
            'ep_id' => $epId,
            'season_id' => $epData['season_id'] ?? '',
            'title' => $currentEp['title'] ?? $epData['title'] ?? '未知番剧',
            'cover' => $currentEp['cover'] ?? $epData['cover'] ?? ''
        ];
    }
    
    private function getCheeseFullInfo($id) {
        // 检查是否是ep_id格式（通常ep_id比season_id大很多）
        if (strlen($id) > 6) {
            // 尝试通过ep_id获取season_id
            $epUrl = "https://api.bilibili.com/pugv/view/web/episode?ep_id={$id}";
            $headers = $this->headers;
            $headers['Referer'] = 'https://www.bilibili.com/cheese/play/ep' . $id;
            
            list($success, $result) = NetworkUtils::request($epUrl, $headers, $this->cookies);
            if ($success) {
                $data = json_decode($result['content'], true);
                if ($data['code'] == 0 && isset($data['data'])) {
                    // 直接返回episode API的数据
                    $epData = $data['data'];
                    $seasonId = $epData['season_id'] ?? $id;
                    $seasonTitle = $epData['season_title'] ?? '未知课程';
                    $bvid = $epData['bvid'] ?? '';
                    $cid = $epData['cid'] ?? '';
                    
                    $cheeseEpisodes = [
                        [
                            'ep_id' => $id,
                            'season_id' => $seasonId,
                            'bvid' => $bvid,
                            'cid' => $cid,
                            'ep_index' => '第1集',
                            'ep_title' => $epData['title'] ?? '未知剧集',
                            'duration' => $epData['duration'] ?? 0,
                            'duration_str' => $this->formatDuration($epData['duration'] ?? 0)
                        ]
                    ];
                    
                    return [
                        'success' => true,
                        'season_title' => $this->sanitizeFilename($seasonTitle),
                        'season_id' => $seasonId,
                        'total_episodes' => 1,
                        'episodes' => $cheeseEpisodes
                    ];
                }
            }
            // 如果episode API失败，尝试直接使用id作为season_id
            $ssid = $id;
        } else {
            // 直接使用id作为season_id
            $ssid = $id;
        }
        
        $url = $this->config->getApiUrl('cheese_info_api', ['ssid' => $ssid]);
        // 如果API配置不存在，使用默认的课程信息API URL
        if (!$url) {
            $url = "https://api.bilibili.com/pugv/view/web/season?season_id={$ssid}";
        }
        
        $headers = $this->headers;
        $headers['Referer'] = 'https://www.bilibili.com/cheese/play/ss' . $ssid;
        
        list($success, $result) = NetworkUtils::request($url, $headers, $this->cookies);
        if (!$success) {
            throw new \Exception('课程API请求失败：' . $result['error'] . '，URL: ' . $url);
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            // 尝试使用ep_id直接获取课程信息
            if (strlen($id) > 6) {
                $altUrl = "https://api.bilibili.com/pugv/view/web/episode?ep_id={$id}";
                list($altSuccess, $altResult) = NetworkUtils::request($altUrl, $headers, $this->cookies);
                if ($altSuccess) {
                    $altData = json_decode($altResult['content'], true);
                    if ($altData['code'] == 0 && isset($altData['data'])) {
                        // 从ep信息构建课程信息
                        $epData = $altData['data'];
                        $seasonId = $epData['season_id'] ?? $id;
                        $seasonTitle = $epData['season_title'] ?? '未知课程';
                        $bvid = $epData['bvid'] ?? '';
                        $cid = $epData['cid'] ?? '';
                        
                        $cheeseEpisodes = [
                            [
                                'ep_id' => $id,
                                'season_id' => $seasonId,
                                'bvid' => $bvid,
                                'cid' => $cid,
                                'ep_index' => '第1集',
                                'ep_title' => $epData['title'] ?? '未知剧集',
                                'duration' => $epData['duration'] ?? 0,
                                'duration_str' => $this->formatDuration($epData['duration'] ?? 0)
                            ]
                        ];
                        
                        return [
                            'success' => true,
                            'season_title' => $this->sanitizeFilename($seasonTitle),
                            'season_id' => $seasonId,
                            'total_episodes' => 1,
                            'episodes' => $cheeseEpisodes
                        ];
                    }
                }
            }
            throw new \Exception('课程API错误：' . ($data['message'] ?? '未知错误') . '，URL: ' . $url);
        }
        
        // 尝试从不同位置获取数据，符合API文档结构
        $dataSource = $data['data'] ?? $data['result'] ?? [];
        $episodes = [];
        
        if (isset($dataSource['episodes'])) {
            $episodes = $dataSource['episodes'];
        } elseif (isset($dataSource['sections'])) {
            foreach ($dataSource['sections'] as $section) {
                if (isset($section['episodes']) && $section['episodes']) {
                    $episodes = $section['episodes'];
                    break;
                }
            }
        }
        
        if (!$episodes) {
            throw new \Exception('API未返回剧集数据');
        }
        
        $seasonTitle = $dataSource['title'] ?? '未知课程';
        $seasonTitle = $this->sanitizeFilename($seasonTitle);
        $seasonId = $ssid;
        
        $cheeseEpisodes = [];
        foreach ($episodes as $idx => $ep) {
            $epNum = $ep['index'] ?? $ep['ep'] ?? ($idx + 1);
            $epIndex = "第{$epNum}集";
            
            $title = $ep['title'] ?? $ep['part'] ?? "第{$epNum}集";
            $title = trim($title);
            if (!$title) {
                $title = "第{$epNum}集";
            }
            
            $bvid = $ep['bvid'] ?? $ep['aid'] ?? '';
            if (!$bvid && isset($ep['aid'])) {
                $bvid = "av{$ep['aid']}";
            }
            
            $cheeseEpisodes[] = [
                'ep_id' => $ep['id'] ?? '',
                'season_id' => $ssid,
                'bvid' => $bvid,
                'cid' => $ep['cid'] ?? '',
                'ep_index' => $epIndex,
                'ep_title' => $this->sanitizeFilename($title),
                'duration' => $ep['duration'] ?? 0,
                'duration_str' => $this->formatDuration($ep['duration'] ?? 0)
            ];
        }
        
        return [
            'success' => true,
            'season_title' => $seasonTitle,
            'season_id' => $seasonId,
            'total_episodes' => count($cheeseEpisodes),
            'episodes' => $cheeseEpisodes
        ];
    }
    
    private function getCid($mediaType, $mediaId, $page = 1) {
        if ($mediaType == 'video') {
            $url = $this->config->getApiUrl('cid_api', ['bvid' => $mediaId]);
            if ($url) {
                list($success, $result) = NetworkUtils::request($url, $this->headers, $this->cookies);
                if ($success) {
                    $data = json_decode($result['content'], true);
                    if ($data['code'] == 0) {
                        if (isset($data['data'])) {
                            $pagesData = $data['data'];
                        } elseif (isset($data['result'])) {
                            $pagesData = $data['result'];
                        } else {
                            throw new \Exception('API返回格式错误');
                        }
                        
                        if (is_array($pagesData) && count($pagesData) >= $page) {
                            return strval($pagesData[$page - 1]['cid']);
                        }
                    }
                }
            }
            
            $videoInfoUrl = $this->config->getApiUrl('video_info_api', ['bvid' => $mediaId]);
            if (!$videoInfoUrl) {
                throw new \Exception('API配置错误：video_info_api未配置');
            }
            list($success, $result) = NetworkUtils::request($videoInfoUrl, $this->headers, $this->cookies);
            if (!$success) {
                throw new \Exception('视频信息API获取失败：' . $result['error']);
            }
            
            $data = json_decode($result['content'], true);
            if ($data['code'] != 0) {
                throw new \Exception('视频信息API返回错误：' . ($data['message'] ?? '未知错误'));
            }
            
            if (isset($data['data'])) {
                $videoData = $data['data'];
            } elseif (isset($data['result'])) {
                $videoData = $data['result'];
            } else {
                throw new \Exception('API返回格式错误');
            }
            
            if (isset($videoData['cid'])) {
                return strval($videoData['cid']);
            }
            
            if (isset($videoData['pages']) && is_array($videoData['pages']) && count($videoData['pages']) >= $page) {
                return strval($videoData['pages'][$page - 1]['cid']);
            }
            
            throw new \Exception('API未返回CID数据');
        } elseif ($mediaType == 'bangumi') {
            $bangumiInfo = $this->getBangumiFullInfo($mediaId);
            if ($bangumiInfo['episodes']) {
                return strval($bangumiInfo['episodes'][0]['cid']);
            }
            throw new \Exception('未找到番剧CID');
        } elseif ($mediaType == 'cheese') {
            $cheeseInfo = $this->getCheeseFullInfo($mediaId);
            if ($cheeseInfo['episodes']) {
                return strval($cheeseInfo['episodes'][0]['cid']);
            }
            throw new \Exception('未找到课程CID');
        } else {
            throw new \Exception('不支持的媒体类型：' . $mediaType);
        }
    }
    
    public function getFavorites($mediaId, $page = 1, $getAll = false) {
        try {
            // 构建请求URL
            $url = "https://api.bilibili.com/x/v3/fav/resource/list";
            
            // 构建请求参数
            $params = [
                'media_id' => $mediaId,
                'ps' => 20, // API限制最大为20
                'pn' => $page,
                'platform' => 'web'
            ];
            
            // 确保cookies是字符串格式
            $cookies = $this->cookies;
            if (is_array($cookies)) {
                $cookieStr = '';
                foreach ($cookies as $key => $value) {
                    $cookieStr .= $key . '=' . $value . '; ';
                }
                $cookies = rtrim($cookieStr, '; ');
            }
            
            // 发送请求
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $url . '?' . http_build_query($params));
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            $headerList = [];
            foreach ($this->headers as $k => $v) {
                $headerList[] = "$k: $v";
            }
            $headerList[] = 'Cookie: ' . $cookies;
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headerList);
            curl_setopt($ch, CURLOPT_TIMEOUT, 10);
            // 忽略SSL证书验证（解决本地证书问题）
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
            
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $error = curl_error($ch);
            
            
            if ($error) {
                throw new \Exception('获取收藏夹内容失败：' . $error);
            }
            
            $data = json_decode($response, true);
            if (isset($data['code']) && $data['code'] != 0) {
                throw new \Exception('获取收藏夹内容失败：' . ($data['message'] ?? '未知错误'));
            }
            
            // 处理数据
            $resultData = $data['data'] ?? [];
            $medias = $resultData['medias'] ?? [];
            $hasMore = $resultData['has_more'] ?? false;
            
            $collectionItems = [];
            foreach ($medias as $item) {
                // 只处理类型为2的视频稿件
                if ($item['type'] == 2) {
                    $collectionItems[] = [
                        'id' => $item['id'] ?? '',
                        'type' => 'video',
                        'title' => $item['title'] ?? '未知内容',
                        'cover' => $item['cover'] ?? '',
                        'bvid' => $item['bv_id'] ?? $item['bvid'] ?? '',
                        'aid' => $item['id'] ?? '',
                        'up_name' => $item['upper']['name'] ?? '未知UP主',
                        'duration' => $item['duration'] ?? 0,
                        'fav_time' => $item['fav_time'] ?? 0
                    ];
                }
            }
            
            // 如果需要获取所有内容
            if ($getAll && $hasMore) {
                $allItems = $collectionItems;
                $currentPage = $page + 1;
                
                while (true) {
                    $params['pn'] = $currentPage;
                    
                    // 发送请求
                    $ch = curl_init();
                    curl_setopt($ch, CURLOPT_URL, $url . '?' . http_build_query($params));
                    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                    $headerList = [];
                    foreach ($this->headers as $k => $v) {
                        $headerList[] = "$k: $v";
                    }
                    $headerList[] = 'Cookie: ' . $cookies;
                    curl_setopt($ch, CURLOPT_HTTPHEADER, $headerList);
                    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
                    // 忽略SSL证书验证（解决本地证书问题）
                    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                    curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
                    
                    $response = curl_exec($ch);
                    $error = curl_error($ch);
                    
                    
                    if ($error) {
                        throw new \Exception('获取收藏夹内容失败：' . $error);
                    }
                    
                    $data = json_decode($response, true);
                    if (isset($data['code']) && $data['code'] != 0) {
                        throw new \Exception('获取收藏夹内容失败：' . ($data['message'] ?? '未知错误'));
                    }
                    
                    $pageData = $data['data'] ?? [];
                    $pageMedias = $pageData['medias'] ?? [];
                    $hasMore = $pageData['has_more'] ?? false;
                    
                    foreach ($pageMedias as $item) {
                        if ($item['type'] == 2) {
                            $allItems[] = [
                                'id' => $item['id'] ?? '',
                                'type' => 'video',
                                'title' => $item['title'] ?? '未知内容',
                                'cover' => $item['cover'] ?? '',
                                'bvid' => $item['bv_id'] ?? $item['bvid'] ?? '',
                                'aid' => $item['id'] ?? '',
                                'up_name' => $item['upper']['name'] ?? '未知UP主',
                                'duration' => $item['duration'] ?? 0,
                                'fav_time' => $item['fav_time'] ?? 0
                            ];
                        }
                    }
                    
                    if (!$hasMore) {
                        break;
                    }
                    
                    $currentPage++;
                    // 避免请求过快被封
                    usleep(500000); // 0.5秒
                }
                
                return [
                    'items' => $allItems,
                    'has_more' => false,
                    'total' => count($allItems)
                ];
            } else {
                // 从API响应中获取真实的收藏夹内容数量
                $total = 0;
                if (isset($resultData['info']) && isset($resultData['info']['media_count'])) {
                    $total = $resultData['info']['media_count'];
                } else {
                    $total = count($collectionItems);
                }
                return [
                    'items' => $collectionItems,
                    'has_more' => $hasMore,
                    'total' => $total
                ];
            }
        } catch (\Exception $e) {
            throw $e;
        }
    }
    
    public function getDanmaku($cid) {
        try {
            $url = "https://api.bilibili.com/x/v1/dm/list.so?oid={$cid}";
            
            $headers = [
                'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer' => 'https://www.bilibili.com/'
            ];
            
            list($success, $result) = NetworkUtils::request($url, $headers, [], [], 'GET');
            if (!$success) {
                throw new \Exception('获取弹幕失败：' . $result['error']);
            }
            
            // 解析XML格式的弹幕
            $content = $result['content'];
            
            // 处理编码问题
            if (preg_match('/<弹幕类型[^>]*>/', $content)) {
                $content = mb_convert_encoding($content, 'UTF-8', 'GBK');
            }
            
            $danmakuList = [];
            
            // 使用正则表达式解析弹幕
            if (preg_match_all('/<d p="([^"]+)">([^<]+)<\/d>/', $content, $matches, PREG_SET_ORDER)) {
                foreach ($matches as $match) {
                    $danmakuList[] = [
                        'time' => floatval(explode(',', $match[1])[0]),
                        'text' => $match[2]
                    ];
                }
            }
            
            return [
                'cid' => $cid,
                'count' => count($danmakuList),
                'danmaku' => $danmakuList
            ];
        } catch (\Exception $e) {
            throw $e;
        }
    }
    
    public function getUserFavoritesList() {
        try {
            // 首先获取用户信息以获取mid
            $userInfo = $this->getUserInfo();
            if (!$userInfo || !isset($userInfo['mid'])) {
                throw new \Exception('获取用户信息失败，无法获取收藏夹');
            }
            
            $mid = $userInfo['mid'];
            
            // 获取用户收藏夹列表 - 使用正确的API
            $url = "https://api.bilibili.com/x/v3/fav/folder/created/list-all";
            
            $headers = [
                'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer' => 'https://www.bilibili.com/',
                'Origin' => 'https://www.bilibili.com'
            ];
            
            // 确保cookies是字符串格式
            $cookies = $this->cookies;
            if (is_array($cookies)) {
                $cookieStr = '';
                foreach ($cookies as $key => $value) {
                    $cookieStr .= $key . '=' . $value . '; ';
                }
                $cookies = rtrim($cookieStr, '; ');
            }
            
            // 发送请求获取收藏夹
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $url . '?up_mid=' . $mid . '&platform=web');
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            $headerList = [];
            foreach ($headers as $k => $v) {
                $headerList[] = "$k: $v";
            }
            $headerList[] = 'Cookie: ' . $cookies;
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headerList);
            curl_setopt($ch, CURLOPT_TIMEOUT, 10);
            // 忽略SSL证书验证（解决本地证书问题）
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
            
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $error = curl_error($ch);
            
            
            if ($error) {
                throw new \Exception('获取收藏夹列表失败：' . $error);
            }
            
            $data = json_decode($response, true);
            
            // 某些情况下API会返回-6或-352表示需要登录
            if (isset($data['code']) && $data['code'] != 0) {
                $msg = $data['message'] ?? '未知错误';
                if ($data['code'] == -6 || $data['code'] == -352) {
                    throw new \Exception('登录状态已过期，请重新登录');
                }
                throw new \Exception('获取收藏夹列表失败：' . $msg);
            }
            
            $favoritesList = [];
            $listData = $data['data'] ?? [];
            
            if (isset($listData['list']) && is_array($listData['list'])) {
                foreach ($listData['list'] as $item) {
                    $favoritesList[] = [
                        'id' => $item['id'] ?? '',
                        'title' => $item['title'] ?? '未命名收藏夹',
                        'media_count' => $item['media_count'] ?? 0,
                        'cover' => $item['cover'] ?? ''
                    ];
                }
            }
            
            return [
                'list' => $favoritesList,
                'count' => count($favoritesList)
            ];
        } catch (\Exception $e) {
            throw $e;
        }
    }
    
    /**
     * 获取收藏夹内容
     */
    public function getFavoritesContent($favId) {
        try {
            // 构建请求URL
            $url = "https://api.bilibili.com/x/v3/fav/resource/list";
            
            // 构建请求参数
            $params = [
                'media_id' => $favId,
                'pn' => 1,
                'ps' => 20,
                'keyword' => '',
                'order' => 'mtime',
                'type' => 0,
                'tid' => 0,
                'platform' => 'web'
            ];
            
            // 构建请求头
            $headerList = $this->config->getDefaultHeaders();
            
            // 添加Cookie
            if (!empty($this->cookies)) {
                // 确保cookies是字符串格式
                $cookies = $this->cookies;
                if (is_array($cookies)) {
                    $cookieStr = '';
                    foreach ($cookies as $key => $value) {
                        $cookieStr .= $key . '=' . $value . '; ';
                    }
                    $cookies = rtrim($cookieStr, '; ');
                }
                $headerList[] = 'Cookie: ' . $cookies;
            }
            
            // 添加Referer头
            $headerList[] = 'Referer: https://www.bilibili.com/';
            
            // 构建完整URL
            $fullUrl = $url . '?' . http_build_query($params);
            
            // 发送请求
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $fullUrl);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headerList);
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
            curl_setopt($ch, CURLOPT_TIMEOUT, 15);
            
            $response = curl_exec($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            
            if (curl_errno($ch)) {
                $error = curl_error($ch);
                throw new \Exception('请求错误：' . $error);
            }
            
            if ($httpCode != 200) {
                throw new \Exception('HTTP错误：' . $httpCode);
            }
            
            // 解析响应
            $data = json_decode($response, true);
            
            if (!$data) {
                throw new \Exception('响应解析失败');
            }
            
            if (isset($data['code']) && $data['code'] != 0) {
                $msg = $data['message'] ?? '未知错误';
                throw new \Exception('获取收藏夹内容失败：' . $msg);
            }
            
            $videosList = [];
            $listData = $data['data'] ?? [];
            
            if (isset($listData['medias']) && is_array($listData['medias'])) {
                foreach ($listData['medias'] as $item) {
                    $videosList[] = [
                        'bvid' => $item['bvid'] ?? '',
                        'aid' => $item['aid'] ?? '',
                        'title' => $item['title'] ?? '未命名视频',
                        'cover' => $item['cover'] ?? '',
                        'owner' => [
                            'mid' => $item['upper']['mid'] ?? '',
                            'name' => $item['upper']['name'] ?? '未知UP主'
                        ],
                        'duration' => $item['duration'] ?? 0,
                        'view' => $item['cnt_info']['play'] ?? 0,
                        'danmaku' => $item['cnt_info']['danmaku'] ?? 0
                    ];
                }
            }
            
            return $videosList;
            
        } catch (\Exception $e) {
            throw $e;
        }
    }
    
    public function getSpaceInfo($mid) {
        try {
            // 1. 先使用第一个API获取UP主基本信息: https://api.bilibili.com/x/web-interface/card
            $upName = "UP主{$mid}";
            
            $url1 = "https://api.bilibili.com/x/web-interface/card";
            $params1 = ['mid' => $mid];
            
            $headers1 = [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer: https://space.bilibili.com/' . $mid,
                'Accept: application/json, text/plain, */*',
                'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
                'Connection: keep-alive',
                'Cache-Control: no-cache'
            ];
            
            // 确保cookies是字符串格式
            $cookies = $this->cookies;
            if (is_array($cookies)) {
                $cookieStr = '';
                foreach ($cookies as $key => $value) {
                    $cookieStr .= $key . '=' . $value . '; ';
                }
                $cookies = rtrim($cookieStr, '; ');
            }
            if ($cookies) {
                $headers1[] = 'Cookie: ' . $cookies;
            }
            
            $ch1 = curl_init();
            curl_setopt($ch1, CURLOPT_URL, $url1 . '?' . http_build_query($params1));
            curl_setopt($ch1, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch1, CURLOPT_HTTPHEADER, $headers1);
            curl_setopt($ch1, CURLOPT_TIMEOUT, 15);
            curl_setopt($ch1, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch1, CURLOPT_SSL_VERIFYHOST, false);
            $response1 = curl_exec($ch1);
            $httpCode1 = curl_getinfo($ch1, CURLINFO_HTTP_CODE);
            
            
            if ($httpCode1 == 200 && !empty($response1)) {
                $data1 = json_decode($response1, true);
                if ($data1 && isset($data1['code']) && $data1['code'] == 0 && isset($data1['data']['card']['name'])) {
                    $upName = $data1['data']['card']['name'];
                }
            }
            
            // 2. 使用移动端 API 获取视频列表: https://api.bilibili.com/x/space/arc/search
            $url2 = "https://api.bilibili.com/x/space/arc/search";
            $params2 = [
                'mid' => $mid,
                'pn' => 1,
                'ps' => 30,
                'order' => 'pubdate'
            ];
            
            // 使用移动端 User-Agent (这是关键！)
            $headers2 = [
                'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Referer: https://m.bilibili.com/space/' . $mid,
                'Accept: application/json, text/plain, */*',
                'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
                'Connection: keep-alive',
                'Cache-Control: no-cache',
                'Origin: https://m.bilibili.com'
            ];
            
            $ch2 = curl_init();
            curl_setopt($ch2, CURLOPT_URL, $url2 . '?' . http_build_query($params2));
            curl_setopt($ch2, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch2, CURLOPT_HTTPHEADER, $headers2);
            curl_setopt($ch2, CURLOPT_TIMEOUT, 15);
            curl_setopt($ch2, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch2, CURLOPT_SSL_VERIFYHOST, false);
            
            // 添加移动端所需的 cookies
            $cookieStr2 = 'buvid3=7B0F6C90-7F6A-4B1D-8B8F-7B0F6C907F6A12345infoc; ';
            $cookieStr2 .= 'bili_jct=1234567890abcdef1234567890abcdef; ';
            $cookieStr2 .= 'DedeUserID=123456789; ';
            $cookieStr2 .= 'DedeUserID__ckMd5=1234567890abcdef; ';
            $cookieStr2 .= 'sid=1234567890abcdef';
            if ($cookies) {
                $cookieStr2 .= '; ' . $cookies;
            }
            curl_setopt($ch2, CURLOPT_COOKIE, $cookieStr2);
            
            $response2 = curl_exec($ch2);
            $httpCode2 = curl_getinfo($ch2, CURLINFO_HTTP_CODE);
            $error2 = curl_error($ch2);
            
            
            $archives = [];
            
            if ($httpCode2 == 200 && !empty($response2)) {
                $data2 = json_decode($response2, true);
                if ($data2 && isset($data2['code']) && $data2['code'] == 0) {
                    if (isset($data2['data']['list']['vlist']) && is_array($data2['data']['list']['vlist'])) {
                        foreach ($data2['data']['list']['vlist'] as $video) {
                            $archives[] = [
                                'bvid' => $video['bvid'] ?? '',
                                'title' => $video['title'] ?? '',
                                'play' => $video['play'] ?? 0,
                                'length' => $video['length'] ?? '',
                                'created' => $video['created'] ?? 0
                            ];
                        }
                    }
                }
            }
            
            // 构建返回数据
            $spaceInfo = [
                'mid' => $mid,
                'name' => $upName,
                'follower' => 0,
                'archives' => $archives
            ];
            
            return $spaceInfo;
        } catch (\Exception $e) {
            // 如果出错，返回至少包含mid和名称的基本信息
            return [
                'mid' => $mid,
                'name' => "UP主{$mid}",
                'follower' => 0,
                'archives' => []
            ];
        }
    }
    
    private function getSpaceTopVideo($mid) {
        $url = "https://api.bilibili.com/x/space/top/arc";
        $params = ['vmid' => $mid];
        
        $cookies = $this->cookies;
        if (is_array($cookies)) {
            $cookieStr = '';
            foreach ($cookies as $key => $value) {
                $cookieStr .= $key . '=' . $value . '; ';
            }
            $cookies = rtrim($cookieStr, '; ');
        }
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url . '?' . http_build_query($params));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        
        $headerList = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept: application/json, text/plain, */*',
            'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
            'Referer: https://space.bilibili.com/' . $mid,
            'Origin: https://space.bilibili.com',
            'Connection: keep-alive'
        ];
        if ($cookies) {
            $headerList[] = 'Cookie: ' . $cookies;
        }
        
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headerList);
        curl_setopt($ch, CURLOPT_TIMEOUT, 10);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        
        $response = curl_exec($ch);
        
        
        $data = json_decode($response, true);
        if (isset($data['code']) && $data['code'] == 0 && isset($data['data'])) {
            return [
                'bvid' => $data['data']['bvid'] ?? '',
                'title' => '【置顶】' . ($data['data']['title'] ?? ''),
                'play' => $data['data']['stat']['view'] ?? 0,
                'length' => '',
                'created' => $data['data']['pubdate'] ?? 0,
                'is_top' => true
            ];
        }
        
        return null;
    }
    
    private function getCollectionInfo($bvid) {
        $url = $this->config->getApiUrl('video_info_api', ['bvid' => $bvid]);
        list($success, $result) = NetworkUtils::request($url, $this->headers, $this->cookies);
        if (!$success) {
            throw new \Exception('获取合集信息失败：' . $result['error']);
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            throw new \Exception('获取合集信息失败：' . ($data['message'] ?? '未知错误'));
        }
        
        if (isset($data['data'])) {
            $videoData = $data['data'];
        } elseif (isset($data['result'])) {
            $videoData = $data['result'];
        } else {
            throw new \Exception('API返回格式错误');
        }
        
        $collection = [];
        
        if (isset($videoData['ugc_season'])) {
            $ugcSeason = $videoData['ugc_season'];
            if (isset($ugcSeason['sections'])) {
                foreach ($ugcSeason['sections'] as $section) {
                    if (isset($section['episodes'])) {
                        foreach ($section['episodes'] as $idx => $ep) {
                            $pageInfo = null;
                            if (isset($ep['page'])) {
                                $pageInfo = $ep['page'];
                            } elseif (isset($ep['pages']) && $ep['pages']) {
                                $pageInfo = $ep['pages'][0];
                            }
                            
                            if ($pageInfo) {
                                $duration = $pageInfo['duration'] ?? 0;
                                $collection[] = [
                                    'page' => $idx + 1,
                                    'cid' => $pageInfo['cid'] ?? 0,
                                    'bvid' => $ep['bvid'] ?? $bvid,
                                    'title' => $this->sanitizeFilename($ep['title'] ?? '第' . ($idx + 1) . '集'),
                                    'duration' => $duration,
                                    'duration_str' => $this->formatDuration($duration)
                                ];
                            }
                        }
                        break;
                    }
                }
            }
        }
        
        if (!$collection) {
            $pages = $videoData['pages'] ?? [];
            foreach ($pages as $page) {
                $duration = $page['duration'] ?? 0;
                $collection[] = [
                    'page' => $page['page'] ?? 0,
                    'cid' => $page['cid'] ?? 0,
                    'title' => $this->sanitizeFilename($page['part'] ?? "第{$page['page']}集"),
                    'duration' => $duration,
                    'duration_str' => $this->formatDuration($duration)
                ];
            }
        }
        
        return $collection;
    }
    
    private function getVideoMainInfo($bvid) {
        $url = $this->config->getApiUrl('video_info_api', ['bvid' => $bvid]);
        if (!$url) {
            throw new \Exception('API配置错误：video_info_api未配置');
        }
        list($success, $result) = NetworkUtils::request($url, $this->headers, $this->cookies);
        if (!$success) {
            throw new \Exception('视频信息获取失败：' . $result['error'] . '，URL: ' . $url);
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            throw new \Exception('视频信息获取失败：' . ($data['message'] ?? '未知错误') . '，URL: ' . $url);
        }
        
        $videoData = null;
        if (isset($data['data'])) {
            $videoData = $data['data'];
        } elseif (isset($data['result'])) {
            $videoData = $data['result'];
        } else {
            throw new \Exception('API返回格式错误，URL: ' . $url);
        }
        
        if (isset($videoData['View'])) {
            $viewData = $videoData['View'];
            $videoData = array_merge($videoData, $viewData);
        }
        
        return $videoData;
    }
    
    public function getPlayInfo($mediaType, $bvid, $cid, $isTvMode, $seasonId = null, $epId = null, $qn = 80) {
        // 对于番剧类型，需要请求高画质来获取所有可用画质列表
        $requestedQn = $qn;
        if ($mediaType == 'bangumi' || $mediaType == 'bangumi_ep') {
            // 请求最高画质(127)来获取所有可用画质，使用正确的fnval
            $qn = 127;
            $playUrl = "https://api.bilibili.com/pgc/player/web/playurl?cid={$cid}&bvid={$bvid}&qn={$qn}&fnval=4048&fnver=0&fourk=1&type=&otype=json";
        } elseif ($mediaType == 'cheese') {
            // 使用课程专用的API URL
            $playUrl = "https://api.bilibili.com/pugv/player/web/playurl?cid={$cid}&bvid={$bvid}&qn={$qn}&type=&otype=json&fourk=1&fnver=0&fnval=4048&ep_id={$epId}";
        } elseif ($isTvMode) {
            $playUrl = $this->config->getApiUrl('tv_play_url_api', ['cid' => $cid, 'bvid' => $bvid, 'qn' => $qn]);
        } else {
            $playUrl = $this->config->getApiUrl('play_url_api', ['cid' => $cid, 'bvid' => $bvid, 'qn' => $qn]);
        }
        
        // 添加适当的Referer头
        $headers = $this->headers;
        if ($mediaType == 'bangumi' || $mediaType == 'bangumi_ep') {
            $headers['Referer'] = "https://www.bilibili.com/bangumi/play/ep{$epId}";
        } elseif ($mediaType == 'cheese') {
            $headers['Referer'] = "https://www.bilibili.com/cheese/play/ss{$seasonId}";
        } else {
            $headers['Referer'] = "https://www.bilibili.com/video/{$bvid}/";
        }
        
        list($success, $result) = NetworkUtils::request($playUrl, $headers, $this->cookies);
        if (!$success) {
            if (strpos($result['error'], '访问权限不足') !== false) {
                throw new \Exception('访问权限不足');
            }
            throw new \Exception('获取播放链接失败：' . $result['error']);
        }

        $data = json_decode($result['content'], true);

        if ($data['code'] != 0) {
            $errorMsg = $data['message'] ?? '权限不足';
            if ($data['code'] == 403) {
                $errorMsg .= '（可能是Cookie失效或无对应画质权限）';
            }
            throw new \Exception($errorMsg);
        }

        $qualities = [];
        $videoUrls = [];
        $audioUrl = '';
        $keyId = '';
        $flvQns = [];
        // 优化：缓存用户信息，避免每次都请求
        static $cachedUserInfo = null;
        if ($cachedUserInfo === null) {
            $cachedUserInfo = $this->getUserInfo();
        }
        $isVip = $cachedUserInfo['success'] ? $cachedUserInfo['is_vip'] : true;
        $hasHevc = false;
        $qualityMap = $this->config->getQualityMap();

        // 番剧API返回在result字段，普通视频在data字段
        $dataSource = $data['data'] ?? $data['result'] ?? [];
        
        // === FLV模式回退：如果DASH的dash.video缺少高画质流，尝试用FLV格式获取 ===
        if (isset($dataSource['dash']) && isset($dataSource['dash']['video']) && isset($dataSource['support_formats'])) {
            $dashQns = [];
            foreach ($dataSource['dash']['video'] as $v) {
                $dashQns[] = $v['id'] ?? 0;
            }
            $supportQns = [];
            foreach ($dataSource['support_formats'] as $f) {
                $supportQns[] = $f['quality'] ?? 0;
            }
            $maxDashQn = max($dashQns);
            $maxSupportQn = max($supportQns);
            // 如果support_formats提供了比dash.video更高的画质（如1080P是FLV格式），尝试获取
            if ($maxSupportQn > $maxDashQn && $maxDashQn < 80) {
                $flvQn = min($maxSupportQn, 80); // 目标画质最高到1080P（qn=80）
                $flvHeaders = $headers;
                $flvHeaders['Referer'] = $headers['Referer'] ?? "https://www.bilibili.com/video/{$bvid}/";
                // 使用fnval=1（FLV/HTML5模式）获取高画质流
                $flvPlayUrl = $this->config->getApiUrl('play_url_api', ['cid' => $cid, 'bvid' => $bvid, 'qn' => $flvQn]);
                $flvPlayUrl = str_replace('fnval=4048', 'fnval=1', $flvPlayUrl);
                $flvPlayUrl = str_replace('fnval=80', 'fnval=1', $flvPlayUrl);
                $flvPlayUrl .= '&platform=html5&high_quality=1&try_look=1';
                
                list($flvSuccess, $flvResult) = NetworkUtils::request($flvPlayUrl, $flvHeaders, $this->cookies);
                if ($flvSuccess) {
                    $flvData = json_decode($flvResult['content'], true);
                    if ($flvData['code'] == 0) {
                        $flvSource = $flvData['data'] ?? $flvData['result'] ?? [];
                        $flvQnActual = $flvSource['quality'] ?? 0;
                        if ($flvQnActual > $maxDashQn && isset($flvSource['durl']) && !empty($flvSource['durl'])) {
                            // FLV获取到了更高画质，直接切换到FLV模式（音视频一体，无需单独音频流）
                            $dataSource = $flvSource;
                        }
                    }
                }
            }
        }
        
        if (isset($dataSource['dash'])) {
            if (isset($dataSource['dash']['audio']) && $dataSource['dash']['audio']) {
                $audioItem = $dataSource['dash']['audio'][0];
                if (isset($audioItem['baseUrl'])) {
                    $audioUrl = trim($audioItem['baseUrl']);
                } elseif (isset($audioItem['url'])) {
                    $audioUrl = trim($audioItem['url']);
                } elseif (isset($audioItem['backup_url']) && is_array($audioItem['backup_url']) && count($audioItem['backup_url']) > 0) {
                    $audioUrl = trim($audioItem['backup_url'][0]);
                }
            }
            
            if (isset($dataSource['support_formats'])) {
                // 先从support_formats获取所有可用画质
                foreach ($dataSource['support_formats'] as $format) {
                    $qn = $format['quality'] ?? 0;
                    $qualityName = $qualityMap[$qn] ?? ($format['new_description'] ?? $format['description'] ?? "未知画质($qn)");
                    
                    if (in_array($qn, [125, 127])) {
                        $hasHevc = true;
                    }
                    
                    if (in_array($qn, [112, 120, 125, 127]) && !$isVip) {
                        continue;
                    }
                    
                    $qualities[] = [$qn, $qualityName];
                }
            }
            
            if (isset($dataSource['dash']['video'])) {
                // 从dash.video中获取视频URL
                foreach ($dataSource['dash']['video'] as $video) {
                    $qn = $video['id'] ?? 0;
                    
                    $videoUrl = '';
                    if (isset($video['baseUrl'])) {
                        $videoUrl = trim($video['baseUrl']);
                    } elseif (isset($video['url'])) {
                        $videoUrl = trim($video['url']);
                    } elseif (isset($video['backup_url']) && is_array($video['backup_url']) && count($video['backup_url']) > 0) {
                        $videoUrl = trim($video['backup_url'][0]);
                    }
                    
                    if ($videoUrl) {
                        $videoUrls[$qn] = $videoUrl;
                    }
                }
            }
            
            // 过滤：只保留videoUrls中实际存在的画质（dash.video可能不包含所有support_formats画质）
            $validQualities = [];
            foreach ($qualities as $q) {
                if (isset($videoUrls[$q[0]])) {
                    $validQualities[] = $q;
                }
            }
            $qualities = $validQualities;
            
            // 合并FLV回退的高画质（如果DASH缺少高画质，由FLV模式补充）
            if (isset($dataSource['_flv_fallback']) && is_array($dataSource['_flv_fallback'])) {
                foreach ($dataSource['_flv_fallback'] as $flvQn => $flvUrl) {
                    if (!isset($videoUrls[$flvQn]) && $flvUrl) {
                        $videoUrls[$flvQn] = $flvUrl;
                        $qualityName = $qualityMap[$flvQn] ?? "画质($flvQn)";
                        $qualities[] = [$flvQn, $qualityName];
                    }
                }
            }
            
            // 如果support_formats为空，则回退到从dash.video获取
            if (empty($qualities) && isset($dataSource['dash']['video'])) {
                foreach ($dataSource['dash']['video'] as $video) {
                    $qn = $video['id'] ?? 0;
                    $qualityName = $qualityMap[$qn] ?? "未知画质($qn)";
                    
                    if (in_array($qn, [125, 127])) {
                        $hasHevc = true;
                        $qualityName .= ' (HEVC)';
                    }
                    
                    if (in_array($qn, [112, 120, 125, 127]) && !$isVip) {
                        continue;
                    }
                    
                    $videoUrl = '';
                    if (isset($video['baseUrl'])) {
                        $videoUrl = trim($video['baseUrl']);
                    } elseif (isset($video['url'])) {
                        $videoUrl = trim($video['url']);
                    } elseif (isset($video['backup_url']) && is_array($video['backup_url']) && count($video['backup_url']) > 0) {
                        $videoUrl = trim($video['backup_url'][0]);
                    }
                    
                    if ($videoUrl) {
                        $videoUrls[$qn] = $videoUrl;
                        $qualities[] = [$qn, $qualityName];
                    }
                }
            }
            
            // 提取key_id - 尝试多种可能的位置
            if (isset($dataSource['dash']['video'][0]['key_id'])) {
                $keyId = $dataSource['dash']['video'][0]['key_id'];
                file_put_contents('debug_key_id.txt', "找到key_id在 dash.video[0].key_id: $keyId\n");
            } elseif (isset($dataSource['dash']['video'][0]['KeyId'])) {
                $keyId = $dataSource['dash']['video'][0]['KeyId'];
                file_put_contents('debug_key_id.txt', "找到key_id在 dash.video[0].KeyId: $keyId\n");
            } elseif (isset($dataSource['dash']['video'][0]['keyid'])) {
                $keyId = $dataSource['dash']['video'][0]['keyid'];
                file_put_contents('debug_key_id.txt', "找到key_id在 dash.video[0].keyid: $keyId\n");
            } elseif (isset($dataSource['dash']['video'][0]['bilidrm_uri'])) {
                // 从bilidrm_uri中提取key_id
                $bilidrmUri = $dataSource['dash']['video'][0]['bilidrm_uri'];
                if (preg_match('/uri:bili:\/\/(\w+)/', $bilidrmUri, $matches)) {
                    $keyId = $matches[1];
                    file_put_contents('debug_key_id.txt', "找到key_id在 dash.video[0].bilidrm_uri: $keyId\n");
                }
            } else {
                // 调试：保存完整的API响应
                file_put_contents('debug_api_response.txt', json_encode($data, JSON_PRETTY_PRINT));
                file_put_contents('debug_key_id.txt', "未找到key_id，已保存完整响应到 debug_api_response.txt\n");
            }
        } elseif (isset($dataSource['durl'])) {
            $currentQn = intval($dataSource['quality'] ?? 0);
            
            if ($dataSource['durl'] && $currentQn > 0) {
                $videoUrl = $dataSource['durl'][0]['url'];
                
                if (!$videoUrl) {
                    throw new \Exception('durl格式视频链接为空');
                }
                
                $qualityName = $qualityMap[$currentQn] ?? "画质($currentQn)";
                
                if (in_array($currentQn, [125, 127])) {
                    $hasHevc = true;
                    $qualityName .= ' (HEVC)';
                }
                
                if (!in_array($currentQn, [112, 120, 125, 127]) || $isVip) {
                    $videoUrls[$currentQn] = $videoUrl;
                    $qualities[] = [$currentQn, $qualityName];
                    $flvQns[] = $currentQn;
                }
            }
        } else {
            throw new \Exception('API返回格式错误，未找到播放链接数据');
        }
        
        if (!$videoUrls) {
            throw new \Exception('未获取到任何视频链接');
        }
        
        $qualities = array_unique($qualities, SORT_REGULAR);
        usort($qualities, function($a, $b) {
            return $b[0] - $a[0];
        });
        
        return [
            'success' => true,
            'qualities' => $qualities,
            'video_urls' => $videoUrls,
            'audio_url' => $audioUrl,
            'flv_qns' => $flvQns,
            'is_vip' => $isVip,
            'has_hevc' => $hasHevc,
            'key_id' => $keyId
        ];
    }
    
    public function getUserInfo() {
        $apiUrl = 'https://api.bilibili.com/x/web-interface/nav';
        
        list($success, $result) = NetworkUtils::request($apiUrl, $this->headers, $this->cookies);
        if (!$success) {
            return ['success' => false, 'msg' => '获取用户信息失败：' . $result['error'], 'is_vip' => false];
        }
        
        $data = json_decode($result['content'], true);
        if ($data['code'] != 0) {
            $msg = $data['message'] ?? '未知错误';
            return ['success' => false, 'msg' => 'API返回错误：' . $msg, 'is_vip' => false];
        }
        
        $data = $data['data'] ?? [];
        $isLogin = $data['isLogin'] ?? false;
        if (!$isLogin) {
            return ['success' => false, 'msg' => '未登录或Cookie失效', 'is_vip' => false];
        }
        
        return [
            'success' => true,
            'name' => $data['uname'] ?? '未知用户',
            'uname' => $data['uname'] ?? '未知用户',
            'mid' => strval($data['mid'] ?? '未知ID'),
            'is_vip' => $data['vipStatus'] == 1,
            'vip_type' => $data['vipType'] ?? 0,
            'level' => $data['level_info']['current_level'] ?? 0,
            'face' => $data['face'] ?? '',
            'msg' => '登录用户：' . ($data['uname'] ?? '未知用户') . ' | 等级' . ($data['level_info']['current_level'] ?? 0) . ' | ' . ($data['vipStatus'] == 1 ? '会员' : '普通用户')
        ];
    }
    
    public function verifyCookie() {
        if (empty($this->cookies)) {
            return [false, '未加载任何Cookie'];
        }
        
        $requiredCookies = ['SESSDATA'];
        $missing = [];
        foreach ($requiredCookies as $ck) {
            if (!isset($this->cookies[$ck])) {
                $missing[] = $ck;
            }
        }
        if ($missing) {
            return [false, '缺少关键Cookie：' . implode(',', $missing) . '（登录必需）'];
        }
        
        $userInfo = $this->getUserInfo();
        if (!$userInfo['success']) {
            return [false, $userInfo['msg']];
        }
        
        return [true, $userInfo['msg']];
    }
    
    public function downloadFile($url, $saveDir, $progressCallback = null, $fileType = 'video', $bvid = null) {
        if (!is_dir($saveDir)) {
            mkdir($saveDir, 0777, true);
        }
        
        $tempDir = __DIR__ . '/../temp';
        if (!is_dir($tempDir)) {
            mkdir($tempDir, 0777, true);
        }
        
        $tempFilename = "temp_{$fileType}_{$this->generateHash($url)}_{time()}.m4s";
        $tempPath = $tempDir . '/' . $tempFilename;
        
        $headers = $this->headers;
        if ($bvid) {
            $headers['Referer'] = "https://www.bilibili.com/video/{$bvid}/";
        }
        
        list($success, $result) = NetworkUtils::downloadFile($url, $tempPath, $headers, $this->cookies, $progressCallback);
        if (!$success) {
            throw new \Exception("{$fileType}下载失败：{$result}");
        }
        
        return $tempPath;
    }
    
    public function mergeMedia($videoPath, $audioPath, $outputPath) {
        if (!file_exists($videoPath)) {
            throw new \Exception('视频文件不存在');
        }
        
        if ($audioPath && !file_exists($audioPath)) {
            throw new \Exception('音频文件不存在');
        }
        
        if (!is_dir(dirname($outputPath))) {
            mkdir(dirname($outputPath), 0777, true);
        }
        
        if ($audioPath) {
            $ffmpegPath = __DIR__ . '/../ffmpeg/bin/ffmpeg.exe';
            if (!file_exists($ffmpegPath)) {
                throw new \Exception('未找到ffmpeg！请安装并添加到系统环境变量，或放在./ffmpeg/bin目录下');
            }
            
            $command = "{$ffmpegPath} -i \"{$videoPath}\" -i \"{$audioPath}\" -c:v copy -c:a copy -loglevel error -y \"{$outputPath}\"";
            exec($command, $output, $returnVar);
            
            if ($returnVar != 0) {
                throw new \Exception('ffmpeg执行失败');
            }
            
            unlink($videoPath);
            unlink($audioPath);
        } else {
            if (file_exists($outputPath)) {
                unlink($outputPath);
            }
            rename($videoPath, $outputPath);
        }
        
        if (!file_exists($outputPath)) {
            throw new \Exception('合并后文件不存在');
        }
        
        return true;
    }
    
    private function sanitizeFilename($filename) {
        return preg_replace('/[\/\\:*?"<>|]/', '_', $filename);
    }
    
    private function formatDuration($seconds) {
        $minutes = floor($seconds / 60);
        $secs = $seconds % 60;
        return sprintf('%02d:%02d', $minutes, $secs);
    }
    
    private function generateHash($string) {
        return md5($string);
    }
    
    public function getBangumiEpisodePlayinfo($bvid, $cid, $quality = 80) {
        try {
            $playUrl = $this->config->getApiUrl('bangumi_play_url_api', ['cid' => $cid, 'bvid' => $bvid, 'fnval' => 80]);
            list($success, $result) = NetworkUtils::request($playUrl, $this->headers, $this->cookies);
            if (!$success) {
                if (strpos($result['error'], '访问权限不足') !== false) {
                    return ['success' => false, 'error' => '访问权限不足'];
                }
                return ['success' => false, 'error' => '获取番剧播放链接失败：' . $result['error']];
            }
            
            $data = json_decode($result['content'], true);
            if ($data['code'] != 0) {
                $errorMsg = $data['message'] ?? '权限不足';
                if ($data['code'] == 403) {
                    $errorMsg .= '（可能是会员专享集或Cookie失效）';
                }
                return ['success' => false, 'error' => $errorMsg];
            }
            
            $dataSource = $data['data'] ?? $data['result'] ?? [];
            
            $videoUrl = '';
            $audioUrl = '';
            if (isset($dataSource['dash'])) {
                if (isset($dataSource['dash']['video'])) {
                    $selectedVideo = null;
                    foreach ($dataSource['dash']['video'] as $video) {
                        if ($video['id'] == $quality) {
                            $selectedVideo = $video;
                            break;
                        }
                    }
                    if (!$selectedVideo) {
                        $selectedVideo = $dataSource['dash']['video'][0];
                    }
                    if (isset($selectedVideo['baseUrl'])) {
                        $videoUrl = trim($selectedVideo['baseUrl']);
                    } elseif (isset($selectedVideo['url'])) {
                        $videoUrl = trim($selectedVideo['url']);
                    } elseif (isset($selectedVideo['backup_url']) && is_array($selectedVideo['backup_url']) && count($selectedVideo['backup_url']) > 0) {
                        $videoUrl = trim($selectedVideo['backup_url'][0]);
                    }
                }
                if (isset($dataSource['dash']['audio'])) {
                    $audioItem = $dataSource['dash']['audio'][0];
                    if (isset($audioItem['baseUrl'])) {
                        $audioUrl = trim($audioItem['baseUrl']);
                    } elseif (isset($audioItem['url'])) {
                        $audioUrl = trim($audioItem['url']);
                    } elseif (isset($audioItem['backup_url']) && is_array($audioItem['backup_url']) && count($audioItem['backup_url']) > 0) {
                        $audioUrl = trim($audioItem['backup_url'][0]);
                    }
                }
            } elseif (isset($dataSource['durl'])) {
                $videoUrl = $dataSource['durl'][0]['url'];
            }
            
            if (!$videoUrl) {
                return ['success' => false, 'error' => '未获取到视频播放链接'];
            }
            
            return [
                'success' => true,
                'video_url' => $videoUrl,
                'audio_url' => $audioUrl
            ];
        } catch (\Exception $e) {
            return [
                'success' => false,
                'error' => '番剧单集播放链接获取失败：' . $e->getMessage()
            ];
        }
    }
    
    public function downloadVideo($bvid, $aid, $cid, $qn, $savePath, $page, $progressCallback = null) {
        try {
            $playInfo = $this->getPlayInfo('video', $bvid, $cid, false);
            if (!$playInfo['success']) {
                throw new \Exception($playInfo['error']);
            }
            
            $videoUrl = $playInfo['video_urls'][$qn] ?? $playInfo['video_urls'][key($playInfo['video_urls'])];
            $audioUrl = $playInfo['audio_url'] ?? '';
            
            if (!$videoUrl) {
                throw new \Exception('未获取到视频链接');
            }
            
            $videoPath = $this->downloadFile($videoUrl, $savePath, $progressCallback, 'video', $bvid);
            $audioPath = '';
            
            if ($audioUrl) {
                $audioPath = $this->downloadFile($audioUrl, $savePath, $progressCallback, 'audio', $bvid);
            }
            
            $outputFilename = "{$bvid}_第{$page}集.mp4";
            $outputPath = $savePath . '/' . $outputFilename;
            
            $this->mergeMedia($videoPath, $audioPath, $outputPath);
            
            return $outputPath;
        } catch (\Exception $e) {
            throw $e;
        }
    }
    
    public function downloadBangumiEpisode($bvid, $aid, $cid, $qn, $savePath, $epId, $progressCallback = null) {
        try {
            $playInfo = $this->getPlayInfo('bangumi', $bvid, $cid, false);
            if (!$playInfo['success']) {
                throw new \Exception($playInfo['error']);
            }
            
            $videoUrl = $playInfo['video_urls'][$qn] ?? $playInfo['video_urls'][key($playInfo['video_urls'])];
            $audioUrl = $playInfo['audio_url'] ?? '';
            
            if (!$videoUrl) {
                throw new \Exception('未获取到视频链接');
            }
            
            $videoPath = $this->downloadFile($videoUrl, $savePath, $progressCallback, 'video', $bvid);
            $audioPath = '';
            
            if ($audioUrl) {
                $audioPath = $this->downloadFile($audioUrl, $savePath, $progressCallback, 'audio', $bvid);
            }
            
            $outputFilename = "{$bvid}_ep{$epId}.mp4";
            $outputPath = $savePath . '/' . $outputFilename;
            
            $this->mergeMedia($videoPath, $audioPath, $outputPath);
            
            return $outputPath;
        } catch (\Exception $e) {
            throw $e;
        }
    }
}
?>