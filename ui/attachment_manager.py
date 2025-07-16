# Enhanced Attachment Manager with Description Support

import os
import shutil
import hashlib
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QListWidgetItem, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu,
    QFileIconProvider, QDialog, QDialogButtonBox, QTextEdit, QFrame, QSplitter,
    QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QIcon, QAction, QCursor, QDesktopServices, QFont
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QFileInfo, QUrl, QDateTime, QLocale
)
import re

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'attachments')

class CreateAttachmentListDialog(QDialog):
    """Professional dialog for creating new attachment lists with descriptions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Attachment List")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout(self)
        
        # List name
        layout.addWidget(QLabel("List Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter attachment list name...")
        layout.addWidget(self.name_edit)
        
        # Description
        layout.addWidget(QLabel("Description (Optional):"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Enter description for this attachment list...")
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.name_edit.textChanged.connect(self._validate_input)
        self._validate_input()
    
    def _validate_input(self):
        name = self.name_edit.text().strip()
        valid = bool(name and re.match(r'^[a-zA-Z0-9_\-\s]+$', name))
        self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
    
    def get_list_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip()
        }

class EnhancedAttachmentManager(QWidget):
    """Enhanced Attachment Manager with description support and professional UI."""
    
    counts_changed = pyqtSignal(int, int)
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.current_list = None
        self.current_list_path = None
        self.icon_provider = QFileIconProvider()
        
        os.makedirs(DATA_DIR, exist_ok=True)
        
        self._setup_ui()
        self._load_lists()
        self._apply_styling()
    
    def _setup_ui(self):
        """Setup the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel - Lists
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Right panel - Attachments view
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Description panel
        desc_panel = self._create_description_panel()
        splitter.addWidget(desc_panel)
        
        splitter.setSizes([600, 200])
        main_layout.addWidget(splitter, 3)
    
    def _create_left_panel(self):
        """Create the left panel with list management."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMaximumWidth(350)
        panel.setMinimumWidth(250)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("📎 Attachment Lists")
        header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("QLabel { background: #f39c12; color: white; padding: 8px; border-radius: 4px; }")
        layout.addWidget(header)
        
        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search lists...")
        self.search_edit.textChanged.connect(self._filter_lists)
        layout.addWidget(self.search_edit)
        
        # Lists
        self.attachment_lists = QListWidget()
        self.attachment_lists.itemClicked.connect(self._on_list_selected)
        self.attachment_lists.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.attachment_lists.customContextMenuRequested.connect(self._show_list_context_menu)
        layout.addWidget(self.attachment_lists)
        
        # Buttons
        buttons_layout = QVBoxLayout()
        
        self.btn_create_list = QPushButton("➕ New List")
        self.btn_create_list.clicked.connect(self._create_new_list)
        self.btn_create_list.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 8px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_create_list)
        
        self.btn_delete_list = QPushButton("🗑️ Delete List")
        self.btn_delete_list.clicked.connect(self._delete_list)
        self.btn_delete_list.setStyleSheet("QPushButton { background: #e74c3c; color: white; padding: 8px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_delete_list)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_right_panel(self):
        """Create the right panel with attachments table."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header_layout = QHBoxLayout()
        self.table_header = QLabel("📋 Attachments")
        self.table_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.table_header)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Attachments table
        self.attachment_table = QTableWidget()
        self.attachment_table.setColumnCount(5)
        self.attachment_table.setHorizontalHeaderLabels(["Icon", "File Name", "Size", "Type", "Date Added"])
        self.attachment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attachment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.attachment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.attachment_table.setColumnWidth(0, 40)  # Icon column
        self.attachment_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.attachment_table.customContextMenuRequested.connect(self._show_attachment_context_menu)
        layout.addWidget(self.attachment_table)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.btn_add_files = QPushButton("📁 Add Files")
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_files.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 6px 12px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_add_files)
        
        self.btn_add_folder = QPushButton("📂 Add Folder")
        self.btn_add_folder.clicked.connect(self._add_folder)
        buttons_layout.addWidget(self.btn_add_folder)
        
        self.btn_open_file = QPushButton("👁️ Open")
        self.btn_open_file.clicked.connect(self._open_file)
        buttons_layout.addWidget(self.btn_open_file)
        
        self.btn_remove_file = QPushButton("🗑️ Remove")
        self.btn_remove_file.clicked.connect(self._remove_file)
        self.btn_remove_file.setStyleSheet("QPushButton { background: #e74c3c; color: white; padding: 6px 12px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_remove_file)
        
        buttons_layout.addStretch()
        
        # File count info
        self.file_count_label = QLabel("0 files")
        self.file_count_label.setStyleSheet("QLabel { color: #7f8c8d; font-style: italic; }")
        buttons_layout.addWidget(self.file_count_label)
        
        layout.addLayout(buttons_layout)
        
        return panel
    
    def _create_description_panel(self):
        """Create the description panel."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("📝 Description")
        header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("QLabel { background: #95a5a6; color: white; padding: 6px; border-radius: 4px; }")
        layout.addWidget(header)
        
        # Scrollable description area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.description_label = QLabel("Select a list to view its description.")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.description_label.setStyleSheet("QLabel { padding: 10px; background: white; }")
        
        scroll_area.setWidget(self.description_label)
        layout.addWidget(scroll_area)
        
        # Edit button
        self.btn_edit_desc = QPushButton("✏️ Edit Description")
        self.btn_edit_desc.clicked.connect(self._edit_description)
        self.btn_edit_desc.setEnabled(False)
        layout.addWidget(self.btn_edit_desc)
        
        return panel
    
    def _apply_styling(self):
        """Apply professional styling."""
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background: #ecf0f1;
            }
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background: #f39c12;
                color: white;
            }
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background: white;
                gridline-color: #ecf0f1;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus {
                border: 2px solid #f39c12;
            }
            QPushButton {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px 12px;
                background: #ecf0f1;
            }
            QPushButton:hover {
                background: #d5dbdb;
            }
            QPushButton:pressed {
                background: #bdc3c7;
            }
        """)
    
    # ========== List Management Methods ==========
    
    def _load_lists(self):
        """Load all available attachment lists."""
        self.attachment_lists.clear()
        
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                self.attachment_lists.addItem(item)
        
        self._update_counts()
    
    def _filter_lists(self):
        """Filter lists based on search text."""
        search_text = self.search_edit.text().lower()
        for i in range(self.attachment_lists.count()):
            item = self.attachment_lists.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def _create_new_list(self):
        """Create a new attachment list."""
        dialog = CreateAttachmentListDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_list_data()
            list_name = data['name']
            description = data['description']
            
            # Check if list already exists
            list_dir = os.path.join(DATA_DIR, list_name)
            if os.path.exists(list_dir):
                QMessageBox.warning(self, "List Exists", f"An attachment list named '{list_name}' already exists.")
                return
            
            try:
                # Create list directory
                os.makedirs(list_dir, exist_ok=True)
                
                # Save description
                if description:
                    desc_file = os.path.join(list_dir, "description.txt")
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(description)
                
                self._load_lists()
                
                # Select the new list
                for i in range(self.attachment_lists.count()):
                    if self.attachment_lists.item(i).text() == list_name:
                        self.attachment_lists.setCurrentRow(i)
                        self._on_list_selected(self.attachment_lists.item(i))
                        break
                
                QMessageBox.information(self, "Success", f"Attachment list '{list_name}' created successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create list: {str(e)}")
    
    def _delete_list(self):
        """Delete the selected attachment list."""
        current_item = self.attachment_lists.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a list to delete.")
            return
        
        list_name = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the attachment list '{list_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                list_dir = os.path.join(DATA_DIR, list_name)
                shutil.rmtree(list_dir)
                
                self._load_lists()
                self._clear_attachments_view()
                
                QMessageBox.information(self, "Success", f"Attachment list '{list_name}' deleted successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete list: {str(e)}")
    
    def _on_list_selected(self, item):
        """Handle list selection."""
        if not item:
            return
        
        list_name = item.text()
        self.current_list = list_name
        self.current_list_path = os.path.join(DATA_DIR, list_name)
        
        # Update description
        self._load_description(list_name)
        
        # Load attachments
        self._load_attachments()
        
        # Update UI
        self.table_header.setText(f"📋 {list_name} - Attachments")
        self.btn_edit_desc.setEnabled(True)
    
    def _load_description(self, list_name):
        """Load and display list description."""
        desc_file = os.path.join(DATA_DIR, list_name, "description.txt")
        
        if os.path.exists(desc_file):
            try:
                with open(desc_file, 'r', encoding='utf-8') as f:
                    description = f.read().strip()
                
                if description:
                    self.description_label.setText(description)
                else:
                    self.description_label.setText("No description available.")
            except Exception as e:
                self.description_label.setText(f"Error loading description: {str(e)}")
        else:
            self.description_label.setText("No description available.")
    
    def _edit_description(self):
        """Edit the description of the current list."""
        if not self.current_list:
            return
        
        desc_file = os.path.join(DATA_DIR, self.current_list, "description.txt")
        current_desc = ""
        
        if os.path.exists(desc_file):
            try:
                with open(desc_file, 'r', encoding='utf-8') as f:
                    current_desc = f.read().strip()
            except:
                pass
        
        new_desc, ok = QInputDialog.getMultiLineText(
            self, "Edit Description", 
            f"Description for '{self.current_list}':",
            current_desc
        )
        
        if ok:
            try:
                if new_desc.strip():
                    with open(desc_file, 'w', encoding='utf-8') as f:
                        f.write(new_desc.strip())
                else:
                    # Remove description file if empty
                    if os.path.exists(desc_file):
                        os.remove(desc_file)
                
                self._load_description(self.current_list)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save description: {str(e)}")
    
    def _load_attachments(self):
        """Load attachments for the selected list."""
        if not self.current_list_path:
            return
        
        self.attachment_table.setRowCount(0)
        
        try:
            files = []
            for item in os.listdir(self.current_list_path):
                item_path = os.path.join(self.current_list_path, item)
                if os.path.isfile(item_path) and item != "description.txt":
                    files.append(item)
            
            files.sort()  # Sort alphabetically
            
            for filename in files:
                self._add_file_to_table(filename)
            
            self.file_count_label.setText(f"{len(files)} files")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load attachments: {str(e)}")
    
    def _add_file_to_table(self, filename):
        """Add a file to the attachments table."""
        file_path = os.path.join(self.current_list_path, filename)
        
        row = self.attachment_table.rowCount()
        self.attachment_table.insertRow(row)
        
        # Icon
        file_info = QFileInfo(file_path)
        icon = self.icon_provider.icon(file_info)
        icon_item = QTableWidgetItem("")
        icon_item.setIcon(icon)
        self.attachment_table.setItem(row, 0, icon_item)
        
        # File name
        self.attachment_table.setItem(row, 1, QTableWidgetItem(filename))
        
        # File size
        try:
            size = os.path.getsize(file_path)
            size_str = self._format_file_size(size)
        except:
            size_str = "Unknown"
        self.attachment_table.setItem(row, 2, QTableWidgetItem(size_str))
        
        # File type
        ext = os.path.splitext(filename)[1].upper()
        if ext:
            file_type = ext[1:] + " File"  # Remove the dot
        else:
            file_type = "File"
        self.attachment_table.setItem(row, 3, QTableWidgetItem(file_type))
        
        # Date added
        try:
            mtime = os.path.getmtime(file_path)
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except:
            date_str = "Unknown"
        self.attachment_table.setItem(row, 4, QTableWidgetItem(date_str))
    
    def _format_file_size(self, size):
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _clear_attachments_view(self):
        """Clear the attachments view."""
        self.attachment_table.setRowCount(0)
        self.current_list = None
        self.current_list_path = None
        self.table_header.setText("📋 Attachments")
        self.file_count_label.setText("0 files")
        self.description_label.setText("Select a list to view its description.")
        self.btn_edit_desc.setEnabled(False)
    
    # ========== File Management Methods ==========
    
    def _add_files(self):
        """Add files to the current list."""
        if not self.current_list_path:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Files", "", "All Files (*)"
        )
        
        if file_paths:
            try:
                added_count = 0
                skipped_count = 0
                
                for file_path in file_paths:
                    filename = os.path.basename(file_path)
                    target_path = os.path.join(self.current_list_path, filename)
                    
                    if os.path.exists(target_path):
                        reply = QMessageBox.question(
                            self, "File Exists",
                            f"'{filename}' already exists. Replace it?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No
                        )
                        
                        if reply == QMessageBox.StandardButton.No:
                            skipped_count += 1
                            continue
                    
                    shutil.copy2(file_path, target_path)
                    added_count += 1
                
                self._load_attachments()
                self._update_counts()
                
                msg = f"Added {added_count} file(s)"
                if skipped_count > 0:
                    msg += f", skipped {skipped_count} file(s)"
                QMessageBox.information(self, "Files Added", msg)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add files: {str(e)}")
    
    def _add_folder(self):
        """Add all files from a folder to the current list."""
        if not self.current_list_path:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        folder_path = QFileDialog.getExistingDirectory(self, "Add Folder")
        
        if folder_path:
            try:
                added_count = 0
                skipped_count = 0
                
                for root, dirs, files in os.walk(folder_path):
                    for filename in files:
                        source_path = os.path.join(root, filename)
                        target_path = os.path.join(self.current_list_path, filename)
                        
                        if os.path.exists(target_path):
                            reply = QMessageBox.question(
                                self, "File Exists",
                                f"'{filename}' already exists. Replace it?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No
                            )
                            
                            if reply == QMessageBox.StandardButton.No:
                                skipped_count += 1
                                continue
                        
                        shutil.copy2(source_path, target_path)
                        added_count += 1
                
                self._load_attachments()
                self._update_counts()
                
                msg = f"Added {added_count} file(s) from folder"
                if skipped_count > 0:
                    msg += f", skipped {skipped_count} file(s)"
                QMessageBox.information(self, "Folder Added", msg)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add folder: {str(e)}")
    
    def _open_file(self):
        """Open the selected file."""
        row = self.attachment_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a file to open.")
            return
        
        filename = self.attachment_table.item(row, 1).text()
        file_path = os.path.join(self.current_list_path, filename)
        
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")
    
    def _remove_file(self):
        """Remove the selected file."""
        selected_rows = set()
        for item in self.attachment_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select file(s) to remove.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Are you sure you want to remove {len(selected_rows)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for row in sorted(selected_rows):
                    filename = self.attachment_table.item(row, 1).text()
                    file_path = os.path.join(self.current_list_path, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                self._load_attachments()
                self._update_counts()
                
                QMessageBox.information(self, "Success", f"Removed {len(selected_rows)} file(s).")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove files: {str(e)}")
    
    # ========== Context Menu Methods ==========
    
    def _show_list_context_menu(self, position):
        """Show context menu for lists."""
        item = self.attachment_lists.itemAt(position)
        
        menu = QMenu()
        
        if item:
            menu.addAction("📂 Open", lambda: self._on_list_selected(item))
            menu.addSeparator()
            menu.addAction("✏️ Edit Description", self._edit_description)
            menu.addSeparator()
            menu.addAction("🗑️ Delete", self._delete_list)
        
        menu.addSeparator()
        menu.addAction("➕ New List", self._create_new_list)
        menu.addAction("🔄 Refresh", self._load_lists)
        
        menu.exec(self.attachment_lists.mapToGlobal(position))
    
    def _show_attachment_context_menu(self, position):
        """Show context menu for attachments."""
        menu = QMenu()
        
        menu.addAction("📁 Add Files", self._add_files)
        menu.addAction("📂 Add Folder", self._add_folder)
        
        if self.attachment_table.currentRow() >= 0:
            menu.addSeparator()
            menu.addAction("👁️ Open", self._open_file)
            menu.addAction("🗑️ Remove", self._remove_file)
        
        menu.exec(self.attachment_table.mapToGlobal(position))
    
    # ========== Utility Methods ==========
    
    def _update_counts(self):
        """Update the counts and emit signal."""
        folder_count, file_count = self.count_attachment_folders_and_files()
        self.counts_changed.emit(folder_count, file_count)
    
    def count_attachment_folders_and_files(self):
        """Count attachment folders and files for dashboard."""
        folder_count = 0
        total_file_count = 0
        
        try:
            if os.path.isdir(DATA_DIR):
                for item_name in os.listdir(DATA_DIR):
                    item_path = os.path.join(DATA_DIR, item_name)
                    if os.path.isdir(item_path):
                        folder_count += 1
                        try:
                            files_in_folder = [
                                f for f in os.listdir(item_path) 
                                if os.path.isfile(os.path.join(item_path, f)) and f != "description.txt"
                            ]
                            total_file_count += len(files_in_folder)
                        except Exception:
                            pass
        except Exception:
            pass
        
        return folder_count, total_file_count
    
    # ========== Public Methods ==========
    
    def get_list_count(self):
        """Get the number of attachment lists."""
        return self.attachment_lists.count()
    
    def refresh_lists(self):
        """Refresh the lists display."""
        self._load_lists()

# Original function for compatibility
def count_attachment_folders_and_files(base_dir):
    """Count attachment folders and files (compatibility function)."""
    folder_count = 0
    total_file_count = 0
    try:
        if os.path.isdir(base_dir):
            for item_name in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item_name)
                if os.path.isdir(item_path):
                    folder_count += 1
                    try:
                        files_in_folder = [f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))]
                        total_file_count += len(files_in_folder)
                    except Exception: 
                        pass
    except Exception: 
        pass
    return folder_count, total_file_count

