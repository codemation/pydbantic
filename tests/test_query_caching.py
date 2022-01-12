import os
import time
import pytest
from tests.models import EmployeeInfo

@pytest.mark.asyncio
async def test_query_caching(loaded_database_and_model_with_cache):
    db, Employee = loaded_database_and_model_with_cache

    start = time.time()
    sel = await Employee.select('*')
    perf = time.time() - start

    sel2 = await Employee.select('*')
    perf2 = time.time() - (start + perf)

    print(f"perf: {perf} perf2: {perf2}")
    
    assert len(sel2) == 20

    # trigger cache clear event

    prestart = time.time()
    await Employee.select('*')
    await Employee.select('*')
    prestart = time.time() - prestart

    employee = sel2[0]
    employee.salary = 100000.00
    await employee.update()

    verify_employee = await Employee.get(employee_id=employee.employee_id)

    assert employee == verify_employee

    # should NOT be cached -  yet
    filter_sel = await Employee.filter(salary=0.0)
    await Employee.filter(salary=0.0)

    all_emp_info = await EmployeeInfo.all()
    for info in all_emp_info:
        await info.delete()
    
    all_emps = await Employee.all()
    filtered_emps = await Employee.filter(salary=all_emps[0].salary)

    assert all_emps[0] == filtered_emps[0]