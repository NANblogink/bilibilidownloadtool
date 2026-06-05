import os
import sys
import logging
import zipfile
import shutil
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platform_utils import IS_MACOS, IS_WINDOWS, subprocess_no_window_kwargs


def _get_app_dir():
    try:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
    except Exception:
        pass
    return os.path.dirname(os.path.abspath(__file__))

LOG_DIR = os.path.join(_get_app_dir(), 'log')
LOG_FORMAT = '%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 10
KEEP_DAYS = 30


class _ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35;1m',
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, '')
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        name = record.name.split('.')[-1] if '.' in record.name else record.name
        msg = record.getMessage()
        
        if record.exc_info and record.exc_info[0]:
            exc_text = self.formatException(record.exc_info)
            return f"{self.DIM}{time_str}{self.RESET} {level_color}{record.levelname:<7}{self.RESET} {self.BOLD}{name:<18}{self.RESET} {msg}\n{exc_text}"
        
        if record.levelno >= logging.ERROR:
            return f"{self.DIM}{time_str}{self.RESET} {level_color}{record.levelname:<7}{self.RESET} {self.BOLD}{name:<18}{self.RESET} {level_color}{msg}{self.RESET}"
        elif record.levelno == logging.WARNING:
            return f"{self.DIM}{time_str}{self.RESET} {level_color}{record.levelname:<7}{self.RESET} {name:<18} {level_color}{msg}{self.RESET}"
        elif record.levelno == logging.DEBUG:
            return f"{self.DIM}{time_str}{self.RESET} \033[90mDEBUG   {self.RESET} {self.DIM}{name:<18}{self.RESET} {self.DIM}{msg}{self.RESET}"
        else:
            return f"{self.DIM}{time_str}{self.RESET} {level_color}\u2713{self.RESET}      {name:<18} {msg}"


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging():
    _ensure_log_dir()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    existing_handlers = list(root_logger.handlers)
    for h in existing_handlers:
        root_logger.removeHandler(h)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(_ColorFormatter())
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    root_logger.addHandler(console_handler)
    
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    log_filepath = os.path.join(LOG_DIR, log_filename)
    
    file_handler = RotatingFileHandler(
        log_filepath,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    ))
    root_logger.addHandler(file_handler)
    
    logging.getLogger('PyQt5').setLevel(logging.ERROR)
    logging.getLogger('PyQt5.QtCore').setLevel(logging.ERROR)
    logging.getLogger('PyQt5.QtWidgets').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("日志系统初始化完成，日志文件: %s", log_filepath)


def get_log_dir():
    return LOG_DIR


def get_log_files():
    _ensure_log_dir()
    files = []
    if os.path.exists(LOG_DIR):
        for f in os.listdir(LOG_DIR):
            fp = os.path.join(LOG_DIR, f)
            if os.path.isfile(fp):
                stat = os.stat(fp)
                files.append({
                    'name': f,
                    'path': fp,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                })
    files.sort(key=lambda x: x['modified'], reverse=True)
    return files


def get_log_total_size():
    total = 0
    for f in get_log_files():
        total += f['size']
    return total


def clear_old_logs(days=KEEP_DAYS):
    _ensure_log_dir()
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    freed = 0
    for f in get_log_files():
        if f['modified'] < cutoff:
            try:
                size = f['size']
                os.remove(f['path'])
                removed += 1
                freed += size
            except Exception:
                pass
    logger = logging.getLogger(__name__)
    logger.info("清理了 %d 个旧日志文件，释放 %.2f MB", removed, freed / (1024 * 1024))
    return removed, freed


def package_logs(output_path=None):
    _ensure_log_dir()
    
    log_files = get_log_files()
    if not log_files:
        logger = logging.getLogger(__name__)
        logger.warning("没有可打包的日志文件")
        return None
    
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(LOG_DIR, f'logs_{timestamp}.zip')
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in log_files:
                arc_name = os.path.join('logs', f['name'])
                zf.write(f['path'], arc_name)
        
        zip_size = os.path.getsize(output_path)
        logger = logging.getLogger(__name__)
        logger.info("日志打包完成: %s (%.2f KB)", output_path, zip_size / 1024)
        return output_path
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error("日志打包失败: %s", str(e))
        return None


def copy_logs_to_clipboard():
    zip_path = package_logs()
    if not zip_path:
        return False
    
    logger = logging.getLogger(__name__)
    abs_path = os.path.abspath(zip_path)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QMimeData, QUrl
        
        app = QApplication.instance()
        if app:
            clipboard = app.clipboard()
            
            mime_data = QMimeData()
            url = QUrl.fromLocalFile(abs_path)
            mime_data.setUrls([url])
            clipboard.setMimeData(mime_data)
            
            logger.info("日志压缩包已复制到剪贴板: %s", zip_path)
            return True
    except Exception as e:
        logger.debug("QClipboard文件复制失败: %s", str(e))
    
    try:
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(abs_path)
        logger.info("日志路径已复制到剪贴板: %s", abs_path)
        return True
    except Exception as e:
        logger.warning("PyQt5剪贴板操作失败: %s", str(e))
    
    if IS_WINDOWS:
        try:
            import subprocess
            safe_path = abs_path.replace('\\', '/')
            ps_cmd = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetText("{safe_path}")'
            
            proc = subprocess.Popen(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **subprocess_no_window_kwargs()
            )
            try:
                stdout, stderr = proc.communicate(timeout=5)
                if proc.returncode == 0:
                    logger.info("日志路径已通过PowerShell复制到剪贴板")
                    return True
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning("PowerShell执行超时")
        except Exception as e:
            logger.debug("PowerShell剪贴板操作失败: %s", str(e))
    elif IS_MACOS:
        try:
            import subprocess
            proc = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            proc.communicate(input=abs_path.encode('utf-8'), timeout=5)
            if proc.returncode == 0:
                logger.info("日志路径已通过pbcopy复制到剪贴板")
                return True
        except Exception as e:
            logger.debug("pbcopy剪贴板操作失败: %s", str(e))
    
    logger.error("所有复制方式均失败，请手动复制: %s", abs_path)
    return False


def clear_all_logs():
    _ensure_log_dir()
    removed = 0
    freed = 0
    for f in get_log_files():
        try:
            size = f['size']
            os.remove(f['path'])
            removed += 1
            freed += size
        except Exception:
            pass
    logger = logging.getLogger(__name__)
    logger.info("已清理全部 %d 个日志文件，释放 %.2f MB", removed, freed / (1024 * 1024))
    return removed, freed


logger = logging.getLogger(__name__)
