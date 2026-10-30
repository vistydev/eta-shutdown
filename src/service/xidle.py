#!/usr/bin/env python3
# https://github.com/g0hl1n/xprintidle/blob/master/xprintidle.c
import ctypes
class XScreenSaverInfo( ctypes.Structure ):
    _fields_ = [("window",     ctypes.c_ulong),
                ("state",      ctypes.c_int),
                ("kind",       ctypes.c_int),
                ("since",      ctypes.c_ulong),
                ("idle",       ctypes.c_ulong),
                ("event_mask", ctypes.c_ulong)]

def get_idle_time(display=None):
    xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
    xss = ctypes.cdll.LoadLibrary("libXss.so.1")
    if xss is None or xlib is None:
        return 0
    # Without these ctypes uses int for the return values, which cuts the
    # 64 bit Display pointer and crashes or fails to open the display
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xlib.XFree.argtypes = [ctypes.c_void_p]
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
    xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                          ctypes.POINTER(XScreenSaverInfo)]
    display = xlib.XOpenDisplay(bytes(display, 'ascii'))
    if not display:
        return None
    xssinfo = xss.XScreenSaverAllocInfo()
    window = xlib.XDefaultRootWindow(display)
    if not xssinfo or not window:
        xlib.XCloseDisplay(display)
        return None
    status = xss.XScreenSaverQueryInfo(display, window, xssinfo)
    idle = xssinfo.contents.idle
    xlib.XFree(xssinfo)
    xlib.XCloseDisplay(display)
    if not status:
        return None

    return idle

if __name__ == "__main__":
    import os
    import sys
    # used by the service: print the idle time of one display
    if len(sys.argv) > 1:
        idle = get_idle_time(sys.argv[1])
        if idle is None:
            sys.exit(1)
        print(idle)
        sys.exit(0)
    idle_time = -1
    for display in os.listdir("/tmp/.X11-unix/"):
        idle = get_idle_time(f":{display[1:]}")
        if idle is None:
            continue
        if idle_time < 0 or idle < idle_time:
            idle_time = idle
    print("idle_time: {}".format(idle_time))
