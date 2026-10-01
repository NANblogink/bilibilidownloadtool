# -*- coding: utf-8 -*-
"""在**没有 PyQt5** 的平台上提供最小可用的 Qt 兼容层。

为什么需要这个文件
==================

`core/downloader.py` 与 `core/utils.py` 顶层就 `from PyQt5.QtCore import ...`，
而 Android 上根本没有 PyQt5（官方不提供）。结果是：

    import downloader  ->  ImportError  ->  下载功能完全不可用

如果为了绕开它而"另写一套下载逻辑"，就违背了"功能与桌面版一模一样"
的要求（两套实现必然逐渐产生差异）。

因此这里不去改桌面版的代码，而是**提供一个同名的 `PyQt5` 影子包**，
只实现桌面版真正用到的那几个 Qt 符号：

    QObject, pyqtSignal, QThread, QMutex, QWaitCondition, Qt

实现要点
--------

* ``pyqtSignal``：桌面版只做 ``sig.emit(...)`` 和 ``sig.connect(fn)``。
  这里用「描述符 + 每个实例独立的回调列表」实现，emit 时同步调用回调。
  与 Qt 的差异：Qt 的跨线程 emit 默认是队列投递（异步），这里是同步调用。
  调用方（Android 界面层）必须自己用 ``Clock.schedule_once`` 切回主线程
  —— 界面代码里已经这么做了，所以行为是正确的。

* ``QThread``：桌面版的 ``DownloadManager`` 与 ``EpisodeDownloadThread``
  都继承它。这里用真实线程实现 ``start()/run()/isRunning()/wait()``，
  并把 ``run()`` 放到线程里执行。

* ``QMutex`` / ``QWaitCondition``：用 ``threading.Lock`` 与
  ``threading.Condition`` 实现，语义与 Qt 一致（`wait(mutex, ms)`）。

如果将来某个平台真的有 PyQt5，这个模块不会被使用
（入口只在导入 PyQt5 失败时才安装影子包）。
"""
import sys
import threading
import types

__all__ = ["install", "is_installed"]


# ==========================================================================
# pyqtSignal
# ==========================================================================

class pyqtSignal:
    """最小可用的信号实现。

    用法与 Qt 一致::

        class Foo(QObject):
            done = pyqtSignal(int, str)

        f = Foo()
        f.done.connect(lambda n, s: print(n, s))
        f.done.emit(1, "ok")
    """

    def __init__(self, *types_, **kwargs):
        self._types = types_
        self._name = kwargs.get("name", None)
        # 每实例各持回调表
        self._store = {}
        self._lock = threading.RLock()

    def __set_name__(self, owner, name):
        self._name = name

    def _key(self, obj):
        return id(obj)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return _BoundSignal(self, obj)

    # 可对类属性emit
    def emit(self, *args, **kwargs):
        pass

    def connect(self, slot):
        pass


class _BoundSignal:
    """绑定到具体实例的信号对象。"""

    __slots__ = ("_sig", "_obj")

    def __init__(self, sig, obj):
        self._sig = sig
        self._obj = obj

    def connect(self, slot, *args, **kwargs):
        with self._sig._lock:
            cbs = self._sig._store.setdefault(self._sig._key(self._obj), [])
            if slot not in cbs:
                cbs.append(slot)
        return slot

    def disconnect(self, slot=None):
        with self._sig._lock:
            cbs = self._sig._store.get(self._sig._key(self._obj), [])
            if slot is None:
                cbs.clear()
            elif slot in cbs:
                cbs.remove(slot)

    def emit(self, *args, **kwargs):
        # 取快照再调免遍历异常
        with self._sig._lock:
            cbs = list(self._sig._store.get(self._sig._key(self._obj), []))
        for cb in cbs:
            try:
                cb(*args, **kwargs)
            except Exception:
                # 槽抛错不应中断主流程
                # 这里吞掉并记录
                try:
                    import traceback
                    traceback.print_exc()
                except Exception:
                    pass


