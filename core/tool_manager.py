import os
import sys
import time
import shutil
import logging
import subprocess
import requests
from pathlib import Path

from platform_utils import (
    IS_MACOS, IS_WINDOWS, exe, get_cdn_url, get_bento4_sdk_dirname,
    app_data_dir, program_files_dir, is_admin,
    add_to_system_path, remove_from_system_path,
)

logger = logging.getLogger(__name__)


def _app_tool_dirs():
    """返回可能存放工具的"用户数据目录"列表（各平台不同）。

    历史上这里硬编码 Windows 的 LOCALAPPDATA/APPDATA，在 Linux/macOS 上
    会指向不存在的路径（甚至因反斜杠而变成奇怪的文件名）。
    """
    dirs = []
    for d in (app_data_dir(), program_files_dir()):
        if d and d not in dirs:
            dirs.append(d)
    #Win留LocalApp
    if IS_WINDOWS:
        local = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
        cand = os.path.join(local, 'BilibiliDownloadTool')
        if cand not in dirs:
            dirs.append(cand)
    return dirs


def _download_file(url, save_path, progress_callback=None):
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


def _extract_zip(zip_path, target_dir, progress_callback=None):
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


def _extract_tar(archive_path, target_dir, progress_callback=None):
    """解压 .tar.xz / .tar.gz / .tar.bz2（Linux 下 ffmpeg 官方静态包是 tar.xz）。

    安全要点：逐个成员过滤绝对路径与 ".."，避免压缩包穿越写入目标目录之外。
    """
    import tarfile
    try:
        with tarfile.open(archive_path, 'r:*') as tf:
            members = tf.getmembers()
            total = len(members) or 1
            base = os.path.abspath(target_dir)
            for i, m in enumerate(members):
                name = m.name
                # 跳过绝对与穿越
                if name.startswith('/') or name.startswith('\\'):
                    continue
                dest = os.path.abspath(os.path.join(base, name))
                if not (dest == base or dest.startswith(base + os.sep)):
                    continue
                tf.extract(m, target_dir)
                if progress_callback and i % 20 == 0:
                    progress_callback(int((i + 1) / total * 100), "解压中...")
        return True, None
    except Exception as e:
        return False, str(e)


def _extract_archive(archive_path, target_dir, progress_callback=None):
    """按扩展名分派到 zip / tar 解压器。"""
    low = archive_path.lower()
    if low.endswith('.zip'):
        return _extract_zip(archive_path, target_dir, progress_callback)
    if low.endswith(('.tar.xz', '.txz', '.tar.gz', '.tgz', '.tar.bz2', '.tar')):
        return _extract_tar(archive_path, target_dir, progress_callback)
    # 未知先zip后tar
    ok, err = _extract_zip(archive_path, target_dir, progress_callback)
    if ok:
        return ok, err
    return _extract_tar(archive_path, target_dir, progress_callback)


def _copy_if_needed(src, dst):
    """复制工具文件。当源与目标为同一文件时跳过，避免 SameFileError。
    返回 True 表示已在目标就位（已复制或本就同一文件）。"""
    try:
        if os.path.abspath(src) == os.path.abspath(dst) or os.path.samefile(src, dst):
            return True
    except OSError:
        pass
    shutil.copy2(src, dst)
    return True


