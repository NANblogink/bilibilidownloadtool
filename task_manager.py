
import os
import json
import time
from datetime import datetime

class TaskManager:
    def __init__(self):
        self.tasks_file = "download_tasks.json"
        self.tasks = self._load_tasks()

    def _load_tasks(self):
        if os.path.exists(self.tasks_file):
            try:
                file_size = os.path.getsize(self.tasks_file)
                if file_size > 1024 * 1024:
                    print(f"任务文件过大 ({file_size/1024/1024:.2f}MB)，可能导致加载缓慢")
                
                with open(self.tasks_file, 'r', encoding='utf-8', errors='ignore') as f:
                    tasks = json.load(f)
                    
                    max_tasks = 100
                    if len(tasks) > max_tasks:
                        print(f"任务数量过多 ({len(tasks)}个)，只加载最近的{max_tasks}个任务")
                        tasks = tasks[-max_tasks:]
                    
                    for task in tasks:
                        if task.get("status") == "downloading":
                            task["status"] = "failed"
                            task["error_message"] = "异常中断"
                    
                    self.tasks = tasks
                    if any(task.get("status") == "failed" for task in tasks):
                        self.save_tasks()
                    print(f"成功加载{len(tasks)}个任务")
                    return tasks
            except Exception as e:
                print(f"加载任务文件失败：{str(e)}")
                self.tasks = []
                return []
        else:
            self.tasks = []
            return []

    def save_tasks(self):
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存任务文件失败：{str(e)}")
            return False

    def add_task(self, task_info):
        task = {
            "id": task_info["id"],  
            "url": task_info.get("url", ""),
            "title": task_info.get("title", ""),
            "save_path": task_info.get("save_path", ""),
            "progress": task_info.get("progress", 0),
            "status": task_info.get("status", "pending"),  
            "error_message": task_info.get("error_message", ""),
            "video_info": task_info.get("video_info", {}),
            "qn": task_info.get("qn", ""),
            "episodes": task_info.get("episodes", []),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "downloaded_episodes": task_info.get("downloaded_episodes", []),
            "temp_files": task_info.get("temp_files", []),
            "download_video": task_info.get("download_video", True),
            "download_danmaku": task_info.get("download_danmaku", False),
            "danmaku_format": task_info.get("danmaku_format", "XML")
        }
        self.tasks.append(task)
        self.save_tasks()
        return task

    def update_task(self, task_id, updates):
        for task in self.tasks:
            if task.get("id") == task_id:
                task.update(updates)
                task["updated_at"] = datetime.now().isoformat()
                self.save_tasks()
                return True
        return False

    def get_task(self, task_id):
        for task in self.tasks:
            if task.get("id") == task_id:
                return task
        return None

    def get_all_tasks(self):
        return self.tasks

    def get_tasks_by_status(self, status):
        return [task for task in self.tasks if task.get("status") == status]

    def delete_task(self, task_id):
        self.tasks = [task for task in self.tasks if task.get("id") != task_id]
        self.save_tasks()
        return True

    def clear_completed_tasks(self):
        self.tasks = [task for task in self.tasks if task.get("status") != "completed"]
        self.save_tasks()
        return True

    def update_task_progress(self, task_id, progress):
        return self.update_task(task_id, {"progress": progress})

    def update_task_status(self, task_id, status, error_message="", task_data=None):
        updates = {"status": status}
        
        if error_message and status == "failed":
            updates["error_message"] = error_message
        elif status == "completed" or status == "downloading" or status == "pending":
            updates["error_message"] = ""
        if task_data:
            updates.update(task_data)
        return self.update_task(task_id, updates)
