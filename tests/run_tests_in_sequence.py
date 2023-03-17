import time

import pytest

for test in [
    # "tests/test_database.py",
    "tests/test_integration_fastapi.py",
    "tests/test_model_1_to_1.py",
    "tests/test_model_advanced.py",
    "tests/test_model_connections.py",
    "tests/test_model_counting.py",
    "tests/test_model_deletions.py",
    "tests/test_model_filtering_operators.py",
    "tests/test_model_insertions.py",
    "tests/test_model_limit_offset.py",
    "tests/test_model_many_to_many.py",
    "tests/test_models.py",
    "tests/test_model_updates.py",
    "tests/test_query_caching.py",
    "tests/test_querying.py",
    "tests/test_query_no_caching.py",
]:
    pytest.main([test])
    time.sleep(2)
