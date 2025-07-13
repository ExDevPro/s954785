# ui/proxy_manager_integrated.py
"""
Integrated proxy manager using new foundation architecture.

This module provides the GUI for proxy management using:
- New data models (core.data.models)
- New file handling (core.data.file_handler) 
- New worker system (workers.base_worker)
- New validation and error handling
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTableWidget,
    QHeaderView, QLineEdit, QProgressBar, QMessageBox, QFileDialog, QInputDialog,
    QApplication, QTableWidgetItem, QMenu, QAbstractItemView, QStyle, QDialog,
    QComboBox, QDialogButtonBox, QGridLayout, QSpinBox, QFormLayout
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import new foundation components
from core.data.file_handler import FileHandler
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.base_worker import BaseWorker, WorkerProgress, WorkerStatus

logger = get_module_logger(__name__)


class ProxyData:
    """Data class for proxy information."""
    
    def __init__(self, host: str, port: int, username: str = "", password: str = "", 
                 proxy_type: str = "HTTP", description: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.proxy_type = proxy_type  # HTTP, HTTPS, SOCKS4, SOCKS5
        self.description = description
        self.status = "Untested"  # Untested, Working, Failed
        self.created_date = datetime.now()
        self.last_tested = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'proxy_type': self.proxy_type,
            'description': self.description,
            'status': self.status,
            'created_date': self.created_date.isoformat(),
            'last_tested': self.last_tested.isoformat() if self.last_tested else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProxyData':
        """Create from dictionary."""
        proxy = cls(
            host=data['host'],
            port=data['port'],
            username=data.get('username', ''),
            password=data.get('password', ''),
            proxy_type=data.get('proxy_type', 'HTTP'),
            description=data.get('description', '')
        )
        proxy.status = data.get('status', 'Untested')
        if 'created_date' in data:
            proxy.created_date = datetime.fromisoformat(data['created_date'])
        if data.get('last_tested'):
            proxy.last_tested = datetime.fromisoformat(data['last_tested'])
        return proxy
    
    def get_proxy_url(self) -> str:
        """Get proxy URL for use with requests."""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        
        protocol = self.proxy_type.lower()
        if protocol in ['socks4', 'socks5']:
            protocol = f"socks{protocol[-1]}"
        elif protocol in ['http', 'https']:
            protocol = 'http'
        
        return f"{protocol}://{auth}{self.host}:{self.port}"


class ProxyWorker(QObject, BaseWorker):
    """Worker for proxy operations using new foundation."""
    
    proxies_loaded = pyqtSignal(list)  # List[ProxyData]
    proxies_saved = pyqtSignal(bool, str)  # success, message
    proxies_imported = pyqtSignal(list, int)  # proxies, total_count
    proxy_tested = pyqtSignal(int, bool, str)  # index, success, message
    progress_updated = pyqtSignal(object)  # WorkerProgress
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__(name="proxy_worker")
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Connect BaseWorker progress to PyQt signals
        self.add_progress_callback(self._emit_progress)
        self.add_completion_callback(self._emit_completion)
        
        # Operation parameters
        self.operation = None
        self.file_path = None
        self.proxies_data = None
        self.test_proxy_index = None
    
    def _emit_progress(self, progress: WorkerProgress):
        """Emit progress signal."""
        self.progress_updated.emit(progress)
    
    def _emit_completion(self, result: Any, error: Optional[Exception]):
        """Emit completion signals."""
        if error:
            self.error_occurred.emit(str(error))
        else:
            # Emit operation-specific signals
            if self.operation == "load":
                self.proxies_loaded.emit(result or [])
            elif self.operation == "save":
                self.proxies_saved.emit(True, "Proxies saved successfully")
            elif self.operation == "import":
                self.proxies_imported.emit(result or [], len(result) if result else 0)
            elif self.operation == "test":
                success, message = result if result else (False, "Test failed")
                self.proxy_tested.emit(self.test_proxy_index, success, message)
        
        self.finished.emit()
    
    def load_proxies(self, file_path: str):
        """Load proxies from file."""
        self.operation = "load"
        self.file_path = file_path
        self.start()
    
    def save_proxies(self, file_path: str, proxies: List[ProxyData]):
        """Save proxies to file."""
        self.operation = "save"
        self.file_path = file_path
        self.proxies_data = proxies
        self.start()
    
    def import_proxies(self, file_path: str):
        """Import proxies from Excel/CSV file."""
        self.operation = "import"
        self.file_path = file_path
        self.start()
    
    def test_proxy(self, proxy: ProxyData, index: int):
        """Test a proxy connection."""
        self.operation = "test"
        self.proxies_data = [proxy]
        self.test_proxy_index = index
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_proxies()
            elif self.operation == "save":
                return self._save_proxies()
            elif self.operation == "import":
                return self._import_proxies()
            elif self.operation == "test":
                return self._test_proxy()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in proxy worker operation: {self.operation}")
            raise
    
    def _load_proxies(self) -> List[ProxyData]:
        """Load proxies from file."""
        logger.info("Loading proxies from file", file_path=self.file_path)
        
        self._update_progress(0, 100, "Loading proxies file...")
        
        try:
            if not os.path.exists(self.file_path):
                return []
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            proxies = []
            proxy_list = data.get('proxies', [])
            
            for idx, proxy_data in enumerate(proxy_list):
                if self.is_cancelled():
                    break
                
                progress = int((idx / len(proxy_list)) * 90) + 10
                self._update_progress(idx, len(proxy_list), f"Processing proxy {idx + 1}")
                
                try:
                    proxy = ProxyData.from_dict(proxy_data)
                    proxies.append(proxy)
                except Exception as e:
                    logger.warning("Failed to load proxy data", error=str(e))
                    continue
            
            self._update_progress(100, 100, f"Loaded {len(proxies)} proxies")
            logger.info("Proxies loaded successfully", count=len(proxies))
            return proxies
            
        except Exception as e:
            error_msg = f"Failed to load proxies: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _save_proxies(self) -> bool:
        """Save proxies to file."""
        logger.info("Saving proxies to file", file_path=self.file_path, count=len(self.proxies_data))
        
        self._update_progress(0, 100, "Saving proxies...")
        
        try:
            data = {
                'proxies': [proxy.to_dict() for proxy in self.proxies_data],
                'count': len(self.proxies_data),
                'created': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self._update_progress(100, 100, "Proxies saved successfully")
            logger.info("Proxies saved successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save proxies: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _import_proxies(self) -> List[ProxyData]:
        """Import proxies from Excel/CSV file."""
        logger.info("Importing proxies from file", file_path=self.file_path)
        
        self._update_progress(0, 100, "Importing proxies...")
        
        try:
            data = self.file_handler.load_excel(self.file_path)
            if not data or len(data) < 2:
                logger.warning("No data found in proxies file")
                return []
            
            headers = data[0]
            rows = data[1:]
            
            # Find columns
            host_col = port_col = username_col = password_col = type_col = None
            
            for i, header in enumerate(headers):
                header_lower = str(header).lower()
                if 'host' in header_lower or 'ip' in header_lower:
                    host_col = i
                elif 'port' in header_lower:
                    port_col = i
                elif 'user' in header_lower or 'username' in header_lower:
                    username_col = i
                elif 'pass' in header_lower or 'password' in header_lower:
                    password_col = i
                elif 'type' in header_lower or 'protocol' in header_lower:
                    type_col = i
            
            if host_col is None or port_col is None:
                raise ValidationError("Host and Port columns not found in file")
            
            proxies = []
            
            for idx, row in enumerate(rows):
                if self.is_cancelled():
                    break
                
                progress = int((idx / len(rows)) * 90) + 10
                self._update_progress(idx, len(rows), f"Processing proxy {idx + 1} of {len(rows)}")
                
                try:
                    # Extract data safely
                    host = str(row[host_col]).strip() if host_col < len(row) else ""
                    port_str = str(row[port_col]).strip() if port_col < len(row) else "8080"
                    username = str(row[username_col]).strip() if username_col is not None and username_col < len(row) else ""
                    password = str(row[password_col]).strip() if password_col is not None and password_col < len(row) else ""
                    proxy_type = str(row[type_col]).strip() if type_col is not None and type_col < len(row) else "HTTP"
                    
                    if not host:
                        continue  # Skip rows without host
                    
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 8080  # Default port
                    
                    # Create proxy
                    proxy = ProxyData(
                        host=host,
                        port=port,
                        username=username,
                        password=password,
                        proxy_type=proxy_type.upper()
                    )
                    
                    proxies.append(proxy)
                    
                except Exception as e:
                    logger.warning("Failed to process proxy row", row=idx, error=str(e))
                    continue
            
            self._update_progress(100, 100, f"Imported {len(proxies)} proxies")
            logger.info("Proxies imported successfully", count=len(proxies))
            return proxies
            
        except Exception as e:
            error_msg = f"Failed to import proxies: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _test_proxy(self) -> tuple:
        """Test a proxy connection."""
        if not self.proxies_data:
            return False, "No proxy to test"
        
        proxy = self.proxies_data[0]
        logger.info("Testing proxy", host=proxy.host, port=proxy.port)
        
        self._update_progress(0, 100, "Testing proxy connection...")
        
        try:
            import requests
            
            # Test URL
            test_url = "http://httpbin.org/ip"
            
            # Configure proxy
            proxies = {
                'http': proxy.get_proxy_url(),
                'https': proxy.get_proxy_url()
            }
            
            self._update_progress(50, 100, "Connecting through proxy...")
            
            # Make test request with timeout
            response = requests.get(test_url, proxies=proxies, timeout=10)
            
            if response.status_code == 200:
                # Update proxy status
                proxy.status = "Working"
                proxy.last_tested = datetime.now()
                
                self._update_progress(100, 100, "Proxy test successful")
                logger.info("Proxy test successful", host=proxy.host, port=proxy.port)
                return True, "Proxy is working"
            else:
                proxy.status = "Failed"
                proxy.last_tested = datetime.now()
                
                message = f"HTTP {response.status_code}"
                logger.warning("Proxy test failed", host=proxy.host, port=proxy.port, status=response.status_code)
                return False, message
                
        except requests.exceptions.ProxyError as e:
            proxy.status = "Failed"
            proxy.last_tested = datetime.now()
            message = "Proxy connection failed"
            logger.warning("Proxy connection failed", host=proxy.host, port=proxy.port, error=str(e))
            return False, message
            
        except requests.exceptions.Timeout as e:
            proxy.status = "Failed"
            proxy.last_tested = datetime.now()
            message = "Connection timeout"
            logger.warning("Proxy test timeout", host=proxy.host, port=proxy.port)
            return False, message
            
        except Exception as e:
            proxy.status = "Failed"
            proxy.last_tested = datetime.now()
            message = f"Test error: {str(e)}"
            logger.error("Proxy test error", host=proxy.host, port=proxy.port, error=str(e))
            return False, message


class ProxyEditDialog(QDialog):
    """Dialog for editing/adding proxies."""
    
    def __init__(self, proxy: ProxyData = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Proxy" if proxy else "Add Proxy")
        self.setModal(True)
        self.resize(400, 350)
        
        self.proxy = proxy
        
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Host
        self.host_edit = QLineEdit()
        if proxy:
            self.host_edit.setText(proxy.host)
        form_layout.addRow("Host/IP:", self.host_edit)
        
        # Port
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(proxy.port if proxy else 8080)
        form_layout.addRow("Port:", self.port_spin)
        
        # Proxy Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["HTTP", "HTTPS", "SOCKS4", "SOCKS5"])
        if proxy:
            index = self.type_combo.findText(proxy.proxy_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        form_layout.addRow("Type:", self.type_combo)
        
        # Username
        self.username_edit = QLineEdit()
        if proxy:
            self.username_edit.setText(proxy.username)
        form_layout.addRow("Username:", self.username_edit)
        
        # Password
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        if proxy:
            self.password_edit.setText(proxy.password)
        form_layout.addRow("Password:", self.password_edit)
        
        # Description
        self.description_edit = QLineEdit()
        if proxy:
            self.description_edit.setText(proxy.description)
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_proxy_data(self) -> Dict[str, Any]:
        """Get the proxy data."""
        return {
            'host': self.host_edit.text().strip(),
            'port': self.port_spin.value(),
            'username': self.username_edit.text().strip(),
            'password': self.password_edit.text().strip(),
            'proxy_type': self.type_combo.currentText(),
            'description': self.description_edit.text().strip()
        }


class IntegratedProxyManager(QWidget):
    """Integrated proxy manager using new foundation."""
    
    # Signals for communication with main window
    stats_updated = pyqtSignal(int, int)  # list_count, total_proxies
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proxy Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.proxies: List[ProxyData] = []
        self.current_list_file = None
        self.current_list_name = None
        
        # Worker for background operations
        self.worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_proxy_lists()
        
        logger.info("Integrated proxy manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top layout for main content
        top_layout = QHBoxLayout()
        
        # Left side - proxy lists
        left_widget = QWidget()
        left_widget.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_widget)
        
        # Title
        title = QLabel("<b>Proxy Lists</b>")
        left_layout.addWidget(title)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search Proxy Lists")
        self.search_bar.textChanged.connect(self.filter_lists)
        left_layout.addWidget(self.search_bar)
        
        # List controls
        list_controls = QHBoxLayout()
        
        self.btn_new_list = QPushButton("➕ New List")
        self.btn_new_list.clicked.connect(self.create_new_list)
        list_controls.addWidget(self.btn_new_list)
        
        self.btn_delete_list = QPushButton("🗑 Delete")
        self.btn_delete_list.clicked.connect(self.delete_list)
        list_controls.addWidget(self.btn_delete_list)
        
        left_layout.addLayout(list_controls)
        
        # Proxy lists
        self.proxy_list = QListWidget()
        self.proxy_list.itemClicked.connect(self.load_selected_list)
        self.proxy_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.proxy_list.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.proxy_list)
        
        top_layout.addWidget(left_widget, 1)
        
        # Right side - proxies table
        right_layout = QVBoxLayout()
        
        # Table controls
        table_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_proxies)
        table_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_proxies)
        table_controls.addWidget(self.btn_export)
        
        self.btn_add_proxy = QPushButton("➕ Add Proxy")
        self.btn_add_proxy.clicked.connect(self.add_proxy)
        table_controls.addWidget(self.btn_add_proxy)
        
        self.btn_test_all = QPushButton("🧪 Test All")
        self.btn_test_all.clicked.connect(self.test_all_proxies)
        table_controls.addWidget(self.btn_test_all)
        
        table_controls.addStretch()
        right_layout.addLayout(table_controls)
        
        # Proxies table
        self.proxies_table = QTableWidget()
        self.proxies_table.setColumnCount(7)
        self.proxies_table.setHorizontalHeaderLabels([
            "Host", "Port", "Type", "Status", "Username", "Description", "Last Tested"
        ])
        self.proxies_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.proxies_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.proxies_table.customContextMenuRequested.connect(self.show_proxy_context_menu)
        self.proxies_table.cellDoubleClicked.connect(self.edit_proxy)
        
        # Enable manual column resizing
        header = self.proxies_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 120)  # Host
        header.resizeSection(1, 60)   # Port
        header.resizeSection(2, 80)   # Type
        header.resizeSection(3, 80)   # Status
        header.resizeSection(4, 100)  # Username
        header.resizeSection(5, 150)  # Description
        header.resizeSection(6, 120)  # Last Tested
        
        right_layout.addWidget(self.proxies_table)
        
        top_layout.addLayout(right_layout, 3)
        layout.addLayout(top_layout)
        
        # Bottom section - progress and status
        bottom_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        
        layout.addLayout(bottom_layout)
    
    def load_proxy_lists(self):
        """Load available proxy lists (folders and files)."""
        try:
            proxies_dir = get_data_directory('proxies')
            os.makedirs(proxies_dir, exist_ok=True)
            
            self.proxy_list.clear()
            
            # Find both folders (new structure) and files (legacy)
            for item in os.listdir(proxies_dir):
                item_path = os.path.join(proxies_dir, item)
                
                if os.path.isdir(item_path):
                    # New folder structure
                    self.proxy_list.addItem(item)
                elif item.endswith('.json'):
                    # Legacy file structure
                    name = item.rsplit('.', 1)[0]
                    self.proxy_list.addItem(name)
            
            logger.info("Proxy lists loaded", count=self.proxy_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to load proxy lists")
            QMessageBox.warning(self, "Error", f"Failed to load proxy lists: {e}")
    
    def create_new_list(self):
        """Create a new proxy list with proper folder structure."""
        name, ok = QInputDialog.getText(self, "New Proxy List", "Enter list name:")
        if not ok or not name.strip():
            return
        
        # Clean the name
        name = name.strip()
        if name.endswith('.json'):
            name = name.rsplit('.', 1)[0]
        
        # Sanitize name for folder creation
        import re
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a valid list name.")
            return
        
        proxies_dir = get_data_directory('proxies')
        os.makedirs(proxies_dir, exist_ok=True)
        
        # Create folder for this list
        list_folder = os.path.join(proxies_dir, name)
        if os.path.exists(list_folder):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            # Create list folder
            os.makedirs(list_folder, exist_ok=True)
            
            # Create the data file inside the folder
            file_path = os.path.join(list_folder, f"{name}.json")
            
            # Create empty proxies list
            self.proxies = []
            self.current_list_file = file_path
            self.current_list_name = name
            
            # Save empty file
            self.save_current_list()
            
            # Refresh list
            self.load_proxy_lists()
            
            # Select the new list
            for i in range(self.proxy_list.count()):
                if self.proxy_list.item(i).text() == name:
                    self.proxy_list.setCurrentRow(i)
                    break
            
            logger.info("New proxy list created with folder", name=name, folder=list_folder)
            QMessageBox.information(self, "Success", f"Proxy list '{name}' created successfully!\nFolder: {list_folder}")
            
        except Exception as e:
            handle_exception(e, "Failed to create new proxy list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def load_selected_list(self):
        """Load the selected proxy list."""
        current_item = self.proxy_list.currentItem()
        if not current_item:
            return
        
        list_name = current_item.text()
        proxies_dir = get_data_directory('proxies')
        
        # Check folder structure (new) or file structure (legacy)
        folder_path = os.path.join(proxies_dir, list_name)
        
        file_path = None
        
        if os.path.isdir(folder_path):
            # New folder structure
            json_file = os.path.join(folder_path, f"{list_name}.json")
            if os.path.exists(json_file):
                file_path = json_file
            else:
                # Create the data file
                file_path = json_file
            self.current_list_name = list_name
        else:
            # Legacy file structure
            legacy_file = os.path.join(proxies_dir, f"{list_name}.json")
            if os.path.exists(legacy_file):
                file_path = legacy_file
                self.current_list_name = list_name
        
        if not file_path:
            QMessageBox.warning(self, "Error", f"Data file not found for list: {list_name}")
            return
        
        self.load_proxies_from_file(file_path)
    
    def load_proxies_from_file(self, file_path: str):
        """Load proxies from file using worker."""
        try:
            self.current_list_file = file_path
            self.status_label.setText("Loading proxies...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = ProxyWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.proxies_loaded.connect(self.on_proxies_loaded)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.load_proxies(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start proxy loading")
            QMessageBox.critical(self, "Error", f"Failed to load proxies: {e}")
    
    def on_proxies_loaded(self, proxies: List[ProxyData]):
        """Handle proxies loaded from worker."""
        self.proxies = proxies
        self.update_proxies_table()
        
        # Update stats
        list_count = self.proxy_list.count()
        total_proxies = len(self.proxies)
        self.stats_updated.emit(list_count, total_proxies)
        
        logger.info("Proxies loaded in UI", count=len(proxies))
    
    def update_proxies_table(self):
        """Update the proxies table display."""
        self.proxies_table.setRowCount(len(self.proxies))
        
        for row, proxy in enumerate(self.proxies):
            # Host
            self.proxies_table.setItem(row, 0, QTableWidgetItem(proxy.host))
            
            # Port
            self.proxies_table.setItem(row, 1, QTableWidgetItem(str(proxy.port)))
            
            # Type
            self.proxies_table.setItem(row, 2, QTableWidgetItem(proxy.proxy_type))
            
            # Status
            status_item = QTableWidgetItem(proxy.status)
            if proxy.status == "Working":
                status_item.setBackground(Qt.GlobalColor.green)
            elif proxy.status == "Failed":
                status_item.setBackground(Qt.GlobalColor.red)
            self.proxies_table.setItem(row, 3, status_item)
            
            # Username
            self.proxies_table.setItem(row, 4, QTableWidgetItem(proxy.username))
            
            # Description
            self.proxies_table.setItem(row, 5, QTableWidgetItem(proxy.description))
            
            # Last Tested
            last_tested = proxy.last_tested.strftime("%Y-%m-%d %H:%M") if proxy.last_tested else "Never"
            self.proxies_table.setItem(row, 6, QTableWidgetItem(last_tested))
        
        logger.debug("Proxies table updated", rows=len(self.proxies))
    
    def save_current_list(self):
        """Save current proxies to file."""
        if not self.current_list_file:
            QMessageBox.information(self, "No File", "No file selected to save to.")
            return
        
        try:
            self.status_label.setText("Saving proxies...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = ProxyWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.proxies_saved.connect(self.on_proxies_saved)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_proxies(self.current_list_file, self.proxies)
            
        except Exception as e:
            handle_exception(e, "Failed to save proxies")
            QMessageBox.critical(self, "Error", f"Failed to save proxies: {e}")
    
    def on_proxies_saved(self, success: bool, message: str):
        """Handle save completion."""
        if success:
            logger.info("Proxies saved successfully")
    
    def import_proxies(self):
        """Import proxies from external file."""
        if not self.current_list_file:
            QMessageBox.warning(
                self, "No List Selected",
                "Please create or select a proxy list first before importing."
            )
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Proxies",
            "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Importing proxies...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = ProxyWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.proxies_imported.connect(self.on_proxies_imported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.import_proxies(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start proxy import")
            QMessageBox.critical(self, "Error", f"Failed to import proxies: {e}")
    
    def on_proxies_imported(self, imported_proxies: List[ProxyData], total_count: int):
        """Handle imported proxies."""
        if imported_proxies:
            # Add to current proxies (avoid duplicates)
            existing_proxies = {f"{p.host}:{p.port}" for p in self.proxies}
            new_proxies = [p for p in imported_proxies 
                          if f"{p.host}:{p.port}" not in existing_proxies]
            
            self.proxies.extend(new_proxies)
            self.update_proxies_table()
            
            # Auto-save
            if self.current_list_file:
                self.save_current_list()
            
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(new_proxies)} new proxies.\n"
                f"Skipped {len(imported_proxies) - len(new_proxies)} duplicates."
            )
            
            logger.info("Proxies imported successfully", new=len(new_proxies), duplicates=len(imported_proxies) - len(new_proxies))
    
    def export_proxies(self):
        """Export current proxies."""
        if not self.proxies:
            QMessageBox.information(self, "No Data", "No proxies to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Proxies",
            f"proxies_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Exporting proxies...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = ProxyWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.proxies_saved.connect(self.on_proxies_exported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_proxies(file_path, self.proxies)
            
        except Exception as e:
            handle_exception(e, "Failed to start proxy export")
            QMessageBox.critical(self, "Error", f"Failed to export proxies: {e}")
    
    def on_proxies_exported(self, success: bool, message: str):
        """Handle export completion."""
        if success:
            QMessageBox.information(self, "Export Complete", "Proxies exported successfully.")
            logger.info("Proxies exported successfully")
    
    def add_proxy(self):
        """Add a new proxy manually."""
        dialog = ProxyEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            proxy_data = dialog.get_proxy_data()
            
            if not proxy_data['host']:
                QMessageBox.warning(self, "Invalid Input", "Host cannot be empty.")
                return
            
            # Check for duplicates
            proxy_key = f"{proxy_data['host']}:{proxy_data['port']}"
            existing_keys = {f"{p.host}:{p.port}" for p in self.proxies}
            
            if proxy_key in existing_keys:
                QMessageBox.warning(self, "Duplicate", "This proxy already exists.")
                return
            
            try:
                # Create proxy
                proxy = ProxyData(
                    host=proxy_data['host'],
                    port=proxy_data['port'],
                    username=proxy_data['username'],
                    password=proxy_data['password'],
                    proxy_type=proxy_data['proxy_type'],
                    description=proxy_data['description']
                )
                
                self.proxies.append(proxy)
                self.update_proxies_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Proxy added manually", host=proxy.host, port=proxy.port)
                
            except Exception as e:
                handle_exception(e, "Failed to add proxy")
                QMessageBox.critical(self, "Error", f"Failed to add proxy: {e}")
    
    def edit_proxy(self, row: int, column: int):
        """Edit a proxy."""
        if row >= len(self.proxies):
            return
        
        proxy = self.proxies[row]
        dialog = ProxyEditDialog(proxy, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            proxy_data = dialog.get_proxy_data()
            
            if not proxy_data['host']:
                QMessageBox.warning(self, "Invalid Input", "Host cannot be empty.")
                return
            
            try:
                # Update proxy
                proxy.host = proxy_data['host']
                proxy.port = proxy_data['port']
                proxy.username = proxy_data['username']
                proxy.password = proxy_data['password']
                proxy.proxy_type = proxy_data['proxy_type']
                proxy.description = proxy_data['description']
                
                # Reset test status if connection details changed
                proxy.status = "Untested"
                proxy.last_tested = None
                
                self.update_proxies_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Proxy edited", host=proxy.host, port=proxy.port)
                
            except Exception as e:
                handle_exception(e, "Failed to edit proxy")
                QMessageBox.critical(self, "Error", f"Failed to edit proxy: {e}")
    
    def test_proxy(self, row: int):
        """Test a single proxy."""
        if row >= len(self.proxies):
            return
        
        proxy = self.proxies[row]
        
        try:
            self.status_label.setText(f"Testing proxy {proxy.host}:{proxy.port}...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = ProxyWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.proxy_tested.connect(self.on_proxy_tested)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.test_proxy(proxy, row)
            
        except Exception as e:
            handle_exception(e, "Failed to start proxy test")
            QMessageBox.critical(self, "Error", f"Failed to test proxy: {e}")
    
    def on_proxy_tested(self, index: int, success: bool, message: str):
        """Handle proxy test completion."""
        if 0 <= index < len(self.proxies):
            proxy = self.proxies[index]
            self.update_proxies_table()
            
            # Auto-save
            if self.current_list_file:
                self.save_current_list()
            
            status = "✅ Working" if success else "❌ Failed"
            logger.info("Proxy test completed", host=proxy.host, port=proxy.port, success=success, message=message)
    
    def test_all_proxies(self):
        """Test all proxies in the list."""
        if not self.proxies:
            QMessageBox.information(self, "No Data", "No proxies to test.")
            return
        
        reply = QMessageBox.question(
            self, "Test All Proxies",
            f"This will test all {len(self.proxies)} proxies. This may take several minutes.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Test proxies sequentially
            self.current_test_index = 0
            self.test_next_proxy()
    
    def test_next_proxy(self):
        """Test the next proxy in sequence."""
        if self.current_test_index >= len(self.proxies):
            QMessageBox.information(self, "Testing Complete", "All proxies have been tested.")
            return
        
        self.test_proxy(self.current_test_index)
        self.current_test_index += 1
        
        # Schedule next test after current one completes
        QTimer.singleShot(2000, self.test_next_proxy)
    
    def delete_proxy(self, row: int):
        """Delete a proxy."""
        if row >= len(self.proxies):
            return
        
        proxy = self.proxies[row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this proxy?\n\n{proxy.host}:{proxy.port}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.proxies.pop(row)
                self.update_proxies_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Proxy deleted", host=proxy.host, port=proxy.port)
                
            except Exception as e:
                handle_exception(e, "Failed to delete proxy")
                QMessageBox.critical(self, "Error", f"Failed to delete proxy: {e}")
    
    def delete_list(self):
        """Delete the selected proxy list."""
        current_item = self.proxy_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a list to delete.")
            return
        
        list_name = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{list_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                proxies_dir = get_data_directory('proxies')
                
                # Try folder structure first
                folder_path = os.path.join(proxies_dir, list_name)
                if os.path.isdir(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)
                else:
                    # Try legacy files
                    file_path = os.path.join(proxies_dir, f"{list_name}.json")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                # Clear current data if this was the loaded list
                if self.current_list_name == list_name:
                    self.proxies = []
                    self.current_list_file = None
                    self.current_list_name = None
                    self.update_proxies_table()
                
                # Refresh list
                self.load_proxy_lists()
                
                logger.info("Proxy list deleted", list_name=list_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete proxy list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def filter_lists(self, text: str):
        """Filter the proxy lists based on search text."""
        for i in range(self.proxy_list.count()):
            item = self.proxy_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())
    
    def show_list_context_menu(self, position):
        """Show context menu for proxy lists."""
        if self.proxy_list.itemAt(position):
            menu = QMenu(self)
            
            menu.addAction("Load", self.load_selected_list)
            menu.addAction("Delete", self.delete_list)
            
            menu.exec(self.proxy_list.mapToGlobal(position))
    
    def show_proxy_context_menu(self, position):
        """Show context menu for proxies."""
        if self.proxies_table.itemAt(position):
            row = self.proxies_table.itemAt(position).row()
            menu = QMenu(self)
            
            menu.addAction("Edit", lambda: self.edit_proxy(row, 0))
            menu.addAction("Test", lambda: self.test_proxy(row))
            menu.addAction("Delete", lambda: self.delete_proxy(row))
            
            menu.exec(self.proxies_table.mapToGlobal(position))
    
    def update_progress(self, progress: WorkerProgress):
        """Update progress bar from worker."""
        self.progress_bar.setValue(int(progress.percentage))
        self.status_label.setText(progress.message)
    
    def on_worker_finished(self):
        """Handle worker completion."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")
        self.worker = None
    
    def on_worker_error(self, error_message: str):
        """Handle worker error."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Operation Error", error_message)
        self.worker = None