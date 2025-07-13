# ui/leads_manager_integrated.py
"""
Integrated leads manager using new foundation architecture.

This module provides the GUI for leads management using:
- New data models (core.data.models.Lead)
- New file handling (core.data.file_handler)
- New worker system (workers.base_worker)
- New validation (core.validation)
- New error handling and logging
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTableWidget,
    QHeaderView, QLineEdit, QProgressBar, QMessageBox, QFileDialog, QInputDialog,
    QApplication, QTableWidgetItem, QMenu, QAbstractItemView, QStyle, QDialog,
    QComboBox, QDialogButtonBox, QGridLayout
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import new foundation components
from core.data.models import Lead, LeadStatus
from core.data.file_handler import FileHandler
from core.validation.email_validator import EmailValidator
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.base_worker import BaseWorker, WorkerProgress, WorkerStatus

logger = get_module_logger(__name__)


class LeadsWorker(BaseWorker):
    """Worker for leads operations using new foundation."""
    
    leads_loaded = pyqtSignal(list)  # List[Lead]
    leads_saved = pyqtSignal(bool, str)  # success, message
    leads_imported = pyqtSignal(list, int)  # leads, total_count
    validation_completed = pyqtSignal(dict)  # validation results
    
    def __init__(self):
        super().__init__(name="leads_worker")
        self.file_handler = FileHandler()
        self.email_validator = EmailValidator()
        self.data_validator = DataValidator()
        
        # Operation parameters
        self.operation = None
        self.file_path = None
        self.leads_data = None
        self.validation_data = None
    
    def load_leads(self, file_path: str):
        """Load leads from file."""
        self.operation = "load"
        self.file_path = file_path
        self.start()
    
    def save_leads(self, file_path: str, leads: List[Lead]):
        """Save leads to file."""
        self.operation = "save"
        self.file_path = file_path
        self.leads_data = leads
        self.start()
    
    def import_leads(self, file_path: str):
        """Import leads from Excel/CSV file."""
        self.operation = "import"
        self.file_path = file_path
        self.start()
    
    def validate_leads(self, leads: List[Lead]):
        """Validate leads data."""
        self.operation = "validate"
        self.leads_data = leads
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_leads()
            elif self.operation == "save":
                return self._save_leads()
            elif self.operation == "import":
                return self._import_leads()
            elif self.operation == "validate":
                return self._validate_leads()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in leads worker operation: {self.operation}")
            raise
    
    def _load_leads(self) -> List[Lead]:
        """Load leads from file."""
        logger.info("Loading leads from file", file_path=self.file_path)
        
        # Update progress
        self._update_progress(0, 100, "Loading leads file...")
        
        try:
            # Load data using file handler
            data = self.file_handler.load_excel(self.file_path)
            
            if not data or len(data) < 2:  # Need header + at least one row
                logger.warning("No data found in leads file")
                return []
            
            headers = data[0]
            rows = data[1:]
            
            # Find required columns
            email_col = None
            first_name_col = None
            last_name_col = None
            
            for i, header in enumerate(headers):
                header_lower = str(header).lower()
                if 'email' in header_lower:
                    email_col = i
                elif 'first' in header_lower and 'name' in header_lower:
                    first_name_col = i
                elif 'last' in header_lower and 'name' in header_lower:
                    last_name_col = i
            
            if email_col is None:
                raise ValidationError("Email column not found in file")
            
            # Convert rows to Lead objects
            leads = []
            total_rows = len(rows)
            
            for idx, row in enumerate(rows):
                if self.is_cancelled():
                    break
                
                # Update progress
                progress = int((idx / total_rows) * 90) + 10  # 10-100%
                self._update_progress(idx, total_rows, 
                                   f"Processing lead {idx + 1} of {total_rows}")
                
                try:
                    # Extract data safely
                    email = str(row[email_col]).strip() if email_col < len(row) else ""
                    first_name = str(row[first_name_col]).strip() if first_name_col is not None and first_name_col < len(row) else ""
                    last_name = str(row[last_name_col]).strip() if last_name_col is not None and last_name_col < len(row) else ""
                    
                    if not email:
                        continue  # Skip rows without email
                    
                    # Create lead
                    lead = Lead(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        status=LeadStatus.ACTIVE
                    )
                    
                    # Add custom fields for additional columns
                    for i, header in enumerate(headers):
                        if i not in [email_col, first_name_col, last_name_col] and i < len(row):
                            value = str(row[i]).strip() if row[i] else ""
                            if value:
                                lead.set_custom_field(str(header), value)
                    
                    leads.append(lead)
                    
                except Exception as e:
                    logger.warning("Error processing lead row", row_index=idx, error=str(e))
                    continue
            
            logger.info("Leads loaded successfully", count=len(leads), total_rows=total_rows)
            self.leads_loaded.emit(leads)
            return leads
            
        except Exception as e:
            error_msg = f"Failed to load leads: {e}"
            logger.error(error_msg)
            self.leads_loaded.emit([])
            raise FileError(error_msg)
    
    def _save_leads(self) -> bool:
        """Save leads to file."""
        logger.info("Saving leads to file", file_path=self.file_path, count=len(self.leads_data))
        
        try:
            # Update progress
            self._update_progress(0, 100, "Preparing leads data...")
            
            # Convert leads to tabular data
            if not self.leads_data:
                # Empty file
                data = [["Email", "First Name", "Last Name", "Status", "Created Date"]]
            else:
                # Collect all custom fields
                all_custom_fields = set()
                for lead in self.leads_data:
                    all_custom_fields.update(lead.custom_fields.keys())
                
                # Create headers
                headers = ["Email", "First Name", "Last Name", "Status", "Created Date"]
                headers.extend(sorted(all_custom_fields))
                
                # Create data rows
                data = [headers]
                total_leads = len(self.leads_data)
                
                for idx, lead in enumerate(self.leads_data):
                    if self.is_cancelled():
                        break
                    
                    # Update progress
                    progress = int((idx / total_leads) * 90) + 10
                    self._update_progress(idx, total_leads, 
                                       f"Processing lead {idx + 1} of {total_leads}")
                    
                    row = [
                        lead.email,
                        lead.first_name or "",
                        lead.last_name or "",
                        lead.status.value,
                        lead.created_date.strftime("%Y-%m-%d %H:%M:%S")
                    ]
                    
                    # Add custom fields
                    for field in sorted(all_custom_fields):
                        row.append(lead.custom_fields.get(field, ""))
                    
                    data.append(row)
            
            # Save using file handler
            self.file_handler.save_excel(self.file_path, data)
            
            logger.info("Leads saved successfully")
            self.leads_saved.emit(True, "Leads saved successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save leads: {e}"
            logger.error(error_msg)
            self.leads_saved.emit(False, error_msg)
            raise FileError(error_msg)
    
    def _import_leads(self) -> List[Lead]:
        """Import leads from external file."""
        logger.info("Importing leads from file", file_path=self.file_path)
        
        try:
            # This is similar to load but with additional validation
            leads = self._load_leads()
            
            # Additional import validation
            if leads:
                # Validate emails
                self._update_progress(90, 100, "Validating imported emails...")
                email_results = self.email_validator.validate_bulk([lead.email for lead in leads])
                
                valid_count = sum(1 for result in email_results.values() if result.is_valid)
                logger.info("Import validation completed", 
                           total=len(leads), valid_emails=valid_count)
            
            self.leads_imported.emit(leads, len(leads))
            return leads
            
        except Exception as e:
            error_msg = f"Failed to import leads: {e}"
            logger.error(error_msg)
            self.leads_imported.emit([], 0)
            raise FileError(error_msg)
    
    def _validate_leads(self) -> Dict[str, Any]:
        """Validate leads data."""
        logger.info("Validating leads", count=len(self.leads_data))
        
        try:
            results = {
                'total_leads': len(self.leads_data),
                'valid_leads': 0,
                'invalid_leads': 0,
                'email_validation': {},
                'errors': []
            }
            
            # Validate each lead
            total_leads = len(self.leads_data)
            emails_to_validate = []
            
            for idx, lead in enumerate(self.leads_data):
                if self.is_cancelled():
                    break
                
                # Update progress
                progress = int((idx / total_leads) * 50)  # First 50% for lead validation
                self._update_progress(idx, total_leads, 
                                   f"Validating lead {idx + 1} of {total_leads}")
                
                try:
                    # Basic lead validation
                    if self.data_validator.validate_lead(lead):
                        results['valid_leads'] += 1
                        emails_to_validate.append(lead.email)
                    else:
                        results['invalid_leads'] += 1
                        results['errors'].append(f"Invalid lead data: {lead.email}")
                        
                except Exception as e:
                    results['invalid_leads'] += 1
                    results['errors'].append(f"Validation error for {lead.email}: {e}")
            
            # Bulk email validation
            if emails_to_validate and not self.is_cancelled():
                self._update_progress(50, 100, "Validating email addresses...")
                email_results = self.email_validator.validate_bulk(emails_to_validate)
                results['email_validation'] = email_results
            
            logger.info("Lead validation completed", results=results)
            self.validation_completed.emit(results)
            return results
            
        except Exception as e:
            error_msg = f"Failed to validate leads: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg)


class IntegratedLeadsManager(QWidget):
    """Integrated leads manager using new foundation."""
    
    # Signals for communication with main window
    stats_updated = pyqtSignal(int, int)  # list_count, total_leads
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Leads Manager")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.leads: List[Lead] = []
        self.current_list_file = None
        
        # Worker for background operations
        self.worker = None
        
        # Setup UI
        self.setup_ui()
        self.load_leads_files()
        
        logger.info("Integrated leads manager initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Top section - file list and controls
        top_layout = QHBoxLayout()
        
        # Left side - leads files list
        left_layout = QVBoxLayout()
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search Leads Lists")
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
        
        # Leads files list
        self.leads_list = QListWidget()
        self.leads_list.itemClicked.connect(self.load_selected_list)
        self.leads_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.leads_list.customContextMenuRequested.connect(self.show_list_context_menu)
        left_layout.addWidget(self.leads_list)
        
        top_layout.addLayout(left_layout, 1)
        
        # Right side - leads table
        right_layout = QVBoxLayout()
        
        # Table controls
        table_controls = QHBoxLayout()
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.clicked.connect(self.import_leads)
        table_controls.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Export")
        self.btn_export.clicked.connect(self.export_leads)
        table_controls.addWidget(self.btn_export)
        
        self.btn_validate = QPushButton("✅ Validate")
        self.btn_validate.clicked.connect(self.validate_leads)
        table_controls.addWidget(self.btn_validate)
        
        self.btn_add_lead = QPushButton("➕ Add Lead")
        self.btn_add_lead.clicked.connect(self.add_lead)
        table_controls.addWidget(self.btn_add_lead)
        
        table_controls.addStretch()
        right_layout.addLayout(table_controls)
        
        # Leads table
        self.leads_table = QTableWidget()
        self.leads_table.setColumnCount(6)
        self.leads_table.setHorizontalHeaderLabels([
            "Email", "First Name", "Last Name", "Status", "Tags", "Created"
        ])
        self.leads_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.leads_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.leads_table.customContextMenuRequested.connect(self.show_lead_context_menu)
        self.leads_table.cellChanged.connect(self.on_lead_edited)
        
        # Enable manual column resizing
        header = self.leads_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # Allow manual resizing
        # Set reasonable default widths
        header.resizeSection(0, 200)  # Email
        header.resizeSection(1, 120)  # First Name
        header.resizeSection(2, 120)  # Last Name
        header.resizeSection(3, 80)   # Status
        header.resizeSection(4, 100)  # Tags
        header.resizeSection(5, 120)  # Created
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Tags
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Created
        
        right_layout.addWidget(self.leads_table)
        
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
    
    def load_leads_files(self):
        """Load available leads files."""
        try:
            leads_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'leads')
            os.makedirs(leads_dir, exist_ok=True)
            
            self.leads_list.clear()
            
            # Find Excel files
            for filename in os.listdir(leads_dir):
                if filename.endswith(('.xlsx', '.xls')):
                    self.leads_list.addItem(filename)
            
            logger.info("Leads files loaded", count=self.leads_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to load leads files")
            QMessageBox.warning(self, "Error", f"Failed to load leads files: {e}")
    
    def load_selected_list(self):
        """Load the selected leads list."""
        current_item = self.leads_list.currentItem()
        if not current_item:
            return
        
        filename = current_item.text()
        leads_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'leads')
        file_path = os.path.join(leads_dir, filename)
        
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found: {filename}")
            return
        
        self.load_leads_from_file(file_path)
    
    def load_leads_from_file(self, file_path: str):
        """Load leads from file using worker."""
        try:
            self.current_list_file = file_path
            self.status_label.setText("Loading leads...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = LeadsWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.leads_loaded.connect(self.on_leads_loaded)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.load_leads(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start leads loading")
            QMessageBox.critical(self, "Error", f"Failed to load leads: {e}")
    
    def on_leads_loaded(self, leads: List[Lead]):
        """Handle leads loaded from worker."""
        self.leads = leads
        self.update_leads_table()
        
        # Update stats
        list_count = self.leads_list.count()
        total_leads = len(self.leads)
        self.stats_updated.emit(list_count, total_leads)
        
        logger.info("Leads loaded in UI", count=len(leads))
    
    def update_leads_table(self):
        """Update the leads table display."""
        self.leads_table.setRowCount(len(self.leads))
        
        for row, lead in enumerate(self.leads):
            # Email
            self.leads_table.setItem(row, 0, QTableWidgetItem(lead.email))
            
            # First Name
            self.leads_table.setItem(row, 1, QTableWidgetItem(lead.first_name or ""))
            
            # Last Name
            self.leads_table.setItem(row, 2, QTableWidgetItem(lead.last_name or ""))
            
            # Status
            self.leads_table.setItem(row, 3, QTableWidgetItem(lead.status.value))
            
            # Tags
            tags_text = ", ".join(lead.tags) if lead.tags else ""
            self.leads_table.setItem(row, 4, QTableWidgetItem(tags_text))
            
            # Created
            created_text = lead.created_date.strftime("%Y-%m-%d %H:%M")
            self.leads_table.setItem(row, 5, QTableWidgetItem(created_text))
        
        logger.debug("Leads table updated", rows=len(self.leads))
    
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
        """Create a new leads list."""
        name, ok = QInputDialog.getText(self, "New Leads List", "Enter list name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        if not name.endswith(('.xlsx', '.xls')):
            name += '.xlsx'
        
        leads_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'leads')
        os.makedirs(leads_dir, exist_ok=True)  # Ensure directory exists
        file_path = os.path.join(leads_dir, name)
        
        if os.path.exists(file_path):
            QMessageBox.warning(self, "Error", "A list with this name already exists.")
            return
        
        try:
            # Create empty leads list
            self.leads = []
            self.current_list_file = file_path
            
            # Save empty file
            self.save_current_list()
            
            # Refresh file list
            self.load_leads_files()
            
            # Select the new file
            for i in range(self.leads_list.count()):
                if self.leads_list.item(i).text() == name:
                    self.leads_list.setCurrentRow(i)
                    break
            
            logger.info("New leads list created", name=name)
            
        except Exception as e:
            handle_exception(e, "Failed to create new leads list")
            QMessageBox.critical(self, "Error", f"Failed to create new list: {e}")
    
    def delete_list(self):
        """Delete the selected leads list."""
        current_item = self.leads_list.currentItem()
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
                leads_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'leads')
                file_path = os.path.join(leads_dir, filename)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Clear current data if this was the loaded file
                if self.current_list_file == file_path:
                    self.leads = []
                    self.current_list_file = None
                    self.update_leads_table()
                
                # Refresh file list
                self.load_leads_files()
                
                logger.info("Leads list deleted", filename=filename)
                
            except Exception as e:
                handle_exception(e, "Failed to delete leads list")
                QMessageBox.critical(self, "Error", f"Failed to delete list: {e}")
    
    def import_leads(self):
        """Import leads from external file."""
        # Check if a list is selected
        if not self.current_list_file:
            QMessageBox.warning(
                self, "No List Selected",
                "Please create or select a leads list first before importing."
            )
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Leads",
            "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Importing leads...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = LeadsWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.leads_imported.connect(self.on_leads_imported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.import_leads(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start leads import")
            QMessageBox.critical(self, "Error", f"Failed to import leads: {e}")
    
    def on_leads_imported(self, imported_leads: List[Lead], total_count: int):
        """Handle imported leads."""
        if imported_leads:
            # Add to current leads (avoid duplicates)
            existing_emails = {lead.email.lower() for lead in self.leads}
            new_leads = [lead for lead in imported_leads 
                        if lead.email.lower() not in existing_emails]
            
            self.leads.extend(new_leads)
            self.update_leads_table()
            
            # Auto-save if we have a current file
            if self.current_list_file:
                self.save_current_list()
            
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {len(new_leads)} new leads.\n"
                f"Skipped {len(imported_leads) - len(new_leads)} duplicates."
            )
            
            logger.info("Leads imported successfully", 
                       new_leads=len(new_leads), duplicates=len(imported_leads) - len(new_leads))
        else:
            QMessageBox.information(self, "Import Complete", "No leads were imported.")
    
    def export_leads(self):
        """Export current leads to file."""
        if not self.leads:
            QMessageBox.information(self, "No Data", "No leads to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Leads",
            f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            self.status_label.setText("Exporting leads...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = LeadsWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.leads_saved.connect(self.on_leads_exported)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_leads(file_path, self.leads)
            
        except Exception as e:
            handle_exception(e, "Failed to start leads export")
            QMessageBox.critical(self, "Error", f"Failed to export leads: {e}")
    
    def on_leads_exported(self, success: bool, message: str):
        """Handle export completion."""
        if success:
            QMessageBox.information(self, "Export Complete", "Leads exported successfully.")
            logger.info("Leads exported successfully")
        else:
            QMessageBox.critical(self, "Export Failed", f"Export failed: {message}")
    
    def validate_leads(self):
        """Validate current leads."""
        if not self.leads:
            QMessageBox.information(self, "No Data", "No leads to validate.")
            return
        
        try:
            self.status_label.setText("Validating leads...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = LeadsWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.validation_completed.connect(self.on_validation_completed)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.validate_leads(self.leads)
            
        except Exception as e:
            handle_exception(e, "Failed to start leads validation")
            QMessageBox.critical(self, "Error", f"Failed to validate leads: {e}")
    
    def on_validation_completed(self, results: Dict[str, Any]):
        """Handle validation completion."""
        total = results['total_leads']
        valid = results['valid_leads']
        invalid = results['invalid_leads']
        
        # Count valid emails
        email_results = results.get('email_validation', {})
        valid_emails = sum(1 for result in email_results.values() if result.is_valid)
        
        message = (
            f"Validation Results:\n\n"
            f"Total Leads: {total}\n"
            f"Valid Data: {valid}\n"
            f"Invalid Data: {invalid}\n"
            f"Valid Emails: {valid_emails}/{total}\n"
        )
        
        if results['errors']:
            message += f"\nErrors: {len(results['errors'])}"
            if len(results['errors']) <= 5:
                message += "\n" + "\n".join(results['errors'][:5])
            else:
                message += f"\n{results['errors'][0]}\n... and {len(results['errors']) - 1} more"
        
        QMessageBox.information(self, "Validation Results", message)
        logger.info("Leads validation completed", results=results)
    
    def add_lead(self):
        """Add a new lead manually."""
        dialog = LeadEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            lead_data = dialog.get_lead_data()
            
            try:
                lead = Lead(
                    email=lead_data['email'],
                    first_name=lead_data['first_name'],
                    last_name=lead_data['last_name'],
                    status=LeadStatus.ACTIVE
                )
                
                # Check for duplicate
                existing_emails = {l.email.lower() for l in self.leads}
                if lead.email.lower() in existing_emails:
                    QMessageBox.warning(self, "Duplicate", "A lead with this email already exists.")
                    return
                
                self.leads.append(lead)
                self.update_leads_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Lead added manually", email=lead.email)
                
            except Exception as e:
                handle_exception(e, "Failed to add lead")
                QMessageBox.critical(self, "Error", f"Failed to add lead: {e}")
    
    def save_current_list(self):
        """Save current leads to file."""
        if not self.current_list_file:
            QMessageBox.information(self, "No File", "No file selected to save to.")
            return
        
        try:
            self.status_label.setText("Saving leads...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start worker
            self.worker = LeadsWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.leads_saved.connect(self.on_leads_saved)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_leads(self.current_list_file, self.leads)
            
        except Exception as e:
            handle_exception(e, "Failed to save leads")
            QMessageBox.critical(self, "Error", f"Failed to save leads: {e}")
    
    def on_leads_saved(self, success: bool, message: str):
        """Handle save completion."""
        if success:
            logger.info("Leads saved successfully")
        else:
            QMessageBox.critical(self, "Save Failed", f"Save failed: {message}")
    
    def filter_lists(self, text: str):
        """Filter leads lists based on search text."""
        for i in range(self.leads_list.count()):
            item = self.leads_list.item(i)
            visible = text.lower() in item.text().lower()
            item.setHidden(not visible)
    
    def show_list_context_menu(self, position):
        """Show context menu for leads list."""
        item = self.leads_list.itemAt(position)
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
        
        menu.exec(self.leads_list.mapToGlobal(position))
    
    def show_lead_context_menu(self, position):
        """Show context menu for leads table."""
        row = self.leads_table.rowAt(position.y())
        if row < 0 or row >= len(self.leads):
            return
        
        menu = QMenu(self)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self.edit_lead(row))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_lead(row))
        menu.addAction(delete_action)
        
        menu.exec(self.leads_table.mapToGlobal(position))
    
    def edit_lead(self, row: int):
        """Edit a lead."""
        if row < 0 or row >= len(self.leads):
            return
        
        lead = self.leads[row]
        dialog = LeadEditDialog(self, lead)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            lead_data = dialog.get_lead_data()
            
            try:
                # Update lead
                lead.email = lead_data['email']
                lead.first_name = lead_data['first_name']
                lead.last_name = lead_data['last_name']
                lead.last_modified = datetime.now()
                
                self.update_leads_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Lead edited", email=lead.email)
                
            except Exception as e:
                handle_exception(e, "Failed to edit lead")
                QMessageBox.critical(self, "Error", f"Failed to edit lead: {e}")
    
    def delete_lead(self, row: int):
        """Delete a lead."""
        if row < 0 or row >= len(self.leads):
            return
        
        lead = self.leads[row]
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete lead '{lead.email}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                del self.leads[row]
                self.update_leads_table()
                
                # Auto-save if we have a current file
                if self.current_list_file:
                    self.save_current_list()
                
                logger.info("Lead deleted", email=lead.email)
                
            except Exception as e:
                handle_exception(e, "Failed to delete lead")
                QMessageBox.critical(self, "Error", f"Failed to delete lead: {e}")
    
    def on_lead_edited(self, row: int, column: int):
        """Handle direct table editing."""
        if row < 0 or row >= len(self.leads):
            return
        
        lead = self.leads[row]
        item = self.leads_table.item(row, column)
        value = item.text().strip() if item else ""
        
        try:
            # Update lead based on column
            if column == 0:  # Email
                lead.email = value
            elif column == 1:  # First Name
                lead.first_name = value or None
            elif column == 2:  # Last Name
                lead.last_name = value or None
            elif column == 3:  # Status
                if value.lower() in [status.value for status in LeadStatus]:
                    lead.status = LeadStatus(value.lower())
            elif column == 4:  # Tags
                lead.tags = [tag.strip() for tag in value.split(',') if tag.strip()]
            
            lead.last_modified = datetime.now()
            
            # Auto-save if we have a current file
            if self.current_list_file:
                QTimer.singleShot(1000, self.save_current_list)  # Debounced save
            
        except Exception as e:
            handle_exception(e, "Failed to update lead")
            # Revert the change
            self.update_leads_table()


class LeadEditDialog(QDialog):
    """Dialog for editing lead information."""
    
    def __init__(self, parent=None, lead: Optional[Lead] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Lead" if lead else "Add Lead")
        self.setModal(True)
        self.resize(400, 200)
        
        self.lead = lead
        self.setup_ui()
        
        if lead:
            self.load_lead_data()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QGridLayout()
        
        # Email
        form_layout.addWidget(QLabel("Email:"), 0, 0)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Enter email address")
        form_layout.addWidget(self.email_edit, 0, 1)
        
        # First Name
        form_layout.addWidget(QLabel("First Name:"), 1, 0)
        self.first_name_edit = QLineEdit()
        self.first_name_edit.setPlaceholderText("Enter first name")
        form_layout.addWidget(self.first_name_edit, 1, 1)
        
        # Last Name
        form_layout.addWidget(QLabel("Last Name:"), 2, 0)
        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Enter last name")
        form_layout.addWidget(self.last_name_edit, 2, 1)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_lead_data(self):
        """Load existing lead data into form."""
        if self.lead:
            self.email_edit.setText(self.lead.email)
            self.first_name_edit.setText(self.lead.first_name or "")
            self.last_name_edit.setText(self.lead.last_name or "")
    
    def get_lead_data(self) -> Dict[str, str]:
        """Get lead data from form."""
        return {
            'email': self.email_edit.text().strip(),
            'first_name': self.first_name_edit.text().strip(),
            'last_name': self.last_name_edit.text().strip()
        }
    
    def accept(self):
        """Validate and accept the dialog."""
        data = self.get_lead_data()
        
        if not data['email']:
            QMessageBox.warning(self, "Validation Error", "Email is required.")
            self.email_edit.setFocus()
            return
        
        # Basic email validation
        if '@' not in data['email'] or '.' not in data['email']:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid email address.")
            self.email_edit.setFocus()
            return
        
        super().accept()