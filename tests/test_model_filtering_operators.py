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


    employees_with_salary = await Employees.filter(
        Employees.gt('salary', 0),
        order_by=Employees.asc('salary')
    )
    for i, employee in enumerate(employees_with_salary):
        if i == 0:
            continue
        assert employees_with_salary[i].salary > employees_with_salary[i-1].salary

    employees_with_salary = await Employees.filter(
        Employees.gt('salary', 0),
        order_by=Employees.desc('salary')
    )
    for i, employee in enumerate(employees_with_salary):
        if i == 0:
            continue
        assert employees_with_salary[i].salary < employees_with_salary[i-1].salary

    mid_salary_employees = await Employees.filter(

        Employees.gte('salary', 30000),
        Employees.lte('salary', 40000)
    )
    assert len(mid_salary_employee) == 2

    mid_salary_employees = await Employees.filter(
        Employees.salary >= 30000,
        Employees.salary <= 40000
    )

    assert len(mid_salary_employee) == 2

    mid_salary_employees = await Employees.filter(
        Employees.salary.matches([30000, 40000])
    )
    
    assert len(mid_salary_employee) == 2

    mid_salary_employees = await Employees.filter(
        Employees.salary == 30000,
    )
    assert len(mid_salary_employee) == 2

    init_employees = await Employees.filter(
        Employees.salary >= 30000
    )
    second_employees = await Employees.filter(
        Employees.salary.matches([20000, 40000])
    )

    mid_salary_employees = await Employees.filter(
        Employees.OR(
            Employees.salary >= 30000,
            Employees.salary.matches([20000, 40000])
        ),
        Employees.is_employed == True
    )
    
    assert len(mid_salary_employees) == 4