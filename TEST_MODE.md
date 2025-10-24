# Test-Modus für schnelle Tests

Der Sitemapper unterstützt jetzt einen Test-Modus, der die Verarbeitung auf maximal 10 Dokumente pro Core begrenzt. Dies ermöglicht schnelle Tests ohne lange Wartezeiten.

## Aktivierung des Test-Modus

### 1. In der Konfigurationsdatei

Erstelle eine Test-Konfiguration (z.B. `sitemapper-test.toml`):

```toml
[processing]
parallel_workers = 2
log_level = "DEBUG"
test_mode = true  # Aktiviert den Test-Modus

[[cores]]
name = "test_core"
url = "http://your-solr-server/solr/core"
id_field = "id"
date_field = "last_indexed"
url_pattern = "https://example.com/id/{id}"
batch_size = 5  # Kleine Batch-Größe für Tests
timeout = 30
```

### 2. Programmatisch im Code

```python
from src.sitemapper.solr_client import SolrClient

# Test-Modus aktiviert
async with SolrClient("http://solr-url", test_mode=True) as client:
    total_docs = await client.get_total_docs("id")  # Maximal 10
    docs = await client.fetch_docs_batch("id", "date", 0, 20)  # Maximal 10
```

## Verhalten im Test-Modus

### Dokumentenzählung
- `get_total_docs()` gibt maximal 10 zurück, auch wenn mehr Dokumente vorhanden sind

### Batch-Verarbeitung
- `fetch_docs_batch()` respektiert das 10-Dokumente-Limit:
  - `start=0, rows=5` → maximal 5 Dokumente
  - `start=0, rows=15` → maximal 10 Dokumente (begrenzt)
  - `start=8, rows=5` → maximal 2 Dokumente (10-8)
  - `start=10, rows=5` → 0 Dokumente (über Limit)

## Empfohlene Test-Konfiguration

```toml
[sitemap]
output_dir = "./sitemaps-test"
max_urls_per_file = 50000
compress = true
base_url = "https://your-domain.com"

[processing]
parallel_workers = 1      # Einfacheres Debugging
log_level = "DEBUG"       # Detaillierte Logs
test_mode = true          # Test-Modus aktiviert

[[cores]]
name = "test_core"
url = "http://your-solr-server/solr/core"
id_field = "id"
date_field = "last_indexed"
url_pattern = "https://your-domain.com/id/{id}"
changefreq = "weekly"
batch_size = 5            # Kleine Batches
timeout = 30
```

## Verwendung

```bash
# Mit Test-Konfiguration
python -m sitemapper --config sitemapper-test.toml

# Oder mit normalem Modus
python -m sitemapper --config sitemapper.toml
```

## Vorteile des Test-Modus

- ⚡ **Schnelle Tests**: Nur 10 Dokumente pro Core
- 🐛 **Einfaches Debugging**: Weniger Daten zum Analysieren
- 💾 **Geringer Speicherverbrauch**: Minimale Ressourcennutzung
- 🔄 **Schnelle Iterationen**: Ideal für Entwicklung und Testing

## Überprüfung des Test-Modus

```python
client = SolrClient("http://solr-url", test_mode=True)
if client.is_test_mode():
    print("Test-Modus ist aktiviert - maximal 10 Dokumente pro Core")
else:
    print("Produktions-Modus - alle Dokumente werden verarbeitet")
```