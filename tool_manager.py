"""
工具管理器 - 负责管理FFmpeg和Bento4工具的部署
"""
import os
import sys
import time
import shutil
import logging
import subprocess
import ctypes
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

CDN_URLS = {
    'ffmpeg': 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'bento4': 'https://github.com/nicholasgasior/bento4/releases/download/v1-6-0-641/Bento4-Win64-v1-6-0-641.zip'
}


class ToolManager:
    
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.install_dir = os.path.dirname(sys.executable)
            _parent_dir = os.path.dirname(self.install_dir)
            if os.path.isdir(os.path.join(_parent_dir, 'ffmpeg')) and os.path.isdir(os.path.join(_parent_dir, 'bento4')):
                self.install_dir = _parent_dir
                logger.info(f"检测到工具在上级目录，使用: {self.install_dir}")
        else:
            program_files_dir = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'BilibiliDownloadTool')
            user_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming')), 'BilibiliDownloadTool')
            
            if self._is_admin() or self._check_write_permission(program_files_dir):
                self.install_dir = program_files_dir
            else:
                self.install_dir = user_data_dir
        
        self.ffmpeg_dir = os.path.join(self.install_dir, 'ffmpeg', 'bin')
        self.bento4_dir = os.path.join(self.install_dir, 'bento4', 'bin')
        
        self.ffmpeg_path = os.path.join(self.ffmpeg_dir, 'ffmpeg.exe')
        self.mp4decrypt_path = os.path.join(self.bento4_dir, 'mp4decrypt.exe')

        if not os.path.exists(self.mp4decrypt_path):
            nested = os.path.join(self.install_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin', 'mp4decrypt.exe')
            if os.path.exists(nested):
                self.bento4_dir = os.path.join(self.install_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
                self.mp4decrypt_path = nested

        self.project_root = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            self.project_root = os.path.dirname(sys.executable)
        
        logger.info(f"工具管理器初始化，安装路径: {self.install_dir}")
    
    def _is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def _check_write_permission(self, directory):
        try:
            test_file = os.path.join(directory, '.test_permission.tmp')
            os.makedirs(directory, exist_ok=True)
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False
    
    def _find_local_tools(self):
        """在工作目录中查找本地工具文件，返回找到的路径字典"""
        local = {}
        
        ffmpeg_candidates = [
            os.path.join(self.project_root, 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(self.project_root, 'ffmpeg', 'bin'),
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            parent_dir = os.path.dirname(exe_dir)
            ffmpeg_candidates.insert(0, os.path.join(parent_dir, 'ffmpeg', 'bin', 'ffmpeg.exe'))
            ffmpeg_candidates.insert(1, os.path.join(parent_dir, 'ffmpeg', 'bin'))
            ffmpeg_candidates.insert(2, os.path.join(exe_dir, 'ffmpeg', 'bin', 'ffmpeg.exe'))
            ffmpeg_candidates.insert(3, os.path.join(exe_dir, 'ffmpeg', 'bin'))
        for path in ffmpeg_candidates:
            if os.path.isfile(path):
                local['ffmpeg'] = path
                local['ffmpeg_dir'] = os.path.dirname(path)
                break
            elif os.path.isdir(path):
                exe = os.path.join(path, 'ffmpeg.exe')
                if os.path.isfile(exe):
                    local['ffmpeg'] = exe
                    local['ffmpeg_dir'] = path
                    break
        
        bento4_candidates = [
            os.path.join(self.project_root, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin', 'mp4decrypt.exe'),
            os.path.join(self.project_root, 'bento4', 'bin', 'mp4decrypt.exe'),
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            parent_dir = os.path.dirname(exe_dir)
            bento4_candidates.insert(0, os.path.join(parent_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin', 'mp4decrypt.exe'))
            bento4_candidates.insert(1, os.path.join(parent_dir, 'bento4', 'bin', 'mp4decrypt.exe'))
            bento4_candidates.insert(2, os.path.join(exe_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin', 'mp4decrypt.exe'))
            bento4_candidates.insert(3, os.path.join(exe_dir, 'bento4', 'bin', 'mp4decrypt.exe'))
        for path in bento4_candidates:
            if os.path.isfile(path):
                local['mp4decrypt'] = path
                local['bento4_dir'] = os.path.dirname(path)
                break
        
        logger.info(f"本地工具查找结果: {list(local.keys())}")
        return local
    
    def get_source_paths(self):
        source_paths = {}
        
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
            source_paths['ffmpeg'] = os.path.join(base_dir, 'ffmpeg', 'bin')
            source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'bin')
            if not os.path.exists(source_paths.get('bento4', '')):
                source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
        else:
            base_dir = self.project_root
            source_paths['ffmpeg'] = os.path.join(base_dir, 'ffmpeg', 'bin')
            source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
        
        return source_paths
    
    def check_tools_installed(self):
        results = {
            'ffmpeg_exists': os.path.exists(self.ffmpeg_path),
            'bento4_exists': os.path.exists(self.mp4decrypt_path),
            'ffmpeg_path': self.ffmpeg_path,
            'bento4_path': self.mp4decrypt_path
        }
        logger.info(f"工具检查结果: {results}")
        return results
    
    def _download_file(self, url, save_path, progress_callback=None):
        try:
            resp = requests.get(url, stream=True, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            resp.raise_for_status()
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            pct = int(downloaded * 100 / total_size)
                            progress_callback(pct, f"下载中... {pct}%")
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _extract_zip(self, zip_path, target_dir, progress_callback=None):
        import zipfile
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                total_files = len(z.namelist())
                for i, name in enumerate(z.namelist()):
                    z.extract(name, target_dir)
                    if progress_callback and total_files > 0:
                        pct = int((i + 1) / total_files * 100)
                        progress_callback(pct, f"解压中... {pct}%")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _install_from_local(self, local_tools, progress_callback=None):
        """从本地工作目录安装工具到目标路径"""
        results = {'ffmpeg_installed': False, 'bento4_installed': False}
        
        def update(p, m):
            if progress_callback:
                progress_callback(p, m)
        
        if 'ffmpeg' in local_tools:
            update(35, "从本地复制 FFmpeg...")
            if not os.path.exists(self.ffmpeg_dir):
                os.makedirs(self.ffmpeg_dir, exist_ok=True)
            src = local_tools['ffmpeg']
            shutil.copy2(src, self.ffmpeg_path)
            update(45, "FFmpeg 安装完成")
            results['ffmpeg_installed'] = True
        else:
            update(35, "本地未找到 FFmpeg")
        
        if 'mp4decrypt' in local_tools:
            update(55, "从本地复制 Bento4...")
            if not os.path.exists(self.bento4_dir):
                os.makedirs(self.bento4_dir, exist_ok=True)
            src = local_tools['mp4decrypt']
            shutil.copy2(src, self.mp4decrypt_path)
            update(65, "Bento4 安装完成")
            results['bento4_installed'] = True
        else:
            update(55, "本地未找到 Bento4")
        
        return results
    
    def _install_from_cdn(self, need_ffmpeg, need_bento4, progress_callback=None):
        """从 CDN 下载并安装工具"""
        results = {'ffmpeg_installed': False, 'bento4_installed': False}
        
        def update(p, m):
            if progress_callback:
                progress_callback(int(p), m)
        
        temp_dir = os.path.join(self.install_dir, '_temp_download')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            if need_ffmpeg:
                update(30, "正在从网络下载 FFmpeg...")
                ffmpeg_zip = os.path.join(temp_dir, 'ffmpeg.zip')
                ok, err = self._download_file(CDN_URLS['ffmpeg'], ffmpeg_zip,
                                              lambda p, m: progress_callback(int(30 + p * 0.3), f"下载 FFmpeg: {m}") if progress_callback else None)
                if ok:
                    update(60, "正在解压 FFmpeg...")
                    extract_dir = os.path.join(temp_dir, 'ffmpeg_extract')
                    self._extract_zip(ffmpeg_zip, extract_dir,
                                       lambda p, m: progress_callback(int(60 + p * 0.15), f"解压 FFmpeg: {m}") if progress_callback else None)
                    
                    found_exe = None
                    for root, dirs, files in os.walk(extract_dir):
                        if 'ffmpeg.exe' in files:
                            found_exe = os.path.join(root, 'ffmpeg.exe')
                            break
                    
                    if found_exe:
                        os.makedirs(self.ffmpeg_dir, exist_ok=True)
                        shutil.copy2(found_exe, self.ffmpeg_path)
                        ffprobe_src = found_exe.replace('ffmpeg.exe', 'ffprobe.exe')
                        if os.path.isfile(ffprobe_src):
                            shutil.copy2(ffprobe_src, os.path.join(self.ffmpeg_dir, 'ffprobe.exe'))
                        update(75, "FFmpeg 安装完成")
                        results['ffmpeg_installed'] = True
                    else:
                        update(75, "FFmpeg 压缩包内未找到 ffmpeg.exe")
                else:
                    update(75, f"FFmpeg 下载失败: {err}")
            
            if need_bento4:
                p_start = 77 if results.get('ffmpeg_installed') else 65
                update(p_start, "正在从网络下载 Bento4...")
                bento4_zip = os.path.join(temp_dir, 'bento4.zip')
                
                def bento_progress(p, m):
                    if progress_callback:
                        progress_callback(int(p_start + p * 0.2), f"下载 Bento4: {m}")
                
                ok, err = self._download_file(CDN_URLS['bento4'], bento4_zip, bento_progress)
                if ok:
                    update(88, "正在解压 Bento4...")
                    extract_dir = os.path.join(temp_dir, 'bento4_extract')
                    self._extract_zip(bento4_zip, extract_dir,
                                       lambda p, m: progress_callback(int(88 + p * 0.08), f"解压 Bento4: {m}") if progress_callback else None)
                    
                    found_exe = None
                    for root, dirs, files in os.walk(extract_dir):
                        if 'mp4decrypt.exe' in files:
                            found_exe = os.path.join(root, 'mp4decrypt.exe')
                            break
                    
                    if found_exe:
                        os.makedirs(self.bento4_dir, exist_ok=True)
                        shutil.copy2(found_exe, self.mp4decrypt_path)
                        update(96, "Bento4 安装完成")
                        results['bento4_installed'] = True
                    else:
                        update(96, "Bento4 压缩包内未找到 mp4decrypt.exe")
                else:
                    update(96, f"Bento4 下载失败: {err}")
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        
        return results

    def install_tools(self, force=False, progress_callback=None):
        results = {
            'success': False,
            'message': '',
            'ffmpeg_installed': False,
            'bento4_installed': False
        }
        
        def update_progress(progress, message):
            if progress_callback:
                try:
                    progress_callback(progress, message)
                except Exception as e:
                    logger.warning(f"进度回调失败: {str(e)}")
            logger.info(f"{progress}%: {message}")
        
        try:
            update_progress(0, "检查工具状态...")
            
            check_result = self.check_tools_installed()
            if not force and check_result['ffmpeg_exists'] and check_result['bento4_exists']:
                update_progress(25, "检查 FFmpeg...")
                time.sleep(0.15)
                update_progress(50, f"FFmpeg已就绪: {check_result['ffmpeg_path']}")
                time.sleep(0.15)
                update_progress(75, "检查 Bento4...")
                time.sleep(0.15)
                update_progress(90, f"Bento4已就绪: {check_result['bento4_path']}")
                time.sleep(0.3)
                
                results['success'] = True
                results['message'] = '工具已存在，无需重新安装'
                results['ffmpeg_installed'] = True
                results['bento4_installed'] = True
                update_progress(100, results['message'])
                time.sleep(0.5)
                return results
            
            local_tools = self._find_local_tools()
            has_local_ffmpeg = 'ffmpeg' in local_tools
            has_local_bento4 = 'mp4decrypt' in local_tools
            
            need_ffmpeg = force or not check_result['ffmpeg_exists']
            need_bento4 = force or not check_result['bento4_exists']
            
            if not os.path.exists(self.install_dir):
                os.makedirs(self.install_dir, exist_ok=True)
            
            if has_local_ffmpeg or has_local_bento4:
                update_progress(10, "检测到本地工具文件，正在安装...")
                local_results = self._install_from_local(local_tools, progress_callback)
                results['ffmpeg_installed'] = results['ffmpeg_installed'] or local_results.get('ffmpeg_installed', False)
                results['bento4_installed'] = results['bento4_installed'] or local_results.get('bento4_installed', False)
                
                need_ffmpeg = need_ffmpeg and not results['ffmpeg_installed']
                need_bento4 = need_bento4 and not results['bento4_installed']
            
            if need_ffmpeg or need_bento4:
                update_progress(20, "本地未找到全部工具，准备从网络下载...")
                cdn_results = self._install_from_cdn(need_ffmpeg, need_bento4, progress_callback)
                results['ffmpeg_installed'] = results['ffmpeg_installed'] or cdn_results.get('ffmpeg_installed', False)
                results['bento4_installed'] = results['bento4_installed'] or cdn_results.get('bento4_installed', False)
            
            final_check = self.check_tools_installed()
            if final_check['ffmpeg_exists'] and final_check['bento4_exists']:
                results['success'] = True
                results['message'] = '工具安装成功'
            elif final_check['ffmpeg_exists']:
                results['message'] = '仅 FFmpeg 安装成功，Bento4 安装失败'
            elif final_check['bento4_exists']:
                results['message'] = '仅 Bento4 安装成功，FFmpeg 安装失败'
            else:
                results['message'] = '工具安装失败，请检查网络连接后重试'
            
            update_progress(100, results['message'])
            return results
            
        except PermissionError as e:
            logger.error(f"权限不足: {str(e)}")
            results['success'] = False
            results['message'] = '权限不足，需要管理员权限'
            return results
        except Exception as e:
            logger.error(f"安装工具失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'安装工具失败: {str(e)}'
            return results
    
    def add_to_path(self, user_only=True):
        results = {'success': False, 'message': ''}
        try:
            import winreg
            if user_only:
                root_key = winreg.HKEY_CURRENT_USER
                sub_key = r'Environment'
            else:
                root_key = winreg.HKEY_LOCAL_MACHINE
                sub_key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
            
            key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            
            paths_to_add = [self.ffmpeg_dir, self.bento4_dir]
            paths_updated = False
            for path in paths_to_add:
                if path not in current_path:
                    current_path = f"{current_path};{path}" if current_path else path
                    paths_updated = True
                    logger.info(f"添加到PATH: {path}")
            
            if paths_updated:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, current_path)
                winreg.CloseKey(key)
                self._broadcast_env_change()
                results['success'] = True
                results['message'] = '环境变量更新成功，请重启应用或重新登录'
            else:
                results['success'] = True
                results['message'] = '环境变量已包含工具路径'
            
            logger.info(results['message'])
            return results
        except PermissionError:
            results['success'] = False
            results['message'] = '权限不足，请以管理员身份运行'
            return results
        except Exception as e:
            logger.error(f"更新环境变量失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'更新环境变量失败: {str(e)}'
            return results
    
    def _broadcast_env_change(self):
        try:
            import win32gui
            import win32con
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x1A
            win32gui.SendMessageTimeout(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                'Environment', win32con.SMTO_ABORTIFHUNG, 5000
            )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"广播环境变量变更失败: {str(e)}")
    
    def remove_from_path(self, user_only=True):
        results = {'success': False, 'message': ''}
        try:
            import winreg
            if user_only:
                root_key = winreg.HKEY_CURRENT_USER
                sub_key = r'Environment'
            else:
                root_key = winreg.HKEY_LOCAL_MACHINE
                sub_key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
            
            key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            
            paths_to_remove = [self.ffmpeg_dir, self.bento4_dir]
            paths_updated = False
            for path in paths_to_remove:
                if path in current_path:
                    current_path = current_path.replace(path, '')
                    current_path = current_path.replace(';;', ';')
                    if current_path.startswith(';'):
                        current_path = current_path[1:]
                    if current_path.endswith(';'):
                        current_path = current_path[:-1]
                    paths_updated = True
                    logger.info(f"从PATH移除: {path}")
            
            if paths_updated:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, current_path)
                winreg.CloseKey(key)
                self._broadcast_env_change()
                results['success'] = True
                results['message'] = '环境变量更新成功'
            else:
                results['success'] = True
                results['message'] = '环境变量中没有工具路径'
            
            return results
        except Exception as e:
            logger.error(f"移除环境变量失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'移除环境变量失败: {str(e)}'
            return results
    
    def get_tool_paths(self):
        return {
            'install_dir': self.install_dir,
            'ffmpeg_dir': self.ffmpeg_dir,
            'bento4_dir': self.bento4_dir,
            'ffmpeg': self.ffmpeg_path,
            'mp4decrypt': self.mp4decrypt_path
        }


_tool_manager = None


def get_tool_manager():
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager
