import pytest

for i in range(0, 9):
    result = pytest.main([f"tests/migrations/test_model_migration_{i}.py"])
    assert result == 0
