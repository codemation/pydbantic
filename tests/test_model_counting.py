import pytest

from tests.models import EmployeeInfo


@pytest.mark.asyncio
async def test_model_counting(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    all_employees = await Employees.all()
    employee_count = await Employees.count()

    print(f"Number of Employees is ", employee_count)

    assert employee_count == len(all_employees)

    employed = await Employees.filter(is_employed=True)

    employed_count = await Employees.filter(
        is_employed=True,
        count_rows=True,
    )

    assert len(employed) == employed_count

    un_employed = await Employees.filter(is_employed=False, count_rows=True)
    assert un_employed == 0
