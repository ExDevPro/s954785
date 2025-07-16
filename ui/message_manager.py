# Enhanced Message Manager with Description Support

import os
import shutil
import traceback
import re
from functools import partial
import time

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QProgressBar, QApplication, QStyle, QAbstractItemView, QMenu,
    QDialog, QDialogButtonBox, QFrame, QSplitter, QScrollArea,
    QSizePolicy
)
from PyQt6.QtGui import QAction, QCursor, QDesktopServices, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSize, QUrl

# --- Import the Preview Window ---
try:
    from .message_preview import MessagePreviewWindow, find_message_file
except ImportError:
    # Fallback if preview window doesn't exist
    MessagePreviewWindow = None
    def find_message_file(folder_path):
        return None

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'messages')

class CreateMessageListDialog(QDialog):
    """Professional dialog for creating new message lists with descriptions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Message List")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout(self)
        
        # List name
        layout.addWidget(QLabel("List Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter message list name...")
        layout.addWidget(self.name_edit)
        
        # Description
        layout.addWidget(QLabel("Description (Optional):"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Enter description for this message list...")
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

class EnhancedMessageManager(QWidget):
    """Enhanced Message Manager with description support and better UI."""
    
    counts_changed = pyqtSignal()
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.current_list = None
        
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
        
        # Right panel - Messages view
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
        header = QLabel("💬 Message Lists")
        header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("QLabel { background: #9b59b6; color: white; padding: 8px; border-radius: 4px; }")
        layout.addWidget(header)
        
        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search lists...")
        self.search_edit.textChanged.connect(self._filter_lists)
        layout.addWidget(self.search_edit)
        
        # Lists
        self.message_lists = QListWidget()
        self.message_lists.itemClicked.connect(self._on_list_selected)
        self.message_lists.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_lists.customContextMenuRequested.connect(self._show_list_context_menu)
        layout.addWidget(self.message_lists)
        
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
        """Create the right panel with messages table."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(panel)
        
        # Header
        header_layout = QHBoxLayout()
        self.table_header = QLabel("📋 Messages")
        self.table_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.table_header)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Messages table
        self.message_table = QTableWidget()
        self.message_table.setColumnCount(3)
        self.message_table.setHorizontalHeaderLabels(["Message Name", "Type", "Size"])
        self.message_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.message_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.message_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_table.customContextMenuRequested.connect(self._show_message_context_menu)
        layout.addWidget(self.message_table)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.btn_add_message = QPushButton("➕ Add Message")
        self.btn_add_message.clicked.connect(self._add_message)
        self.btn_add_message.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 6px 12px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_add_message)
        
        self.btn_preview = QPushButton("👁️ Preview")
        self.btn_preview.clicked.connect(self._preview_message)
        buttons_layout.addWidget(self.btn_preview)
        
        self.btn_edit = QPushButton("✏️ Edit")
        self.btn_edit.clicked.connect(self._edit_message)
        buttons_layout.addWidget(self.btn_edit)
        
        self.btn_delete_message = QPushButton("🗑️ Delete")
        self.btn_delete_message.clicked.connect(self._delete_message)
        self.btn_delete_message.setStyleSheet("QPushButton { background: #e74c3c; color: white; padding: 6px 12px; border-radius: 4px; }")
        buttons_layout.addWidget(self.btn_delete_message)
        
        buttons_layout.addStretch()
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
                background: #9b59b6;
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
                border: 2px solid #9b59b6;
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
        """Load all available message lists."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.message_lists.clear()
        
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                self.message_lists.addItem(item)
        
        self.counts_changed.emit()
    
    def _filter_lists(self):
        """Filter lists based on search text."""
        search_text = self.search_edit.text().lower()
        for i in range(self.message_lists.count()):
            item = self.message_lists.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def _create_new_list(self):
        """Create a new message list."""
        dialog = CreateMessageListDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_list_data()
            list_name = data['name']
            description = data['description']
            
            # Check if list already exists
            list_dir = os.path.join(DATA_DIR, list_name)
            if os.path.exists(list_dir):
                QMessageBox.warning(self, "List Exists", f"A message list named '{list_name}' already exists.")
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
                for i in range(self.message_lists.count()):
                    if self.message_lists.item(i).text() == list_name:
                        self.message_lists.setCurrentRow(i)
                        self._on_list_selected(self.message_lists.item(i))
                        break
                
                QMessageBox.information(self, "Success", f"Message list '{list_name}' created successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create list: {str(e)}")
    
    def _delete_list(self):
        """Delete the selected message list."""
        current_item = self.message_lists.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a list to delete.")
            return
        
        list_name = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the message list '{list_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                list_dir = os.path.join(DATA_DIR, list_name)
                shutil.rmtree(list_dir)
                
                self._load_lists()
                self._clear_messages_view()
                
                QMessageBox.information(self, "Success", f"Message list '{list_name}' deleted successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete list: {str(e)}")
    
    def _on_list_selected(self, item):
        """Handle list selection."""
        if not item:
            return
        
        list_name = item.text()
        self.current_list = list_name
        
        # Update description
        self._load_description(list_name)
        
        # Load messages
        self._load_messages(list_name)
        
        # Update UI
        self.table_header.setText(f"📋 {list_name} - Messages")
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
    
    def _load_messages(self, list_name):
        """Load messages for the selected list."""
        list_dir = os.path.join(DATA_DIR, list_name)
        self.message_table.setRowCount(0)
        
        if not os.path.exists(list_dir):
            return
        
        try:
            for item in os.listdir(list_dir):
                item_path = os.path.join(list_dir, item)
                if os.path.isdir(item_path) and item != "description.txt":
                    # Add message folder to table
                    row = self.message_table.rowCount()
                    self.message_table.insertRow(row)
                    
                    # Message name
                    self.message_table.setItem(row, 0, QTableWidgetItem(item))
                    
                    # Message type (determine from files in folder)
                    msg_type = self._get_message_type(item_path)
                    self.message_table.setItem(row, 1, QTableWidgetItem(msg_type))
                    
                    # Folder size
                    size = self._get_folder_size(item_path)
                    self.message_table.setItem(row, 2, QTableWidgetItem(size))
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load messages: {str(e)}")
    
    def _get_message_type(self, folder_path):
        """Determine message type from files in folder."""
        try:
            files = os.listdir(folder_path)
            if any(f.endswith('.html') for f in files):
                return "HTML"
            elif any(f.endswith('.txt') for f in files):
                return "Text"
            else:
                return "Mixed"
        except:
            return "Unknown"
    
    def _get_folder_size(self, folder_path):
        """Get human-readable folder size."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            
            # Convert to human-readable format
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024.0:
                    return f"{total_size:.1f} {unit}"
                total_size /= 1024.0
            return f"{total_size:.1f} TB"
        except:
            return "Unknown"
    
    def _clear_messages_view(self):
        """Clear the messages view."""
        self.message_table.setRowCount(0)
        self.current_list = None
        self.table_header.setText("📋 Messages")
        self.description_label.setText("Select a list to view its description.")
        self.btn_edit_desc.setEnabled(False)
    
    # ========== Message Management Methods ==========
    
    def _add_message(self):
        """Add a new message to the current list."""
        if not self.current_list:
            QMessageBox.warning(self, "No List", "Please select a list first.")
            return
        
        msg_name, ok = QInputDialog.getText(self, "New Message", "Enter message name:")
        if ok and msg_name.strip():
            msg_name = msg_name.strip()
            msg_dir = os.path.join(DATA_DIR, self.current_list, msg_name)
            
            if os.path.exists(msg_dir):
                QMessageBox.warning(self, "Message Exists", f"A message named '{msg_name}' already exists.")
                return
            
            try:
                os.makedirs(msg_dir, exist_ok=True)
                
                # Create default HTML template
                html_file = os.path.join(msg_dir, "message.html")
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Email Message</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Hello {{first_name}}!</h1>
    <p>This is your new email message template.</p>
    <p>You can edit this message and add your content here.</p>
    <p>Best regards,<br>
    {{from_name}}</p>
