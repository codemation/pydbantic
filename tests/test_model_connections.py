import time
import pytest
import sqlite3

@pytest.mark.asyncio
async def test_model_transactions(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    async with db as conn:
        async with conn.transaction():
            all_employees = await Employees.all()

            await all_employees[-1].delete()
            await all_employees[-2].delete()

            employee = await all_employees[-1].insert()

            result = await all_employees[-2].save()

    assert  all_employees[-2] == await Employees.get(employee_id=all_employees[-2].employee_id)

    # test unique
    try:
        employee = await all_employees[-1].insert()
    except Exception:
        pass
    else:
        assert (
            False
        ), 'expected IntegrityError due to duplicate primary key insert attempts'


    new_employee = all_employees[-1]
    new_employee.employee_id = 'special'

    async with db:
        await new_employee.insert()

        verify_examples = await Employees.filter(employee_id='special')

    assert len(verify_examples) == 1