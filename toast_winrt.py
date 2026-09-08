import os
import sys
import tempfile
import subprocess
import threading

# 应用标识（AUMID）：必须与 ui.py 中发送通知所用 _WINRT_TOAST_APP_ID 一致。
# Windows 通知中心只有在该 AUMID 关联到开始菜单快捷方式时才会显示 Toast 按钮。
APP_AUMID = "B站视频下载工具"
_APP_NAME = "B站视频下载工具"

_C_SHARP = r"""
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

public class ShortcutRegistrar
{
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    public class ShellLink { }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
    public interface IShellLinkW
    {
        [PreserveSig] int GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, uint fFlags);
        [PreserveSig] int GetIDList(out IntPtr ppidl);
        [PreserveSig] int SetIDList(IntPtr pidl);
        [PreserveSig] int GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cch);
        [PreserveSig] int SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        [PreserveSig] int GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cch);
        [PreserveSig] int SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
        [PreserveSig] int GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cch);
        [PreserveSig] int SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
        [PreserveSig] int GetHotkey(out short pwHotkey);
        [PreserveSig] int SetHotkey(short wHotkey);
        [PreserveSig] int GetShowCmd(out int piShowCmd);
        [PreserveSig] int SetShowCmd(int iShowCmd);
        [PreserveSig] int GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cch, out int piIcon);
        [PreserveSig] int SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
        [PreserveSig] int SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, uint dwReserved);
        [PreserveSig] int Resolve(IntPtr hwnd, uint fFlags);
        [PreserveSig] int SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
    }
    [StructLayout(LayoutKind.Explicit)]
    public struct PROPVARIANT
    {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(2)] public ushort wReserved1;
        [FieldOffset(4)] public ushort wReserved2;
        [FieldOffset(6)] public ushort wReserved3;
        [FieldOffset(8)] public IntPtr pwszVal;
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    public interface IPropertyStore
    {
        [PreserveSig] int GetCount(out uint cProps);
        [PreserveSig] int GetAt(uint iProp, out PROPERTYKEY pkey);
        [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
        [PreserveSig] int Commit();
    }

    [DllImport("ole32.dll")]
    static extern int PropVariantClear(ref PROPVARIANT pvar);

    public static int Register(string lnk, string target, string workdir, string aumid, string icon)
    {
        IShellLinkW link = (IShellLinkW)new ShellLink();
        link.SetPath(target);
        link.SetWorkingDirectory(workdir);
        link.SetArguments("");
        if (!string.IsNullOrEmpty(icon))
            link.SetIconLocation(icon, 0);

        IPropertyStore ps = (IPropertyStore)link;
        PROPERTYKEY key = new PROPERTYKEY();
        key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
        key.pid = 5; // System.AppUserModel.ID 的正确 PropID 是 5
        PROPVARIANT pv = new PROPVARIANT();
        pv.vt = 31;
        pv.pwszVal = Marshal.StringToCoTaskMemUni(aumid);
        int hrs = ps.SetValue(ref key, ref pv);
        int hrc = ps.Commit();
        Marshal.FreeCoTaskMem(pv.pwszVal);

        IPersistFile pf = (IPersistFile)link;
        pf.Save(lnk, true);

        Marshal.ReleaseComObject(pf);
        Marshal.ReleaseComObject(ps);
        Marshal.ReleaseComObject(link);
        if (hrs != 0) return hrs;
        if (hrc != 0) return hrc;
        return 0;
    }
}
"""


def _shortcut_path():
    base = os.environ.get("APPDATA", "")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", _APP_NAME + ".lnk")


def _launch_target():
    # 打包后指向 exe；源码运行指向 python 解释器
    return sys.executable


def _esc_ps(s):
    return "'" + str(s).replace("'", "''") + "'"


def _app_icon_path():
    """返回应用图标(ico)绝对路径，用于快捷方式图标；找不到则返回空串。"""
    try:
        from icon_manager import get_effective_icon_path
        p = get_effective_icon_path()
        if p and os.path.exists(p):
            return p.replace("/", "\\")
    except Exception:
        pass
    tries = []
    if getattr(sys, "frozen", False):
        _exe = os.path.dirname(sys.executable)
        tries = [os.path.join(_exe, "logo.ico"),
                 os.path.join(_exe, "_internal", "logo.ico")]
    else:
        tries = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")]
    for _t in tries:
        if os.path.exists(_t):
            return _t.replace("/", "\\")
    return ""


def _register(lnk_path, target):
    ps = r"""
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
__C_SHARP__
"@
$hr = [ShortcutRegistrar]::Register(__LNK__, __TARGET__, __WORKDIR__, __AUMID__, __ICON__)
if ($hr -ne 0) { Write-Output ("FAIL:" + $hr) } else { Write-Output "OK" }
"""
    ps = ps.replace("__C_SHARP__", _C_SHARP)
    ps = ps.replace("__LNK__", _esc_ps(lnk_path))
    ps = ps.replace("__TARGET__", _esc_ps(target))
    ps = ps.replace("__WORKDIR__", _esc_ps(os.path.dirname(target)))
    ps = ps.replace("__AUMID__", _esc_ps(APP_AUMID))
    ps = ps.replace("__ICON__", _esc_ps(_app_icon_path()))
    try:
        fd, path = tempfile.mkstemp(suffix=".ps1")
        with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
            f.write(ps)
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            startupinfo=subprocess.STARTUPINFO() if sys.platform == "win32" else None,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.stdout:
            out = proc.stdout.read().decode("utf-8", "replace").strip()
        else:
            out = ""
        proc.wait(timeout=30)
        proc.stdout.close()
        return out == "OK"
    except Exception:
        return False
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def register_app_identity():
    """在注册表注册 AUMID 的显示名，让通知中心的来源名显示为应用名而不是"新通知"。
    免安装桌面应用在 HKCU\\Software\\Classes\\AppUserModelID\\<AUMID> 下写 DisplayName 即可生效。"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg
        sub = r"Software\Classes\AppUserModelID\%s" % APP_AUMID
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, sub, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, _APP_NAME)
            winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 0)
        try:
            target = _launch_target()
            if target and os.path.exists(target):
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0,
                                    winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ,
                                      target.replace("/", "\\"))
        except Exception:
            pass
        return True
    except Exception:
        return False


def register_aumid_shortcut():
    """确保开始菜单里存在带 AUMID 的快捷方式（通知按钮显示的前提）。
    每次启动都重新写入，避免旧快捷方式缺少 AUMID 导致按钮不显示。"""
    if not sys.platform.startswith("win"):
        return False
    register_app_identity()
    lnk_path = _shortcut_path()
    target = _launch_target()
    return _register(lnk_path, target)


def register_aumid_shortcut_async():
    """在后台线程注册 AUMID，避免阻塞主线程启动。"""
    if not sys.platform.startswith("win"):
        return
    t = threading.Thread(target=register_aumid_shortcut, daemon=True)
    t.start()


def get_aumid():
    return APP_AUMID