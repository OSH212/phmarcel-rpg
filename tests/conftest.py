"""Pytest configuration and fixtures."""

import sys
import pytest
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before running tests."""
    # Ensure bucket directory exists
    bucket_dir = Path("bucket")
    bucket_dir.mkdir(exist_ok=True)
    
    # Ensure sample docs exist
    sample_docs = Path("sample_docs")
    assert sample_docs.exists(), "sample_docs directory not found"
    assert (sample_docs / "T4_sample.JPG").exists(), "T4_sample.JPG not found"
    assert (sample_docs / "drivers_license.jpg").exists(), "drivers_license.jpg not found"
    
    yield
    
    # Cleanup after tests (optional)
    # You might want to clean up test database and uploaded files here

