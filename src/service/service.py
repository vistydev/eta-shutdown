import os
import sys
import time
import subprocess
import threading
import configparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

from logger import log

"""
[AUTO_SHUTDOWN]
enabled = False
hour = 01
minute = 00

[TIMED_MODE]
mode = "shutdown"
hour = 00
minute = 00
"""

CONFIG_FILE = "/etc/pardus/eta-shutdown.conf"
XIDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xidle.py")
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

def check_time(hour, minute, delay):
    now = datetime.now()
    nex = datetime(now.year, now.month, now.day, hour, minute)
    print(now, nex, delay)
    return nex.timestamp() - delay - now.timestamp() < 0


def check_x11(disp):
    # /tmp/.X11-unix is world writable, a display that never answers
    # must not block the service
    try:
        sp = subprocess.run(["env", "DISPLAY={}".format(disp), "xset", "-q"],
                            capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return sp.returncode == 0


def get_display_idle(disp):
    # Same reason, ask in a child process with a timeout
    try:
        sp = subprocess.run([sys.executable, XIDLE, disp],
                            capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        return None
    if sp.returncode != 0:
        return None
    try:
        return int(sp.stdout.decode().strip())
    except ValueError:
        return None

ret = None
def send_notify(message, yes_msg, no_msg, timeout):
    global ret
    def send_notify_disp(disp):
        global ret
        cmd = ["timeout", str(timeout),
            "env", "DISPLAY={}".format(disp),
            "notify-send", "-w",
            "-A", "true={}".format(yes_msg),
            "-A", "false={}".format(no_msg),
            "-t", str(timeout*1000), message]
        log(cmd)
        sp = subprocess.run(cmd, capture_output=True)
        if ret == None:
            ret = (sp.stdout.decode("utf-8").strip() == "true")
    ths = []
    ret = None
    for display in os.listdir("/tmp/.X11-unix/"):
        if check_x11(f":{display[1:]}"):
            th = threading.Thread(target=send_notify_disp, args=[f":{display[1:]}"])
            ths.append(th)
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    print(ret)
    return ret

message_shown = False
delay = 0
init=False
ignore_auto=False

def service():
    global message_shown
    global delay
    global init
    global ignore_auto

    # variables
    auto_hour = int(config["AUTO_SHUTDOWN"]["hour"])
    auto_minute = int(config["AUTO_SHUTDOWN"]["minute"])
    hour = int(config["TIMED_MODE"]["hour"])
    minute = int(config["TIMED_MODE"]["minute"])
    # first boot check
    if not init:
        init = True
        if check_time(auto_hour, auto_minute, 0):
            ignore_auto = True

    log("###### Eta Shutdown {} ######".format(time.time()))
    # timed shutdown
    mode = config["TIMED_MODE"]["mode"]
    if mode != "none":
        # The machine is idle only if every display is idle, so use the
        # smallest idle time. With the largest one an idle second session
        # (or any display a user starts) powered off the active one.
        idle_time = -1
        for display in os.listdir("/tmp/.X11-unix/"):
            idle = get_display_idle(f":{display[1:]}")
            if idle is None:
                continue
            if idle_time < 0 or idle < idle_time:
                idle_time = idle
        print("idle_time: {}".format(idle_time))
        req_idle = (hour*3600 + minute * 60)*1000
        if req_idle < 5*60*1000:
            req_idle = 5*60*1000
        print("req_idle:", req_idle)
        if idle_time > req_idle:
            if mode == "shutdown":
                os.system("poweroff -f")
            elif mode == "suspend":
                os.system("systemctl suspend")
    # auto shutdown
    if ignore_auto:
        print("Ignore auto shutdown")
    elif config["AUTO_SHUTDOWN"]["enabled"].lower() == "true":
        if check_time(auto_hour, auto_minute, (600)):
            if not message_shown:
                message_shown = True
                if send_notify("Sistem 10dk sonra kapatılacak.", "1 saat ertele", "Tamam", 30):
                    delay -= 60*60
                    message_shown = False
        if check_time(auto_hour, auto_minute, delay):
            print("auto shutdown")
            os.system("poweroff -f")

if __name__ == "__main__":
    send_notify(sys.argv[1], "Yes", "No", 10)
