"""
授權聲明對話框 (License Dialog)
包含作者資訊、意見回饋聯絡信箱、第三方套件清單與公益免責聲明
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
from PyQt6.QtCore import Qt
from ui.theme import THEMES


class LicenseDialog(QDialog):
    """程式授權聲明與第三方套件致謝"""

    def __init__(self, theme_key: str = "night", parent=None):
        super().__init__(parent)
        self.setWindowTitle("授權聲明")
        self.resize(620, 560)
        self.theme_key = theme_key
        self._init_ui()

    def _init_ui(self):
        t = THEMES.get(self.theme_key, THEMES["night"])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        bg_color = t["bg_secondary"]
        text_color = t["text_primary"]
        accent_color = t["accent"]
        h2_color = t["text_editor"] if self.theme_key == "night" else t["accent"]

        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(
            f"font-size: 11pt; font-family: 'Microsoft JhengHei UI', '微軟正黑體', sans-serif; "
            f"background-color: {bg_color}; border: 1px solid {t['border']}; "
            f"border-radius: 8px; padding: 16px; color: {text_color}; line-height: 1.6;"
        )

        html = f"""
        <h2 style="color: {h2_color}; margin-bottom: 10px;">軟體授權與開發聲明</h2>
        <div style="background: rgba(255, 255, 255, 0.05); padding: 12px 14px; border-radius: 6px; border-left: 4px solid {accent_color}; margin-bottom: 14px;">
            <b>本程式由徐承佑獨立開發與維護，如有使用意見歡迎回饋 <a href="mailto:llm0968@gmail.com" style="color: {accent_color}; font-weight: bold; text-decoration: none;">llm0968@gmail.com</a></b>
        </div>

        <p style="font-size: 10.5pt; line-height: 1.6;">
            本程式專為聾人、聽障朋友及多音源即時轉錄輔助需求開發，秉持公益無償、輔助溝通之初衷提供使用。
        </p>

        <hr style="border: none; border-top: 1px solid {t['border']}; margin: 14px 0;" />

        <h3 style="color: {h2_color}; margin-bottom: 8px;">使用之第三方開源套件與技術</h3>
        <ul style="line-height: 1.7; margin-left: -15px; font-size: 10.5pt;">
            <li><b>PyQt6</b>（Riverbank Computing）—— 高效能 GUI 桌面框架（GPL v3）</li>
            <li><b>aiohttp</b> —— 非同步 HTTP 與 WebSocket 串流伺服端（Apache 2.0）</li>
            <li><b>comtypes</b> —— Windows Core Audio API 底層端點列舉（MIT License）</li>
            <li><b>pywin32</b> —— Windows 系統整合與 Win32 API 調用（PSF License）</li>
            <li><b>SoundVolumeView</b>（NirSoft）—— Windows 預設錄音端點快速切換工具（Freeware）</li>
            <li><b>Web Speech API</b> —— Microsoft Edge / Chromium 即時語音辨識雲端引擎</li>
        </ul>
        <p style="font-size: 9.5pt; color: #94a3b8; margin-top: 4px;">
            * 註：第三方開源專案作者未參與本程式開發，亦不代表其背書。相關商標與技術歸各原作者所有。
        </p>

        <hr style="border: none; border-top: 1px solid {t['border']}; margin: 14px 0;" />

        <h3 style="color: {h2_color}; margin-bottom: 8px;">公益非營利與免責聲明</h3>
        <div style="background: rgba(0,0,0,0.2); padding: 10px 14px; border-radius: 6px; border-left: 4px solid #64748b; line-height: 1.5; font-size: 10pt;">
            本程式為作者個人出於<b>公益無償、聾人／聽障輔助</b>用途開發與分享，全無商業營利行為。<br/>
            本程式依「現狀」（AS IS）提供，開發者對本程式之正確性、即時性、語音辨識率不作任何明示或暗示之擔保。
            因使用本程式所產生之任何直接、間接損害或辨識遺漏，開發者概不承擔任何法律與經濟責任。
        </div>
        """
        content.setHtml(html)
        layout.addWidget(content)

        btn_layout = QHBoxLayout()
        btn_close = QPushButton("關閉")
        btn_close.setFixedSize(120, 38)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"background-color: {t['btn_active']}; color: {t['btn_active_text']}; "
            f"font-size: 14px; font-weight: bold; border-radius: 6px;"
        )
        btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
