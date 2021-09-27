from typing import List
from fastapi import FastAPI
from pydbantic import Database
from tests.models import Employee

#from tests.conftest import endpoint_router

app = FastAPI()

#Employee.media_type = 'application/json'

#app.include_router(endpoint_router())

@app.on_event('startup')
async def db_setup():
    db = await Database.create(
        'sqlite:///test4.db',
        tables=[Employee],
        #cache_enabled=True,
        debug=True
    )
    #breakpoint()

@app.post('/employee')
async def new_example(employee: Employee):
    #breakpoint()
    return await employee.insert()

@app.get('/employees', response_model=List[Employee])
async def view_employees():
    return await Employee.all()