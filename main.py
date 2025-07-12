# main.py
"""
Main application entry point for Bulk Email Sender.

This module initializes the application with the new foundation architecture:
- Configuration management
- Centralized logging 
- Error handling
- GUI initialization
"""

import sys
import os
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QPixmap, QFontDatabase, QFont
from PyQt6.QtCore import Qt

# Import new foundation components
from config.settings import get_config, update_config
from config.logging_config import setup_logging
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ApplicationError

# --- Constants ---
APP_NAME = "Bulk Email Sender"
DEFAULT_THEME_FILENAME = "Default.qss"
PREFERRED_DEFAULT_FONT = "Roboto"
FALLBACK_DEFAULT_FONT = "Segoe UI"

# Initialize logging first
logger = get_module_logger(__name__)

# --- Global variables ---
BASE_PATH = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_PATH, 'data')

# --- Helper Functions ---
def get_base_path():
    """Get base path for application files."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))

def setup_data_dirs(base):
    """Setup data directories with new foundation structure."""
    try:
        global DATA_DIR
        DATA_DIR = os.path.join(base, 'data')
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Create standard data directories
        for sub in ('leads', 'smtps', 'subjects', 'messages', 'attachments', 
                   'proxies', 'campaigns', 'logs', 'config'):
            os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
        
        # Create asset directories
        os.makedirs(os.path.join(base, 'assets', 'themes'), exist_ok=True)
        os.makedirs(os.path.join(base, 'assets', 'fonts'), exist_ok=True)
        
        logger.info("Data directories setup completed", path=DATA_DIR)
        
    except Exception as e:
        handle_exception(e, "Failed to setup data directories")
        raise ApplicationError(f"Cannot create required directories: {e}")

def load_fonts(base):
    """Load custom fonts from assets/fonts into the application database."""
    try:
        fonts_dir = os.path.join(base, 'assets', 'fonts')
        loaded_fonts = 0
        total_files = 0
        
        logger.info("Scanning for fonts", fonts_dir=fonts_dir)
        
        if os.path.isdir(fonts_dir):
            for f in os.listdir(fonts_dir):
                if f.lower().endswith(('.ttf', '.otf')):
                    total_files += 1
                    font_path = os.path.join(fonts_dir, f)
                    logger.debug("Attempting to load font file", file=f)
                    
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id != -1:
                        loaded_fonts += 1
                        families = QFontDatabase.applicationFontFamilies(font_id)
                        logger.info("Font loaded successfully", file=f, families=families)
                    else:
                        logger.warning("Failed to load font file", file=f)
        else:
            logger.warning("Font directory not found", path=fonts_dir)
        
        logger.info("Font loading completed", loaded=loaded_fonts, total=total_files)
        
    except Exception as e:
        handle_exception(e, "Error loading fonts")
        # Don't raise - fonts are optional

def load_and_apply_theme(app, base_path, config):
    """Load and apply theme using new configuration system."""
    try:
        themes_dir = os.path.join(base_path, 'assets', 'themes')
        theme_filename = config.get('gui.default_theme', DEFAULT_THEME_FILENAME)
        theme_path = os.path.join(themes_dir, theme_filename)
        
        if not os.path.exists(theme_path):
            logger.warning("Saved theme missing, falling back to default", 
                         theme=theme_filename)
            theme_filename = DEFAULT_THEME_FILENAME
            theme_path = os.path.join(themes_dir, theme_filename)
            update_config('gui.default_theme', theme_filename)
        
        if not os.path.exists(theme_path):
            logger.warning("Default theme missing, using no theme")
            app.setStyleSheet("")
            return ""
        
        with open(theme_path, 'r', encoding='utf-8') as f:
            qss = f.read()
        
        app.setStyleSheet(qss)
        logger.info("Theme applied successfully", theme=theme_filename)
        return qss
        
    except Exception as e:
        handle_exception(e, "Error loading theme")
        QMessageBox.warning(None, "Theme Error", 
                          f"Could not load theme '{theme_filename}': {e}")
        app.setStyleSheet("")
        return ""

# --- Exception Hook ---
def exception_hook(exc_type, exc_value, exc_tb):
    """Global exception handler for uncaught exceptions."""
    try:
        # Use new foundation error handling
        error_msg = handle_exception(
            Exception(f"{exc_type.__name__}: {exc_value}"),
            "Uncaught exception occurred",
            exc_tb=exc_tb
        )
        
        # Show user-friendly message
        app_instance = QApplication.instance()
        if app_instance:
            try:
                QMessageBox.critical(None, "Fatal Error", 
                                   f"An unexpected error occurred:\n\n{error_msg}\n\n"
                                   f"Please check the logs for details.")
            except Exception as msg_e:
                logger.error("Error showing critical message box", error=str(msg_e))
        else:
            logger.error("Fatal error with no app instance", error=error_msg)
        
        sys.exit(1)
        
    except Exception as hook_error:
        # Fallback if even our error handling fails
        print(f"CRITICAL: Exception hook failed: {hook_error}")
        print(f"Original error: {exc_type.__name__}: {exc_value}")
        sys.exit(1)

# --- Main Execution ---
def main():
    """Main application entry point."""
    try:
        # Set up global exception handling
        sys.excepthook = exception_hook
        
        # Initialize base path and setup
        global BASE_PATH
        BASE_PATH = get_base_path()
        
        # Setup logging first (before any other operations)
        setup_logging()
        logger.info("Application starting", app_name=APP_NAME, base_path=BASE_PATH)
        
        # Setup data directories
        setup_data_dirs(BASE_PATH)
        
        # Initialize PyQt6 application
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setOrganizationName("YourOrganizationName")
        
        logger.info("Qt Application initialized")
        
        # Load fonts
        logger.info("Loading fonts")
        load_fonts(BASE_PATH)
        
        # Set application font
        logger.info("Setting application font")
        font_set = False
        
        # Try preferred font
        if PREFERRED_DEFAULT_FONT in QFontDatabase.families():
            try:
                app.setFont(QFont(PREFERRED_DEFAULT_FONT))
                font_set = True
                logger.info("Font set successfully", font=PREFERRED_DEFAULT_FONT)
            except Exception as e:
                logger.warning("Failed to set preferred font", 
                             font=PREFERRED_DEFAULT_FONT, error=str(e))
        else:
            logger.warning("Preferred font not found", font=PREFERRED_DEFAULT_FONT)
        
        # Try fallback font
        if not font_set:
            try:
                if FALLBACK_DEFAULT_FONT in QFontDatabase.families():
                    app.setFont(QFont(FALLBACK_DEFAULT_FONT))
                    font_set = True
                    logger.info("Fallback font set successfully", font=FALLBACK_DEFAULT_FONT)
                else:
                    logger.warning("Fallback font not found", font=FALLBACK_DEFAULT_FONT)
            except Exception as e:
                logger.warning("Failed to set fallback font", 
                             font=FALLBACK_DEFAULT_FONT, error=str(e))
        
        if not font_set:
            logger.info("Using system default font")
        
        # Load configuration
        logger.info("Loading configuration")
        config = get_config()
        
        # Load and apply theme
        logger.info("Loading theme")
        load_and_apply_theme(app, BASE_PATH, config)
        
        # Create splash screen
        logger.info("Creating splash screen")
        splash_icon_path = os.path.join(BASE_PATH, 'assets', 'icons', 'logo.ico')
        pix = QPixmap(splash_icon_path) if os.path.exists(splash_icon_path) else QPixmap()
        
        if pix.isNull():
            try:
                standard_icon = app.style().standardIcon(
                    app.style().StandardPixmap.SP_DriveNetIcon)
                pix = standard_icon.pixmap(128, 128)
            except Exception as e:
                logger.warning("Failed to get standard icon", error=str(e))
                pix = QPixmap(128, 128)
                pix.fill(Qt.GlobalColor.lightGray)
        
        splash = QSplashScreen(pix)
        splash.show()
        
        # Minimum splash time
        start_time = datetime.now()
        min_splash_time = 1.0
        while (datetime.now() - start_time).total_seconds() < min_splash_time:
            app.processEvents()
        
        # Setup system tray
        logger.info("Setting up system tray")
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not supported")
            app.tray_icon = None
        else:
            try:
                tray_icon_path = os.path.join(BASE_PATH, 'assets', 'icons', 'logo.ico')
                if os.path.exists(tray_icon_path):
                    tray_icon = QIcon(tray_icon_path)
                else:
                    try:
                        tray_icon = app.style().standardIcon(
                            app.style().StandardPixmap.SP_ComputerIcon)
                    except Exception as e:
                        logger.warning("Failed to get standard tray icon", error=str(e))
                        tray_icon = QIcon()
                
                if tray_icon.isNull():
                    logger.warning("Invalid tray icon")
                
                tray = QSystemTrayIcon(tray_icon, parent=app)
                tray.setToolTip(APP_NAME)
                tray.show()
                app.tray_icon = tray
                logger.info("System tray created successfully")
                
            except Exception as e:
                logger.warning("Could not create system tray", error=str(e))
                app.tray_icon = None
        
        # Initialize main window
        logger.info("Initializing main window")
        try:
            from ui.main_window import MainWindow
            window = MainWindow(base_path=BASE_PATH, config=config)
            window.show()
            splash.finish(window)
            
            logger.info("Application started successfully")
            sys.exit(app.exec())
            
        except ImportError as import_err:
            logger.error("Failed to import MainWindow", error=str(import_err))
            QMessageBox.critical(None, "Import Error", 
                               f"Failed to start UI:\n{import_err}")
            sys.exit(1)
            
        except Exception as main_err:
            # Re-raise for global exception handler
            raise
        
    except Exception as e:
        # This will be caught by sys.excepthook
        raise


if __name__ == "__main__":
    main()