def install_tools_from_cdn(dest_dir, need_ffmpeg=True, need_bento4=True, progress_callback=None):
    """从 CDN 下载 ffmpeg/bento4 并安装到 dest_dir/<name>/bin。
    供安装器与运行时自愈共用。返回 {'ffmpeg_installed','bento4_installed'}。"""
    results = {'ffmpeg_installed': False, 'bento4_installed': False}

    def update(p, m):
        if progress_callback:
            progress_callback(int(p), m)

    temp_dir = os.path.join(dest_dir, '_temp_download')
    os.makedirs(temp_dir, exist_ok=True)

    try:
        if need_ffmpeg:
            update(30, "正在从网络下载 FFmpeg...")
            ffmpeg_url = get_cdn_url('ffmpeg')
            #Linux静态tar.xz
            # 扩展名不匹配会失败
            _ff_ext = '.tar.xz' if ffmpeg_url.lower().endswith(('.tar.xz', '.txz')) else '.zip'
            ffmpeg_archive = os.path.join(temp_dir, 'ffmpeg' + _ff_ext)
            ok, err = _download_file(
                ffmpeg_url, ffmpeg_archive,
                lambda p, m: progress_callback(int(30 + p * 0.3), f"下载 FFmpeg: {m}") if progress_callback else None
            )
            if ok:
                update(60, "正在解压 FFmpeg...")
                extract_dir = os.path.join(temp_dir, 'ffmpeg_extract')
                _extract_archive(
                    ffmpeg_archive, extract_dir,
                    lambda p, m: progress_callback(int(60 + p * 0.15), f"解压 FFmpeg: {m}") if progress_callback else None
                )

                found_exe = None
                ffmpeg_name = exe('ffmpeg')
                for root, dirs, files in os.walk(extract_dir):
                    if ffmpeg_name in files:
                        found_exe = os.path.join(root, ffmpeg_name)
                        break

                if found_exe:
                    ffmpeg_dir = os.path.join(dest_dir, 'ffmpeg', 'bin')
                    os.makedirs(ffmpeg_dir, exist_ok=True)
                    _copy_if_needed(found_exe, os.path.join(ffmpeg_dir, ffmpeg_name))
                    if not IS_WINDOWS:
                        try:
                            os.chmod(os.path.join(ffmpeg_dir, ffmpeg_name), 0o755)
                        except Exception:
                            pass
                    ffprobe_name = exe('ffprobe')
                    ffprobe_src = os.path.join(os.path.dirname(found_exe), ffprobe_name)
                    if os.path.isfile(ffprobe_src):
                        _copy_if_needed(ffprobe_src, os.path.join(ffmpeg_dir, ffprobe_name))
                        if not IS_WINDOWS:
                            try:
                                os.chmod(os.path.join(ffmpeg_dir, ffprobe_name), 0o755)
                            except Exception:
                                pass
                    update(75, "FFmpeg 安装完成")
                    results['ffmpeg_installed'] = True
                else:
                    update(75, f"FFmpeg 压缩包内未找到 {ffmpeg_name}")
            else:
                update(75, f"FFmpeg 下载失败: {err}")

        if need_bento4:
            p_start = 77 if results.get('ffmpeg_installed') else 65
            update(p_start, "正在从网络下载 Bento4...")
            bento4_url = get_cdn_url('bento4')
            _b4_ext = '.tar.xz' if bento4_url.lower().endswith(('.tar.xz', '.txz')) else '.zip'
            bento4_archive = os.path.join(temp_dir, 'bento4' + _b4_ext)

            def bento_progress(p, m):
                if progress_callback:
                    progress_callback(int(p_start + p * 0.2), f"下载 Bento4: {m}")

            ok, err = _download_file(bento4_url, bento4_archive, bento_progress)
            if ok:
                update(88, "正在解压 Bento4...")
                extract_dir = os.path.join(temp_dir, 'bento4_extract')
                _extract_archive(
                    bento4_archive, extract_dir,
                    lambda p, m: progress_callback(int(88 + p * 0.08), f"解压 Bento4: {m}") if progress_callback else None
                )

                found_exe = None
                mp4decrypt_name = exe('mp4decrypt')
                for root, dirs, files in os.walk(extract_dir):
                    if mp4decrypt_name in files:
                        found_exe = os.path.join(root, mp4decrypt_name)
                        break

                if found_exe:
                    bento4_dir = os.path.join(dest_dir, 'bento4', 'bin')
                    os.makedirs(bento4_dir, exist_ok=True)
                    _copy_if_needed(found_exe, os.path.join(bento4_dir, mp4decrypt_name))
                    if not IS_WINDOWS:
                        try:
                            os.chmod(os.path.join(bento4_dir, mp4decrypt_name), 0o755)
                        except Exception:
                            pass
                    update(96, "Bento4 安装完成")
                    results['bento4_installed'] = True
                else:
                    update(96, f"Bento4 压缩包内未找到 {mp4decrypt_name}")
            else:
                update(96, f"Bento4 下载失败: {err}")
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return results


