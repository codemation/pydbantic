import pytest

from tests.models import Department


@pytest.mark.asyncio
async def test_model_deletions(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    employee = await Employees.all()

    assert len(employee) == 200
    employee = employee[0]

    res = await employee.delete()

    result = await Employees.all()

    assert len(result) == 199

    await employee.insert()

    result = await Employees.all()

    assert len(result) == 200

    employee2 = employee

    try:
        await employee2.insert()
    except Exception as e:
        pass

    employee2.employee_id += "_new"
    await employee2.insert()

    result = await Employees.all()

    assert len(result) == 201

    await Employees.delete_many(result[:100])

    result = await Employees.all()

    assert len(result) == 101

    await Employees.delete_filter(Employees.is_employed == True)

    assert await Employees.count() == 0
