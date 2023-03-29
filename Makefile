test:
	pytest tests/test_database.py -s -x;
	pytest tests/test_integration_fastapi.py -s -x;
	pytest tests/test_model_1_to_1.py -s -x;
	pytest tests/test_model_advanced.py -s -x;
	pytest tests/test_model_connections.py -s -x;
	pytest tests/test_model_counting.py -s -x;
	pytest tests/test_model_deletions.py -s -x;
	pytest tests/test_model_filtering_operators.py -s -x;
	pytest tests/test_model_insertions.py -s -x;
	pytest tests/test_model_limit_offset.py -s -x;
	pytest tests/test_model_many_to_many.py -s -x;
	pytest tests/test_models.py -s -x;
	pytest tests/test_model_updates.py -s -x;
	pytest tests/test_query_caching.py -s -x;
	pytest tests/test_querying.py -s -x;
	pytest tests/test_query_no_caching.py -s -x;
	pytest tests/test_multiple_databases -s -x;

test-migrations:
	python tests/migrations/test_migrations.py
