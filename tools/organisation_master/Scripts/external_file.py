"""Open a document without passing the frozen app's private DLL search path to its editor."""
import ctypes
import os
import sys
import threading

_launch_lock = threading.Lock()


def open_file(path):
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return os.startfile(str(path))
    # PyInstaller's SetDllDirectory setting is inherited by programs opened through
    # ShellExecute. A long-lived image editor must use its own installed libraries.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    get_directory = kernel.GetDllDirectoryW
    get_directory.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    get_directory.restype = ctypes.c_uint32
    set_directory = kernel.SetDllDirectoryW
    set_directory.argtypes = [ctypes.c_wchar_p]
    set_directory.restype = ctypes.c_int
    with _launch_lock:
        buffer = ctypes.create_unicode_buffer(32768)
        get_directory(len(buffer), buffer)
        previous = buffer.value
        old_path = os.environ.get('PATH')
        bundle = os.path.normcase(os.path.abspath(getattr(sys, '_MEIPASS', '')))
        def bundled(entry):
            candidate = os.path.normcase(os.path.abspath(entry.strip('"')))
            return candidate == bundle or candidate.startswith(bundle + os.sep)
        if not set_directory(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if old_path is not None:
                os.environ['PATH'] = os.pathsep.join(entry for entry in old_path.split(os.pathsep) if not bundled(entry))
            return os.startfile(str(path))
        finally:
            if old_path is not None:
                os.environ['PATH'] = old_path
            set_directory(previous or None)
