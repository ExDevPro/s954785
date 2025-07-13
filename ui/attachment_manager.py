# ui/attachment_manager.py (Complete Code: Auto Dedupe, Columns, Icons, Fixes)
import os
import shutil
import hashlib
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QLabel, QListWidget, QListWidgetItem, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QHBoxLayout, QVBoxLayout, QInputDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu,
    QFileIconProvider # Correct icon provider import
)
from PyQt6.QtGui import QIcon, QAction, QCursor, QDesktopServices
# Ensure all necessary QtCore classes are imported
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QFileInfo, QUrl, QDateTime, QLocale # QLocale is needed
)

# (BASE_PATH, DATA_DIR, count_attachment_folders_and_files remain the same)
BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_PATH, 'data', 'attachments')

def count_attachment_folders_and_files(base_dir):
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
                    except Exception: pass
    except Exception: pass
    # print(f"Attachment count: {folder_count} lists, {total_file_count} total files")
    return folder_count, total_file_count

class AttachmentManager(QWidget):
    counts_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.current_list_path = None
        self.icon_provider = QFileIconProvider() # Correct provider
        self._build_ui()
        self._refresh_list()

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