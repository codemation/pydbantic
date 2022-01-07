import pytest
from tests.models import EmployeeInfo, Employee

@pytest.mark.asyncio
async def test_model_filtering_operators(loaded_database_and_model):
    db = loaded_database_and_model

    all_employees = await Employee.all()
    employee = all_employees[0]

    employee_info = await EmployeeInfo.get(
        EmployeeInfo.ssn == employee.employee_info.ssn
    )
    
    assert employee_info.employee.employee_id == employee.employee_id
    assert employee_info.employee.is_employed == employee.is_employed
    assert employee_info.employee.salary == employee.salary
    assert employee_info.employee.date_employed == employee.date_employed

