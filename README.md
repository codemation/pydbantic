![](docs/images/logo.png)

'db' within pydantic - A single model for shaping, creating, accessing, storing data within a Database

[![Documentation Status](https://readthedocs.org/projects/pydbantic/badge/?version=latest)](https://pydbantic.readthedocs.io/en/latest/?badge=latest) [![PyPI version](https://badge.fury.io/py/pydbantic.svg)](https://badge.fury.io/py/pydbantic)[![Unit & Integration Tests](https://github.com/codemation/pydbantic/actions/workflows/package.yaml/badge.svg)](https://github.com/codemation/pydbantic/actions/workflows/package.yaml)

## Key Features
- Automatic Migration on Schema Changes
- Flexible Data Types
- One Model for type validation & database access
- Dynamic Model Relationships
- Integrated Redis Caching Support

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
from typing import List, Optional, Union
from pydbantic import DataBaseModel, PrimaryKey

class Department(DataBaseModel):
    department_id: str = PrimaryKey()
    name: str
    company: str
    is_sensitive: bool = False
    positions: List[Optional['Positions']] = []  # One to Many

class Positions(DataBaseModel):
    position_id: str = PrimaryKey()
    name: str
    department: Department = None               # One to One mapping 
    employees: List[Optional['Employee']] = []  # One to Many

class EmployeeInfo(DataBaseModel):
    ssn: str = PrimaryKey()
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]
    new: Optional[str]
    employee: Optional[Union['Employee', dict]] = None # One to One 

class Employee(DataBaseModel):
    employee_id: str = PrimaryKey()
    employee_info: Optional[EmployeeInfo] = None  # One to One
    position: List[Optional[Positions]] = []      # One to Many 
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```

## Basic Usage - Connecting a Database to Models

```python
import asyncio
from pydbantic import Database
from models import Employee, EmployeeInfo, Positions, Department

async def main():
    db = await Database.create(
        'sqlite:///test.db',
        tables=[
            Employee,
            EmployeeInfo,
            Positions,
            Department
        ]
    )

if __name__ == '__main__':
    asyncio.run(main())
```

## Model Usage

Import and use the models where you need them. As long as DB as already been created,
the Models can accesss the & Use the connected DB 

```python
from models import (
    Employee, 
    EmployeeInfo, 
    Position, 
    Department
)

```

### Model - Creation

```python
    # create department 
    hr_department = await Department.create(
        id='d1234',
        name='hr'
        company='abc-company',
        is_sensitive=True,
    )
```
Via instance using insert or save

```python
    hr_department = Department.create(
        id='d1234',
        name='hr'
        company='abc-company',
        is_sensitive=True,
    )

    await hr_department.insert()
    await hr_department.save()
```

Insert with related models 

```python

    # create a Position in Hr Department
    hr_manager = Position.create(
        id='p1234',
        name='manager',
        department=hr_department
    )
    
    # create instance on an hr employee
    hr_emp_info = EmployeeInfo.create(
        ssn='123-456-789',
        first_name='john',
        last_name='doe',
        address='123 lane',
        city='snake city',
        zip=12345
    )

    # create an hr employee 
    hr_employee = await Employee.create(
        id='e1234',
        employee_info=hr_emp_info,
        position=hr_manager,
        is_employed=True,
        date_employed='1970-01-01'
    )
```

### Filtering
```python
    # get all hr managers currently employed
    managers = await Employee.filter(
        Employee.position==hr_manager, # conditional
        is_employed=True               # key-word argument
    )

    first_100_employees = await Employee.all(
        limit=100
    )

```
See also filtering [operators](https://pydbantic.readthedocs.io/en/latest/model-usage/#model-usage-query-filtering)


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

`.save()` results in a new row created in `Employee` table as well as the related `EmployeeInfo`, `Position`, `Department` tables if not yet created.  s

## What is pydbantic
`pydbantic` was built to solve some of the most common pain developers may face working with databases. 
- migrations 
- model creation / managment
- dynamic relationships
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
    id: str = PrimaryKey(default=get_uuid4)
    lat_long: tuple
    journeys: List[Optional["Journey"]] = []

class Journey(DataBaseModel):
    trip_id: str = PrimaryKey(default=get_uuid4)
    waypoints: List[Optional[Coordinate]] = []

```
