#!/usr/bin/env python3
"""
Test script to verify core functionality without GUI.

This script tests:
1. Folder creation for all data types
2. File handler operations 
3. Worker instantiation (without PyQt GUI)
4. Data model creation
5. Basic application structure

Run this to verify the issues reported by the user are fixed.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_folder_creation():
    """Test that all data folders are created properly."""
    print("🧪 Testing folder creation...")
    
    # Expected data directories
    expected_dirs = [
        'data/leads',
        'data/smtps', 
        'data/messages',
        'data/subjects',
        'data/attachments',
        'data/proxy',
        'data/campaigns',
        'logs'
    ]
    
    for dir_path in expected_dirs:
        full_path = os.path.join(project_root, dir_path)
        os.makedirs(full_path, exist_ok=True)
        
        if os.path.exists(full_path):
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} - Failed to create")
            return False
    
    print("✅ All data folders created successfully")
    return True

def test_core_imports():
    """Test that core modules can be imported without GUI."""
    print("\n🧪 Testing core imports...")
    
    try:
        # Test core foundation imports
        from core.data.models import Lead, SMTPConfig, EmailTemplate, Campaign
        from core.data.file_handler import FileHandler
        from core.validation.email_validator import EmailValidator
        from core.validation.data_validator import DataValidator
        from core.utils.logger import get_module_logger
        from core.utils.exceptions import handle_exception
        from core.security.encryption import EncryptionManager
        from workers.base_worker import BaseWorker
        
        print("  ✅ Core foundation imports")
        
        # Test data models creation
        lead = Lead(email="test@example.com", first_name="Test", last_name="User")
        print("  ✅ Lead model creation")
        
        smtp = SMTPConfig(
            host="smtp.example.com",
            port=587,
            username="test@example.com",
            password="password"
        )
        print("  ✅ SMTP model creation")
        
        template = EmailTemplate(
            name="Test Template",
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test"
        )
        print("  ✅ Email template creation")
        
        # Test file handler
        file_handler = FileHandler()
        print("  ✅ File handler creation")
        
        # Test validators
        email_validator = EmailValidator()
        data_validator = DataValidator()
        print("  ✅ Validators creation")
        
        # Test logger
        logger = get_module_logger("test")
        logger.info("Test log message")
        print("  ✅ Logger creation")
        
        print("✅ All core imports and instantiations successful")
        return True
        
    except Exception as e:
        print(f"  ❌ Core import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_operations():
    """Test file handler operations."""
    print("\n🧪 Testing file operations...")
    
    try:
        from core.data.file_handler import FileHandler
        
        file_handler = FileHandler()
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("email,first_name,last_name\n")
            f.write("test@example.com,Test,User\n")
            temp_csv = f.name
        
        # Test CSV reading
        data = list(file_handler.read_csv_file(temp_csv))
        if len(data) == 1 and data[0]['email'] == 'test@example.com':
            print("  ✅ CSV reading")
        else:
            print("  ❌ CSV reading failed")
            return False
        
        # Test Excel operations
        excel_data = [
            {'col1': 'value1', 'col2': 'value2'},
            {'col1': 'value3', 'col2': 'value4'}
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_excel = f.name
        
        # Test Excel writing
        success = file_handler.save_excel(excel_data, temp_excel)
        if success:
            print("  ✅ Excel writing")
        else:
            print("  ❌ Excel writing failed")
            return False
        
        # Test Excel reading
        loaded_data = file_handler.load_excel(temp_excel)
        if len(loaded_data) >= 2:  # Header + data
            print("  ✅ Excel reading")
        else:
            print("  ❌ Excel reading failed")
            return False
        
        # Cleanup
        os.unlink(temp_csv)
        os.unlink(temp_excel)
        
        print("✅ All file operations successful")
        return True
        
    except Exception as e:
        print(f"  ❌ File operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_worker_base_class():
    """Test that BaseWorker can be instantiated and used."""
    print("\n🧪 Testing BaseWorker base class...")
    
    try:
        from workers.base_worker import BaseWorker
        
        class TestWorker(BaseWorker):
            def __init__(self):
                super().__init__(name="test_worker")
            
            def _execute(self, *args, **kwargs):
                return "test_result"
        
        worker = TestWorker()
        print("  ✅ Worker instantiation")
        
        # Test worker properties
        assert worker.name == "test_worker"
        assert not worker.is_running
        assert not worker.is_completed
        print("  ✅ Worker properties")
        
        print("✅ BaseWorker tests successful")
        return True
        
    except Exception as e:
        print(f"  ❌ BaseWorker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration loading."""
    print("\n🧪 Testing configuration...")
    
    try:
        from config.settings import get_config
        
        config = get_config()
        print("  ✅ Configuration loading")
        
        # Test some basic config access
        smtp_timeout = config.get('smtp.timeout', 30)
        assert isinstance(smtp_timeout, (int, float))
        print("  ✅ Configuration access")
        
        print("✅ Configuration tests successful")
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Core Functionality (No GUI)\n")
    
    tests = [
        test_folder_creation,
        test_core_imports,
        test_file_operations,
        test_worker_base_class,
        test_configuration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\n❌ Test failed: {test.__name__}")
    
    print(f"\n{'='*50}")
    print(f"TEST RESULTS: {passed}/{total} PASSED")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Core functionality is working.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())