# ui/proxy_manager_improved.py
"""
Improved Proxy Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QPushButton, QComboBox, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import socket
import socks
from datetime import datetime

class ProxyTestWorker(QThread):
    """Worker for testing proxy connections"""
    test_completed = pyqtSignal(int, bool, str, float)  # row, success, message, response_time
    
    def __init__(self, proxy_data, row, test_host="smtp.gmail.com", test_port=587, parent=None):
        super().__init__(parent)
        self.proxy_data = proxy_data
        self.row = row
        self.test_host = test_host
        self.test_port = test_port
    
    def run(self):
        try:
            import time
            start_time = time.time()
            
            # Parse proxy data
            proxy_parts = self.proxy_data.get('proxy', '').split(':')
            if len(proxy_parts) < 2:
                self.test_completed.emit(self.row, False, "Invalid proxy format", 0)
                return
            
            ip = proxy_parts[0]
            port = int(proxy_parts[1])
            username = proxy_parts[2] if len(proxy_parts) > 2 else None
            password = proxy_parts[3] if len(proxy_parts) > 3 else None
            
            proxy_type = self.proxy_data.get('type', 'HTTP').upper()
            
            # Test connection
            if proxy_type == 'SOCKS5':
                sock = socks.socksocket()
                sock.set_proxy(socks.SOCKS5, ip, port, username=username, password=password)
            elif proxy_type == 'SOCKS4':
                sock = socks.socksocket()
                sock.set_proxy(socks.SOCKS4, ip, port, username=username)
            else:  # HTTP/HTTPS
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            sock.settimeout(10)  # 10 second timeout
            
            if proxy_type.startswith('HTTP'):
                # For HTTP proxies, test by connecting to proxy
                sock.connect((ip, port))
            else:
                # For SOCKS, test by connecting through proxy to target
                sock.connect((self.test_host, self.test_port))
            
            sock.close()
            
            response_time = time.time() - start_time
            self.test_completed.emit(self.row, True, f"Connected ({response_time:.2f}s)", response_time)
            
        except Exception as e:
            response_time = time.time() - start_time
            self.test_completed.emit(self.row, False, str(e), response_time)

class ProxyManagerImproved(BaseManager):
    """Improved Proxy Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="proxy",
            data_subdir="proxies",
            file_extension=".xlsx",
            parent=parent
        )
        
        # Proxy-specific headers
        self.default_headers = [
            "Proxy", "Type", "Country", "Speed", "Status", 
            "Last Tested", "Response Time", "Success Rate", "Notes"
        ]
        
        self.test_workers = {}  # Track test workers
    
    def _create_toolbar(self):
        """Create proxy-specific toolbar"""
        toolbar_layout = super()._create_toolbar()
        
        # Add proxy-specific controls
        
        # Test target configuration
        test_config_layout = QHBoxLayout()
        test_config_layout.addWidget(QLabel("Test Target:"))
        
        self.test_host_combo = QComboBox()
        self.test_host_combo.addItems([
            "smtp.gmail.com:587",
            "smtp.outlook.com:587", 
            "smtp.yahoo.com:587",
            "google.com:80",
            "httpbin.org:80"
        ])
        self.test_host_combo.setToolTip("Select target host:port for proxy testing")
        test_config_layout.addWidget(self.test_host_combo)
        
        # Test buttons
        btn_test_all = QPushButton("🧪 Test All Proxies")
        btn_test_all.setToolTip("Test all proxy connections")
        btn_test_all.clicked.connect(self._test_all_proxies)
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
        btn_test_selected.setToolTip("Test selected proxy connection")
        btn_test_selected.clicked.connect(self._test_selected_proxy)
        
        # Insert before the stretch
        toolbar_layout.insertLayout(toolbar_layout.count() - 2, test_config_layout)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_test_all)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_test_selected)
        
        return toolbar_layout
    
    def _create_new_list_structure(self, list_name: str):
        """Create new proxy list structure"""
        # Create folder for proxy list
        list_folder = os.path.join(self.data_dir, list_name)
        os.makedirs(list_folder, exist_ok=True)
        
        # Create Excel file with default headers
        excel_path = os.path.join(list_folder, f"{list_name}.xlsx")
        
        from openpyxl import Workbook
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(self.default_headers)
        workbook.save(excel_path)
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to proxy list Excel file"""
        return os.path.join(self.data_dir, list_name, f"{list_name}.xlsx")
    
    def _create_empty_list_data(self):
        """Create empty proxy data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _add_row(self):
        """Add a new proxy row with default values"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a proxy list first!")
            return
        
        # Create new row with default values
        new_row = ["", "HTTP", "", "", "Untested", "", "", "", ""]
        self.current_data.append(new_row)
        
        # Update table
        self._update_table()
        
        # Select the new row and focus on proxy field
        new_row_index = len(self.current_data) - 1
        self.table_widget.selectRow(new_row_index)
        self.table_widget.scrollToItem(self.table_widget.item(new_row_index, 0))
        
        # Focus on proxy field for editing
        proxy_item = self.table_widget.item(new_row_index, 0)
        if proxy_item:
            self.table_widget.setCurrentItem(proxy_item)
            self.table_widget.editItem(proxy_item)
    
    def _test_all_proxies(self):
        """Test all proxy connections in current list"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No proxy configurations to test!")
            return
        
        # Get test target
        test_target = self.test_host_combo.currentText()
        host, port = test_target.split(':')
        port = int(port)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.current_data))
        self.progress_bar.setValue(0)
        
        # Start test workers for each proxy
        for row, proxy_data in enumerate(self.current_data):
            if len(proxy_data) > 0:
                proxy_config = {
                    'proxy': proxy_data[0] if len(proxy_data) > 0 else '',
                    'type': proxy_data[1] if len(proxy_data) > 1 else 'HTTP',
                }
                
                worker = ProxyTestWorker(proxy_config, row, host, port)
                worker.test_completed.connect(self._on_proxy_test_completed)
                self.test_workers[row] = worker
                worker.start()
    
    def _test_selected_proxy(self):
        """Test selected proxy connection"""
        current_row = self.table_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select a proxy configuration to test!")
            return
        
        if current_row >= len(self.current_data):
            return
        
        # Get test target
        test_target = self.test_host_combo.currentText()
        host, port = test_target.split(':')
        port = int(port)
        
        proxy_data = self.current_data[current_row]
        proxy_config = {
            'proxy': proxy_data[0] if len(proxy_data) > 0 else '',
            'type': proxy_data[1] if len(proxy_data) > 1 else 'HTTP',
        }
        
        worker = ProxyTestWorker(proxy_config, current_row, host, port)
        worker.test_completed.connect(self._on_proxy_test_completed)
        self.test_workers[current_row] = worker
        worker.start()
        
        # Update status to "Testing..."
        if len(proxy_data) > 4:
            proxy_data[4] = "Testing..."
            status_item = QTableWidgetItem("Testing...")
            self.table_widget.setItem(current_row, 4, status_item)
    
    def _on_proxy_test_completed(self, row: int, success: bool, message: str, response_time: float):
        """Handle proxy test completion"""
        if row < len(self.current_data):
            # Update data
            if len(self.current_data[row]) >= 9:
                self.current_data[row][4] = "✅ Working" if success else "❌ Failed"  # Status
                self.current_data[row][5] = self._get_current_timestamp()  # Last tested
                self.current_data[row][6] = f"{response_time:.2f}s"  # Response time
                
                # Update success rate (simplified)
                if self.current_data[row][7]:  # If success rate exists
                    try:
                        current_rate = float(self.current_data[row][7].replace('%', ''))
                        # Simple moving average (you could make this more sophisticated)
                        new_rate = (current_rate + (100 if success else 0)) / 2
                        self.current_data[row][7] = f"{new_rate:.1f}%"
                    except:
                        self.current_data[row][7] = "100%" if success else "0%"
                else:
                    self.current_data[row][7] = "100%" if success else "0%"
            
            # Update table
            status_item = QTableWidgetItem("✅ Working" if success else "❌ Failed")
            if success:
                status_item.setBackground(Qt.GlobalColor.green)
            else:
                status_item.setBackground(Qt.GlobalColor.red)
                status_item.setToolTip(message)
            
            self.table_widget.setItem(row, 4, status_item)
            
            # Update other columns
            if self.table_widget.columnCount() > 5:
                timestamp_item = QTableWidgetItem(self._get_current_timestamp())
                self.table_widget.setItem(row, 5, timestamp_item)
                
                response_item = QTableWidgetItem(f"{response_time:.2f}s")
                self.table_widget.setItem(row, 6, response_item)
        
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
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _update_table(self):
        """Update table with proxy-specific formatting"""
        super()._update_table()
        
        # Apply proxy-specific formatting
        for row in range(self.table_widget.rowCount()):
            # Color-code status column
            if self.table_widget.columnCount() > 4:
                status_item = self.table_widget.item(row, 4)
                if status_item:
                    status_text = status_item.text()
                    if "Working" in status_text or "✅" in status_text:
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif "Failed" in status_text or "❌" in status_text:
                        status_item.setBackground(Qt.GlobalColor.red)
                    elif "Testing" in status_text:
                        status_item.setBackground(Qt.GlobalColor.yellow)
            
            # Color-code response time
            if self.table_widget.columnCount() > 6:
                response_item = self.table_widget.item(row, 6)
                if response_item:
                    try:
                        response_time = float(response_item.text().replace('s', ''))
                        if response_time < 1.0:
                            response_item.setBackground(Qt.GlobalColor.green)  # Fast
                        elif response_time < 3.0:
                            response_item.setBackground(Qt.GlobalColor.yellow)  # Medium
                        else:
                            response_item.setBackground(Qt.GlobalColor.red)  # Slow
                    except:
                        pass
    
    def _on_operation_completed(self, result: dict):
        """Handle completed operations with proxy-specific processing"""
        super()._on_operation_completed(result)
        
        # Additional proxy processing
        if 'data' in result and result.get('manager_type') == 'proxy':
            # Validate proxy format
            self._validate_proxy_data()
    
    def _validate_proxy_data(self):
        """Validate proxy data and highlight issues"""
        if not self.current_data:
            return
        
        for row in range(self.table_widget.rowCount()):
            # Check proxy field (column 0)
            proxy_item = self.table_widget.item(row, 0)
            if proxy_item:
                proxy = proxy_item.text().strip()
                if not proxy:
                    proxy_item.setBackground(Qt.GlobalColor.red)
                    proxy_item.setToolTip("Proxy address is required")
                elif ':' not in proxy:
                    proxy_item.setBackground(Qt.GlobalColor.yellow)
                    proxy_item.setToolTip("Proxy should be in format IP:PORT or IP:PORT:USER:PASS")
                else:
                    proxy_item.setBackground(Qt.GlobalColor.white)
                    proxy_item.setToolTip("")