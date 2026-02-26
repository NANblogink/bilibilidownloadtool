# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
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
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                    return tasks
            except Exception as e:
                print(f"加载任务文件失败：{str(e)}")
                return []
        else:
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
            "id": str(int(time.time() * 1000)),
            "url": task_info.get("url", ""),
            "title": task_info.get("title", ""),
            "save_path": task_info.get("save_path", ""),
            "progress": task_info.get("progress", 0),
            "status": task_info.get("status", "pending"),  # pending, downloading, completed, failed
            "error_message": task_info.get("error_message", ""),
            "video_info": task_info.get("video_info", {}),
            "qn": task_info.get("qn", ""),
            "episodes": task_info.get("episodes", []),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
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
        # 只有当任务失败时才设置错误信息
        if error_message and status == "failed":
            updates["error_message"] = error_message
        elif status == "completed" or status == "downloading" or status == "pending":
            # 清除成功或进行中任务的错误信息
            updates["error_message"] = ""
        if task_data:
            updates.update(task_data)
        return self.update_task(task_id, updates)
