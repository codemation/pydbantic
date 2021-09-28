import time
import pytest
from pydbantic import Database
from tests.models import Employee

@pytest.mark.asyncio
async def test_database(db_url):
    db = await Database.create(
        db_url,
        tables=[Employee],
        cache_enabled=True
    )
    sel = await db.TableMeta.select('*')

    result = await Employee.select('*')

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
    
    employee = Employee(**new_employee)
    await employee.insert()

    result = await Employee.select('*', where={'id': employee.id})

    result = await Employee.select('*')

    await employee.delete()

    result = await Employee.select('*', where={'id': employee.id})

    result = await Employee.select('*', where={'id': employee.id})

    result = await Employee.select('*', where={'id': employee.id})

    for i in range(21, 40):
        i = int(time.time()) + i
        position = new_employee['position']
        position['id'] = f'p{i}'
        row = Employee(
            id=f'a{i}',
            position=position,
            is_employed=True, 
            salary=new_employee['salary'], 
            employee_info=new_employee['employee_info'],
        )
        await row.insert()
    employees = await Employee.select('*', where={'id': row.id})
    
    filtered_employee = await Employee.filter(is_employed=True)
    assert len(filtered_employee) > 0

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 0

    await employee.insert()

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 1

    Employee.__metadata__.tables['Employee']['table'].drop()
    
    db.metadata.drop_all()
    await db.cache.redis.flushdb()