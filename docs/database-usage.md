## Database Ussage
The Sqlite, Mysql and Postgres trio are supported for use with pydbantic via URL connection strings. 


### SqLite
```python
db = await Database.create(
    'sqlite:///company.db',
    tables=[Employee]
)
```

### Mysql
```python
db = await Database.create(
    'mysql://codemation:abcd1234@127.0.0.1/company',
    tables=[Employee]
)
```

### Postgres
```python
db = await Database.create(
    'postgresql://codemation:abcd1234@localhost/database',
    tables=[Employee]
)
```