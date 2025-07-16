# ui/enhanced_base_manager.py
"""
Enhanced Base Manager with Professional UI and Fixed Data Persistence
Addresses all issues: auto-save, responsive design, descriptions, drag scrolling
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QProgressBar,
    QMessageBox, QInputDialog, QFileDialog, QAbstractItemView, QStyle,
    QFrame, QSplitter, QScrollArea, QTextEdit, QDialog, QDialogButtonBox,
    QFormLayout, QListWidgetItem, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QCursor, QDragMoveEvent, QMouseEvent

import os
import json
import csv
from typing import Dict, List, Any, Optional
from openpyxl import Workbook, load_workbook
from core.utils.logger import get_module_logger

logger = get_module_logger(__name__)

class ListDescriptionDialog(QDialog):
    """Professional dialog for creating lists with descriptions"""
    
    def __init__(self, parent=None, list_name: str = "", description: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Create/Edit List")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        # Setup UI
        self._setup_ui(list_name, description)
        
    def _setup_ui(self, list_name: str, description: str):
        layout = QVBoxLayout(self)
        
        # Form layout for inputs
        form_layout = QFormLayout()
        
        # List name input
        self.name_input = QLineEdit(list_name)
        self.name_input.setPlaceholderText("Enter list name...")
        form_layout.addRow("List Name:", self.name_input)
        
        # Description input
        self.description_input = QTextEdit(description)
        self.description_input.setPlaceholderText("Enter a short description for this list...")
        self.description_input.setMaximumHeight(100)
        form_layout.addRow("Description:", self.description_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Focus on name input
        self.name_input.setFocus()
        
    def get_list_data(self) -> tuple:
        """Get the list name and description"""
        return self.name_input.text().strip(), self.description_input.toPlainText().strip()

class DragScrollTableWidget(QTableWidget):
    """Table widget with professional drag-to-scroll functionality"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_pan_point = QPoint()
        self.panning = False
        self.pan_button_pressed = False
        
        # Enable smooth scrolling
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # Smooth scroll animation
        self.scroll_animation = QPropertyAnimation(self.horizontalScrollBar(), b"value")
        self.scroll_animation.setDuration(200)
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_button_pressed = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.pan_button_pressed:
            delta = event.pos() - self.last_pan_point
            
            # Scroll horizontally and vertically
            h_scroll = self.horizontalScrollBar()
            v_scroll = self.verticalScrollBar()
            
            h_scroll.setValue(h_scroll.value() - delta.x())
            v_scroll.setValue(v_scroll.value() - delta.y())
            
            self.last_pan_point = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_button_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        # Enhanced wheel scrolling with shift for horizontal scroll
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            # Horizontal scroll
            h_scroll = self.horizontalScrollBar()
            delta = event.angleDelta().y()
            h_scroll.setValue(h_scroll.value() - delta)
            event.accept()
        else:
            super().wheelEvent(event)

