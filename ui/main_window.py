"""
主視窗模組 (Main Window)
即時語音轉錄核心介面：多音源頂部快速切換、即時文字串流（含 Interim 臨時字即時顯示）、
錄音時防誤觸唯讀保護（暫停後開放自由編輯）、字級大小即時縮放（預設 24pt）、
支援回捲查看歷史文字 + 懸浮【⬇️ 回到底部】按鈕、狀態列【強制置底】開關、純繁體中文介面。
"""

import os
import sys
import html
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QToolBar,
    QComboBox, QSpinBox, QFileDialog, QMessageBox,
    QStatusBar, QFrame, QApplication, QCheckBox, QProgressBar
)
from PyQt6.QtGui import QFont, QTextCursor, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QEvent

from audio_manager import AudioManager, AudioDeviceInfo
from capture_server import CaptureServer
from ui.theme import THEMES, get_stylesheet, ASSETS_DIR
from ui.glossary_dialog import GlossaryDialog, load_glossary, apply_glossary
from ui.settings_dialog import SettingsDialog
from ui.license_dialog import LicenseDialog
from ui.typography_dialog import TypographyDialog, load_typography

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_appdata_dir = os.environ.get("EDGESRT_APPDATA_DIR", os.path.join(APP_DIR, "_appdata"))
AUTOSAVE_FILE = os.path.join(_appdata_dir, "autosave", "autosave.txt")


