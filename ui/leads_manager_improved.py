# ui/leads_manager_improved.py
"""
Improved Leads Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem
from PyQt6.QtCore import Qt
import os

class LeadsManagerImproved(BaseManager):
    """Improved Leads Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="leads",
            data_subdir="leads", 
            file_extension=".xlsx",
            parent=parent
        )
        
        # Leads-specific headers
        self.default_headers = [
            "Email", "First Name", "Last Name", "Company", 
            "Phone", "Country", "Industry", "Notes"
        ]
    
    def _create_new_list_structure(self, list_name: str):
        """Create new leads list structure"""
        # Create folder for leads list
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
        """Get path to leads list Excel file"""
        return os.path.join(self.data_dir, list_name, f"{list_name}.xlsx")
    
    def _create_empty_list_data(self):
        """Create empty leads data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _add_row(self):
        """Add a new leads row with validation"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a leads list first!")
            return
        
        # Create new row with default values
        new_row = ["", "", "", "", "", "", "", ""]  # Match default headers length
        self.current_data.append(new_row)
        
        # Update table
        self._update_table()
        
        # Select the new row and focus on email field
        new_row_index = len(self.current_data) - 1
        self.table_widget.selectRow(new_row_index)
        self.table_widget.scrollToItem(self.table_widget.item(new_row_index, 0))
        
        # Focus on email field for editing
        email_item = self.table_widget.item(new_row_index, 0)
        if email_item:
            self.table_widget.setCurrentItem(email_item)
            self.table_widget.editItem(email_item)
    
    def _save_current_data(self):
        """Save current leads data to file"""
        if not self.current_list_name:
            return
        
        try:
            # Collect data from table (in case user made edits)
            self._collect_table_data()
            
            # Save using worker thread
            data_path = self._get_list_data_path(self.current_list_name)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            
            self.worker.set_operation(
                'save_excel',
                data_to_save=self.current_data,
                save_path=data_path,
                headers=self.headers
            )
            self.worker.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save leads data:\n{str(e)}")
    
    def _collect_table_data(self):
        """Collect data from table widget back to current_data"""
        self.current_data = []
        
        for row in range(self.table_widget.rowCount()):
            row_data = []
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                row_data.append(item.text() if item else "")
            self.current_data.append(row_data)
    
    def _validate_email(self, email: str) -> bool:
        """Simple email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _on_operation_completed(self, result: dict):
        """Handle completed operations with leads-specific processing"""
        super()._on_operation_completed(result)
        
        # Additional leads processing
        if 'data' in result and result.get('manager_type') == 'leads':
            # Validate email addresses and highlight invalid ones
            self._highlight_invalid_emails()
    
    def _highlight_invalid_emails(self):
        """Highlight invalid email addresses in red"""
        if not self.current_data:
            return
        
        # Assuming email is in first column (index 0)
        for row in range(self.table_widget.rowCount()):
            email_item = self.table_widget.item(row, 0)
            if email_item:
                email = email_item.text().strip()
                if email and not self._validate_email(email):
                    email_item.setBackground(Qt.GlobalColor.red)
                    email_item.setToolTip("Invalid email format")
                else:
                    email_item.setBackground(Qt.GlobalColor.white)
                    email_item.setToolTip("")