## Database Usage
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

### With Alembic
If Alembic migrations are used, there is not need to await `Database.create` as migrations are driven by alembic, so the following may be used anywhere in the code to create an instance.
```python
db = Database.create(
    'postgresql://codemation:abcd1234@localhost/database',
    tables=[Employee]
)
```