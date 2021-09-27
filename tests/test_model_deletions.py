import pytest

@pytest.mark.asyncio
async def test_model_deletions(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    employee = await Employees.select('*')
    #breakpoint()
    assert len(employee) == 200
    employee = employee[0]

    await employee.delete()

    result = await Employees.select('*')

    assert len(result) == 199

    await employee.insert()

    result = await Employees.select('*')

    assert len(result) == 200

    employee2 = Employees(**employee.dict())

    try:
        await employee2.insert()
    except Exception as e:
        pass
    
    employee2.id += '_new'
    await employee2.insert()

    result = await Employees.select('*')

    assert len(result) == 201

    for row in result:
        await row.delete()
    
    result = await Employees.select('*')

    assert len(result) == 0
    