class EnhancedBaseManager(QWidget):
    """Enhanced base manager with professional UI and fixed data persistence"""
    
    # Signals
    counts_changed = pyqtSignal(int, int)  # list_count, item_count
    list_selected = pyqtSignal(str)  # list_name
    data_changed = pyqtSignal()  # When data is modified
    
    def __init__(self, manager_type: str, data_subdir: str, file_extension: str = ".xlsx", parent=None):
        super().__init__(parent)
        
        # Manager configuration
        self.manager_type = manager_type
        self.data_subdir = data_subdir
        self.file_extension = file_extension
        
        # Paths
        self.base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        self.data_dir = os.path.join(self.base_path, 'data', self.data_subdir)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # State management
        self.current_list_name = None
        self.current_data = []
        self.headers = []
        self.list_descriptions = {}
        self.auto_save_enabled = True
        
        # UI Components
        self.list_widget = None
        self.table_widget = None
        self.description_label = None
        self.stats_label = None
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self._auto_save_current_data)
        
        # Build UI
        self._build_enhanced_ui()
        self._load_lists_and_descriptions()
        
        # Connect data change signals
        self.data_changed.connect(self._on_data_changed)
        
        # Update counts timer
        self.counts_timer = QTimer()
        self.counts_timer.timeout.connect(self._update_counts)
        self.counts_timer.start(3000)  # Update every 3 seconds
    
    def _build_enhanced_ui(self):
        """Build the enhanced professional UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        
        # Left panel - List management
        left_panel = self._create_enhanced_left_panel()
        
        # Right panel - Data display
        right_panel = self._create_enhanced_right_panel()
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def _create_enhanced_left_panel(self):
        """Create enhanced left panel with professional styling"""
        panel = QFrame()
        panel.setObjectName("manager-sidebar")
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(400)
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title section
        title_layout = QHBoxLayout()
        title_label = QLabel(f"{self.manager_type.title()} Lists")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2C3E50;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # List management buttons
        buttons_layout = QHBoxLayout()
        
        btn_create = QPushButton("📝 Create")
        btn_create.setObjectName("success")
        btn_create.setToolTip(f"Create new {self.manager_type} list")
        btn_create.clicked.connect(self._create_new_list)
        
        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setObjectName("danger")
        btn_delete.setToolTip(f"Delete selected {self.manager_type} list")
        btn_delete.clicked.connect(self._delete_current_list)
        
        btn_edit = QPushButton("✏️ Edit")
        btn_edit.setObjectName("primary")
        btn_edit.setToolTip("Edit list name and description")
        btn_edit.clicked.connect(self._edit_current_list)
        
        buttons_layout.addWidget(btn_create)
        buttons_layout.addWidget(btn_edit)
        buttons_layout.addWidget(btn_delete)
        layout.addLayout(buttons_layout)
        
        # Lists widget
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemClicked.connect(self._on_list_selected)
        layout.addWidget(self.list_widget)
        
        # Description display
        desc_frame = QFrame()
        desc_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        desc_frame.setMaximumHeight(120)
        desc_layout = QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(8, 8, 8, 8)
        
        desc_title = QLabel("Description:")
        desc_title.setStyleSheet("font-weight: bold; color: #495057;")
        self.description_label = QLabel("Select a list to see its description")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #6C757D; font-style: italic;")
        
        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(self.description_label)
        desc_layout.addStretch()
        layout.addWidget(desc_frame)
        
        # Statistics
        self.stats_label = QLabel("Lists: 0 | Items: 0")
        self.stats_label.setStyleSheet("color: #6C757D; font-size: 10pt;")
        layout.addWidget(self.stats_label)
        
        return panel
    
    def _create_enhanced_right_panel(self):
        """Create enhanced right panel with professional data display"""
        panel = QFrame()
        panel.setObjectName("manager")
        
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Toolbar
        toolbar = self._create_enhanced_toolbar()
        layout.addLayout(toolbar)
        
        # Enhanced table with drag scrolling
        self.table_widget = DragScrollTableWidget()
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setToolTip("Middle-click and drag to pan the table\nShift+wheel to scroll horizontally")
        
        # Connect table signals for auto-save
        self.table_widget.itemChanged.connect(self._on_table_item_changed)
        
        layout.addWidget(self.table_widget)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.data_status_label = QLabel("No data loaded")
        self.data_status_label.setStyleSheet("color: #6C757D; font-size: 10pt;")
        status_layout.addWidget(self.data_status_label)
        status_layout.addStretch()
        
        # Progress bar for operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(6)
        status_layout.addWidget(self.progress_bar)
        
        layout.addLayout(status_layout)
        
        return panel
    
    def _create_enhanced_toolbar(self):
        """Create enhanced toolbar with professional styling"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        # Import section
        btn_import = QPushButton("📥 Import")
        btn_import.setObjectName("primary")
        btn_import.setToolTip(f"Import {self.manager_type} data from file")
        btn_import.clicked.connect(self._import_data)
        
        btn_export = QPushButton("📤 Export")
        btn_export.setObjectName("warning")
        btn_export.setToolTip(f"Export {self.manager_type} data to file")
        btn_export.clicked.connect(self._export_data)
        
        # Data manipulation
        btn_add = QPushButton("➕ Add Row")
        btn_add.setObjectName("success")
        btn_add.setToolTip(f"Add new {self.manager_type} entry")
        btn_add.clicked.connect(self._add_row)
        
        btn_delete_row = QPushButton("➖ Delete Row")
        btn_delete_row.setObjectName("danger")
        btn_delete_row.setToolTip("Delete selected row")
        btn_delete_row.clicked.connect(self._delete_row)
        
        # Auto-save toggle
        self.auto_save_checkbox = QCheckBox("Auto-save")
        self.auto_save_checkbox.setChecked(True)
        self.auto_save_checkbox.toggled.connect(self._toggle_auto_save)
        self.auto_save_checkbox.setToolTip("Automatically save changes")
        
        # Manual save
        btn_save = QPushButton("💾 Save")
        btn_save.setObjectName("primary")
        btn_save.setToolTip("Save current data manually")
        btn_save.clicked.connect(self._save_current_data)
        
        # Add to layout
        toolbar_layout.addWidget(btn_import)
        toolbar_layout.addWidget(btn_export)
        toolbar_layout.addWidget(btn_add)
        toolbar_layout.addWidget(btn_delete_row)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.auto_save_checkbox)
        toolbar_layout.addWidget(btn_save)
        
        return toolbar_layout
    
    # =============================================================================
    # List Management Methods
    # =============================================================================
    
    def _load_lists_and_descriptions(self):
        """Load all lists and their descriptions"""
        self.list_widget.clear()
        self.list_descriptions = {}
        
        try:
            # Load descriptions from metadata file
            metadata_file = os.path.join(self.data_dir, 'list_metadata.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.list_descriptions = json.load(f)
            
            # Scan for lists
            if os.path.exists(self.data_dir):
                items = os.listdir(self.data_dir)
                lists = []
                
                for item in items:
                    if item == 'list_metadata.json':
                        continue
                        
                    item_path = os.path.join(self.data_dir, item)
                    if os.path.isdir(item_path):
                        lists.append(item)
                    elif item.endswith(self.file_extension):
                        list_name = os.path.splitext(item)[0]
                        lists.append(list_name)
                
                # Sort and add to widget
                lists.sort()
                for list_name in lists:
                    item = QListWidgetItem(list_name)
                    description = self.list_descriptions.get(list_name, "No description")
                    item.setToolTip(f"{list_name}\n\n{description}")
                    self.list_widget.addItem(item)
                
                # Update counts
                self._update_counts()
                
        except Exception as e:
            logger.error(f"Failed to load {self.manager_type} lists: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to load {self.manager_type} lists:\n{str(e)}")
    
    def _save_list_metadata(self):
        """Save list descriptions to metadata file"""
        try:
            metadata_file = os.path.join(self.data_dir, 'list_metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.list_descriptions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {str(e)}")
    
    def _create_new_list(self):
        """Create new list with description"""
        dialog = ListDescriptionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            list_name, description = dialog.get_list_data()
            
            if not list_name:
                QMessageBox.warning(self, "Error", "List name cannot be empty!")
                return
            
            if self._list_exists(list_name):
                QMessageBox.warning(self, "Error", f"List '{list_name}' already exists!")
                return
            
            try:
                # Create list structure
                self._create_new_list_structure(list_name)
                
                # Save description
                self.list_descriptions[list_name] = description or "No description"
                self._save_list_metadata()
                
                # Refresh lists
                self._load_lists_and_descriptions()
                
                # Select the new list
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == list_name:
                        self.list_widget.setCurrentRow(i)
                        self._on_list_selected(self.list_widget.item(i))
                        break
                
                QMessageBox.information(self, "Success", f"List '{list_name}' created successfully!")
                
            except Exception as e:
                logger.error(f"Failed to create list: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to create list:\n{str(e)}")
    
    def _edit_current_list(self):
        """Edit current list name and description"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a list to edit!")
            return
        
        current_description = self.list_descriptions.get(self.current_list_name, "")
        dialog = ListDescriptionDialog(self, self.current_list_name, current_description)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_description = dialog.get_list_data()
            
            if not new_name:
                QMessageBox.warning(self, "Error", "List name cannot be empty!")
                return
            
            if new_name != self.current_list_name and self._list_exists(new_name):
                QMessageBox.warning(self, "Error", f"List '{new_name}' already exists!")
                return
            
            try:
                # Save current data before renaming
                self._save_current_data()
                
                # Rename if necessary
                if new_name != self.current_list_name:
                    self._rename_list(self.current_list_name, new_name)
                
                # Update description
                self.list_descriptions[new_name] = new_description or "No description"
                if new_name != self.current_list_name and self.current_list_name in self.list_descriptions:
                    del self.list_descriptions[self.current_list_name]
                
                self._save_list_metadata()
                
                # Update current list name
                self.current_list_name = new_name
                
                # Refresh lists
                self._load_lists_and_descriptions()
                
                # Select the updated list
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == new_name:
                        self.list_widget.setCurrentRow(i)
                        break
                
                # Update description display
                self.description_label.setText(new_description or "No description")
                
                QMessageBox.information(self, "Success", "List updated successfully!")
                
            except Exception as e:
                logger.error(f"Failed to edit list: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to edit list:\n{str(e)}")
    
    def _delete_current_list(self):
        """Delete the currently selected list"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a list to delete!")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the list '{self.current_list_name}'?\n\n"
            f"This action cannot be undone and will delete all data in this list.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete list structure
                self._delete_list_structure(self.current_list_name)
                
                # Remove from descriptions
                if self.current_list_name in self.list_descriptions:
                    del self.list_descriptions[self.current_list_name]
                self._save_list_metadata()
                
                # Clear current selection
                self.current_list_name = None
                self.current_data = []
                self.headers = []
                
                # Refresh lists
                self._load_lists_and_descriptions()
                self._clear_table()
                self.description_label.setText("Select a list to see its description")
                
                QMessageBox.information(self, "Success", "List deleted successfully!")
                
            except Exception as e:
                logger.error(f"Failed to delete list: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to delete list:\n{str(e)}")
    
    def _on_list_selected(self, item):
        """Handle list selection"""
        if not item:
            return
        
        # Save current data before switching
        if self.current_list_name and self.auto_save_enabled:
            self._save_current_data()
        
        list_name = item.text()
        self.current_list_name = list_name
        
        # Update description
        description = self.list_descriptions.get(list_name, "No description")
        self.description_label.setText(description)
        
        # Load list data
        self._load_list_data(list_name)
        
        # Emit signal
        self.list_selected.emit(list_name)
    
    # =============================================================================
    # Data Management Methods
    # =============================================================================
    
    def _on_table_item_changed(self, item):
        """Handle table item changes for auto-save"""
        # Update current data
        row = item.row()
        col = item.column()
        
        if row < len(self.current_data) and col < len(self.current_data[row]):
            self.current_data[row][col] = item.text()
            
            # Trigger auto-save
            if self.auto_save_enabled:
                self.auto_save_timer.start(1000)  # Save after 1 second of inactivity
            
            self.data_changed.emit()
    
    def _on_data_changed(self):
        """Handle data change signal"""
        self._update_data_status()
    
    def _auto_save_current_data(self):
        """Auto-save current data"""
        if self.current_list_name and self.auto_save_enabled:
            self._save_current_data()
    
    def _toggle_auto_save(self, enabled: bool):
        """Toggle auto-save functionality"""
        self.auto_save_enabled = enabled
        if enabled:
            self.auto_save_checkbox.setToolTip("Auto-save enabled - changes will be saved automatically")
        else:
            self.auto_save_checkbox.setToolTip("Auto-save disabled - save manually")
    
    def _add_row(self):
        """Add a new row - override in subclasses"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", f"Please select a {self.manager_type} list first!")
            return
        
        # Create new row with empty values
        new_row = [""] * len(self.headers)
        self.current_data.append(new_row)
        
        # Update table
        self._update_table_display()
        
        # Select the new row
        new_row_index = len(self.current_data) - 1
        self.table_widget.selectRow(new_row_index)
        self.table_widget.scrollToItem(self.table_widget.item(new_row_index, 0))
        
        # Trigger auto-save
        if self.auto_save_enabled:
            self.auto_save_timer.start(1000)
        
        self.data_changed.emit()
    
    def _delete_row(self):
        """Delete selected rows"""
        selected_rows = set()
        for item in self.table_widget.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Please select rows to delete!")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete {len(selected_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete rows in reverse order to maintain indices
            for row in sorted(selected_rows, reverse=True):
                if row < len(self.current_data):
                    del self.current_data[row]
            
            # Update table
            self._update_table_display()
            
            # Trigger auto-save
            if self.auto_save_enabled:
                self.auto_save_timer.start(1000)
            
            self.data_changed.emit()
    
    def _update_table_display(self):
        """Update table display with current data"""
        if not self.headers:
            self._clear_table()
            return
        
        # Set up table
        self.table_widget.setRowCount(len(self.current_data))
        self.table_widget.setColumnCount(len(self.headers))
        self.table_widget.setHorizontalHeaderLabels(self.headers)
        
        # Populate data
        for row_idx, row_data in enumerate(self.current_data):
            for col_idx, cell_value in enumerate(row_data):
                if col_idx < len(self.headers):
                    item = QTableWidgetItem(str(cell_value) if cell_value is not None else "")
                    self.table_widget.setItem(row_idx, col_idx, item)
        
        # Auto-resize columns
        self.table_widget.resizeColumnsToContents()
        
        # Update status
        self._update_data_status()
    
    def _clear_table(self):
        """Clear table display"""
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)
        self.data_status_label.setText("No data loaded")
    
    def _update_data_status(self):
        """Update data status label"""
        if self.current_list_name:
            row_count = len(self.current_data)
            col_count = len(self.headers)
            self.data_status_label.setText(
                f"List: {self.current_list_name} | Rows: {row_count} | Columns: {col_count}"
            )
        else:
            self.data_status_label.setText("No list selected")
    
    def _update_counts(self):
        """Update list and item counts"""
        try:
            list_count = self.list_widget.count()
            total_items = 0
            
            # Count items in all lists
            for i in range(list_count):
                list_name = self.list_widget.item(i).text()
                items = self._count_items_in_list(list_name)
                total_items += items
            
            # Update display
            self.stats_label.setText(f"Lists: {list_count} | Items: {total_items}")
            
            # Emit signal
            self.counts_changed.emit(list_count, total_items)
            
        except Exception as e:
            logger.error(f"Failed to update counts: {str(e)}")
    
    # =============================================================================
    # Abstract Methods - Override in Subclasses
    # =============================================================================
    
    def _create_new_list_structure(self, list_name: str):
        """Create new list structure - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _create_new_list_structure")
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to list data - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _get_list_data_path")
    
    def _load_list_data(self, list_name: str):
        """Load list data - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _load_list_data")
    
    def _save_current_data(self):
        """Save current data - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _save_current_data")
    
    def _import_data(self):
        """Import data from file - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _import_data")
    
    def _export_data(self):
        """Export data to file - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _export_data")
    
    def _list_exists(self, list_name: str) -> bool:
        """Check if list exists - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _list_exists")
    
    def _delete_list_structure(self, list_name: str):
        """Delete list structure - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _delete_list_structure")
    
    def _rename_list(self, old_name: str, new_name: str):
        """Rename list - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _rename_list")
    
    def _count_items_in_list(self, list_name: str) -> int:
        """Count items in a list - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _count_items_in_list")