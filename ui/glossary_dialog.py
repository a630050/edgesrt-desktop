"""
詞彙替換表對話框 (Glossary Dialog)
支援自訂辨識錯字校正與專業術語自動替換
"""

import os
import json
from typing import Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

import sys

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_appdata_dir = os.environ.get("EDGESRT_APPDATA_DIR", os.path.join(APP_DIR, "_appdata"))
GLOSSARY_FILE = os.path.join(_appdata_dir, "glossary.json")


def load_glossary() -> Dict[str, str]:
    """讀取詞彙表"""
    if os.path.isfile(GLOSSARY_FILE):
        try:
            with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_glossary(data: Dict[str, str]):
    """儲存詞彙表"""
    try:
        os.makedirs(os.path.dirname(GLOSSARY_FILE), exist_ok=True)
        with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def apply_glossary(text: str, glossary: Dict[str, str]) -> str:
    """批量套用詞彙替換"""
    if not glossary or not text:
        return text
    for src in sorted(glossary.keys(), key=len, reverse=True):
        if src in text:
            text = text.replace(src, glossary[src])
    return text


class GlossaryDialog(QDialog):
    """詞彙管理對話框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 自訂詞彙替換表")
        self.resize(520, 420)
        self.glossary = load_glossary()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["原始錯誤詞 / 待替換", "正確替換目標"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # 填入現有資料
        for src, dst in self.glossary.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(src))
            self.table.setItem(row, 1, QTableWidgetItem(dst))

        # 按鈕列
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 新增一行")
        del_btn = QPushButton("🗑️ 刪除選取")
        save_btn = QPushButton("💾 儲存並套用")
        close_btn = QPushButton("取消")

        add_btn.clicked.connect(self._add_row)
        del_btn.clicked.connect(self._delete_row)
        save_btn.clicked.connect(self._save_and_close)
        close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))

    def _delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def _save_and_close(self):
        new_dict = {}
        for r in range(self.table.rowCount()):
            src_item = self.table.item(r, 0)
            dst_item = self.table.item(r, 1)
            src = src_item.text().strip() if src_item else ""
            dst = dst_item.text().strip() if dst_item else ""
            if src:
                new_dict[src] = dst

        self.glossary = new_dict
        save_glossary(new_dict)
        self.accept()
