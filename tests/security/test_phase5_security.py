#!/usr/bin/env python3
"""
Security audit tests for Phase 5 centralization.
"""
import os
import stat
import tempfile
from pathlib import Path
import pytest
import sys

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from astro_data.db import init_db


class TestSecurity:
    def test_db_file_created_0600(self):
        """Verify SQLite DB files are created with mode 0600."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = init_db(str(db_path))
            
            # Verify file exists
            assert db_path.exists(), "DB file should be created"
            
            # Verify mode is 0600 (user read/write only)
            mode = db_path.stat().st_mode & 0o777
            assert mode == 0o600, f"DB file mode should be 0600, got {oct(mode)}"
            
            conn.close()

    def test_db_in_memory_has_no_permissions(self):
        """In-memory DBs should not have file permissions (no path)."""
        conn = init_db(None)  # :memory:
        # This should just work without errors
        conn.execute("SELECT 1")
        conn.close()
