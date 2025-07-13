# ui/subjects_manager_enhanced.py
"""
Enhanced Subjects Manager with Professional UI and Fixed Data Persistence
"""

from ui.enhanced_base_manager import EnhancedBaseManager
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QTableWidgetItem
import os
from core.utils.logger import get_module_logger

logger = get_module_logger(__name__)

class SubjectsManagerEnhanced(EnhancedBaseManager):
    """Enhanced Subjects Manager with professional UI and data persistence"""
    
    def __init__(self, parent=None):
        # Subjects use single column
        self.default_headers = ["Subject Line"]
        
        super().__init__(
            manager_type="Subjects",
            data_subdir="subjects", 
            file_extension=".txt",
            parent=parent
        )
    
    def _create_new_list_structure(self, list_name: str):
        """Create new subjects list structure with folder and text file"""
        try:
            # Create folder for the list
            list_folder = os.path.join(self.data_dir, list_name)
            os.makedirs(list_folder, exist_ok=True)
            
            # Create text file
            txt_path = os.path.join(list_folder, f"{list_name}.txt")
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("")  # Empty file
            
            logger.info(f"Created subjects list structure: {list_folder}")
            
        except Exception as e:
            logger.error(f"Failed to create subjects list structure: {str(e)}")
            raise e
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to subjects list text file"""
        return os.path.join(self.data_dir, list_name, f"{list_name}.txt")
    
    def _load_list_data(self, list_name: str):
        """Load subjects data from text file"""
        try:
            data_path = self._get_list_data_path(list_name)
            
            if not os.path.exists(data_path):
                self._create_empty_list_data()
                return
            
            # Load from text file
            with open(data_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Set headers
            self.headers = self.default_headers.copy()
            
            # Read data
            self.current_data = []
            for line in lines:
                line = line.strip()
                if line:  # Skip empty lines
                    self.current_data.append([line])
            
            self._update_table_display()
            
            logger.info(f"Loaded subjects list: {list_name} ({len(self.current_data)} subjects)")
            
        except Exception as e:
            logger.error(f"Failed to load subjects data: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load subjects data:\n{str(e)}")
            self._create_empty_list_data()
    
    def _create_empty_list_data(self):
        """Create empty subjects data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table_display()
    
    def _save_current_data(self):
        """Save current subjects data to text file"""
        if not self.current_list_name:
            return
        
        try:
            data_path = self._get_list_data_path(self.current_list_name)
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            
            self._collect_table_data()
            
            # Save to text file
            with open(data_path, 'w', encoding='utf-8') as f:
                for row_data in self.current_data:
                    if row_data and row_data[0].strip():  # Only save non-empty lines
                        f.write(row_data[0].strip() + '\n')
            
            logger.info(f"Saved subjects data: {self.current_list_name} ({len(self.current_data)} subjects)")
            
        except Exception as e:
            logger.error(f"Failed to save subjects data: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save subjects data:\n{str(e)}")
    
    def _collect_table_data(self):
        """Collect current data from table widget"""
        if not self.table_widget:
            return
        
        self.current_data = []
        for row_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row_idx, 0)
            if item and item.text().strip():
                self.current_data.append([item.text().strip()])
    
    def _import_data(self):
        """Import subjects data from text file"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a subjects list first!")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Subjects Data",
            "", "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            
            imported_subjects = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line:  # Skip empty lines
                    imported_subjects.append([line])
            
            # Ask about merge or replace
            if self.current_data:
                reply = QMessageBox.question(
                    self, "Import Options",
                    f"Found {len(imported_subjects)} subjects to import.\n\n"
                    f"Current list has {len(self.current_data)} subjects.\n\n"
                    f"Replace existing data?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                elif reply == QMessageBox.StandardButton.Yes:
                    self.current_data = []
            
            # Add imported data
            self.current_data.extend(imported_subjects)
            
            self._update_table_display()
            
            if self.auto_save_enabled:
                self._save_current_data()
            
            self.progress_bar.setVisible(False)
            
            QMessageBox.information(
                self, "Import Successful",
                f"Successfully imported {len(imported_subjects)} subjects!"
            )
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            logger.error(f"Failed to import subjects: {str(e)}")
            QMessageBox.critical(self, "Import Error", f"Failed to import subjects:\n{str(e)}")
    
    def _export_data(self):
        """Export subjects data to text file"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No data to export!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Subjects Data",
            f"{self.current_list_name}_subjects.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, len(self.current_data))
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for idx, row_data in enumerate(self.current_data):
                    if row_data and row_data[0].strip():
                        f.write(row_data[0].strip() + '\n')
                    self.progress_bar.setValue(idx + 1)
            
            self.progress_bar.setVisible(False)
            
            QMessageBox.information(
                self, "Export Successful",
                f"Successfully exported {len(self.current_data)} subjects to:\n{file_path}"
            )
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            logger.error(f"Failed to export subjects: {str(e)}")
            QMessageBox.critical(self, "Export Error", f"Failed to export subjects:\n{str(e)}")
    
    def _list_exists(self, list_name: str) -> bool:
        """Check if subjects list exists"""
        return os.path.exists(self._get_list_data_path(list_name))
    
    def _delete_list_structure(self, list_name: str):
        """Delete subjects list structure"""
        import shutil
        list_folder = os.path.join(self.data_dir, list_name)
        if os.path.exists(list_folder):
            shutil.rmtree(list_folder)
            logger.info(f"Deleted subjects list: {list_folder}")
    
    def _rename_list(self, old_name: str, new_name: str):
        """Rename subjects list"""
        old_folder = os.path.join(self.data_dir, old_name)
        new_folder = os.path.join(self.data_dir, new_name)
        
        if os.path.exists(old_folder):
            os.rename(old_folder, new_folder)
            
            old_file = os.path.join(new_folder, f"{old_name}.txt")
            new_file = os.path.join(new_folder, f"{new_name}.txt")
            if os.path.exists(old_file):
                os.rename(old_file, new_file)
            
            logger.info(f"Renamed subjects list: {old_name} -> {new_name}")
    
    def _count_items_in_list(self, list_name: str) -> int:
        """Count subjects in a list"""
        try:
            data_path = self._get_list_data_path(list_name)
            if not os.path.exists(data_path):
                return 0
            
            with open(data_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            count = 0
            for line in lines:
                if line.strip():
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to count subjects in {list_name}: {str(e)}")
            return 0
    
    def _add_row(self):
        """Add a new subject row with focus"""
        super()._add_row()
        
        # Focus on the new subject field
        if self.table_widget.rowCount() > 0:
            last_row = self.table_widget.rowCount() - 1
            subject_item = self.table_widget.item(last_row, 0)
            if subject_item:
                self.table_widget.setCurrentItem(subject_item)
                self.table_widget.editItem(subject_item)