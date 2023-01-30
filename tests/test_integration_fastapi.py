import time
import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_fastapi_integration(fastapi_app_with_loaded_database):
    with TestClient(fastapi_app_with_loaded_database) as client:

        from tests.models import Employee, Department, Positions, EmployeeInfo

        response = client.get('/employees')
        
        assert response.status_code == 200

        current_employees = response.json()

        for employee in current_employees:
            del employee['employee_info']['employee']
            del employee['position'][0]['employees']
            del employee['position'][0]['department']['positions']
            try:
                Employee(**employee)
            except Exception as e:
                pass
        
        response = client.get('/employees')
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 200

        emps = await Employee.all()
        pos = await Positions.all()
        deps = await Department.all()

        for employee in employees:
            del employee['employee_info']['employee']
            del employee['position'][0]['employees']
            del employee['position'][0]['department']['positions']

            new_employee = Employee(**employee)
        
            new_employee.employee_id = f'{employee["employee_id"]}_new_{time.time()}'
            response = client.post('/employee', json=new_employee.dict())
            assert response.status_code == 200
    

        response = client.get('/employees')
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 400

        # verify bad input
        for employee in employees:
            del employee['employee_info']['employee']
            del employee['position'][0]['employees']
            del employee['position'][0]['department']['positions']
            Employee(**employee)
        
            employee['employee_id'] = f'{employee["employee_id"]}_new_{time.time()}'
            employee['is_employed'] = 'not a bool'
            response = client.post('/employee', json=employee)

            # should fail with 422
            assert response.status_code == 422