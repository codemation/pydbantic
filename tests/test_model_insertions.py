import time
import pytest
import sqlite3

@pytest.mark.asyncio
async def test_model_insertions(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    all_employees = await Employees.all()
    await all_employees[-1].delete()
    await all_employees[-2].delete()
    # result = await all_employees[-2].save()
    # deleted_emp = await Employees.get(id=all_employees[-2].id)

    new_employee = {
            'employee_id': 'abcd1990', 
            'employee_info': {
                'first_name': 'joe', 
                'last_name': 'last', 
                'address': '199 lane', 
                'address2': None, 
                'city': None, 
                'zip': None, 
                'new': None, 
            }, 
            'position': [
                {
                    'position_id': '1234', 
                    'name': 'manager', 
                    'department': {
                        'department_id': '5678', 
                        'name': 'hr', 
                        'company': 'abc company', 
                        'is_sensitive': False
                    }
                }
            ],
            'salary': 0.0,
            'is_employed': True, 
            'date_employed': None
        }
    # creation via .create
    employee = await Employees.create(**new_employee)

    #breakpoint()
    # creation via .save #TODO - determine why Save fails to 
    # update foreign models 
    result = await all_employees[-2].save()

    
    verify_emp = await Employees.get(employee_id=all_employees[-2].employee_id)

    assert  all_employees[-2].employee_id == verify_emp.employee_id
    assert  all_employees[-2].salary == verify_emp.salary


    # test unique
    try:
        await Employees.create(
            **new_employee
        )
    except Exception:
        pass
    else:
        assert (
            False
        ), 'expected IntegrityError due to duplicate primary key insert attempts'


    data = new_employee
    data['employee_id'] = 'special'
    new_example = Employees(
        **data
    )

    await new_example.insert()

    verify_examples = await Employees.filter(employee_id='special')

    assert len(verify_examples) == 1