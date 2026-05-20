#!/usr/bin/env python3
"""
APEX Runtime Server Entry Point
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from apex_runtime.runtime import Runtime
from apex_runtime.config import Config

def main():
    config = Config.load('configs/config.yaml')
    runtime = Runtime(config)
    runtime.run()

if __name__ == '__main__':
    main()
