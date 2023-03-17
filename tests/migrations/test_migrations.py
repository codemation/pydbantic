import pytest

for i in range(0, 9):
    pytest.main([f"tests/migrations/test_model_migration_{i}.py"])
