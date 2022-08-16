from uuid import uuid4
from datetime import datetime
from typing import List, Optional, Union
from pydbantic import DataBaseModel, PrimaryKey, Unique

def uuid_str():
    return str(uuid4())

class Department(DataBaseModel):
    department_id: str = PrimaryKey()
    name: str
    company: str
    is_sensitive: bool = False
    positions: List[Optional['Positions']] = []

class Positions(DataBaseModel):
    position_id: str = PrimaryKey()
    name: str
    department: Department = None
    employees: List[Optional['Employee']] = []

class EmployeeInfo(DataBaseModel):
    #__renamed__= [{'old_name': 'first_name', 'new_name': 'first_names'}]
    ssn: str = PrimaryKey()
    bio_id: str = Unique(default=uuid_str)
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]
    new: Optional[str]
    employee: Optional[Union['Employee', dict]] = None

class Employee(DataBaseModel):
    employee_id: str = PrimaryKey()
    employee_info: Optional[EmployeeInfo] = None
    position: List[Optional[Positions]] = []
    salary: float
    is_employed: bool
    date_employed: Optional[str]

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