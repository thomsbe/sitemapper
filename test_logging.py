#!/usr/bin/env python3
"""Test script for the logging system."""

import sys
sys.path.insert(0, 'src')

from sitemapper.logging import configure_logging, get_logger
from sitemapper.types import LogLevel

def test_logging():
    """Test the logging system functionality."""
    print("Testing logging system...")
    
    # Test basic logging configuration
    configure_logging(log_level=LogLevel.INFO, structured=True)
    
    # Test contextual logger
    logger = get_logger({'component': 'test'})
    logger.info('Test message', test_param='test_value')
    logger.warning('Test warning', error_code=404)
    
    # Test core logging methods
    logger.log_core_start('test_core', 'http://localhost:8983/solr/test', 1000)
    logger.log_core_progress('test_core', 500, 1000, 'processing')
    logger.log_core_completion('test_core', 1000, 2, 15.5, 0)
    
    print("✓ Logging system test completed successfully")

if __name__ == "__main__":
    test_logging()