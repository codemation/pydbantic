
from pickle import load
import pytest
import time
import sys
import os
import nest_asyncio
import json
import asyncio
import importlib

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from pydbantic import DataBaseModel, Database
from pydbantic.cache import Redis
from tests.models import Department, Employee, EmployeeInfo, Positions


DB_PATH = {
    'sqlite': 'sqlite:///test.db',
    'mysql': 'mysql://josh:abcd1234@127.0.0.1/database',
    'postgres': 'postgresql://postgres:postgres@localhost/database'
}

DB_URL = DB_PATH[os.environ['ENV']]

@pytest.fixture(scope="session")
def event_loop():
    nest_asyncio.apply()
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture()
def db_url():
    return DB_PATH[os.environ['ENV']]

@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def empty_database_and_model_no_cache(request):
    db = await Database.create(
        request.param,
        tables=[Employee, 
                EmployeeInfo, 
                Positions,
                Department],
        cache_enabled=False,
        testing=True
    )
    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def database_with_cache(request):

    db = await Database.create(
            request.param,  
            tables=[
                Employee, 
                EmployeeInfo, 
                Positions,
                Department
            ],
            cache_enabled=False,
            testing=True
        )

    yield db, Employee
    db.metadata.drop_all()

    #await db.cache.redis.flushall()
    #await db.cache.redis.close()

@pytest.fixture()
async def empty_database_and_model_with_cache(database_with_cache):

    db = database_with_cache

    yield db, Employee

async def load_db(db):
    async with db:
        employees = []
        for i in range(200):
            employee = Employee(**json.loads(
        f"""
  {{
    "employee_id": "abcd{i}",
    "employee_info": {{
      "ssn": "{i}",
      "first_name": "joe",
      "last_name": "last",
      "address": "{i} lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": [{{
      "position_id": "1234",
      "name": "manager",
      "department": {{
        "department_id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }}],
    "salary": 0,
    "is_employed": true,
    "date_employed": null
  }}""")
    )
            employees.append(employee)
        await Employee.insert_many(employees)

@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model(database_with_cache):
    db, Employee = database_with_cache
    await load_db(db)
    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model_no_cache(empty_database_and_model_no_cache):
    db = empty_database_and_model_no_cache
    for i in range(200):
        employee = Employee(**json.loads(
        f"""
  {{
    "employee_id": "abcd{i}",
    "employee_info": {{
      "ssn": "1234",
      "first_name": "joe",
      "last_name": "last",
      "address": "123 lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": [{{
      "position_id": "1234",
      "name": "manager",
      "department": {{
        "department_id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }}],
    "salary": 0,
    "is_employed": true,
    "date_employed": null
  }}""")
    )

        await employee.insert()

    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model_with_cache(database_with_cache):
    db = database_with_cache
    for i in range(20):
        employee = Employee(**json.loads(
        f"""
  {{
    "employee_id": "abcd{time.time()}",
    "employee_info": {{
      "ssn": "{i}1234",
      "first_name": "joe",
      "last_name": "last",
      "address": "123 lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": [{{
      "position_id": "1234",
      "name": "manager",
      "department": {{
        "department_id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }}],
    "salary": 0,
    "is_employed": true,
    "date_employed": null
  }}""")
    )

        await employee.insert()

    yield db, Employee

def endpoint_router():
    router = APIRouter()
    @router.post('/example/create')
    async def create_new_example(employee: Employee):
        return await employee.insert()
    
    return router

@pytest.mark.asyncio()
@pytest.fixture()
async def fastapi_app_with_loaded_database(loaded_database_and_model):
    app = FastAPI()

    app.include_router(endpoint_router())

    @app.post('/employee')
    async def new_example(employee: Employee):
        return await employee.insert()

    @app.get('/employees')
    async def view_employees():
        employees = await Employee.all()
        return employees

    return app