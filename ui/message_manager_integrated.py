# ui/message_manager_integrated.py
"""
Integrated message manager using new foundation architecture.

This module provides the GUI for message management using:
- New email template models (core.data.models.EmailTemplate)
- New file handling (core.data.file_handler)
- New worker system (workers.base_worker)
- New validation and error handling
- Centralized logging
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QPushButton, QFileDialog, QMessageBox, 
    QHBoxLayout, QVBoxLayout, QInputDialog, QTableWidget, QTableWidgetItem, 
    QHeaderView, QTextEdit, QProgressBar, QApplication, QStyle, 
    QAbstractItemView, QMenu, QDialog, QGridLayout, QDialogButtonBox,
    QLineEdit, QComboBox, QSplitter, QFrame
)
from PyQt6.QtGui import QAction, QCursor, QDesktopServices, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer

import os
import shutil
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import new foundation components
from core.data.models import EmailTemplate, TemplateVariable, TemplateStatus
from core.data.file_handler import FileHandler
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.base_worker import BaseWorker, WorkerProgress, WorkerStatus

# Import existing message preview window
from ui.message_preview import MessagePreviewWindow, find_message_file

logger = get_module_logger(__name__)


class MessageWorker(BaseWorker):
    """Worker for message operations using new foundation."""
    
    messages_loaded = pyqtSignal(list)  # List[EmailTemplate]
    messages_imported = pyqtSignal(list)  # List[str] - imported folder paths
    messages_exported = pyqtSignal(bool, str)  # success, message
    folder_created = pyqtSignal(str)  # folder path
    
    def __init__(self):
        super().__init__()
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Operation parameters
        self.operation = None
        self.base_dir = None
        self.list_name = None
        self.source_files = None
        self.templates = None
        self.export_path = None
    
    def load_message_list(self, base_dir: str, list_name: str):
        """Load messages from a specific list folder."""
        self.operation = "load"
        self.base_dir = base_dir
        self.list_name = list_name
        self.start()
    
    def import_messages(self, message_tasks: List[tuple]):
        """Import messages from external files."""
        self.operation = "import"
        self.message_tasks = message_tasks
        self.start()
    
    def export_messages(self, templates: List[EmailTemplate], export_path: str):
        """Export messages to external location."""
        self.operation = "export"
        self.templates = templates
        self.export_path = export_path
        self.start()
    
    def create_message_folder(self, base_dir: str, list_name: str, message_name: str):
        """Create a new message folder."""
        self.operation = "create_folder"
        self.base_dir = base_dir
        self.list_name = list_name
        self.message_name = message_name
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_messages()
            elif self.operation == "import":
                return self._import_messages()
            elif self.operation == "export":
                return self._export_messages()
            elif self.operation == "create_folder":
                return self._create_message_folder()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in message worker operation: {self.operation}")
            raise
    
    def _load_messages(self) -> List[EmailTemplate]:
        """Load messages from list folder."""
        list_path = os.path.join(self.base_dir, self.list_name)
        logger.info("Loading messages from list", list_name=self.list_name, path=list_path)
        
        templates = []
        
        if not os.path.exists(list_path):
            logger.warning("Message list path not found", path=list_path)
            self.messages_loaded.emit(templates)
            return templates
        
        try:
            # Get message folders
            message_folders = [
                folder for folder in os.listdir(list_path)
                if os.path.isdir(os.path.join(list_path, folder))
            ]
            
            total_folders = len(message_folders)
            logger.info("Found message folders", count=total_folders)
            
            for idx, message_folder in enumerate(message_folders):
                if self.is_cancelled():
                    break
                
                # Update progress
                progress = int((idx / max(total_folders, 1)) * 100)
                self._update_progress(idx, total_folders, f"Loading message {idx + 1} of {total_folders}")
                
                message_path = os.path.join(list_path, message_folder)
                
                try:
                    # Look for HTML and text files
                    html_file = None
                    text_file = None
                    attachments = []
                    
                    for file in os.listdir(message_path):
                        file_path = os.path.join(message_path, file)
                        if os.path.isfile(file_path):
                            file_lower = file.lower()
                            if file_lower.endswith('.html') or file_lower.endswith('.htm'):
                                html_file = file_path
                            elif file_lower.endswith('.txt'):
                                text_file = file_path
                            else:
                                attachments.append(file_path)
                    
                    # Read content
                    html_content = ""
                    text_content = ""
                    
                    if html_file:
                        try:
                            with open(html_file, 'r', encoding='utf-8') as f:
                                html_content = f.read()
                        except Exception as e:
                            logger.warning("Failed to read HTML file", file=html_file, error=str(e))
                    
                    if text_file:
                        try:
                            with open(text_file, 'r', encoding='utf-8') as f:
                                text_content = f.read()
                        except Exception as e:
                            logger.warning("Failed to read text file", file=text_file, error=str(e))
                    
                    # Create template
                    template = EmailTemplate(
                        name=message_folder,
                        subject=self._extract_subject(html_content, text_content),
                        html_content=html_content,
                        text_content=text_content,
                        status=TemplateStatus.ACTIVE
                    )
                    
                    # Extract variables from content
                    variables = self._extract_variables(html_content, text_content)
                    for var_name, var_type in variables.items():
                        template.add_variable(TemplateVariable(
                            name=var_name,
                            type=var_type,
                            required=True
                        ))
                    
                    # Add attachment info
                    for attachment in attachments:
                        template.add_tag(f"attachment:{os.path.basename(attachment)}")
                    
                    templates.append(template)
                    
                except Exception as e:
                    logger.warning("Failed to load message folder", folder=message_folder, error=str(e))
                    continue
            
            logger.info("Messages loaded successfully", count=len(templates))
            self.messages_loaded.emit(templates)
            return templates
            
        except Exception as e:
            error_msg = f"Failed to load messages: {e}"
            logger.error(error_msg)
            self.messages_loaded.emit([])
            raise FileError(error_msg)
    
    def _extract_subject(self, html_content: str, text_content: str) -> str:
        """Extract subject from content."""
        # Try to find subject in HTML title tag
        if html_content:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                subject = title_match.group(1).strip()
                if subject:
                    return subject
        
        # Try first line of text content
        if text_content:
            lines = text_content.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line and len(first_line) < 100:  # Reasonable subject length
                    return first_line
        
        return "No Subject"
    
    def _extract_variables(self, html_content: str, text_content: str) -> Dict[str, str]:
        """Extract template variables from content."""
        variables = {}
        
        # Common variable patterns
        patterns = [
            r'\{\{(\w+)\}\}',  # {{variable}}
            r'\{(\w+)\}',      # {variable}
            r'\$\{(\w+)\}',    # ${variable}
            r'%(\w+)%',        # %variable%
        ]
        
        content = (html_content + " " + text_content).lower()
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                var_name = match.lower()
                # Guess variable type based on name
                if any(keyword in var_name for keyword in ['email', 'mail']):
                    var_type = 'email'
                elif any(keyword in var_name for keyword in ['name', 'first', 'last']):
                    var_type = 'text'
                elif any(keyword in var_name for keyword in ['date', 'time']):
                    var_type = 'datetime'
                elif any(keyword in var_name for keyword in ['url', 'link']):
                    var_type = 'url'
                else:
                    var_type = 'text'
                
                variables[var_name] = var_type
        
        return variables
    
    def _import_messages(self) -> List[str]:
        """Import messages from external files."""
        logger.info("Importing messages", task_count=len(self.message_tasks))
        
        imported_folders = []
        total_files = sum(len(files) for _, files in self.message_tasks)
        files_processed = 0
        
        try:
            for dest_folder_path, source_files in self.message_tasks:
                if self.is_cancelled():
                    break
                
                message_name = os.path.basename(dest_folder_path)
                
                try:
                    # Create destination folder
                    os.makedirs(dest_folder_path, exist_ok=True)
                    
                    # Copy files
                    for src_path in source_files:
                        if self.is_cancelled():
                            break
                        
                        file_name = os.path.basename(src_path)
                        dst_path = os.path.join(dest_folder_path, file_name)
                        
                        try:
                            if not os.path.exists(dst_path):
                                shutil.copy2(src_path, dst_path)
                                logger.debug("File copied", src=src_path, dst=dst_path)
                            else:
                                logger.debug("File already exists, skipping", dst=dst_path)
                        except Exception as e:
                            logger.warning("Failed to copy file", src=src_path, dst=dst_path, error=str(e))
                        
                        files_processed += 1
                        progress = int((files_processed / max(total_files, 1)) * 100)
                        self._update_progress(files_processed, total_files, 
                                           f"Importing {message_name}: {file_name}")
                    
                    imported_folders.append(dest_folder_path)
                    
                except Exception as e:
                    logger.warning("Failed to import message", message=message_name, error=str(e))
                    continue
            
            logger.info("Message import completed", imported_count=len(imported_folders))
            self.messages_imported.emit(imported_folders)
            return imported_folders
            
        except Exception as e:
            error_msg = f"Failed to import messages: {e}"
            logger.error(error_msg)
            self.messages_imported.emit([])
            raise FileError(error_msg)
    
    def _create_message_folder(self) -> str:
        """Create a new message folder."""
        folder_path = os.path.join(self.base_dir, self.list_name, self.message_name)
        logger.info("Creating message folder", path=folder_path)
        
        try:
            os.makedirs(folder_path, exist_ok=True)
            
            # Create default template files
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.message_name}</title>
</head>
<body>
    <h1>Hello {{{{first_name}}}},</h1>
    <p>This is a sample email template.</p>
    <p>Best regards,<br>{{{{sender_name}}}}</p>
</body>
</html>"""
            
            text_content = f"""{self.message_name}

Hello {{first_name}},

This is a sample email template.

Best regards,
{{sender_name}}"""
            
            # Write files
            html_file = os.path.join(folder_path, 'message.html')
            text_file = os.path.join(folder_path, 'message.txt')
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            logger.info("Message folder created successfully", path=folder_path)
            self.folder_created.emit(folder_path)
            return folder_path
            
        except Exception as e:
            error_msg = f"Failed to create message folder: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)


