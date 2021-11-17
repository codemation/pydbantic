import os
import time
import pytest
from tests.models import EmployeeInfo

@pytest.mark.asyncio
async def test_query_without_caching(loaded_database_and_model_no_cache):
    db, Employee = loaded_database_and_model_no_cache

    sel = await Employee.select('*')

    sel2 = await Employee.select('*')

    assert len(sel2) == 200

    # trigger cache clear

    Employee = sel2[0]
    Employee.salary = 100000.00
    await Employee.update()

    sel3 = await Employee.select('*')

    # should NOT be cached -  yet
    filter_sel = await Employee.filter(salary=0.0)

    filter_sel2 = await Employee.filter(salary=0.0)


    all_emp_info = await EmployeeInfo.all()
    for info in all_emp_info:
        await info.delete()
    
    all_emps = await Employee.all()
    filtered_emps = await Employee.filter(salary=all_emps[0].salary)

    assert all_emps[0] == filtered_emps[0]