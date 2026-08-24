"""
主程式入口 (Application Entry Point)
啟動 Edge 即時語音轉錄桌面應用
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# 強制 UTF-8 編碼
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

ICON_PATH = os.path.join(BUNDLE_DIR, "ui", "assets", "app_icon.ico")

_appdata_base = os.path.join(APP_DIR, "_appdata")
LOG_DIR = os.path.join(_appdata_base, "logs")

try:
    os.makedirs(LOG_DIR, exist_ok=True)
except PermissionError:
    # 針對放置於 C:\Program Files 等唯讀目錄的應對方案
    _appdata_base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "EdgeSRT", "_appdata")
    LOG_DIR = os.path.join(_appdata_base, "logs")
    os.makedirs(LOG_DIR, exist_ok=True)
    
# 將實際使用的 _appdata_base 寫入環境變數供其他模組讀取
os.environ["EDGESRT_APPDATA_DIR"] = _appdata_base

# 日誌初始化
log_file = os.path.join(LOG_DIR, f"app_{datetime.now():%Y%m%d}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=3*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AppMain")

from ui.main_window import MainWindow


def main():
    logger.info("=== 啟動 Edge 即時語音轉錄桌面工具 ===")
    
    # 啟用高 DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("EdgeLiveCaptions")
    app.setOrganizationName("EdgeLiveCaptions")
    if os.path.isfile(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    logger.info("=== 程式正常結束 ===")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
