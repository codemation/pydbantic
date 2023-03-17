## Migrations Using Alembic
Although Pydbantic can handle migrations automatically, alembic may also be used if preferred. Configuration can be done in a few easy steps

### Install alembic
Generally no need to install alembic, as it is also a dependency of automatic migrations with `pydbantic`

### Define Models & DB instance
```python
#models.py
from pydbantic import DataBaseModel, PrimaryKey, Default

def time_now_str():
    return datetime.now().isoformat()

def stringify_uuid():
    return str(uuid.uuid4())

class Employee(DataBaseModel):
    id: str = PrimaryKey(default=stringify_uuid)
    salary: float
    is_employed: bool
    date_employed: str = Default(default=time_now_str)
```

### Connect with Database
```python
#db.py
from pydbantic import Database
from models import Employee

db = Database.create(
    'sqlite:///company.db',
    tables=[Employee],
    use_alembic=True
)
```
### Initialize alembic
```bash
alembic init migrations
```
Within the current directory, alembic will create a `migrations` folder that will store `versions` and its `env.py` that will need to updated. We will remove most of the boiler plate code and simply `import db` and use `db.alembic_migrate()`.


Update `migrations/env.py` file
```python
#migrations/env.py
from alembic import context
from db import db

def run_migrations_offline() -> None:
    db.alembic_migrate()

def run_migrations_online() -> None:
    db.alembic_migrate()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Creating the first migration file
Until now, we have just told alembic where to store our migrations, and where our db is configured. We still have not created any database tables to match our `Employee` model.
```bash
alembic revision -m "init_migration" --autogenerate
```

Alembic is capable of detecting schema changes and often can do most of the work to build your migrations. Notice the new file in `migrations/versions/` matching the `-m "init_migration"` commit message.


### Trigger Migration
The final step once we have created a migration file is to trigger the migration. The instructions defined in the latest `migrations/versions` will be followed.

```bash
alembic upgrade head
```

### Run Application
Now we are all set, we can Create new persistent instances of our model and trust they are safely stored.

```python
#app.py
import asyncio
from db import db
from models import Employee

async def main():
    await Employee.create(
        salary=10000,
        is_employed=True
    )
    all_employees = await Employee.all()
    print(all_employees)

asyncio.run(main())
```

### Adding a new Model

```python
# models.py
import uuid
from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel
from pydbantic import DataBaseModel, PrimaryKey, Default

def time_now_str():
    return datetime.now().isoformat()

def stringify_uuid():
    return str(uuid.uuid4())

class Positions(DataBaseModel):
    name: str = PrimaryKey()
    level: int = 4

class Employee(DataBaseModel):
    id: str = PrimaryKey(default=stringify_uuid)
    salary: float
    is_employed: bool
    date_employed: str = Default(default=time_now_str)
    position: Union[Positions, None] = Positions(name='Manager')
```

Connect to database

```python
#db.py
from pydbantic import Database
from models import Employee, Positions

db = Database.create(
    'sqlite:///company.db',
    tables=[Employee, Positions],
    use_alembic=True
)
```
Create new revision

```bash
alembic revision -m "added Positions" --autogenerate
```
Migrate!
```bash
alembic upgrade head
```
