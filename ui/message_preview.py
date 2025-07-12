# ui/message_preview.py (Fixed QFontDatabase TypeError)
import os
import sys
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QMessageBox, QSizePolicy, QSpacerItem, QToolButton, QStyle,
    QToolBar, QComboBox, QFontComboBox, QWidget
)
from PyQt6.QtGui import (
    QIcon, QTextDocument, QDesktopServices, QAction, QColor, QFont,
    QTextCharFormat, QTextBlockFormat, QTextCursor, QTextListFormat,
    QActionGroup, QFontDatabase # Verified imports
)
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QSize, QDir, QFileInfo, QIODevice

DEFAULT_ICON_SIZE = QSize(24, 24)
WINDOW_TITLE_PREFIX = "Message Preview/Edit"

# --- Helper ---
def find_message_file(folder_path):
    if not folder_path or not os.path.isdir(folder_path): return None
    try:
        files = os.listdir(folder_path)
        html_files = [f for f in files if f.lower().endswith('.html')]
        txt_files = [f for f in files if f.lower().endswith('.txt')]
        if html_files: return os.path.join(folder_path, html_files[0])
        if txt_files: return os.path.join(folder_path, txt_files[0])
    except Exception as e: print(f"Error finding message file in {folder_path}: {e}")
    return None

