![](docs/images/logo.png)

'db' within pydantic - A single model for shaping, creating, accessing, storing data within a Database

[![Documentation Status](https://readthedocs.org/projects/pydbantic/badge/?version=latest)](https://pydbantic.readthedocs.io/en/latest/?badge=latest) [![PyPI version](https://badge.fury.io/py/pydbantic.svg)](https://badge.fury.io/py/pydbantic)[![Unit & Integration Tests](https://github.com/codemation/pydbantic/actions/workflows/package.yaml/badge.svg)](https://github.com/codemation/pydbantic/actions/workflows/package.yaml)

## Key Features
- Integrated Redis Caching Support
- Automatic Migration on Schema Changes
- Flexible Data Types
- One Model for type validation & database access

## Documentation
[https://pydbantic.readthedocs.io/en/latest/](https://pydbantic.readthedocs.io/en/latest/)

## Setup
```bash
$ pip install pydbantic
$ pip install pydbantic[sqlite]
$ pip install pydbantic[mysql]
$ pip install pydbantic[postgres]
```

## Basic Usage - Model

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from pydbantic import DataBaseModel, PrimaryKey

class Department(DataBaseModel):
    id: str = PrimaryKey()
    name: str
    company: str
    is_sensitive: bool = False

class Positions(DataBaseModel):
    id: str = PrimaryKey()
    name: str
    department: Department

class EmployeeInfo(DataBaseModel):
    ssn: str = PrimaryKey()
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]
    arrival_date: datetime = datetime = Default(default=datetime.now)

class Employee(DataBaseModel):
    id: str = PrimaryKey()
    employee_info: EmployeeInfo
    position: Positions
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```

## Basic Usage - Connecting a Database to Models

```python
import asyncio
from pydbantic import Database
from models import Employee

async def main():
    db = await Database.create(
        'sqlite:///test.db',
        tables=[Employee]
    )

if __name__ == '__main__':
    asyncio.run(main())
```

## Model Usage

```python
from models import (
    Employee, 
    EmployeeInfo, 
    Position, 
    Department
)

async def main():
    # db creation is above

    # create department 
    hr_department = Department(
        id='d1234',
        name='hr'
        company='abc-company',
        is_sensitive=True,
    )

    # create a Position in Hr Department
    hr_manager = Position(
        id='p1234',
        name='manager',
        department=hr_department
    )
    
    # create information on an hr employee
    hr_emp_info = EmployeeInfo(
        ssn='123-456-789',
        first_name='john',
        last_name='doe',
        address='123 lane',
        city='snake city',
        zip=12345
    )

    # create an hr employee 
    hr_employee = Employee(
        id='e1234',
        employee_info=hr_emp_info,
        position=hr_manager,
        is_employed=True,
        date_employed='1970-01-01'
    )

```
Note: At this point only the models have been created, but nothing is saved in the database yet.

```python
    # save to database
    await hr_employee.save()
```

### Filtering
```python
    # get all hr managers currently employed
    managers = await Employee.filter(
        position=hr_manager,
        is_employed=True
    )

```

### Deleting
```python
    # remove all managers not employed anymore
    for manager in await Employee.filter(
        position=hr_manager,
        is_employed=False
    ):
        await manager.delete()
```
### Updating
```python
    # raise salary of all managers
    for manager in await Employee.filter(
        position=hr_manager,
        is_employed=False
    ):
        manager.salary = manager.salary + 1000.0
        await manager.update() # or manager.save()
```

Save results in a new row created in `Employee` table as well as the related `EmployeeInfo`, `Position`, `Department` tables if non-existing.  

## What is pydbantic
`pydbantic` was built to solve some of the most common pain developers may face working with databases. 
- migrations 
- model creation / managment
- caching

`pydbantic` believes that related data should be stored together, in the shape the developer plans to use

`pydbantic` knows data is rarely flat or follows a set schema

`pydbantic` understand migrations are not fun, and does them for you

`pydbantic` speaks many `types` 


## Pillars
- [pydantic](https://pydantic-docs.helpmanual.io/) - Models, Type validation
- [databases](https://www.encode.io/databases/) - Database Connection Abstractions
- [sqlalchemy](https://www.sqlalchemy.org/) - Core Database Query and Database Model 

## Models
`pydbantic` most basic object is a `DataBaseModel`. This object may be comprised of almost any `pickle-able` python object, though you are encouraged to stay within the type-validation land by using `pydantic`'s `BaseModels` and validators.

### Primary Keys
`DataBaseModel` 's also have a priamry key, which is the first item defined in a model or marked with `= PrimaryKey()`

```python
class NotesBm(DataBaseModel):
    id: str = PrimaryKey()
    text: Optional[str]  # optional
    data: DataModel      # required 
    coridinates: tuple   # required
    items: list          # required
    nested: dict = {'nested': True} # Optional - w/ Default
```
### Model Types & Typing
`DataBaseModel` items are capable of being multiple layers deep following `pydantic` model validation
- Primary Key - First Item, must be unique
- Required - items without default values are assumed required
- Optional - marked explicitly with `typing.Optional` or with a default value
- Union - Accepts Either specified input type Union[str|int]
- List[item] - Lists of specified items

Input datatypes without a natural / built in serialization path are serialized using `pickle` and stored as bytes. More on this later. 

## Migrations
`pydbantic` handles migrations automatically in response to detected model changes: `New Field`, `Removed Field`, `Modified Field`, `Renamed Field`, `Primary Key Changes`

### Renaming an exiting column
Speical consideration is needed when renaming a field in a `DataBaseModel`, extra metadata `__renamed__` is needed to ensure existing data is migrated:

```python
# field `first_name` is renamed to `first_names`

class EmployeeInfo(DataBaseModel):
    __renamed__= [{'old_name': 'first_name', 'new_name': 'first_names'}]
    ssn: str = PrimaryKey()
    first_names: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]
```


## Cache
Adding cache with Redis is easy with `pydbantic`, and is complete with built in `cache invalidation`. 

```python
    db = await Database.create(
        'sqlite:///test.db',
        tables=[Employee],
        cache_enabled=True,
        redis_url="redis://localhost"
    )
```

## Models with arrays of Foreign Objects

`DataBaseModel` models can support arrays of both `BaseModels` and other `DataBaseModel`. Just like single `DataBaseModel` references, data is stored in separate tables, and populated automatically when the child `DataBaseModel` is instantiated.

```python
from uuid import uuid4
from datetime import datetime
from typing import List, Optional
from pydbantic import DataBaseModel, PrimaryKey


def time_now():
    return datetime.now().isoformat()
def get_uuid4():
    return str(uuid4())

class Coordinate(DataBaseModel):
    time: str = PrimaryKey(default=time_now)
    latitude: float
    longitude: float

class Journey(DataBaseModel):
    trip_id: str = PrimaryKey(default=get_uuid4)
    waypoints: List[Optional[Coordinate]]




```
