<?php

namespace BilibiliDownloader;

class TaskManager {
    private $tasksFile;
    private $tasks;
    
    public function __construct($tasksFile = null) {
        $this->tasksFile = $tasksFile ?? __DIR__ . '/../download_tasks.json';
        $this->loadTasks();
    }
    
    private function loadTasks() {
        if (file_exists($this->tasksFile)) {
            $content = file_get_contents($this->tasksFile);
            $this->tasks = json_decode($content, true) ?? [];
        } else {
            $this->tasks = [];
        }
    }
    
    private function saveTasks() {
        file_put_contents($this->tasksFile, json_encode($this->tasks, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    }
    
    public function addTask($taskInfo) {
        $this->tasks[$taskInfo['id']] = $taskInfo;
        $this->saveTasks();
        return $taskInfo['id'];
    }
    
    public function saveTask($taskId, $taskData) {
        $this->tasks[$taskId] = $taskData;
        $this->saveTasks();
    }
    
    public function updateTaskProgress($taskId, $progress) {
        if (isset($this->tasks[$taskId])) {
            $this->tasks[$taskId]['progress'] = $progress;
            $this->saveTasks();
        }
    }
    
    public function updateTaskStatus($taskId, $status, $errorMessage = '', $additionalData = []) {
        if (isset($this->tasks[$taskId])) {
            $this->tasks[$taskId]['status'] = $status;
            if ($errorMessage) {
                $this->tasks[$taskId]['error_message'] = $errorMessage;
            }
            foreach ($additionalData as $key => $value) {
                $this->tasks[$taskId][$key] = $value;
            }
            $this->saveTasks();
        }
    }
    
    public function deleteTask($taskId) {
        if (isset($this->tasks[$taskId])) {
            unset($this->tasks[$taskId]);
            $this->saveTasks();
        }
    }
    
    public function getTask($taskId) {
        return $this->tasks[$taskId] ?? null;
    }
    
    public function get_all_tasks() {
        return array_values($this->tasks);
    }
    
    public function clear_completed_tasks() {
        foreach ($this->tasks as $taskId => $task) {
            if ($task['status'] == 'completed') {
                unset($this->tasks[$taskId]);
            }
        }
        $this->saveTasks();
    }
    
    public function getPendingTasks() {
        $pending = [];
        foreach ($this->tasks as $task) {
            if ($task['status'] == 'pending') {
                $pending[] = $task;
            }
        }
        return $pending;
    }
    
    public function getActiveTasks() {
        $active = [];
        foreach ($this->tasks as $task) {
            if (in_array($task['status'], ['downloading', 'pending'])) {
                $active[] = $task;
            }
        }
        return $active;
    }
}
?>