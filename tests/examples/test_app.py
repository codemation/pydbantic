from typing import List

from fastapi import FastAPI

from pydbantic import Database
from tests.models import Employee

app = FastAPI()


@app.on_event("startup")
async def db_setup():
    db = await Database.create(
        "sqlite:///test4.db",
        tables=[Employee],
        debug=True,
    )


@app.post("/employee")
async def new_example(employee: Employee):
    return await employee.insert()


@app.get("/employees", response_model=List[Employee])
async def view_employees():
    return await Employee.all()
