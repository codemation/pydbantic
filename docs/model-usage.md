## DataBaseModel Usage

### Model Definitions
`DataBaseModel`s can be comprised of native `type` objects such as [str, int, float, bool, list, dict, tuple], `BaseModel` objects comprised and structured with native types and `BaseModels`, and lastly other related `DataBaseModel` objects. Data is automatically serialized before stored in a database when needed, and deseriaized to match the model's definition including related data. 

```python
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

### Model Usage - Updating
Updates to `DataBaseModel` objects must be done directly via an object instance, related `DataBaseModel` field objects must be updated by calling the related fields object's `.save()` or `.update()` method. 


```python
    all_employees = await Employees.select('*')
    
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
    all_employees = await Employees.select('*')
    
    # delete latest employee
    await all_employees[-1].delete()
```

!!! WARNING
    Deleted objects which are depended on by other `DataBaseModel` are <u>NOT</u> deleted, as no strict table relationships exist between `DataBaseModel`. This may be changed later. 