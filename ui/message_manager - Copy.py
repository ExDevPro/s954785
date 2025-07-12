# ui/message_manager.py (Corrected DATA_DIR definition)
import os
import shutil
import traceback
import re # Added for consistency
from functools import partial # For connecting buttons with arguments

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QProgressBar, QApplication, QStyle, QAbstractItemView
)
from PyQt6.QtGui import QAction, QCursor # Added QCursor for consistency
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSize

# *** CORRECTED: Ensure BASE_PATH and DATA_DIR are defined at module level ***
BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
# Define the specific data directory for messages
DATA_DIR = os.path.join(BASE_PATH, 'data', 'messages')


# --- Helper Functions ---
def count_files_in_folders(base_dir):
    """Counts total files across all subdirectories in base_dir."""
    folder_count = 0
    total_file_count = 0
    try:
        if os.path.isdir(base_dir):
            for item_name in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item_name)
                if os.path.isdir(item_path):
                    folder_count += 1
                    try:
                        # Count files directly within this folder
                        files_in_folder = [f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))]
                        total_file_count += len(files_in_folder)
                    except Exception:
                        pass # Ignore errors reading subfolder contents for count
    except Exception:
        pass # Ignore errors reading base directory
    return folder_count, total_file_count

# --- Background Thread for Copying Files/Folders ---
class MessageCopyThread(QThread):
    """Worker thread for copying files/folders during import."""
    copy_finished = pyqtSignal(bool, str, int)
    copy_progress = pyqtSignal(int, int)

    def __init__(self, items_to_copy, destination_folder, parent=None):
        super().__init__(parent)
        self.items_to_copy = items_to_copy
        self.destination_folder = destination_folder
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        copied_count = 0
        total_items = len(self.items_to_copy)
        errors = []
        self.copy_progress.emit(0, total_items)
        print(f"Copy Thread: Starting copy of {total_items} items to {self.destination_folder}")
        for i, src_path in enumerate(self.items_to_copy):
            if not self._is_running: errors.append("Operation cancelled."); break
            base_name = os.path.basename(src_path)
            dst_path = os.path.join(self.destination_folder, base_name)
            try:
                if os.path.isdir(src_path):
                    if os.path.exists(dst_path): print(f"Copy Thread: Folder '{base_name}' exists, skipping copytree.")
                    else: shutil.copytree(src_path, dst_path, dirs_exist_ok=True); print(f"Copy Thread: Copied folder {src_path} to {dst_path}")
                elif os.path.isfile(src_path):
                    if os.path.exists(dst_path): print(f"Copy Thread: File '{base_name}' exists, skipping.")
                    else: shutil.copy2(src_path, dst_path); print(f"Copy Thread: Copied file {src_path} to {dst_path}")
                else: print(f"Copy Thread: Source item '{src_path}' not file/folder, skipping.")
                copied_count += 1
            except Exception as e: error_msg = f"Failed to copy '{base_name}': {e}"; errors.append(error_msg); print(f"Copy Thread: Error - {error_msg}")
            self.copy_progress.emit(i + 1, total_items)

        if not self._is_running: message = "Import cancelled."; success = False
        elif errors: message = "Import completed with errors:\n- " + "\n- ".join(errors); success = False
        else: message = f"Import successful. Processed {copied_count} item(s)."; success = True
        print(f"Copy Thread: Finished. Success: {success}, Message: {message}, Copied: {copied_count}")
        self.copy_finished.emit(success, message, copied_count)


