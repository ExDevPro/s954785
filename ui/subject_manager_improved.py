# ui/subject_manager_improved.py
"""
Improved Subject Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QDialog, QDialogButtonBox
from PyQt6.QtCore import Qt
import os

class SubjectPreviewDialog(QDialog):
    """Dialog for previewing/editing subjects"""
    
    def __init__(self, subjects_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subject Preview")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText('\n'.join(subjects_list))
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_subjects(self):
        """Get edited subjects list"""
        text = self.text_edit.toPlainText()
        return [line.strip() for line in text.split('\n') if line.strip()]

class SubjectManagerImproved(BaseManager):
    """Improved Subject Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="subject",
            data_subdir="subjects",
            file_extension=".txt",
            parent=parent
        )
        
        # Override table headers for subjects
        self.default_headers = ["Subject Line", "Length", "Has Variables", "Category"]
    
    def _create_toolbar(self):
        """Create subject-specific toolbar"""
        toolbar_layout = super()._create_toolbar()
        
        # Add subject-specific buttons
        btn_preview = QPushButton("👁 Preview Subjects")
        btn_preview.setToolTip("Preview all subjects in current list")
        btn_preview.clicked.connect(self._preview_subjects)
        btn_preview.setStyleSheet("""
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
        
        btn_validate = QPushButton("✓ Validate Subjects")
        btn_validate.setToolTip("Check subjects for common issues")
        btn_validate.clicked.connect(self._validate_subjects)
        
        # Insert before the stretch
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_preview)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_validate)
        
        return toolbar_layout
    
    def _create_new_list_structure(self, list_name: str):
        """Create new subject list structure"""
        # Create folder for subject list
        list_folder = os.path.join(self.data_dir, list_name)
        os.makedirs(list_folder, exist_ok=True)
        
        # Create text file
        txt_path = os.path.join(list_folder, f"{list_name}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("# Sample subject lines\nWelcome to our newsletter!\nExclusive offer just for you\n")
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to subject list text file"""
        return os.path.join(self.data_dir, list_name, f"{list_name}.txt")
    
    def _get_item_count(self, list_name: str) -> int:
        """Get the number of subjects in a list"""
        try:
            data_path = self._get_list_data_path(list_name)
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    return sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
        except Exception:
            pass
        return 0
    
    def _create_empty_list_data(self):
        """Create empty subject data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _on_operation_completed(self, result: dict):
        """Handle completed operations with subject-specific processing"""
        if 'data' in result and result.get('manager_type') == 'subject':
            # Convert text lines to table format
            subjects = result['data']
            
            # Filter out comments and empty lines
            filtered_subjects = [s for s in subjects if s.strip() and not s.strip().startswith('#')]
            
            # Convert to table format
            self.headers = self.default_headers.copy()
            self.current_data = []
            
            for subject in filtered_subjects:
                subject_data = [
                    subject,  # Subject line
                    str(len(subject)),  # Length
                    "Yes" if self._has_variables(subject) else "No",  # Has variables
                    self._categorize_subject(subject)  # Category
                ]
                self.current_data.append(subject_data)
            
            self._update_table()
            self._update_counts()
        else:
            super()._on_operation_completed(result)
    
    def _has_variables(self, subject: str) -> bool:
        """Check if subject has template variables"""
        import re
        # Look for patterns like {name}, {company}, {{variable}}, etc.
        return bool(re.search(r'\{[^}]+\}', subject))
    
    def _categorize_subject(self, subject: str) -> str:
        """Categorize subject based on content"""
        subject_lower = subject.lower()
        
        if any(word in subject_lower for word in ['offer', 'sale', 'discount', 'deal', '%', 'save']):
            return "Promotional"
        elif any(word in subject_lower for word in ['welcome', 'hello', 'hi', 'greetings']):
            return "Welcome"
        elif any(word in subject_lower for word in ['update', 'news', 'newsletter', 'announcement']):
            return "Newsletter"
        elif any(word in subject_lower for word in ['urgent', 'important', 'action required', 'expires']):
            return "Urgent"
        elif '?' in subject:
            return "Question"
        else:
            return "General"
    
    def _add_row(self):
        """Add a new subject"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a subject list first!")
            return
        
        # Create new row
        new_subject = "New Subject Line"
        new_row = [
            new_subject,
            str(len(new_subject)),
            "No",
            "General"
        ]
        self.current_data.append(new_row)
        
        # Update table
        self._update_table()
        
        # Select the new row and focus on subject field
        new_row_index = len(self.current_data) - 1
        self.table_widget.selectRow(new_row_index)
        self.table_widget.scrollToItem(self.table_widget.item(new_row_index, 0))
        
        # Focus on subject field for editing
        subject_item = self.table_widget.item(new_row_index, 0)
        if subject_item:
            self.table_widget.setCurrentItem(subject_item)
            self.table_widget.editItem(subject_item)
    
    def _preview_subjects(self):
        """Preview all subjects in a dialog"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No subjects to preview!")
            return
        
        subjects = [row[0] for row in self.current_data]
        
        dialog = SubjectPreviewDialog(subjects, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update subjects from dialog
            edited_subjects = dialog.get_subjects()
            
            # Rebuild current_data
            self.current_data = []
            for subject in edited_subjects:
                subject_data = [
                    subject,
                    str(len(subject)),
                    "Yes" if self._has_variables(subject) else "No",
                    self._categorize_subject(subject)
                ]
                self.current_data.append(subject_data)
            
            self._update_table()
    
    def _validate_subjects(self):
        """Validate subjects for common issues"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No subjects to validate!")
            return
        
        issues = []
        
        for i, row in enumerate(self.current_data):
            subject = row[0]
            
            # Check length
            if len(subject) > 50:
                issues.append(f"Row {i+1}: Subject too long ({len(subject)} chars) - may be truncated in email clients")
            
            # Check for spam triggers
            spam_words = ['free', 'urgent', 'act now', 'limited time', 'click here', 'buy now']
            if any(word in subject.lower() for word in spam_words):
                issues.append(f"Row {i+1}: Contains potential spam trigger words")
            
            # Check for all caps
            if subject.isupper() and len(subject) > 5:
                issues.append(f"Row {i+1}: All caps may trigger spam filters")
            
            # Check for empty
            if not subject.strip():
                issues.append(f"Row {i+1}: Empty subject line")
        
        if issues:
            message = "Validation Issues Found:\n\n" + "\n".join(issues[:10])
            if len(issues) > 10:
                message += f"\n\n... and {len(issues) - 10} more issues"
            QMessageBox.warning(self, "Validation Results", message)
        else:
            QMessageBox.information(self, "Validation Results", "All subjects look good! ✅")
    
    def _export_data(self):
        """Export subjects to text file"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No data to export!")
            return
        
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Subject Lines", 
            f"{self.current_list_name or 'subjects'}.txt", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Subject lines exported from {self.current_list_name or 'list'}\n")
                    f.write(f"# Total subjects: {len(self.current_data)}\n\n")
                    
                    for row in self.current_data:
                        f.write(row[0] + '\n')
                
                QMessageBox.information(self, "Success", f"Subjects exported to:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export subjects:\n{str(e)}")
    
    def _import_data(self):
        """Import subjects from file with text format support"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a subject list first!")
            return
        
        from PyQt6.QtWidgets import QFileDialog
        
        file_filter = "Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Subject Lines", 
            "", 
            file_filter
        )
        
        if file_path:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            
            # Use text import for .txt files
            if file_path.endswith('.txt'):
                operation_type = 'import_txt'
            elif file_path.endswith('.csv'):
                operation_type = 'import_csv'
            elif file_path.endswith('.xlsx'):
                operation_type = 'import_excel'
            else:
                QMessageBox.warning(self, "Error", "Unsupported file format!")
                return
            
            self.worker.set_operation(
                operation_type,
                file_path=file_path,
                manager_type=self.manager_type
            )
            self.worker.start()
    
    def _update_table(self):
        """Update table with subject-specific formatting"""
        super()._update_table()
        
        # Apply subject-specific formatting
        for row in range(self.table_widget.rowCount()):
            # Color-code length column
            if self.table_widget.columnCount() > 1:
                length_item = self.table_widget.item(row, 1)
                if length_item:
                    try:
                        length = int(length_item.text())
                        if length > 50:
                            length_item.setBackground(Qt.GlobalColor.red)
                            length_item.setToolTip("Subject line may be too long")
                        elif length < 10:
                            length_item.setBackground(Qt.GlobalColor.yellow)
                            length_item.setToolTip("Subject line may be too short")
                        else:
                            length_item.setBackground(Qt.GlobalColor.green)
                            length_item.setToolTip("Good length")
                    except:
                        pass
            
            # Color-code variables column
            if self.table_widget.columnCount() > 2:
                vars_item = self.table_widget.item(row, 2)
                if vars_item and vars_item.text() == "Yes":
                    vars_item.setBackground(Qt.GlobalColor.lightGray)
                    vars_item.setToolTip("Contains template variables")