</body>
</html>""")
                
                self._load_messages(self.current_list)
                QMessageBox.information(self, "Success", f"Message '{msg_name}' created successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create message: {str(e)}")
    
    def _preview_message(self):
        """Preview the selected message."""
        row = self.message_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a message to preview.")
            return
        
        msg_name = self.message_table.item(row, 0).text()
        msg_dir = os.path.join(DATA_DIR, self.current_list, msg_name)
        
        if MessagePreviewWindow:
            try:
                preview = MessagePreviewWindow(msg_dir, self)
                preview.show()
            except Exception as e:
                QMessageBox.critical(self, "Preview Error", f"Failed to preview message: {str(e)}")
        else:
            QMessageBox.information(self, "Preview", f"Preview for '{msg_name}' would open here.")
    
    def _edit_message(self):
        """Edit the selected message."""
        row = self.message_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a message to edit.")
            return
        
        msg_name = self.message_table.item(row, 0).text()
        msg_dir = os.path.join(DATA_DIR, self.current_list, msg_name)
        
        try:
            # Open message folder in file explorer
            QDesktopServices.openUrl(QUrl.fromLocalFile(msg_dir))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open message folder: {str(e)}")
    
    def _delete_message(self):
        """Delete the selected message."""
        row = self.message_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a message to delete.")
            return
        
        msg_name = self.message_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the message '{msg_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                msg_dir = os.path.join(DATA_DIR, self.current_list, msg_name)
                shutil.rmtree(msg_dir)
                
                self._load_messages(self.current_list)
                QMessageBox.information(self, "Success", f"Message '{msg_name}' deleted successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete message: {str(e)}")
    
    # ========== Context Menu Methods ==========
    
    def _show_list_context_menu(self, position):
        """Show context menu for lists."""
        item = self.message_lists.itemAt(position)
        
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
        
        menu.exec(self.message_lists.mapToGlobal(position))
    
    def _show_message_context_menu(self, position):
        """Show context menu for messages."""
        menu = QMenu()
        
        menu.addAction("➕ Add Message", self._add_message)
        
        if self.message_table.currentRow() >= 0:
            menu.addAction("👁️ Preview", self._preview_message)
            menu.addAction("✏️ Edit", self._edit_message)
            menu.addAction("🗑️ Delete", self._delete_message)
        
        menu.exec(self.message_table.mapToGlobal(position))
    
    # ========== Public Methods ==========
    
    def get_list_count(self):
        """Get the number of message lists."""
        return self.message_lists.count()
    
    def refresh_lists(self):
        """Refresh the lists display."""
        self._load_lists()
    
    # ========== Original Methods (for compatibility) ==========
    
    def count_message_folders_for_dashboard(self):
        """Count message folders for dashboard display."""
        list_folder_count = 0
        total_message_subfolder_count = 0
        
        try:
            if os.path.isdir(DATA_DIR):
                for list_name in os.listdir(DATA_DIR):
                    list_path = os.path.join(DATA_DIR, list_name)
                    if os.path.isdir(list_path):
                        list_folder_count += 1
                        try:
                            message_folders_in_list = [
                                msg_folder for msg_folder in os.listdir(list_path)
                                if os.path.isdir(os.path.join(list_path, msg_folder)) and msg_folder != "description.txt"
                            ]
                            total_message_subfolder_count += len(message_folders_in_list)
                        except Exception as e:
                            print(f"Warning: Could not read subfolders in list folder {list_path}: {e}")
        except Exception as e:
            print(f"Error counting message folders: {e}")
        
        return list_folder_count, total_message_subfolder_count


# --- Helper Functions ---
# *** REVERTED COUNTING LOGIC TO ORIGINAL INTENT (COUNTING MESSAGE SUBFOLDERS) ***
def count_message_folders_for_dashboard(base_dir):
    """
    Counts message list folders and total message subfolders within them.
    Returns: (list_folder_count, total_message_subfolder_count)
    """
    list_folder_count = 0
    total_message_subfolder_count = 0
    try:
        if os.path.isdir(base_dir):
            # Iterate through list folders (e.g., 'dsa', 'fs', 'xz')
            for list_name in os.listdir(base_dir):
                list_path = os.path.join(base_dir, list_name)
                if os.path.isdir(list_path):
                    list_folder_count += 1
                    try:
                        # Count message subfolders (e.g., 'message_1', 'visual_message_9')
                        message_folders_in_list = [
                            msg_folder for msg_folder in os.listdir(list_path)
                            if os.path.isdir(os.path.join(list_path, msg_folder))
                        ]
                        total_message_subfolder_count += len(message_folders_in_list)
                    except Exception as e:
                        print(f"Warning: Could not read subfolders in list folder {list_path}: {e}")
                        pass # Ignore errors reading message folders inside a list folder
    except Exception as e:
        print(f"Error counting message folders for dashboard in {base_dir}: {e}")
        pass # Ignore errors reading base directory
    print(f"Dashboard count: {list_folder_count} lists, {total_message_subfolder_count} total message folders")
    return list_folder_count, total_message_subfolder_count


# --- Background Thread for Copying Files/Folders ---
# (MessageCopyThread remains the same)
class MessageCopyThread(QThread):
    copy_finished = pyqtSignal(bool, str, list)
    copy_progress = pyqtSignal(int, int)
    def __init__(self, message_tasks, parent=None):
        super().__init__(parent)
        self.message_tasks = message_tasks; self._is_running = True
    def stop(self): self._is_running = False
    def run(self):
        created_folders = []; total_files_to_copy = sum(len(files) for _, files in self.message_tasks)
        files_copied_so_far = 0; errors = []; success = True
        print(f"Copy Thread: Starting import for {len(self.message_tasks)} messages ({total_files_to_copy} total files).")
        self.copy_progress.emit(0, total_files_to_copy)
        for dest_folder_path, source_files in self.message_tasks:
            if not self._is_running: errors.append("Operation cancelled."); success = False; break
            message_name = os.path.basename(dest_folder_path)
            try:
                if not os.path.exists(dest_folder_path): os.makedirs(dest_folder_path); print(f"Copy Thread: Created folder {dest_folder_path}")
                folder_errors = []
                for src_path in source_files:
                    if not self._is_running: folder_errors.append("Cancelled during file copy."); break
                    base_name = os.path.basename(src_path); dst_path = os.path.join(dest_folder_path, base_name)
                    try:
                        if os.path.exists(dst_path): print(f"Copy Thread: File '{base_name}' exists in {message_name}, skipping.")
                        else: shutil.copy2(src_path, dst_path)
                        files_copied_so_far += 1; self.copy_progress.emit(files_copied_so_far, total_files_to_copy)
                    except Exception as e: err = f"Failed copy {base_name} for {message_name}: {e}"; folder_errors.append(err); errors.append(err); print(f"Copy Thread: Error - {err}"); success = False
                if not folder_errors: created_folders.append(dest_folder_path)
            except Exception as e: err = f"Failed create/process folder {message_name}: {e}"; errors.append(err); print(f"Copy Thread: Error - {err}"); success = False
            if not self._is_running: break
        if not self._is_running: message = "Import cancelled."
        elif errors: message = f"Import finished with {len(errors)} errors. {len(created_folders)} messages processed.\nSee console/logs."
        else: message = f"Import successful. {len(created_folders)} messages imported."
        print(f"Copy Thread: Finished. Success: {success}, Message: {message}, Created Folders: {len(created_folders)}")
        self.copy_finished.emit(success, message, created_folders)


# --- Message Manager UI ---
class MessageManager(QWidget):
    # Existing signal: emits (list_folder_count, total_messages_count)
    counts_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.current_list_path = None
        self.current_message_folders = []
        self.copy_thread = None
        self.preview_window = None
        self._build_ui()
        self._refresh_list() # Initial load and count update

    def _build_ui(self):
        # (UI building remains the same)
        main_layout = QHBoxLayout(self)
        left_pane_widget = QWidget(); left_layout = QVBoxLayout(left_pane_widget); left_layout.setSpacing(5)
        list_button_layout = QHBoxLayout(); btn_new = QPushButton("＋ New List"); btn_new.clicked.connect(self._new_list)
        btn_del = QPushButton("🗑️ Delete List"); btn_del.clicked.connect(self._delete_list)
        list_button_layout.addWidget(btn_new); list_button_layout.addWidget(btn_del); left_layout.addLayout(list_button_layout)
        self.list_widget = QListWidget(); self.list_widget.setObjectName("messageListWidget"); self.list_widget.currentTextChanged.connect(self._load_list_contents)
        left_layout.addWidget(self.list_widget)
        right_pane_widget = QWidget(); right_layout = QVBoxLayout(right_pane_widget); right_layout.setSpacing(5)
        file_action_layout = QHBoxLayout()
        btn_import = QPushButton("✉️ Import Message(s)"); btn_import.setToolTip("Import one or more messages (txt/html + auto-detected images)"); btn_import.clicked.connect(self._import_messages)
        btn_refresh = QPushButton("🔄 Refresh Messages"); btn_refresh.clicked.connect(lambda: self._load_list_contents(self.list_widget.currentItem().text() if self.list_widget.currentItem() else None))
        file_action_layout.addWidget(btn_import); file_action_layout.addWidget(btn_refresh); file_action_layout.addStretch(1)
        right_layout.addLayout(file_action_layout)
        self.status_label = QLabel("Messages: 0"); self.status_label.setObjectName("messageStatusBarLabel")
        right_layout.addWidget(self.status_label)
        self.file_table = QTableWidget(); self.file_table.setObjectName("messageFileTable"); self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["Message Name", "Action"]); header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_file_context_menu)
        self.file_table.itemDoubleClicked.connect(self._handle_item_double_click)
        right_layout.addWidget(self.file_table)
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0); self.progress_bar.setTextVisible(True); self.progress_bar.setFormat("Importing... %p%")
        right_layout.addWidget(self.progress_bar)
        main_layout.addWidget(left_pane_widget, 1); main_layout.addWidget(right_pane_widget, 3)


    # --- List (Folder) Management Methods ---
    def _update_dashboard_counts(self):
        """Calculates counts using the FOLDER counting logic and emits the signal."""
        # *** Uses the REVERTED counting function (counts message subfolders) ***
        list_folder_count, total_message_subfolder_count = count_message_folders_for_dashboard(DATA_DIR)
        # Emit the signal with (list_count, total_message_subfolder_count)
        self.counts_changed.emit(list_folder_count, total_message_subfolder_count)

    # (Methods _refresh_list, _new_list, _delete_list, _clear_right_pane remain the same,
    #  they correctly call _update_dashboard_counts which now uses the folder counting logic)
    def _refresh_list(self):
        self.list_widget.blockSignals(True); current_selection_name = self.list_widget.currentItem().text() if self.list_widget.currentItem() else None
        self.list_widget.clear(); found_selection = False
        try:
            if os.path.isdir(DATA_DIR):
                for name in sorted(os.listdir(DATA_DIR)):
                    if os.path.isdir(os.path.join(DATA_DIR, name)): self.list_widget.addItem(name)
                    if name == current_selection_name: found_selection = True
        except Exception as e: QMessageBox.critical(self, "Error", f"Could not read message dirs:\n{e}")
        if found_selection and current_selection_name:
             items = self.list_widget.findItems(current_selection_name, Qt.MatchFlag.MatchExactly)
             if items and self.list_widget.currentItem() != items[0]: self.list_widget.setCurrentItem(items[0])
        self.list_widget.blockSignals(False)
        self._update_dashboard_counts()
        if self.list_widget.currentItem(): self._load_list_contents(self.list_widget.currentItem().text())
        else: self._clear_right_pane()
    def _new_list(self):
        name, ok = QInputDialog.getText(self, "New Message List", "Enter list name:")
        if ok and name and name.strip():
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
            if not clean_name: QMessageBox.warning(self, "Invalid Name","Enter valid name."); return
            path = os.path.join(DATA_DIR, clean_name)
            if os.path.exists(path): QMessageBox.warning(self, "Exists", f"List folder '{clean_name}' exists."); return
            try: os.makedirs(path); print(f"Created list folder: {path}"); self._refresh_list();
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not create dir '{clean_name}':\n{e}")
    def _delete_list(self):
        current_item = self.list_widget.currentItem()
        if not current_item: QMessageBox.warning(self, "No Selection", "Select list folder to delete."); return
        name = current_item.text(); path_to_delete = os.path.join(DATA_DIR, name)
        msg = f"Delete list folder '{name}' and ALL messages inside?"
        reply = QMessageBox.question(self, "Confirm Delete", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted = False; error_occurred = False
            try:
                if os.path.isdir(path_to_delete): shutil.rmtree(path_to_delete); print(f"Deleted list folder: {name}"); deleted = True
                else: QMessageBox.warning(self, "Not Found", f"Directory '{name}' not found.")
            except Exception as e: QMessageBox.critical(self, "Error Deleting", f"Could not delete list '{name}':\n{e}"); error_occurred = True
            if deleted and self.current_list_path == path_to_delete: self._clear_right_pane(); self.current_list_path = None
            self._refresh_list()
    def _clear_right_pane(self):
        self.file_table.setRowCount(0); self.status_label.setText("Messages: 0"); self.current_message_folders = []


    # --- Message (Subfolder) Loading and Display ---
    # (No changes needed in _load_list_contents, _handle_item_double_click,
    # _open_preview_window)
    def _load_list_contents(self, list_name):
        self.file_table.setRowCount(0); self.current_message_folders = []
        if not list_name: self.current_list_path = None; self._clear_right_pane(); print("List selection cleared."); return
        new_path = os.path.join(DATA_DIR, list_name)
        if new_path == self.current_list_path and len(self.current_message_folders) == self.file_table.rowCount() and self.file_table.rowCount() > 0 : return
        self.current_list_path = new_path
        if not os.path.isdir(self.current_list_path):
             QMessageBox.warning(self, "Error", f"List folder '{list_name}' not found."); self.current_list_path = None
             self._clear_right_pane(); self._refresh_list(); return
        print(f"Loading message folders from: {list_name}")
        try:
            self.current_message_folders = sorted([os.path.join(self.current_list_path, item) for item in os.listdir(self.current_list_path) if os.path.isdir(os.path.join(self.current_list_path, item))])
            self.file_table.setRowCount(len(self.current_message_folders)); self.file_table.blockSignals(True)
            for row, folder_path in enumerate(self.current_message_folders):
                message_name = os.path.basename(folder_path)
                item_name = QTableWidgetItem(message_name); item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.file_table.setItem(row, 0, item_name)
                btn_preview = QPushButton("Preview/Edit"); btn_preview.setToolTip(f"Preview/Edit {message_name}")
                btn_preview.clicked.connect(partial(self._open_preview_window, folder_path))
                self.file_table.setCellWidget(row, 1, btn_preview)
            self.file_table.resizeColumnsToContents(); self.file_table.blockSignals(False)
            self.status_label.setText(f"Messages: {len(self.current_message_folders)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load messages from '{list_name}':\n{e}")
            self._clear_right_pane(); self.current_list_path = None
    def _handle_item_double_click(self, item):
         if item is None: return; row = item.row()
         if 0 <= row < len(self.current_message_folders): self._open_preview_window(self.current_message_folders[row])
    def _open_preview_window(self, message_folder_path):
        if not self.current_message_folders: QMessageBox.warning(self, "Error", "No messages loaded."); return
        if self.preview_window and self.preview_window.isVisible(): self.preview_window.close()
        print(f"Opening preview window for message folder: {message_folder_path}")
        self.preview_window = MessagePreviewWindow(self.current_message_folders, message_folder_path, BASE_PATH, self)
        self.preview_window.message_modified.connect(self._handle_message_modification)
        self.preview_window.show()

    def _handle_message_modification(self, modified_folder_path):
        # (Updates counts after modification)
        print(f"Manager Notified: Message modified - {modified_folder_path}")
        self._update_dashboard_counts()

    # --- Import Methods ---
    # (No changes needed in _import_messages, _on_copy_progress)
    def _import_messages(self):
        if not self.current_list_path or not os.path.isdir(self.current_list_path): QMessageBox.warning(self, "Select List", "Select a message list folder first."); return
        if self.copy_thread and self.copy_thread.isRunning(): QMessageBox.warning(self, "Import Running", "Import in progress."); return
        primary_files, _ = QFileDialog.getOpenFileNames(self, "Select Primary Message File(s) (.txt/.html)", "", "Messages (*.txt *.html)")
        if not primary_files: return
        message_tasks = []; errors_preparing = []; image_parse_warnings = []
        print(f"Analyzing {len(primary_files)} primary files for import...")
        for primary_file_path in primary_files:
            source_folder = os.path.dirname(primary_file_path); base_name = os.path.splitext(os.path.basename(primary_file_path))[0]
            message_folder_name = re.sub(r'[<>:"/\\|?*]', '_', base_name.strip());
            if not message_folder_name: message_folder_name += f"_Imported_{len(message_tasks)+1}"
            counter = 1; final_folder_name = message_folder_name; destination_base = self.current_list_path
            while os.path.exists(os.path.join(destination_base, final_folder_name)): final_folder_name = f"{message_folder_name}_{counter}"; counter += 1
            destination_folder_path = os.path.join(destination_base, final_folder_name)
            files_to_copy_for_this_message = [primary_file_path]
            if primary_file_path.lower().endswith('.html'):
                try:
                    with open(primary_file_path, 'r', encoding='utf-8') as f: content = f.read()
                    image_sources = re.findall(r'<img[^>]+src\s*=\s*["\']([^"\'>]+)["\']', content, re.IGNORECASE)
                    for img_src in image_sources:
                        img_src = img_src.strip()
                        if not re.match(r"^[a-zA-Z]+:", img_src) and not img_src.startswith('data:'):
                            potential_img_path = os.path.abspath(os.path.join(source_folder, img_src))
                            if os.path.exists(potential_img_path) and os.path.isfile(potential_img_path):
                                if potential_img_path not in files_to_copy_for_this_message: files_to_copy_for_this_message.append(potential_img_path)
                            else:
                                missing_img_warning = f"'{os.path.basename(primary_file_path)}' refs missing image: '{img_src}' (in {source_folder})"
                                if missing_img_warning not in image_parse_warnings: image_parse_warnings.append(missing_img_warning)
                                print(f"    -> Warning: {missing_img_warning}")
                except Exception as e: err = f"Error parsing HTML {os.path.basename(primary_file_path)}: {e}"; errors_preparing.append(err); print(f"  Error: {err}"); continue
            print(f"  -> Prepared Task: Copy {len(files_to_copy_for_this_message)} file(s) (Primary: {os.path.basename(primary_file_path)}) TO FOLDER {final_folder_name}")
            message_tasks.append((destination_folder_path, files_to_copy_for_this_message))
        if errors_preparing: QMessageBox.warning(self, "Preparation Errors", "Errors while analyzing files:\n- " + "\n- ".join(errors_preparing))
        if image_parse_warnings: QMessageBox.warning(self, "Missing Images", "Some referenced images not found:\n\n- " + "\n- ".join(image_parse_warnings))
        if not message_tasks: QMessageBox.information(self, "No Messages", "No valid messages prepared for import."); return
        total_files_overall = sum(len(files) for _, files in message_tasks); self.progress_bar.setVisible(True); self.progress_bar.setValue(0); self.progress_bar.setFormat(f"Copying {total_files_overall} files... %p%")
        print(f"Starting copy thread for {len(message_tasks)} messages...")
        self.copy_thread = MessageCopyThread(message_tasks, self); self.copy_thread.copy_progress.connect(self._on_copy_progress); self.copy_thread.copy_finished.connect(self._on_import_messages_finished); self.copy_thread.start()
    def _on_copy_progress(self, current, total):
        if total > 0: percentage = int((current / total) * 100); self.progress_bar.setValue(percentage)
        else: self.progress_bar.setValue(0)

    def _on_import_messages_finished(self, success, message, created_folder_paths):
        # (Updates counts after import finishes)
        print("Multi-message copy thread finished."); self.progress_bar.setVisible(False); self.copy_thread = None
        if success: QMessageBox.information(self, "Import Complete", message)
        else: QMessageBox.warning(self, "Import Finished with Errors", message)
        self._load_list_contents(os.path.basename(self.current_list_path) if self.current_list_path else None)
        self._update_dashboard_counts()

    # --- Context Menu and Deletion ---
    # (No changes needed in _show_file_context_menu, _open_containing_list_folder, _open_selected_message_folder)
    def _show_file_context_menu(self, pos):
        menu = QMenu(self); selected_rows = self.file_table.selectionModel().selectedRows(); num_selected = len(selected_rows)
        action_delete = QAction(f"Delete {num_selected} Message(s)" if num_selected > 1 else "Delete Message", self); action_delete.setEnabled(num_selected > 0); action_delete.triggered.connect(self._delete_selected_messages); menu.addAction(action_delete)
        if num_selected == 1: action_open_folder = QAction("Open Message Folder", self); action_open_folder.triggered.connect(self._open_selected_message_folder); menu.addAction(action_open_folder)
        if self.current_list_path: action_open_list_folder = QAction("Open List Folder", self); action_open_list_folder.triggered.connect(self._open_containing_list_folder); menu.addAction(action_open_list_folder)
        menu.exec(self.file_table.mapToGlobal(pos))
    def _open_containing_list_folder(self):
        if self.current_list_path and os.path.isdir(self.current_list_path):
            success = False
            try: url = QUrl.fromLocalFile(self.current_list_path); success = QDesktopServices.openUrl(url)
            except Exception as e: QMessageBox.warning(self, "Error", f"An error occurred opening folder:\n{e}")
            if not success: QMessageBox.warning(self, "Error", f"Could not open folder (returned False):\n{self.current_list_path}")
        else: QMessageBox.warning(self, "Error", "Current list folder path not valid.")
    def _open_selected_message_folder(self):
        selected_rows = self.file_table.selectionModel().selectedRows()
        if len(selected_rows) != 1: return
        row = selected_rows[0].row()
        if 0 <= row < len(self.current_message_folders):
            folder_path = self.current_message_folders[row]
            if os.path.isdir(folder_path):
                success = False
                try: url = QUrl.fromLocalFile(folder_path); success = QDesktopServices.openUrl(url)
                except Exception as e: QMessageBox.warning(self, "Error", f"An error occurred opening message folder:\n{e}")
                if not success: QMessageBox.warning(self, "Error", f"Could not open message folder (returned False):\n{folder_path}")
            else: QMessageBox.warning(self, "Error", "Selected message folder path not valid.")

    def _delete_selected_messages(self):
        # (Updates counts after deletion)
        if not self.current_list_path: return
        selected_rows = self.file_table.selectionModel().selectedRows();
        if not selected_rows: return
        folders_to_delete = []; folder_names_display = []
        selected_indices = sorted([index.row() for index in selected_rows], reverse=True)
        for row_index in selected_indices:
            if 0 <= row_index < len(self.current_message_folders):
                 folder_path = self.current_message_folders[row_index]; folders_to_delete.append(folder_path); folder_names_display.append(os.path.basename(folder_path))
            else: print(f"Warning: Selected row index {row_index} out of bounds.")
        if not folders_to_delete: return
        reply = QMessageBox.question(self, "Confirm Delete", f"Permanently delete {len(folders_to_delete)} message(s)?\n\n- "+ "\n- ".join(folder_names_display[:10]) + ("..." if len(folder_names_display)>10 else ""), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0; errors = []
            for folder_path in folders_to_delete:
                try:
                    if os.path.isdir(folder_path): shutil.rmtree(folder_path); print(f"Deleted: {folder_path}"); deleted_count += 1
                    else: print(f"Skipping non-folder: {folder_path}")
                except Exception as e: error_msg = f"Could not delete {os.path.basename(folder_path)}: {e}"; errors.append(error_msg); print(f"Error: {error_msg}")
            if errors: QMessageBox.warning(self,"Deletion Errors", f"Finished. {deleted_count} message(s) deleted.\n\nErrors:\n- " + "\n- ".join(errors))
            elif deleted_count > 0: QMessageBox.information(self, "Deletion Complete", f"{deleted_count} message(s) deleted.")
            self._load_list_contents(os.path.basename(self.current_list_path) if self.current_list_path else None)
            self._update_dashboard_counts()

    # --- Cleanup ---
    def closeEvent(self, event):
        # (Remains the same)
        if self.preview_window and self.preview_window.isVisible(): self.preview_window.close()
        if self.copy_thread and self.copy_thread.isRunning(): self.copy_thread.stop(); self.copy_thread.wait(1000)
        event.accept()