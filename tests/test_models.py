import time
import pytest

from pydbantic import Database
from tests.models import Employee

@pytest.mark.asyncio
async def test_models(database_with_cache):
    db_path, _ = database_with_cache


    result = await Employee.select('*')

    # no data is expected yet
    assert len(result) == 0, 'no data is expected yet'

    new_employee = {
        'employee_id': 'abcd1632173531.8840718', 
        'employee_info': {
            'first_name': 'new name - updated', 
            'last_name': 'last', 
            'address': '123 lane', 
            'address2': None, 'city': None, 'zip': None
        }, 
        'position': [{
            'position_id': '1234', 
            'name': 'manager', 
            'department': {
                'department_id': '5678', 
                'name': 'hr',
                'company': 'abc company', 
                'is_sensitive': False
            }}], 
        'salary': 0.0, 
        'is_employed': False, 
        'date_employed': None
    }
    employee = Employee(
        **new_employee
    )

    await employee.insert()

    result = await Employee.select('*')

    assert len(result) == 1, 'expected a single entry'

    # verify data in result matches original example
    assert result[0].employee_id == employee.employee_id
    assert result[0].position[0].position_id == employee.position[0].position_id
    assert result[0].position[0].name == employee.position[0].name
    assert result[0].salary == employee.salary
    assert result[0].is_employed == employee.is_employed