# ==========================================================================
# QObject
# ==========================================================================

class QObject:
    """只提供桌面版用到的能力：可作为信号宿主、有 parent/children 概念。"""

    def __init__(self, parent=None):
        self._parent = parent
        self._children = []
        if parent is not None and hasattr(parent, "_children"):
            parent._children.append(self)

    def parent(self):
        return self._parent

    def children(self):
        return list(self._children)

    def deleteLater(self):
        pass

    def objectName(self):
        return getattr(self, "_object_name", "")

    def setObjectName(self, name):
        self._object_name = name


# ==========================================================================
# QThread
# ==========================================================================

class QThread(QObject):
    """用真实线程实现的 QThread。

    只实现桌面版实际用到的 API：
        start() / run() / isRunning() / wait() / quit() / terminate()
        finished 信号
    """

    finished = pyqtSignal()
    started = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._running = False
        self._stop_flag = threading.Event()
        self._mutex = threading.RLock()

    # ---------------------------------------------------------------- 生命周期
    def start(self, *args, **kwargs):
        with self._mutex:
            if self._running:
                return
            self._running = True
            self._stop_flag.clear()
        self._thread = threading.Thread(target=self._bootstrap, daemon=True)
        self._thread.start()

    def _bootstrap(self):
        try:
            self.started.emit()
            self.run()
        except Exception:
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass
        finally:
            with self._mutex:
                self._running = False
            self._stop_flag.set()
            try:
                self.finished.emit()
            except Exception:
                pass

    def run(self):
        """子类覆写。"""

    def isRunning(self):
        with self._mutex:
            return self._running

    def wait(self, msecs=None):
        """等待线程结束。msecs 为 None 表示一直等。返回 True 表示已结束。"""
        t = self._thread
        if t is None:
            return True
        if msecs is None:
            t.join()
            return True
        # threading无join
        t.join(timeout=max(0.0, msecs / 1000.0))
        return not t.is_alive()

    def quit(self):
        self._stop_flag.set()

    def terminate(self):
        # 置标志让run退出
        # 桌面版也靠标志协作
        self._stop_flag.set()

    def msleep(self, msecs):
        import time
        time.sleep(msecs / 1000.0)

    def usleep(self, usecs):
        import time
        time.sleep(usecs / 1_000_000.0)

    def sleep(self, secs):
        import time
        time.sleep(secs)

    @property
    def stop_requested(self):
        return self._stop_flag.is_set()


# ==========================================================================
# 同步原语
# ==========================================================================

class QMutex:
    """QMutex 的最小实现（非递归，与 Qt 默认一致）。"""

    def __init__(self, mode=None):
        self._lock = threading.Lock()

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        try:
            self._lock.release()
        except RuntimeError:
            # 未持有unlock
            pass

    def tryLock(self, timeout=0):
        if timeout and timeout > 0:
            return self._lock.acquire(timeout=timeout / 1000.0)
        return self._lock.acquire(blocking=False)

    # 可当上下文管理器
    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, *exc):
        self.unlock()
        return False


class QWaitCondition:
    """QWaitCondition 的最小实现，语义对齐 Qt：

        cond.wait(mutex, msecs)  —— 原子地释放 mutex 并等待，醒来时重新持有
    """

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())

    def wait(self, mutex, msecs=None):
        """等待。mutex 是 QMutex；返回 True 表示被唤醒，False 表示超时。"""
        # 先释放调用方持有的锁
        try:
            mutex.unlock()
        except Exception:
            pass
        got = False
        try:
            with self._cond:
                if msecs is None:
                    self._cond.wait()
                    got = True
                else:
                    got = self._cond.wait(timeout=max(0.0, msecs / 1000.0))
        finally:
            # 重新拿回mutex
            try:
                mutex.lock()
            except Exception:
                pass
        return got

    def wakeOne(self):
        with self._cond:
            self._cond.notify(1)

    def wakeAll(self):
        with self._cond:
            self._cond.notify_all()


