# ui/smtp_manager_integrated.py
"""
Integrated SMTP manager using new foundation architecture.

This module provides the GUI for SMTP management using:
- New SMTP models (core.data.models.SMTPConfig)
- New worker system (workers.smtp_test_worker)
- New validation and error handling
- Centralized logging
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QTableWidget, QTableWidgetItem,
    QToolButton, QComboBox, QLabel, QFileDialog, QMessageBox, QMenu, QInputDialog,
    QAbstractItemView, QApplication, QStyle, QHeaderView, QDialog, QLineEdit, QPushButton,
    QGridLayout, QDialogButtonBox, QCheckBox, QSpinBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import new foundation components
from core.data.models import SMTPConfig, SMTPSecurityType, SMTPStatus
from core.data.file_handler import FileHandler
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.smtp_test_worker import SMTPTestWorker, SMTPTestResult

logger = get_module_logger(__name__)


class IntegratedSMTPManager(QWidget):
    """Integrated SMTP manager using new foundation."""
    
    # Signals for communication with main window
    stats_updated = pyqtSignal(int, int)  # list_count, total_smtps
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SMTP Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        self.smtp_configs: List[SMTPConfig] = []
        self.current_list_file = None
        
        # Worker for testing
        self.test_worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_smtp_files()
        
        logger.info("Integrated SMTP manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Top section - file list and controls
        top_layout = QHBoxLayout()
        
        # Left side - SMTP files list
        left_layout = QVBoxLayout()
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search SMTP Lists")
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
        
        # SMTP files list
        self.smtp_list = QListWidget()
        self.smtp_list.itemClicked.connect(self.load_selected_list)
        self.smtp_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.smtp_list.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.smtp_list)
        
        top_layout.addLayout(left_layout, 1)
        
        # Right side - SMTP table
        right_layout = QVBoxLayout()
        
        # Table controls
        table_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_smtp_configs)
        table_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_smtp_configs)
        table_controls.addWidget(self.btn_export)
        
        self.btn_add_smtp = QPushButton("➕ Add SMTP")
        self.btn_add_smtp.clicked.connect(self.add_smtp_config)
        table_controls.addWidget(self.btn_add_smtp)
        
        self.btn_test_selected = QPushButton("🧪 Test Selected")
        self.btn_test_selected.clicked.connect(self.test_selected)
        table_controls.addWidget(self.btn_test_selected)
        
        self.btn_test_all = QPushButton("🧪 Test All")
        self.btn_test_all.clicked.connect(self.test_all)
        table_controls.addWidget(self.btn_test_all)
        
        table_controls.addStretch()
        
        # Thread count selector
        table_controls.addWidget(QLabel("Threads:"))
        self.thread_count_combo = QComboBox()
        self.thread_count_combo.addItems([str(i) for i in [1, 2, 3, 4, 5, 10, 20]])
        self.thread_count_combo.setCurrentText("5")
        table_controls.addWidget(self.thread_count_combo)
        
        right_layout.addLayout(table_controls)
        
        # SMTP table
        self.smtp_table = QTableWidget()
        self.smtp_table.setColumnCount(10)
        self.smtp_table.setHorizontalHeaderLabels([
            "Host", "Port", "Security", "Username", "Password", 
            "From Name", "From Email", "Status", "Response Time", "Last Tested"
        ])
        self.smtp_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.smtp_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.smtp_table.customContextMenuRequested.connect(self.show_smtp_context_menu)
        self.smtp_table.cellChanged.connect(self.on_smtp_edited)
        
        # Enable manual column resizing
        header = self.smtp_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # Allow manual resizing
        # Set reasonable default widths
        header.resizeSection(0, 150)  # Host
        header.resizeSection(1, 60)   # Port
        header.resizeSection(2, 80)   # Security
        header.resizeSection(3, 120)  # Username
        header.resizeSection(4, 100)  # Password
        header.resizeSection(5, 120)  # From Name
        header.resizeSection(6, 150)  # From Email
        header.resizeSection(7, 80)   # Status
        header.resizeSection(8, 100)  # Response Time
        header.resizeSection(9, 120)  # Last Tested
        
        right_layout.addWidget(self.smtp_table)
        
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
    
    def load_smtp_files(self):
        """Load available SMTP files."""
        try:
            smtp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'smtps')
            os.makedirs(smtp_dir, exist_ok=True)
            
            self.smtp_list.clear()
            
            # Find Excel files
            for filename in os.listdir(smtp_dir):
                if filename.endswith(('.xlsx', '.xls')):
                    self.smtp_list.addItem(filename)
            
            logger.info("SMTP files loaded", count=self.smtp_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to load SMTP files")
            QMessageBox.warning(self, "Error", f"Failed to load SMTP files: {e}")
    
    def load_selected_list(self):
        """Load the selected SMTP list."""
        current_item = self.smtp_list.currentItem()
        if not current_item:
            return
        
        filename = current_item.text()
        smtp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'smtps')
        file_path = os.path.join(smtp_dir, filename)
        
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {filename}")
            return
        
        self.load_smtp_from_file(file_path)
    
    def load_smtp_from_file(self, file_path: str):
        """Load SMTP configs from file."""
        try:
            self.current_list_file = file_path
            self.status_label.setText("Loading SMTP configs...")
            
            # Load data using file handler
            data = self.file_handler.load_excel(file_path)
            
            if not data or len(data) < 2:
                self.smtp_configs = []
                self.update_smtp_table()
                return
            
            headers = data[0]
            rows = data[1:]
            
            # Parse SMTP configs
            self.smtp_configs = []
            
            # Find column indices
            col_indices = {}
            for i, header in enumerate(headers):
                header_lower = str(header).lower()
                if 'host' in header_lower or 'server' in header_lower:
                    col_indices['host'] = i
                elif 'port' in header_lower:
                    col_indices['port'] = i
                elif 'security' in header_lower or 'ssl' in header_lower or 'tls' in header_lower:
                    col_indices['security'] = i
                elif 'user' in header_lower or 'username' in header_lower:
                    col_indices['username'] = i
                elif 'pass' in header_lower:
                    col_indices['password'] = i
                elif 'from' in header_lower and 'name' in header_lower:
                    col_indices['from_name'] = i
                elif 'from' in header_lower and ('email' in header_lower or 'address' in header_lower):
                    col_indices['from_email'] = i
            
            # Process rows
            for row in rows:
                try:
                    host = str(row[col_indices.get('host', 0)]).strip() if col_indices.get('host', 0) < len(row) else ""
                    if not host:
                        continue
                    
                    port = int(row[col_indices.get('port', 1)]) if col_indices.get('port', 1) < len(row) and str(row[col_indices.get('port', 1)]).isdigit() else 587
                    
                    security_text = str(row[col_indices.get('security', 2)]).lower() if col_indices.get('security', 2) < len(row) else "tls"
                    if 'ssl' in security_text:
                        security = SMTPSecurityType.SSL
                    elif 'tls' in security_text:
                        security = SMTPSecurityType.TLS
                    else:
                        security = SMTPSecurityType.NONE
                    
                    username = str(row[col_indices.get('username', 3)]).strip() if col_indices.get('username', 3) < len(row) else ""
                    password = str(row[col_indices.get('password', 4)]).strip() if col_indices.get('password', 4) < len(row) else ""
                    from_name = str(row[col_indices.get('from_name', 5)]).strip() if col_indices.get('from_name', 5) < len(row) else ""
                    from_email = str(row[col_indices.get('from_email', 6)]).strip() if col_indices.get('from_email', 6) < len(row) else ""
                    
                    smtp_config = SMTPConfig(
                        host=host,
                        port=port,
                        security=security,
                        username=username,
                        password=password,
                        from_name=from_name,
                        from_email=from_email
                    )
                    
                    self.smtp_configs.append(smtp_config)
                    
                except Exception as e:
                    logger.warning("Error parsing SMTP config row", error=str(e))
                    continue
            
            self.update_smtp_table()
            
            # Update stats
            list_count = self.smtp_list.count()
            total_smtps = len(self.smtp_configs)
            self.stats_updated.emit(list_count, total_smtps)
            
            logger.info("SMTP configs loaded", count=len(self.smtp_configs))
            
        except Exception as e:
            handle_exception(e, "Failed to load SMTP configs")
            QMessageBox.critical(self, "Error", f"Failed to load SMTP configs: {e}")
    
    def update_smtp_table(self):
        """Update the SMTP table display."""
        self.smtp_table.setRowCount(len(self.smtp_configs))
        
        for row, smtp_config in enumerate(self.smtp_configs):
            # Host
            self.smtp_table.setItem(row, 0, QTableWidgetItem(smtp_config.host))
            
            # Port
            self.smtp_table.setItem(row, 1, QTableWidgetItem(str(smtp_config.port)))
            
            # Security
            self.smtp_table.setItem(row, 2, QTableWidgetItem(smtp_config.security.value.upper()))
            
            # Username
            self.smtp_table.setItem(row, 3, QTableWidgetItem(smtp_config.username or ""))
            
            # Password (masked)
            password_text = "*" * len(smtp_config.password) if smtp_config.password else ""
            self.smtp_table.setItem(row, 4, QTableWidgetItem(password_text))
            
            # From Name
            self.smtp_table.setItem(row, 5, QTableWidgetItem(smtp_config.from_name or ""))
            
            # From Email
            self.smtp_table.setItem(row, 6, QTableWidgetItem(smtp_config.from_email or ""))
            
            # Status
            status_text = smtp_config.status.value.upper()
            if smtp_config.status == SMTPStatus.WORKING:
                status_text = "✅ " + status_text
            elif smtp_config.status == SMTPStatus.FAILED:
                status_text = "❌ " + status_text
            elif smtp_config.status == SMTPStatus.TESTING:
                status_text = "🧪 " + status_text
            else:
                status_text = "⚪ " + status_text
            
            self.smtp_table.setItem(row, 7, QTableWidgetItem(status_text))
            
            # Response Time
            response_time = f"{smtp_config.response_time:.2f}s" if smtp_config.response_time else ""
            self.smtp_table.setItem(row, 8, QTableWidgetItem(response_time))
            
            # Last Tested
            last_tested = smtp_config.last_tested.strftime("%Y-%m-%d %H:%M") if smtp_config.last_tested else ""
            self.smtp_table.setItem(row, 9, QTableWidgetItem(last_tested))
        
        logger.debug("SMTP table updated", rows=len(self.smtp_configs))
    
    def create_new_list(self):
        """Create a new SMTP list."""
        name, ok = QInputDialog.getText(self, "New SMTP List", "Enter list name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        if not name.endswith(('.xlsx', '.xls')):
            name += '.xlsx'
        
        smtp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'smtps')
        os.makedirs(smtp_dir, exist_ok=True)  # Ensure directory exists
        file_path = os.path.join(smtp_dir, name)
        
        if os.path.exists(file_path):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            # Create empty SMTP list
            self.smtp_configs = []
            self.current_list_file = file_path
            
            # Save empty file
            self.save_current_list()
            
            # Refresh file list
            self.load_smtp_files()
            
            # Select the new file
            for i in range(self.smtp_list.count()):
                if self.smtp_list.item(i).text() == name:
                    self.smtp_list.setCurrentRow(i)
                    break
            
            logger.info("New SMTP list created", name=name)
            
        except Exception as e:
            handle_exception(e, "Failed to create new SMTP list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def delete_list(self):
        """Delete the selected SMTP list."""
        current_item = self.smtp_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a list to delete.")
            return
        
        filename = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{filename}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                smtp_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'smtps')
                file_path = os.path.join(smtp_dir, filename)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Clear current data if this was the loaded file
                if self.current_list_file == file_path:
                    self.smtp_configs = []
                    self.current_list_file = None
                    self.update_smtp_table()
                
                # Refresh file list
                self.load_smtp_files()
                
                logger.info("SMTP list deleted", filename=filename)
                
            except Exception as e:
                handle_exception(e, "Failed to delete SMTP list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def import_smtp_configs(self):
        """Import SMTP configs from external file."""
        # Check if a list is selected
        if not self.current_list_file:
            QMessageBox.warning(
                self, "No List Selected",
                "Please create or select an SMTP list first before importing."
            )
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import SMTP Configs",
            "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # Load and import
            self.load_smtp_from_file(file_path)
            
            # Auto-save if we have a current file
            if self.current_list_file:
                self.save_current_list()
            
            QMessageBox.information(self, "Import Complete", 
                                  f"Imported {len(self.smtp_configs)} SMTP configurations.")
            
            logger.info("SMTP configs imported successfully", count=len(self.smtp_configs))
            
        except Exception as e:
            handle_exception(e, "Failed to import SMTP configs")
            QMessageBox.critical(self, "Error", f"Failed to import SMTP configs: {e}")
    
    def export_smtp_configs(self):
        """Export current SMTP configs to file."""
        if not self.smtp_configs:
            QMessageBox.information(self, "No Data", "No SMTP configs to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export SMTP Configs",
            f"smtp_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            self.save_smtp_to_file(file_path)
            QMessageBox.information(self, "Export Complete", "SMTP configs exported successfully.")
            logger.info("SMTP configs exported successfully")
            
        except Exception as e:
            handle_exception(e, "Failed to export SMTP configs")
            QMessageBox.critical(self, "Error", f"Failed to export SMTP configs: {e}")
    
    def save_current_list(self):
        """Save current SMTP configs to file."""
        if not self.current_list_file:
            QMessageBox.information(self, "No File", "No file selected to save to.")
            return
        
        try:
            self.save_smtp_to_file(self.current_list_file)
            logger.info("SMTP configs saved successfully")
            
        except Exception as e:
            handle_exception(e, "Failed to save SMTP configs")
            QMessageBox.critical(self, "Error", f"Failed to save SMTP configs: {e}")
    
    def save_smtp_to_file(self, file_path: str):
        """Save SMTP configs to file."""
        try:
            # Convert to tabular data
            headers = [
                "Host", "Port", "Security", "Username", "Password",
                "From Name", "From Email", "Status", "Response Time", "Last Tested"
            ]
            
            data = [headers]
            
            for smtp_config in self.smtp_configs:
                row = [
                    smtp_config.host,
                    str(smtp_config.port),
                    smtp_config.security.value,
                    smtp_config.username or "",
                    smtp_config.password or "",
                    smtp_config.from_name or "",
                    smtp_config.from_email or "",
                    smtp_config.status.value,
                    f"{smtp_config.response_time:.2f}" if smtp_config.response_time else "",
                    smtp_config.last_tested.strftime("%Y-%m-%d %H:%M:%S") if smtp_config.last_tested else ""
                ]
                data.append(row)
            
            # Save using file handler
            self.file_handler.save_excel_tabular(data, file_path)
            
        except Exception as e:
            raise FileError(f"Failed to save SMTP configs: {e}")
    
    def add_smtp_config(self):
        """Add a new SMTP configuration."""
        dialog = SMTPEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            smtp_data = dialog.get_smtp_data()
            
            try:
                smtp_config = SMTPConfig(
                    host=smtp_data['host'],
                    port=smtp_data['port'],
                    security=smtp_data['security'],
                    username=smtp_data['username'],
                    password=smtp_data['password'],
                    from_name=smtp_data['from_name'],
                    from_email=smtp_data['from_email']
                )
                
                self.smtp_configs.append(smtp_config)
                self.update_smtp_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("SMTP config added", host=smtp_config.host)
                
            except Exception as e:
                handle_exception(e, "Failed to add SMTP config")
                QMessageBox.critical(self, "Error", f"Failed to add SMTP config: {e}")
    
    def test_selected(self):
        """Test selected SMTP configurations."""
        selected_rows = set()
        for item in self.smtp_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select SMTP configs to test.")
            return
        
        selected_configs = [self.smtp_configs[row] for row in selected_rows if row < len(self.smtp_configs)]
        self.start_smtp_testing(selected_configs)
    
    def test_all(self):
        """Test all SMTP configurations."""
        if not self.smtp_configs:
            QMessageBox.information(self, "No Data", "No SMTP configs to test.")
            return
        
        self.start_smtp_testing(self.smtp_configs)
    
    def start_smtp_testing(self, configs_to_test: List[SMTPConfig]):
        """Start SMTP testing with worker."""
        try:
            thread_count = int(self.thread_count_combo.currentText())
            
            self.status_label.setText(f"Testing {len(configs_to_test)} SMTP configs...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(len(configs_to_test))
            
            # Mark configs as testing
            for config in configs_to_test:
                config.status = SMTPStatus.TESTING
            self.update_smtp_table()
            
            # Create and start worker
            self.test_worker = SMTPTestWorker()
            self.test_worker.progress_updated.connect(self.update_test_progress)
            self.test_worker.test_completed.connect(self.on_test_completed)
            self.test_worker.all_tests_completed.connect(self.on_all_tests_completed)
            self.test_worker.error_occurred.connect(self.on_test_error)
            
            self.test_worker.test_smtp_configs(configs_to_test, max_threads=thread_count)
            
            logger.info("SMTP testing started", count=len(configs_to_test), threads=thread_count)
            
        except Exception as e:
            handle_exception(e, "Failed to start SMTP testing")
            QMessageBox.critical(self, "Error", f"Failed to start testing: {e}")
    
    def update_test_progress(self, progress):
        """Update testing progress."""
        self.progress_bar.setValue(progress.current)
        self.status_label.setText(progress.message)
    
    def on_test_completed(self, result: SMTPTestResult):
        """Handle individual test completion."""
        # Find the config in our list and update it
        for config in self.smtp_configs:
            if (config.host == result.smtp_config.host and 
                config.port == result.smtp_config.port and
                config.username == result.smtp_config.username):
                
                config.status = SMTPStatus.WORKING if result.success else SMTPStatus.FAILED
                config.response_time = result.response_time
                config.last_tested = datetime.now()
                config.error_message = result.error_message if not result.success else None
                break
        
        self.update_smtp_table()
        logger.debug("SMTP test completed", host=result.smtp_config.host, success=result.success)
    
    def on_all_tests_completed(self, results: List[SMTPTestResult]):
        """Handle all tests completion."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Testing completed")
        
        # Auto-save results
        if self.current_list_file:
            self.save_current_list()
        
        # Show summary
        successful = sum(1 for result in results if result.success)
        failed = len(results) - successful
        
        QMessageBox.information(
            self, "Testing Complete",
            f"Testing completed:\n\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}\n"
            f"Total: {len(results)}"
        )
        
        logger.info("SMTP testing completed", 
                   total=len(results), successful=successful, failed=failed)
        
        self.test_worker = None
    
    def on_test_error(self, error_message: str):
        """Handle testing error."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Testing error")
        QMessageBox.critical(self, "Testing Error", error_message)
        self.test_worker = None
    
    def filter_lists(self, text: str):
        """Filter SMTP lists based on search text."""
        for i in range(self.smtp_list.count()):
            item = self.smtp_list.item(i)
            visible = text.lower() in item.text().lower()
            item.setHidden(not visible)
    
    def show_list_context_menu(self, position):
        """Show context menu for SMTP list."""
        item = self.smtp_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        load_action = QAction("Load", self)
        load_action.triggered.connect(self.load_selected_list)
        menu.addAction(load_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_list)
        menu.addAction(delete_action)
        
        menu.exec(self.smtp_list.mapToGlobal(position))
    
    def show_smtp_context_menu(self, position):
        """Show context menu for SMTP table."""
        row = self.smtp_table.rowAt(position.y())
        if row < 0 or row >= len(self.smtp_configs):
            return
        
        menu = QMenu(self)
        
        test_action = QAction("Test", self)
        test_action.triggered.connect(lambda: self.test_single_smtp(row))
        menu.addAction(test_action)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self.edit_smtp(row))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_smtp(row))
        menu.addAction(delete_action)
        
        menu.exec(self.smtp_table.mapToGlobal(position))
    
    def test_single_smtp(self, row: int):
        """Test a single SMTP configuration."""
        if row < 0 or row >= len(self.smtp_configs):
            return
        
        self.start_smtp_testing([self.smtp_configs[row]])
    
    def edit_smtp(self, row: int):
        """Edit an SMTP configuration."""
        if row < 0 or row >= len(self.smtp_configs):
            return
        
        smtp_config = self.smtp_configs[row]
        dialog = SMTPEditDialog(self, smtp_config)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            smtp_data = dialog.get_smtp_data()
            
            try:
                # Update config
                smtp_config.host = smtp_data['host']
                smtp_config.port = smtp_data['port']
                smtp_config.security = smtp_data['security']
                smtp_config.username = smtp_data['username']
                smtp_config.password = smtp_data['password']
                smtp_config.from_name = smtp_data['from_name']
                smtp_config.from_email = smtp_data['from_email']
                smtp_config.status = SMTPStatus.UNTESTED  # Reset status
                smtp_config.last_modified = datetime.now()
                
                self.update_smtp_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("SMTP config edited", host=smtp_config.host)
                
            except Exception as e:
                handle_exception(e, "Failed to edit SMTP config")
                QMessageBox.critical(self, "Error", f"Failed to edit SMTP config: {e}")
    
    def delete_smtp(self, row: int):
        """Delete an SMTP configuration."""
        if row < 0 or row >= len(self.smtp_configs):
            return
        
        smtp_config = self.smtp_configs[row]
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete SMTP config '{smtp_config.host}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                del self.smtp_configs[row]
                self.update_smtp_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("SMTP config deleted", host=smtp_config.host)
                
            except Exception as e:
                handle_exception(e, "Failed to delete SMTP config")
                QMessageBox.critical(self, "Error", f"Failed to delete SMTP config: {e}")
    
    def on_smtp_edited(self, row: int, column: int):
        """Handle direct table editing."""
        if row < 0 or row >= len(self.smtp_configs):
            return
        
        smtp_config = self.smtp_configs[row]
        item = self.smtp_table.item(row, column)
        value = item.text().strip() if item else ""
        
        try:
            # Update config based on column
            if column == 0:  # Host
                smtp_config.host = value
            elif column == 1:  # Port
                if value.isdigit():
                    smtp_config.port = int(value)
            elif column == 2:  # Security
                value_lower = value.lower()
                if 'ssl' in value_lower:
                    smtp_config.security = SMTPSecurityType.SSL
                elif 'tls' in value_lower:
                    smtp_config.security = SMTPSecurityType.TLS
                elif 'none' in value_lower:
                    smtp_config.security = SMTPSecurityType.NONE
            elif column == 3:  # Username
                smtp_config.username = value
            elif column == 4:  # Password (can't edit masked password directly)
                pass
            elif column == 5:  # From Name
                smtp_config.from_name = value
            elif column == 6:  # From Email
                smtp_config.from_email = value
            
            smtp_config.status = SMTPStatus.UNTESTED  # Reset status after edit
            smtp_config.last_modified = datetime.now()
            
            # Auto-save if we have a current file
            if self.current_list_file:
                QTimer.singleShot(1000, self.save_current_list)  # Debounced save
            
        except Exception as e:
            handle_exception(e, "Failed to update SMTP config")
            # Revert the change
            self.update_smtp_table()


class SMTPEditDialog(QDialog):
    """Dialog for editing SMTP configuration."""
    
    def __init__(self, parent=None, smtp_config: Optional[SMTPConfig] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit SMTP Config" if smtp_config else "Add SMTP Config")
        self.setModal(True)
        self.resize(500, 400)
        
        self.smtp_config = smtp_config
        self.setup_ui()
        
        if smtp_config:
            self.load_smtp_data()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QGridLayout()
        
        # Host
        form_layout.addWidget(QLabel("Host:"), 0, 0)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("smtp.gmail.com")
        form_layout.addWidget(self.host_edit, 0, 1)
        
        # Port
        form_layout.addWidget(QLabel("Port:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(587)
        form_layout.addWidget(self.port_spin, 1, 1)
        
        # Security
        form_layout.addWidget(QLabel("Security:"), 2, 0)
        self.security_combo = QComboBox()
        self.security_combo.addItems(["TLS", "SSL", "None"])
        self.security_combo.setCurrentText("TLS")
        form_layout.addWidget(self.security_combo, 2, 1)
        
        # Username
        form_layout.addWidget(QLabel("Username:"), 3, 0)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("your.email@gmail.com")
        form_layout.addWidget(self.username_edit, 3, 1)
        
        # Password
        form_layout.addWidget(QLabel("Password:"), 4, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Your password or app password")
        form_layout.addWidget(self.password_edit, 4, 1)
        
        # Show password checkbox
        self.show_password_check = QCheckBox("Show password")
        self.show_password_check.toggled.connect(self.toggle_password_visibility)
        form_layout.addWidget(self.show_password_check, 5, 1)
        
        # From Name
        form_layout.addWidget(QLabel("From Name:"), 6, 0)
        self.from_name_edit = QLineEdit()
        self.from_name_edit.setPlaceholderText("Your Name")
        form_layout.addWidget(self.from_name_edit, 6, 1)
        
        # From Email
        form_layout.addWidget(QLabel("From Email:"), 7, 0)
        self.from_email_edit = QLineEdit()
        self.from_email_edit.setPlaceholderText("your.email@gmail.com")
        form_layout.addWidget(self.from_email_edit, 7, 1)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def toggle_password_visibility(self, checked: bool):
        """Toggle password visibility."""
        if checked:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    def load_smtp_data(self):
        """Load existing SMTP data into form."""
        if self.smtp_config:
            self.host_edit.setText(self.smtp_config.host)
            self.port_spin.setValue(self.smtp_config.port)
            self.security_combo.setCurrentText(self.smtp_config.security.value.upper())
            self.username_edit.setText(self.smtp_config.username or "")
            self.password_edit.setText(self.smtp_config.password or "")
            self.from_name_edit.setText(self.smtp_config.from_name or "")
            self.from_email_edit.setText(self.smtp_config.from_email or "")
    
    def get_smtp_data(self) -> Dict[str, Any]:
        """Get SMTP data from form."""
        security_text = self.security_combo.currentText().lower()
        if security_text == "ssl":
            security = SMTPSecurityType.SSL
        elif security_text == "tls":
            security = SMTPSecurityType.TLS
        else:
            security = SMTPSecurityType.NONE
        
        return {
            'host': self.host_edit.text().strip(),
            'port': self.port_spin.value(),
            'security': security,
            'username': self.username_edit.text().strip(),
            'password': self.password_edit.text(),
            'from_name': self.from_name_edit.text().strip(),
            'from_email': self.from_email_edit.text().strip()
        }
    
    def accept(self):
        """Validate and accept the dialog."""
        data = self.get_smtp_data()
        
        if not data['host']:
            QMessageBox.warning(self, "Validation Error", "Host is required.")
            self.host_edit.setFocus()
            return
        
        if not data['username']:
            QMessageBox.warning(self, "Validation Error", "Username is required.")
            self.username_edit.setFocus()
            return
        
        if not data['password']:
            QMessageBox.warning(self, "Validation Error", "Password is required.")
            self.password_edit.setFocus()
            return
        
        super().accept()