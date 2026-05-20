#!/usr/bin/env python3
"""
APEX Runtime Test Runner
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main(['-v', 'src/tests/', 'src/apex_runtime/tests/']))
