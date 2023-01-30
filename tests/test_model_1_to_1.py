import pytest
from tests.models import EmployeeInfo, Employee, Department

@pytest.mark.asyncio
async def test_model_1_to_1(loaded_database_and_model):
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

    positoin_in_department = await employee_info.employee.position[0].department.positions[0]()
    assert positoin_in_department.department.department_id == employee_info.employee.position[0].department.department_id
