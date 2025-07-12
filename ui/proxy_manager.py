### File: /ui/proxy_manager.py

import os
import shutil
import csv
import socket
import socks
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QTableWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QTableWidgetItem, QFileDialog, QMessageBox, QInputDialog, QComboBox, QProgressBar,
    QLineEdit, QHeaderView, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from engine.sender import test_proxy

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'proxies')

class ProxyTestWorker(QThread):
    result = pyqtSignal(str, int, bool)
    finished = pyqtSignal(str)

    def __init__(self, list_name, proxies, proxy_type, smtp_host, smtp_port, max_workers=10):
        super().__init__()
        self.list_name = list_name
        self.proxies = proxies
        self.proxy_type = proxy_type
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.max_workers = max_workers

    def run(self):
        futures = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for idx, proxy in enumerate(self.proxies):
                futures.append((idx, executor.submit(self.test_proxy, proxy)))

            for idx, future in futures:
                try:
                    success = future.result()
                    self.result.emit(self.list_name, idx, success)
                except Exception:
                    self.result.emit(self.list_name, idx, False)

        self.finished.emit(self.list_name)

    def test_proxy(self, proxy_str, timeout=5):
        parts = proxy_str.split(':')
        if len(parts) == 2:
            ip, port = parts
            user = pwd = None
        elif len(parts) == 4:
            ip, port, user, pwd = parts
        else:
            return False

        try:
            s = socks.socksocket()
            s.set_proxy(
                proxy_type=socks.SOCKS5 if self.proxy_type.lower() == "socks5" else socks.SOCKS4,
                addr=ip,
                port=int(port),
                username=user,
                password=pwd
            )
            s.settimeout(timeout)
            s.connect((self.smtp_host, int(self.smtp_port)))
            s.close()
            return True
        except Exception:
            return False

class ProxyManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.workers = {}
        self.current_list = None
        self._build_ui()
        self._refresh_lists()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Proxy Lists</b>"))
        self.list_widget = QListWidget()
        self.list_widget.currentTextChanged.connect(self._load_list)
        left_layout.addWidget(self.list_widget)

        list_buttons = QHBoxLayout()
        btn_new = QPushButton("＋ New List")
        btn_new.clicked.connect(self._new_list)
        btn_del = QPushButton("🗑️ Delete List")
        btn_del.clicked.connect(self._delete_list)
        list_buttons.addWidget(btn_new)
        list_buttons.addWidget(btn_del)
        left_layout.addLayout(list_buttons)

        right_layout = QVBoxLayout()

        top_controls = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter proxies...")
        self.filter_input.textChanged.connect(self._filter_table)
        top_controls.addWidget(QLabel("Filter:"))
        top_controls.addWidget(self.filter_input)

        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["SOCKS4", "SOCKS5"])
        top_controls.addWidget(QLabel("Proxy Type:"))
        top_controls.addWidget(self.proxy_type_combo)

        self.smtp_host_input = QLineEdit()
        self.smtp_host_input.setPlaceholderText("SMTP Host")
        top_controls.addWidget(QLabel("SMTP Host:"))
        top_controls.addWidget(self.smtp_host_input)

        self.smtp_port_input = QLineEdit()
        self.smtp_port_input.setPlaceholderText("Port")
        top_controls.addWidget(QLabel("Port:"))
        top_controls.addWidget(self.smtp_port_input)
        self.max_threads_input = QSpinBox()
        self.max_threads_input.setRange(1, 500)
        self.max_threads_input.setValue(50)
        top_controls.addWidget(QLabel("Max Threads:"))
        top_controls.addWidget(self.max_threads_input)

        right_layout.addLayout(top_controls)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Host/IP", "Port", "Username", "Password", "Location", "SMTP Host", "Result", "Imported", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.table)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        right_layout.addWidget(self.progress)

        bottom_buttons = QHBoxLayout()
        btn_import = QPushButton("⬆️ Import")
        btn_import.clicked.connect(self._import)
        btn_test = QPushButton("🔎 Test All")
        btn_test.clicked.connect(self._test_all)
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._save)
        btn_remove_dead = QPushButton("🗑️ Remove Dead")
        btn_remove_dead.clicked.connect(self._remove_dead)
        bottom_buttons.addWidget(btn_import)
        bottom_buttons.addWidget(btn_test)
        bottom_buttons.addWidget(btn_save)
        bottom_buttons.addWidget(btn_remove_dead)
        right_layout.addLayout(bottom_buttons)

        layout.addLayout(left_layout, 1)
        layout.addLayout(right_layout, 3)

    def _refresh_lists(self):
        self.list_widget.clear()
        if os.path.isdir(DATA_DIR):
            for name in sorted(os.listdir(DATA_DIR)):
                if os.path.isdir(os.path.join(DATA_DIR, name)):
                    self.list_widget.addItem(name)

    def _new_list(self):
        name, ok = QInputDialog.getText(self, "New List", "Enter list name:")
        if ok and name.strip():
            path = os.path.join(DATA_DIR, name.strip())
            if not os.path.exists(path):
                os.makedirs(path)
                self._refresh_lists()

    def _delete_list(self):
        item = self.list_widget.currentItem()
        if item:
            name = item.text()
            path = os.path.join(DATA_DIR, name)
            if os.path.isdir(path):
                shutil.rmtree(path)
                self._refresh_lists()
                self.table.setRowCount(0)

    def _import(self):
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Select a list first.")
            return
        src, _ = QFileDialog.getOpenFileName(self, "Import Proxies", "", "Text Files (*.txt)")
        if src:
            with open(src, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for line in lines:
                parts = line.split(':')
                if 2 <= len(parts) <= 4:
                    self._add_row(parts, now)
            self._remove_duplicates()

    def _add_row(self, parts, now):
        row = self.table.rowCount()
        self.table.insertRow(row)
        ip, port, user, pwd = (parts + ["", ""])[:4]
        for col, value in enumerate([ip, port, user, pwd, "", "", "Pending", now, now]):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, col, item)

    def _test_all(self):
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Select a list first.")
            return
        proxies = []
        for r in range(self.table.rowCount()):
            ip = self.table.item(r, 0).text()
            port = self.table.item(r, 1).text()
            user = self.table.item(r, 2).text()
            pwd = self.table.item(r, 3).text()
            proxy = f"{ip}:{port}" if not user else f"{ip}:{port}:{user}:{pwd}"
            proxies.append(proxy)

        proxy_type = self.proxy_type_combo.currentText().lower()
        smtp_host = self.smtp_host_input.text()
        smtp_port = self.smtp_port_input.text()

        max_threads = self.max_threads_input.value()
        worker = ProxyTestWorker(self.current_list, proxies, proxy_type, smtp_host, smtp_port, max_workers=max_threads)
        worker.result.connect(self._update_result)
        worker.finished.connect(self._testing_finished)
        self.workers[self.current_list] = worker
        self.progress.setRange(0, len(proxies))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        worker.start()

    def _update_result(self, list_name, idx, success):
        if self.current_list != list_name:
            return
        result = "✅ Live" if success else "❌ Dead"
        self.table.item(idx, 6).setText(result)
        self.progress.setValue(self.progress.value() + 1)

    def _testing_finished(self, list_name):
        if self.current_list == list_name:
            self.progress.setVisible(False)
        del self.workers[list_name]

    def _save(self):
        if not self.current_list:
            return
        path = os.path.join(DATA_DIR, self.current_list, "proxies.csv")
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for r in range(self.table.rowCount()):
                row_data = [self.table.item(r, c).text() for c in range(self.table.columnCount())]
                writer.writerow(row_data)

    def _remove_dead(self):
        rows_to_remove = []
        for r in range(self.table.rowCount()):
            result = self.table.item(r, 6).text()
            if "Dead" in result:
                rows_to_remove.append(r)
        for r in reversed(rows_to_remove):
            self.table.removeRow(r)

    def _remove_duplicates(self):
        seen = set()
        rows_to_remove = []
        for r in range(self.table.rowCount()):
            proxy = self.table.item(r, 0).text(), self.table.item(r, 1).text()
            if proxy in seen:
                rows_to_remove.append(r)
            else:
                seen.add(proxy)
        for r in reversed(rows_to_remove):
            self.table.removeRow(r)

    def _load_list(self, list_name):
        if not list_name:
            return
        self.current_list = list_name
        path = os.path.join(DATA_DIR, list_name, "proxies.csv")
        self.table.setRowCount(0)
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    row_idx = self.table.rowCount()
                    self.table.insertRow(row_idx)
                    for col_idx, value in enumerate(row):
                        item = QTableWidgetItem(value)
                        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled)
                        self.table.setItem(row_idx, col_idx, item)

    def _filter_table(self, text):
        text = text.lower()
        for r in range(self.table.rowCount()):
            proxy = self.table.item(r, 0).text()
            self.table.setRowHidden(r, text not in proxy.lower())

    def closeEvent(self, event):
        for worker in self.workers.values():
            worker.terminate()
            worker.wait()
        self.workers.clear()
        event.accept()