class MessagePreviewWindow(QDialog):
    message_modified = pyqtSignal(str)

    def __init__(self, message_folder_paths, initial_folder_path, base_path, parent=None):
        super().__init__(parent)
        self.message_folder_paths = message_folder_paths; self.current_index = -1
        self.base_path = base_path; self.current_file_path = None
        self.is_editing = False; self.original_content = ""
        try: # Robust index finding
            self.current_index = self.message_folder_paths.index(initial_folder_path)
        except (ValueError, TypeError): self.current_index = 0 if self.message_folder_paths else -1
        except Exception as e: print(f"Error finding initial index: {e}"); self.current_index = 0 if self.message_folder_paths else -1

        self._build_ui();
        if self.current_index != -1: self._load_current_message()
        else: self.setWindowTitle(f"{WINDOW_TITLE_PREFIX} - No Messages"); # Don't try to access self.content_edit yet
        self.resize(700, 800)
        # Load message content *after* build_ui finishes if index was invalid initially
        if self.current_index == -1:
             if hasattr(self, 'content_edit'): # Check if build_ui created it
                 self.content_edit.setPlainText("No messages available in the list.")
             else: # Should not happen if build_ui is correct
                 print("Error: content_edit not created in _build_ui")


    def _get_icon(self, standard_pixmap, fallback_name=None):
        icon = QIcon()
        try: icon = self.style().standardIcon(standard_pixmap)
        except Exception: pass
        if (icon.isNull() or fallback_name) and self.base_path:
             if fallback_name:
                 icon_path = os.path.join(self.base_path, 'assets', 'icons', fallback_name)
                 if os.path.exists(icon_path): icon = QIcon(icon_path)
        return icon

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setSpacing(5)
        toolbar = QToolBar("Main Toolbar"); toolbar.setIconSize(DEFAULT_ICON_SIZE)
        self.action_prev = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_ArrowBack), "Previous"); self.action_prev.triggered.connect(self._go_previous)
        self.action_next = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_ArrowForward), "Next"); self.action_next.triggered.connect(self._go_next)
        toolbar.addSeparator()
        self.action_desktop = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_ComputerIcon, "desktop.ico"), "Desktop View"); self.action_desktop.triggered.connect(self._set_desktop_view)
        self.action_mobile = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_DriveNetIcon, "mobile.ico"), "Mobile View"); self.action_mobile.triggered.connect(self._set_mobile_view)
        toolbar.addSeparator()
        self.action_view = QAction("👁️ View", self); self.action_view.setCheckable(True); self.action_view.setChecked(True); self.action_view.triggered.connect(self._set_view_mode)
        self.action_edit_basic = QAction("✏️ Edit Text", self); self.action_edit_basic.setCheckable(True); self.action_edit_basic.triggered.connect(self._set_edit_basic_mode)
        self.action_edit_advanced = QAction("🎨 Edit Rich Text", self); self.action_edit_advanced.setCheckable(True); self.action_edit_advanced.triggered.connect(self._set_edit_advanced_mode)
        edit_action_group = QActionGroup(self); edit_action_group.addAction(self.action_view); edit_action_group.addAction(self.action_edit_basic); edit_action_group.addAction(self.action_edit_advanced); edit_action_group.setExclusive(True)
        toolbar.addActions([self.action_view, self.action_edit_basic, self.action_edit_advanced])
        toolbar.addSeparator()
        self.action_save = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_DialogSaveButton),"Save"); self.action_save.triggered.connect(self._save_changes); self.action_save.setEnabled(False)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred); toolbar.addWidget(spacer)
        self.action_close = toolbar.addAction(self._get_icon(QStyle.StandardPixmap.SP_DialogCloseButton),"Close"); self.action_close.triggered.connect(self.reject)
        layout.addWidget(toolbar)

        # Create Content Area FIRST
        self.content_edit = QTextEdit();
        self.content_edit.setObjectName("messagePreviewContent");
        self.content_edit.setAcceptRichText(True)
        self.content_edit.currentCharFormatChanged.connect(self._update_format_actions);
        self.content_edit.cursorPositionChanged.connect(self._update_format_actions)
        self.content_edit.textChanged.connect(self._handle_text_change)

        # Rich Text Toolbar
        self.format_toolbar = QToolBar("Format Toolbar");
        self.format_toolbar.setIconSize(QSize(16,16));
        self.format_toolbar.setVisible(False)
        self.combo_font = QFontComboBox(self);
        self.combo_font.currentFontChanged.connect(self._set_font_family)
        self.format_toolbar.addWidget(self.combo_font)
        self.combo_size = QComboBox(self)

        # *** FIXED: Removed 'db =' and call standardSizes statically ***
        sizes = [str(s) for s in QFontDatabase.standardSizes()] # No instance needed

        self.combo_size.addItems(sizes)
        default_size_str = "12"
        if default_size_str in sizes: self.combo_size.setCurrentIndex(sizes.index(default_size_str))
        elif sizes: self.combo_size.setCurrentIndex(0) # Fallback if 12 not found
        self.combo_size.currentTextChanged.connect(self._set_font_size)
        self.format_toolbar.addWidget(self.combo_size); self.format_toolbar.addSeparator()

        self.action_bold = QAction(self._get_icon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton, "bold.ico"), "Bold", self); self.action_bold.setCheckable(True); self.action_bold.triggered.connect(lambda c: self.content_edit.setFontWeight(QFont.Weight.Bold if c else QFont.Weight.Normal))
        self.action_italic = QAction(self._get_icon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton, "italic.ico"), "Italic", self); self.action_italic.setCheckable(True); self.action_italic.triggered.connect(self.content_edit.setFontItalic)
        self.action_underline = QAction(self._get_icon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton, "underline.ico"), "Underline", self); self.action_underline.setCheckable(True); self.action_underline.triggered.connect(self.content_edit.setFontUnderline)
        self.format_toolbar.addActions([self.action_bold, self.action_italic, self.action_underline])
        layout.addWidget(self.format_toolbar)

        # Add Content Area to layout AFTER toolbars
        layout.addWidget(self.content_edit)

        self._set_view_mode(); # Start in view mode
        self._update_nav_buttons()

    # --- Other methods remain the same ---
    # ... (Implementations from previous correct version) ...
    def _set_font_family(self, font): self.content_edit.setCurrentFont(font)
    def _set_font_size(self, size):
        try: self.content_edit.setFontPointSize(float(size) if float(size)>0 else 0) # Basic check
        except ValueError: pass
    def _set_view_mode(self):
        if self.is_editing and self.check_unsaved_changes():
             if self.action_edit_basic.isChecked(): self.action_edit_basic.setChecked(False); self.action_view.setChecked(True)
             if self.action_edit_advanced.isChecked(): self.action_edit_advanced.setChecked(False); self.action_view.setChecked(True)
             return
        self.content_edit.setReadOnly(True); self.format_toolbar.setVisible(False)
        self.is_editing = False; self.action_save.setEnabled(False)
        if not self.action_view.isChecked(): self.action_view.setChecked(True)
    def _set_edit_basic_mode(self):
        if self.is_editing and self.check_unsaved_changes():
            self.action_edit_basic.setChecked(False); self.action_view.setChecked(True); self._set_view_mode(); return
        self.content_edit.setReadOnly(False); self.format_toolbar.setVisible(False)
        self.is_editing = True;
        if not self.action_edit_basic.isChecked(): self.action_edit_basic.setChecked(True)
        self._handle_text_change(); self.content_edit.setFocus()
    def _set_edit_advanced_mode(self):
        if self.is_editing and self.check_unsaved_changes():
            self.action_edit_advanced.setChecked(False); self.action_view.setChecked(True); self._set_view_mode(); return
        self.content_edit.setReadOnly(False); self.format_toolbar.setVisible(True)
        self.is_editing = True;
        if not self.action_edit_advanced.isChecked(): self.action_edit_advanced.setChecked(True)
        self._handle_text_change(); self.content_edit.setFocus(); self._update_format_actions()
    def _handle_text_change(self):
        if self.is_editing:
            current_content = "";
            try:
                if self.current_file_path and self.current_file_path.lower().endswith('.html'): current_content = self.content_edit.toHtml()
                else: current_content = self.content_edit.toPlainText()
            except RuntimeError: current_content = ""
            self.action_save.setEnabled(current_content != self.original_content)
    def _update_format_actions(self):
        if not self.is_editing or not self.format_toolbar.isVisible(): return
        cursor = self.content_edit.textCursor(); char_format = cursor.charFormat()
        font_family = char_format.font().family(); idx = self.combo_font.findText(font_family)
        self.combo_font.blockSignals(True); self.combo_font.setCurrentIndex(idx if idx != -1 else 0); self.combo_font.blockSignals(False)
        point_size = str(char_format.font().pointSize()); idx = self.combo_size.findText(point_size)
        self.combo_size.blockSignals(True); self.combo_size.setCurrentIndex(idx if idx != -1 else 4); self.combo_size.blockSignals(False)
        self.action_bold.setChecked(char_format.fontWeight() == QFont.Weight.Bold)
        self.action_italic.setChecked(char_format.fontItalic())
        self.action_underline.setChecked(char_format.fontUnderline())
    def get_current_folder_path(self):
        if 0 <= self.current_index < len(self.message_folder_paths): return self.message_folder_paths[self.current_index]
        return None
    def _load_current_message(self):
        folder_path = self.get_current_folder_path()
        self.current_file_path = find_message_file(folder_path) if folder_path else None
        self.action_save.setEnabled(False); self.original_content = ""
        window_title = f"{WINDOW_TITLE_PREFIX} - Error"
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            self.content_edit.setPlainText(f"Error: Message file (.txt/.html) not found in folder\n'{os.path.basename(folder_path) if folder_path else 'N/A'}'\nor no message selected.")
        else:
            # print(f"Preview Window: Loading {self.current_file_path}")
            self.content_edit.blockSignals(True)
            try:
                with open(self.current_file_path, 'r', encoding='utf-8') as f: content = f.read()
                if self.current_file_path.lower().endswith('.html'):
                    base_url = QUrl.fromLocalFile(folder_path + os.path.sep); self.content_edit.document().setMetaInformation(QTextDocument.MetaInformation.DocumentUrl, base_url.toString())
                    self.content_edit.setHtml(content); self.original_content = self.content_edit.toHtml()
                else: self.content_edit.document().setMetaInformation(QTextDocument.MetaInformation.DocumentUrl, ""); self.content_edit.setPlainText(content); self.original_content = self.content_edit.toPlainText()
                window_title = f"{WINDOW_TITLE_PREFIX} - {os.path.basename(folder_path)}"
            except Exception as e: error_msg = f"Error loading file:\n{self.current_file_path}\n\n{e}"; self.content_edit.setPlainText(error_msg); QMessageBox.warning(self, "Load Error", error_msg)
            finally: self.content_edit.blockSignals(False)
        self.setWindowTitle(window_title); self._update_nav_buttons(); self._set_view_mode()
    def _update_nav_buttons(self):
        self.action_prev.setEnabled(self.current_index > 0)
        self.action_next.setEnabled(self.current_index < len(self.message_folder_paths) - 1)
    def check_unsaved_changes(self):
        if self.is_editing and self.action_save.isEnabled():
            reply = QMessageBox.question(self, "Unsaved Changes", "Save current changes?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save: return not self._save_changes()
            elif reply == QMessageBox.StandardButton.Cancel: return True
        return False
    def _go_next(self):
        if self.check_unsaved_changes(): return
        if self.current_index < len(self.message_folder_paths) - 1: self.current_index += 1; self._load_current_message()
    def _go_previous(self):
        if self.check_unsaved_changes(): return
        if self.current_index > 0: self.current_index -= 1; self._load_current_message()
    def _save_changes(self):
        if not self.current_file_path: QMessageBox.warning(self, "Save Error", "No file loaded."); return False
        if not self.is_editing: QMessageBox.information(self, "Save", "Not in edit mode."); return False
        try:
            if self.current_file_path.lower().endswith('.html'): content_to_save = self.content_edit.toHtml()
            else: content_to_save = self.content_edit.toPlainText()
            if content_to_save != self.original_content:
                with open(self.current_file_path, 'w', encoding='utf-8') as f: f.write(content_to_save)
                print(f"Preview Window: Saved changes to {self.current_file_path}"); self.original_content = content_to_save; self.action_save.setEnabled(False); self.message_modified.emit(self.get_current_folder_path())
            else: print("Save skipped: Content unchanged."); self.action_save.setEnabled(False)
            return True
        except Exception as e: QMessageBox.critical(self, "Save Error", f"Could not save:\n{self.current_file_path}\n\n{e}"); return False
    def _set_desktop_view(self): self.resize(900, self.height())
    def _set_mobile_view(self): self.resize(450, self.height())
    def closeEvent(self, event):
        if self.check_unsaved_changes(): event.ignore()
        else: event.accept()