## Tutorials
This section will cover some basic and advanced concepts creating a basic model with `pydbantic`, linking this with a database, integrating within an new FastAPI application and create some data, then modifying our model to demonstrate migrations.

### Tutorial - Basic
!!! TIP 
    pydbantic `DataBaseModels` are effectivly pydantic `BaseModels` in that they directly extend pydantic capabilities by translating both standard `types`, `BaseModels`, and `DataBaseModels` into indirect table relationships(in the case of `DataBaseModels`) and object serialization for `types` and `BaseModels` 

#### Creating a Model
Here we create a `DataBaseModel` which stores employee information. This model contains only `types` with `typing` extensions `Optional` indicating  whether a null value is allowed

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
Here we are extending our existing `EmployeeInfo` model with a new  `DataBaseModel` which will reference the data in  `EmployeeInfo` when the data structure is gathered.d

```python
class Employee(DataBaseModel):
    id: str
    employee_info: EmployeeInfo
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```
 
 This structure indicates that field `employee_info` should be of type `EmployeeInfo` and thus follow the same typing, structure  constraints.


!!! TIP 
    As our new `DataBaseModel` (`Employee`) and existing are both `DataBaseModel`'s  their respective data will be saved in separte tables. Since `Employee` depends on an `EmployeeInfo` model, the data is linked by `Employee` storing the related `EmployeeInfo` primary key. 

#### Linking Models with a database
Models are linked with a database by feeding a list of `DataBaseModels` into a pydbantic `Database` at creation. 

!!!TIP
    Models with depedent `DataBaseModels` do not need feed their depdencies, this is taken care of automatically on startup. 

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

!!! NOTE
    The first parameter to `Database.create` is a URL DB connection string. This is needed for all database types and should contain relevant user / pw, host, port and other user requirements as necesssary. 


#### Using Models with a FastAPI application
As `DataBaseModels` are inherintly pydantic `BaseModels`, they work seamlessly with `FastAPI`'s openAPI schema generation to allow us to generate self documentating API's with expected input / response data structures.

Here we link our existing `Employee` model with a basic API that creates new employees, lists existing employees

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
        tables=[Employee],
    )

@app.post('/employee')
async def new_example(employee: Employee):
    return await employee.insert()

@app.get('/employees', response_model=List[Employee])
async def view_employees():
    return await Employee.all()
```

At this point we should be able to start our Application and feed in some data to create persistent `Employee` objects. 

!!! NOTE
    When viewed from the application `/docs`, the `view_employees` endpoint should indicate the response should be a `List` of `Employees`. 

#### Model Changes to Existing Models - Adding a new Dependent Model
Here we will add a new field to our existing `Employee` model which is also a `DataBaseModel` representing employee positions in the company.

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
class Employee(DataBaseModel):
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
