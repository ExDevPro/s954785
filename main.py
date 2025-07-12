# main.py
import sys, os, traceback, json
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen, QSystemTrayIcon
# Import QFontDatabase, QFont here
from PyQt6.QtGui     import QIcon, QPixmap, QFontDatabase, QFont
from PyQt6.QtCore    import Qt

# --- Constants ---
APP_NAME = "Bulk Email Sender"
DEFAULT_THEME_FILENAME = "Default.qss"
# *** Define preferred default fonts ***
PREFERRED_DEFAULT_FONT = "Roboto" # TRY THIS FIRST (Needs Roboto-Regular.ttf in assets/fonts)
FALLBACK_DEFAULT_FONT = "Segoe UI" # Fallback if preferred not found/loaded

# --- Global variables ---
BASE_PATH = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_PATH, 'data')

# --- Helper Functions ---
def get_base_path():
    if getattr(sys, 'frozen', False): return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))

def setup_data_dirs(base):
    global DATA_DIR; DATA_DIR = os.path.join(base, 'data'); os.makedirs(DATA_DIR, exist_ok=True)
    for sub in ('leads','smtps','subjects','messages', 'attachments','proxies','campaigns','logs', 'config'):
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
    os.makedirs(os.path.join(base, 'assets', 'themes'), exist_ok=True)
    os.makedirs(os.path.join(base, 'assets', 'fonts'), exist_ok=True) # Still ensure fonts dir exists

def load_fonts(base):
    """ Loads custom fonts from assets/fonts into the application database. """
    fonts_dir = os.path.join(base, 'assets', 'fonts'); loaded_fonts = 0; total_files = 0
    print(f"--- Scanning for fonts in: {fonts_dir} ---")
    if os.path.isdir(fonts_dir):
        for f in os.listdir(fonts_dir):
            if f.lower().endswith(('.ttf','.otf')):
                total_files += 1; font_path = os.path.join(fonts_dir, f); print(f"Attempting to load font file: {f}")
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1: loaded_fonts += 1; families = QFontDatabase.applicationFontFamilies(font_id); print(f"  ✅ SUCCESS: Loaded '{f}'. Found Families: {families}")
                else: print(f"  ❌ FAILED: Could not load font file '{f}'. Check if valid.")
    else: print(f"Font directory not found: {fonts_dir}")
    print(f"--- Font Scan Complete: {loaded_fonts} loaded ---")

def get_config_path(base):
    return os.path.join(DATA_DIR, 'config', 'settings.json')

def load_config(config_path):
    """ Loads config, removes old 'default_font' key if present. """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if 'default_font' in data:
                print("Removing obsolete 'default_font' from config.")
                del data['default_font']
                save_config(config_path, data) # Save cleaned config
            return data
        except json.JSONDecodeError: print(f"W: Error reading config {config_path}. Using defaults."); return {}
    return {}

def save_config(config_path, config_data):
    """ Saves config, ensures 'default_font' key is removed. """
    try:
        config_data.pop('default_font', None); os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
    except Exception as e: print(f"E: Saving config {config_path}: {e}")

def load_and_apply_theme(app, base_path, config):
    themes_dir = os.path.join(base_path, 'assets', 'themes'); config_path = get_config_path(base_path)
    theme_filename = config.get('default_theme', DEFAULT_THEME_FILENAME); theme_path = os.path.join(themes_dir, theme_filename)
    if not os.path.exists(theme_path):
        print(f"W: Saved theme '{theme_filename}' missing. Falling back.")
        theme_filename = DEFAULT_THEME_FILENAME; theme_path = os.path.join(themes_dir, theme_filename)
        config['default_theme'] = theme_filename; save_config(config_path, config)
    if not os.path.exists(theme_path): print(f"W: Default theme missing. No theme."); app.setStyleSheet(""); return ""
    try:
        with open(theme_path, 'r', encoding='utf-8') as f: qss = f.read()
        app.setStyleSheet(qss); print(f"Applied theme: {theme_filename}"); return qss
    except Exception as e: print(f"E: Loading theme {theme_path}: {e}"); QMessageBox.warning(None, "Theme Error", f"Could not load theme '{theme_filename}': {e}"); app.setStyleSheet(""); return ""

# --- Exception Hook ---
def exception_hook(exc_type, exc_value, exc_tb):
    log_dir = os.path.join(DATA_DIR, 'logs');
    try: os.makedirs(log_dir, exist_ok=True)
    except Exception as dir_e: print(f"FATAL: No log dir {log_dir}: {dir_e}"); timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); error_message = f"Error AND failed log dir:\n\n{exc_type.__name__}: {exc_value}"; print(f"CRITICAL ERROR ({timestamp}): {error_message}"); traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr); sys.exit(1)
    fn = os.path.join(log_dir, 'error.log'); timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); error_message = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}\n\nSee log file for details:\n{fn}"; print(f"CRITICAL ERROR ({timestamp}): {error_message}")
    try:
        with open(fn, 'a', encoding='utf-8') as f: f.write(f"\n----- Uncaught Exception ({timestamp}) -----\n"); traceback.print_exception(exc_type, exc_value, exc_tb, file=f); f.write("-----\n")
    except Exception as log_e: print(f"FATAL: No write log {fn}: {log_e}"); error_message += f"\n\nNo write log: {log_e}"
    app_instance = QApplication.instance()
    if app_instance:
        try: # Correctly indented try/except for message box
            QMessageBox.critical(None, "Fatal Error", error_message)
        except Exception as msg_e:
            print(f"Error showing critical message box: {msg_e}")
    else: print(f"Fatal Error (No App): {error_message}")
    sys.exit(1)

