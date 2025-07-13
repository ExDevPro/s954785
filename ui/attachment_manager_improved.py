# ui/attachment_manager_improved.py
"""
Improved Attachment Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QPushButton, QFileDialog, QLabel
from PyQt6.QtCore import Qt
import os
import shutil

class AttachmentManagerImproved(BaseManager):
    """Improved Attachment Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="attachment",
            data_subdir="attachments",
            file_extension="",  # Folder-based
            parent=parent
        )
        
        # Attachment-specific headers
        self.default_headers = [
            "Filename", "Size", "Type", "Path", "Status", "Upload Date"
        ]
    
    def _create_toolbar(self):
        """Create attachment-specific toolbar"""
        toolbar_layout = super()._create_toolbar()
        
        # Add attachment-specific buttons
        btn_add_files = QPushButton("📎 Add Files")
        btn_add_files.setToolTip("Add attachment files to current list")
        btn_add_files.clicked.connect(self._add_attachment_files)
        btn_add_files.setStyleSheet("""
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
        
        btn_remove_files = QPushButton("🗑 Remove Files")
        btn_remove_files.setToolTip("Remove selected attachment files")
        btn_remove_files.clicked.connect(self._remove_attachment_files)
        
        # Insert before the stretch
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_add_files)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_remove_files)
        
        return toolbar_layout
    
    def _create_new_list_structure(self, list_name: str):
        """Create new attachment list structure"""
        # Create folder for attachment list
        list_folder = os.path.join(self.data_dir, list_name)
        os.makedirs(list_folder, exist_ok=True)
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to attachment list folder"""
        return os.path.join(self.data_dir, list_name)
    
    def _get_item_count(self, list_name: str) -> int:
        """Get the number of attachments in a list"""
        try:
            list_path = self._get_list_data_path(list_name)
            if os.path.isdir(list_path):
                return len([f for f in os.listdir(list_path) 
                           if os.path.isfile(os.path.join(list_path, f))])
        except Exception:
            pass
        return 0
    
    def _load_list_data(self, list_name: str):
        """Load attachment data for a specific list"""
        try:
            list_path = self._get_list_data_path(list_name)
            
            if os.path.isdir(list_path):
                self.headers = self.default_headers.copy()
                self.current_data = []
                
                # Scan files in the folder
                for filename in os.listdir(list_path):
                    file_path = os.path.join(list_path, filename)
                    if os.path.isfile(file_path):
                        try:
                            file_size = os.path.getsize(file_path)
                            file_ext = os.path.splitext(filename)[1].lower()
                            file_type = self._get_file_type(file_ext)
                            file_mtime = os.path.getmtime(file_path)
                            upload_date = self._format_timestamp(file_mtime)
                            
                            # Format file size
                            size_str = self._format_file_size(file_size)
                            
                            attachment_data = [
                                filename,           # Filename
                                size_str,          # Size  
                                file_type,         # Type
                                file_path,         # Path
                                "✅ Available",    # Status
                                upload_date        # Upload Date
                            ]
                            self.current_data.append(attachment_data)
                            
                        except Exception as e:
                            # Add error entry
                            attachment_data = [
                                filename, "Error", "Unknown", file_path, 
                                f"❌ Error: {str(e)}", "Unknown"
                            ]
                            self.current_data.append(attachment_data)
                
                self._update_table()
            else:
                # Create empty folder and data
                os.makedirs(list_path, exist_ok=True)
                self._create_empty_list_data()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load attachment data:\n{str(e)}")
            self._create_empty_list_data()
    
    def _create_empty_list_data(self):
        """Create empty attachment data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _get_file_type(self, file_ext: str) -> str:
        """Get file type from extension"""
        type_map = {
            '.pdf': 'PDF Document',
            '.doc': 'Word Document', 
            '.docx': 'Word Document',
            '.xls': 'Excel Spreadsheet',
            '.xlsx': 'Excel Spreadsheet',
            '.ppt': 'PowerPoint',
            '.pptx': 'PowerPoint',
            '.txt': 'Text Document',
            '.jpg': 'Image', '.jpeg': 'Image', '.png': 'Image', '.gif': 'Image',
            '.zip': 'Archive', '.rar': 'Archive', '.7z': 'Archive',
            '.mp3': 'Audio', '.wav': 'Audio', '.mp4': 'Video', '.avi': 'Video'
        }
        return type_map.get(file_ext, 'Unknown')
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp to readable date"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    
    def _add_attachment_files(self):
        """Add attachment files to current list"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select an attachment list first!")
            return
        
        # File dialog for multiple files
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Attachment Files",
            "",
            "All Files (*)"
        )
        
        if file_paths:
            list_path = self._get_list_data_path(self.current_list_name)
            
            successful_copies = 0
            failed_copies = []
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, len(file_paths))
            
            for i, source_path in enumerate(file_paths):
                try:
                    filename = os.path.basename(source_path)
                    dest_path = os.path.join(list_path, filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    original_dest = dest_path
                    while os.path.exists(dest_path):
                        name, ext = os.path.splitext(filename)
                        new_filename = f"{name}_{counter}{ext}"
                        dest_path = os.path.join(list_path, new_filename)
                        counter += 1
                    
                    # Copy file
                    shutil.copy2(source_path, dest_path)
                    successful_copies += 1
                    
                except Exception as e:
                    failed_copies.append(f"{filename}: {str(e)}")
                
                self.progress_bar.setValue(i + 1)
            
            self.progress_bar.setVisible(False)
            
            # Show results
            if successful_copies > 0:
                self._load_list_data(self.current_list_name)  # Refresh
                
            message = f"Successfully added {successful_copies} files."
            if failed_copies:
                message += f"\n\nFailed to add {len(failed_copies)} files:\n" + "\n".join(failed_copies[:5])
                if len(failed_copies) > 5:
                    message += f"\n... and {len(failed_copies) - 5} more"
                    
            if successful_copies > 0:
                QMessageBox.information(self, "Files Added", message)
            else:
                QMessageBox.warning(self, "Error", message)
    
    def _remove_attachment_files(self):
        """Remove selected attachment files"""
        current_row = self.table_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select an attachment to remove!")
            return
        
        if current_row >= len(self.current_data):
            return
        
        filename = self.current_data[current_row][0]
        file_path = self.current_data[current_row][3]
        
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove '{filename}' from the attachment list?\n\nThis will delete the file permanently.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Remove from data and update table
                del self.current_data[current_row]
                self._update_table()
                
                QMessageBox.information(self, "Success", f"'{filename}' removed successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove file:\n{str(e)}")
    
    def _update_table(self):
        """Update table with attachment-specific formatting"""
        super()._update_table()
        
        # Apply attachment-specific formatting
        for row in range(self.table_widget.rowCount()):
            # Color-code status column
            if self.table_widget.columnCount() > 4:
                status_item = self.table_widget.item(row, 4)
                if status_item:
                    status_text = status_item.text()
                    if "Available" in status_text or "✅" in status_text:
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif "Error" in status_text or "❌" in status_text:
                        status_item.setBackground(Qt.GlobalColor.red)
            
            # Color-code file types
            if self.table_widget.columnCount() > 2:
                type_item = self.table_widget.item(row, 2)
                if type_item:
                    file_type = type_item.text()
                    if "Image" in file_type:
                        type_item.setBackground(Qt.GlobalColor.lightGray)
                    elif "Document" in file_type:
                        type_item.setBackground(Qt.GlobalColor.cyan)
                    elif "Archive" in file_type:
                        type_item.setBackground(Qt.GlobalColor.yellow)