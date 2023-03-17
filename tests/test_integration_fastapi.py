import time

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_fastapi_integration(fastapi_app_with_loaded_database):
    async with AsyncClient(
        app=fastapi_app_with_loaded_database, base_url="http://test"
    ) as test_client:
        from tests.models import Department, Employee, EmployeeInfo, Positions

        response = await test_client.get("/employees")

        assert response.status_code == 200

        current_employees = response.json()

        for employee in current_employees:
            del employee["employee_info"]["employee"]
            del employee["position"][0]["employees"]
            del employee["position"][0]["department"]["positions"]
            try:
                Employee(**employee)
            except Exception as e:
                pass

        response = await test_client.get("/employees")
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 200

        emps = await Employee.all()
        pos = await Positions.all()
        deps = await Department.all()

        for employee in employees:
            del employee["employee_info"]["employee"]
            del employee["position"][0]["employees"]
            del employee["position"][0]["department"]["positions"]

            new_employee = Employee(**employee)

            new_employee.employee_id = f'{employee["employee_id"]}_new_{time.time()}'
            response = await test_client.post("/employee", json=new_employee.dict())
            assert response.status_code == 200

        response = await test_client.get("/employees")
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 400

        # verify bad input
        for employee in employees:
            del employee["employee_info"]["employee"]
            del employee["position"][0]["employees"]
            del employee["position"][0]["department"]["positions"]
            Employee(**employee)

            employee["employee_id"] = f'{employee["employee_id"]}_new_{time.time()}'
            employee["is_employed"] = "not a bool"
            response = await test_client.post("/employee", json=employee)

            # should fail with 422
            assert response.status_code == 422
