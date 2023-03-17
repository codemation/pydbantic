## Tutorials
This section will cover:

- basic and advanced concepts creating a basic model with `pydbantic`
- linking `DataBaseModel`s with a database
- integrating `DataBaseModel` within a FastAPI application and create some data
- modifying our model to demonstrate migrations.

#### Creating a Model
Here we create a `DataBaseModel` which stores employee information. This model contains only standard `types` and `typing` extensions `Optional` indicating  whether a null value is allowed

```python
# models.py
class EmployeeInfo(DataBaseModel):
    ssn: str
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]

```

#### Creating Models with Relationships
Here we are extending our existing `EmployeeInfo` model with a new  `DataBaseModel` name `Employees` which will populate data from `EmployeeInfo` based on an automatic relationship between `Employees.id` & `EmployeeInfo.ssn`

```python
class Employees(DataBaseModel):
    id: str
    employee_info: EmployeeInfo
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```

#### Linking Models with a database
Models are linked with a database by feeding a list of `DataBaseModel`s into a pydbantic `Database` at creation.

```python
import asyncio
from pydbantic import Database
from models import Employees

async def main():
    db = await Database.create(
        'sqlite:///test.db',
        tables=[Employees]
    )

if __name__ == '__main__':
    asyncio.run(main())
```

!!! NOTE
    The first parameter to `Database.create` is a URL DB connection string. This is needed for all database types and should contain relevant user / pw, host, port and other user requirements as necessary.


#### Using Models with a FastAPI application
As `DataBaseModels` are inherently pydantic `BaseModels`, they work seamlessly with the `FastAPI` openAPI schema, generating self documenting API's with expected input / response data structures.

Here we link our existing `Employees` model with a basic API that creates new employees, lists existing employees

```python
# fastapi application
from typing import List
from fastapi import FastAPI
from pydbantic import Database
from tests.models import Employee

app = FastAPI()

@app.on_event('startup')
async def db_setup():
    db = await Database.create(
        'sqlite:///company.db',
        tables=[Employees],
    )

@app.post('/employee')
async def new_example(employee: Employee):
    return await employee.insert()

@app.get('/employees', response_model=List[Employees])
async def view_employees():
    return await Employee.all()
```

At this point we should be able to start our Application and feed in some data to create persistent `Employees` objects.

!!! NOTE
    When viewed from the application `/docs`, the `view_employees` endpoint should indicate the response should be a `List` of `Employees`.

#### Changing a DataBaseModel - Adding a new Dependent Model
Here we will add a new field to our existing `Employees` model which is also a `DataBaseModel` representing employee positions in a company.

```python
## models.py
from enum import Enum
from pydbantic import DataBaseModel, PrimaryKey

class PositionNames(str, Enum):
    manager: str = 'manager'
    director: str 'director'
    engineer: str 'engineer'


class Positions(DataBaseModel):
    id: str = PrimaryKey()
    name: PositionNames


## Adding Positions to Employee
class Employees(DataBaseModel):
    id: str = PrimaryKey()
    employee_info: EmployeeInfo
    position: Positions = Position(id='p123', name='engineer')
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```

The next time we start our application, the new schema will be detected and existing data migrated with new schema.

!!! TIP
    Default Values or `Optional` types are needed when adding a field to an existing model. Once migrated, the default value fields can be removed if undesired.
