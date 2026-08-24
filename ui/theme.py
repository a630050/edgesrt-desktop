"""
主題配色與樣式表模組 (Themes)
提供 6 組精簡命名主題：夜晚 (預設)、白天、羊皮、深海、森林、禪風
"""

import os
import sys
from typing import Dict

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = os.path.join(sys._MEIPASS, "ui")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CHECK_ICON_PATH = os.path.join(ASSETS_DIR, "check_white.png").replace("\\", "/")

THEMES: Dict[str, Dict[str, str]] = {
    # 🌙 夜晚 (預設)
    "night": {
        "name": "夜晚",
        "bg_primary": "#0b0e14",
        "bg_secondary": "#111111",
        "bg_editor": "#000000",
        "text_primary": "#e8edf5",
        "text_editor": "#ffd700",  # 高對比金黃色
        "text_interim": "#4f8ff7",  # 即時辨識字亮藍色
        "accent": "#4f8ff7",
        "accent_active": "#22c55e",
        "border": "#232830",
        "toolbar_bg": "#111111",
        "btn_bg": "#1a1a1a",
        "btn_hover": "#252b36",
        "btn_active": "#16a34a",
        "btn_active_text": "#ffffff",
        "chk_border": "#4b5563",
        "chk_bg": "#111111",
        "chk_hover_border": "#4f8ff7",
        "chk_checked_bg": "#16a34a",
        "chk_checked_border": "#22c55e",
    },
    # ☀️ 白天
    "day": {
        "name": "白天",
        "bg_primary": "#f0f2f5",
        "bg_secondary": "#e4e7ec",
        "bg_editor": "#ffffff",
        "text_primary": "#1a1d23",
        "text_editor": "#1a1d23",
        "text_interim": "#4f8ff7",
        "accent": "#4f8ff7",
        "accent_active": "#16a34a",
        "border": "#d5dae1",
        "toolbar_bg": "#e4e7ec",
        "btn_bg": "#ffffff",
        "btn_hover": "#d5dae1",
        "btn_active": "#16a34a",
        "btn_active_text": "#ffffff",
        "chk_border": "#94a3b8",
        "chk_bg": "#ffffff",
        "chk_hover_border": "#4f8ff7",
        "chk_checked_bg": "#16a34a",
        "chk_checked_border": "#15803d",
    },
    # 📜 羊皮
    "parchment": {
        "name": "羊皮",
        "bg_primary": "#f3e9d2",
        "bg_secondary": "#faf3e2",
        "bg_editor": "#f3e9d2",
        "text_primary": "#4a3826",
        "text_editor": "#4a3826",
        "text_interim": "#a97c3f",
        "accent": "#a97c3f",
        "accent_active": "#387a38",
        "border": "#d8c5a0",
        "toolbar_bg": "#faf3e2",
        "btn_bg": "#efe2c4",
        "btn_hover": "#e2d2ae",
        "btn_active": "#387a38",
        "btn_active_text": "#ffffff",
        "chk_border": "#a89778",
        "chk_bg": "#efe2c4",
        "chk_hover_border": "#a97c3f",
        "chk_checked_bg": "#387a38",
        "chk_checked_border": "#2d622d",
    },
    # 🌊 深海
    "ocean": {
        "name": "深海",
        "bg_primary": "#0d1b2a",
        "bg_secondary": "#16283b",
        "bg_editor": "#0d1b2a",
        "text_primary": "#dce8f0",
        "text_editor": "#dce8f0",
        "text_interim": "#4f9dc9",
        "accent": "#4f9dc9",
        "accent_active": "#06d6a0",
        "border": "#2c4a63",
        "toolbar_bg": "#16283b",
        "btn_bg": "#1d3348",
        "btn_hover": "#24405c",
        "btn_active": "#06d6a0",
        "btn_active_text": "#0d1b2a",
        "chk_border": "#4f9dc9",
        "chk_bg": "#1d3348",
        "chk_hover_border": "#6fbf9b",
        "chk_checked_bg": "#06d6a0",
        "chk_checked_border": "#06d6a0",
    },
    # 🌿 森林
    "forest": {
        "name": "森林",
        "bg_primary": "#eef2ea",
        "bg_secondary": "#f7faf5",
        "bg_editor": "#eef2ea",
        "text_primary": "#33422f",
        "text_editor": "#33422f",
        "text_interim": "#5f8c5a",
        "accent": "#5f8c5a",
        "accent_active": "#3d6e38",
        "border": "#c7d6bd",
        "toolbar_bg": "#f7faf5",
        "btn_bg": "#e4ecdf",
        "btn_hover": "#d2e0cc",
        "btn_active": "#3d6e38",
        "btn_active_text": "#ffffff",
        "chk_border": "#8aab6f",
        "chk_bg": "#e4ecdf",
        "chk_hover_border": "#5f8c5a",
        "chk_checked_bg": "#3d6e38",
        "chk_checked_border": "#2a4c26",
    },
    # 🍵 禪風
    "wa": {
        "name": "禪風",
        "bg_primary": "#f1ece3",
        "bg_secondary": "#f8f4ec",
        "bg_editor": "#f1ece3",
        "text_primary": "#3c332a",
        "text_editor": "#3c332a",
        "text_interim": "#9c6b53",
        "accent": "#9c6b53",
        "accent_active": "#5a7a6f",
        "border": "#cdbfa8",
        "toolbar_bg": "#f8f4ec",
        "btn_bg": "#e9e1d2",
        "btn_hover": "#dbd0bd",
        "btn_active": "#5a7a6f",
        "btn_active_text": "#ffffff",
        "chk_border": "#b5a388",
        "chk_bg": "#e9e1d2",
        "chk_hover_border": "#9c6b53",
        "chk_checked_bg": "#5a7a6f",
        "chk_checked_border": "#435d54",
    },
    # 🎨 自訂
    "custom": {
        "name": "自訂",
        "bg_primary": "#0b0e14",
        "bg_secondary": "#151e2e",
        "bg_editor": "#000000",
        "text_primary": "#e8edf5",
        "text_editor": "#ffd700",
        "text_interim": "#38bdf8",
        "accent": "#38bdf8",
        "accent_active": "#22c55e",
        "border": "#283548",
        "toolbar_bg": "#151e2e",
        "btn_bg": "#1e293b",
        "btn_hover": "#2e3f59",
        "btn_active": "#16a34a",
        "btn_active_text": "#ffffff",
        "chk_border": "#64748b",
        "chk_bg": "#1e293b",
        "chk_hover_border": "#38bdf8",
        "chk_checked_bg": "#16a34a",
        "chk_checked_border": "#22c55e",
    }
}


def get_stylesheet(theme_key: str = "night") -> str:
    """根據主題識別碼生成完整的 PyQt 樣式表"""
    t = THEMES.get(theme_key, THEMES["night"])

    return f"""
    QMainWindow, QDialog {{
        background-color: {t['bg_primary']};
        color: {t['text_primary']};
    }}
    
    QWidget {{
        color: {t['text_primary']};
        font-family: "Microsoft JhengHei UI", "微軟正黑體", "Segoe UI", sans-serif;
    }}
    
    /* 頂部音訊來源外框容器：深色背景一致 */
    QFrame#top_source_frame {{
        background-color: {t['toolbar_bg']};
        border: 1px solid {t['border']};
        border-radius: 6px;
    }}
    
    QToolBar {{
        background-color: {t['toolbar_bg']};
        border-top: 1px solid {t['border']};
        border-bottom: 1px solid {t['border']};
        spacing: 6px;
        padding: 5px 8px;
    }}
    
    QTextEdit {{
        background-color: {t['bg_editor']};
        color: {t['text_editor']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 16px;
        line-height: 1.6;
        selection-background-color: {t['accent']};
        selection-color: #ffffff;
    }}
    
    QPushButton {{
        background-color: {t['btn_bg']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 14px;
        font-weight: 500;
    }}
    
    QPushButton:hover {{
        background-color: {t['btn_hover']};
        border-color: {t['accent']};
    }}
    
    QPushButton:pressed {{
        background-color: {t['border']};
    }}
    
    /* 頂部音源快速切換按鈕樣式 */
    QPushButton.audio-source-btn {{
        background-color: {t['btn_bg']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 14px;
        font-weight: 500;
    }}
    
    QPushButton.audio-source-btn:hover {{
        border-color: {t['accent']};
    }}
    
    QPushButton.audio-source-btn-active {{
        background-color: {t['btn_active']};
        color: {t['btn_active_text']};
        border: 1px solid {t['accent_active']};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 14px;
        font-weight: bold;
    }}
    
    QComboBox, QSpinBox, QLineEdit {{
        background-color: {t['btn_bg']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 14px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {t['btn_bg']};
        color: {t['text_primary']};
        selection-background-color: {t['accent']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 4px;
    }}
    
    /* 核取方塊 (QCheckBox) */
    QCheckBox {{
        color: {t['text_primary']};
        spacing: 6px;
        font-size: 13px;
        font-weight: bold;
    }}
    
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border: 2px solid {t['chk_border']};
        border-radius: 4px;
        background-color: {t['chk_bg']};
    }}
    
    QCheckBox::indicator:hover {{
        border-color: {t['chk_hover_border']};
    }}
    
    QCheckBox::indicator:checked {{
        border: 2px solid {t['chk_checked_border']};
        background-color: {t['chk_checked_bg']};
        image: url("{CHECK_ICON_PATH}");
    }}
    
    QCheckBox::indicator:checked:hover {{
        border-color: {t['accent_active']};
    }}
    
    /* 水平滑桿 (QSlider) 現代化樣式 */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {t['border']};
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t['accent']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: #ffffff;
        border: 2px solid {t['accent']};
        width: 18px;
        margin-top: -6px;
        margin-bottom: -6px;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {t['accent']};
        border-color: #ffffff;
    }}
    
    QStatusBar {{
        background-color: {t['bg_secondary']};
        color: {t['text_primary']};
        border-top: 1px solid {t['border']};
        font-size: 13px;
        padding: 3px 8px;
    }}
    
    /* 移除狀態列元件邊框 */
    QStatusBar::item {{
        border: none;
    }}
    
    QTableWidget {{
        background-color: {t['bg_secondary']};
        gridline-color: {t['border']};
        border: 1px solid {t['border']};
    }}
    
    QHeaderView::section {{
        background-color: {t['toolbar_bg']};
        color: {t['text_primary']};
        padding: 6px;
        border: 1px solid {t['border']};
        font-weight: bold;
    }}
    """
