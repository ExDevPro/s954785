# ui/message_manager.py (Reverted counting logic to folders)
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
    QProgressBar, QApplication, QStyle, QAbstractItemView, QMenu
)
from PyQt6.QtGui import QAction, QCursor, QDesktopServices
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSize, QUrl

# --- Import the Preview Window ---
from .message_preview import MessagePreviewWindow, find_message_file

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'messages')


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