import pytest
from tests.models import Employee, EmployeeInfo, Positions, Department

@pytest.mark.asyncio
async def test_model_many_to_many(loaded_database_and_model):
    db = loaded_database_and_model

    departments = await Department.all()
    department = departments[0]

    assert len(department.positions) == 1
    assert len(department.positions[0].employees) == 200

    manager_position = department.positions[0]

    # test removal via pop
    department.positions.pop(0)
    await department.save()

    departments = await Department.all()
    assert len(departments[0].positions) == 0

    manager_position = await Positions.get(Positions.position_id==manager_position.position_id)

    assert len(manager_position.employees) == 200
    
    removed_employee = manager_position.employees.pop()

    await manager_position.save()

    manager_position = await Positions.get(Positions.position_id==manager_position.position_id)

    assert len(manager_position.employees) == 199
    
    employee = await Employee.get(Employee.employee_id == removed_employee.employee_id)
    assert len(employee.position) == 0

