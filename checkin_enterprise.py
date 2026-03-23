# checkin_enterprise.py
# Enterprise Android Automation via ADB

import subprocess
import time
import xml.etree.ElementTree as ET
import re
import os
import datetime
import logging
import sys
from logging.handlers import RotatingFileHandler

ADB = "adb"
PACKAGE = "com.hrisproject"
    
# button check in text
CHECK_IN_TEXT = "CHECK IN"

# button check out text
CHECK_OUT_TEXT = "CHECK OUT"

# button check out confirm text
CHECK_OUT_CONFIRM_TEXT = "Đồng ý"

# menu text to open check in page
TEST_MENU_TEXT = "Tạo đơn"

RETRY_MAX = 3
ELEMENT_TIMEOUT = 30

SCREENSHOT_PHONE = "/sdcard/checkin.jpg"
SCREENSHOT_PC = "checkin.jpg"

TELEGRAM_BOT = "7852978460:AAEPDG4rW3RJM9B-uuGc1KzwGmw5FtlIT04"
TELEGRAM_CHAT = "-4868727178"

PIN_CODE = "0000"  # Ganti dengan PIN yang sesuai

APP_READY_TIMEOUT = 60

# ===== LOG ROTATE =====
logger = logging.getLogger("automation")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    "automation.log",
    maxBytes=1024*1024,
    backupCount=5,
    encoding="utf-8"
)
formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def log(msg):
    print(msg)
    logger.info(msg)

def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Force decode UTF-8, ignore invalid byte
        stdout = result.stdout.decode("utf-8", errors="ignore")
        return stdout.strip()

    except Exception as e:
        log("run_cmd error: " + str(e))
        return ""


# ================= NETWORK =================

def check_Samsung_network():
    
    log("Checking network...")
    
    
    
    result = subprocess.run("ping 8.8.8.8 -n 1", shell=True)
    return result.returncode == 0


# ================= ADB =================

def adb_connected():
    output = run_cmd("adb devices")
    lines = output.splitlines()
    for line in lines:
        if "\tdevice" in line:
            return True
    return False


def reconnect_adb():
    log("Reconnecting ADB...")
    run_cmd("adb kill-server")
    time.sleep(2)
    run_cmd("adb start-server")
    time.sleep(3)


def ensure_adb():
    if not adb_connected():
        log("ADB not connected. Reconnecting...")
        reconnect_adb()
        if not adb_connected():
            log("ADB reconnect failed.")
            return False
    return True


# ================= DEVICE CONTROL =================

def press(keycode):
    run_cmd(ADB + " shell input keyevent " + str(keycode))


def tap(x, y):
    log("Tapping at (" + str(x) + ", " + str(y) + ")")
    run_cmd(ADB + " shell input tap " + str(x) + " " + str(y))


def swipe_up():
    run_cmd(ADB + " shell input swipe 500 1600 500 300 750")

def check_is_sceren_on():
    output = run_cmd(ADB + " shell dumpsys power | findstr \"Display Power\" | findstr \"state=\"")
    return "ON" in output


def check_is_screen_off():
    output = run_cmd(ADB + " shell dumpsys power | findstr \"Display Power\" | findstr \"state=\"")
    return "OFF" in output

################ WIFI  #################

def samsung_is_connected_to_internet():
    output = run_cmd(ADB + " shell ping -c 1 8.8.8.8")
    return "1 packets transmitted, 1 received" in output

def samsung_disable_and_reenable_wifi():
    output = run_cmd(ADB + " shell svc wifi disable")
    log("WiFi disabled")
    time.sleep(5)
    output = run_cmd(ADB + " shell svc wifi enable")
    log("WiFi enabled")
    time.sleep(5)
    log("WiFi toggled off and on")    
    
################ SCREEN CONTROL ################
    
def turnon_screen():
    if check_is_sceren_on():
        log("Screen is already on")
        return
    log("Turning on screen")
    press(26)
    time.sleep(1)
    
    
def turnoff_screen():
    if check_is_screen_off():
        log("Screen is already off")
        return
    log("Turning off screen")
    press(26)
    time.sleep(1)

def unlock():
    log("turn on screen and swipe up to unlock")
    turnon_screen()
    time.sleep(1)
    swipe_up()
    time.sleep(2)

def unlock_with_pin(pin):
    log("turn on screen and swipe up to unlock with PIN")
    turnon_screen()
    #time.sleep(1)
    swipe_up()

    for digit in pin:
        keycode = 7 + int(digit)  # KeyEvent for digits starts at 7
        press(keycode)

    press(66)  # Press Enter

def lock():
    log("Lock device")
    press(26)

def check_is_app_running():
    output = run_cmd(ADB + " shell pidof " + PACKAGE)
    return output != ""

def stop_app():
    log("Stop app")
    run_cmd(ADB + " shell am force-stop " + PACKAGE)

def start_app():
    if check_is_app_running():
        log("App is running, stopping first")
        stop_app()
    log("Start app")
    run_cmd(ADB + " shell monkey -p " + PACKAGE + " -c android.intent.category.LAUNCHER 1")
    time.sleep(8)

# ================= UI =================

