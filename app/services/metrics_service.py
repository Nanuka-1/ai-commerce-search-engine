from prometheus_client import Counter


chat_requests_total = Counter(
    "chat_requests_total",
    "Total chat requests",
)


ai_used_total = Counter(
    "ai_used_total",
    "Total requests where AI was used",
)


ai_fallback_total = Counter(
    "ai_fallback_total",
    "Total AI fallback events",
)


search_success_total = Counter(
    "search_success_total",
    "Total successful searches",
)


search_zero_results_total = Counter(
    "search_zero_results_total",
    "Total zero-result searches",
)

search_strategy_total = Counter(
    "search_strategy_total",
    "Search strategy usage",
    ["strategy"],
)

search_fallback_level_total = Counter(
    "search_fallback_level_total",
    "Search fallback level usage",
    ["fallback_level"],
)