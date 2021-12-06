## DataBaseModel Usage

### Model Definitions
`DataBaseModel`s can be comprised of native `type` objects such as [str, int, float, bool, list, dict, tuple], `BaseModel` objects comprised and structured with native types and `BaseModels`, and lastly other related `DataBaseModel` objects. Data is automatically serialized before stored in a database when needed, and deseriaized to match the model's definition including related data. 

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from pydbantic import DataBaseModel, PrimaryKey

class Coordinates(BaseModel):

class Department(DataBaseModel):
    name: str = PrimaryKey()
    company: str
    location: Optional[str]

class Positions(DataBaseModel):
    name: str = PrimaryKey()
    department: Department

class EmployeeInfo(DataBaseModel):
    ssn: str = PrimaryKey()
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]

class Employee(DataBaseModel):
    id: str = PrimaryKey()
    employee_info: EmployeeInfo
    position: Positions
    salary: float
    is_employed: bool
    date_employed: Optional[str]
```

### Model Usage - Creation
`DataBaseModel` instances can be created in the same way as `pydantic` `BaseModel`'s, with some differences in how and when data becomes persistent.

#### Create Model & Save Immediately in Database

```python
# create department 
hr_department = await Department.create(
    id='d1234',
    name='hr'
    company='abc-company',
    is_sensitive=True,
)
```
#### Create Model & Save to DB later

```python
# create department 
hr_department = Department(
    id='d1234',
    name='hr'
    company='abc-company',
    is_sensitive=True,
)

await hr_department.insert()
```

#### Create Model & Save / Update Later

```python
# create department 
hr_department = Department(
    id='d1234',
    name='hr'
    company='abc-company',
    is_sensitive=True,
)

await hr_department.save()

```

### Model Usage - Query / Filtering
`DataBaseModel`s can be querried using filter which include absolute values such as integer_column=40, string_column='40', float_column=40.0 etc.. 
 

#### Filtering
In this example, `hr_manager` is a `DataBaseModel` named `Position` which has attributes indicating it's position in hr department. 
```python
# get all hr managers currently employed
managers = await Employee.filter(
    position=hr_manager,
    is_employed=True
)
```
##### Filtering - Operators
`DataBaseModel`s can be filtered using `>`, `>=`, `<=`, `<`, `==`, and a `.matches([value1, value2, value3])` 

```python
# conditionals
mid_salary_employees = await Employees.filter(
    Employees.salary >= 30000,
    Employees.salary <= 40000
)

mid_salary_employees = await Employees.filter(
    Employees.salary.matches([30000, 40000])
)

mid_salary_employees = await Employees.filter(
    Employees.salary == 30000,
)

# combining conditionals with keyword args
mid_salary_employees = await Employees.filter(
    Employees.OR(
        Employees.salary >= 30000,
        Employees.salary.matches([20000, 40000])
    ),
    is_employed = True
)

```

`DataBaseModel`s are also equipped with operator methods allowing for additional filtering of desired objects

```python
# greater than or equal
big_salary_employee = await Employees.filter(
    Employees.gte('salary', 50000)
)

# combined - operators
mid_salary_employee = await Employees.filter(
    Employees.gte('salary', 30000),
    Employees.lte('salary', 40000)
)

low_and_high_salary = await Employees.filter(
    Employees.lt('salary', 20000),
    Employees.gt('salary', 40000)
)

# text searching
employees_starting_with_jo = await EmployeeInfo.filter(
    EmployeeInfo.contains('first_name', 'jo')
)

# sort employees with salary - highest salary first
employees_with_salary = await Employees.filter(
    Employees.gt('salary', 0),
    order_by=Employees.asc('salary')
)

# sort employees with salary - lowest salary first
employees_with_salary = await Employees.filter(
    Employees.gt('salary', 0),
    order_by=Employees.desc('salary')
)

```

#### Get - Primary Key
Objects can be querrried by primary_key using .get() method on a `DataBaseModel` class.


In this example, `Employee` objects are querried for an employee matching a specific 'id', 'id' is the `DataBaseModel` primary key, i.e the first entry in the model

```python
an_employee = await Employee.get(id='abcd1234')
```

#### All Objects
All objects for a given `DataBaseModel` can be querried by using the `.all()` method. 

```python
all_employees = await Employee.all()
```

#### Pagination
`DataBaseModel` query methods `.all()` and `.filter` can be provided with `limit=` and/or `offset=` to generate paginated results.

```python

first_100 = await Employees.all(limit=100, offset=0)

second_100 = await Empoyees.all(limit=100, offset=100)

```

```
# latest 25 employees that are still employed

latest_employees = await Employees.filter(
    is_employed=True,
    limit=25,
    offset=175
)
```
#### Counting
`DataBaseModel` objects can be counted by calling the `.count()` method. Filtered `DataBaseModel` objects can use `.filter(.., count_rows=True)` to return a total count of objects matching a given filter.

```python
employee_count = await Employees.count()

employed_count = await Employees.filter(
      is_employed=True,
      count_rows=True
)
```

### Model Usage - Updating
Updates to `DataBaseModel` objects must be done directly via an object instance, related `DataBaseModel` field objects must be updated by calling the related fields object's `.save()` or `.update()` method. 


```python
all_employees = await Employees.all()

# update is_employed to False for all employees

for employee in all_employees:
    employee.is_employed=False
    await employee.update()


# updating position name of each employee
for employee in all_employees:
    position = employee.position
    position.name = f"{position.name} - terminated"
    await position.update()
```
!!! TIP
    `.save()` can also be used, but first verified object existence before attempting save, while `.update()` does not verify before attempting to update. 

### Model Usage - Deleting
Much like updates, `DataBaseModel` objects can only be deleted by directly calling the `.delete()` method of an object instance. 

```python
all_employees = await Employees.all()

# delete latest employee
await all_employees[-1].delete()
```

!!! WARNING
    Deleted objects which are depended on by other `DataBaseModel` are <u>NOT</u> deleted, as no strict table relationships exist between `DataBaseModel`. This may be changed later. 


### Models with arrays of Foreign Objects

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