class MainWindow(QMainWindow):
    """即時語音轉錄桌面主視窗"""
    
    sig_interim_text = pyqtSignal(str)
    sig_final_text = pyqtSignal(str)
    sig_status_msg = pyqtSignal(str)
    sig_volume = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edge 即時語音轉錄工具 (多音源快速切換版)")
        icon_path = os.path.join(ASSETS_DIR, "app_icon.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1080, 750)
        self.setMinimumSize(360, 400)

        # 核心狀態與資料
        self.audio_manager = AudioManager()
        self.glossary: Dict[str, str] = load_glossary()
        self.typography_cfg = load_typography()
        self.current_theme = "night"
        self.is_recording = True
        self.layout_mode = "full"  # "full" | "half" | "third"
        self.font_size = int(self.typography_cfg.get("font_size", 24))
        self.font_family = self.typography_cfg.get("font_family", "Microsoft JhengHei UI")
        self.line_spacing = float(self.typography_cfg.get("line_spacing", 1.2))
        self.auto_scroll = True
        
        # 轉錄文字緩衝區
        self.final_paragraphs: List[str] = []
        self.current_interim = ""
        self.active_device_id: Optional[str] = self.audio_manager.get_current_default_device_id()

        # 語音後台服務
        self.capture_server = CaptureServer(
            on_interim_text=lambda t: self.sig_interim_text.emit(t),
            on_final_text=lambda t: self.sig_final_text.emit(t),
            on_status_change=lambda s: self.sig_status_msg.emit(s),
            on_volume=lambda v: self.sig_volume.emit(v)
        )

        # 建立 UI 與訊號
        self._init_ui()
        self._init_signals()
        self._apply_theme(self.current_theme)

        # 啟動 Edge 背景識別引擎
        self.capture_server.start(hidden_edge=True)

        # 自動存檔定時器 (每 10 秒)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._auto_save)
        self.autosave_timer.start(10000)

        # 恢復自動存檔
        self._restore_autosave()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. 頂部音訊來源快速切換按鈕區
        self.top_source_frame = QFrame()
        self.top_source_frame.setObjectName("top_source_frame")
        self.top_source_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.top_source_layout = QHBoxLayout(self.top_source_frame)
        self.top_source_layout.setContentsMargins(8, 4, 8, 4)
        self.top_source_layout.setSpacing(8)
        main_layout.addWidget(self.top_source_frame)

        # 2. 主要功能工具列
        self.main_toolbar = self._create_main_toolbar()

        # 3. 核心文字轉錄區 (預設唯讀，暫停後開放編輯)
        self.editor = QTextEdit()
        font = QFont(self.font_family, self.font_size)
        self.editor.setFont(font)
        self.editor.setReadOnly(True)  # 錄音中不可編輯文字
        self.editor.textChanged.connect(self._on_user_text_edited)
        self.editor.installEventFilter(self)
        self.editor.viewport().installEventFilter(self)

        # 捲軸監聽 (偵測使用者是否向上回捲)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_scrolled)
        main_layout.addWidget(self.editor, stretch=1)

        # 懸浮按鈕：【⬇️ 回到底部】
        self.btn_jump_bottom = QPushButton("⬇️ 回到底部", self.editor)
        self.btn_jump_bottom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_jump_bottom.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #ffffff; font-size: 14px; font-weight: bold; "
            "border-radius: 18px; padding: 8px 16px; border: 2px solid #60a5fa; }"
            "QPushButton:hover { background-color: #1d4ed8; border-color: #93c5fd; }"
        )
        self.btn_jump_bottom.clicked.connect(self._scroll_to_bottom)
        self.btn_jump_bottom.hide()

        # 空白初始提示疊層 (採用 Qt 原生佈局保證 100% 絕對幾何上下垂直置中)
        self.empty_prompt_widget = QWidget(self.editor.viewport())
        self.empty_prompt_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.empty_prompt_widget.setStyleSheet("background: transparent;")
        
        prompt_layout = QVBoxLayout(self.empty_prompt_widget)
        prompt_layout.setContentsMargins(24, 20, 24, 20)
        prompt_layout.setSpacing(10)
        prompt_layout.addStretch(1)

        self.lbl_empty_icon = QLabel("🎙️")
        self.lbl_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_icon.setStyleSheet("font-size: 38pt; background: transparent;")
        prompt_layout.addWidget(self.lbl_empty_icon)

        self.lbl_empty_title = QLabel("正在即時聆聽語音中...")
        self.lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_title.setStyleSheet("font-size: 20pt; font-weight: bold; background: transparent;")
        prompt_layout.addWidget(self.lbl_empty_title)

        self.lbl_empty_desc = QLabel("請開始說話或播放電腦音訊，辨識文字將即時呈現於此。")
        self.lbl_empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_desc.setStyleSheet("font-size: 14pt; background: transparent; opacity: 0.85;")
        prompt_layout.addWidget(self.lbl_empty_desc)

        prompt_layout.addSpacing(14)

        tip_container = QHBoxLayout()
        tip_container.addStretch(1)
        self.lbl_empty_tip = QLabel("💡 <b>溫馨提醒：</b>若上方音量條沒有波動，請確認電腦播放音量／麥克風已調大且未被靜音。")
        self.lbl_empty_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_container.addWidget(self.lbl_empty_tip)
        tip_container.addStretch(1)
        prompt_layout.addLayout(tip_container)

        prompt_layout.addStretch(1)

        # 4. 底部狀態列 (左側狀態、幾何絕對置中授權聲明、右側字數與最右側強制置底)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.installEventFilter(self)
        
        self.lbl_ws_status = QLabel("🟢 正在連線語音引擎...")
        self.lbl_mode_status = QLabel("🔒 文字區唯讀保護")
        self.lbl_word_count = QLabel("總字數: 0 字")
        
        # 視窗置頂核取方塊 (拉高層級常駐最上層)
        self.chk_always_on_top = QCheckBox("視窗置頂")
        self.chk_always_on_top.setToolTip("勾選後將拉高視窗優先層級，即使切換到其他程式也不會被覆蓋")
        self.chk_always_on_top.setChecked(False)
        self.chk_always_on_top.setStyleSheet("QCheckBox { margin-left: 10px; margin-right: 6px; }")
        self.chk_always_on_top.stateChanged.connect(self._on_always_on_top_toggled)

        # 字幕置底核取方塊 (置於最右側，保留右側邊距不貼邊)
        self.chk_force_scroll = QCheckBox("字幕置底 ")
        self.chk_force_scroll.setToolTip("勾選後將始終鎖定捲軸置底，禁止回捲")
        self.chk_force_scroll.setChecked(False)
        self.chk_force_scroll.setStyleSheet("QCheckBox { margin-right: 12px; margin-left: 6px; }")
        self.chk_force_scroll.stateChanged.connect(self._on_force_scroll_toggled)

        # 狀態列左側元件 (保留轉錄連線狀態與唯讀保護狀態)
        self.status_bar.addWidget(self.lbl_ws_status)
        self.status_bar.addWidget(self.lbl_mode_status)

        # 狀態列右側常駐元件 (右側由左至右：字數統計 -> 視窗置頂 -> 字幕置底)
        self.status_bar.addPermanentWidget(self.lbl_word_count)
        self.status_bar.addPermanentWidget(self.chk_always_on_top)
        self.status_bar.addPermanentWidget(self.chk_force_scroll)

        # 狀態列中間【授權聲明】四個字按鈕（絕對幾何置中，不受左側狀態文字長短影響）
        self.btn_license_status = QPushButton("授權聲明", self.status_bar)
        self.btn_license_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_license_status.setToolTip("點擊查看完整軟體授權、開發者聲明與第三方開源套件清單")
        self.btn_license_status.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 13px; color: #38bdf8; text-decoration: underline; padding: 2px 8px; }"
            "QPushButton:hover { color: #60a5fa; }"
        )
        self.btn_license_status.clicked.connect(self._open_license)

        # 5. 渲染頂部按鈕與初始畫面
        self._refresh_top_source_buttons()
        self._render_transcript()

    def _create_main_toolbar(self) -> QToolBar:
        toolbar = QToolBar("主要功能工具列")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # === Group 1: 語音轉錄控制與語言選擇 ===
        self.btn_toggle_record = QPushButton("⏸️ 暫停轉錄")
        self.btn_toggle_record.setToolTip("暫停 AI 語音寫入，並解鎖文字區以供手動編輯修改")
        self.btn_toggle_record.clicked.connect(self._toggle_recording)
        toolbar.addWidget(self.btn_toggle_record)

        # 語言選擇
        self.lbl_lang = QLabel(" 語言: ")
        self.act_lbl_lang = toolbar.addWidget(self.lbl_lang)
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("繁體中文 (台灣)", "zh-TW")
        self.combo_lang.addItem("簡體中文 (大陸)", "zh-CN")
        self.combo_lang.addItem("English (US)", "en-US")
        self.combo_lang.addItem("日本語 (日本)", "ja-JP")
        self.combo_lang.currentIndexChanged.connect(self._on_lang_changed)
        self.act_combo_lang = toolbar.addWidget(self.combo_lang)

        self.act_sep1 = toolbar.addSeparator()

        # === Group 2: 字幕與文字處理 (清空、複製、匯出) ===
        # 清空畫面
        self.btn_clear = QPushButton("🧹 清空文字")
        self.btn_clear.setToolTip("清空目前編輯區中的全部轉錄文字")
        self.btn_clear.clicked.connect(self._clear_editor)
        self.act_btn_clear = toolbar.addWidget(self.btn_clear)

        # 複製全文
        self.btn_copy = QPushButton("📋 複製全文")
        self.btn_copy.setToolTip("將目前全部轉錄文字複製到剪貼簿")
        self.btn_copy.clicked.connect(self._copy_all_text)
        self.act_btn_copy = toolbar.addWidget(self.btn_copy)

        # 匯出文字
        self.btn_export = QPushButton("💾 匯出文字")
        self.btn_export.setToolTip("匯出目前轉錄內容為 TXT 純文字檔案")
        self.btn_export.clicked.connect(self._export_txt)
        self.act_btn_export = toolbar.addWidget(self.btn_export)

        self.act_sep2 = toolbar.addSeparator()

        # === Group 3: 系統偏好與設定 (詞彙、音源、排版) ===
        # 詞彙替換表
        self.btn_glossary = QPushButton("📖 詞彙替換")
        self.btn_glossary.clicked.connect(self._open_glossary)
        self.act_btn_glossary = toolbar.addWidget(self.btn_glossary)

        # 音源設定
        self.btn_settings = QPushButton("⚙️ 音源設定")
        self.btn_settings.setToolTip("設定 Windows 辨識到的錄音裝置別名與切換按鈕")
        self.btn_settings.clicked.connect(self._open_settings)
        self.act_btn_settings = toolbar.addWidget(self.btn_settings)

        # 排版設定 (字體大小、字型、行距、自訂色彩)
        self.btn_typography = QPushButton("🎨 排版設定")
        self.btn_typography.setToolTip("自訂字型、字體大小、行距倍數與色彩方案")
        self.btn_typography.clicked.connect(self._open_typography)
        self.act_btn_typography = toolbar.addWidget(self.btn_typography)

        self.act_sep3 = toolbar.addSeparator()

        # === Group 4: 介面主題外觀 ===
        self.lbl_theme = QLabel(" 主題: ")
        self.act_lbl_theme = toolbar.addWidget(self.lbl_theme)
        self.combo_theme = QComboBox()
        for k, v in THEMES.items():
            self.combo_theme.addItem(v["name"], k)
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        self.act_combo_theme = toolbar.addWidget(self.combo_theme)

        self.act_sep4 = toolbar.addSeparator()

        # === Group 5: 視窗佈局輪替切換按鈕 (全螢幕 ➔ 1/2 ➔ 1/3) ===
        self.btn_layout_cycle = QPushButton("🪟 1/2")
        self.btn_layout_cycle.setToolTip("點擊切換視窗佈局：全螢幕 ➔ 1/2靠右 ➔ 1/3靠右")
        self.btn_layout_cycle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_layout_cycle.clicked.connect(self._cycle_window_layout)
        toolbar.addWidget(self.btn_layout_cycle)

        return toolbar

    def _refresh_top_source_buttons(self):
        """依據設定動態生成頂部音源快速切換按鈕"""
        while self.top_source_layout.count():
            item = self.top_source_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        t = THEMES.get(self.current_theme, THEMES["night"])
        tip_title = QLabel("<b>🎙️ 音源切換：</b>")
        tip_title.setStyleSheet(f"font-size: 14px; color: {t['text_primary']};")
        self.top_source_layout.addWidget(tip_title)

        devices = self.audio_manager.list_capture_devices()
        self.active_device_id = self.audio_manager.get_current_default_device_id()

        current_active_alias = "未偵測到裝置"

        for dev in devices:
            if not dev.show_in_topbar:
                continue

            btn = QPushButton(dev.alias)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"點擊切換為 Windows 預設錄音裝置：\n{dev.name}")

            is_active = (dev.id == self.active_device_id)
            if is_active:
                btn.setStyleSheet(
                    f"background-color: {t['btn_active']}; color: {t['btn_active_text']}; font-weight: bold; "
                    f"border: 1px solid {t['accent_active']}; border-radius: 6px; padding: 6px 14px; font-size: 14px;"
                )
                current_active_alias = dev.alias
            else:
                btn.setStyleSheet(
                    f"background-color: {t['btn_bg']}; color: {t['text_primary']}; "
                    f"border: 1px solid {t['border']}; border-radius: 6px; padding: 6px 14px; font-size: 14px;"
                )

            btn.clicked.connect(lambda _, d=dev: self._switch_audio_source(d))
            self.top_source_layout.addWidget(btn)

        self.top_source_layout.addStretch()

        # 音量跳動條 + 提示警語 (緊湊相鄰排列)
        vol_widget = QWidget()
        vol_layout = QHBoxLayout(vol_widget)
        vol_layout.setContentsMargins(0, 0, 0, 0)
        vol_layout.setSpacing(4)
        vol_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lbl_vol_icon = QLabel("🔈")
        lbl_vol_icon.setFixedWidth(18)
        lbl_vol_icon.setStyleSheet("font-size: 13px; margin: 0; padding: 0;")
        vol_layout.addWidget(lbl_vol_icon)

        self.progress_volume = QProgressBar()
        self.progress_volume.setRange(0, 100)
        self.progress_volume.setValue(0)
        self.progress_volume.setTextVisible(False)
        self.progress_volume.setFixedSize(65, 8)
        self.progress_volume.setStyleSheet(
            f"QProgressBar {{ background-color: {t['btn_bg']}; border: 1px solid {t['border']}; border-radius: 4px; margin: 0; }}"
            f"QProgressBar::chunk {{ background-color: {t['accent_active']}; border-radius: 3px; }}"
        )
        vol_layout.addWidget(self.progress_volume)

        # 音量提示說明文字 (1/2 與 1/3 模式自動隱藏)
        self.lbl_vol_tip = QLabel("💡 提示：若音量條無波動，請確認音源已開啟且音量有調大")
        self.lbl_vol_tip.setStyleSheet(f"font-size: 12px; color: {t['text_primary']}; opacity: 0.75; margin-left: 8px;")
        self.lbl_vol_tip.setVisible(self.layout_mode == "full")
        vol_layout.addWidget(self.lbl_vol_tip)

        self.top_source_layout.addWidget(vol_widget)

    def _switch_audio_source(self, dev: AudioDeviceInfo):
        """切換 Windows 預設錄音源並通知 Edge 立即切換識別"""
        # 切換音源瞬間立即清空前一個音源的臨時暫存字
        self.current_interim = ""
        self._render_transcript()

        if dev.id == self.active_device_id:
            self.capture_server.restart_asr()
            return

        ok = self.audio_manager.set_default_device(dev.id)
        if ok:
            self.active_device_id = dev.id
            self._refresh_top_source_buttons()
            self.capture_server.restart_asr()
            self.status_bar.showMessage(f"已成功切換錄音源至：{dev.alias}", 3000)
        else:
            QMessageBox.warning(self, "切換失敗", f"無法切換至所選音源：{dev.name}")

    def _init_signals(self):
        self.sig_interim_text.connect(self._handle_interim_text)
        self.sig_final_text.connect(self._handle_final_text)
        self.sig_status_msg.connect(self._handle_status_msg)
        self.sig_volume.connect(self._handle_volume)

    def _handle_volume(self, vol: int):
        """即時更新音量進度條"""
        if hasattr(self, 'progress_volume') and self.progress_volume:
            pct = min(100, int(vol * 2.5))
            self.progress_volume.setValue(pct)

    def _render_transcript(self):
        """即時將 Final 落地段落與 Interim 臨時辨識字渲染到文字區"""
        t = THEMES.get(self.current_theme, THEMES["night"])
        
        font_family = self.typography_cfg.get("font_family", "Microsoft JhengHei UI")
        font_size = self.typography_cfg.get("font_size", 24)
        line_spacing = self.typography_cfg.get("line_spacing", 1.6)

        # 自訂主題色彩套用
        if self.current_theme == "custom":
            bg_color = self.typography_cfg.get("custom_bg", "#000000")
            fg_color = self.typography_cfg.get("custom_fg", "#ffd700")
            interim_color = self.typography_cfg.get("custom_interim", "#38bdf8")
            self.editor.setStyleSheet(
                f"background-color: {bg_color}; color: {fg_color}; "
                f"border: 1px solid {t['border']}; border-radius: 6px; padding: 16px;"
            )
        else:
            self.editor.setStyleSheet("")
            fg_color = t["text_editor"]
            interim_color = t["text_interim"]

        has_text = bool(self.final_paragraphs or self.current_interim.strip())

        if not has_text:
            self._update_empty_prompt_style()
            self._update_empty_prompt_geometry()
            self.empty_prompt_widget.show()
            self.empty_prompt_widget.raise_()
            full_html = ""
        else:
            self.empty_prompt_widget.hide()
            html_parts = [
                f'<div style="font-family: \'{font_family}\', sans-serif; '
                f'font-size: {font_size}pt; line-height: {line_spacing}; color: {fg_color};">'
            ]

            # 1. 已確定的落地文字段落 (Final)
            for para in self.final_paragraphs:
                safe_text = html.escape(para).replace('\n', '<br>')
                html_parts.append(f'<p style="margin: 0 0 10px 0;">{safe_text}</p>')

            # 2. 即時正在說話的臨時辨識字 (Interim)
            if self.current_interim.strip():
                safe_interim = html.escape(self.current_interim.strip())
                html_parts.append(
                    f'<p style="margin: 0 0 10px 0; color: {interim_color}; font-weight: bold;">'
                    f'{safe_interim} <span style="opacity: 0.7; font-size: 0.85em;">...</span></p>'
                )

            html_parts.append('</div>')
            full_html = "".join(html_parts)

        # 記錄當前捲軸位置
        vbar = self.editor.verticalScrollBar()
        prev_scroll = vbar.value()

        # 阻斷 textChanged 避免誤觸
        self.editor.blockSignals(True)
        self.editor.setHtml(full_html)
        self.editor.blockSignals(False)

        # 判斷是否強制置底或自動捲動
        if self.chk_force_scroll.isChecked() or self.auto_scroll:
            vbar.setValue(vbar.maximum())
            self.btn_jump_bottom.hide()
        else:
            # 使用者正在回看上方內容：保持當前捲軸位置不強制跳回底部
            vbar.setValue(prev_scroll)
            self._update_jump_button_pos()
            self.btn_jump_bottom.show()

        self._update_word_count()

    def _update_empty_prompt_geometry(self):
        """保證空白提示疊層覆蓋整個 editor viewport 並自動幾何置中"""
        if hasattr(self, 'empty_prompt_widget') and hasattr(self, 'editor'):
            vp = self.editor.viewport()
            self.empty_prompt_widget.setGeometry(0, 0, vp.width(), vp.height())

    def _update_empty_prompt_style(self):
        """根據當前主題與自訂色彩更新空白提示文字顏色"""
        if not hasattr(self, 'empty_prompt_widget') or not hasattr(self, 'lbl_empty_title'):
            return
        t = THEMES.get(self.current_theme, THEMES["night"])
        if self.current_theme == "custom":
            fg_color = self.typography_cfg.get("custom_fg", "#ffd700")
        else:
            fg_color = t.get("text_editor", t["text_primary"])

        self.lbl_empty_title.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {fg_color}; background: transparent;")
        self.lbl_empty_desc.setStyleSheet(f"font-size: 14pt; color: {t['text_primary']}; opacity: 0.85; background: transparent;")
        self.lbl_empty_tip.setStyleSheet(
            f"font-size: 12pt; color: {fg_color}; padding: 8px 22px; border-radius: 18px; "
            f"background: rgba(255, 215, 0, 0.08); border: 1px solid rgba(255, 215, 0, 0.28);"
        )

    def _handle_interim_text(self, text: str):
        """接收即時 Interim 臨時字"""
        if not self.is_recording:
            return
        self.lbl_ws_status.setText("🟢 語音辨識中")
        if not text or not text.strip():
            self.current_interim = ""
        else:
            self.current_interim = apply_glossary(text, self.glossary)
        self._render_transcript()

    def _handle_final_text(self, text: str):
        """接收 Final 最終落地字"""
        if not self.is_recording:
            return
        self.lbl_ws_status.setText("🟢 語音辨識中")
        processed = apply_glossary(text, self.glossary)
        stripped = processed.strip()
        if stripped:
            # Edge 語音引擎在背景自動重連（斷線重連/僵死恢復）時，偶爾會把重連前
            # 剛落地過的同一段話重新辨識一次並再送一次 final，導致整段文字重複。
            # 只針對「較長、完全相同」的連續重複做防呆；短詞重複（如「OK，OK」）
            # 是真實語意，不能被這條規則吃掉。
            is_dup = (
                len(stripped) >= 8
                and self.final_paragraphs
                and self.final_paragraphs[-1] == stripped
            )
            if not is_dup:
                self.final_paragraphs.append(stripped)
        self.current_interim = ""
        self._render_transcript()

    def _handle_status_msg(self, msg: str):
        self.lbl_ws_status.setText(f"🟢 {msg}")

    def _on_editor_scrolled(self, value: int):
        """監聽文字區捲動：判斷是否顯示【⬇️ 回到底部】懸浮按鈕"""
        vbar = self.editor.verticalScrollBar()
        if self.chk_force_scroll.isChecked():
            # 強制置底啟用時：禁止向上回捲
            if value < vbar.maximum():
                vbar.setValue(vbar.maximum())
            self.auto_scroll = True
            self.btn_jump_bottom.hide()
            return

        # 容許 30px 誤差
        is_at_bottom = (value >= vbar.maximum() - 30)
        if is_at_bottom:
            self.auto_scroll = True
            self.btn_jump_bottom.hide()
        else:
            # 使用者已向上回捲查看先前內容
            self.auto_scroll = False
            self._update_jump_button_pos()
            self.btn_jump_bottom.show()

    def _scroll_to_bottom(self):
        """點擊懸浮按鈕：回到最底部並恢復自動捲動"""
        vbar = self.editor.verticalScrollBar()
        vbar.setValue(vbar.maximum())
        self.auto_scroll = True
        self.btn_jump_bottom.hide()

    def _on_always_on_top_toggled(self, state: int):
        """切換視窗置頂 (拉高視窗優先層級常駐最上層)"""
        is_on_top = bool(self.chk_always_on_top.isChecked())
        try:
            import win32gui
            import win32con
            hwnd = int(self.winId())
            hwnd_insert_after = win32con.HWND_TOPMOST if is_on_top else win32con.HWND_NOTOPMOST
            win32gui.SetWindowPos(
                hwnd,
                hwnd_insert_after,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
            )
        except Exception:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, is_on_top)
            self.show()

        if is_on_top:
            self.status_bar.showMessage("已開啟【視窗置頂】，本視窗將常駐於最上層", 2500)
        else:
            self.status_bar.showMessage("已解除【視窗置頂】", 2500)

    def _on_force_scroll_toggled(self, state: int):
        """字幕置底核取方塊切換"""
        if self.chk_force_scroll.isChecked():
            self._scroll_to_bottom()
            self.status_bar.showMessage("已開啟【字幕置底】模式", 2000)
        else:
            self.status_bar.showMessage("已解除【字幕置底】模式，現在可自由向上回看", 2000)

    def _update_jump_button_pos(self):
        """更新【⬇️ 回到底部】按鈕在文字區右下角的位置"""
        if not hasattr(self, 'editor') or not hasattr(self, 'btn_jump_bottom'):
            return
        w = self.editor.width()
        h = self.editor.height()
        btn_w = 126
        btn_h = 38
        self.btn_jump_bottom.setGeometry(w - btn_w - 30, h - btn_h - 26, btn_w, btn_h)

    def _update_license_button_pos(self):
        """保證【授權聲明】按鈕在狀態列水平幾何正中心，不受兩側狀態文字長度影響"""
        if not hasattr(self, 'btn_license_status') or not hasattr(self, 'status_bar'):
            return
        if self.layout_mode == "third" or not self.btn_license_status.isVisible():
            return
        bar_w = self.status_bar.width()
        bar_h = self.status_bar.height()
        btn_sz = self.btn_license_status.sizeHint()
        btn_w = btn_sz.width()
        btn_h = btn_sz.height()
        # 絕對幾何正中央
        x = (bar_w - btn_w) // 2
        y = (bar_h - btn_h) // 2
        self.btn_license_status.setGeometry(x, y, btn_w, btn_h)
        self.btn_license_status.raise_()
        self.btn_license_status.raise_()

    def eventFilter(self, obj, event):
        """雙擊文字區切換全螢幕，大小變動時即時更新懸浮按鈕與授權聲明座標"""
        if obj in (self.editor, self.editor.viewport()):
            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                self.toggle_fullscreen()
                return True
            elif event.type() == QEvent.Type.Resize:
                self._update_jump_button_pos()
                self._update_empty_prompt_geometry()
        elif obj == self.status_bar:
            if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest, QEvent.Type.Show):
                self._update_license_button_pos()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_empty_prompt_geometry()
        self._update_license_button_pos()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_jump_button_pos()
        self._update_license_button_pos()
        self._update_empty_prompt_geometry()

    def toggle_fullscreen(self):
        """切換全螢幕模式 (進入全螢幕隱藏工具列/狀態列；退出還原為視窗顯示)"""
        if self.isFullScreen():
            # 退出全螢幕：還原為視窗顯示狀態
            if self.layout_mode == "full":
                self.showMaximized()
            else:
                self.showNormal()
            self.main_toolbar.show()
            self.top_source_frame.show()
            self.status_bar.show()
            self._set_toolbar_mode(self.layout_mode)
            self._update_license_button_pos()
            self._update_empty_prompt_geometry()
            self.status_bar.showMessage("已退出全螢幕模式", 2000)
        else:
            # 進入全螢幕：隱藏所有外框、工具列與狀態列
            self.main_toolbar.hide()
            self.top_source_frame.hide()
            self.status_bar.hide()
            self.showFullScreen()
            self._update_empty_prompt_geometry()

    def _cycle_window_layout(self):
        """輪替切換視窗佈局：全螢幕 ➔ 1/2靠右 ➔ 1/3靠右"""
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry()

        if self.layout_mode == "full":
            # 切換到 1/2 靠右模式 (保留轉錄、清空、複製、匯出、佈局切換)
            self.layout_mode = "half"
            self.btn_layout_cycle.setText("🪟 1/3")
            self.btn_layout_cycle.setToolTip("目前為 1/2 靠右模式，點擊切換至 1/3 靠右")
            self._set_toolbar_mode("half")
            self.showNormal()
            w = avail.width() // 2
            h = avail.height()
            x = avail.x() + avail.width() - w
            y = avail.y()
            self.setGeometry(x, y, w, h)
            self._update_empty_prompt_geometry()
            self.status_bar.showMessage("已切換為右側 1/2 佈局模式", 2000)

        elif self.layout_mode == "half":
            # 切換到 1/3 靠右模式 (超精簡模式：僅保留 啟動轉錄 與 佈局切換按鈕)
            self.layout_mode = "third"
            self.btn_layout_cycle.setText("🖥️ 全螢幕")
            self.btn_layout_cycle.setToolTip("目前為 1/3 靠右模式，點擊還原全螢幕最大化")
            self._set_toolbar_mode("third")
            self.showNormal()
            w = max(340, avail.width() // 3)
            h = avail.height()
            x = avail.x() + avail.width() - w
            y = avail.y()
            self.setGeometry(x, y, w, h)
            self._update_empty_prompt_geometry()
            self.status_bar.showMessage("已切換為右側 1/3 佈局模式", 2000)

        else:
            # 切換回 全螢幕 / 最大化
            self.layout_mode = "full"
            self.btn_layout_cycle.setText("🪟 1/2")
            self.btn_layout_cycle.setToolTip("目前為全螢幕模式，點擊切換至 1/2 靠右")
            self._set_toolbar_mode("full")
            self.showMaximized()
            self._update_empty_prompt_geometry()
            self.status_bar.showMessage("已還原為全螢幕最大化模式", 2000)

    def _set_toolbar_mode(self, mode: str):
        """
        依據佈局模式動態精簡工具列、狀態列與音量提示
        mode:
        - 'full': 全部項目可見，音量提示、授權聲明、字數皆顯示
        - 'half': 保留 啟動轉錄、清空文字、複製全文、匯出文字、佈局按鈕；隱藏音量提示文字；顯示授權聲明與字數
        - 'third': 僅保留 啟動轉錄、佈局按鈕；隱藏音量提示文字、隱藏授權聲明、隱藏字數統計
        """
        is_full = (mode == "full")
        is_half_or_full = (mode in ("full", "half"))

        # 語言、設定、主題僅在 full 顯示
        for act_name in (
            'act_lbl_lang', 'act_combo_lang', 'act_sep1',
            'act_btn_glossary', 'act_btn_settings', 'act_btn_typography',
            'act_sep3', 'act_lbl_theme', 'act_combo_theme', 'act_sep4'
        ):
            if hasattr(self, act_name):
                getattr(self, act_name).setVisible(is_full)

        # 清空、複製、匯出在 full 和 half 顯示，在 third 隱藏
        for act_name in ('act_btn_clear', 'act_btn_copy', 'act_btn_export', 'act_sep2'):
            if hasattr(self, act_name):
                getattr(self, act_name).setVisible(is_half_or_full)

        # 音量跳動條右邊的說明文字：在 1/2 和 1/3 隱藏，僅在 full 顯示
        if hasattr(self, 'lbl_vol_tip') and self.lbl_vol_tip:
            self.lbl_vol_tip.setVisible(is_full)

        # 授權聲明與字數統計：在 1/3 模式隱藏，在 full 和 half 顯示
        if hasattr(self, 'lbl_word_count') and self.lbl_word_count:
            self.lbl_word_count.setVisible(is_half_or_full)
        if hasattr(self, 'btn_license_status') and self.btn_license_status:
            self.btn_license_status.setVisible(is_half_or_full)
            if is_half_or_full:
                self._update_license_button_pos()

    def keyPressEvent(self, event):
        """支援快捷鍵：Esc / F11 切換全螢幕，Ctrl+F4 關閉程式"""
        if event.key() == Qt.Key.Key_F4 and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.close()
            return
        elif event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11) and self.isFullScreen():
            self.toggle_fullscreen()
            return
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        super().keyPressEvent(event)

    def _toggle_recording(self):
        """切換錄音/暫停狀態（錄音時唯讀保護；暫停時解鎖編輯）"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            # 恢復錄音：將使用者在暫停期間手動修改的文字同步回緩衝區，並鎖定唯讀
            edited_text = self.editor.toPlainText().strip()
            if edited_text:
                self.final_paragraphs = [p.strip() for p in edited_text.split('\n') if p.strip()]
            else:
                self.final_paragraphs = []
            self.current_interim = ""

            self.editor.setReadOnly(True)
            self.btn_toggle_record.setText("⏸️ 暫停轉錄")
            self.lbl_mode_status.setText("🔒 文字區唯讀保護")
            self.capture_server.resume_asr()
            self._render_transcript()
            self.status_bar.showMessage("已恢復即時轉錄（文字區已重新鎖定為唯讀保護）", 2500)
        else:
            # 暫停錄音：開放手動編輯
            self.current_interim = ""
            self._render_transcript()
            self.editor.setReadOnly(False)
            self.btn_toggle_record.setText("▶️ 繼續轉錄")
            self.lbl_mode_status.setText("✏️ 文字區已解鎖編輯")
            self.capture_server.pause_asr()
            self.status_bar.showMessage("已暫停轉錄（您現在可以自由編輯、刪改文字）", 2500)

    def _on_user_text_edited(self):
        """在暫停期間使用者手動編輯文字時更新字數"""
        if not self.is_recording:
            self._update_word_count()

    def _on_font_size_changed(self, size: int):
        """調整字級大小：立即全域更新文字區大小"""
        self.font_size = size
        font = self.editor.font()
        font.setPointSize(size)
        self.editor.setFont(font)
        self._render_transcript()

    def _clear_editor(self):
        reply = QMessageBox.question(
            self, "確認清空", "確定要清空目前的全部轉錄文字嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.final_paragraphs.clear()
            self.current_interim = ""
            self.editor.clear()
            self._render_transcript()

    def _copy_all_text(self):
        """一鍵複製全文"""
        text = "\n\n".join(self.final_paragraphs)
        if not text:
            text = self.editor.toPlainText()
        if text.strip():
            clipboard = QApplication.clipboard()
            clipboard.setText(text.strip())
            QMessageBox.information(self, "複製成功", "已成功將全部轉錄文字複製到剪貼簿！")
        else:
            QMessageBox.information(self, "提示", "目前沒有文字可供複製。")

    def _export_txt(self):
        """匯出 TXT 純文字檔"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "匯出轉錄文字檔", f"語音轉錄_{datetime.now():%Y%m%d_%H%M%S}.txt", "文字檔案 (*.txt)"
        )
        if file_path:
            try:
                content = "\n\n".join(self.final_paragraphs)
                if not content:
                    content = self.editor.toPlainText()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"=== 語音轉錄記錄 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n\n")
                    f.write(content)
                QMessageBox.information(self, "匯出成功", f"檔案已成功儲存至：\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "匯出失敗", f"儲存檔案時發生錯誤：{e}")

    def _open_glossary(self):
        dlg = GlossaryDialog(self)
        if dlg.exec():
            self.glossary = dlg.glossary
            self.status_bar.showMessage("詞彙替換表已更新", 2000)

    def _open_settings(self):
        dlg = SettingsDialog(self.audio_manager, self)
        dlg.settings_saved.connect(self._refresh_top_source_buttons)
        dlg.exec()

    def _open_typography(self):
        """開啟排版與字體色彩設定視窗"""
        dlg = TypographyDialog(self.current_theme, self)
        dlg.settings_updated.connect(self._on_typography_updated)
        dlg.exec()

    def _on_typography_updated(self, new_cfg: dict):
        """套用新的排版與色彩設定"""
        self.typography_cfg = new_cfg
        self.font_size = int(new_cfg.get("font_size", 24))
        
        # 自動切換為「自訂」主題並套用
        idx = self.combo_theme.findData("custom")
        if idx >= 0:
            self.combo_theme.setCurrentIndex(idx)
        else:
            self._apply_theme("custom")
            
        self._render_transcript()
        self.status_bar.showMessage("排版與色彩設定已更新並套用！", 2500)

    def _open_license(self):
        """開啟授權聲明與開發者資訊對話框"""
        dlg = LicenseDialog(self.current_theme, self)
        dlg.exec()

    def _on_theme_changed(self):
        theme_key = self.combo_theme.currentData()
        self._apply_theme(theme_key)

    def _apply_theme(self, theme_key: str):
        self.current_theme = theme_key
        qss = get_stylesheet(theme_key)
        self.setStyleSheet(qss)
        self._refresh_top_source_buttons()
        self._render_transcript()

    def _on_lang_changed(self):
        lang = self.combo_lang.currentData()
        self.capture_server.set_language(lang)
        self.status_bar.showMessage(f"已切換語音識別語言為：{self.combo_lang.currentText()}", 2500)

    def _update_word_count(self):
        all_text = " ".join(self.final_paragraphs) + " " + self.current_interim
        cnt = len(all_text.replace(" ", "").replace("\n", ""))
        self.lbl_word_count.setText(f"總字數: {cnt} 字")

    def _auto_save(self):
        """定期自動存檔 (若設定關閉後清除文本則不寫入磁碟)"""
        if self.typography_cfg.get("clear_on_exit", False):
            return
        try:
            os.makedirs(os.path.dirname(AUTOSAVE_FILE), exist_ok=True)
            text = "\n\n".join(self.final_paragraphs)
            if text.strip():
                with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
                    f.write(text)
        except Exception:
            pass

    def _restore_autosave(self):
        """載入上次未手動清空的轉錄文字 (若開啟關閉清除則啟動時清空)"""
        if self.typography_cfg.get("clear_on_exit", False):
            if os.path.isfile(AUTOSAVE_FILE):
                try:
                    os.remove(AUTOSAVE_FILE)
                except Exception:
                    pass
            return

        if os.path.isfile(AUTOSAVE_FILE):
            try:
                with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self.final_paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                        self._render_transcript()
            except Exception:
                pass

    def closeEvent(self, event):
        """關閉程式前彈窗確認、依設定存檔並清理背景程序"""
        has_text = bool(self.final_paragraphs or self.current_interim.strip() or self.editor.toPlainText().strip())
        
        # 若編輯區已有轉錄文字，彈窗提示確認避免誤關損失文字
        if has_text:
            reply = QMessageBox.question(
                self,
                "確認退出程式",
                "目前編輯區中已有即時轉錄文字，確定要關閉程式嗎？\n\n（若未儲存或複製，關閉後記錄將可能清除）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        if self.typography_cfg.get("clear_on_exit", False):
            if os.path.isfile(AUTOSAVE_FILE):
                try:
                    os.remove(AUTOSAVE_FILE)
                except Exception:
                    pass
        else:
            self._auto_save()
            
        self.capture_server.stop()
        event.accept()
