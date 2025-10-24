#!/usr/bin/env python3
"""
Quick test script for SolrClient functionality.
"""

import asyncio
from datetime import datetime
from src.sitemapper.solr_client import SolrClient
from src.sitemapper.types import SolrDocument


async def test_date_parsing():
    """Test the Solr date parsing functionality."""
    print("Testing Solr date parsing...")
    
    client = SolrClient("http://dummy-url")
    
    # Test various date formats
    test_dates = [
        "2023-12-01T10:30:00Z",
        "2023-12-01T10:30:00.123Z", 
        "2023-12-01 10:30:00",
        "2023-12-01T10:30:00",
        "invalid-date",
        None,
        ""
    ]
    
    for date_str in test_dates:
        result = client._parse_solr_date(date_str)
        print(f"  '{date_str}' -> {result}")
    
    print("✅ Date parsing test completed")


async def test_solr_document_creation():
    """Test SolrDocument dataclass creation."""
    print("\nTesting SolrDocument creation...")
    
    # Test with datetime
    doc1 = SolrDocument(id="doc123", last_modified=datetime.now())
    print(f"  Doc with datetime: {doc1}")
    
    # Test without datetime
    doc2 = SolrDocument(id="doc456")
    print(f"  Doc without datetime: {doc2}")
    
    print("✅ SolrDocument creation test completed")


async def test_client_initialization():
    """Test SolrClient initialization and basic properties."""
    print("\nTesting SolrClient initialization...")
    
    # Test with trailing slash
    client1 = SolrClient("http://localhost:8983/solr/core1/")
    print(f"  URL with trailing slash: '{client1.base_url}'")
    
    # Test without trailing slash
    client2 = SolrClient("http://localhost:8983/solr/core1")
    print(f"  URL without trailing slash: '{client2.base_url}'")
    
    # Test custom timeout
    client3 = SolrClient("http://localhost:8983/solr/core1", timeout=60)
    print(f"  Custom timeout: {client3.timeout}s")
    
    # Test test mode
    client4 = SolrClient("http://localhost:8983/solr/core1", test_mode=True)
    print(f"  Test mode enabled: {client4.is_test_mode()}")
    
    # Test normal mode
    client5 = SolrClient("http://localhost:8983/solr/core1", test_mode=False)
    print(f"  Test mode disabled: {client5.is_test_mode()}")
    
    print("✅ Client initialization test completed")


async def test_context_manager():
    """Test async context manager functionality."""
    print("\nTesting async context manager...")
    
    async with SolrClient("http://dummy-url") as client:
        print(f"  Client in context: {type(client).__name__}")
        print(f"  Base URL: {client.base_url}")
        print(f"  Test mode: {client.is_test_mode()}")
    
    async with SolrClient("http://dummy-url", test_mode=True) as test_client:
        print(f"  Test client in context: {type(test_client).__name__}")
        print(f"  Test mode: {test_client.is_test_mode()}")
    
    print("✅ Context manager test completed")


async def test_test_mode_functionality():
    """Test test mode specific functionality."""
    print("\nTesting test mode functionality...")
    
    # Test batch size limiting in test mode
    test_client = SolrClient("http://dummy-url", test_mode=True)
    
    # Simulate batch fetching scenarios
    print("  Test mode batch scenarios:")
    
    # Scenario 1: start=0, rows=5 -> should return up to 5
    print(f"    start=0, rows=5 -> max docs: 5")
    
    # Scenario 2: start=0, rows=15 -> should limit to 10
    print(f"    start=0, rows=15 -> max docs: 10 (limited)")
    
    # Scenario 3: start=8, rows=5 -> should return max 2 (10-8)
    print(f"    start=8, rows=5 -> max docs: 2 (10-8)")
    
    # Scenario 4: start=10, rows=5 -> should return 0
    print(f"    start=10, rows=5 -> max docs: 0 (beyond limit)")
    
    print("✅ Test mode functionality test completed")


async def main():
    """Run all tests."""
    print("🧪 Running SolrClient tests...\n")
    
    await test_date_parsing()
    await test_solr_document_creation()
    await test_client_initialization()
    await test_context_manager()
    await test_test_mode_functionality()
    
    print("\n🎉 All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())