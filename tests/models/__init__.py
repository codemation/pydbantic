from uuid import uuid4
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from pydbantic import DataBaseModel, PrimaryKey, Default

class Department(DataBaseModel):
    id: str 
    name: str
    company: str
    is_sensitive: bool = False

class Positions(DataBaseModel):
    id: str
    name: str
    department: Department

class EmployeeInfo(DataBaseModel):
    #__renamed__= [{'old_name': 'first_name', 'new_name': 'first_names'}]
    ssn: str
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]
    new: Optional[str]

class Employee(DataBaseModel):
    id: str = PrimaryKey()
    employee_info: Optional[EmployeeInfo]
    position: Positions
    salary: float
    is_employed: bool
    date_employed: Optional[str]

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
