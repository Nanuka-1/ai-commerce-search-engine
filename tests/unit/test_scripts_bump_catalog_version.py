"""03.11: скрипты каталога после изменений ставят новый «номер дня», а НЕ стирают весь кэш.
cache_service.clear() в redis = flushdb → стёр бы разговоры клиентов (chat:*) и кэш ИИ."""
import inspect

import pytest

from ingestion import build_embeddings, collect_new_products, scrape_category


@pytest.mark.parametrize("module", [scrape_category, collect_new_products, build_embeddings])
def test_script_bumps_version_and_never_clears_whole_cache(module):
    source = inspect.getsource(module)
    assert "cache_service.bump_catalog_version()" in source
    assert "cache_service.clear()" not in source