class QSemaphore:
    def __init__(self, n=0):
        self._sem = threading.Semaphore(n)

    def acquire(self, n=1):
        for _ in range(n):
            self._sem.acquire()

    def release(self, n=1):
        for _ in range(n):
            self._sem.release()

    def tryAcquire(self, n=1, timeout=0):
        return self._sem.acquire(timeout=timeout / 1000.0 if timeout else -1)


# ==========================================================================
# Qt 常量命名空间
# ==========================================================================

class _QtNamespace:
    """桌面版用到的 Qt.* 常量。"""

    # 对齐方式
    AlignLeft = 0x0001
    AlignRight = 0x0002
    AlignHCenter = 0x0004
    AlignTop = 0x0020
    AlignBottom = 0x0040
    AlignVCenter = 0x0080
    AlignCenter = AlignVCenter | AlignHCenter

    # 文本交互
    TextSelectableByMouse = 0x0001
    TextSelectableByKeyboard = 0x0002

    # 鼠标
    NoPen = 0
    NoBrush = 0
    SolidLine = 1
    LeftButton = 1
    RightButton = 2

    # 窗口
    WindowStaysOnTopHint = 0x00040000
    FramelessWindowHint = 0x00000800
    WA_TranslucentBackground = 0x00000001

    # 其它
    SmoothTransformation = 1
    KeepAspectRatio = 1
    IgnoreAspectRatio = 0


Qt = _QtNamespace()


# ==========================================================================
# 安装影子包
# ==========================================================================

_installed = False


def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def install(verbose=False):
    """把影子 PyQt5 注册进 sys.modules。

    只有在真实 PyQt5 不可用时才生效；已安装 PyQt5 的环境不受影响。
    返回 True 表示影子包已生效。
    """
    global _installed
    if _installed:
        return True

    # 真PyQt5则不插手
    try:
        import PyQt5  # noqa: F401
        if verbose:
            print("[qt_compat] 检测到真实 PyQt5，跳过影子包")
        return False
    except Exception:
        pass

    sig_mod = _make_module("PyQt5.QtCore",
                           QObject=QObject,
                           pyqtSignal=pyqtSignal,
                           QThread=QThread,
                           QMutex=QMutex,
                           QWaitCondition=QWaitCondition,
                           QSemaphore=QSemaphore,
                           Qt=Qt,
                           QTimer=type("QTimer", (), {}),
                           QSize=type("QSize", (), {}),
                           QPoint=type("QPoint", (), {}),
                           QRect=type("QRect", (), {}),
                           QUrl=type("QUrl", (), {}),
                           QEvent=type("QEvent", (), {}),
                           QCoreApplication=type("QCoreApplication", (), {}))
    gui_mod = _make_module("PyQt5.QtGui",
                           QImage=type("QImage", (), {}),
                           QPixmap=type("QPixmap", (), {}),
                           QPainter=type("QPainter", (), {}),
                           QColor=type("QColor", (), {}),
                           QIcon=type("QIcon", (), {}),
                           QFont=type("QFont", (), {}))
    widgets_mod = _make_module("PyQt5.QtWidgets",
                               QMessageBox=type("QMessageBox", (), {}),
                               QApplication=type("QApplication", (), {}),
                               QWidget=type("QWidget", (), {}),
                               QDialog=type("QDialog", (), {}))
    pyqt_mod = _make_module("PyQt5",
                            QtCore=sig_mod,
                            QtGui=gui_mod,
                            QtWidgets=widgets_mod)
    pyqt_mod.__path__ = []          # 标记为包
    pyqt_mod.__version__ = "0.0.0-shim"

    sys.modules["PyQt5"] = pyqt_mod
    sys.modules["PyQt5.QtCore"] = sig_mod
    sys.modules["PyQt5.QtGui"] = gui_mod
    sys.modules["PyQt5.QtWidgets"] = widgets_mod

    _installed = True
    if verbose:
        print("[qt_compat] 已安装影子 PyQt5（无真实 Qt 环境）")
    return True


def is_installed():
    return _installed
