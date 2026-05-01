"""
工具管理器 - 负责管理FFmpeg和Bento4工具的部署
这样还能缺失我把电脑吃了
"""
import os
import sys
import time
import shutil
import logging
import subprocess
import ctypes
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolManager:
    """工具管理器"""
    
    def __init__(self):
        """初始化工具管理器"""
        # 默认安装路径：首先尝试Program Files，如果没有权限则使用用户目录
        program_files_dir = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'BilibiliDownloadTool')
        user_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming')), 'BilibiliDownloadTool')
        
        # 检查是否有写入权限
        if self._is_admin() or self._check_write_permission(program_files_dir):
            self.install_dir = program_files_dir
            logger.info(f"使用系统目录: {self.install_dir}")
        else:
            self.install_dir = user_data_dir
            logger.info(f"使用用户目录: {self.install_dir}")
        
        self.ffmpeg_dir = os.path.join(self.install_dir, 'ffmpeg', 'bin')
        self.bento4_dir = os.path.join(self.install_dir, 'bento4', 'bin')
        
        # 工具路径
        self.ffmpeg_path = os.path.join(self.ffmpeg_dir, 'ffmpeg.exe')
        self.mp4decrypt_path = os.path.join(self.bento4_dir, 'mp4decrypt.exe')
        
        logger.info(f"工具管理器初始化，安装路径: {self.install_dir}")
    
    def _is_admin(self):
        """检查是否有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def _check_write_permission(self, directory):
        """检查是否有写入权限"""
        try:
            # 尝试创建一个临时文件
            test_file = os.path.join(directory, '.test_permission.tmp')
            os.makedirs(directory, exist_ok=True)
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False
    
    def request_admin_permission(self):
        """请求管理员权限，重新启动程序"""
        try:
            import ctypes
            from PyQt5.QtWidgets import QMessageBox
            
            # 提示用户需要管理员权限
            result = QMessageBox.question(
                None, 
                "需要管理员权限", 
                "为了将工具安装到系统目录，需要管理员权限。\n是否以管理员身份重新运行程序？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # 重新启动程序，请求管理员权限
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                sys.exit(0)
            return False
        except Exception as e:
            logger.error(f"请求管理员权限失败: {str(e)}")
            return False
    
    def get_source_paths(self):
        """获取源工具路径（从打包的资源或开发目录）"""
        source_paths = {}
        
        import sys
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller打包环境
            base_dir = sys._MEIPASS
            source_paths['ffmpeg'] = os.path.join(base_dir, 'ffmpeg', 'bin')
            source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'bin')
            
            # 如果找不到，尝试完整路径
            if not os.path.exists(source_paths['bento4']):
                source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
        else:
            # 开发环境
            base_dir = os.path.dirname(os.path.abspath(__file__))
            source_paths['ffmpeg'] = os.path.join(base_dir, 'ffmpeg', 'bin')
            source_paths['bento4'] = os.path.join(base_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
        
        logger.info(f"源工具路径: ffmpeg={source_paths.get('ffmpeg')}, bento4={source_paths.get('bento4')}")
        return source_paths
    
    def check_tools_installed(self):
        """检查工具是否已正确安装"""
        results = {
            'ffmpeg_exists': os.path.exists(self.ffmpeg_path),
            'bento4_exists': os.path.exists(self.mp4decrypt_path),
            'ffmpeg_path': self.ffmpeg_path,
            'bento4_path': self.mp4decrypt_path
        }
        
        logger.info(f"工具检查结果: {results}")
        return results
    
    def install_tools(self, force=False, progress_callback=None):
        """
        安装工具到目标目录
        
        Args:
            force: 是否强制覆盖安装
            progress_callback: 进度回调函数，格式为 callback(progress, message)
            
        Returns:
            dict: 安装结果
        """
        results = {
            'success': False,
            'message': '',
            'ffmpeg_installed': False,
            'bento4_installed': False
        }
        
        def update_progress(progress, message):
            """更新进度"""
            if progress_callback:
                try:
                    progress_callback(progress, message)
                except Exception as e:
                    logger.warning(f"进度回调失败: {str(e)}")
            logger.info(f"{progress}%: {message}")
        
        try:
            update_progress(0, "检查工具状态...")
            
            # 检查是否已安装
            check_result = self.check_tools_installed()
            if not force and check_result['ffmpeg_exists'] and check_result['bento4_exists']:
                update_progress(25, "检查 FFmpeg...")
                time.sleep(0.2)
                update_progress(50, f"FFmpeg已就绪: {check_result['ffmpeg_path']}")
                time.sleep(0.2)
                update_progress(75, "检查 Bento4...")
                time.sleep(0.2)
                update_progress(90, f"Bento4已就绪: {check_result['bento4_path']}")
                time.sleep(0.3)
                
                results['success'] = True
                results['message'] = '工具已存在，无需重新安装'
                results['ffmpeg_installed'] = True
                results['bento4_installed'] = True
                update_progress(100, results['message'])
                time.sleep(0.5)  # 给用户一点时间看到完成信息
                return results
            
            update_progress(10, "获取工具源路径...")
            # 获取源路径
            source_paths = self.get_source_paths()
            
            update_progress(20, f"创建安装目录: {self.install_dir}")
            # 创建安装目录
            if not os.path.exists(self.install_dir):
                os.makedirs(self.install_dir, exist_ok=True)
                logger.info(f"创建安装目录: {self.install_dir}")
            
            # 安装 FFmpeg
            if force or not check_result['ffmpeg_exists']:
                update_progress(30, "准备安装 FFmpeg...")
                ffmpeg_source = source_paths['ffmpeg']
                if os.path.exists(ffmpeg_source):
                    update_progress(32, f"FFmpeg源路径: {ffmpeg_source}")
                    
                    if not os.path.exists(self.ffmpeg_dir):
                        os.makedirs(self.ffmpeg_dir, exist_ok=True)
                    
                    # 获取文件列表并复制
                    files = [f for f in os.listdir(ffmpeg_source) if os.path.isfile(os.path.join(ffmpeg_source, f))]
                    total_files = len(files)
                    update_progress(35, f"发现 {total_files} 个 FFmpeg 文件")
                    
                    for idx, filename in enumerate(files):
                        src_file = os.path.join(ffmpeg_source, filename)
                        dst_file = os.path.join(self.ffmpeg_dir, filename)
                        shutil.copy2(src_file, dst_file)
                        
                        # 更新进度
                        ffmpeg_progress = 35 + (idx + 1) / total_files * 15
                        update_progress(int(ffmpeg_progress), f"复制 FFmpeg: {filename}")
                    
                    results['ffmpeg_installed'] = True
                    update_progress(50, "FFmpeg 安装完成")
                else:
                    logger.warning(f"FFmpeg源不存在: {ffmpeg_source}")
                    update_progress(50, f"警告: FFmpeg源不存在")
            
            # 安装 Bento4
            if force or not check_result['bento4_exists']:
                update_progress(55, "准备安装 Bento4...")
                bento4_source = source_paths['bento4']
                if os.path.exists(bento4_source):
                    update_progress(57, f"Bento4源路径: {bento4_source}")
                    
                    if not os.path.exists(self.bento4_dir):
                        os.makedirs(self.bento4_dir, exist_ok=True)
                    
                    # 获取文件列表并复制
                    files = [f for f in os.listdir(bento4_source) if os.path.isfile(os.path.join(bento4_source, f))]
                    total_files = len(files)
                    update_progress(60, f"发现 {total_files} 个 Bento4 文件")
                    
                    for idx, filename in enumerate(files):
                        src_file = os.path.join(bento4_source, filename)
                        dst_file = os.path.join(self.bento4_dir, filename)
                        shutil.copy2(src_file, dst_file)
                        
                        # 更新进度
                        bento4_progress = 60 + (idx + 1) / total_files * 30
                        update_progress(int(bento4_progress), f"复制 Bento4: {filename}")
                    
                    results['bento4_installed'] = True
                    update_progress(90, "Bento4 安装完成")
                else:
                    logger.warning(f"Bento4源不存在: {bento4_source}")
                    update_progress(90, f"警告: Bento4源不存在")
            
            update_progress(95, "验证安装...")
            # 检查最终结果
            final_check = self.check_tools_installed()
            if final_check['ffmpeg_exists'] and final_check['bento4_exists']:
                results['success'] = True
                results['message'] = '工具安装成功'
            else:
                results['success'] = False
                results['message'] = '部分工具安装失败'
            
            update_progress(100, results['message'])
            return results
            
        except PermissionError as e:
            logger.error(f"权限不足: {str(e)}")
            results['success'] = False
            results['message'] = '权限不足，需要管理员权限'
            results['needs_admin'] = True
            return results
        except Exception as e:
            logger.error(f"安装工具失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'安装工具失败: {str(e)}'
            return results
    
    def add_to_path(self, user_only=True):
        """
        将工具目录添加到PATH环境变量
        
        Args:
            user_only: 是否只添加到用户环境变量
            
        Returns:
            dict: 操作结果
        """
        results = {
            'success': False,
            'message': ''
        }
        
        try:
            import winreg
            
            # 确定注册表路径
            if user_only:
                root_key = winreg.HKEY_CURRENT_USER
                sub_key = r'Environment'
            else:
                root_key = winreg.HKEY_LOCAL_MACHINE
                sub_key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
            
            # 打开注册表
            key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_ALL_ACCESS)
            
            # 获取当前PATH
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            
            # 检查是否已添加
            paths_to_add = [self.ffmpeg_dir, self.bento4_dir]
            paths_updated = False
            
            for path in paths_to_add:
                if path not in current_path:
                    current_path = f"{current_path};{path}" if current_path else path
                    paths_updated = True
                    logger.info(f"添加到PATH: {path}")
            
            if paths_updated:
                # 更新注册表
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, current_path)
                winreg.CloseKey(key)
                
                # 广播环境变量变更
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
            logger.error(results['message'])
            return results
        except Exception as e:
            logger.error(f"更新环境变量失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'更新环境变量失败: {str(e)}'
            return results
    
    def _broadcast_env_change(self):
        """广播环境变量变更消息"""
        try:
            import win32gui
            import win32con
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x1A
            
            win32gui.SendMessageTimeout(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                'Environment', win32con.SMTO_ABORTIFHUNG, 5000
            )
            logger.info("已广播环境变量变更消息")
        except ImportError:
            logger.warning("pywin32未安装，无法广播环境变量变更")
        except Exception as e:
            logger.warning(f"广播环境变量变更失败: {str(e)}")
    
    def remove_from_path(self, user_only=True):
        """
        从PATH环境变量中移除工具目录
        
        Args:
            user_only: 是否只从用户环境变量移除
            
        Returns:
            dict: 操作结果
        """
        results = {
            'success': False,
            'message': ''
        }
        
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
            
            # 移除路径
            paths_to_remove = [self.ffmpeg_dir, self.bento4_dir]
            paths_updated = False
            
            for path in paths_to_remove:
                if path in current_path:
                    # 移除路径，处理可能的分号
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
            
            logger.info(results['message'])
            return results
            
        except Exception as e:
            logger.error(f"移除环境变量失败: {str(e)}", exc_info=True)
            results['success'] = False
            results['message'] = f'移除环境变量失败: {str(e)}'
            return results
    
    def get_tool_paths(self):
        """获取工具路径"""
        return {
            'install_dir': self.install_dir,
            'ffmpeg_dir': self.ffmpeg_dir,
            'bento4_dir': self.bento4_dir,
            'ffmpeg': self.ffmpeg_path,
            'mp4decrypt': self.mp4decrypt_path
        }


# 全局工具管理器实例
_tool_manager = None


def get_tool_manager():
    """获取工具管理器单例"""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager
