"""
排版設定對話框 (Typography & Layout Settings Dialog)
支援字體大小（12~100 pt）與行距倍數（雙欄對稱滑桿）、字型選擇、
自訂色彩（左側）與大寬度即時預覽（右側對比）、關閉後清除文本選項。
"""

import os
import sys
import json
import html
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QFontComboBox,
    QTextEdit, QColorDialog, QFrame, QWidget, QCheckBox
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal

from ui.theme import THEMES

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_appdata_dir = os.environ.get("EDGESRT_APPDATA_DIR", os.path.join(APP_DIR, "_appdata"))
CONFIG_FILE = os.path.join(_appdata_dir, "typography.json")

DEFAULT_TYPOGRAPHY: Dict[str, Any] = {
    "font_family": "Microsoft JhengHei UI",
    "font_size": 24,
    "line_spacing": 1.2,
    "custom_bg": "#000000",
    "custom_fg": "#ffd700",
    "custom_interim": "#38bdf8",
    "clear_on_exit": True
}


def load_typography() -> Dict[str, Any]:
    """載入排版與文字設定"""
    cfg = dict(DEFAULT_TYPOGRAPHY)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            pass
    return cfg


def save_typography(cfg: Dict[str, Any]):
    """儲存排版設定"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"儲存排版設定失敗: {e}")


class TypographyDialog(QDialog):
    """排版與自訂色彩設定視窗 (寬版：左側自訂色彩，右側大寬度即時預覽)"""

    settings_updated = pyqtSignal(dict)

    def __init__(self, theme_key: str = "night", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 排版與字體色彩設定")
        self.resize(880, 560)
        self.setMinimumSize(780, 480)
        self.theme_key = theme_key
        self.cfg = load_typography()

        # 暫存色彩
        self.custom_bg = self.cfg.get("custom_bg", "#000000")
        self.custom_fg = self.cfg.get("custom_fg", "#ffd700")
        self.custom_interim = self.cfg.get("custom_interim", "#38bdf8")

        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        t = THEMES.get(self.theme_key, THEMES["night"])
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(14)

        # ── 1. 頂部區域：字型選擇與雙欄對稱滑桿 ──
        top_box = QVBoxLayout()
        top_box.setSpacing(10)

        # 字型選擇行
        font_header = QHBoxLayout()
        font_header.setSpacing(12)
        lbl_font = QLabel("<b>🔤 字型選擇：</b>")
        lbl_font.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        font_header.addWidget(lbl_font)

        self.combo_font = QFontComboBox()
        self.combo_font.setMaximumWidth(450)
        self.combo_font.setMaxVisibleItems(10)
        self.combo_font.setSizeAdjustPolicy(QFontComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_font.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.combo_font.view().setTextElideMode(Qt.TextElideMode.ElideRight)
        self.combo_font.setCurrentFont(QFont(self.cfg.get("font_family", "Microsoft JhengHei UI")))
        self.combo_font.currentFontChanged.connect(self._update_preview)
        font_header.addWidget(self.combo_font)
        font_header.addStretch(1)
        top_box.addLayout(font_header)

        # 雙欄式滑桿：左欄字體大小 (12~100 pt) + 右欄行距倍數 (1.0~3.0 倍)
        dual_slider_layout = QHBoxLayout()
        dual_slider_layout.setSpacing(24)

        # 左欄：字體大小
        size_box = QVBoxLayout()
        size_box.setSpacing(4)
        size_header = QHBoxLayout()
        lbl_size = QLabel("<b>📏 字體大小：</b>")
        lbl_size.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        size_header.addWidget(lbl_size)

        init_size = int(self.cfg.get("font_size", 24))
        self.lbl_font_size_val = QLabel(f"<b>{init_size} pt</b>")
        self.lbl_font_size_val.setStyleSheet(f"font-size: 14px; color: {t['accent']};")
        size_header.addWidget(self.lbl_font_size_val)
        size_header.addStretch()
        size_box.addLayout(size_header)

        self.slider_font_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_font_size.setRange(12, 100)
        self.slider_font_size.setValue(init_size)
        self.slider_font_size.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_font_size.setTickInterval(8)
        self.slider_font_size.valueChanged.connect(self._on_font_size_slider_changed)
        size_box.addWidget(self.slider_font_size)
        dual_slider_layout.addLayout(size_box, 1)

        # 右欄：行距倍數
        spacing_box = QVBoxLayout()
        spacing_box.setSpacing(4)
        spacing_header = QHBoxLayout()
        lbl_spacing = QLabel("<b>📐 行距倍數：</b>")
        lbl_spacing.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        spacing_header.addWidget(lbl_spacing)

        init_spacing = float(self.cfg.get("line_spacing", 1.6))
        self.lbl_line_spacing_val = QLabel(f"<b>{init_spacing:.1f} 倍</b>")
        self.lbl_line_spacing_val.setStyleSheet(f"font-size: 14px; color: {t['accent']};")
        spacing_header.addWidget(self.lbl_line_spacing_val)
        spacing_header.addStretch()
        spacing_box.addLayout(spacing_header)

        self.slider_line_spacing = QSlider(Qt.Orientation.Horizontal)
        self.slider_line_spacing.setRange(10, 30)  # 1.0 ~ 3.0 倍
        self.slider_line_spacing.setValue(int(init_spacing * 10))
        self.slider_line_spacing.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_line_spacing.setTickInterval(2)
        self.slider_line_spacing.valueChanged.connect(self._on_line_spacing_slider_changed)
        spacing_box.addWidget(self.slider_line_spacing)
        dual_slider_layout.addLayout(spacing_box, 1)

        top_box.addLayout(dual_slider_layout)
        main_layout.addLayout(top_box)

        # 分割線
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"color: {t['border']}; margin: 2px 0;")
        main_layout.addWidget(sep1)

        # ── 2. 中間區域：左側自訂色彩與設定 vs 右側大寬度即時預覽 ──
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(20)

        # === 左側欄：色彩自訂與進階選項 ===
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        lbl_color_title = QLabel("<b>🎨 自訂色彩方案（【自訂】主題）：</b>")
        lbl_color_title.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        left_col.addWidget(lbl_color_title)

        color_layout = QGridLayout()
        color_layout.setSpacing(8)

        # 編輯區背景底色
        color_layout.addWidget(QLabel("編輯區背景底色："), 0, 0)
        self.btn_bg_color = QPushButton(f"  {self.custom_bg}  ")
        self.btn_bg_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_color_btn(self.btn_bg_color, self.custom_bg)
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        color_layout.addWidget(self.btn_bg_color, 0, 1)

        # 已確認文字顏色 (落地字幕)
        color_layout.addWidget(QLabel("已確認文字顏色 (落地字幕)："), 1, 0)
        self.btn_fg_color = QPushButton(f"  {self.custom_fg}  ")
        self.btn_fg_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_color_btn(self.btn_fg_color, self.custom_fg)
        self.btn_fg_color.clicked.connect(self._pick_fg_color)
        color_layout.addWidget(self.btn_fg_color, 1, 1)

        # 即時辨識中顏色 (未落地字幕)
        color_layout.addWidget(QLabel("即時辨識中顏色 (未落地字幕)："), 2, 0)
        self.btn_interim_color = QPushButton(f"  {self.custom_interim}  ")
        self.btn_interim_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_color_btn(self.btn_interim_color, self.custom_interim)
        self.btn_interim_color.clicked.connect(self._pick_interim_color)
        color_layout.addWidget(self.btn_interim_color, 2, 1)
        left_col.addLayout(color_layout)

        # 分割線 (區隔色彩設定與系統行為選項)
        left_sep = QFrame()
        left_sep.setFrameShape(QFrame.Shape.HLine)
        left_sep.setStyleSheet(f"color: {t['border']}; margin: 8px 0;")
        left_col.addWidget(left_sep)

        # 關閉後清除文本選項
        self.chk_clear_on_exit = QCheckBox("關閉程式後清除文本（下次啟動不留記錄）")
        self.chk_clear_on_exit.setChecked(bool(self.cfg.get("clear_on_exit", False)))
        self.chk_clear_on_exit.setStyleSheet("font-size: 13px; font-weight: bold;")
        left_col.addWidget(self.chk_clear_on_exit)

        left_col.addStretch(1)
        mid_layout.addLayout(left_col, 4)

        # === 右側欄：寬敞的即時預覽區 ===
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        lbl_prev = QLabel("<b>效果即時預覽（落地字幕 vs 未落地即時字幕）：</b>")
        lbl_prev.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        right_col.addWidget(lbl_prev)

        self.preview_editor = QTextEdit()
        self.preview_editor.setReadOnly(True)
        right_col.addWidget(self.preview_editor, 1)

        mid_layout.addLayout(right_col, 6)
        main_layout.addLayout(mid_layout, 1)

        # ── 3. 底部按鈕列 ──
        btn_layout = QHBoxLayout()

        btn_reset = QPushButton("🔄 重設為預設值")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 儲存並套用")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            f"background-color: {t['btn_active']}; color: {t['btn_active_text']}; "
            f"font-weight: bold; padding: 6px 18px;"
        )
        btn_save.clicked.connect(self._save_and_apply)
        btn_layout.addWidget(btn_save)

        main_layout.addLayout(btn_layout)

    def _on_font_size_slider_changed(self, val: int):
        self.lbl_font_size_val.setText(f"<b>{val} pt</b>")
        self._update_preview()

    def _on_line_spacing_slider_changed(self, val: int):
        sp = val / 10.0
        self.lbl_line_spacing_val.setText(f"<b>{sp:.1f} 倍</b>")
        self._update_preview()

    def _style_color_btn(self, btn: QPushButton, color_hex: str):
        """設定色塊按鈕背景與對比文字色"""
        c = QColor(color_hex)
        lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        txt_col = "#000000" if lum > 140 else "#ffffff"
        btn.setStyleSheet(
            f"background-color: {color_hex}; color: {txt_col}; font-weight: bold; "
            f"border: 2px solid #555; border-radius: 6px; padding: 6px 14px;"
        )
        btn.setText(f"  {color_hex.upper()}  ")

    def _pick_bg_color(self):
        col = QColorDialog.getColor(QColor(self.custom_bg), self, "選擇編輯區背景底色")
        if col.isValid():
            self.custom_bg = col.name()
            self._style_color_btn(self.btn_bg_color, self.custom_bg)
            self._update_preview()

    def _pick_fg_color(self):
        col = QColorDialog.getColor(QColor(self.custom_fg), self, "選擇已確認落地字幕顏色")
        if col.isValid():
            self.custom_fg = col.name()
            self._style_color_btn(self.btn_fg_color, self.custom_fg)
            self._update_preview()

    def _pick_interim_color(self):
        col = QColorDialog.getColor(QColor(self.custom_interim), self, "選擇即時辨識中（未落地）字幕顏色")
        if col.isValid():
            self.custom_interim = col.name()
            self._style_color_btn(self.btn_interim_color, self.custom_interim)
            self._update_preview()

    def _update_preview(self):
        """更新即時預覽畫面"""
        font_fam = self.combo_font.currentFont().family()
        font_sz = self.slider_font_size.value()
        line_sp = self.slider_line_spacing.value() / 10.0

        self.preview_editor.setStyleSheet(
            f"background-color: {self.custom_bg}; border: 1px solid #444; border-radius: 6px; padding: 14px;"
        )

        preview_html = (
            f'<div style="font-family: \'{font_fam}\', sans-serif; font-size: {font_sz}pt; '
            f'line-height: {line_sp}; color: {self.custom_fg};">'
            f'<p style="margin: 0 0 10px 0;">這是已確認辨識的文字段落（落地字幕範例）。</p>'
            f'<p style="margin: 0; color: {self.custom_interim}; font-weight: bold;">'
            f'這是正在即時辨識中的文字（未落地即時字幕範例）... <span style="opacity: 0.6;">...</span></p>'
            f'</div>'
        )
        self.preview_editor.setHtml(preview_html)

    def _reset_defaults(self):
        self.combo_font.setCurrentFont(QFont(DEFAULT_TYPOGRAPHY["font_family"]))
        self.slider_font_size.setValue(DEFAULT_TYPOGRAPHY["font_size"])
        self.slider_line_spacing.setValue(int(DEFAULT_TYPOGRAPHY["line_spacing"] * 10))
        self.custom_bg = DEFAULT_TYPOGRAPHY["custom_bg"]
        self.custom_fg = DEFAULT_TYPOGRAPHY["custom_fg"]
        self.custom_interim = DEFAULT_TYPOGRAPHY["custom_interim"]
        self.chk_clear_on_exit.setChecked(DEFAULT_TYPOGRAPHY["clear_on_exit"])
        self._style_color_btn(self.btn_bg_color, self.custom_bg)
        self._style_color_btn(self.btn_fg_color, self.custom_fg)
        self._style_color_btn(self.btn_interim_color, self.custom_interim)
        self._update_preview()

    def _save_and_apply(self):
        new_cfg = {
            "font_family": self.combo_font.currentFont().family(),
            "font_size": self.slider_font_size.value(),
            "line_spacing": self.slider_line_spacing.value() / 10.0,
            "custom_bg": self.custom_bg,
            "custom_fg": self.custom_fg,
            "custom_interim": self.custom_interim,
            "clear_on_exit": self.chk_clear_on_exit.isChecked()
        }
        save_typography(new_cfg)
        self.settings_updated.emit(new_cfg)
        self.accept()
