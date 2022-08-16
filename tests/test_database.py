import time
import pytest
from pydbantic import Database
from tests.models import Employee, EmployeeInfo, Positions, Department

@pytest.mark.asyncio
async def test_database(db_url):
    db = await Database.create(
        db_url,
        tables=[Employee, Positions, Department],
        cache_enabled=False,
        testing=True
    )
    sel = await db.TableMeta.select('*')

    result = await Employee.select('*')

    new_employee = {
        'employee_id': 'abcd1632173531.8840718', 
        'employee_info': {
            'ssn': '1234', 
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
    
    employee = Employee(**new_employee)
    await employee.insert()
    emp_info = await EmployeeInfo.filter(bio_id=employee.employee_info.bio_id)

    result = await Employee.select('*', where={'employee_id': employee.employee_id})

    result = await Employee.select('*')

    await employee.delete()

    result = await Employee.select('*', where={'employee_id': employee.employee_id})

    result = await Employee.select('*', where={'employee_id': employee.employee_id})

    result = await Employee.select('*', where={'employee_id': employee.employee_id})

    for i in range(21, 40):
        i = int(time.time()) + i
        position = new_employee['position'][0]
        position['employee_id'] = f'p{i}'
        emp = Employee(
            employee_id=f'a{i}',
            position=[position],
            is_employed=True, 
            salary=new_employee['salary'], 
            employee_info=new_employee['employee_info'],
        )
        await emp.insert()
        emp = await Employee.get(employee_id=f'a{i}')
        emp_info: EmployeeInfo = await EmployeeInfo.filter(bio_id=emp.employee_info.bio_id)
        assert len(emp_info) == 1

        emp_info = emp_info[0]
        # this should fail due to unique constraint on bio_id
        emp_info.ssn = 1234567890
        await emp_info.save()
    
    filtered_employee = await Employee.filter(is_employed=True)
    assert len(filtered_employee) > 0

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 0

    await employee.insert()

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 1
    
    db.metadata.drop_all()