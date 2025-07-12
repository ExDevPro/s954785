# ui/settings_panel.py
# FONTS FEATURE REMOVED
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import QApplication

class SettingsPanel(QWidget):
    def __init__(self, base_path: str, config: dict, config_path: str, parent=None):
        super().__init__(parent)
        self.base_path = base_path
        self.config = config
        self.config_path = config_path
        self.themes_dir = os.path.join(self.base_path, 'assets', 'themes')
        self.current_theme_name = None

        self.setObjectName("settingsPanel")
        os.makedirs(self.themes_dir, exist_ok=True)

        self._build_ui()
        self._set_initial_theme_selection()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Theme Selection ---
        theme_group_layout = QHBoxLayout()
        theme_label = QLabel("Application Theme:")
        theme_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        theme_group_layout.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.setToolTip("Select application theme")
        self.theme_combo.setObjectName("themeSelector")
        self.theme_combo.setMaximumWidth(300)
        available_themes = self._get_theme_files()
        self.theme_combo.addItems(available_themes)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        theme_group_layout.addWidget(self.theme_combo)
        theme_group_layout.addStretch(1)
        main_layout.addLayout(theme_group_layout)

        # --- Font Selection Removed ---

        main_layout.addStretch(1)

    # --- Theme Methods ---
    def _get_theme_files(self):
        themes = []; themes_dir = os.path.join(self.base_path, 'assets', 'themes')
        if os.path.isdir(themes_dir):
            for fname in os.listdir(themes_dir):
                if fname.lower().endswith('.qss'): themes.append(os.path.splitext(fname)[0])
        return sorted(themes)

    def _apply_theme(self, theme_name: str):
        theme_filename = f"{theme_name}.qss"; theme_path = os.path.join(self.themes_dir, theme_filename)
        app_instance = QApplication.instance();
        if not app_instance: print("E: No QApplication instance"); return False
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r', encoding='utf-8') as f: qss = f.read()
                app_instance.setStyleSheet(qss); app_instance.style().unpolish(app_instance); app_instance.style().polish(app_instance)
                print(f"Applied theme: {theme_filename}"); return True
            except Exception as e: QMessageBox.warning(self, "Theme Error", f"Could not load theme '{theme_filename}':\n{e}"); return False
        else: QMessageBox.warning(self, "Theme Error", f"Theme file not found:\n{theme_path}"); return False

    def _save_default_theme_preference(self, theme_name: str):
         self.config['default_theme'] = f"{theme_name}.qss"
         self.config.pop('default_font', None) # Remove old font key
         try:
             os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
             with open(self.config_path, 'w', encoding='utf-8') as f:
                 json.dump(self.config, f, indent=4)
             print(f"Saved '{theme_name}' as default theme.")
         except Exception as e:
             QMessageBox.critical(self, "Config Error", f"Could not save default theme setting:\n{e}")

    def _set_initial_theme_selection(self):
         default_theme_filename = self.config.get('default_theme', 'Default.qss'); self.current_theme_name = os.path.splitext(default_theme_filename)[0]
         current_index = self.theme_combo.findText(self.current_theme_name)
         if current_index >= 0: self.theme_combo.blockSignals(True); self.theme_combo.setCurrentIndex(current_index); self.theme_combo.blockSignals(False)
         else:
              if self.theme_combo.count() > 0: print(f"W (SettingsPanel): Saved theme '{self.current_theme_name}' missing. Using '{self.theme_combo.itemText(0)}'."); self.theme_combo.blockSignals(True); self.theme_combo.setCurrentIndex(0); self.theme_combo.blockSignals(False); self.current_theme_name = self.theme_combo.itemText(0)
              else: print("W (SettingsPanel): No themes found."); self.current_theme_name = None

    def _on_theme_selected(self, index: int):
        if index < 0: return
        selected_theme_name = self.theme_combo.itemText(index)
        if not selected_theme_name or selected_theme_name == self.current_theme_name: return
        msgBox = QMessageBox(self); msgBox.setWindowTitle("Apply Theme"); msgBox.setText(f"Apply theme '{selected_theme_name}'?"); msgBox.setIcon(QMessageBox.Icon.Question); one_time_button = msgBox.addButton("One Time", QMessageBox.ButtonRole.AcceptRole); default_button = msgBox.addButton("Set as Default", QMessageBox.ButtonRole.AcceptRole); msgBox.addButton("Cancel", QMessageBox.ButtonRole.RejectRole); msgBox.exec()
        applied = False
        if msgBox.clickedButton() == one_time_button: applied = self._apply_theme(selected_theme_name)
        elif msgBox.clickedButton() == default_button:
            if self._apply_theme(selected_theme_name): self._save_default_theme_preference(selected_theme_name); applied = True
        if applied: self.current_theme_name = selected_theme_name
        else:
             if self.current_theme_name:
                 current_index = self.theme_combo.findText(self.current_theme_name)
                 if current_index >= 0: self.theme_combo.blockSignals(True); self.theme_combo.setCurrentIndex(current_index); self.theme_combo.blockSignals(False)

    # *** REMOVED All Font Handling Methods ***