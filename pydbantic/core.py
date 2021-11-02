import uuid
from pydantic import BaseModel, Field
from typing import Optional, Union, List
from pydantic.typing import is_callable_type
import sqlalchemy
from sqlalchemy import select
from pickle import dumps, loads

from pydbantic import database

class _Generic(BaseModel):
    pass

def resolve_missing_attribute(missing_error: str):
    try:
        missing_attr = ''.join(
            missing_error.split("Can't get attribute")[1].split('on <module')
        ).split('from')[0].split(' ')[1][1:-1]

        missing_mod = ''.join(
            missing_error.split("Can't get attribute")[1].split('on <module')
        ).split('from')[0].split(' ')[3][1:-1]

        mod = __import__(missing_mod)
        setattr(mod, missing_attr, _Generic)
    except Exception:
        pass


class BaseMeta:
    translations: dict = {
        str: sqlalchemy.String,
        int: sqlalchemy.Integer,
        float: sqlalchemy.Float,
        bool: sqlalchemy.Boolean,
        dict: sqlalchemy.LargeBinary,
        list: sqlalchemy.LargeBinary,
        tuple: sqlalchemy.LargeBinary
    }
    tables: dict = {}

def PrimaryKey(default=..., ):
    if isinstance(default, type(lambda x: x)):
        return Field(default_factory=default, primary_key=True)
    return Field(default=default, primary_key=True)

def Default(default=...):
    if isinstance(default, type(lambda x: x)):
        return Field(default_factory=default)
    return Field(default=default)


