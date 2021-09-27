import os
import time
import pytest

@pytest.mark.asyncio
async def test_query_caching(loaded_database_and_model_with_cache):
    db, Employee = loaded_database_and_model_with_cache

    start = time.time()
    sel = await Employee.select('*')
    perf = time.time() - start

    sel2 = await Employee.select('*')
    perf2 = time.time() - (start + perf)

    print(f"perf: {perf} perf2: {perf2}")

    if not os.environ['ENV'] == 'sqlite':
        assert perf2 < perf, f"cache should have resulted in better performance"
    
    assert len(sel2) == 800

    # trigger cache clear event

    prestart = time.time()
    await Employee.select('*')
    await Employee.select('*')
    prestart = time.time() - prestart

    employee = sel2[0]
    employee.salary = 100000.00
    await employee.update()

    start = time.time()
    sel3 = await Employee.select('*')
    await Employee.select('*')
    perf3 = time.time() - start
    
    if not os.environ['ENV'] == 'sqlite':
        assert perf3 > prestart, f"expected lower perf after cache clear event"

    assert employee == await Employee.get(id=employee.id)

    start = time.time()

    # should NOT be cached -  yet
    filter_sel = await Employee.filter(salary=0.0)
    await Employee.filter(salary=0.0)

    perf4 = time.time() - start

    # should be cached - if enabled
    filter_sel2 = await Employee.filter(salary=0.0)
    await Employee.filter(salary=0.0)

    perf5 = time.time() - (start + perf4)

    print(f"perf4: {perf} perf5: {perf4}")

    if not os.environ['ENV'] == 'sqlite':
        assert abs(perf4 - perf5) < 0.1, f"cache should have resulted in better performance"