import pytest

@pytest.mark.asyncio
async def test_model_updates(loaded_database_and_model):
    db, Employees = loaded_database_and_model

    all_employees = await Employees.all()
    employee = all_employees[0]

    # trigger update of sub-model
    employee.employee_info.first_name = 'new name - updated'
    await employee.employee_info.update()

    updated_employee = await Employees.select('*', where={'employee_id': employee.employee_id})

    assert updated_employee[0].employee_info.first_name == 'new name - updated'

    # same model update
    employee = updated_employee[0]

    employee.is_employed = False
    await employee.update()

    updated_employee = await Employees.select('*', where={'is_employed': False})

    assert updated_employee[0].is_employed == employee.is_employed

    updated_employee[0].employee_info = all_employees[1].employee_info

    await updated_employee[0].update()

    modified_employee = await Employees.get(employee_id=updated_employee[0].employee_id)

    assert modified_employee.employee_info.ssn == all_employees[1].employee_info.ssn