# --- Main Execution ---
def main():
    sys.excepthook = exception_hook
    global BASE_PATH; BASE_PATH = get_base_path(); setup_data_dirs(BASE_PATH)

    app = QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setOrganizationName("YourOrganizationName")

    print("\n--- Loading Fonts ---")
    load_fonts(BASE_PATH)
    print("---------------------\n")

    # *** MODIFIED: Set Default Application Font (No Config Check) ***
    print(f"--- Setting Application Font ---")
    font_set = False
    # 1. Try setting the preferred default (e.g., "Roboto")
    if PREFERRED_DEFAULT_FONT in QFontDatabase.families():
        try: print(f"Attempting to set font: '{PREFERRED_DEFAULT_FONT}'"); app.setFont(QFont(PREFERRED_DEFAULT_FONT)); font_set = True; print(f"  ✅ Set font to '{PREFERRED_DEFAULT_FONT}'")
        except Exception as e: print(f"  E: Failed setting '{PREFERRED_DEFAULT_FONT}': {e}")
    else: print(f"W: Font '{PREFERRED_DEFAULT_FONT}' not found.")
    # 2. Try fallback if preferred failed
    if not font_set:
        print(f"Attempting fallback: '{FALLBACK_DEFAULT_FONT}'")
        try:
            if FALLBACK_DEFAULT_FONT in QFontDatabase.families(): app.setFont(QFont(FALLBACK_DEFAULT_FONT)); font_set = True; print(f"  ✅ Set font to fallback '{FALLBACK_DEFAULT_FONT}'")
            else: print(f"  W: Fallback '{FALLBACK_DEFAULT_FONT}' also not found.")
        except Exception as e: print(f"  E: Failed fallback '{FALLBACK_DEFAULT_FONT}': {e}")
    if not font_set: print("W: Using system default font.")
    print("--------------------------\n")

    # Load config (mainly for theme now)
    config_path = get_config_path(BASE_PATH)
    config = load_config(config_path) # Load config (cleaned of font pref)

    # Load theme AFTER setting font
    print("--- Loading Theme ---")
    load_and_apply_theme(app, BASE_PATH, config)
    print("---------------------\n")

    # Splash Screen (Corrected try/except)
    splash_icon_path = os.path.join(BASE_PATH, 'assets', 'icons', 'logo.ico'); pix = QPixmap(splash_icon_path) if os.path.exists(splash_icon_path) else QPixmap()
    if pix.isNull():
        try: standard_icon = app.style().standardIcon(app.style().StandardPixmap.SP_DriveNetIcon); pix = standard_icon.pixmap(128, 128)
        except Exception as style_e: print(f"W: Std icon: {style_e}"); pix = QPixmap(128, 128); pix.fill(Qt.GlobalColor.lightGray)
    splash = QSplashScreen(pix); splash.show(); start_time = datetime.now(); min_splash_time = 1.0
    while (datetime.now() - start_time).total_seconds() < min_splash_time: app.processEvents()

    # System Tray Icon (Corrected try/except)
    if not QSystemTrayIcon.isSystemTrayAvailable(): print("W: Sys tray not supported."); app.tray_icon = None
    else:
         tray_icon_path = os.path.join(BASE_PATH, 'assets', 'icons', 'logo.ico')
         if os.path.exists(tray_icon_path): tray_icon = QIcon(tray_icon_path)
         else:
              try: tray_icon = app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon)
              except Exception as style_e: print(f"W: Std tray icon: {style_e}"); tray_icon = QIcon()
         if tray_icon.isNull(): print("W: Invalid tray icon.")
         try: tray = QSystemTrayIcon(tray_icon, parent=app); tray.setToolTip(APP_NAME); tray.show(); app.tray_icon = tray
         except Exception as tray_e: print(f"E: Could not create/show sys tray: {tray_e}"); app.tray_icon = None

    # Main Window
    try:
         print("Importing MainWindow...")
         from ui.main_window import MainWindow
         print("Initializing MainWindow...")
         window = MainWindow(base_path=BASE_PATH, config=config);
         print("Showing MainWindow...")
         window.show();
         splash.finish(window)
         print(f"✅ {APP_NAME} started successfully."); sys.exit(app.exec())
    # Corrected except block
    except ImportError as import_err:
        print(f"FATAL ERROR: Import MainWindow: {import_err}")
        QMessageBox.critical(None, "Import Error", f"Failed to start UI:\n{import_err}")
        sys.exit(1)
    except Exception as main_err:
         raise # Re-raise other exceptions for the hook

if __name__ == "__main__":
    main()