class DataBaseModel(BaseModel):
    __metadata__: BaseMeta = BaseMeta()

    @classmethod
    async def refresh_models(cls):
        """
        convert rows into .dict() & save back to DB, refreshing any changed 
        models
        """
        rows = await cls.all()
        rows_dict = [row.dict() for row in rows]
        rows_model = [cls(**row) for row in rows_dict]
        for row in rows_model:
            await row.update()

    @classmethod
    def setup(cls, database):
        
        if not hasattr(cls.__metadata__, 'metadata'):
            cls.init_set_metadata(database.metadata)
            cls.init_set_database(database)
        if not cls.__name__ in cls.__metadata__.tables:
            cls.generate_sqlalchemy_table()
        
    @classmethod
    def init_set_metadata(cls, metadata):
        """
        Applies an instantiated sqlalchemy.MetaData() instance to __metadata__.metadata
        """
        cls.__metadata__.metadata = metadata
    
    @classmethod
    def init_set_database(cls, database):
        """
        Applies an instantiated easydb.Database() instance to __metadata__.database
        """
        cls.__metadata__.database = database

    @classmethod
    def generate_sqlalchemy_table(cls):
        if not hasattr(cls.__metadata__, 'metadata'):
            raise Exception(f"No connected sqlalchemy.MetaData() instance yet, first run {cls}.init_set_metadata()")
        name = cls.__name__

        cls.__metadata__.tables[name]['table'] = sqlalchemy.Table(
            name,
            cls.__metadata__.metadata,
            *cls.convert_fields_to_columns()
        )
        
    @classmethod
    def convert_fields_to_columns(
        cls, 
        model_fields: list = None, 
        include: list = None,
        alias: dict = None,
        update: bool = False
    ):
        """
        primary key is assumed to be first field, #TODO - add override later
        """
        if not alias:
            alias = {}
        
        if not include:
            include = [f for f in cls.__fields__]

        primary_key = None
        for property, config in cls.schema()['properties'].items():
            if 'primary_key' in config:
                if primary_key:
                    raise Exception(f"Duplicate Primary Key Specified for {cls.__name__}")
                primary_key = property

        if not model_fields:
            model_fields_list = [
                f for _,f in cls.__fields__.items() 
                if f.name in include or f.name in alias
            ]
            model_fields = []
            for field in model_fields_list:
                field_name = field.name
                if field.name in alias:
                    field_name = alias[field.name]
                model_fields.append({'name': field_name, 'type': field.type_, 'required': field.required})

        name = cls.__name__
        primary_key = model_fields[0]['name'] if not primary_key else primary_key
        if not name in cls.__metadata__.tables or update:
            
            cls.__metadata__.tables[name] = {
                'primary_key': primary_key,
                'column_map': {},
                'foreign_keys': {},
            }

        columns = []
        for i, field in enumerate(model_fields):
            if issubclass(field['type'], DataBaseModel):
                # ensure DataBaseModel also exists in Database, even if not already
                # explicity added

                cls.__metadata__.database.add_table(field['type'])

                # create a string or foreign table column to be used to reference 
                # other table
                foreign_table_name = field['type'].__name__
                foreign_primary_key_name = field['type'].__metadata__.tables[foreign_table_name]['primary_key']
                foreign_key_type = field['type'].__metadata__.tables[foreign_table_name]['column_map'][foreign_primary_key_name][1]


                cls.__metadata__.tables[name]['column_map'][field['name']] = (
                    cls.__metadata__.database.get_translated_column_type(foreign_key_type),
                    field['type']
                )

                # store field name in map to quickly determine attribute is tied to 
                # foreign table
                cls.__metadata__.tables[name]['foreign_keys'][field['name']] =  (
                    f'fk_{foreign_table_name}_{foreign_primary_key_name}'.lower()
                )
                foreign_type_config = cls.__metadata__.tables[name]['column_map'][field['name']][0]
                columns.append(
                    sqlalchemy.Column(
                        cls.__metadata__.tables[name]['foreign_keys'][field['name']],
                        foreign_type_config['column_type'](
                            *foreign_type_config['args'],
                            **foreign_type_config['kwargs']
                        )
                    )
                )
                continue

            cls.__metadata__.tables[name]['column_map'][field['name']] = (
                cls.__metadata__.database.get_translated_column_type(field['type']),
                field['type']
            )

            column_type_config = cls.__metadata__.tables[name]['column_map'][field['name']][0]
            columns.append(
                sqlalchemy.Column(
                    field['name'], 
                    column_type_config['column_type'](
                        *column_type_config['args'], 
                        **column_type_config['kwargs']
                    ),
                    primary_key = field['name'] == primary_key
                )
            )
        return columns
    
    @classmethod
    def normalize(cls, results: list):
        """
        ensure results of db querries are dict before parsing
        """
        return [dict(r) for r in results]

    async def serialize(self, data: dict, insert: bool = False, alias=None):
        """
        expects
            `data` - data to be serialized
        """
        if not alias:
            alias = {}

        values = {**data}

        for k, v in data.items():
            name = self.__class__.__name__
            if k in self.__metadata__.tables[name]['foreign_keys']:

                # use the foreign DataBaseModel's primary key / value 
                foreign_type = self.__metadata__.tables[name]['column_map'][k][1]
                foreign_primary_key = foreign_type.__metadata__.tables[foreign_type.__name__]['primary_key']
                foreign_model = foreign_type(**v)
                foreign_primary_key_value = getattr(foreign_model, foreign_primary_key)
                values[f'fk_{foreign_type.__name__}_{foreign_primary_key}'.lower()] = foreign_primary_key_value
                del values[k]
                if insert:
                    exists = await foreign_type.exists(**{foreign_primary_key: foreign_primary_key_value})

                    if not exists:
                        
                        await foreign_model.insert()
                continue

            if self.__metadata__.tables[name]['column_map'][k][0]['column_type'] is sqlalchemy.LargeBinary:
                values[k] = dumps(getattr(self, k))
                continue
            values[k] = v

        return values

    async def save(self):
        primary_key = self.__metadata__.tables[self.__class__.__name__]['primary_key']
        exists = await self.__class__.exists(
            **{primary_key: getattr(self, primary_key)}
        )
        if not exists:
            return await self.insert()
        return await self.update()

    @classmethod
    def where(cls, query, where: dict):
        table = cls.get_table()
        conditions = []
        values = []
        for cond, value in where.items():
            # check if cond is a foreign key, handle pulling foreign references matching query
            if cond in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                foreign_column_name = cls.__metadata__.tables[cls.__name__]['foreign_keys'][cond]
                foreign_primary_key = cls.__metadata__.tables[value.__class__.__name__]['primary_key']
                conditions.append(table.c[foreign_column_name]==getattr(value, foreign_primary_key))
                continue
            if not cond in table.c:
                raise Exception(f"{cond} is not a valid column in {table}")
            query_value = value
            if cls.__metadata__.tables[cls.__name__]['column_map'][cond][0]['column_type'] is sqlalchemy.LargeBinary:
                query_value = dumps(value)
            conditions.append(table.c[cond] == query_value)
            values.append(query_value)
        for condition in conditions:
            query = query.where(condition)
        return query, tuple(values)

    @classmethod
    def get_table(cls):
        if not cls.__name__ in cls.__metadata__.tables:
            cls.generate_sqlalchemy_table()

        return cls.__metadata__.tables[cls.__name__]['table']

    @classmethod
    async def exists(cls,
        **column_values: dict
    ) -> bool:

        table = cls.get_table()
        primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']

        for k in column_values:
            if not k in table.c:
                raise Exception(f"{k} is not a valid column in  {table} ")
        
        
        sel = select([table.c[primary_key]])

        sel, values = cls.where(sel, column_values)

        database = cls.__metadata__.database

        results = await database.fetch(sel, cls.__name__, values)

        if results:
            return True
        return False
        
    @classmethod
    async def select(cls,
        *selection,
        where: Optional[Union[dict, None]] = None,
        alias: Optional[dict] = None,
    ) -> List[dict]:
        if alias is None:
            alias = {}

        table = cls.get_table()

        if selection[0] == '*':
            selection = [k for k in cls.__metadata__.tables[cls.__name__]['column_map']]

        #
        items_to_select = []
        for _sel in selection:
            column_name = _sel

            if column_name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                fk_name = cls.__metadata__.tables[cls.__name__]['foreign_keys'][column_name]
                items_to_select.append(table.c[fk_name])
                continue

            if column_name not in table.c:
                raise Exception(f"{column_name} is not a valid column in {table} - columns: {[k for k in table.c]}")
            items_to_select.append(table.c[column_name])
        #
        sel = select(items_to_select)
        #
        values = None
        if where:
            sel, values = cls.where(sel, where)

        decoded_results = []

        database = cls.__metadata__.database
        
        results = await database.fetch(sel, cls.__name__, values)

        for result in cls.normalize(results):
            values = {}
            for sel, value in zip(selection, result):
                if sel in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                    foreign_type = cls.__metadata__.tables[cls.__name__]['column_map'][sel][1]
                    foreign_primary_key = foreign_type.__metadata__.tables[foreign_type.__name__]['primary_key']
                    values[sel] = await foreign_type.select(
                        '*', 
                        where={foreign_primary_key: result[value]},
                    )
                    values[sel] = values[sel][0] if values[sel] else None
                    continue 

                if cls.__metadata__.tables[cls.__name__]['column_map'][sel][0]['column_type'] == sqlalchemy.LargeBinary:
                    try:
                        values[sel] = loads(result[value])
                    except AttributeError as e:
                        resolve_missing_attribute(
                            str(repr(e))
                        )
                        values[sel] = loads(result[value])
                    #breakpoint()
                    continue

                values[sel] = result[value]

                if sel in alias:
                    values[alias[sel]] = values.pop(sel)
            
            if values:
                decoded_results.append(
                    cls(**values)
                )

        return decoded_results
    @classmethod
    async def all(cls):
        return await cls.select('*')

    @classmethod
    async def filter(cls, **column_filters):
        table = cls.get_table()
        columns = [k for k in cls.__fields__]
        if not column_filters:
            raise Exception(f"{cls.__name__}.filter() expects keyword arguments for columns: {columns}")
        sel = table.select()

        sel, values = cls.where(sel, column_filters)
        database = cls.__metadata__.database

        results = await database.fetch(sel, cls.__name__, values)
        rows = []
        for result in cls.normalize(results):
            values = {}
            for sel, value in zip(columns, result):
                if sel in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                    foreign_type = cls.__metadata__.tables[cls.__name__]['column_map'][sel][1]
                    foreign_primary_key = foreign_type.__metadata__.tables[foreign_type.__name__]['primary_key']
                    values[sel] = await foreign_type.select(
                        '*', where={foreign_primary_key: result[value]}
                    )
                    values[sel] =  values[sel][0]
                    continue 

                if cls.__metadata__.tables[cls.__name__]['column_map'][sel][0]['column_type'] == sqlalchemy.LargeBinary:
                    try:
                        values[sel] = loads(result[value])
                    except AttributeError as e:
                        resolve_missing_attribute(
                            str(repr(e))
                        )
                        values[sel] = loads(result[value])
                    continue
                values[sel] = result[value]
            try:
                rows.append(
                    cls(**values)
                )
            except Exception as e:
                pass
        return rows

    async def update(self,
        where: dict = None,
        **to_update
    ):
        self.__class__.get_table()

        table_name = self.__class__.__name__
        primary_key = self.__metadata__.tables[table_name]['primary_key']

        if not to_update:
            to_update = self.dict()
            del to_update[primary_key]

        where_ = dict(*where if where else {})
        if not where_:
            where_ = {primary_key: getattr(self, primary_key)}

        table = self.__metadata__.tables[self.__class__.__name__]['table']
        for column in to_update.copy():
            if column in self.__metadata__.tables[table_name]['foreign_keys']:
                del to_update[column] # = foreign_pk_value
                continue
            if column not in table.c:
                raise Exception(f"{column} is not a valid column in {table}")
        
        query, _ = self.where(table.update(), where_)
        query = query.values(**to_update)
        
        to_update = await self.serialize(to_update)

        await self.__metadata__.database.execute(query, to_update)

            
    async def delete(self):
        table_name = self.__class__.__name__
        table = self.__metadata__.tables[table_name]['table']
        primary_key = self.__metadata__.tables[table_name]['primary_key']

        query, _ = self.where(table.delete(table), {primary_key: getattr(self, primary_key)})

        return await self.__metadata__.database.execute(query, None)
    
    async def insert(self):
        table = self.__class__.get_table()
        
        values = await self.serialize(self.dict(), insert=True)
        query = table.insert()

        return await self.__metadata__.database.execute(
            query, values
        )

    @classmethod
    async def get(cls, **p_key):
        for k in p_key:
            primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']
            if not k == cls.__metadata__.tables[cls.__name__]['primary_key']:
                raise f"Expected primary key {primary_key}=<value>"
        result = await cls.select('*', where={**p_key})
        return result[0] if result else None

    @classmethod
    async def create(cls, **column_args):
        new_obj = cls(**column_args)
        await new_obj.insert()
        return new_obj


class TableMeta(DataBaseModel):
    table_name: str = PrimaryKey()
    model: dict
    columns: list

class DatabaseInit(DataBaseModel):
    database_url: str = PrimaryKey()
    status: Optional[str]
    reservation: Optional[str]

