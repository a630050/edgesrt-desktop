"""
音源裝置與系統設定對話框 (Settings Dialog)
用於偵測 Windows 系統音訊輸入裝置，自訂別名與頂部切換按鈕顯示
"""

from typing import List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QCheckBox,
    QLineEdit, QLabel, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from audio_manager import AudioManager, AudioDeviceInfo


class SettingsDialog(QDialog):
    """音訊輸入端點與別名設定對話框"""
    settings_saved = pyqtSignal()

    def __init__(self, audio_manager: AudioManager, parent=None):
        super().__init__(parent)
        self.audio_manager = audio_manager
        self.setWindowTitle("⚙️ 音訊輸入源與快捷按鈕設定")
        self.resize(760, 500)
        self.device_items: List[AudioDeviceInfo] = []
        self._init_ui()
        self._refresh_devices()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        tip_label = QLabel(
            "💡 <b>音源別名設定說明：</b><br>"
            "系統已自動為辨識到的錄音端點預設三組標準別名（<b>💻 電腦聲音</b>、<b>📞 電話聲音</b>、<b>🎤 USB麥克風</b>）。<br>"
            "您可以自由修改名稱或勾選【頂部顯示】，儲存後主視窗頂部將立即生成對應的快速切換按鈕。"
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #94a3b8; margin-bottom: 10px; font-size: 14px; line-height: 1.5;")
        layout.addWidget(tip_label)

        # 裝置表格
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["頂部顯示", "自訂別名 (按鈕文字)", "Windows 實體裝置名稱", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 200)
        layout.addWidget(self.table)

        # 底部按鈕列
        btn_layout = QHBoxLayout()
        rescan_btn = QPushButton("🔄 重新掃描裝置")
        save_btn = QPushButton("💾 儲存設定並更新前台")
        cancel_btn = QPushButton("取消")

        rescan_btn.clicked.connect(self._refresh_devices)
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(rescan_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _refresh_devices(self):
        """重新掃描系統音訊輸入裝置並填入表格"""
        self.table.setRowCount(0)
        self.device_items = self.audio_manager.list_capture_devices()

        for row, dev in enumerate(self.device_items):
            self.table.insertRow(row)

            # 1. 頂部顯示核取方塊
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(dev.show_in_topbar)
            chk_layout.addWidget(chk)
            self.table.setCellWidget(row, 0, chk_widget)

            # 2. 自訂別名輸入框
            alias_edit = QLineEdit(dev.alias)
            alias_edit.setPlaceholderText("例如: 💻 電腦聲音 / 📞 電話聲音 / 🎤 USB麥克風 / 🔌 有線麥克風")
            self.table.setCellWidget(row, 1, alias_edit)

            # 3. 實體裝置全名與目前預設標記
            name_text = dev.name
            if dev.is_default:
                name_text = f"⭐ [目前預設] {dev.name}"
            item_name = QTableWidgetItem(name_text)
            item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_name)

            # 4. 測試切換按鈕
            test_btn = QPushButton("立即切換至此裝置")
            test_btn.clicked.connect(lambda _, d=dev: self._switch_and_update(d.id))
            self.table.setCellWidget(row, 3, test_btn)

    def _switch_and_update(self, dev_id: str):
        """測試立即切換裝置"""
        ok = self.audio_manager.set_default_device(dev_id)
        if ok:
            QMessageBox.information(self, "切換成功", "已成功將 Windows 預設錄音端點切換至所選裝置！")
            self._refresh_devices()
        else:
            QMessageBox.warning(self, "切換失敗", "切換音訊端點失敗，請確認裝置是否已正確連接。")

    def _save_and_close(self):
        """儲存表格中編輯後的別名與顯示設定"""
        updated_list = []
        for row in range(self.table.rowCount()):
            if row >= len(self.device_items):
                break
            dev = self.device_items[row]

            chk_widget = self.table.cellWidget(row, 0)
            show_in_topbar = True
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk:
                    show_in_topbar = chk.isChecked()

            alias_edit = self.table.cellWidget(row, 1)
            alias = alias_edit.text().strip() if alias_edit else dev.name
            if not alias:
                alias = dev.name

            updated_list.append(AudioDeviceInfo(
                id=dev.id,
                name=dev.name,
                alias=alias,
                show_in_topbar=show_in_topbar,
                is_default=dev.is_default
            ))

        self.audio_manager.save_configs(updated_list)
        self.settings_saved.emit()
        self.accept()
