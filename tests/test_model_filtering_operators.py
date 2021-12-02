import pytest
from tests.models import EmployeeInfo

@pytest.mark.asyncio
async def test_model_filtering_operators(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    all_employees = await Employees.all()

    print(f"Number of Employees is ", len(all_employees))

    assert len(all_employees) == 200

    for i in range(1, 6):
        all_employees[i].salary = i * 10000
        await all_employees[i].save()

    big_salary_employee = await Employees.filter(
        Employees.gte('salary', 50000)
    )
    assert len(big_salary_employee) == 1


    mid_salary_employee = await Employees.filter(
        Employees.gte('salary', 30000),
        Employees.lte('salary', 40000)
    )
    assert len(mid_salary_employee) == 2

    low_and_high_salary = await Employees.filter(
        Employees.lt('salary', 20000),
        Employees.gt('salary', 40000)
    )

    assert len(mid_salary_employee) == 2


    employees_starting_with_jo = await EmployeeInfo.filter(
        EmployeeInfo.contains('first_name', 'jo')
    )
    assert len(employees_starting_with_jo) == 200

