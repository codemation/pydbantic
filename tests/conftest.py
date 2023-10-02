import asyncio
import json
import os
import time

import pytest
from fastapi import APIRouter, FastAPI

from pydbantic import Database
from pydbantic.cache import Redis
from tests.models import Child, Department, Employee, EmployeeInfo, Parent, Positions

DB_PATH = {
    "sqlite": "sqlite:///test.db",
    "mysql": "mysql://mysqltestuser:abcd1234@127.0.0.1/database",
    "postgres": "postgresql://postgres:postgres@localhost/database",
}

DB_URL = DB_PATH[os.environ["ENV"]]


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop
    loop.close()


@pytest.fixture()
def db_url():
    return DB_PATH[os.environ["ENV"]]


@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def empty_database_and_model_no_cache(request):
    db = await Database.create(
        request.param,
        tables=[EmployeeInfo, Employee, Positions, Department],
        cache_enabled=False,
        # testing=True,
    )
    yield db, Employee
    db.metadata.drop_all(db.engine)


@pytest.mark.asyncio
@pytest.fixture(params=[DB_URL])
async def database_with_cache(request):
    db = await Database.create(
        request.param,
        tables=[EmployeeInfo, Employee, Positions, Department, Parent, Child],
        cache_enabled=False,
        testing=True,
    )

    yield db, Employee
    db.metadata.drop_all(db.engine)

    # await db.cache.redis.flushall()
    # await db.cache.redis.close()


@pytest.fixture()
async def empty_database_and_model_with_cache(database_with_cache):
    db = database_with_cache

    yield db, Employee


async def load_db(db):
    async with db:
        employees = []
        for i in range(200):
            employee = Employee(
                **json.loads(
                    f"""
  {{
    "employee_id": "abcd{i}",
    "employee_info": {{
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
  }}"""
                )
            )
            employees.append(employee)
        result = await Employee.insert_many(employees)


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
        employee = Employee(
            **json.loads(
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
  }}"""
            )
        )

        await employee.insert()

    yield db, Employee


@pytest.mark.asyncio
@pytest.fixture()
async def loaded_database_and_model_with_cache(database_with_cache):
    db = database_with_cache
    for i in range(20):
        employee = Employee(
            **json.loads(
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
  }}"""
            )
        )

        await employee.insert()

    yield db, Employee


@pytest.mark.asyncio
@pytest.fixture()
async def fastapi_app_with_loaded_database(loaded_database_and_model):
    app = FastAPI()

    router = APIRouter()

    @router.post("/example/create")
    async def create_new_example(employee: Employee):
        return await employee.insert()

    app.include_router(router)

    @app.post("/employee")
    async def new_example(employee: Employee):
        result = await employee.insert()
        return result

    @app.get("/employees")
    async def view_employees():
        employees = await Employee.all()
        return employees

    yield app
