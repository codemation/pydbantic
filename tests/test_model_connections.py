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
            
            employee = await Employees.create(
                **all_employees[-1].dict()
            )

            result = await all_employees[-2].save()

    assert  all_employees[-2] == await Employees.get(id=all_employees[-2].id)

    # test unique 
    try:
        await Employees.create(
            **all_employees[-1].dict()
        )
    except Exception:
        pass
    else:
        assert False, f"expected IntegrityError due to duplicate primary key insert attempts"

    data = all_employees[-1].dict()
    data['id'] = 'special'
    new_example = Employees(
        **data
    )

    async with db:
        await new_example.insert()

        verify_examples = await Employees.filter(id='special')

    assert len(verify_examples) == 1