def dump_ui():
    run_cmd(ADB + " shell uiautomator dump /sdcard/ui.xml")
    run_cmd(ADB + " pull /sdcard/ui.xml ui.xml")


def parse_bounds(bounds):
    nums = re.findall(r'\d+', bounds)
    x1, y1, x2, y2 = map(int, nums)
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def wait_and_click(text, timeout=ELEMENT_TIMEOUT):
    log("Waiting element: " + text)
    start_time = time.time()

    while time.time() - start_time < timeout:
        dump_ui()
        tree = ET.parse("ui.xml")
        root = tree.getroot()

        for node in root.iter("node"):
            node_text = node.attrib.get("text", "")
            if text.strip().lower() == node_text.strip().lower():
                bounds = node.attrib.get("bounds")
                x, y = parse_bounds(bounds)
                log("Element found: " + text)
                tap(x, y)
                return True

        time.sleep(2)

    log("Element timeout: " + text)
    return False

def close_overlay_if_any():
    log("Checking overlay popup...")

    dump_ui()
    tree = ET.parse("ui.xml")
    root = tree.getroot()

    for node in root.iter("node"):
        node_text = node.attrib.get("text", "")
        if "Đóng" in node_text:
            bounds = node.attrib.get("bounds")
            x, y = parse_bounds(bounds)
            log("Overlay found. Closing...")
            tap(x, y)
            time.sleep(2)
            return True

    log("No overlay detected")
    return False

# check is app load ready by checking if "Trang chủ" button appear, if appear then close it and return true, otherwise return false
def wait_app_ready():
    log("Checking if app is ready...")
    if wait_and_click("Trang chủ", timeout=APP_READY_TIMEOUT):
        log("App is ready")
        return True
    else:
        log("App is not ready")
        return False
    

# ================= TELEGRAM =================

def send_telegram_message(text):
    cmd = (
        "curl -X POST https://api.telegram.org/bot" + TELEGRAM_BOT +
        "/sendMessage -d chat_id=" + TELEGRAM_CHAT +
        " -d text=\"" + text + "\""
    )
    run_cmd(cmd)


def send_telegram_photo():
    cmd = (
        "curl -F chat_id=" + TELEGRAM_CHAT +
        " -F photo=@" + SCREENSHOT_PC +
        " https://api.telegram.org/bot" + TELEGRAM_BOT + "/sendPhoto"
    )
    run_cmd(cmd)


# ================= SCREENSHOT =================

def screenshot():
    run_cmd(ADB + " shell screencap -p " + SCREENSHOT_PHONE)
    run_cmd(ADB + " pull " + SCREENSHOT_PHONE + " " + SCREENSHOT_PC)


# ================= MAIN =================

def main_flow(mode):
    # Ensure ADB connection
    if not ensure_adb():
        return False

    # unlock device
    unlock_with_pin(PIN_CODE)
    
    # Check network and toggle WiFi if not connected
    if samsung_is_connected_to_internet(): 
        log("Device is connected to internet")
    else:
        log("Device is NOT connected to internet, toggling WiFi")
        samsung_disable_and_reenable_wifi()
        if not samsung_is_connected_to_internet():
            log("Failed to connect to internet after toggling WiFi")
            return False

    start_app()

    # Close overlay popup if exists
    close_overlay_if_any()

    if mode == "CHECK_IN":

        if not wait_and_click(CHECK_IN_TEXT):
            return False

    elif mode == "CHECK_OUT":

        if not wait_and_click(CHECK_OUT_TEXT):
            return False

        time.sleep(3)

        if not wait_and_click(CHECK_OUT_CONFIRM_TEXT, timeout=15):
            log("Confirm popup not found")
            return False
        
        time.sleep(3)
        
        tap(635 , 201) # click icon close button popup

    elif mode == "TEST":

        log("TEST mode: clicking ""Tạo đơn""")

        if not wait_and_click(TEST_MENU_TEXT, timeout=20):
            log("Menu ""Tạo đơn"" not found")
            return False

    else:
        log("Invalid mode")
        return False

    time.sleep(5)   
        
    if close_overlay_if_any():
        time.sleep(1)
    
    screenshot()
    send_telegram_photo()

    stop_app()
    lock()

    return True


def main():
    print("working directory: " + os.getcwd())  # debug
    
    if len(sys.argv) < 2:
        print("Usage: python3 checkin_enterprise.py CHECK_IN|CHECK_OUT|TEST")
        return

    mode = sys.argv[1].upper()

    log("=== START MODE: " + mode + " ===")

    for attempt in range(RETRY_MAX):
        log("Attempt " + str(attempt + 1))

        if main_flow(mode):
            log("SUCCESS")
            return
        else:
            log("FAILED attempt")
            stop_app()
            time.sleep(3)

    log("ALL RETRIES FAILED")
    send_telegram_message("Automation FAILED mode: " + mode)

    log("=== END ===")
    
    print("Script finished")  # debug
    sys.stdout.flush()
    os._exit(0)  # force exit

if __name__ == "__main__":
    try:
        main()
    finally:
        import logging
        logging.shutdown()
        import os
        os._exit(0)