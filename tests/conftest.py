"""Pytest configuration and fixtures for tests."""
import pytest
from src.services.cleanup_service import CleanupService


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """
    Automatically clean up team rosters and draft files after each test.
    
    This fixture runs automatically (autouse=True) after each test to ensure
    test data doesn't persist between test runs.
    """
    # Setup: nothing needed before test
    yield
    
    # Teardown: clean up after test
    cleanup = CleanupService()
    cleanup.cleanup_everything(keep_latest_draft=False)


@pytest.fixture
def cleanup_service():
    """Provide a cleanup service instance for tests."""
    return CleanupService()


@pytest.fixture
def cleanup_manual():
    """
    Manual cleanup fixture for tests that need to control when cleanup happens.
    
    Usage:
        def test_something(cleanup_manual):
            # ... do test ...
            cleanup_manual.cleanup_everything()
    """
    return CleanupService()