class ToolManager:

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.install_dir = os.path.dirname(sys.executable)
            _parent_dir = os.path.dirname(self.install_dir)
            #PyI6.x在_internal
            _internal_dir = os.path.join(self.install_dir, '_internal')
            if os.path.isdir(_internal_dir):
                self.install_dir = _internal_dir
                logger.info(f"检测到 PyInstaller _internal 目录，工具/运行文件均在此: {self.install_dir}")
            elif os.path.isdir(os.path.join(_parent_dir, 'ffmpeg')) and os.path.isdir(os.path.join(_parent_dir, 'bento4')):
                self.install_dir = _parent_dir
                logger.info(f"检测到工具在上级目录，使用: {self.install_dir}")
        else:
            # 源码 / 非打包运行：
            # 仓库自带的直接用
            # 否则落用户可写目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if self._looks_like_tool_home(project_root):
                self.install_dir = project_root
            elif IS_MACOS:
                self.install_dir = app_data_dir()
            elif IS_WINDOWS:
                pf_dir = program_files_dir()
                ud_dir = app_data_dir()
                if is_admin() or self._check_write_permission(pf_dir):
                    self.install_dir = pf_dir
                else:
                    self.install_dir = ud_dir
            else:
                # 优先用户目录
                self.install_dir = app_data_dir()

        self.ffmpeg_dir = os.path.join(self.install_dir, 'ffmpeg', 'bin')
        self.bento4_dir = os.path.join(self.install_dir, 'bento4', 'bin')

        self.ffmpeg_path = os.path.join(self.ffmpeg_dir, exe('ffmpeg'))
        self.mp4decrypt_path = os.path.join(self.bento4_dir, exe('mp4decrypt'))

        if not os.path.exists(self.mp4decrypt_path):
            nested = os.path.join(self.install_dir, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt'))
            if os.path.exists(nested):
                self.bento4_dir = os.path.join(self.install_dir, 'bento4', get_bento4_sdk_dirname(), 'bin')
                self.mp4decrypt_path = nested

        self.project_root = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            self.project_root = os.path.dirname(sys.executable)

        if IS_MACOS:
            self._check_mac_system_tools()
        else:
            self._fallback_to_local_tools()

        logger.info(f"工具管理器初始化，安装路径: {self.install_dir}")
        logger.info(f"FFmpeg: {self.ffmpeg_path} (存在: {os.path.exists(self.ffmpeg_path)})")
        logger.info(f"Bento4 mp4decrypt: {self.mp4decrypt_path} (存在: {os.path.exists(self.mp4decrypt_path)})")

    def _fallback_to_local_tools(self):
        """如果install_dir下的工具不存在，尝试从本地/项目目录找到并使用"""
        need_ffmpeg = not os.path.exists(self.ffmpeg_path)
        need_bento4 = not os.path.exists(self.mp4decrypt_path)

        if not need_ffmpeg and not need_bento4:
            return

        logger.info("install_dir中工具不完整，尝试从本地查找...")
        local_tools = self._find_local_tools()

        if need_ffmpeg and 'ffmpeg' in local_tools:
            self.ffmpeg_path = local_tools['ffmpeg']
            self.ffmpeg_dir = local_tools.get('ffmpeg_dir', os.path.dirname(self.ffmpeg_path))
            logger.info(f"回退到本地FFmpeg: {self.ffmpeg_path}")

        if need_bento4 and 'mp4decrypt' in local_tools:
            self.mp4decrypt_path = local_tools['mp4decrypt']
            self.bento4_dir = local_tools.get('bento4_dir', os.path.dirname(self.mp4decrypt_path))
            logger.info(f"回退到本地Bento4: {self.mp4decrypt_path}")

        # 最后尝试系统PATH
        if need_ffmpeg and not os.path.exists(self.ffmpeg_path):
            sys_ffmpeg = shutil.which('ffmpeg')
            if sys_ffmpeg:
                self.ffmpeg_path = sys_ffmpeg
                self.ffmpeg_dir = os.path.dirname(sys_ffmpeg)
                logger.info(f"回退到系统FFmpeg: {sys_ffmpeg}")

        if need_bento4 and not os.path.exists(self.mp4decrypt_path):
            sys_mp4 = shutil.which(exe('mp4decrypt'))
            if sys_mp4:
                self.mp4decrypt_path = sys_mp4
                self.bento4_dir = os.path.dirname(sys_mp4)
                logger.info(f"回退到系统mp4detect: {sys_mp4}")

    def _check_mac_system_tools(self):
        if not IS_MACOS:
            return
        if not os.path.exists(self.ffmpeg_path):
            sys_ffmpeg = shutil.which('ffmpeg')
            if sys_ffmpeg:
                self.ffmpeg_path = sys_ffmpeg
                self.ffmpeg_dir = os.path.dirname(sys_ffmpeg)
                logger.info(f"macOS: 使用系统 FFmpeg: {sys_ffmpeg}")
        if not os.path.exists(self.mp4decrypt_path):
            sys_mp4decrypt = shutil.which('mp4decrypt')
            if sys_mp4decrypt:
                self.mp4decrypt_path = sys_mp4decrypt
                self.bento4_dir = os.path.dirname(sys_mp4decrypt)
                logger.info(f"macOS: 使用系统 mp4decrypt: {sys_mp4decrypt}")

    def _is_admin(self):
        return is_admin()

    def _check_write_permission(self, directory):
        try:
            test_file = os.path.join(directory, '.test_permission.tmp')
            os.makedirs(directory, exist_ok=True)
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except Exception:
            return False

    def _looks_like_tool_home(self, root):
        """判断 root 下是否已有随仓库/安装包分发的 ffmpeg 或 bento4 目录。"""
        if not root or not os.path.isdir(root):
            return False
        for sub in ('ffmpeg', 'bento4'):
            if os.path.isdir(os.path.join(root, sub)):
                return True
        return False

    def _find_local_tools(self):
        local = {}

        ffmpeg_candidates = [
            os.path.join(self.project_root, 'ffmpeg', 'bin', exe('ffmpeg')),
            os.path.join(self.project_root, 'ffmpeg', 'bin'),
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            parent_dir = os.path.dirname(exe_dir)
            internal_dir = os.path.join(exe_dir, '_internal')
            ffmpeg_candidates.insert(0, os.path.join(internal_dir, 'ffmpeg', 'bin', exe('ffmpeg')))
            ffmpeg_candidates.insert(1, os.path.join(internal_dir, 'ffmpeg', 'bin'))
            ffmpeg_candidates.insert(2, os.path.join(parent_dir, 'ffmpeg', 'bin', exe('ffmpeg')))
            ffmpeg_candidates.insert(3, os.path.join(parent_dir, 'ffmpeg', 'bin'))
            ffmpeg_candidates.insert(4, os.path.join(exe_dir, 'ffmpeg', 'bin', exe('ffmpeg')))
            ffmpeg_candidates.insert(5, os.path.join(exe_dir, 'ffmpeg', 'bin'))
            # 搜用户数据目录
            for _ad in _app_tool_dirs():
                ffmpeg_candidates.extend([
                    os.path.join(_ad, 'ffmpeg', 'bin', exe('ffmpeg')),
                    os.path.join(_ad, 'ffmpeg', 'bin'),
                ])
        else:
            # 源码搜dist与上级
            dist_internal = os.path.join(self.project_root, 'dist', 'BilibiliDownloader', '_internal', 'ffmpeg', 'bin')
            dist_root = os.path.join(self.project_root, 'dist', 'BilibiliDownloader', 'ffmpeg', 'bin')
            parent_project = os.path.dirname(self.project_root)
            ffmpeg_candidates.extend([
                os.path.join(dist_internal, exe('ffmpeg')),
                dist_internal,
                os.path.join(dist_root, exe('ffmpeg')),
                dist_root,
                os.path.join(parent_project, 'ffmpeg', 'bin', exe('ffmpeg')),
                os.path.join(parent_project, 'ffmpeg', 'bin'),
            ])
            for _ad in _app_tool_dirs():
                ffmpeg_candidates.extend([
                    os.path.join(_ad, 'ffmpeg', 'bin', exe('ffmpeg')),
                    os.path.join(_ad, 'ffmpeg', 'bin'),
                ])
            #也搜PATH的ffmpeg
            sys_ffmpeg = shutil.which(exe('ffmpeg'))
            if sys_ffmpeg:
                ffmpeg_candidates.append(sys_ffmpeg)

        for path in ffmpeg_candidates:
            if os.path.isfile(path):
                local['ffmpeg'] = path
                local['ffmpeg_dir'] = os.path.dirname(path)
                break
            elif os.path.isdir(path):
                ffmpeg_exe = os.path.join(path, exe('ffmpeg'))
                if os.path.isfile(ffmpeg_exe):
                    local['ffmpeg'] = ffmpeg_exe
                    local['ffmpeg_dir'] = path
                    break

        bento4_candidates = [
            os.path.join(self.project_root, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')),
            os.path.join(self.project_root, 'bento4', 'bin', exe('mp4decrypt')),
        ]
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            parent_dir = os.path.dirname(exe_dir)
            internal_dir = os.path.join(exe_dir, '_internal')
            bento4_candidates.insert(0, os.path.join(internal_dir, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')))
            bento4_candidates.insert(1, os.path.join(internal_dir, 'bento4', 'bin', exe('mp4decrypt')))
            bento4_candidates.insert(2, os.path.join(parent_dir, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')))
            bento4_candidates.insert(3, os.path.join(parent_dir, 'bento4', 'bin', exe('mp4decrypt')))
            bento4_candidates.insert(4, os.path.join(exe_dir, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')))
            bento4_candidates.insert(5, os.path.join(exe_dir, 'bento4', 'bin', exe('mp4decrypt')))
            for _ad in _app_tool_dirs():
                bento4_candidates.extend([
                    os.path.join(_ad, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')),
                    os.path.join(_ad, 'bento4', 'bin', exe('mp4decrypt')),
                ])
        else:
            # 源码运行另搜dist
            dist_internal_b4 = os.path.join(self.project_root, 'dist', 'BilibiliDownloader', '_internal', 'bento4')
            parent_project = os.path.dirname(self.project_root)
            bento4_candidates.extend([
                os.path.join(dist_internal_b4, get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')),
                os.path.join(dist_internal_b4, 'bin', exe('mp4decrypt')),
                os.path.join(parent_project, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')),
                os.path.join(parent_project, 'bento4', 'bin', exe('mp4decrypt')),
            ])
            for _ad in _app_tool_dirs():
                bento4_candidates.extend([
                    os.path.join(_ad, 'bento4', get_bento4_sdk_dirname(), 'bin', exe('mp4decrypt')),
                    os.path.join(_ad, 'bento4', 'bin', exe('mp4decrypt')),
                ])
            #PATH找mp4d
            sys_mp4decrypt = shutil.which(exe('mp4decrypt'))
            if sys_mp4decrypt:
                bento4_candidates.append(sys_mp4decrypt)

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
                source_paths['bento4'] = os.path.join(base_dir, 'bento4', get_bento4_sdk_dirname(), 'bin')
        else:
            base_dir = self.project_root
            source_paths['ffmpeg'] = os.path.join(base_dir, 'ffmpeg', 'bin')
            source_paths['bento4'] = os.path.join(base_dir, 'bento4', get_bento4_sdk_dirname(), 'bin')

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

    def _install_from_local(self, local_tools, progress_callback=None):
        results = {'ffmpeg_installed': False, 'bento4_installed': False}

        def update(p, m):
            if progress_callback:
                progress_callback(p, m)

        if 'ffmpeg' in local_tools:
            update(35, "从本地复制 FFmpeg...")
            if not os.path.exists(self.ffmpeg_dir):
                os.makedirs(self.ffmpeg_dir, exist_ok=True)
            src = local_tools['ffmpeg']
            _copy_if_needed(src, self.ffmpeg_path)
            if IS_MACOS or IS_WINDOWS:
                try:
                    os.chmod(self.ffmpeg_path, 0o755)
                except Exception:
                    pass
            update(45, "FFmpeg 安装完成")
            results['ffmpeg_installed'] = True
        else:
            update(35, "本地未找到 FFmpeg")

        if 'mp4decrypt' in local_tools:
            update(55, "从本地复制 Bento4...")
            if not os.path.exists(self.bento4_dir):
                os.makedirs(self.bento4_dir, exist_ok=True)
            src = local_tools['mp4decrypt']
            _copy_if_needed(src, self.mp4decrypt_path)
            if IS_MACOS:
                try:
                    os.chmod(self.mp4decrypt_path, 0o755)
                except Exception:
                    pass
            update(65, "Bento4 安装完成")
            results['bento4_installed'] = True
        else:
            update(55, "本地未找到 Bento4")

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
                cdn_results = install_tools_from_cdn(self.install_dir, need_ffmpeg, need_bento4, progress_callback)
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
        paths_to_add = [self.ffmpeg_dir, self.bento4_dir]
        success, message = add_to_system_path(paths_to_add, user_only=user_only)
        return {'success': success, 'message': message}

    def remove_from_path(self, user_only=True):
        paths_to_remove = [self.ffmpeg_dir, self.bento4_dir]
        success, message = remove_from_system_path(paths_to_remove, user_only=user_only)
        return {'success': success, 'message': message}

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
