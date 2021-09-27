import time
import pytest

@pytest.mark.asyncio
async def test_query_without_caching(loaded_database_and_model_no_cache):
    db, Employee = loaded_database_and_model_no_cache

    start = time.time()
    sel = await Employee.select('*')
    perf = time.time() - start

    sel2 = await Employee.select('*')
    perf2 = time.time() - (start + perf)

    print(f"perf: {perf} perf2: {perf2}")

    assert abs(perf - perf2) < 0.05, f"expected similar performance without caching"
    

    assert len(sel2) == 200

    # trigger cache clear

    Employee = sel2[0]
    Employee.salary = 100000.00
    await Employee.update()

    start = time.time()
    sel3 = await Employee.select('*')
    perf3 = time.time() - start

    start = time.time()

    # should NOT be cached -  yet
    filter_sel = await Employee.filter(salary=0.0)

    perf4 = time.time() - start

    # should be cached - if enabled
    filter_sel2 = await Employee.filter(salary=0.0)

    perf5 = time.time() - (start + perf4)

    print(f"perf4: {perf} perf5: {perf4}")

    assert abs(perf4 - perf3) < 0.05, f"expected similar performance without caching"