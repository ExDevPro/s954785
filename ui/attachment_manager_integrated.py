# ui/attachment_manager_integrated.py
"""
Integrated attachment manager using new foundation architecture.

This module provides the GUI for attachment management using:
- New data models (core.data.models)
- New file handling (core.data.file_handler)
- New worker system (workers.base_worker)
- New validation and error handling
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTableWidget,
    QHeaderView, QLineEdit, QProgressBar, QMessageBox, QFileDialog, QInputDialog,
    QApplication, QTableWidgetItem, QMenu, QAbstractItemView, QStyle, QDialog,
    QComboBox, QDialogButtonBox, QGridLayout, QTextEdit, QCheckBox, QSpinBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject

import os
import json
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import new foundation components
from core.data.file_handler import FileHandler
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.base_worker import BaseWorker, WorkerProgress, WorkerStatus

logger = get_module_logger(__name__)


class AttachmentData:
    """Data class for attachment information."""
    
    def __init__(self, file_path: str, display_name: str = None, description: str = ""):
        self.file_path = file_path
        self.display_name = display_name or os.path.basename(file_path)
        self.description = description
        self.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        self.file_extension = os.path.splitext(file_path)[1].lower()
        self.created_date = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'file_path': self.file_path,
            'display_name': self.display_name,
            'description': self.description,
            'file_size': self.file_size,
            'file_extension': self.file_extension,
            'created_date': self.created_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttachmentData':
        """Create from dictionary."""
        attachment = cls(
            file_path=data['file_path'],
            display_name=data.get('display_name'),
            description=data.get('description', '')
        )
        attachment.file_size = data.get('file_size', 0)
        attachment.file_extension = data.get('file_extension', '')
        if 'created_date' in data:
            attachment.created_date = datetime.fromisoformat(data['created_date'])
        return attachment


class AttachmentWorker(QObject, BaseWorker):
    """Worker for attachment operations using new foundation."""
    
    attachments_loaded = pyqtSignal(list)  # List[AttachmentData]
    attachments_saved = pyqtSignal(bool, str)  # success, message
    attachments_imported = pyqtSignal(list, int)  # attachments, total_count
    progress_updated = pyqtSignal(object)  # WorkerProgress
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__(name="attachment_worker")
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Connect BaseWorker progress to PyQt signals
        self.add_progress_callback(self._emit_progress)
        self.add_completion_callback(self._emit_completion)
        
        # Operation parameters
        self.operation = None
        self.file_path = None
        self.attachments_data = None
        self.source_files = None
        self.target_folder = None
    
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
                self.attachments_loaded.emit(result or [])
            elif self.operation == "save":
                self.attachments_saved.emit(True, "Attachments saved successfully")
            elif self.operation == "import":
                self.attachments_imported.emit(result or [], len(result) if result else 0)
        
        self.finished.emit()
    
    def load_attachments(self, file_path: str):
        """Load attachments from file."""
        self.operation = "load"
        self.file_path = file_path
        self.start()
    
    def save_attachments(self, file_path: str, attachments: List[AttachmentData]):
        """Save attachments to file."""
        self.operation = "save"
        self.file_path = file_path
        self.attachments_data = attachments
        self.start()
    
    def import_attachments(self, source_files: List[str], target_folder: str):
        """Import attachment files to target folder."""
        self.operation = "import"
        self.source_files = source_files
        self.target_folder = target_folder
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_attachments()
            elif self.operation == "save":
                return self._save_attachments()
            elif self.operation == "import":
                return self._import_attachments()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in attachment worker operation: {self.operation}")
            raise
    
    def _load_attachments(self) -> List[AttachmentData]:
        """Load attachments from file."""
        logger.info("Loading attachments from file", file_path=self.file_path)
        
        self._update_progress(0, 100, "Loading attachments file...")
        
        try:
            if not os.path.exists(self.file_path):
                return []
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            attachments = []
            attachment_list = data.get('attachments', [])
            
            for idx, attachment_data in enumerate(attachment_list):
                if self.is_cancelled():
                    break
                
                progress = int((idx / len(attachment_list)) * 90) + 10
                self._update_progress(idx, len(attachment_list), f"Processing attachment {idx + 1}")
                
                try:
                    attachment = AttachmentData.from_dict(attachment_data)
                    # Verify file still exists
                    if os.path.exists(attachment.file_path):
                        attachments.append(attachment)
                    else:
                        logger.warning("Attachment file not found", file_path=attachment.file_path)
                except Exception as e:
                    logger.warning("Failed to load attachment data", error=str(e))
                    continue
            
            self._update_progress(100, 100, f"Loaded {len(attachments)} attachments")
            logger.info("Attachments loaded successfully", count=len(attachments))
            return attachments
            
        except Exception as e:
            error_msg = f"Failed to load attachments: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _save_attachments(self) -> bool:
        """Save attachments to file."""
        logger.info("Saving attachments to file", file_path=self.file_path, count=len(self.attachments_data))
        
        self._update_progress(0, 100, "Saving attachments...")
        
        try:
            data = {
                'attachments': [att.to_dict() for att in self.attachments_data],
                'count': len(self.attachments_data),
                'created': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self._update_progress(100, 100, "Attachments saved successfully")
            logger.info("Attachments saved successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save attachments: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _import_attachments(self) -> List[AttachmentData]:
        """Import attachment files to target folder."""
        logger.info("Importing attachments", source_count=len(self.source_files), target=self.target_folder)
        
        self._update_progress(0, 100, "Importing attachments...")
        
        try:
            os.makedirs(self.target_folder, exist_ok=True)
            imported_attachments = []
            
            for idx, source_file in enumerate(self.source_files):
                if self.is_cancelled():
                    break
                
                progress = int((idx / len(self.source_files)) * 90) + 10
                self._update_progress(idx, len(self.source_files), f"Copying file {idx + 1}")
                
                try:
                    # Generate unique filename if necessary
                    filename = os.path.basename(source_file)
                    target_path = os.path.join(self.target_folder, filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    original_target = target_path
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(filename)
                        target_path = os.path.join(self.target_folder, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    # Copy file
                    shutil.copy2(source_file, target_path)
                    
                    # Create attachment data
                    attachment = AttachmentData(target_path)
                    imported_attachments.append(attachment)
                    
                    logger.info("File imported", source=source_file, target=target_path)
                    
                except Exception as e:
                    logger.warning("Failed to import file", file=source_file, error=str(e))
                    continue
            
            self._update_progress(100, 100, f"Imported {len(imported_attachments)} attachments")
            logger.info("Attachments imported successfully", count=len(imported_attachments))
            return imported_attachments
            
        except Exception as e:
            error_msg = f"Failed to import attachments: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)


class AttachmentEditDialog(QDialog):
    """Dialog for editing attachment properties."""
    
    def __init__(self, attachment: AttachmentData = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Attachment" if attachment else "Add Attachment")
        self.setModal(True)
        self.resize(500, 300)
        
        self.attachment = attachment
        
        layout = QVBoxLayout(self)
        
        # File path
        layout.addWidget(QLabel("File Path:"))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        if attachment:
            self.file_path_edit.setText(attachment.file_path)
        layout.addWidget(self.file_path_edit)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(browse_btn)
        
        # Display name
        layout.addWidget(QLabel("Display Name:"))
        self.display_name_edit = QLineEdit()
        if attachment:
            self.display_name_edit.setText(attachment.display_name)
        layout.addWidget(self.display_name_edit)
        
        # Description
        layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        if attachment:
            self.description_edit.setPlainText(attachment.description)
        layout.addWidget(self.description_edit)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def browse_file(self):
        """Browse for attachment file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Attachment File",
            "", "All Files (*)"
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            if not self.display_name_edit.text():
                self.display_name_edit.setText(os.path.basename(file_path))
    
    def get_attachment_data(self) -> Dict[str, str]:
        """Get the attachment data."""
        return {
            'file_path': self.file_path_edit.text().strip(),
            'display_name': self.display_name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip()
        }


