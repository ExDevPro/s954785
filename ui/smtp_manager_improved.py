# ui/smtp_manager_improved.py
"""
Improved SMTP Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QPushButton, QComboBox, QHBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os

class SMTPTestWorker(QThread):
    """Worker for testing SMTP connections"""
    test_completed = pyqtSignal(int, bool, str)  # row, success, message
    
    def __init__(self, smtp_data, row, parent=None):
        super().__init__(parent)
        self.smtp_data = smtp_data
        self.row = row
    
    def run(self):
        try:
            # Test SMTP connection
            import smtplib
            import ssl
            
            host = self.smtp_data.get('host', '')
            port = int(self.smtp_data.get('port', 587))
            security = self.smtp_data.get('security', 'TLS').upper()
            username = self.smtp_data.get('username', '')
            password = self.smtp_data.get('password', '')
            
            if security == 'SSL':
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=context)
            else:
                server = smtplib.SMTP(host, port)
                if security == 'TLS':
                    server.starttls()
            
            server.login(username, password)
            server.quit()
            
            self.test_completed.emit(self.row, True, "Connection successful")
            
        except Exception as e:
            self.test_completed.emit(self.row, False, str(e))

class SMTPManagerImproved(BaseManager):
    """Improved SMTP Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="smtp",
            data_subdir="smtps",
            file_extension=".xlsx", 
            parent=parent
        )
        
        # SMTP-specific headers
        self.default_headers = [
            "Host", "Port", "Security", "Username", "Password", 
            "From Name", "From Email", "Status", "Last Tested", "Notes"
        ]
        
        self.test_workers = {}  # Track test workers
    
    def _create_toolbar(self):
        """Create SMTP-specific toolbar"""
        toolbar_layout = super()._create_toolbar()
        
        # Add SMTP-specific buttons
        btn_test_all = QPushButton("🧪 Test All SMTPs")
        btn_test_all.setToolTip("Test all SMTP connections")
        btn_test_all.clicked.connect(self._test_all_smtps)
        btn_test_all.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        
        btn_test_selected = QPushButton("🔍 Test Selected")
        btn_test_selected.setToolTip("Test selected SMTP connection")
        btn_test_selected.clicked.connect(self._test_selected_smtp)
        
        # Insert before the stretch
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_test_all)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_test_selected)
        
        return toolbar_layout
    
    def _create_new_list_structure(self, list_name: str):
        """Create new SMTP list structure"""
        # Create Excel file directly in smtps folder
        excel_path = os.path.join(self.data_dir, f"{list_name}.xlsx")
        
        from openpyxl import Workbook
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(self.default_headers)
        workbook.save(excel_path)
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to SMTP list Excel file"""
        return os.path.join(self.data_dir, f"{list_name}.xlsx")
    
    def _create_empty_list_data(self):
        """Create empty SMTP data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _add_row(self):
        """Add a new SMTP row with default values"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select an SMTP list first!")
            return
        
        # Create new row with default values
        new_row = ["smtp.gmail.com", "587", "TLS", "", "", "", "", "Untested", "", ""]
        self.current_data.append(new_row)
        
        # Update table
        self._update_table()
        
        # Select the new row and focus on host field
        new_row_index = len(self.current_data) - 1
        self.table_widget.selectRow(new_row_index)
        self.table_widget.scrollToItem(self.table_widget.item(new_row_index, 0))
        
        # Focus on host field for editing
        host_item = self.table_widget.item(new_row_index, 0)
        if host_item:
            self.table_widget.setCurrentItem(host_item)
            self.table_widget.editItem(host_item)
    
    def _test_all_smtps(self):
        """Test all SMTP connections in current list"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No SMTP configurations to test!")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.current_data))
        self.progress_bar.setValue(0)
        
        # Start test workers for each SMTP
        for row, smtp_data in enumerate(self.current_data):
            if row < len(self.headers):
                smtp_config = {
                    'host': smtp_data[0] if len(smtp_data) > 0 else '',
                    'port': smtp_data[1] if len(smtp_data) > 1 else '587',
                    'security': smtp_data[2] if len(smtp_data) > 2 else 'TLS',
                    'username': smtp_data[3] if len(smtp_data) > 3 else '',
                    'password': smtp_data[4] if len(smtp_data) > 4 else '',
                }
                
                worker = SMTPTestWorker(smtp_config, row)
                worker.test_completed.connect(self._on_smtp_test_completed)
                self.test_workers[row] = worker
                worker.start()
    
    def _test_selected_smtp(self):
        """Test selected SMTP connection"""
        current_row = self.table_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select an SMTP configuration to test!")
            return
        
        if current_row >= len(self.current_data):
            return
        
        smtp_data = self.current_data[current_row]
        smtp_config = {
            'host': smtp_data[0] if len(smtp_data) > 0 else '',
            'port': smtp_data[1] if len(smtp_data) > 1 else '587',
            'security': smtp_data[2] if len(smtp_data) > 2 else 'TLS',
            'username': smtp_data[3] if len(smtp_data) > 3 else '',
            'password': smtp_data[4] if len(smtp_data) > 4 else '',
        }
        
        worker = SMTPTestWorker(smtp_config, current_row)
        worker.test_completed.connect(self._on_smtp_test_completed)
        self.test_workers[current_row] = worker
        worker.start()
        
        # Update status to "Testing..."
        if len(smtp_data) > 7:
            smtp_data[7] = "Testing..."
            status_item = QTableWidgetItem("Testing...")
            self.table_widget.setItem(current_row, 7, status_item)
    
    def _on_smtp_test_completed(self, row: int, success: bool, message: str):
        """Handle SMTP test completion"""
        if row < len(self.current_data):
            # Update status in data
            if len(self.current_data[row]) > 7:
                self.current_data[row][7] = "✅ Working" if success else "❌ Failed"
                self.current_data[row][8] = self._get_current_timestamp()  # Last tested
            
            # Update status in table
            status_item = QTableWidgetItem("✅ Working" if success else "❌ Failed")
            if success:
                status_item.setBackground(Qt.GlobalColor.green)
            else:
                status_item.setBackground(Qt.GlobalColor.red)
                status_item.setToolTip(message)
            
            self.table_widget.setItem(row, 7, status_item)
            
            # Update last tested column
            if self.table_widget.columnCount() > 8:
                timestamp_item = QTableWidgetItem(self._get_current_timestamp())
                self.table_widget.setItem(row, 8, timestamp_item)
        
        # Update progress
        completed_tests = len([w for w in self.test_workers.values() if w.isFinished()])
        self.progress_bar.setValue(completed_tests)
        
        # Clean up finished worker
        if row in self.test_workers:
            self.test_workers[row].deleteLater()
            del self.test_workers[row]
        
        # Hide progress bar when all tests complete
        if completed_tests >= len(self.current_data):
            self.progress_bar.setVisible(False)
    
    def _get_current_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _update_table(self):
        """Update table with SMTP-specific formatting"""
        super()._update_table()
        
        # Apply SMTP-specific formatting
        for row in range(self.table_widget.rowCount()):
            # Color-code status column
            if self.table_widget.columnCount() > 7:
                status_item = self.table_widget.item(row, 7)
                if status_item:
                    status_text = status_item.text()
                    if "Working" in status_text or "✅" in status_text:
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif "Failed" in status_text or "❌" in status_text:
                        status_item.setBackground(Qt.GlobalColor.red)
                    elif "Testing" in status_text:
                        status_item.setBackground(Qt.GlobalColor.yellow)
    
    def _on_operation_completed(self, result: dict):
        """Handle completed operations with SMTP-specific processing"""
        super()._on_operation_completed(result)
        
        # Additional SMTP processing
        if 'data' in result and result.get('manager_type') == 'smtp':
            # Validate required fields
            self._validate_smtp_data()
    
    def _validate_smtp_data(self):
        """Validate SMTP data and highlight issues"""
        if not self.current_data:
            return
        
        for row in range(self.table_widget.rowCount()):
            # Check host field (column 0)
            host_item = self.table_widget.item(row, 0)
            if host_item:
                host = host_item.text().strip()
                if not host:
                    host_item.setBackground(Qt.GlobalColor.red)
                    host_item.setToolTip("Host is required")
                else:
                    host_item.setBackground(Qt.GlobalColor.white)
                    host_item.setToolTip("")
            
            # Check username field (column 3)
            username_item = self.table_widget.item(row, 3)
            if username_item:
                username = username_item.text().strip()
                if not username:
                    username_item.setBackground(Qt.GlobalColor.yellow)
                    username_item.setToolTip("Username recommended for authentication")
                else:
                    username_item.setBackground(Qt.GlobalColor.white)
                    username_item.setToolTip("")