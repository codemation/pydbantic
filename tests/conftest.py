from asyncio.base_events import _run_until_complete_cb
import pytest
import time
import os
import uvloop
import json
import asyncio
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from pydbantic import DataBaseModel, Database
from tests.models import Employee




DB_PATH = {
    'sqlite': 'sqlite:///test.db',
    'postgres': 'postgresql://postgres:abcd1234@localhost/database'
}

DB_URL = DB_PATH[os.environ['ENV']]

uvloop.install()

@pytest.fixture()
def db_url():
    return DB_PATH[os.environ['ENV']]

@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def empty_database_and_model_no_cache(request):
    db = await Database.create(
        request.param,
        tables=[Employee],
        cache_enabled=False
    )
    yield db, Employee
    Employee.__metadata__.tables['Employee']['table'].drop()
    db.metadata.drop_all()

@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def database_with_cache(request):

    db = await Database.create(
            request.param,  
            tables=[Employee],
            cache_enabled=True
        )

    yield db, Employee

    Employee.__metadata__.tables['Employee']['table'].drop()
    db.metadata.drop_all()
    await db.cache.redis.flushdb()
    await db.cache.redis.close()

@pytest.fixture()
async def empty_database_and_model_with_cache(database_with_cache):

    db = database_with_cache

    #await db.cache.redis.flushdb()
    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model(database_with_cache):
    db = database_with_cache
    for _ in range(200):
        employee = Employee(**json.loads(
        f"""
  {{
    "id": "abcd{time.time()}",
    "employee_info": {{
      "ssn": "1234",
      "first_name": "joe",
      "last_name": "last",
      "address": "123 lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": {{
      "id": "1234",
      "name": "manager",
      "department": {{
        "id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }},
    "salary": 0,
    "is_employed": true,
    "date_employed": null
  }}""")
    )

        await employee.insert()

    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model_no_cache(empty_database_and_model_no_cache):
    db = empty_database_and_model_no_cache
    for _ in range(200):
        employee = Employee(**json.loads(
        f"""
  {{
    "id": "abcd{time.time()}",
    "employee_info": {{
      "ssn": "1234",
      "first_name": "joe",
      "last_name": "last",
      "address": "123 lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": {{
      "id": "1234",
      "name": "manager",
      "department": {{
        "id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }},
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
    for _ in range(800):
        employee = Employee(**json.loads(
        f"""
  {{
    "id": "abcd{time.time()}",
    "employee_info": {{
      "ssn": "1234",
      "first_name": "joe",
      "last_name": "last",
      "address": "123 lane",
      "address2": null,
      "city": null,
      "zip": null
    }},
    "position": {{
      "id": "1234",
      "name": "manager",
      "department": {{
        "id": "5678",
        "name": "hr",
        "company": "abc company",
        "is_sensitive": false
      }}
    }},
    "salary": 0,
    "is_employed": true,
    "date_employed": null
  }}""")
    )

        await employee.insert()

    yield db, Employee

@pytest.mark.asyncio
@pytest.fixture()
def init_model():
    with open('example.py', 'w') as e:
        e.write(f"""
from pydbantic import DataBaseModel
class Data(DataBaseModel):
    a: int
    b: float
    c: str = 'test'
""")
    from example import Data
    yield Data
    with open('example.py', 'w') as e:
        e.write(f"""
from pydbantic import DataBaseModel
class Data(DataBaseModel):
    a: int
    b: float
    c: str = 'test'
    d: tuple = (1,2)
""")

@pytest.fixture()
def new_model_1():
    from example import Data
    yield Data
    with open('example.py', 'w') as e:
        e.write(f"""
from pydbantic import DataBaseModel
class Data(DataBaseModel):
    a: int
    b: float
    c: str = 'test'
    d: list = [1,2]
""")

@pytest.fixture()
def new_model_2():
    with open('example.py', 'w') as e:
        e.write(f"""
from pydbantic import DataBaseModel
class Data(DataBaseModel):
    __renamed__ = [
        {{'old_name': 'b', 'new_name': 'b_new'}}
    ]
    a: int
    b_new: float
    c: str = 'test'
    d: list = [1,2]
""")
    from example import Data
    yield Data

def endpoint_router():
    router = APIRouter()
    @router.post('/example/create')
    async def create_new_example(employee: Employee):
        return await employee.insert()
    
    return router

@pytest.mark.asyncio
@pytest.fixture
async def fastapi_app_with_loaded_database(loaded_database_and_model):
    app = FastAPI()

    app.include_router(endpoint_router())

    @app.post('/employee')
    async def new_example(employee: Employee):
        return await employee.insert()

    @app.get('/employees')
    async def view_employees():
        return await Employee.select('*')
    
    return app