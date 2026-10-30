"""29.10: живьём «client has been closed» — два потока одновременно создали два клиента Gemini.
Клиент должен создаваться ровно один раз, сколько бы потоков ни спросили его сразу."""
import sys
import threading
import time
from types import SimpleNamespace

import app.services.embedding_client as embedding_client


def test_gemini_client_is_created_once_for_parallel_threads(monkeypatch):
    created = []

    def fake_client(api_key):
        time.sleep(0.05)                      # создание «медленное» — как раз окно для гонки
        created.append(api_key)
        return SimpleNamespace(api_key=api_key)

    fake_genai = SimpleNamespace(Client=fake_client)
    import google
    monkeypatch.setattr(google, "genai", fake_genai, raising=False)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(embedding_client, "_client", None)

    clients = []
    threads = [threading.Thread(target=lambda: clients.append(embedding_client._get_client())) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 1
    assert len({id(client) for client in clients}) == 1