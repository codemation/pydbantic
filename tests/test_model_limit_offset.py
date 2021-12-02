import pytest

@pytest.mark.asyncio
async def test_model_limits_and_offsets(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    all_employees = await Employees.all()

    print(f"Number of Employees is ", len(all_employees))

    assert len(all_employees) == 200

    limited = await Employees.all(limit=100, offset=0)
    assert len(limited) == 100
    
    limited_offset = await Employees.all(limit=25, offset=175)
    #breakpoint()
    assert len(limited_offset) == 25

    limited_offset_filtered = await Employees.filter(is_employed=True, limit=25, offset=175)
    #breakpoint()
    assert len(limited_offset) == 25