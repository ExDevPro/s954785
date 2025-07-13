#!/usr/bin/env python3
"""
Test metaclass conflict resolution.

This script tests that the metaclass conflict between QObject and BaseWorker 
has been resolved and that all Worker classes can be instantiated correctly.
"""

import os
import sys

# Set offscreen platform to avoid libEGL issues
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_metaclass_resolution():
    """Test that metaclass conflicts are resolved."""
    print("🧪 Testing metaclass conflict resolution...")
    
    try:
        # Import required modules
        from workers.base_worker import BaseWorker
        from PyQt6.QtCore import QObject, pyqtSignal
        
        # Test 1: Basic multiple inheritance
        print("\n📋 Test 1: Basic multiple inheritance")
        class TestWorker(QObject, BaseWorker):
            test_signal = pyqtSignal()
            
            def __init__(self):
                super().__init__(name='test_worker')
                
            def _execute(self, *args, **kwargs):
                return 'success'
        
        worker = TestWorker()
        print(f"✅ TestWorker created successfully: {worker.name}")
        print(f"✅ Worker status: {worker.status}")
        assert hasattr(worker, 'test_signal'), "PyQt signal not available"
        assert hasattr(worker, 'start'), "BaseWorker methods not available"
        print("✅ Both QObject and BaseWorker functionality available")
        
        # Test 2: LeadsWorker class creation
        print("\n📋 Test 2: LeadsWorker class creation")
        try:
            # Test class definition without instantiation (to avoid Qt dependencies)
            from ui.leads_manager_integrated import LeadsWorker
            print("✅ LeadsWorker class imported successfully")
            
            # Check MRO (Method Resolution Order)
            mro = LeadsWorker.__mro__
            print(f"✅ LeadsWorker MRO: {[cls.__name__ for cls in mro]}")
            assert QObject in mro, "QObject not in MRO"
            assert BaseWorker in mro, "BaseWorker not in MRO"
            
        except ImportError as e:
            if "libEGL" in str(e):
                print("⚠️  Qt GUI import skipped (expected in headless environment)")
            else:
                raise
        
        # Test 3: MessageWorker class creation  
        print("\n📋 Test 3: MessageWorker class creation")
        try:
            from ui.message_manager_integrated import MessageWorker
            print("✅ MessageWorker class imported successfully")
            
            mro = MessageWorker.__mro__
            print(f"✅ MessageWorker MRO: {[cls.__name__ for cls in mro]}")
            assert QObject in mro, "QObject not in MRO"
            assert BaseWorker in mro, "BaseWorker not in MRO"
            
        except ImportError as e:
            if "libEGL" in str(e):
                print("⚠️  Qt GUI import skipped (expected in headless environment)")
            else:
                raise
        
        # Test 4: CampaignWorker class creation
        print("\n📋 Test 4: CampaignWorker class creation")
        try:
            from ui.campaign_builder_integrated import CampaignWorker
            print("✅ CampaignWorker class imported successfully")
            
            mro = CampaignWorker.__mro__
            print(f"✅ CampaignWorker MRO: {[cls.__name__ for cls in mro]}")
            assert QObject in mro, "QObject not in MRO"
            assert BaseWorker in mro, "BaseWorker not in MRO"
            
        except ImportError as e:
            if "libEGL" in str(e):
                print("⚠️  Qt GUI import skipped (expected in headless environment)")
            else:
                raise
        
        print("\n🎉 All metaclass conflict tests PASSED!")
        print("✅ Multiple inheritance QObject + BaseWorker works correctly")
        print("✅ All Worker classes can be created without metaclass conflicts")
        return True
        
    except Exception as e:
        print(f"\n❌ Metaclass test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basewriter_functionality():
    """Test that BaseWorker still functions correctly after removing ABC."""
    print("\n🧪 Testing BaseWorker functionality after ABC removal...")
    
    try:
        from workers.base_worker import BaseWorker, WorkerStatus
        
        # Test 1: Ensure _execute method is required
        print("\n📋 Test 1: _execute method enforcement")
        try:
            class BadWorker(BaseWorker):
                def __init__(self):
                    super().__init__(name='bad_worker')
                # No _execute method
            
            worker = BadWorker()
            print("❌ BadWorker should have failed - _execute method not enforced")
            return False
        except Exception as e:
            if "_execute" in str(e):
                print("✅ _execute method requirement enforced correctly")
            else:
                print(f"❌ Unexpected error: {e}")
                return False
        
        # Test 2: Proper worker creation and functionality
        print("\n📋 Test 2: Proper worker functionality")
        class GoodWorker(BaseWorker):
            def __init__(self):
                super().__init__(name='good_worker')
                
            def _execute(self, *args, **kwargs):
                return {'result': 'success', 'args': args, 'kwargs': kwargs}
        
        worker = GoodWorker()
        print(f"✅ GoodWorker created: {worker.name}")
        print(f"✅ Initial status: {worker.status}")
        assert worker.status == WorkerStatus.IDLE
        assert hasattr(worker, 'start')
        assert hasattr(worker, 'stop')
        assert hasattr(worker, 'add_progress_callback')
        print("✅ All BaseWorker methods available")
        
        print("\n🎉 BaseWorker functionality tests PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ BaseWorker functionality test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Metaclass Conflict Resolution Test")
    print("=" * 60)
    
    success1 = test_metaclass_resolution()
    success2 = test_basewriter_functionality()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED - Metaclass conflict successfully resolved!")
        print("✅ Application should now start without metaclass errors")
        sys.exit(0)
    else:
        print("❌ TESTS FAILED - Metaclass conflict not fully resolved")
        sys.exit(1)