class IntegratedAttachmentManager(QWidget):
    """Integrated attachment manager using new foundation."""
    
    # Signals for communication with main window
    stats_updated = pyqtSignal(int, int)  # list_count, total_attachments
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Attachment Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.attachments: List[AttachmentData] = []
        self.current_list_file = None
        self.current_list_name = None
        
        # Worker for background operations
        self.worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_attachment_lists()
        
        logger.info("Integrated attachment manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top layout for main content
        top_layout = QHBoxLayout()
        
        # Left side - attachment lists
        left_widget = QWidget()
        left_widget.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_widget)
        
        # Title
        title = QLabel("<b>Attachment Lists</b>")
        left_layout.addWidget(title)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search Attachment Lists")
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
        
        # Attachment lists
        self.attachment_list = QListWidget()
        self.attachment_list.itemClicked.connect(self.load_selected_list)
        self.attachment_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.attachment_list.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.attachment_list)
        
        top_layout.addWidget(left_widget, 1)
        
        # Right side - attachments table
        right_layout = QVBoxLayout()
        
        # Table controls
        table_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_attachments)
        table_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_attachments)
        table_controls.addWidget(self.btn_export)
        
        self.btn_add_attachment = QPushButton("➕ Add File")
        self.btn_add_attachment.clicked.connect(self.add_attachment)
        table_controls.addWidget(self.btn_add_attachment)
        
        table_controls.addStretch()
        right_layout.addLayout(table_controls)
        
        # Attachments table
        self.attachments_table = QTableWidget()
        self.attachments_table.setColumnCount(5)
        self.attachments_table.setHorizontalHeaderLabels([
            "Display Name", "File Name", "Size", "Type", "Description"
        ])
        self.attachments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attachments_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.attachments_table.customContextMenuRequested.connect(self.show_attachment_context_menu)
        self.attachments_table.cellDoubleClicked.connect(self.edit_attachment)
        
        # Enable manual column resizing
        header = self.attachments_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 150)  # Display Name
        header.resizeSection(1, 200)  # File Name
        header.resizeSection(2, 80)   # Size
        header.resizeSection(3, 80)   # Type
        header.resizeSection(4, 200)  # Description
        
        right_layout.addWidget(self.attachments_table)
        
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
    
    def load_attachment_lists(self):
        """Load available attachment lists (folders and files)."""
        try:
            attachments_dir = get_data_directory('attachments')
            os.makedirs(attachments_dir, exist_ok=True)
            
            self.attachment_list.clear()
            
            # Find both folders (new structure) and files (legacy)
            for item in os.listdir(attachments_dir):
                item_path = os.path.join(attachments_dir, item)
                
                if os.path.isdir(item_path):
                    # New folder structure
                    self.attachment_list.addItem(item)
                elif item.endswith('.json'):
                    # Legacy file structure
                    name = item.rsplit('.', 1)[0]
                    self.attachment_list.addItem(name)
            
            logger.info("Attachment lists loaded", count=self.attachment_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to load attachment lists")
            QMessageBox.warning(self, "Error", f"Failed to load attachment lists: {e}")
    
    def create_new_list(self):
        """Create a new attachment list with proper folder structure."""
        name, ok = QInputDialog.getText(self, "New Attachment List", "Enter list name:")
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
        
        attachments_dir = get_data_directory('attachments')
        os.makedirs(attachments_dir, exist_ok=True)
        
        # Create folder for this list
        list_folder = os.path.join(attachments_dir, name)
        if os.path.exists(list_folder):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            # Create list folder and files subfolder
            os.makedirs(list_folder, exist_ok=True)
            os.makedirs(os.path.join(list_folder, 'files'), exist_ok=True)
            
            # Create the data file inside the folder
            file_path = os.path.join(list_folder, f"{name}.json")
            
            # Create empty attachments list
            self.attachments = []
            self.current_list_file = file_path
            self.current_list_name = name
            
            # Save empty file
            self.save_current_list()
            
            # Refresh list
            self.load_attachment_lists()
            
            # Select the new list
            for i in range(self.attachment_list.count()):
                if self.attachment_list.item(i).text() == name:
                    self.attachment_list.setCurrentRow(i)
                    break
            
            logger.info("New attachment list created with folder", name=name, folder=list_folder)
            QMessageBox.information(self, "Success", f"Attachment list '{name}' created successfully!\nFolder: {list_folder}")
            
        except Exception as e:
            handle_exception(e, "Failed to create new attachment list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def load_selected_list(self):
        """Load the selected attachment list."""
        current_item = self.attachment_list.currentItem()
        if not current_item:
            return
        
        list_name = current_item.text()
        attachments_dir = get_data_directory('attachments')
        
        # Check folder structure (new) or file structure (legacy)
        folder_path = os.path.join(attachments_dir, list_name)
        
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
            legacy_file = os.path.join(attachments_dir, f"{list_name}.json")
            if os.path.exists(legacy_file):
                file_path = legacy_file
                self.current_list_name = list_name
        
        if not file_path:
            QMessageBox.warning(self, "Error", f"Data file not found for list: {list_name}")
            return
        
        self.load_attachments_from_file(file_path)
    
    def load_attachments_from_file(self, file_path: str):
        """Load attachments from file using worker."""
        try:
            self.current_list_file = file_path
            self.status_label.setText("Loading attachments...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = AttachmentWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.attachments_loaded.connect(self.on_attachments_loaded)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.load_attachments(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start attachment loading")
            QMessageBox.critical(self, "Error", f"Failed to load attachments: {e}")
    
    def on_attachments_loaded(self, attachments: List[AttachmentData]):
        """Handle attachments loaded from worker."""
        self.attachments = attachments
        self.update_attachments_table()
        
        # Update stats
        list_count = self.attachment_list.count()
        total_attachments = len(self.attachments)
        self.stats_updated.emit(list_count, total_attachments)
        
        logger.info("Attachments loaded in UI", count=len(attachments))
    
    def update_attachments_table(self):
        """Update the attachments table display."""
        self.attachments_table.setRowCount(len(self.attachments))
        
        for row, attachment in enumerate(self.attachments):
            # Display Name
            self.attachments_table.setItem(row, 0, QTableWidgetItem(attachment.display_name))
            
            # File Name
            filename = os.path.basename(attachment.file_path)
            self.attachments_table.setItem(row, 1, QTableWidgetItem(filename))
            
            # Size
            size_str = self.format_file_size(attachment.file_size)
            self.attachments_table.setItem(row, 2, QTableWidgetItem(size_str))
            
            # Type
            self.attachments_table.setItem(row, 3, QTableWidgetItem(attachment.file_extension))
            
            # Description
            self.attachments_table.setItem(row, 4, QTableWidgetItem(attachment.description))
        
        logger.debug("Attachments table updated", rows=len(self.attachments))
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} TB"
    
    def save_current_list(self):
        """Save current attachments to file."""
        if not self.current_list_file:
            QMessageBox.information(self, "No File", "No file selected to save to.")
            return
        
        try:
            self.status_label.setText("Saving attachments...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = AttachmentWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.attachments_saved.connect(self.on_attachments_saved)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_attachments(self.current_list_file, self.attachments)
            
        except Exception as e:
            handle_exception(e, "Failed to save attachments")
            QMessageBox.critical(self, "Error", f"Failed to save attachments: {e}")
    
    def on_attachments_saved(self, success: bool, message: str):
        """Handle save completion."""
        if success:
            logger.info("Attachments saved successfully")
    
    def import_attachments(self):
        """Import attachment files."""
        if not self.current_list_file:
            QMessageBox.warning(
                self, "No List Selected",
                "Please create or select an attachment list first before importing."
            )
            return
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Attachment Files",
            "", "All Files (*)"
        )
        
        if not file_paths:
            return
        
        # Get target folder for files
        list_folder = os.path.dirname(self.current_list_file)
        files_folder = os.path.join(list_folder, 'files')
        
        try:
            self.status_label.setText("Importing attachments...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = AttachmentWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.attachments_imported.connect(self.on_attachments_imported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.import_attachments(file_paths, files_folder)
            
        except Exception as e:
            handle_exception(e, "Failed to start attachment import")
            QMessageBox.critical(self, "Error", f"Failed to import attachments: {e}")
    
    def on_attachments_imported(self, imported_attachments: List[AttachmentData], total_count: int):
        """Handle imported attachments."""
        if imported_attachments:
            self.attachments.extend(imported_attachments)
            self.update_attachments_table()
            
            # Auto-save
            if self.current_list_file:
                self.save_current_list()
            
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(imported_attachments)} attachment files."
            )
            
            logger.info("Attachments imported successfully", count=len(imported_attachments))
    
    def add_attachment(self):
        """Add a new attachment manually."""
        dialog = AttachmentEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            attachment_data = dialog.get_attachment_data()
            
            if not attachment_data['file_path']:
                QMessageBox.warning(self, "Invalid Input", "Please select a file.")
                return
            
            if not os.path.exists(attachment_data['file_path']):
                QMessageBox.warning(self, "File Not Found", "The selected file does not exist.")
                return
            
            try:
                # Create attachment
                attachment = AttachmentData(
                    file_path=attachment_data['file_path'],
                    display_name=attachment_data['display_name'],
                    description=attachment_data['description']
                )
                
                self.attachments.append(attachment)
                self.update_attachments_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Attachment added manually", file_path=attachment.file_path)
                
            except Exception as e:
                handle_exception(e, "Failed to add attachment")
                QMessageBox.critical(self, "Error", f"Failed to add attachment: {e}")
    
    def edit_attachment(self, row: int, column: int):
        """Edit an attachment."""
        if row >= len(self.attachments):
            return
        
        attachment = self.attachments[row]
        dialog = AttachmentEditDialog(attachment, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            attachment_data = dialog.get_attachment_data()
            
            try:
                # Update attachment
                attachment.display_name = attachment_data['display_name'] or os.path.basename(attachment.file_path)
                attachment.description = attachment_data['description']
                
                # If file path changed, update it
                if attachment_data['file_path'] != attachment.file_path:
                    if os.path.exists(attachment_data['file_path']):
                        attachment.file_path = attachment_data['file_path']
                        attachment.file_size = os.path.getsize(attachment.file_path)
                        attachment.file_extension = os.path.splitext(attachment.file_path)[1].lower()
                    else:
                        QMessageBox.warning(self, "File Not Found", "The new file path does not exist.")
                        return
                
                self.update_attachments_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Attachment edited", file_path=attachment.file_path)
                
            except Exception as e:
                handle_exception(e, "Failed to edit attachment")
                QMessageBox.critical(self, "Error", f"Failed to edit attachment: {e}")
    
    def delete_attachment(self, row: int):
        """Delete an attachment."""
        if row >= len(self.attachments):
            return
        
        attachment = self.attachments[row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this attachment?\n\n'{attachment.display_name}'",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.attachments.pop(row)
                self.update_attachments_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Attachment deleted", display_name=attachment.display_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete attachment")
                QMessageBox.critical(self, "Error", f"Failed to delete attachment: {e}")
    
    def delete_list(self):
        """Delete the selected attachment list."""
        current_item = self.attachment_list.currentItem()
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
                attachments_dir = get_data_directory('attachments')
                
                # Try folder structure first
                folder_path = os.path.join(attachments_dir, list_name)
                if os.path.isdir(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)
                else:
                    # Try legacy files
                    file_path = os.path.join(attachments_dir, f"{list_name}.json")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                # Clear current data if this was the loaded list
                if self.current_list_name == list_name:
                    self.attachments = []
                    self.current_list_file = None
                    self.current_list_name = None
                    self.update_attachments_table()
                
                # Refresh list
                self.load_attachment_lists()
                
                logger.info("Attachment list deleted", list_name=list_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete attachment list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def export_attachments(self):
        """Export current attachment list metadata."""
        if not self.attachments:
            QMessageBox.information(self, "No Data", "No attachments to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Attachment List",
            f"attachments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Exporting attachments...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = AttachmentWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.attachments_saved.connect(self.on_attachments_exported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_attachments(file_path, self.attachments)
            
        except Exception as e:
            handle_exception(e, "Failed to start attachment export")
            QMessageBox.critical(self, "Error", f"Failed to export attachments: {e}")
    
    def on_attachments_exported(self, success: bool, message: str):
        """Handle export completion."""
        if success:
            QMessageBox.information(self, "Export Complete", "Attachment list exported successfully.")
            logger.info("Attachments exported successfully")
    
    def filter_lists(self, text: str):
        """Filter the attachment lists based on search text."""
        for i in range(self.attachment_list.count()):
            item = self.attachment_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())
    
    def show_list_context_menu(self, position):
        """Show context menu for attachment lists."""
        if self.attachment_list.itemAt(position):
            menu = QMenu(self)
            
            menu.addAction("Load", self.load_selected_list)
            menu.addAction("Delete", self.delete_list)
            
            menu.exec(self.attachment_list.mapToGlobal(position))
    
    def show_attachment_context_menu(self, position):
        """Show context menu for attachments."""
        if self.attachments_table.itemAt(position):
            row = self.attachments_table.itemAt(position).row()
            menu = QMenu(self)
            
            menu.addAction("Edit", lambda: self.edit_attachment(row, 0))
            menu.addAction("Delete", lambda: self.delete_attachment(row))
            
            menu.exec(self.attachments_table.mapToGlobal(position))
    
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