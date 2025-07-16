# ui/settings_panel.py
# FONTS FEATURE REMOVED
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QSizePolicy, QSpacerItem, QSpinBox
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

        # --- Leads Settings ---
        leads_group_layout = QHBoxLayout()
        chunk_label = QLabel("Leads Chunk Size:")
        chunk_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        leads_group_layout.addWidget(chunk_label)
        
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 10000)
        self.chunk_size_spin.setValue(500)  # Default value
        self.chunk_size_spin.setSuffix(" records")
        self.chunk_size_spin.setToolTip("Number of leads to display per page")
        self.chunk_size_spin.setMaximumWidth(150)
        self.chunk_size_spin.valueChanged.connect(self._on_chunk_size_changed)
        leads_group_layout.addWidget(self.chunk_size_spin)
        
        leads_group_layout.addStretch(1)
        main_layout.addLayout(leads_group_layout)

        # --- Auto-save Settings ---
        autosave_group_layout = QHBoxLayout()
        autosave_label = QLabel("Auto-save Delay:")
        autosave_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        autosave_group_layout.addWidget(autosave_label)
        
        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(1, 60)
        self.autosave_spin.setValue(5)  # Default 5 seconds
        self.autosave_spin.setSuffix(" seconds")
        self.autosave_spin.setToolTip("Delay before auto-saving changes")
        self.autosave_spin.setMaximumWidth(150)
        self.autosave_spin.valueChanged.connect(self._on_autosave_delay_changed)
        autosave_group_layout.addWidget(self.autosave_spin)
        
        autosave_group_layout.addStretch(1)
        main_layout.addLayout(autosave_group_layout)

        # Load saved values
        self._load_settings()

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
         # Handle both dict and ConfigManager objects
         if hasattr(self.config, 'set'):
             self.config.set('default_theme', f"{theme_name}.qss")
             if hasattr(self.config, 'remove'):
                 try:
                     self.config.remove('default_font')  # Remove old font key
                 except:
                     pass
         else:
             self.config['default_theme'] = f"{theme_name}.qss"
             if 'default_font' in self.config:
                 del self.config['default_font'] # Remove old font key
         
         try:
             os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
             # Handle ConfigManager vs dict save
             if hasattr(self.config, 'save'):
                 self.config.save()
             else:
                 with open(self.config_path, 'w', encoding='utf-8') as f:
                     json.dump(self.config, f, indent=4)
             print(f"Saved '{theme_name}' as default theme.")
         except Exception as e:
             QMessageBox.critical(self, "Config Error", f"Could not save default theme setting:\n{e}")

    def _set_initial_theme_selection(self):
         # Handle both dict and ConfigManager objects
         if hasattr(self.config, 'get'):
             default_theme_filename = self.config.get('default_theme', 'Default.qss')
         else:
             default_theme_filename = self.config.get('default_theme', 'Default.qss')
         
         self.current_theme_name = os.path.splitext(default_theme_filename)[0]
         current_index = self.theme_combo.findText(self.current_theme_name)
         if current_index >= 0: 
             self.theme_combo.blockSignals(True)
             self.theme_combo.setCurrentIndex(current_index)
             self.theme_combo.blockSignals(False)
         else:
              if self.theme_combo.count() > 0: 
                  print(f"W (SettingsPanel): Saved theme '{self.current_theme_name}' missing. Using '{self.theme_combo.itemText(0)}'.")
                  self.theme_combo.blockSignals(True)
                  self.theme_combo.setCurrentIndex(0)
                  self.theme_combo.blockSignals(False)
                  self.current_theme_name = self.theme_combo.itemText(0)
              else: 
                  print("W (SettingsPanel): No themes found.")
                  self.current_theme_name = None

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

    def _load_settings(self):
        """Load saved settings values."""
        # Load chunk size
        if hasattr(self.config, 'get'):
            chunk_size = self.config.get('leads.chunk_size', 500)
            autosave_delay = self.config.get('general.autosave_delay', 5)
        else:
            chunk_size = self.config.get('leads.chunk_size', 500)
            autosave_delay = self.config.get('general.autosave_delay', 5)
        
        self.chunk_size_spin.blockSignals(True)
        self.chunk_size_spin.setValue(chunk_size)
        self.chunk_size_spin.blockSignals(False)
        
        self.autosave_spin.blockSignals(True)
        self.autosave_spin.setValue(autosave_delay)
        self.autosave_spin.blockSignals(False)
    
    def _on_chunk_size_changed(self, value):
        """Handle chunk size change."""
        self._save_setting('leads.chunk_size', value)
    
    def _on_autosave_delay_changed(self, value):
        """Handle auto-save delay change."""
        self._save_setting('general.autosave_delay', value)
    
    def _save_setting(self, key, value):
        """Save a setting value."""
        try:
            if hasattr(self.config, 'set'):
                self.config.set(key, value)
                if hasattr(self.config, 'save'):
                    self.config.save()
            else:
                # Handle dict-style config
                keys = key.split('.')
                config_ref = self.config
                for k in keys[:-1]:
                    if k not in config_ref:
                        config_ref[k] = {}
                    config_ref = config_ref[k]
                config_ref[keys[-1]] = value
                
                # Save to file
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save setting {key}: {e}")

    # *** REMOVED All Font Handling Methods ***