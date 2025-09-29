"""
Basic functionality tests for the maintenance assistant sample
"""
import pytest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_core_imports():
    """Test that core sample modules can be imported"""
    try:
        import utils
        import knowledge_base
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")

def test_maintenance_app_imports():
    """Test that maintenance assistant app modules can be imported"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'maintenance-assistant-app'))
        import ride_simulator
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import maintenance app modules: {e}")

if __name__ == "__main__":
    pytest.main([__file__])