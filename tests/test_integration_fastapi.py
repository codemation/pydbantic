import time
import pytest
from fastapi.testclient import TestClient
from tests.models import Employee

def test_fastapi_integration(fastapi_app_with_loaded_database):
    with TestClient(fastapi_app_with_loaded_database) as client:

        response = client.get('/employees')
        
        assert response.status_code == 200

        current_employees = response.json()

        for employee in current_employees:
            Employee(**employee)
        
        # # send new model to api_router
        # for employee in current_employees:
        #     new_employee = employee.copy() 
        #     new_employee['id'] = f'{new_employee["id"]}_new_{time.time()}'
        #     response = client.post('/employee/create', json=new_employee)
            
        #     assert response.status_code == 200
        
        response = client.get('/employees')
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 200

        for employee in employees:
            new_employee = Employee(**employee)
        
            new_employee.id = f'{employee["id"]}_new_{time.time()}'
            response = client.post('/employee', json=new_employee.dict())
            assert response.status_code == 200
    

        response = client.get('/employees')
        assert response.status_code == 200

        employees = response.json()

        assert len(employees) == 400

        # verify bad input
        for employee in employees:
            Employee(**employee)
        
            employee['id'] = f'{employee["id"]}_new_{time.time()}'
            employee['is_employed'] = 'not a bool'
            response = client.post('/employee', json=employee)

            # should fail with 422
            assert response.status_code == 422