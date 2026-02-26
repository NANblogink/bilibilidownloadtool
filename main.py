# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import sys
import requests
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from ui import BilibiliDownloader
from bilibili_parser import BilibiliParser
from downloader import DownloadManager
from config import ConfigLoader
from task_manager import TaskManager
from utils import get_unique_filename
from env_checker import check_environment

if __name__ == "__main__":
    env_result = check_environment()
    
    requests.packages.urllib3.disable_warnings()
    app = QApplication(sys.argv)
    font = QFont("SimHei", 9)
    app.setFont(font)
    app.setStyle('Fusion')

    config = ConfigLoader()
    parser = BilibiliParser(config=config)
    task_manager = TaskManager()
    download_manager = DownloadManager(parser=parser, task_manager=task_manager)
    window = BilibiliDownloader(config=config, task_manager=task_manager, download_manager=download_manager)

    # 将parser传递给window
    window.parser = parser

    def handle_cookie_verification(cookie_input):
        try:
            save_success = parser.save_cookies(cookie_input)
            if not save_success:
                window.on_cookie_verified(False, "Cookie格式错误！支持：JSON对象列表、key1=value1;格式")
                return
            success, msg = parser.verify_cookie()
            window.on_cookie_verified(success, msg)
        except Exception as e:
            window.on_cookie_verified(False, f"Cookie处理失败：{str(e)}")

    window.signal_emitter.verify_cookie.connect(handle_cookie_verification)

    def handle_load_user_info():
        user_info = parser.get_user_info()
        window.update_user_info(user_info)

    window.signal_emitter.load_user_info.connect(handle_load_user_info)

    def handle_check_hevc():
        hevc_supported = parser.check_hevc_support()
        window.update_hevc_status(hevc_supported)

    window.signal_emitter.check_hevc.connect(handle_check_hevc)

    def handle_install_hevc():
        def progress_callback(progress):
            window.update_hevc_progress(progress)
        success, msg = parser.install_hevc(progress_callback)
        window.on_hevc_install_finish(success, msg)

    window.signal_emitter.install_hevc.connect(handle_install_hevc)

    def handle_parse_media(url, is_tv_mode):
        media_parse_result = parser.parse_media_url(url)
        if media_parse_result.get("error"):
            window.on_parse_finished({"success": False, "error": media_parse_result["error"]})
            return

        media_type = media_parse_result["type"]
        media_id = media_parse_result["id"]
        if not media_type or not media_id:
            window.on_parse_finished({"success": False, "error": "未识别到有效媒体ID（支持BV/ss/av号）"})
            return

        try:
            media_info = parser.parse_media(media_type, media_id, is_tv_mode)
            window.on_parse_finished(media_info)
        except Exception as e:
            window.on_parse_finished({"success": False, "error": f"解析失败：{str(e)}"})

    window.signal_emitter.parse_start.connect(handle_parse_media)

    window.signal_emitter.start_download.connect(download_manager.start_download)

    def handle_cancel_download():
        download_manager.cancel_all()
        parser.stop_download()
        window.status_label.setText("下载已取消")

    window.signal_emitter.cancel_download.connect(handle_cancel_download)



    download_manager.global_progress_updated.connect(window.update_download_progress)
    download_manager.episode_progress_updated.connect(window.update_episode_progress)
    download_manager.episode_finished.connect(window.finish_episode)

    handle_check_hevc()
    handle_load_user_info()
    parser.reset_running_status()

    window.show()
    sys.exit(app.exec_())