# --- Message Manager UI ---
class MessageManager(QWidget):
    counts_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # *** This line should now work as DATA_DIR is defined above ***
        os.makedirs(DATA_DIR, exist_ok=True)
        self.current_list_path = None
        self.copy_thread = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        # This part remains the same as the previous version,
        # it correctly uses QAbstractItemView which is now imported.
        main_layout = QHBoxLayout(self)
        left_pane_widget = QWidget()
        left_layout = QVBoxLayout(left_pane_widget)
        left_layout.setSpacing(5)
        self.header_label = QLabel("0 lists – 0 files")
        self.header_label.setObjectName("liveHeaderLabel")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.header_label)
        list_button_layout = QHBoxLayout()
        btn_new = QPushButton("＋ New List")
        btn_new.setToolTip("Create a new empty message list folder")
        btn_new.clicked.connect(self._new_list)
        btn_del = QPushButton("🗑️ Delete List")
        btn_del.setToolTip("Delete the selected message list folder and all its contents")
        btn_del.clicked.connect(self._delete_list)
        list_button_layout.addWidget(btn_new)
        list_button_layout.addWidget(btn_del)
        left_layout.addLayout(list_button_layout)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("messageListWidget")
        self.list_widget.currentTextChanged.connect(self._load_list_contents)
        left_layout.addWidget(self.list_widget)
        right_pane_widget = QWidget()
        right_layout = QVBoxLayout(right_pane_widget)
        right_layout.setSpacing(5)
        file_action_layout = QHBoxLayout()
        btn_import = QPushButton("⬆️ Import Files/Folder")
        btn_import.setToolTip("Copy files or a folder's contents into the selected message list")
        btn_import.clicked.connect(self._import_files_or_folder)
        btn_refresh = QPushButton("🔄 Refresh Files")
        btn_refresh.setToolTip("Reload the list of files in the selected list")
        btn_refresh.clicked.connect(lambda: self._load_list_contents(
            self.list_widget.currentItem().text() if self.list_widget.currentItem() else None
        ))
        file_action_layout.addWidget(btn_import)
        file_action_layout.addWidget(btn_refresh)
        file_action_layout.addStretch(1)
        right_layout.addLayout(file_action_layout)
        self.file_table = QTableWidget()
        self.file_table.setObjectName("messageFileTable")
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Action"])
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Read-only
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        right_layout.addWidget(self.file_table, 2)
        self.preview_area = QTextEdit()
        self.preview_area.setObjectName("messagePreviewArea")
        self.preview_area.setReadOnly(True)
        self.preview_area.setPlaceholderText("Click 'Preview' on a .txt or .html file...")
        right_layout.addWidget(self.preview_area, 3)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Importing... %p%")
        right_layout.addWidget(self.progress_bar)
        main_layout.addWidget(left_pane_widget, 1)
        main_layout.addWidget(right_pane_widget, 3)

    # --- List Management Methods --- (_update_header_counts, _refresh_list, _new_list, _delete_list, _clear_right_pane)
    # (No changes needed in these methods from the previous version)
    def _update_header_counts(self):
        folder_count, total_file_count = count_files_in_folders(DATA_DIR)
        self.header_label.setText(f"{folder_count} lists – {total_file_count} files")
        self.counts_changed.emit(folder_count, total_file_count)

    def _refresh_list(self):
        self.list_widget.blockSignals(True)
        current_selection_name = self.list_widget.currentItem().text() if self.list_widget.currentItem() else None
        self.list_widget.clear(); found_selection = False
        try:
            if os.path.isdir(DATA_DIR):
                for name in sorted(os.listdir(DATA_DIR)):
                    if os.path.isdir(os.path.join(DATA_DIR, name)):
                        self.list_widget.addItem(name)
                        if name == current_selection_name: found_selection = True
        except Exception as e: QMessageBox.critical(self, "Error Refreshing Lists", f"Could not read message directories:\n{e}")
        if found_selection and current_selection_name:
             items = self.list_widget.findItems(current_selection_name, Qt.MatchFlag.MatchExactly)
             if items and self.list_widget.currentItem() != items[0]: self.list_widget.setCurrentItem(items[0])
        self.list_widget.blockSignals(False); self._update_header_counts()
        if not self.list_widget.currentItem(): self._clear_right_pane()

    def _new_list(self):
        name, ok = QInputDialog.getText(self, "New Message List", "Enter list name:")
        if ok and name and name.strip():
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
            if not clean_name: QMessageBox.warning(self, "Invalid Name","Please enter a valid list name."); return
            path = os.path.join(DATA_DIR, clean_name)
            if os.path.exists(path): QMessageBox.warning(self, "Exists", f"List (folder) '{clean_name}' already exists."); return
            try:
                os.makedirs(path); print(f"Created new message list folder: {path}")
                self._refresh_list()
                items = self.list_widget.findItems(clean_name, Qt.MatchFlag.MatchExactly)
                if items: self.list_widget.setCurrentItem(items[0])
            except Exception as e: QMessageBox.critical(self, "Error Creating List", f"Could not create directory '{clean_name}':\n{e}")

    def _delete_list(self):
        current_item = self.list_widget.currentItem()
        if not current_item: QMessageBox.warning(self, "No Selection", "Please select a message list to delete."); return
        name = current_item.text(); path_to_delete = os.path.join(DATA_DIR, name)
        if QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete the message list '{name}' and all files inside it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path_to_delete):
                    shutil.rmtree(path_to_delete); print(f"Deleted message list folder: {name}")
                    if self.current_list_path == path_to_delete: self._clear_right_pane(); self.current_list_path = None
                    self._refresh_list()
                else: QMessageBox.warning(self, "Not Found", f"Directory '{name}' not found."); self._refresh_list()
            except Exception as e: QMessageBox.critical(self, "Error Deleting", f"Could not delete list '{name}':\n{e}")

    def _clear_right_pane(self):
        self.file_table.setRowCount(0); self.preview_area.clear()
        self.preview_area.setPlaceholderText("Select a message list folder on the left.")

    # --- File Loading and Display --- (_load_list_contents, _show_preview)
    # (No changes needed in these methods from the previous version)
    def _load_list_contents(self, list_name):
        self.file_table.setRowCount(0); self.preview_area.clear()
        if not list_name: self.current_list_path = None; self._clear_right_pane(); print("Message list selection cleared."); return
        new_path = os.path.join(DATA_DIR, list_name)
        # Avoid reload if path didn't change AND table has rows (assumes content didn't change externally without refresh)
        if new_path == self.current_list_path and self.file_table.rowCount() > 0: return
        self.current_list_path = new_path
        if not os.path.isdir(self.current_list_path):
             QMessageBox.warning(self, "Error", f"Selected list folder '{list_name}' not found."); self.current_list_path = None
             self._clear_right_pane(); self._refresh_list(); return
        print(f"Loading contents for message list: {list_name}")
        try:
            all_files = sorted([f for f in os.listdir(self.current_list_path) if os.path.isfile(os.path.join(self.current_list_path, f))])
            display_files = [f for f in all_files if f.lower().endswith(('.txt', '.html'))]
            self.file_table.setRowCount(len(display_files)); self.file_table.blockSignals(True)
            for row, filename in enumerate(display_files):
                filepath = os.path.join(self.current_list_path, filename)
                item_name = QTableWidgetItem(filename); item_name.setFlags(item_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.file_table.setItem(row, 0, item_name)
                btn_preview = QPushButton("Preview"); btn_preview.setToolTip(f"Preview content of {filename}")
                btn_preview.clicked.connect(partial(self._show_preview, filepath))
                self.file_table.setCellWidget(row, 1, btn_preview)
            self.file_table.resizeColumnsToContents(); self.file_table.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Files", f"Could not load files from list '{list_name}':\n{e}")
            self._clear_right_pane(); self.current_list_path = None

    def _show_preview(self, filepath):
        if not os.path.exists(filepath): QMessageBox.warning(self, "Preview Error", f"File not found:\n{filepath}"); return
        print(f"Previewing file: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
            max_preview_chars = 20000
            if len(content) > max_preview_chars: content = content[:max_preview_chars] + "\n\n[Preview truncated]"
            if filepath.lower().endswith('.html'): self.preview_area.setHtml(content)
            elif filepath.lower().endswith('.txt'): self.preview_area.setPlainText(content)
            else: self.preview_area.setPlainText(f"Preview not available.\n({os.path.basename(filepath)})")
        except Exception as e:
            error_msg = f"Could not read or display file:\n{filepath}\n\nError: {e}"
            self.preview_area.setPlainText(error_msg); QMessageBox.warning(self, "Preview Error", error_msg)

    # --- Import Methods --- (_import_files_or_folder, _on_copy_progress, _on_copy_finished)
    # (No changes needed in these methods from the previous version)
    def _import_files_or_folder(self):
        if not self.current_list_path or not os.path.isdir(self.current_list_path): QMessageBox.warning(self, "Select List", "Please select a message list folder first."); return
        if self.copy_thread and self.copy_thread.isRunning(): QMessageBox.warning(self, "Import Running", "An import operation is already in progress."); return
        msgBox = QMessageBox(self); msgBox.setWindowTitle("Import Type"); msgBox.setText("What do you want to import?")
        msgBox.setIcon(QMessageBox.Icon.Question); files_button = msgBox.addButton("Select Files", QMessageBox.ButtonRole.ActionRole)
        folder_button = msgBox.addButton("Select Folder Contents", QMessageBox.ButtonRole.ActionRole); msgBox.addButton(QMessageBox.StandardButton.Cancel); msgBox.exec()
        items_to_process = []
        if msgBox.clickedButton() == files_button:
            files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Import", "", "All Files (*.*)");
            if files: items_to_process = files
        elif msgBox.clickedButton() == folder_button:
            src_folder = QFileDialog.getExistingDirectory(self, "Select Folder to Import Contents From")
            if src_folder:
                try: items_to_process = [os.path.join(src_folder, item) for item in os.listdir(src_folder)]
                except Exception as e: QMessageBox.critical(self, "Error Reading Folder", f"Could not list items in source folder:\n{e}"); return
        if not items_to_process: print("No items selected for import."); return
        self.progress_bar.setVisible(True); self.progress_bar.setValue(0); self.progress_bar.setFormat("Copying... %p%")
        print(f"Starting copy thread for {len(items_to_process)} items.")
        self.copy_thread = MessageCopyThread(items_to_process, self.current_list_path, self)
        self.copy_thread.copy_progress.connect(self._on_copy_progress)
        self.copy_thread.copy_finished.connect(self._on_copy_finished); self.copy_thread.start()

    def _on_copy_progress(self, current, total):
        if total > 0: percentage = int((current / total) * 100); self.progress_bar.setValue(percentage)
        else: self.progress_bar.setValue(0)

    def _on_copy_finished(self, success, message, items_copied_count):
        print("Copy thread finished."); self.progress_bar.setVisible(False); self.copy_thread = None
        if success: QMessageBox.information(self, "Import Complete", message)
        else: QMessageBox.warning(self, "Import Finished with Errors", message)
        if self.current_list_path and os.path.isdir(self.current_list_path): self._load_list_contents(os.path.basename(self.current_list_path))
        else: self._refresh_list()
        self._update_header_counts()

    # --- Cleanup ---
    def closeEvent(self, event):
        if self.copy_thread and self.copy_thread.isRunning():
            print("Attempting to stop copy thread on close..."); self.copy_thread.stop()
            self.copy_thread.wait(1000); print("Copy thread stopped.")
        event.accept()

# ... (Standalone test code remains the same) ...
if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    if not os.path.exists(os.path.join(BASE_PATH, 'data')): os.makedirs(os.path.join(BASE_PATH, 'data'))
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if not os.path.exists(os.path.join(DATA_DIR, "TestList")): os.makedirs(os.path.join(DATA_DIR, "TestList"))
    if not os.path.exists(os.path.join(DATA_DIR, "TestList","dummy.txt")):
         with open(os.path.join(DATA_DIR, "TestList", "dummy.txt"), "w") as f: f.write("test text")
    if not os.path.exists(os.path.join(DATA_DIR, "TestList","dummy.html")):
         with open(os.path.join(DATA_DIR, "TestList", "dummy.html"), "w") as f: f.write("<h1>Test HTML</h1><p>This is <b>bold</b>.</p>")

    from PyQt6.QtWidgets import QMainWindow # Import QMainWindow for standalone test
    win = QMainWindow()
    manager = MessageManager()
    win.setCentralWidget(manager)
    win.setWindowTitle("Message Manager Test")
    win.resize(900, 600)
    win.show()
    sys.exit(app.exec())