# Maintain backward compatibility
AttachmentManager = EnhancedAttachmentManager

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        # --- Left pane ---
        left_pane_widget = QWidget()
        left_layout = QVBoxLayout(left_pane_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.addWidget(QLabel("<b>Attachment Lists</b>"))
        
        # List controls at the top for consistency
        list_button_layout = QHBoxLayout()
        btn_new = QPushButton("➕ New List"); btn_new.setToolTip("Create a new empty attachment list (folder)"); btn_new.clicked.connect(self._new_list)
        btn_del = QPushButton("🗑 Delete"); btn_del.setToolTip("Delete the selected attachment list (folder) and all its contents"); btn_del.clicked.connect(self._delete_list)
        list_button_layout.addWidget(btn_new); list_button_layout.addWidget(btn_del)
        left_layout.addLayout(list_button_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("attachmentListWidget")
        self.list_widget.currentTextChanged.connect(self._load_list_contents)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        left_layout.addWidget(self.list_widget)

        # --- Right pane ---
        right_pane_widget = QWidget()
        right_layout = QVBoxLayout(right_pane_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        # Action buttons
        file_action_layout = QHBoxLayout()
        btn_import = QPushButton("⬆️ Import Files/Folder"); btn_import.setToolTip("Copy files or a folder's contents into the selected attachment list"); btn_import.clicked.connect(self._import_files_or_folder)
        # *** REMOVED Deduplicate Button ***
        btn_refresh = QPushButton("🔄 Refresh Files"); btn_refresh.setToolTip("Reload the list of files in the selected list"); btn_refresh.clicked.connect(lambda: self._load_list_contents(self.list_widget.currentItem().text() if self.list_widget.currentItem() else None))
        file_action_layout.addWidget(btn_import)
        # btn_dedupe removed
        file_action_layout.addWidget(btn_refresh)
        file_action_layout.addStretch(1); right_layout.addLayout(file_action_layout)
        # Search Bar
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("🔍 Search files in current list..."); self.search_input.textChanged.connect(self._filter_files); right_layout.addWidget(self.search_input)

        # *** Table Widget Setup (Includes Scrolling/Resizing Settings) ***
        self.file_table = QTableWidget()
        self.file_table.setObjectName("attachmentFileTable")
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Size", "Date Modified"])
        # Explicitly set scrollbar policy
        self.file_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.file_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header = self.file_table.horizontalHeader()
        # Set resize modes *after* setting headers
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Filename stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive) # Size interactive
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive) # Date interactive
        # Other Table Properties
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.file_table.setShowGrid(True); self.file_table.verticalHeader().setVisible(False); self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.file_table.customContextMenuRequested.connect(self._show_file_context_menu); self.file_table.setSortingEnabled(True)
        right_layout.addWidget(self.file_table)
        # Add panes to main layout
        main_layout.addWidget(left_pane_widget, 1)
        main_layout.addWidget(right_pane_widget, 3)

    def _update_dashboard_counts(self):
        folder_count, total_file_count = count_attachment_folders_and_files(DATA_DIR)
        self.counts_changed.emit(folder_count, total_file_count)

    def _refresh_list(self):
        current_selection = self.list_widget.currentItem().text() if self.list_widget.currentItem() else None
        self.list_widget.clear(); found_current = False
        try:
            if os.path.isdir(DATA_DIR):
                for name in sorted(os.listdir(DATA_DIR)):
                    path = os.path.join(DATA_DIR, name)
                    if os.path.isdir(path): self.list_widget.addItem(name);
                    if name == current_selection: found_current = True
                if found_current:
                    items = self.list_widget.findItems(current_selection, Qt.MatchFlag.MatchExactly)
                    if items: self.list_widget.setCurrentItem(items[0])
        except Exception as e: QMessageBox.critical(self, "Error Refreshing Lists", f"Could not read attachment directories:\n{e}")
        self._update_dashboard_counts()
        # Load content only if an item is actually selected after refresh
        if self.list_widget.currentItem():
             self._load_list_contents(self.list_widget.currentItem().text())
        else:
             self.file_table.setRowCount(0)
             self.current_list_path = None


    def _new_list(self):
        name, ok = QInputDialog.getText(self, "New Attachment List", "Enter list name:")
        if ok and name and name.strip():
            clean_name = name.strip().replace('\\','_').replace('/','_'); path = os.path.join(DATA_DIR, clean_name)
            if os.path.exists(path): QMessageBox.warning(self, "Exists", f"List (folder) '{clean_name}' already exists.")
            else:
                try:
                    os.makedirs(path); self._refresh_list() # Refresh updates counts and reselects if possible
                    # Ensure selection after refresh if just created
                    items = self.list_widget.findItems(clean_name, Qt.MatchFlag.MatchExactly)
                    if items: self.list_widget.setCurrentItem(items[0])
                except Exception as e: QMessageBox.critical(self, "Error Creating List", f"Could not create directory '{clean_name}':\n{e}")

    def _delete_list(self):
        current_item = self.list_widget.currentItem();
        if not current_item: QMessageBox.warning(self, "No Selection", "Please select an attachment list to delete."); return
        name = current_item.text(); path_to_delete = os.path.join(DATA_DIR, name)
        if QMessageBox.question(self, "Confirm Delete", f"Delete list '{name}' and ALL files inside?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path_to_delete):
                    shutil.rmtree(path_to_delete)
                    if self.current_list_path == path_to_delete: self.file_table.setRowCount(0); self.current_list_path = None
                    self._refresh_list(); print(f"Deleted attachment list: {name}") # Refresh updates counts
                else: QMessageBox.warning(self, "Not Found", f"Directory '{name}' not found."); self._refresh_list()
            except Exception as e: QMessageBox.critical(self, "Error Deleting", f"Could not delete list '{name}':\n{e}")

    def _import_files_or_folder(self):
        """ Imports files/folder with automatic duplicate filename checking. """
        if not self.current_list_path or not os.path.isdir(self.current_list_path):
            QMessageBox.warning(self, "Select List", "Please select a valid attachment list first.")
            return

        try: # Get existing files safely
            existing_files_lower = {f.lower() for f in os.listdir(self.current_list_path) if os.path.isfile(os.path.join(self.current_list_path, f))}
        except Exception as e:
            QMessageBox.critical(self,"Error","Could not read current list folder contents.")
            return

        msgBox = QMessageBox(self); msgBox.setWindowTitle("Import Type"); msgBox.setText("What do you want to import?")
        msgBox.setIcon(QMessageBox.Icon.Question); files_button = msgBox.addButton("Select Files", QMessageBox.ButtonRole.ActionRole); folder_button = msgBox.addButton("Select Folder Contents", QMessageBox.ButtonRole.ActionRole); msgBox.addButton(QMessageBox.StandardButton.Cancel); msgBox.exec()

        imported_count = 0 # Count successfully imported files
        skipped_duplicates = 0

        if msgBox.clickedButton() == files_button:
            files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Import", "", "All Files (*.*)")
            if files:
                for src_file in files:
                    base_name = os.path.basename(src_file)
                    if base_name.lower() in existing_files_lower:
                        print(f"Skipping duplicate file during import: {base_name}")
                        skipped_duplicates += 1
                        continue
                    try:
                        dst_file = os.path.join(self.current_list_path, base_name)
                        shutil.copy2(src_file, dst_file)
                        existing_files_lower.add(base_name.lower()) # Add to set
                        imported_count += 1
                    except Exception as e: QMessageBox.warning(self, "Import Error", f"Could not copy file '{base_name}':\n{e}")

        elif msgBox.clickedButton() == folder_button:
            src_folder = QFileDialog.getExistingDirectory(self, "Select Folder to Import Contents From")
            if src_folder:
                for item_name in os.listdir(src_folder):
                    src_item = os.path.join(src_folder, item_name)
                    if os.path.isfile(src_item):
                        if item_name.lower() in existing_files_lower:
                            print(f"Skipping duplicate file during import: {item_name}")
                            skipped_duplicates += 1
                            continue
                        try:
                            dst_item = os.path.join(self.current_list_path, item_name)
                            shutil.copy2(src_item, dst_item)
                            existing_files_lower.add(item_name.lower()) # Add to set
                            imported_count += 1
                        except Exception as e: QMessageBox.warning(self, "Import Error", f"Could not copy item '{item_name}':\n{e}")

        # Show summary message only if duplicates were skipped
        if skipped_duplicates > 0:
            QMessageBox.information(self, "Import Notice", f"Import process finished.\nSuccessfully imported {imported_count} file(s).\nSkipped {skipped_duplicates} file(s) because files with the same name already exist in this list.")
        elif imported_count > 0:
             QMessageBox.information(self, "Import Complete", f"Successfully imported {imported_count} file(s).")


        if imported_count > 0: # Reload only if something was actually imported
            self._load_list_contents(os.path.basename(self.current_list_path))
            self._update_dashboard_counts()

    def _load_list_contents(self, list_name):
        # (Remains the same as previous version with QLocale fix)
        self.file_table.setRowCount(0)
        self.search_input.clear()
        if not list_name: self.current_list_path = None; return
        self.current_list_path = os.path.join(DATA_DIR, list_name)
        if not os.path.isdir(self.current_list_path): QMessageBox.warning(self, "Error", f"Selected list folder '{list_name}' not found."); self.current_list_path = None; self._refresh_list(); return
        try:
            self.file_table.setSortingEnabled(False); files_data = []
            for filename in os.listdir(self.current_list_path):
                file_path = os.path.join(self.current_list_path, filename)
                if os.path.isfile(file_path):
                    try: stats = os.stat(file_path); file_info = QFileInfo(file_path); files_data.append({'path': file_path, 'name': filename, 'size': stats.st_size, 'modified_ts': stats.st_mtime, 'file_info': file_info})
                    except OSError as e: print(f"Warning: Could not stat file {filename}: {e}")
            files_data.sort(key=lambda x: x['name'].lower()); self.file_table.setRowCount(len(files_data)); locale = QLocale()
            for row, data in enumerate(files_data):
                icon = self.icon_provider.icon(data['file_info']);
                if icon.isNull(): icon = QIcon.fromTheme("application-octet-stream", QIcon())
                filename_item = QTableWidgetItem(data['name']); filename_item.setIcon(icon); filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable); filename_item.setData(Qt.ItemDataRole.UserRole, data['path']); self.file_table.setItem(row, 0, filename_item)
                size_kb = data['size'] / 1024.0; size_text = f"{size_kb:,.1f} KB" if size_kb >= 0.1 else f"{data['size']} B"; size_item = QTableWidgetItem(size_text); size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable); size_item.setData(Qt.ItemDataRole.UserRole + 1, data['size']); self.file_table.setItem(row, 1, size_item)
                dt_modified = QDateTime.fromSecsSinceEpoch(int(data['modified_ts'])); date_text = locale.toString(dt_modified, QLocale.FormatType.ShortFormat); date_item = QTableWidgetItem(date_text); date_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable); date_item.setData(Qt.ItemDataRole.UserRole + 1, int(data['modified_ts'])); self.file_table.setItem(row, 2, date_item)
            self.file_table.setColumnWidth(1, 100); self.file_table.setColumnWidth(2, 150); self.file_table.setSortingEnabled(True)
        except Exception as e: QMessageBox.critical(self, "Error Loading Files", f"Could not load attachments from list '{list_name}':\n{type(e).__name__}: {e}"); print(f"Error loading list contents for {list_name}: {type(e).__name__} - {e}"); self.current_list_path = None

    def _filter_files(self, text):
        # (Remains the same)
        filter_text = text.lower()
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item: filename = item.text().lower(); self.file_table.setRowHidden(row, filter_text not in filename)

    # *** Manual Duplicate Removal Method Removed ***

    def _show_list_context_menu(self, pos):
        # (Remains the same)
        item = self.list_widget.itemAt(pos);
        if not item: return
        menu = QMenu(self); open_action = QAction("Open Folder", self); open_action.triggered.connect(lambda: self._open_folder(os.path.join(DATA_DIR, item.text()))); menu.addAction(open_action)
        rename_action = QAction("Rename List", self); rename_action.triggered.connect(lambda: self._rename_list(item)); menu.addAction(rename_action)
        delete_action = QAction("Delete List", self); delete_action.triggered.connect(self._delete_list); menu.addAction(delete_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _show_file_context_menu(self, pos):
        # (Remains the same)
        selected_rows = self.file_table.selectionModel().selectedRows();
        if not selected_rows: return
        menu = QMenu(self)
        if self.current_list_path: open_folder_action = QAction("Open Containing Folder", self); open_folder_action.triggered.connect(lambda: self._open_folder(self.current_list_path)); menu.addAction(open_folder_action); menu.addSeparator()
        delete_action = QAction(f"Delete {len(selected_rows)} Selected File(s)", self); delete_action.triggered.connect(self._delete_selected_files); menu.addAction(delete_action)
        menu.exec(self.file_table.mapToGlobal(pos))

    def _open_folder(self, folder_path):
        # (Remains the same)
        if folder_path and os.path.isdir(folder_path):
            try: QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
            except Exception as e: QMessageBox.warning(self, "Error", f"Could not open folder '{folder_path}':\n{e}")
        else: QMessageBox.warning(self, "Error", f"Folder path is invalid or does not exist:\n{folder_path}")

    def _rename_list(self, item):
        # (Remains the same)
        old_name = item.text(); old_path = os.path.join(DATA_DIR, old_name)
        if not os.path.isdir(old_path): QMessageBox.warning(self, "Error", f"List folder '{old_name}' not found."); self._refresh_list(); return
        new_name, ok = QInputDialog.getText(self, "Rename List", "Enter new name:", text=old_name)
        if ok and new_name and new_name.strip() and new_name != old_name:
            clean_new_name = new_name.strip().replace('\\','_').replace('/','_'); new_path = os.path.join(DATA_DIR, clean_new_name)
            if os.path.exists(new_path): QMessageBox.warning(self, "Rename Error", f"A list named '{clean_new_name}' already exists."); return
            try:
                os.rename(old_path, new_path); print(f"Renamed list '{old_name}' to '{clean_new_name}'")
                if self.current_list_path == old_path: self.current_list_path = new_path
                self._refresh_list()
                items = self.list_widget.findItems(clean_new_name, Qt.MatchFlag.MatchExactly)
                if items: self.list_widget.setCurrentItem(items[0])
            except Exception as e: QMessageBox.critical(self, "Rename Error", f"Could not rename list:\n{e}"); self._refresh_list()

    def _delete_selected_files(self):
        # (Remains the same)
        selected_rows = self.file_table.selectionModel().selectedRows();
        if not selected_rows or not self.current_list_path: return
        files_to_delete = []; filenames_display = []
        for row_index in [index.row() for index in selected_rows]:
            item = self.file_table.item(row_index, 0)
            if item:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path and os.path.exists(file_path):
                    if file_path not in files_to_delete: files_to_delete.append(file_path); filenames_display.append(os.path.basename(file_path))
                else: print(f"W: Cannot delete item, path invalid or file missing: {item.text()}")
        if not files_to_delete: QMessageBox.information(self,"No Files", "No valid files selected for deletion."); return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {len(files_to_delete)} file(s)?\n\n- " + "\n- ".join(filenames_display[:10]) + ("..." if len(filenames_display)>10 else ""), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0; errors = []
            for file_path in files_to_delete:
                try: os.remove(file_path); deleted_count += 1
                except Exception as e: errors.append(f"Could not delete '{os.path.basename(file_path)}': {e}")
            if errors: QMessageBox.warning(self, "Deletion Errors", f"Finished. {deleted_count} file(s) deleted.\n\nErrors:\n- " + "\n- ".join(errors))
            elif deleted_count > 0: QMessageBox.information(self, "Deletion Complete", f"{deleted_count} file(s) deleted.")
            self._load_list_contents(os.path.basename(self.current_list_path)) # Refresh view
            self._update_dashboard_counts() # Update counts