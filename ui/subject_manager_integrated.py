# ui/subject_manager_integrated.py
"""
Integrated subject manager using new foundation architecture.

This module provides the GUI for subject management using:
- New data models (core.data.models)
- New file handling (core.data.file_handler)
- New worker system (workers.base_worker)
- New validation and error handling
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTableWidget,
    QHeaderView, QLineEdit, QProgressBar, QMessageBox, QFileDialog, QInputDialog,
    QApplication, QTableWidgetItem, QMenu, QAbstractItemView, QStyle, QDialog,
    QComboBox, QDialogButtonBox, QGridLayout, QTextEdit
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


class SubjectWorker(QObject, BaseWorker):
    """Worker for subject operations using new foundation."""
    
    subjects_loaded = pyqtSignal(list)  # List[str]
    subjects_saved = pyqtSignal(bool, str)  # success, message
    subjects_imported = pyqtSignal(list, int)  # subjects, total_count
    progress_updated = pyqtSignal(object)  # WorkerProgress
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__(name="subject_worker")
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Connect BaseWorker progress to PyQt signals
        self.add_progress_callback(self._emit_progress)
        self.add_completion_callback(self._emit_completion)
        
        # Operation parameters
        self.operation = None
        self.file_path = None
        self.subjects_data = None
    
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
                self.subjects_loaded.emit(result or [])
            elif self.operation == "save":
                self.subjects_saved.emit(True, "Subjects saved successfully")
            elif self.operation == "import":
                self.subjects_imported.emit(result or [], len(result) if result else 0)
        
        self.finished.emit()
    
    def load_subjects(self, file_path: str):
        """Load subjects from file."""
        self.operation = "load"
        self.file_path = file_path
        self.start()
    
    def save_subjects(self, file_path: str, subjects: List[str]):
        """Save subjects to file."""
        self.operation = "save"
        self.file_path = file_path
        self.subjects_data = subjects
        self.start()
    
    def import_subjects(self, file_path: str):
        """Import subjects from Excel/CSV file."""
        self.operation = "import"
        self.file_path = file_path
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_subjects()
            elif self.operation == "save":
                return self._save_subjects()
            elif self.operation == "import":
                return self._import_subjects()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in subject worker operation: {self.operation}")
            raise
    
    def _load_subjects(self) -> List[str]:
        """Load subjects from file."""
        logger.info("Loading subjects from file", file_path=self.file_path)
        
        self._update_progress(0, 100, "Loading subjects file...")
        
        try:
            if self.file_path.endswith('.json'):
                # Load from JSON
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    subjects = data.get('subjects', [])
            else:
                # Load from Excel/CSV
                data = self.file_handler.load_excel(self.file_path)
                if not data:
                    return []
                
                # Extract subjects from first column
                subjects = []
                for row in data[1:]:  # Skip header
                    if row and str(row[0]).strip():
                        subjects.append(str(row[0]).strip())
            
            self._update_progress(100, 100, f"Loaded {len(subjects)} subjects")
            logger.info("Subjects loaded successfully", count=len(subjects))
            return subjects
            
        except Exception as e:
            error_msg = f"Failed to load subjects: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _save_subjects(self) -> bool:
        """Save subjects to file."""
        logger.info("Saving subjects to file", file_path=self.file_path, count=len(self.subjects_data))
        
        self._update_progress(0, 100, "Saving subjects...")
        
        try:
            if self.file_path.endswith('.json'):
                # Save as JSON
                data = {
                    'subjects': self.subjects_data,
                    'count': len(self.subjects_data),
                    'created': datetime.now().isoformat(),
                    'version': '1.0'
                }
                
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                # Save as Excel
                excel_data = [['Subject']]  # Header
                excel_data.extend([[subject] for subject in self.subjects_data])
                
                self.file_handler.save_excel(self.file_path, excel_data)
            
            self._update_progress(100, 100, "Subjects saved successfully")
            logger.info("Subjects saved successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save subjects: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _import_subjects(self) -> List[str]:
        """Import subjects from Excel/CSV file."""
        logger.info("Importing subjects from file", file_path=self.file_path)
        
        self._update_progress(0, 100, "Importing subjects...")
        
        try:
            data = self.file_handler.load_excel(self.file_path)
            if not data or len(data) < 2:
                logger.warning("No data found in subjects file")
                return []
            
            subjects = []
            rows = data[1:]  # Skip header
            
            for idx, row in enumerate(rows):
                if self.is_cancelled():
                    break
                
                progress = int((idx / len(rows)) * 90) + 10
                self._update_progress(idx, len(rows), f"Processing subject {idx + 1} of {len(rows)}")
                
                if row and str(row[0]).strip():
                    subject = str(row[0]).strip()
                    if subject and subject not in subjects:
                        subjects.append(subject)
            
            self._update_progress(100, 100, f"Imported {len(subjects)} subjects")
            logger.info("Subjects imported successfully", count=len(subjects))
            return subjects
            
        except Exception as e:
            error_msg = f"Failed to import subjects: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)


class SubjectEditDialog(QDialog):
    """Dialog for editing/adding subjects."""
    
    def __init__(self, subject_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Subject" if subject_text else "Add Subject")
        self.setModal(True)
        self.resize(400, 150)
        
        layout = QVBoxLayout(self)
        
        # Subject input
        layout.addWidget(QLabel("Subject:"))
        self.subject_edit = QTextEdit()
        self.subject_edit.setMaximumHeight(80)
        self.subject_edit.setPlainText(subject_text)
        layout.addWidget(self.subject_edit)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_subject_text(self) -> str:
        """Get the subject text."""
        return self.subject_edit.toPlainText().strip()


class IntegratedSubjectManager(QWidget):
    """Integrated subject manager using new foundation."""
    
    # Signals for communication with main window
    stats_updated = pyqtSignal(int, int)  # list_count, total_subjects
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subject Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.subjects: List[str] = []
        self.current_list_file = None
        self.current_list_name = None
        
        # Worker for background operations
        self.worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_subject_lists()
        
        logger.info("Integrated subject manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top layout for main content
        top_layout = QHBoxLayout()
        
        # Left side - subject lists
        left_widget = QWidget()
        left_widget.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_widget)
        
        # Title
        title = QLabel("<b>Subject Lists</b>")
        left_layout.addWidget(title)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search Subject Lists")
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
        
        # Subject lists
        self.subject_list = QListWidget()
        self.subject_list.itemClicked.connect(self.load_selected_list)
        self.subject_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subject_list.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.subject_list)
        
        top_layout.addWidget(left_widget, 1)
        
        # Right side - subjects table
        right_layout = QVBoxLayout()
        
        # Table controls
        table_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_subjects)
        table_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_subjects)
        table_controls.addWidget(self.btn_export)
        
        self.btn_add_subject = QPushButton("➕ Add Subject")
        self.btn_add_subject.clicked.connect(self.add_subject)
        table_controls.addWidget(self.btn_add_subject)
        
        table_controls.addStretch()
        right_layout.addLayout(table_controls)
        
        # Subjects table
        self.subjects_table = QTableWidget()
        self.subjects_table.setColumnCount(2)
        self.subjects_table.setHorizontalHeaderLabels(["Subject", "Length"])
        self.subjects_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.subjects_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjects_table.customContextMenuRequested.connect(self.show_subject_context_menu)
        self.subjects_table.cellDoubleClicked.connect(self.edit_subject)
        
        # Enable manual column resizing
        header = self.subjects_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 400)  # Subject
        header.resizeSection(1, 80)   # Length
        
        right_layout.addWidget(self.subjects_table)
        
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
    
    def load_subject_lists(self):
        """Load available subject lists (folders and files)."""
        try:
            subjects_dir = get_data_directory('subjects')
            os.makedirs(subjects_dir, exist_ok=True)
            
            self.subject_list.clear()
            
            # Find both folders (new structure) and files (legacy)
            for item in os.listdir(subjects_dir):
                item_path = os.path.join(subjects_dir, item)
                
                if os.path.isdir(item_path):
                    # New folder structure
                    self.subject_list.addItem(item)
                elif item.endswith(('.json', '.xlsx', '.xls')):
                    # Legacy file structure
                    name = item.rsplit('.', 1)[0]
                    self.subject_list.addItem(name)
            
            logger.info("Subject lists loaded", count=self.subject_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to load subject lists")
            QMessageBox.warning(self, "Error", f"Failed to load subject lists: {e}")
    
    def create_new_list(self):
        """Create a new subject list with proper folder structure."""
        name, ok = QInputDialog.getText(self, "New Subject List", "Enter list name:")
        if not ok or not name.strip():
            return
        
        # Clean the name
        name = name.strip()
        if name.endswith(('.json', '.xlsx', '.xls')):
            name = name.rsplit('.', 1)[0]
        
        # Sanitize name for folder creation
        import re
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '_', name)
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a valid list name.")
            return
        
        subjects_dir = get_data_directory('subjects')
        os.makedirs(subjects_dir, exist_ok=True)
        
        # Create folder for this list
        list_folder = os.path.join(subjects_dir, name)
        if os.path.exists(list_folder):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            # Create list folder
            os.makedirs(list_folder, exist_ok=True)
            
            # Create the data file inside the folder
            file_path = os.path.join(list_folder, f"{name}.json")
            
            # Create empty subjects list
            self.subjects = []
            self.current_list_file = file_path
            self.current_list_name = name
            
            # Save empty file
            self.save_current_list()
            
            # Refresh list
            self.load_subject_lists()
            
            # Select the new list
            for i in range(self.subject_list.count()):
                if self.subject_list.item(i).text() == name:
                    self.subject_list.setCurrentRow(i)
                    break
            
            logger.info("New subject list created with folder", name=name, folder=list_folder)
            QMessageBox.information(self, "Success", f"Subject list '{name}' created successfully!\nFolder: {list_folder}")
            
        except Exception as e:
            handle_exception(e, "Failed to create new subject list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def load_selected_list(self):
        """Load the selected subject list."""
        current_item = self.subject_list.currentItem()
        if not current_item:
            return
        
        list_name = current_item.text()
        subjects_dir = get_data_directory('subjects')
        
        # Check folder structure (new) or file structure (legacy)
        folder_path = os.path.join(subjects_dir, list_name)
        
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
            for ext in ['.json', '.xlsx', '.xls']:
                legacy_file = os.path.join(subjects_dir, f"{list_name}{ext}")
                if os.path.exists(legacy_file):
                    file_path = legacy_file
                    self.current_list_name = list_name
                    break
        
        if not file_path:
            QMessageBox.warning(self, "Error", f"Data file not found for list: {list_name}")
            return
        
        self.load_subjects_from_file(file_path)
    
    def load_subjects_from_file(self, file_path: str):
        """Load subjects from file using worker."""
        try:
            self.current_list_file = file_path
            self.status_label.setText("Loading subjects...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = SubjectWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.subjects_loaded.connect(self.on_subjects_loaded)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.load_subjects(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start subject loading")
            QMessageBox.critical(self, "Error", f"Failed to load subjects: {e}")
    
    def on_subjects_loaded(self, subjects: List[str]):
        """Handle subjects loaded from worker."""
        self.subjects = subjects
        self.update_subjects_table()
        
        # Update stats
        list_count = self.subject_list.count()
        total_subjects = len(self.subjects)
        self.stats_updated.emit(list_count, total_subjects)
        
        logger.info("Subjects loaded in UI", count=len(subjects))
    
    def update_subjects_table(self):
        """Update the subjects table display."""
        self.subjects_table.setRowCount(len(self.subjects))
        
        for row, subject in enumerate(self.subjects):
            # Subject text
            self.subjects_table.setItem(row, 0, QTableWidgetItem(subject))
            
            # Length
            self.subjects_table.setItem(row, 1, QTableWidgetItem(str(len(subject))))
        
        logger.debug("Subjects table updated", rows=len(self.subjects))
    
    def save_current_list(self):
        """Save current subjects to file."""
        if not self.current_list_file:
            QMessageBox.information(self, "No File", "No file selected to save to.")
            return
        
        try:
            self.status_label.setText("Saving subjects...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = SubjectWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.subjects_saved.connect(self.on_subjects_saved)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_subjects(self.current_list_file, self.subjects)
            
        except Exception as e:
            handle_exception(e, "Failed to save subjects")
            QMessageBox.critical(self, "Error", f"Failed to save subjects: {e}")
    
    def on_subjects_saved(self, success: bool, message: str):
        """Handle save completion."""
        if success:
            logger.info("Subjects saved successfully")
    
    def import_subjects(self):
        """Import subjects from external file."""
        if not self.current_list_file:
            QMessageBox.warning(
                self, "No List Selected",
                "Please create or select a subject list first before importing."
            )
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Subjects",
            "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Importing subjects...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = SubjectWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.subjects_imported.connect(self.on_subjects_imported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.import_subjects(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start subject import")
            QMessageBox.critical(self, "Error", f"Failed to import subjects: {e}")
    
    def on_subjects_imported(self, imported_subjects: List[str], total_count: int):
        """Handle imported subjects."""
        if imported_subjects:
            # Add to current subjects (avoid duplicates)
            existing_subjects = set(self.subjects)
            new_subjects = [subj for subj in imported_subjects if subj not in existing_subjects]
            
            self.subjects.extend(new_subjects)
            self.update_subjects_table()
            
            # Auto-save
            if self.current_list_file:
                self.save_current_list()
            
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(new_subjects)} new subjects.\n"
                f"Skipped {len(imported_subjects) - len(new_subjects)} duplicates."
            )
            
            logger.info("Subjects imported successfully", new=len(new_subjects), duplicates=len(imported_subjects) - len(new_subjects))
    
    def export_subjects(self):
        """Export current subjects."""
        if not self.subjects:
            QMessageBox.information(self, "No Data", "No subjects to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Subjects",
            f"subjects_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;JSON Files (*.json);;Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Exporting subjects...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = SubjectWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.subjects_saved.connect(self.on_subjects_exported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_subjects(file_path, self.subjects)
            
        except Exception as e:
            handle_exception(e, "Failed to start subject export")
            QMessageBox.critical(self, "Error", f"Failed to export subjects: {e}")
    
    def on_subjects_exported(self, success: bool, message: str):
        """Handle export completion."""
        if success:
            QMessageBox.information(self, "Export Complete", "Subjects exported successfully.")
            logger.info("Subjects exported successfully")
    
    def add_subject(self):
        """Add a new subject manually."""
        dialog = SubjectEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            subject_text = dialog.get_subject_text()
            
            if not subject_text:
                QMessageBox.warning(self, "Invalid Input", "Subject cannot be empty.")
                return
            
            if subject_text in self.subjects:
                QMessageBox.warning(self, "Duplicate", "This subject already exists.")
                return
            
            try:
                self.subjects.append(subject_text)
                self.update_subjects_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Subject added manually", subject=subject_text)
                
            except Exception as e:
                handle_exception(e, "Failed to add subject")
                QMessageBox.critical(self, "Error", f"Failed to add subject: {e}")
    
    def edit_subject(self, row: int, column: int):
        """Edit a subject."""
        if row >= len(self.subjects):
            return
        
        current_subject = self.subjects[row]
        dialog = SubjectEditDialog(current_subject, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_subject = dialog.get_subject_text()
            
            if not new_subject:
                QMessageBox.warning(self, "Invalid Input", "Subject cannot be empty.")
                return
            
            if new_subject != current_subject and new_subject in self.subjects:
                QMessageBox.warning(self, "Duplicate", "This subject already exists.")
                return
            
            try:
                self.subjects[row] = new_subject
                self.update_subjects_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Subject edited", old=current_subject, new=new_subject)
                
            except Exception as e:
                handle_exception(e, "Failed to edit subject")
                QMessageBox.critical(self, "Error", f"Failed to edit subject: {e}")
    
    def delete_subject(self, row: int):
        """Delete a subject."""
        if row >= len(self.subjects):
            return
        
        subject = self.subjects[row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this subject?\n\n'{subject}'",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.subjects.pop(row)
                self.update_subjects_table()
                
                # Auto-save
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Subject deleted", subject=subject)
                
            except Exception as e:
                handle_exception(e, "Failed to delete subject")
                QMessageBox.critical(self, "Error", f"Failed to delete subject: {e}")
    
    def delete_list(self):
        """Delete the selected subject list."""
        current_item = self.subject_list.currentItem()
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
                subjects_dir = get_data_directory('subjects')
                
                # Try folder structure first
                folder_path = os.path.join(subjects_dir, list_name)
                if os.path.isdir(folder_path):
                    import shutil
                    shutil.rmtree(folder_path)
                else:
                    # Try legacy files
                    for ext in ['.json', '.xlsx', '.xls']:
                        file_path = os.path.join(subjects_dir, f"{list_name}{ext}")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            break
                
                # Clear current data if this was the loaded list
                if self.current_list_name == list_name:
                    self.subjects = []
                    self.current_list_file = None
                    self.current_list_name = None
                    self.update_subjects_table()
                
                # Refresh list
                self.load_subject_lists()
                
                logger.info("Subject list deleted", list_name=list_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete subject list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def filter_lists(self, text: str):
        """Filter the subject lists based on search text."""
        for i in range(self.subject_list.count()):
            item = self.subject_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())
    
    def show_list_context_menu(self, position):
        """Show context menu for subject lists."""
        if self.subject_list.itemAt(position):
            menu = QMenu(self)
            
            menu.addAction("Load", self.load_selected_list)
            menu.addAction("Delete", self.delete_list)
            
            menu.exec(self.subject_list.mapToGlobal(position))
    
    def show_subject_context_menu(self, position):
        """Show context menu for subjects."""
        if self.subjects_table.itemAt(position):
            row = self.subjects_table.itemAt(position).row()
            menu = QMenu(self)
            
            menu.addAction("Edit", lambda: self.edit_subject(row, 0))
            menu.addAction("Delete", lambda: self.delete_subject(row))
            
            menu.exec(self.subjects_table.mapToGlobal(position))
    
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