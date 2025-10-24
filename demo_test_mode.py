#!/usr/bin/env python3
"""
Demo script showing how to use test mode for quick testing.
"""

import asyncio
from pathlib import Path
from src.sitemapper.config import ConfigManager
from src.sitemapper.solr_client import SolrClient


async def demo_test_mode():
    """Demonstrate test mode functionality."""
    print("🧪 Demo: Test Mode für schnelle Tests\n")
    
    # Load test configuration
    config_manager = ConfigManager()
    
    try:
        # Try to load test config
        test_config_path = Path("sitemapper-test.toml")
        if test_config_path.exists():
            config = config_manager.load_config(test_config_path)
            print(f"✅ Test-Konfiguration geladen: {test_config_path}")
            print(f"   Test-Modus aktiviert: {config.test_mode}")
            print(f"   Parallel Workers: {config.parallel_workers}")
            print(f"   Log Level: {config.log_level}")
            print(f"   Anzahl Cores: {len(config.cores)}")
            
            # Demo with each core
            for i, core_config in enumerate(config.cores):
                print(f"\n📊 Core {i+1}: {core_config.name}")
                print(f"   URL: {core_config.url}")
                print(f"   Batch Size: {core_config.batch_size}")
                
                # Create client with test mode from config
                async with SolrClient(
                    base_url=core_config.url,
                    timeout=core_config.timeout,
                    test_mode=config.test_mode
                ) as client:
                    print(f"   Test-Modus: {client.is_test_mode()}")
                    
                    if client.is_test_mode():
                        print("   ⚡ Im Test-Modus: Maximal 10 Dokumente pro Core")
                    else:
                        print("   🚀 Im Produktions-Modus: Alle Dokumente")
        else:
            print(f"❌ Test-Konfiguration nicht gefunden: {test_config_path}")
            print("   Erstelle eine mit: cp sitemapper.toml sitemapper-test.toml")
            print("   Und füge 'test_mode = true' in der [processing] Sektion hinzu")
            
    except Exception as e:
        print(f"❌ Fehler beim Laden der Konfiguration: {e}")
    
    print("\n" + "="*60)
    print("💡 Verwendung des Test-Modus:")
    print("   1. Setze 'test_mode = true' in sitemapper-test.toml")
    print("   2. Reduziere 'batch_size' auf kleine Werte (z.B. 5)")
    print("   3. Setze 'parallel_workers' auf 1-2 für einfacheres Debugging")
    print("   4. Verwende 'log_level = \"DEBUG\"' für detaillierte Logs")
    print("   5. Jeder Core wird auf maximal 10 Dokumente begrenzt")
    print("="*60)


async def demo_client_comparison():
    """Compare normal vs test mode clients."""
    print("\n🔄 Vergleich: Normal-Modus vs Test-Modus\n")
    
    base_url = "http://example.com/solr/core"
    
    # Normal client
    normal_client = SolrClient(base_url, test_mode=False)
    print(f"Normal Client:")
    print(f"  Test-Modus: {normal_client.is_test_mode()}")
    print(f"  Verhalten: Verarbeitet alle verfügbaren Dokumente")
    
    # Test client
    test_client = SolrClient(base_url, test_mode=True)
    print(f"\nTest Client:")
    print(f"  Test-Modus: {test_client.is_test_mode()}")
    print(f"  Verhalten: Begrenzt auf maximal 10 Dokumente")
    
    print(f"\n📈 Batch-Verhalten im Test-Modus:")
    print(f"  start=0, rows=5   -> Gibt maximal 5 Dokumente zurück")
    print(f"  start=0, rows=15  -> Gibt maximal 10 Dokumente zurück (begrenzt)")
    print(f"  start=8, rows=5   -> Gibt maximal 2 Dokumente zurück (10-8)")
    print(f"  start=10, rows=5  -> Gibt 0 Dokumente zurück (über Limit)")


if __name__ == "__main__":
    asyncio.run(demo_test_mode())
    asyncio.run(demo_client_comparison())