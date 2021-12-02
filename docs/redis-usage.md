## Redis and Pydbantic
Redis can be enabled for use with Pydbantic by simply passing in a redis URL string into `Database.create()` such as `redis://localhost`

```python
database = await Database.create(
        sqlite:///company.db,  
        tables=[Employee],
        cache_enabled=True,
        redis_url='redis://localhost'
    )
```

### Considerations
When using redis or any caching, it is important to use the same cache target wherever the `DataBaseModel` and database is used. Cache invalidation depends on this to ensure data is consistently querried, updated, and deleted among all applications that might share the same `DataBaseModel`. 