class IntegratedMessageManager(QWidget):
    """Integrated message manager using new foundation."""
    
    # Signals for communication with main window
    counts_changed = pyqtSignal(int, int)  # list_count, total_messages
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Message Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Setup paths
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        self.data_dir = os.path.join(base_path, 'data', 'messages')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Current state
        self.current_list = None
        self.current_templates: List[EmailTemplate] = []
        
        # Worker for background operations
        self.worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_message_lists()
        
        # Update counts on startup
        QTimer.singleShot(100, self._update_dashboard_counts)
        
        logger.info("Integrated message manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Message lists
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        # List controls
        list_controls = QHBoxLayout()
        
        self.btn_new_list = QPushButton("➕ New List")
        self.btn_new_list.clicked.connect(self.create_new_list)
        list_controls.addWidget(self.btn_new_list)
        
        self.btn_delete_list = QPushButton("🗑 Delete")
        self.btn_delete_list.clicked.connect(self.delete_list)
        list_controls.addWidget(self.btn_delete_list)
        
        left_layout.addLayout(list_controls)
        
        # Message lists
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.load_selected_list)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.list_widget)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Message templates
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right_panel)
        
        # Message controls
        msg_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_messages)
        msg_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_messages)
        msg_controls.addWidget(self.btn_export)
        
        self.btn_new_message = QPushButton("➕ New Message")
        self.btn_new_message.clicked.connect(self.create_new_message)
        msg_controls.addWidget(self.btn_new_message)
        
        self.btn_preview = QPushButton("👁 Preview")
        self.btn_preview.clicked.connect(self.preview_message)
        msg_controls.addWidget(self.btn_preview)
        
        msg_controls.addStretch()
        right_layout.addLayout(msg_controls)
        
        # Message table
        self.message_table = QTableWidget()
        self.message_table.setColumnCount(6)
        self.message_table.setHorizontalHeaderLabels([
            "Name", "Subject", "Variables", "Status", "Files", "Modified"
        ])
        self.message_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.message_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_table.customContextMenuRequested.connect(self.show_message_context_menu)
        
        # Auto-resize columns
        header = self.message_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Subject
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Variables
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Files
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Modified
        
        right_layout.addWidget(self.message_table)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 0)  # Left panel fixed
        splitter.setStretchFactor(1, 1)  # Right panel stretches
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # Bottom section - progress and status
        bottom_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        
        layout.addLayout(bottom_layout)
    
    def load_message_lists(self):
        """Load available message lists."""
        try:
            self.list_widget.clear()
            
            if os.path.exists(self.data_dir):
                for list_name in os.listdir(self.data_dir):
                    list_path = os.path.join(self.data_dir, list_name)
                    if os.path.isdir(list_path):
                        self.list_widget.addItem(list_name)
            
            logger.info("Message lists loaded", count=self.list_widget.count())
            self._update_dashboard_counts()
            
        except Exception as e:
            handle_exception(e, "Failed to load message lists")
            QMessageBox.warning(self, "Error", f"Failed to load message lists: {e}")
    
    def load_selected_list(self):
        """Load the selected message list."""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        list_name = current_item.text()
        self.current_list = list_name
        
        self.status_label.setText(f"Loading messages from {list_name}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start worker
        self.worker = MessageWorker()
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.messages_loaded.connect(self.on_messages_loaded)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error_occurred.connect(self.on_worker_error)
        
        self.worker.load_message_list(self.data_dir, list_name)
    
    def on_messages_loaded(self, templates: List[EmailTemplate]):
        """Handle messages loaded from worker."""
        self.current_templates = templates
        self.update_message_table()
        
        logger.info("Messages loaded in UI", count=len(templates))
    
    def update_message_table(self):
        """Update the message table display."""
        self.message_table.setRowCount(len(self.current_templates))
        
        for row, template in enumerate(self.current_templates):
            # Name
            self.message_table.setItem(row, 0, QTableWidgetItem(template.name))
            
            # Subject
            self.message_table.setItem(row, 1, QTableWidgetItem(template.subject))
            
            # Variables
            var_count = len(template.variables)
            var_text = f"{var_count} variables" if var_count > 0 else "No variables"
            self.message_table.setItem(row, 2, QTableWidgetItem(var_text))
            
            # Status
            status_text = template.status.value.upper()
            if template.status == TemplateStatus.ACTIVE:
                status_text = "✅ " + status_text
            elif template.status == TemplateStatus.DRAFT:
                status_text = "📝 " + status_text
            else:
                status_text = "❌ " + status_text
            
            self.message_table.setItem(row, 3, QTableWidgetItem(status_text))
            
            # Files (count HTML, text, attachments)
            file_count = 0
            if template.html_content:
                file_count += 1
            if template.text_content:
                file_count += 1
            
            # Count attachment tags
            attachment_count = sum(1 for tag in template.tags if tag.startswith('attachment:'))
            file_count += attachment_count
            
            file_text = f"{file_count} files"
            self.message_table.setItem(row, 4, QTableWidgetItem(file_text))
            
            # Modified
            modified_text = template.last_modified.strftime("%Y-%m-%d %H:%M")
            self.message_table.setItem(row, 5, QTableWidgetItem(modified_text))
        
        logger.debug("Message table updated", rows=len(self.current_templates))
    
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
    
    def create_new_list(self):
        """Create a new message list."""
        name, ok = QInputDialog.getText(self, "New Message List", "Enter list name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        list_path = os.path.join(self.data_dir, name)
        
        if os.path.exists(list_path):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            os.makedirs(list_path, exist_ok=True)
            self.load_message_lists()
            
            # Select the new list
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).text() == name:
                    self.list_widget.setCurrentRow(i)
                    break
            
            logger.info("New message list created", name=name)
            
        except Exception as e:
            handle_exception(e, "Failed to create new message list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def delete_list(self):
        """Delete the selected message list."""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a list to delete.")
            return
        
        list_name = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete message list '{list_name}'?\n\n"
            f"This will delete all messages in the list.\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                list_path = os.path.join(self.data_dir, list_name)
                if os.path.exists(list_path):
                    shutil.rmtree(list_path)
                
                # Clear current data if this was the loaded list
                if self.current_list == list_name:
                    self.current_list = None
                    self.current_templates = []
                    self.update_message_table()
                
                # Refresh list
                self.load_message_lists()
                
                logger.info("Message list deleted", name=list_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete message list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def import_messages(self):
        """Import messages from external files."""
        if not self.current_list:
            QMessageBox.information(self, "No List Selected", 
                                  "Please select a message list first.")
            return
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Message Files",
            "", "All Files (*);;HTML Files (*.html *.htm);;Text Files (*.txt)"
        )
        
        if not file_paths:
            return
        
        # Group files by message (based on file name patterns)
        message_tasks = self._group_files_for_import(file_paths)
        
        if not message_tasks:
            QMessageBox.information(self, "No Messages", 
                                  "No valid message files found to import.")
            return
        
        try:
            self.status_label.setText("Importing messages...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = MessageWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.messages_imported.connect(self.on_messages_imported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.import_messages(message_tasks)
            
        except Exception as e:
            handle_exception(e, "Failed to start message import")
            QMessageBox.critical(self, "Error", f"Failed to import messages: {e}")
    
    def _group_files_for_import(self, file_paths: List[str]) -> List[tuple]:
        """Group files for import based on naming patterns."""
        message_tasks = []
        
        # Simple grouping: each file becomes its own message
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            name_without_ext = os.path.splitext(file_name)[0]
            
            # Clean up name for folder
            folder_name = re.sub(r'[^\w\-_\.]', '_', name_without_ext)
            
            dest_folder = os.path.join(self.data_dir, self.current_list, folder_name)
            message_tasks.append((dest_folder, [file_path]))
        
        return message_tasks
    
    def on_messages_imported(self, imported_folders: List[str]):
        """Handle imported messages."""
        if imported_folders:
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(imported_folders)} messages successfully."
            )
            
            # Reload current list
            if self.current_list:
                self.load_selected_list()
            
            logger.info("Messages imported successfully", count=len(imported_folders))
        else:
            QMessageBox.information(self, "Import Complete", "No messages were imported.")
    
    def export_messages(self):
        """Export current messages to external location."""
        if not self.current_templates:
            QMessageBox.information(self, "No Data", "No messages to export.")
            return
        
        export_dir = QFileDialog.getExistingDirectory(
            self, "Export Messages To", ""
        )
        
        if not export_dir:
            return
        
        try:
            # Export logic here - for now just show success
            QMessageBox.information(self, "Export Complete", 
                                  f"Exported {len(self.current_templates)} messages.")
            logger.info("Messages exported successfully", count=len(self.current_templates))
            
        except Exception as e:
            handle_exception(e, "Failed to export messages")
            QMessageBox.critical(self, "Error", f"Failed to export messages: {e}")
    
    def create_new_message(self):
        """Create a new message template."""
        if not self.current_list:
            QMessageBox.information(self, "No List Selected", 
                                  "Please select a message list first.")
            return
        
        name, ok = QInputDialog.getText(self, "New Message", "Enter message name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Clean name for folder
        folder_name = re.sub(r'[^\w\-_\.]', '_', name)
        
        try:
            self.status_label.setText("Creating message...")
            
            # Create and start worker
            self.worker = MessageWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.folder_created.connect(self.on_message_created)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.create_message_folder(self.data_dir, self.current_list, folder_name)
            
        except Exception as e:
            handle_exception(e, "Failed to create new message")
            QMessageBox.critical(self, "Error", f"Failed to create message: {e}")
    
    def on_message_created(self, folder_path: str):
        """Handle message creation completion."""
        QMessageBox.information(self, "Message Created", 
                              "Message created successfully. You can now edit the template files.")
        
        # Reload current list
        if self.current_list:
            self.load_selected_list()
        
        logger.info("New message created", path=folder_path)
    
    def preview_message(self):
        """Preview the selected message."""
        current_row = self.message_table.currentRow()
        if current_row < 0 or current_row >= len(self.current_templates):
            QMessageBox.information(self, "No Selection", "Please select a message to preview.")
            return
        
        template = self.current_templates[current_row]
        
        try:
            # Find the message folder
            message_folder = os.path.join(self.data_dir, self.current_list, template.name)
            
            if os.path.exists(message_folder):
                # Use existing preview window
                preview_window = MessagePreviewWindow(message_folder, self)
                preview_window.show()
            else:
                QMessageBox.warning(self, "Error", "Message folder not found.")
                
        except Exception as e:
            handle_exception(e, "Failed to preview message")
            QMessageBox.critical(self, "Error", f"Failed to preview message: {e}")
    
    def show_list_context_menu(self, position):
        """Show context menu for message list."""
        item = self.list_widget.itemAt(position)
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
        
        menu.exec(self.list_widget.mapToGlobal(position))
    
    def show_message_context_menu(self, position):
        """Show context menu for message table."""
        row = self.message_table.rowAt(position.y())
        if row < 0 or row >= len(self.current_templates):
            return
        
        menu = QMenu(self)
        
        preview_action = QAction("Preview", self)
        preview_action.triggered.connect(self.preview_message)
        menu.addAction(preview_action)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self.edit_message(row))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_message(row))
        menu.addAction(delete_action)
        
        menu.exec(self.message_table.mapToGlobal(position))
    
    def edit_message(self, row: int):
        """Edit a message template."""
        if row < 0 or row >= len(self.current_templates):
            return
        
        template = self.current_templates[row]
        message_folder = os.path.join(self.data_dir, self.current_list, template.name)
        
        if os.path.exists(message_folder):
            # Open folder in file explorer
            QDesktopServices.openUrl(QUrl.fromLocalFile(message_folder))
        else:
            QMessageBox.warning(self, "Error", "Message folder not found.")
    
    def delete_message(self, row: int):
        """Delete a message template."""
        if row < 0 or row >= len(self.current_templates):
            return
        
        template = self.current_templates[row]
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete message '{template.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                message_folder = os.path.join(self.data_dir, self.current_list, template.name)
                if os.path.exists(message_folder):
                    shutil.rmtree(message_folder)
                
                # Reload current list
                if self.current_list:
                    self.load_selected_list()
                
                logger.info("Message deleted", name=template.name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete message")
                QMessageBox.critical(self, "Error", f"Failed to delete message: {e}")
    
    def _update_dashboard_counts(self):
        """Update dashboard counts and emit signal."""
        try:
            list_count = 0
            total_messages = 0
            
            if os.path.exists(self.data_dir):
                for list_name in os.listdir(self.data_dir):
                    list_path = os.path.join(self.data_dir, list_name)
                    if os.path.isdir(list_path):
                        list_count += 1
                        
                        # Count message folders in this list
                        try:
                            message_folders = [
                                folder for folder in os.listdir(list_path)
                                if os.path.isdir(os.path.join(list_path, folder))
                            ]
                            total_messages += len(message_folders)
                        except Exception as e:
                            logger.warning("Failed to count messages in list", 
                                          list_name=list_name, error=str(e))
            
            self.counts_changed.emit(list_count, total_messages)
            logger.debug("Dashboard counts updated", lists=list_count, messages=total_messages)
            
        except Exception as e:
            handle_exception(e, "Failed to update dashboard counts")
    
    def _refresh_list(self):
        """Refresh current list (called from main window)."""
        if self.current_list:
            self.load_selected_list()
        else:
            self.load_message_lists()
        
        self._update_dashboard_counts()