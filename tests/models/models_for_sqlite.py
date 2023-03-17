from typing import Optional

from pydantic import BaseModel, Field

from pydbantic import DataBaseModel


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
    __renamed__ = [{"old_name": "first_names", "new_name": "first_name"}]
    ssn: str
    first_name: str
    last_name: str
    address: str
    address2: Optional[str]
    city: Optional[str]
    zip: Optional[int]


class Employee(DataBaseModel):
    id: str
    employee_info: EmployeeInfo
    position: Positions
    salary: float
    is_employed: bool
    date_employed: Optional[str]
