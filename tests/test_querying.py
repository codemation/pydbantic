import time
from typing import MutableSequence
import pytest

@pytest.mark.asyncio
async def test_querying(loaded_database_and_model_with_cache):
    db, Employee = loaded_database_and_model_with_cache

    all_employees = await Employee.all()

    assert len(all_employees) == 20

    all_employees[19].salary = 40000

    await all_employees[19].update()

    # get employee with salary

    emp_with_salary = await Employee.filter(salary=40000)

    assert emp_with_salary[0].salary == 40000

    emp_with_salary = await Employee.filter(Employee.salary==40000)

    assert emp_with_salary[0].salary == 40000

    manager_position = emp_with_salary[0].position
    #breakpoint()
    # filter on manager positions
    managers = await Employee.filter(
        position=manager_position[0],
        salary=40000, 
        employee_info=emp_with_salary[0].employee_info
    )

    assert len(managers) ==1

    # filter on manager positions
    managers = await Employee.filter(
        Employee.position==manager_position[0], 
        Employee.salary==40000, 
        Employee.employee_info==emp_with_salary[0].employee_info
    )
    assert len(managers) ==1

    assert managers[0].salary == 40000

    assert managers[0].employee_info.ssn == emp_with_salary[0].employee_info.ssn

    manager = await Employee.get(employee_id=managers[0].employee_id)

    assert manager.employee_id == managers[0].employee_id

    manager = await Employee.get(Employee.employee_id==managers[0].employee_id)

    assert manager.employee_id == managers[0].employee_id

    ranged_salary = await Employee.filter(
        Employee.salary.inside([40000, 10000, 30000])
    )
    assert len(ranged_salary) ==1