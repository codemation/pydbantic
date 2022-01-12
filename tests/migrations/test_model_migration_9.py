from logging import exception
import time
import random
import uuid
from typing import Optional, List
from attr import has
import pytest


from pydbantic import Database, DataBaseModel, PrimaryKey, Default
from pydantic import BaseModel

def get_uuid():
    return str(uuid.uuid4())

def get_random_name():
    return f"{get_uuid()}_{random.choice(['joe', 'john', 'bill'])}"

class Ancestor(DataBaseModel):
    name: str = PrimaryKey()
    relatives: List['Related'] = []

class Related(DataBaseModel):
    f: str = PrimaryKey(default=get_uuid)
    g: str = 'abcd1234'
    parents: List[Ancestor] = []

class SubData(BaseModel):
    a: int = 1
    b: float = 1.0

class Data(DataBaseModel):
    a: int
    b_new: float
    c: str
    d: list
    e: str = PrimaryKey(default=get_uuid)
    i: str
    sub: SubData = None
    related: Optional[Related] = None

@pytest.mark.asyncio
async def test_model_migrations_9_new(db_url):
    db = await Database.create(
        db_url,
        tables=[Data, Related, Ancestor],
        cache_enabled=False
    )
    data_items = await Data.all()
    ancestor = Ancestor(name=f"{get_random_name()}")

    for data in data_items:
        assert hasattr(data, 'related')
        assert hasattr(data.related, 'parents')
        assert len(data.related.parents) == 0 # should not be a RelationshipRef
        
        data.related.parents.append(
            ancestor
        )
        await data.related.save()
    
    assert len(data_items) == 10

    data_items = await Data.all()

    for data in data_items:
        assert hasattr(data, 'related')
        assert hasattr(data.related, 'parents')
        assert len(data.related.parents) == 1
    
    ancestor = await Ancestor.all()
    assert len(ancestor) == 1

    assert len(ancestor[0].relatives) == 10