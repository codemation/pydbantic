import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_models(database_with_cache):
    db_path, Employees = database_with_cache


    result = await Employees.select('*')

    # no data is expected yet
    assert len(result) == 0, 'no data is expected yet'

    new_employee = {
        'id': 'abcd1632173531.8840718', 
        'employee_info': {
            'ssn': '1234', 
            'first_name': 'new name - updated', 
            'last_name': 'last', 
            'address': '123 lane', 
            'address2': None, 'city': None, 'zip': None
        }, 
        'position': {
            'id': '1234', 
            'name': 'manager', 
            'department': {
                'id': '5678', 
                'name': 'hr', 
                'company': 'abc company', 
                'is_sensitive': False
            }}, 
        'salary': 0.0, 
        'is_employed': False, 
        'date_employed': None
    }

    employee = Employees(
        **new_employee
    )

    await employee.insert()

    result = await Employees.select('*')

    assert len(result) == 1, 'expected a single entry'

    # verify data in result matches original example
    assert result[0].id == employee.id
    assert result[0].employee_info == employee.employee_info
    assert result[0].position == employee.position
    assert result[0].salary == employee.salary
    assert result[0].is_employed == employee.is_employed