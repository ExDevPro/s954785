# Enhanced Proxy Manager with Original Functionality Plus Improvements

import os
import shutil
import csv
import socket
import socks
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import re

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QTableWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QTableWidgetItem, QFileDialog, QMessageBox, QInputDialog, QComboBox, QProgressBar,
    QLineEdit, QHeaderView, QSpinBox, QFrame, QSplitter, QScrollArea, QSizePolicy,
    QDialog, QDialogButtonBox, QTextEdit, QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

try:
    from engine.sender import test_proxy
except ImportError:
    # Fallback proxy testing function
    def test_proxy(proxy_str, proxy_type, smtp_host, smtp_port, timeout=5):
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
                proxy_type=socks.SOCKS5 if proxy_type.lower() == "socks5" else socks.SOCKS4,
                addr=ip,
                port=int(port),
                username=user,
                password=pwd
            )
            s.settimeout(timeout)
            s.connect((smtp_host, int(smtp_port)))
            s.close()
            return True
        except Exception:
            return False

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'proxies')

class CreateProxyListDialog(QDialog):
    """Professional dialog for creating new proxy lists with descriptions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Proxy List")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout(self)
        
        # List name
        layout.addWidget(QLabel("List Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter proxy list name...")
        layout.addWidget(self.name_edit)
        
        # Description
        layout.addWidget(QLabel("Description (Optional):"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Enter description for this proxy list...")
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.name_edit.textChanged.connect(self._validate_input)
        self._validate_input()
    
    def _validate_input(self):
        name = self.name_edit.text().strip()
        valid = bool(name and re.match(r'^[a-zA-Z0-9_\-\s]+$', name))
        self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
    
    def get_list_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip()
        }

class ProxyTestWorker(QThread):
    """Background worker for proxy testing."""
    
    result = pyqtSignal(str, int, bool)
    finished = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, list_name, proxies, proxy_type, smtp_host, smtp_port, max_workers=10):
        super().__init__()
        self.list_name = list_name
        self.proxies = proxies
        self.proxy_type = proxy_type
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.max_workers = max_workers

    def run(self):
        total = len(self.proxies)
        completed = 0
        
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
                
                completed += 1
                self.progress_updated.emit(completed, total)

        self.finished.emit(self.list_name)

    def test_proxy(self, proxy_str, timeout=5):
        """Test a single proxy."""
        return test_proxy(proxy_str, self.proxy_type, self.smtp_host, self.smtp_port, timeout)

class EnhancedProxyManager(QWidget):
    """Enhanced Proxy Manager with original functionality plus improvements."""
    
    counts_changed = pyqtSignal()
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.workers = {}
        self.current_list = None
        
        os.makedirs(DATA_DIR, exist_ok=True)
        
        self._setup_ui()
        self._load_lists()
        self._apply_styling()

    def _setup_ui(self):
        """Setup the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel - Lists
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Right panel - Proxy management
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Description panel
        desc_panel = self._create_description_panel()
        splitter.addWidget(desc_panel)
        
        splitter.setSizes([600, 200])
        main_layout.addWidget(splitter, 3)
    
    def _create_left_panel(self):
        """Create the left panel with list management."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMaximumWidth(350)
        panel.setMinimumWidth(250)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("🌐 Proxy Lists")
        header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("QLabel { background: #34495e; color: white; padding: 8px; border-radius: 4px; }")
        layout.addWidget(header)
        
        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search lists...")
        self.search_edit.textChanged.connect(self._filter_lists)
        layout.addWidget(self.search_edit)
        
        # Lists
        self.list_widget = QListWidget()
        self.list_widget.currentTextChanged.connect(self._load_list)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        layout.addWidget(self.list_widget)
        
        # Buttons
        buttons_layout = QVBoxLayout()
        
        btn_new = QPushButton("➕ New List")
        btn_new.clicked.connect(self._new_list)
        btn_new.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 8px; border-radius: 4px; }")
        buttons_layout.addWidget(btn_new)
        
        btn_del = QPushButton("🗑️ Delete List")
        btn_del.clicked.connect(self._delete_list)
        btn_del.setStyleSheet("QPushButton { background: #e74c3c; color: white; padding: 8px; border-radius: 4px; }")
        buttons_layout.addWidget(btn_del)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_right_panel(self):
        """Create the right panel with proxy table."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header_layout = QHBoxLayout()
        self.table_header = QLabel("📊 Proxy Configurations")
        self.table_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.table_header)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Control panel
        controls_layout = self._create_controls()
        layout.addLayout(controls_layout)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { color: #7f8c8d; font-style: italic; }")
        layout.addWidget(self.status_label)
        
        # Proxy table with original columns
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Host/IP", "Port", "Username", "Password", "Location", "SMTP Host", "Result", "Imported", "Updated"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        layout.addWidget(self.table)
        
        # Bottom buttons
        bottom_buttons = QHBoxLayout()
        
        btn_import = QPushButton("📥 Import")
        btn_import.clicked.connect(self._import)
        btn_import.setStyleSheet("QPushButton { background: #9b59b6; color: white; padding: 6px 12px; border-radius: 4px; }")
        bottom_buttons.addWidget(btn_import)
        
        btn_test = QPushButton("🔧 Test All")
        btn_test.clicked.connect(self._test_all)
        btn_test.setStyleSheet("QPushButton { background: #3498db; color: white; padding: 6px 12px; border-radius: 4px; }")
        bottom_buttons.addWidget(btn_test)
        
        btn_save = QPushButton("💾 Save")
        btn_save.clicked.connect(self._save)
        btn_save.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 6px 12px; border-radius: 4px; }")
        bottom_buttons.addWidget(btn_save)
        
        btn_export = QPushButton("📤 Export")
        btn_export.clicked.connect(self._export)
        btn_export.setStyleSheet("QPushButton { background: #f39c12; color: white; padding: 6px 12px; border-radius: 4px; }")
        bottom_buttons.addWidget(btn_export)
        
        bottom_buttons.addStretch()
        layout.addLayout(bottom_buttons)
        
        return panel
    
    def _create_controls(self):
        """Create the control panel."""
        controls_layout = QVBoxLayout()
        
        # First row
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
        
        controls_layout.addLayout(top_controls)
        
        # Second row
        bottom_controls = QHBoxLayout()
        
        self.smtp_host_input = QLineEdit()
        self.smtp_host_input.setPlaceholderText("SMTP Host (e.g., smtp.gmail.com)")
        bottom_controls.addWidget(QLabel("SMTP Host:"))
        bottom_controls.addWidget(self.smtp_host_input)
        
        self.smtp_port_input = QLineEdit()
        self.smtp_port_input.setPlaceholderText("Port (e.g., 587)")
        self.smtp_port_input.setText("587")  # Default
        bottom_controls.addWidget(QLabel("Port:"))
        bottom_controls.addWidget(self.smtp_port_input)
        
        self.max_threads_input = QSpinBox()
        self.max_threads_input.setRange(1, 500)
        self.max_threads_input.setValue(50)
        bottom_controls.addWidget(QLabel("Max Threads:"))
        bottom_controls.addWidget(self.max_threads_input)
        
        controls_layout.addLayout(bottom_controls)
        
        return controls_layout
    
    def _create_description_panel(self):
        """Create the description panel."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("📝 Description")
        header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("QLabel { background: #95a5a6; color: white; padding: 6px; border-radius: 4px; }")
        layout.addWidget(header)
        
        # Scrollable description area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.description_label = QLabel("Select a list to view its description.")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.description_label.setStyleSheet("QLabel { padding: 10px; background: white; }")
        
        scroll_area.setWidget(self.description_label)
        layout.addWidget(scroll_area)
        
        # Edit button
        self.btn_edit_desc = QPushButton("✏️ Edit Description")
        self.btn_edit_desc.clicked.connect(self._edit_description)
        self.btn_edit_desc.setEnabled(False)
        layout.addWidget(self.btn_edit_desc)
        
        return panel
    
    def _apply_styling(self):
        """Apply professional styling."""
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background: #ecf0f1;
            }
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background: #34495e;
                color: white;
            }
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background: white;
                gridline-color: #ecf0f1;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 2px solid #34495e;
            }
            QPushButton {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px 12px;
                background: #ecf0f1;
            }
            QPushButton:hover {
                background: #d5dbdb;
            }
            QPushButton:pressed {
                background: #bdc3c7;
            }
        """)
    
    # ========== List Management Methods ==========
    
    def _load_lists(self):
        """Load all available proxy lists."""
        self.list_widget.clear()
        
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                self.list_widget.addItem(item)
        
        self.counts_changed.emit()
    
    def _filter_lists(self):
        """Filter lists based on search text."""
        search_text = self.search_edit.text().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def _new_list(self):
        """Create a new proxy list."""
        dialog = CreateProxyListDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_list_data()
            list_name = data['name']
            description = data['description']
            
            # Check if list already exists
            list_dir = os.path.join(DATA_DIR, list_name)
            if os.path.exists(list_dir):
                QMessageBox.warning(self, "List Exists", f"A proxy list named '{list_name}' already exists.")
                return
            
            try:
                # Create list directory
                os.makedirs(list_dir, exist_ok=True)
                
                # Create proxies.csv file with headers
                csv_file = os.path.join(list_dir, "proxies.csv")
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Host/IP", "Port", "Username", "Password", "Location", "SMTP Host", "Result", "Imported", "Updated"])
                
                # Save description
                if description:
                    desc_file = os.path.join(list_dir, "description.txt")
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(description)
                
                self._load_lists()
                
                # Select the new list
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == list_name:
                        self.list_widget.setCurrentRow(i)
                        self._load_list(list_name)
                        break
                
                QMessageBox.information(self, "Success", f"Proxy list '{list_name}' created successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create list: {str(e)}")
    
    def _delete_list(self):
        """Delete the selected proxy list."""
        if not self.current_list:
            QMessageBox.warning(self, "No Selection", "Please select a list to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the proxy list '{self.current_list}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                list_dir = os.path.join(DATA_DIR, self.current_list)
                shutil.rmtree(list_dir)
                
                self._load_lists()
                self._clear_table()
                
                QMessageBox.information(self, "Success", f"Proxy list '{self.current_list}' deleted successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete list: {str(e)}")
    
    def _load_list(self, list_name):
        """Load the selected proxy list."""
        if not list_name:
            return
        
        self.current_list = list_name
        csv_file = os.path.join(DATA_DIR, list_name, "proxies.csv")
        
        self.table.setRowCount(0)
        
        try:
            if os.path.exists(csv_file):
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])  # Skip header row
                    
                    for row_data in reader:
                        if not any(row_data):  # Skip empty rows
                            continue
                        
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        
                        # Pad row to match table columns
                        padded_row = row_data + [""] * (9 - len(row_data))
                        padded_row = padded_row[:9]  # Take only first 9 columns
                        
                        for col, value in enumerate(padded_row):
                            item = QTableWidgetItem(str(value))
                            self.table.setItem(row, col, item)
            
            # Load description
            self._load_description(list_name)
            
            # Update UI
            self.table_header.setText(f"📊 {list_name} - Proxy Configurations")
            self.btn_edit_desc.setEnabled(True)
            self.status_label.setText(f"Loaded {self.table.rowCount()} proxies")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load proxy list: {str(e)}")
    
    def _load_description(self, list_name):
        """Load and display list description."""
        desc_file = os.path.join(DATA_DIR, list_name, "description.txt")
        
        if os.path.exists(desc_file):
            try:
                with open(desc_file, 'r', encoding='utf-8') as f:
                    description = f.read().strip()
                
                if description:
                    self.description_label.setText(description)
                else:
                    self.description_label.setText("No description available.")
            except Exception as e:
                self.description_label.setText(f"Error loading description: {str(e)}")
        else:
            self.description_label.setText("No description available.")
    
    def _edit_description(self):
        """Edit the description of the current list."""
        if not self.current_list:
            return
        
        desc_file = os.path.join(DATA_DIR, self.current_list, "description.txt")
        current_desc = ""
        
        if os.path.exists(desc_file):
            try:
                with open(desc_file, 'r', encoding='utf-8') as f:
                    current_desc = f.read().strip()
            except:
                pass
        
        new_desc, ok = QInputDialog.getMultiLineText(
            self, "Edit Description", 
            f"Description for '{self.current_list}':",
            current_desc
        )
        
        if ok:
            try:
                if new_desc.strip():
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(new_desc.strip())
                else:
                    # Remove description file if empty
                    if os.path.exists(desc_file):
                        os.remove(desc_file)
                
                self._load_description(self.current_list)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save description: {str(e)}")
    
    def _clear_table(self):
        """Clear the proxy table."""
        self.table.setRowCount(0)
        self.current_list = None
        self.table_header.setText("📊 Proxy Configurations")
        self.description_label.setText("Select a list to view its description.")
        self.btn_edit_desc.setEnabled(False)
        self.status_label.setText("Ready")
    
    # ========== Proxy Management Methods ==========
    
    def _filter_table(self):
        """Filter table rows based on search text."""
        search_text = self.filter_input.text().lower()
        
        for row in range(self.table.rowCount()):
            visible = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    visible = True
                    break
            self.table.setRowHidden(row, not visible)
    
    def _import(self):
        """Import proxies from a file."""
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Proxies", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                imported_count = 0
                
                if file_path.endswith('.csv'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        headers = next(reader, [])  # Skip header
                        
                        for row_data in reader:
                            if not any(row_data):
                                continue
                            
                            self._add_proxy_to_table(row_data)
                            imported_count += 1
                
                else:  # Text file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Assume format: ip:port or ip:port:user:pass
                                parts = line.split(':')
                                if len(parts) >= 2:
                                    row_data = parts + [""] * (9 - len(parts))
                                    self._add_proxy_to_table(row_data[:9])
                                    imported_count += 1
                
                self._save()
                self.status_label.setText(f"Imported {imported_count} proxies")
                QMessageBox.information(self, "Import Complete", f"Successfully imported {imported_count} proxies.")
                
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import proxies: {str(e)}")
    
    def _add_proxy_to_table(self, row_data):
        """Add a proxy to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Pad row to match table columns
        padded_row = list(row_data) + [""] * (9 - len(row_data))
        padded_row = padded_row[:9]
        
        # Set default values for some columns
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not padded_row[6]:  # Result column
            padded_row[6] = "Untested"
        if not padded_row[7]:  # Imported column
            padded_row[7] = now_str
        if not padded_row[8]:  # Updated column
            padded_row[8] = now_str
        
        for col, value in enumerate(padded_row):
            item = QTableWidgetItem(str(value))
            self.table.setItem(row, col, item)
    
    def _test_all(self):
        """Test all proxies in the current list."""
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Proxies", "No proxies to test.")
            return
        
        smtp_host = self.smtp_host_input.text().strip()
        smtp_port = self.smtp_port_input.text().strip()
        
        if not smtp_host or not smtp_port:
            QMessageBox.warning(self, "Missing SMTP Info", "Please enter SMTP host and port.")
            return
        
        try:
            smtp_port = int(smtp_port)
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number.")
            return
        
        # Collect proxy data
        proxies = []
        for row in range(self.table.rowCount()):
            host_item = self.table.item(row, 0)
            port_item = self.table.item(row, 1)
            user_item = self.table.item(row, 2)
            pass_item = self.table.item(row, 3)
            
            if host_item and port_item:
                host = host_item.text().strip()
                port = port_item.text().strip()
                user = user_item.text().strip() if user_item else ""
                password = pass_item.text().strip() if pass_item else ""
                
                if user and password:
                    proxy_str = f"{host}:{port}:{user}:{password}"
                else:
                    proxy_str = f"{host}:{port}"
                
                proxies.append(proxy_str)
            else:
                proxies.append("")  # Empty placeholder
        
        if not any(proxies):
            QMessageBox.warning(self, "No Valid Proxies", "No valid proxy configurations found.")
            return
        
        # Start testing
        self.progress.setVisible(True)
        self.progress.setMaximum(len(proxies))
        self.progress.setValue(0)
        self.status_label.setText("Testing proxies...")
        
        proxy_type = self.proxy_type_combo.currentText().lower()
        max_workers = self.max_threads_input.value()
        
        # Stop any existing worker
        if self.current_list in self.workers:
            self.workers[self.current_list].terminate()
            self.workers[self.current_list].wait()
        
        # Create and start new worker
        worker = ProxyTestWorker(self.current_list, proxies, proxy_type, smtp_host, smtp_port, max_workers)
        worker.result.connect(self._on_test_result)
        worker.finished.connect(self._on_test_finished)
        worker.progress_updated.connect(self._on_test_progress)
        worker.start()
        
        self.workers[self.current_list] = worker
    
    def _on_test_result(self, list_name, row_index, success):
        """Handle individual test result."""
        if list_name == self.current_list and row_index < self.table.rowCount():
            # Update result column
            result = "✅ Working" if success else "❌ Failed"
            self.table.setItem(row_index, 6, QTableWidgetItem(result))
            
            # Update SMTP host column
            smtp_host = self.smtp_host_input.text().strip()
            self.table.setItem(row_index, 5, QTableWidgetItem(smtp_host))
            
            # Update timestamp
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row_index, 8, QTableWidgetItem(now_str))
    
    def _on_test_progress(self, completed, total):
        """Handle test progress update."""
        self.progress.setValue(completed)
        self.status_label.setText(f"Testing proxies... {completed}/{total}")
    
    def _on_test_finished(self, list_name):
        """Handle test completion."""
        if list_name == self.current_list:
            self.progress.setVisible(False)
            self.status_label.setText("Proxy testing completed")
            self._save()  # Auto-save after testing
    
    def _save(self):
        """Save the current proxy list."""
        if not self.current_list:
            return
        
        csv_file = os.path.join(DATA_DIR, self.current_list, "proxies.csv")
        
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
                writer.writerow(headers)
                
                # Write data
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            
            self.status_label.setText("Proxy list saved")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save proxy list: {str(e)}")
    
    def _export(self):
        """Export the current proxy list."""
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No proxies to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Proxies", f"{self.current_list}_export.csv", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.txt'):
                    # Export as simple text format
                    with open(file_path, 'w', encoding='utf-8') as f:
                        for row in range(self.table.rowCount()):
                            host = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
                            port = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                            user = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
                            password = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                            
                            if host and port:
                                if user and password:
                                    f.write(f"{host}:{port}:{user}:{password}\n")
                                else:
                                    f.write(f"{host}:{port}\n")
                else:
                    # Export as CSV
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        
                        # Write headers
                        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
                        writer.writerow(headers)
                        
                        # Write data
                        for row in range(self.table.rowCount()):
                            row_data = []
                            for col in range(self.table.columnCount()):
                                item = self.table.item(row, col)
                                row_data.append(item.text() if item else "")
                            writer.writerow(row_data)
                
                QMessageBox.information(self, "Export Complete", f"Proxies exported to '{file_path}'")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export proxies: {str(e)}")
    
    # ========== Context Menu Methods ==========
    
    def _show_list_context_menu(self, position):
        """Show context menu for lists."""
        item = self.list_widget.itemAt(position)
        
        menu = QMenu()
        
        if item:
            menu.addAction("📂 Open", lambda: self._load_list(item.text()))
            menu.addSeparator()
            menu.addAction("✏️ Edit Description", self._edit_description)
            menu.addSeparator()
            menu.addAction("🗑️ Delete", self._delete_list)
        
        menu.addSeparator()
        menu.addAction("➕ New List", self._new_list)
        menu.addAction("🔄 Refresh", self._load_lists)
        
        menu.exec(self.list_widget.mapToGlobal(position))
    
    def _show_table_context_menu(self, position):
        """Show context menu for the table."""
        menu = QMenu()
        
        menu.addAction("📥 Import Proxies", self._import)
        menu.addAction("🔧 Test All", self._test_all)
        menu.addSeparator()
        menu.addAction("💾 Save", self._save)
        menu.addAction("📤 Export", self._export)
        
        menu.exec(self.table.mapToGlobal(position))
    
    # ========== Public Methods ==========
    
    def get_list_count(self):
        """Get the number of proxy lists."""
        return self.list_widget.count()
    
    def refresh_lists(self):
        """Refresh the lists display."""
        self._load_lists()

# Maintain backward compatibility
ProxyManager = EnhancedProxyManager