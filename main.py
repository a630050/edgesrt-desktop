"""
Application entry point.

This build uses Edge as the primary UI. The local Python process only hosts
the helper API, switches Windows audio input devices, and launches Edge.
"""

import os
import sys
import time
import ctypes
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

APPDATA_BASE = os.path.join(
    os.environ.get(
        "LOCALAPPDATA",
        os.path.join(os.path.expanduser("~"), "AppData", "Local"),
    ),
    "EdgeSRT",
)
LOG_DIR = os.path.join(APPDATA_BASE, "logs")

try:
    os.makedirs(LOG_DIR, exist_ok=True)
except PermissionError:
    APPDATA_BASE = os.path.join(os.path.expanduser("~"), "EdgeSRT", "_appdata")
    LOG_DIR = os.path.join(APPDATA_BASE, "logs")
    os.makedirs(LOG_DIR, exist_ok=True)

os.environ["EDGESRT_APPDATA_DIR"] = APPDATA_BASE

log_file = os.path.join(LOG_DIR, f"app_{datetime.now():%Y%m%d}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=3 * 1024 * 1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("AppMain")

from capture_server import CaptureServer


EDGE_LAUNCH_TIMEOUT_SEC = 20


def _show_error(message: str):
    """--windowed 模式沒有主控台可看，至少用原生訊息框讓使用者看到錯誤。"""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "EdgeSRT-Desktop", 0x10)  # MB_ICONERROR
    except Exception:
        logger.exception("無法顯示錯誤訊息框")


EDGE_DEAD_STREAK_THRESHOLD = 2  # 連續幾次輪詢都偵測不到才真的判定視窗已關閉，避免單次查詢抖動誤判
EDGE_POLL_INTERVAL_SEC = 2


def _wait_for_edge(server: CaptureServer):
    # 兩個訊號分開追蹤：
    # - saw_edge：曾經觀察到 Edge 行程存活（用 server.is_edge_alive() 查系統
    #   實際行程狀態，而非只信任 Popen 追蹤到的單一 PID——Chromium 的單一實例
    #   接管機制下，該行程有可能瞬間結束、把視窗交棒給既有的行程），只用來
    #   判斷使用者關閉視窗後要不要跟著結束背景服務。連續 N 次都偵測不到才算數，
    #   避免系統忙碌造成單次查詢逾時/抖動就誤判視窗已關閉。
    # - launch_confirmed：只要曾經偵測到 Edge 存活，或首頁曾經被成功要求過，
    #   就代表啟動其實成功，之後永遠不再判定為「啟動逾時」。
    saw_edge = False
    launch_confirmed = False
    dead_streak = 0
    waited = 0
    while server.running:
        edge_alive = server.is_edge_alive()
        if edge_alive:
            saw_edge = True
            dead_streak = 0
        else:
            dead_streak += 1
        if edge_alive or server.page_loaded:
            launch_confirmed = True

        if saw_edge and dead_streak >= EDGE_DEAD_STREAK_THRESHOLD:
            logger.info("Edge window closed; stopping local helper.")
            break
        elif not launch_confirmed and waited >= EDGE_LAUNCH_TIMEOUT_SEC:
            logger.error(f"等待 {EDGE_LAUNCH_TIMEOUT_SEC} 秒後仍未偵測到 Edge 視窗，可能找不到 Microsoft Edge，程式即將結束。")
            _show_error("找不到 Microsoft Edge，或 Edge 未能成功啟動。\n請確認已安裝 Microsoft Edge 後再試一次。")
            break
        time.sleep(EDGE_POLL_INTERVAL_SEC)
        waited += EDGE_POLL_INTERVAL_SEC


def main():
    logger.info("=== Starting EdgeSRT browser-main helper ===")

    server = CaptureServer(
        on_status_change=lambda msg: logger.info(msg),
        on_interim_text=lambda text: None,
        on_final_text=lambda text: None,
        on_volume=lambda volume: None,
    )

    try:
        server.start(hidden_edge=False, restart_on_disconnect=False)
        _wait_for_edge(server)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception:
        logger.exception("Fatal error in EdgeSRT helper.")
    finally:
        server.stop()
        logger.info("=== EdgeSRT helper stopped ===")


if __name__ == "__main__":
    main()
