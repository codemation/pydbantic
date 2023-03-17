import time

import pytest

from pydbantic import Database
from tests.models import Department, Employee, EmployeeInfo, Positions


@pytest.mark.asyncio
async def test_database(db_url):
    db = await Database.create(
        db_url,
        tables=[EmployeeInfo, Employee, Positions, Department],
        cache_enabled=False,
        testing=True,
        use_alembic=False,
    )
    sel = await db.TableMeta.all()

    result = await Employee.all()

    new_employee = {
        "employee_id": "abcd1632173531.8840718",
        "employee_info": {
            "first_name": "new name - updated",
            "ssn": 0,
            "last_name": "last",
            "address": "123 lane",
            "address2": None,
            "city": None,
            "zip": None,
        },
        "position": [
            {
                "position_id": "1234",
                "name": "manager",
                "department": {
                    "department_id": "5678",
                    "name": "hr",
                    "company": "abc company",
                    "is_sensitive": False,
                },
            }
        ],
        "salary": 0.0,
        "is_employed": False,
        "date_employed": None,
    }

    employee = Employee(**new_employee)

    await employee.insert()
    emp_info = await EmployeeInfo.filter(bio_id=employee.employee_info.bio_id)
    employee.emp_ssn = emp_info[0].ssn
    await employee.save()

    result = await Employee.filter(employee_id=employee.employee_id)

    result = await Employee.all()

    await employee.delete()

    result = await Employee.filter(employee_id=employee.employee_id)

    for i in range(21, 40):
        i = int(time.time()) + i
        position = new_employee["position"][0]
        position["employee_id"] = f"p{i}"
        e_info = employee.employee_info.dict()
        e_info.pop("ssn")
        e_info.pop("bio_id")

        e_info = await EmployeeInfo.create(**e_info)

        e_info = await EmployeeInfo.filter(bio_id=e_info.bio_id)

        emp = Employee(
            employee_id=f"a{i}",
            emp_ssn=e_info[0].ssn,
            position=[position],
            is_employed=True,
            salary=new_employee["salary"],
            employee_info=e_info[0],
        )

        await emp.insert()

        emp = await Employee.get(employee_id=f"a{i}")
        emp_info: EmployeeInfo = await EmployeeInfo.filter(
            bio_id=emp.employee_info.bio_id
        )
        assert len(emp_info) == 1

        try:
            emp_info = emp_info[0]
            # this should fail due to unique constraint on bio_id
            emp_info.ssn = 1234567890
            await emp_info.save()

            assert (
                False
            ), f"This should have thrown an Integrity Exception for Unique field"
        except Exception:
            pass

    filtered_employee = await Employee.filter(is_employed=True)
    assert len(filtered_employee) > 0

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 0

    await employee.insert()

    filtered_employee = await Employee.filter(is_employed=False)
    assert len(filtered_employee) == 1

    all_emps = await Employee.all()
    assert len(all_emps) == 20
