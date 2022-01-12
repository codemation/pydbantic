import asyncio
from pydantic.fields import PrivateAttr
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy.sql.expression import delete
from sqlalchemy.util.langhelpers import NoneType
from pydantic import BaseModel, Field, ValidationError, PrivateAttr
import typing
from typing import Awaitable, Callable, Coroutine, Optional, TypeVar, Union, List, Any, Tuple, ForwardRef
import sqlalchemy
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import relationship, Session, Query
from pickle import dumps, loads

class _Generic(BaseModel):
    pass

def get_model_getter(model, primary_key, primary_key_value):
    return lambda : model.get(**{primary_key: primary_key_value})

class RelationshipRef(BaseModel):
    primary_key: str
    value: Any
    _method_: Callable = PrivateAttr()
    _default_: Callable = PrivateAttr()
    _model_: Callable = PrivateAttr()
    def __init__(self, model, primary_key, value, default=None):

        super().__init__(
            primary_key=primary_key, 
            value=value
        )
        self._method_ = get_model_getter(model, primary_key, value)
        self._default_ = default
        self._model_ = model

    def __repr__(self):
         return f"{self._model_.__name__}Ref({self.primary_key}={self.value})"

    def __call__(self) -> Coroutine:
        return self._method_()

    def _get_value(self):
        return self._default_

    def dict(self, *args, **kwargs):
        return {f"{self.primary_key}": self.value}
        

def get_model_getter(model, primary_key, primary_key_value):
    return lambda : model.get(**{primary_key: primary_key_value})

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

def deserialize(data):
    try:
        return loads(data)
    except AttributeError as e:
        resolve_missing_attribute(repr(e))
        return loads(data)

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

class DataBaseModelCondition:
    def __init__(
        self, 
        description: str,
        condition: sqlalchemy.sql.elements.BinaryExpression,
        values
    ): 
        self.description = description
        self.condition = condition
        self.values = values
    def __repr__(self):
        return self.description
    def str(self):
        return self.description

class DataBaseModelAttribute:
    def __init__(
        self, 
        name: str,
        column: sqlalchemy.sql.schema.Column,
        table,
        serialized: bool = False,
        is_array: bool = False,
        foreign_model = None
    ):
        self.name = name
        self.column = column
        self.table = table
        self.serialized = serialized
        self.is_array = is_array

        self.foreign_model = foreign_model

    def process_value(self, value):
        if value.__class__ is self.table['model']:
            primary_key = self.table['model'].__metadata__.tables[self.foreign_model]['primary_key']
            return getattr(value, primary_key)

        if self.serialized:
            return dumps(value)

        return value

    def __lt__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} < {values}",
            self.column < self.process_value(value),
            (values,)
        )

    def __le__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} <= {values}",
            self.column <= self.process_value(value),
            (values,)
        )

    def __gt__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} > {values}",
            self.column > self.process_value(value),
            (values,)
        )

    def __ge__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} >= {values}",
            self.column >= self.process_value(value),
            (values,)
        )

    def __eq__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} == {values}",
            self.column == self.process_value(value),
            (values,)
        )

    def matches(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} in {choices}",
            self.column.in_(choices),
            tuple(choices)
        )
    def not_matches(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} not in {choices}",
            self.column.not_in(choices),
            tuple(choices)
        )

DataBaseModel = TypeVar('DataBaseModel')

class DataBaseModel(BaseModel):
    __metadata__: BaseMeta = BaseMeta()
    class Config:
       arbitrary_types_allowed = True
        
    @classmethod
    def check_if_subtype(cls, field):

        database_model = None

        if isinstance(field['type'], typing._GenericAlias):
            for sub in field['type'].__args__:
                
                if isinstance(sub, ForwardRef):
                    database_model = sub.__forward_value__
        
                elif issubclass(sub, DataBaseModel):
                    if database_model:
                        raise Exception(f"Cannot Specify two DataBaseModels in Union[] for {field['name']}")
                    database_model = sub
        elif issubclass(field['type'], DataBaseModel):
            return field['type']
        return database_model

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
        cls.update_backward_refs()
        
        if not hasattr(cls.__metadata__, 'metadata'):
            cls.init_set_metadata(database.metadata)
            cls.init_set_database(database)
        if cls.__name__ not in cls.__metadata__.tables:
            cls.generate_sqlalchemy_table()

    @classmethod
    def init_set_metadata(cls, metadata) -> NoneType:
        """
        Applies an instantiated sqlalchemy.MetaData() instance to __metadata__.metadata
        """
        cls.__metadata__.metadata = metadata
    
    @classmethod
    def init_set_database(cls, database) -> NoneType:
        """
        Applies an instantiated easydb.Database() instance to __metadata__.database
        """
        cls.__metadata__.database = database

    @classmethod
    def generate_sqlalchemy_table(cls) -> NoneType:
        if not hasattr(cls.__metadata__, 'metadata'):
            raise Exception(f"No connected sqlalchemy.MetaData() instance yet, first run {cls}.init_set_metadata()")
        name = cls.__name__

        columns, link_tables = cls.convert_fields_to_columns()

        cls.__metadata__.tables[name]['table'] = sqlalchemy.Table(
            name,
            cls.__metadata__.metadata,
            *columns
        )

        for data_base_model, field_name in link_tables:
            cls.generate_relationship_table(data_base_model, field_name)
        

        for rel, table in cls.__metadata__.tables[cls.__name__]['relationships'].items():
            setattr(
                cls.__metadata__.tables[name]['table'],
                table[1],
                relationship(
                    rel,
                    secondary=table[0],
                    backref=table[2]
                )
            )

    @classmethod
    def generate_relationship_table(cls, related_model: DataBaseModel, field_ref: str) -> NoneType:
        """
        creates a 2 column table that enables a link between
        cls primary_key & related_model primary key 
        """
        
        if related_model.__name__ in cls.__metadata__.tables[cls.__name__]['relationships']:
            return
        
        related_model_ref = None
        for f_name, field in related_model.__fields__.items():
            data_base_model = related_model.check_if_subtype({'name': f_name, 'type': field.type_})
            if data_base_model is cls:
                related_model_ref = f_name


        relationship_table = sqlalchemy.Table(
            f"{cls.__name__}_to_{related_model.__name__}",
            cls.__metadata__.metadata,
            sqlalchemy.Column(
                f"{cls.__name__}_{cls.__metadata__.tables[cls.__name__]['primary_key']}",
                sqlalchemy.ForeignKey(
                    f"{cls.__name__}.{cls.__metadata__.tables[cls.__name__]['primary_key']}",
                    ondelete="CASCADE"
                ),
                primary_key=True
            ),
            sqlalchemy.Column(
                f"{related_model.__name__}_{cls.__metadata__.tables[related_model.__name__]['primary_key']}",
                sqlalchemy.ForeignKey(
                    f"{related_model.__name__}.{cls.__metadata__.tables[related_model.__name__]['primary_key']}",
                    ondelete="CASCADE"
                ),
                primary_key=True
            )
        )
        
        cls.__metadata__.tables[cls.__name__]['relationships'][related_model.__name__] = relationship_table, field_ref, related_model_ref
        cls.__metadata__.tables[related_model.__name__]['relationships'][cls.__name__] = relationship_table, related_model_ref, field_ref

    @classmethod 
    def generate_model_attributes(cls) -> NoneType:
        name = cls.__name__
        for c, column in cls.__metadata__.tables[name]['column_map'].items():

            foreign_model = None
            if c in cls.__metadata__.tables[name]['foreign_keys']:
                foreign_model = cls.__metadata__.tables[name]['foreign_keys'][c]
                table = cls.__metadata__.tables[foreign_model.__name__]
                foreign_pk = table['primary_key']
                
                table_column = table['table'].c[foreign_pk]
            else:
                table =  cls.__metadata__.tables[name]
                table_column = table['table'].c[c]

            setattr(
                cls, 
                c, 
                DataBaseModelAttribute(
                    c,
                    table_column,
                    table,
                    column[2],
                    column[3],
                    foreign_model=foreign_model.__name__ if foreign_model else None
                )
            )
    @classmethod
    def update_backward_refs(cls):
        """
        force update forward refs of all backward referncing DataBaseModels
        """
        for _, model_field in cls.__fields__.items():
            data_base_model = cls.check_if_subtype({'type': model_field.type_})
            if data_base_model:
                data_base_model.update_forward_refs()
                
        
    @classmethod
    def convert_fields_to_columns(
        cls, 
        model_fields: list = None, 
        include: list = None,
        alias: dict = None,
        update: bool = False
    ) -> Tuple[List[sqlalchemy.Column], List[Awaitable]]:
        """
        converts model fields to sqlalchemy columns, saturates
        model.__metadata__  with model properties and relationship reference,
        triggers foreign
        """
        if not alias:
            alias = {}
        if not include:
            include = [f for f in cls.__fields__]

        primary_key = None
        array_fields = set()

        field_properties = {}

        try:
            model_schema = cls.schema()
        except TypeError:
            raise Exception(f"{cls.__name__} was referenced by DataBaseModel(s) not added in Database setup tables=[..,]")

        if 'title' in model_schema and model_schema['title'] == cls.__name__:
            field_properties = model_schema['properties']
        elif 'definitions' in model_schema and cls.__name__ in model_schema['definitions']:
            field_properties = model_schema['definitions'][cls.__name__]['properties']
        else:
            field_properties = model_schema['properties']

        for field_property, config in field_properties.items():
            
            if 'primary_key' in config:
                if primary_key:
                    raise Exception(f"Duplicate Primary Key Specified for {cls.__name__}")
                primary_key = field_property
            if 'type' in config and config['type'] == 'array' and not primary_key == field_property:
                array_fields.add(field_property)

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
        if name not in cls.__metadata__.tables or update:

            cls.__metadata__.tables[name] = {
                'primary_key': primary_key,
                'column_map': {},
                'foreign_keys': {},
                'relationships': {} if name not in cls.__metadata__.tables else cls.__metadata__.tables[name]['relationships']
            }

        columns = []
        link_tables = []
        for i, field in enumerate(model_fields):
            
            data_base_model = cls.check_if_subtype(field)
            if data_base_model:
                # ensure DataBaseModel also exists in Database, even if not already
                # explicity added
                data_base_model.update_forward_refs()
                cls.__metadata__.database.add_table(data_base_model)
                
                # create a string or foreign table column to be used to reference 
                # other table
                if not update:
                    link_tables.append((data_base_model, field['name']))

                foreign_table_name = data_base_model.__name__
                foreign_primary_key_name = data_base_model.__metadata__.tables[foreign_table_name]['primary_key']
                foreign_key_type = data_base_model.__metadata__.tables[foreign_table_name]['column_map'][foreign_primary_key_name][1]

                serialize = False

                cls.__metadata__.tables[name]['column_map'][field['name']] = (
                    cls.__metadata__.database.get_translated_column_type(foreign_key_type if not serialize else list)[0],
                    data_base_model,
                    serialize,
                    field['name'] in array_fields
                )

                # store field name in map to quickly determine attribute is tied to 
                # foreign table
                cls.__metadata__.tables[name]['foreign_keys'][field['name']] = data_base_model

                continue

            # get sqlalchemy column type based on field type & if primary_key
            # as well as determine if data should be serialized & de-serialized
            sqlalchemy_model, serialize = cls.__metadata__.database.get_translated_column_type(
                field['type'],
                primary_key = field['name'] == primary_key
            )
            cls.__metadata__.tables[name]['column_map'][field['name']] = (
                sqlalchemy_model,
                field['type'],
                serialize,
                False, #field['name'] in array_fields
            )
            cls.__metadata__.tables[name]['model'] = cls

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

        return columns, link_tables

    async def serialize(
        self: DataBaseModel, 
        data: dict, 
        insert: bool = False,
        update: bool = False,
        alias=None
    ) -> Tuple[dict, List[Awaitable]]:
        """
        expects
            `data` - data to be serialized
        """
        database = self.__metadata__.database
        name = self.__class__.__name__
        if not alias:
            alias = {}

        values = {**data}
        primary_key = self.__metadata__.tables[name]['primary_key']
        
        link_chain = [] 

        for k, v in data.items():
            
            serialize = self.__metadata__.tables[name]['column_map'][k][2]
            skip = False
            if k in self.__metadata__.tables[name]['foreign_keys']:

                # use the foreign DataBaseModel's primary key / value 
                foreign_type = self.__metadata__.tables[name]['column_map'][k][1]
                foreign_name = foreign_type.__name__
                foreign_primary_key = foreign_type.__metadata__.tables[foreign_name]['primary_key']

                link_table = self.__metadata__.tables[name]['relationships'][foreign_name][0]
                
                foreign_values = [v] if not isinstance(v, list) else v
                fk_values = []
                local_value = getattr(self, primary_key)

                foreign_values = getattr(self, k)
                if not isinstance(foreign_values, list):
                    foreign_values = [foreign_values]

                for v in foreign_values:

                    if v is None:
                        continue
                        
                    if isinstance(v, foreign_type):
                        v = v.dict()

                    if isinstance(v, Callable):
                        v = await v()
                        v = v.dict()

                    if isinstance(v, dict):
                        foreign_primary_key_value = v[foreign_primary_key]
                    else:
                        foreign_primary_key_value = v

                    fk_values.append(foreign_primary_key_value)
                    
                    serialize_local = self.__metadata__.tables[name]['column_map'][primary_key][2]
                    serialize_foreign = self.__metadata__.tables[foreign_name]['column_map'][foreign_primary_key][2]

                    
                    if serialize_local:
                        local_value = dumps(local_value)
                    
                    if serialize_foreign:
                        foreign_primary_key_value = dumps(foreign_primary_key_value)

                    link_values = {
                        f'{name}_{primary_key}': local_value, 
                        f'{foreign_name}_{foreign_primary_key}': foreign_primary_key_value
                    }

                    link_insert = database.execute(link_table.insert(), link_values)
                    link_chain.append(link_insert)

                    if insert:
                        exists = await foreign_type.filter(
                            **{
                                foreign_primary_key: foreign_primary_key_value,
                                'count_rows': True,
                                'join': False,
                                },
                        )
                        if exists == 0:
                            foreign_model = foreign_type(**v)
                            link_chain.extend(await foreign_model.save(return_links=True))

                del values[k]

                # delete links between items not in fk_values

                if update and fk_values:
                    link_chain.append(
                        database.execute(
                            delete(link_table).where(
                                and_(
                                    link_table.c[f'{name}_{primary_key}']==local_value,
                                    link_table.c[f'{foreign_type.__name__}_{foreign_primary_key}'].not_in(fk_values)
                                )
                            )
                        )
                    )
                
                # remove existing references, if any, to match removed
                if update and not fk_values:
                    link_chain.append(
                        database.execute(
                            delete(link_table).where(
                                link_table.c[f'{name}_{primary_key}']==local_value
                            )
                        )
                    )
                continue
            
            serialize = self.__metadata__.tables[name]['column_map'][k][2]

            if serialize:
                values[k] = dumps(getattr(self, k))

                continue
            values[k] = v

        return values, link_chain

    async def save(self: DataBaseModel, return_links: bool = False) -> NoneType:
        primary_key = self.__metadata__.tables[self.__class__.__name__]['primary_key']
        count = await self.__class__.filter(
            **{primary_key: getattr(self, primary_key)},
            count_rows=True
        )
        if count == 0:
            return await self.insert(return_links=return_links)
        print(f"{self.__class__.__name__} - updating")
        await self.update()

        if return_links:
            return []
    
    @classmethod
    def where(
        cls, query: Query, 
        where: dict, 
        *conditions: List[DataBaseModelCondition]
    ) -> Tuple[Query, tuple]:

        table = cls.get_table()
        conditions = list(conditions)
        values = []

        # convert keyword arguments into DataBaseModelConditions
        for cond, value in where.items():
            is_serialized = cls.__metadata__.tables[cls.__name__]['column_map'][cond][2]
            if not isinstance(cond, DataBaseModelAttribute) and  hasattr(cls, cond):
                cond = getattr(cls, cond)
                conditions.append(cond == value)

            else:
                raise Exception(f"{cond} is not a valid column in {table}")
            
            
            query_value = value
            if cond.serialized:
                query_value = dumps(value)
        
        for condition in conditions:               
            try:
                query = query.where(condition.condition) 
            except Exception:
                query = query.where(condition.condition.condition) 
            if isinstance(condition.values, tuple):
                values.extend(condition.values)

        return query, tuple(values)

    @classmethod
    def get_table(cls)-> sqlalchemy.Table:
        if cls.__name__ not in cls.__metadata__.tables:
            cls.generate_sqlalchemy_table()

        return cls.__metadata__.tables[cls.__name__]['table']

    @classmethod
    def OR(
        cls, 
        *conditions: List[DataBaseModelCondition], 
        **filters: dict
    ) -> DataBaseModelCondition:
        """
        combines input `conditions` and keyword argument filters
        into an OR separated conditional tied with associated values
        in a new `DataBaseModelCondition` 
        """
        table = cls.get_table()
        conditions = list(conditions)

        for cond, value in filters.items():
            if not isinstance(cond, DataBaseModelAttribute) and  hasattr(cls, cond):
                cond = getattr(cls, cond)
            else:
                raise Exception(f"{cond} is not a valid column in {table}")

            conditions.append(cond == value)
        values = []
        for cond in conditions:
            if isinstance(cond.values, tuple):
                values.extend(cond.values)

        return DataBaseModelCondition(
            " OR ".join([str(cond) for cond in conditions]),
            or_(*[cond.condition for cond in conditions]),
            values=tuple(values)
        )
        

    @classmethod
    def gt(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        
        return DataBaseModelCondition(
            f"{column} > {value}",
            table.c[column] > value,
            value
        )

    @classmethod
    def gte(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} >= {value}",
            table.c[column] >= value,
            value
        )
        

    @classmethod
    def lt(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} < {value}",
            table.c[column] < value,
            value
        )

    @classmethod
    def lte(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} <= {value}",
            table.c[column] >= value,
            value
        )

    @classmethod
    def contains(cls, column: str, value: Any) -> DataBaseModelCondition:
        """
        returns a `DataBaseModelCondition` searching for `value` in a
        `column`
        """
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")

        return DataBaseModelCondition(
            f"{value} in {column}",
            table.c[column].contains(value),
            value
        )

    @classmethod
    def desc(cls, column) -> UnaryExpression:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return table.c[column].desc()

    @classmethod
    def asc(cls, column) -> UnaryExpression:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return table.c[column].asc()
    
    @classmethod
    async def exists(cls,
        **column_values: dict
    ) -> bool:

        table = cls.get_table()
        primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']

        for k in column_values:
            if k not in table.c:
                raise Exception(f"{k} is not a valid column in  {table} ")


        sel = select([table.c[primary_key]])

        sel, values = cls.where(sel, column_values)

        database = cls.__metadata__.database

        results = await database.fetch(sel, cls.__name__, values)

        return bool(results)

    @classmethod
    def deep_join(
        cls,
        model_ref,
        model_ref_primary_key: str,
        column_ref: str,
        session_query: Query,
        tables_to_select: list,
        models_selected: set,
        root_model: DataBaseModel = None,
    ) -> Tuple[Query, List[Tuple[sqlalchemy.Table, DataBaseModel, str, DataBaseModel]]]:
        """
        Traverse a DataBaseModel relationship and add subsequent 
        .join() clauses to active session_query, and append foreign tables
        to list
        """
        if cls.__name__ in models_selected:
            return session_query, tables_to_select

        foreign_models = []
        for column_name in cls.__metadata__.tables[cls.__name__]['column_map']:
            if column_name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
            
                # foreign model
                foreign_model = cls.__metadata__.tables[cls.__name__]['column_map'][column_name][1]
                if foreign_model.__name__ in models_selected:
                    # skipping model, as is already selected in current query
                    continue
                foreign_models.append((foreign_model, column_name))
                

        ref_table = model_ref.get_table()
        table = cls.get_table()
        primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']
        
        link_table = cls.__metadata__.tables[model_ref.__name__]['relationships'][cls.__name__][0]
        
        session_query = session_query.outerjoin(
            link_table, 
            getattr(ref_table.c, model_ref_primary_key) == getattr(link_table.c, f"{model_ref.__name__}_{model_ref_primary_key}")
        ).outerjoin(
            table,
            getattr(
                link_table.c, 
                f"{cls.__name__}_{primary_key}"
            ) == getattr(
                table.c, 
                primary_key
            )
        )
        if not cls is root_model:
            session_query = session_query.add_columns(*[c for c in table.c])
            tables_to_select.append((table, cls, column_ref, model_ref))
        models_selected.add(cls.__name__)

        for foreign_model, column_ref in foreign_models:
            if foreign_model.__name__ in models_selected:
                continue
            session_query, tables_to_select = foreign_model.deep_join(
                cls, primary_key, column_ref,
                session_query, tables_to_select, models_selected
            )
        
        return session_query, tables_to_select

    @classmethod
    async def select(cls,
        *selection: str,
        where: Optional[Union[dict, None]] = None,
        alias: Optional[dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = 0,
        order_by = None,
        primary_key: str = None,
        backward_refs: bool = True,
    ) -> List[Optional[DataBaseModel]]:
        if alias is None:
            alias = {}

        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)
        

        if selection[0] == '*':
            selection = [k for k in cls.__metadata__.tables[cls.__name__]['column_map']]

        tables_to_select = []
        models_selected = set((cls.__name__,))

        primary_key = cls.__metadata__.tables[cls.__name__]['primary_key'] if not primary_key else primary_key
        
        sel = session.query(*[c for c in table.c if c.name in selection])

        for _sel in selection:
            column_name = _sel

            if column_name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                foreign_model = cls.__metadata__.tables[cls.__name__]['column_map'][column_name][1]
                sel, tables_to_select = foreign_model.deep_join(
                    cls, primary_key, column_name,
                    sel, tables_to_select, models_selected,
                    root_model = cls
                )

                continue

            if column_name not in table.c:
                raise Exception(f"{column_name} is not a valid column in {table} - columns: {[k for k in table.c]}")
        
        values = None
        if where:
            sel, values = cls.where(sel, where)

        sel, values = cls.check_limit_offset(sel, values, limit, offset)

        if order_by is not None:
            sel = sel.order_by(order_by)

        results = await database.fetch(sel.statement, cls.__name__, values)
        
        # build results_map
        results_map = {}
        last_ind = -1
        for i, c in enumerate(table.c):
            if not c.name in selection:
                continue

            col_name = c.name if not c.name in alias else alias[c.name]
            last_ind = last_ind + 1
            if c.name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                continue
            if not cls in results_map:
                results_map[cls] = {}
            results_map[cls][col_name] = last_ind

        for f_table, f_model, _, _ in tables_to_select:
            for i, c in enumerate(f_table.c):
                last_ind = last_ind + 1
                if c.name in cls.__metadata__.tables[f_model.__name__]['foreign_keys']:
                    continue
                if not f_model in results_map:
                    results_map[f_model] = {}
                results_map[f_model][c.name] = last_ind

        tables_to_select.reverse()

        decoded_results = {}
        row_results = {}

        for result in results:
            if isinstance(result, dict):
                result = tuple(result.values())

            result_key = result[results_map[cls][primary_key]]


            if not result_key in decoded_results:
                decoded_results[result_key] = {}
                row_results = {}

                for k, result_ind in results_map[cls].items():
                    serialized = cls.__metadata__.tables[cls.__name__]['column_map'][k][2]
                    is_array = cls.__metadata__.tables[cls.__name__]['column_map'][k][3]
                    expected_type = cls.__metadata__.tables[cls.__name__]['column_map'][k][1]
                    row_result = result[result_ind]
                    if serialized:
                        row_result = deserialize(row_result)
                            
                        if expected_type in {set, list, tuple}:
                            row_result = expected_type(row_result)

                    if is_array:
                        if not k in decoded_results[result_key]:
                            decoded_results[result_key][k] = []
                        
                        decoded_results[result_key][k].append(row_result)
                    else:
                        decoded_results[result_key][k] = row_result

            for f_table, f_model, column_name, parent in tables_to_select:
                f_p_key = cls.__metadata__.tables[f_model.__name__]['primary_key']
                f_p_key_value = result[results_map[f_model][f_p_key]]
                new_data = False
                if not row_results.get(f_p_key) == f_p_key_value:
                    new_data = True
                    for k, result_ind in results_map[f_model].items():
                        
                        serialized = cls.__metadata__.tables[f_model.__name__]['column_map'][k][2]
                        is_array = cls.__metadata__.tables[f_model.__name__]['column_map'][k][3]
                        row_result = result[result_ind]

                        if serialized:
                            row_result = deserialize(row_result) if not row_result is None else None
                            row_results[k] = row_result
                                
                        elif is_array:
                            if not k in row_results and not k == f_p_key:
                                row_results[k] = []
                            if row_result:
                                row_results[k].append(row_result)
                        else:
                            row_results[k] = row_result

                # build model with collected results
                is_array_in_parent = parent.__metadata__.tables[parent.__name__]['column_map'][column_name][3]

                parent_p_key = parent.__metadata__.tables[parent.__name__]['primary_key']
                parent_p_key_val = result[results_map[parent][parent_p_key]]

                try:
                    model_ins = f_model(**row_results)

                    for k, foreign_model in cls.__metadata__.tables[f_model.__name__]['foreign_keys'].items():
                        if not parent.__name__ == foreign_model.__name__ or not backward_refs:
                            continue
                        foreign_ref = getattr(model_ins, k)
                        
                        if foreign_ref is None:
                            setattr(model_ins, k, RelationshipRef(parent, parent_p_key, parent_p_key_val, default=foreign_ref))
                        elif foreign_ref == []:
                            setattr(model_ins, k, [RelationshipRef(parent, parent_p_key, parent_p_key_val, default=foreign_ref)])

                except ValidationError:
                    model_ins = None
                        
                if is_array_in_parent:
                    
                    if not column_name in row_results:
                        row_results[column_name] = []
                    if not column_name in decoded_results[result_key]:
                        decoded_results[result_key][column_name] = []
                    if model_ins and new_data:
                        decoded_results[result_key][column_name].append(model_ins)
                        row_results[column_name].append(model_ins)
                    elif model_ins and row_results[column_name]:
                        row_results[column_name][-1] = model_ins
                        decoded_results[result_key][column_name][-1] = model_ins
                    elif model_ins:
                        row_results[column_name].append(model_ins)
                        decoded_results[result_key][column_name].append(model_ins)
                else:
                    row_results[column_name] = model_ins
                    decoded_results[result_key][column_name] = row_results[column_name]

        parsed_results = [
            cls(**decoded_results[pk]) for pk in decoded_results

        ]

        return parsed_results

    @classmethod
    def check_limit_offset(
        cls, 
        query: Query, 
        values: List[Any], 
        limit: int, 
        offset: int
    ) -> Tuple[Query, list]:
        values = list(values) if values else []

        if limit:
            query = query.limit(limit)

        if offset:
            query = query.offset(offset)
        
        if not values:
            values = [limit, offset]
        elif values and (limit or offset):
            values.extend([limit, offset])

        return query, values

    @classmethod
    async def all(
        cls, 
        limit: int = None, 
        offset: int = 0,
        order_by = None,
        backward_refs: bool = True
    ) -> List[Optional[DataBaseModel]]:
        parameters = {}
        if limit:
            parameters['limit'] = limit
        if offset:
            parameters['offset'] = offset
        if order_by is not None:
            parameters['order_by'] = order_by

        return await cls.select('*', **parameters, backward_refs=backward_refs)

    @classmethod
    async def count(cls) -> int:
        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)
        sel = session.query(func.count()).select_from(table)
        results = await database.fetch(sel.statement, cls.__name__)
        return results[0][0] if results else 0

    @classmethod
    async def filter(
        cls, 
        *conditions: List[DataBaseModelCondition], 
        limit: int = None, 
        offset: int = 0,
        order_by = None, 
        count_rows: bool = False,
        join: bool = True,
        backward_refs: bool = True,
        **column_filters: dict
    ) -> List[Optional[DataBaseModel]]:
        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)

        columns = [k for k in cls.__fields__]
        if not column_filters and not conditions:
            raise Exception(f"{cls.__name__}.filter() expects keyword arguments for columns: {columns} or conditions")


        selection = [k for k in cls.__metadata__.tables[cls.__name__]['column_map']]
        
        tables_to_select = []
        models_selected = set((cls.__name__,))

        primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']
        sel = session.query(table)


        for _sel in selection:
            column_name = _sel
            if column_name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                foreign_model = cls.__metadata__.tables[cls.__name__]['column_map'][column_name][1]
                if not join:
                    continue
                sel, tables_to_select = foreign_model.deep_join(
                    cls, primary_key, column_name,
                    sel, tables_to_select, models_selected
                )
                continue

        sel, values = cls.where(sel, column_filters, *conditions)

        sel, values = cls.check_limit_offset(sel.statement, values, limit, offset)
        
        if count_rows:
            row_count = await database.fetch(sel.with_only_columns(func.count()), cls.__name__)
            if row_count:
                if isinstance(row_count[0], dict):
                    return [v for _, v in row_count[0].items()][0]
                return row_count[0][0]
            return 0

        if not order_by is None:
            sel = sel.order_by(order_by)

        results = await database.fetch(sel, cls.__name__, tuple(values))

        results_map = {}
        last_ind = -1
        for i, c in enumerate(table.c):
            last_ind = last_ind + 1
            if c.name in cls.__metadata__.tables[cls.__name__]['foreign_keys']:
                continue
            if not cls in results_map:
                results_map[cls] = {}
            results_map[cls][c.name] = last_ind

        for f_table, f_model, _, _ in tables_to_select:
            for i, c in enumerate(f_table.c):
                last_ind = last_ind + 1
                if c.name in cls.__metadata__.tables[f_model.__name__]['foreign_keys']:
                    continue
                if not f_model in results_map:
                    results_map[f_model] = {}
                results_map[f_model][c.name] = last_ind

        tables_to_select.reverse()
        decoded_results = {}
        row_results = {}

        for result in results:
            if isinstance(result, dict):
                result = tuple(result.values())

            result_key = result[results_map[cls][primary_key]]


            if not result_key in decoded_results:
                decoded_results[result_key] = {}
                row_results = {}

                for k, result_ind in results_map[cls].items():
                    serialized = cls.__metadata__.tables[cls.__name__]['column_map'][k][2]
                    is_array = cls.__metadata__.tables[cls.__name__]['column_map'][k][3]
                    row_result = result[result_ind]
                    if serialized:
                        row_result = deserialize(row_result)
                        row_results[k] = row_result
                        decoded_results[result_key][k] = row_result

                    elif is_array:
                        if not k in decoded_results[result_key]:
                            decoded_results[result_key][k] = []
                        
                        decoded_results[result_key][k].append(row_result)
                    else:
                        decoded_results[result_key][k] = row_result

            for f_table, f_model, column_name, parent in tables_to_select:
                f_p_key = cls.__metadata__.tables[f_model.__name__]['primary_key']
                f_p_key_value = result[results_map[f_model][f_p_key]]
                new_data = False
                if not row_results.get(f_p_key) == f_p_key_value:
                    new_data = True
                    for k, result_ind in results_map[f_model].items():
                        
                        serialized = cls.__metadata__.tables[f_model.__name__]['column_map'][k][2]
                        is_array = cls.__metadata__.tables[f_model.__name__]['column_map'][k][3]
                        row_result = result[result_ind]

                        if serialized:
                            row_result = deserialize(row_result) if not row_result is None else None

                            if isinstance(row_result, list) and is_array:
                                row_results[k] = row_result
                                
                        elif is_array:
                            if not k in row_results and not k == f_p_key:
                                row_results[k] = []
                            if row_result:
                                row_results[k].append(row_result)
                        else:
                            row_results[k] = row_result

                # build model with collected results
                is_array_in_parent = parent.__metadata__.tables[parent.__name__]['column_map'][column_name][3]

                parent_p_key = parent.__metadata__.tables[parent.__name__]['primary_key']
                parent_p_key_val = result[results_map[parent][parent_p_key]]

                try:
                    model_ins = f_model(**row_results)
                    
                    for k, foreign_model in cls.__metadata__.tables[f_model.__name__]['foreign_keys'].items():
                        if not parent.__name__ == foreign_model.__name__ or not backward_refs:
                            continue
                        foreign_ref = getattr(model_ins, k)
                        
                        if foreign_ref is None:
                            setattr(model_ins, k, RelationshipRef(parent, parent_p_key, parent_p_key_val, default=foreign_ref))
                        elif foreign_ref == []:
                            setattr(model_ins, k, [RelationshipRef(parent, parent_p_key, parent_p_key_val, default=foreign_ref)])

                except ValidationError:
                    model_ins = None
                        
                if is_array_in_parent:
                    if not column_name in row_results:
                        row_results[column_name] = []
                    if not column_name in decoded_results[result_key]:
                        decoded_results[result_key][column_name] = []
                    if model_ins and new_data:
                        decoded_results[result_key][column_name].append(model_ins)
                        row_results[column_name].append(model_ins)
                    elif model_ins and row_results[column_name]:
                        row_results[column_name][-1] = model_ins
                        decoded_results[result_key][column_name][-1] = model_ins
                    elif model_ins:
                        row_results[column_name].append(model_ins)
                        decoded_results[result_key][column_name].append(model_ins)
                else:
                    row_results[column_name] = model_ins
                    decoded_results[result_key][column_name] = row_results[column_name]

        parsed_results = [
            cls(**decoded_results[pk]) for pk in decoded_results
        ]
        return parsed_results

    async def update(self,
        where: dict = None,
        **to_update: Optional[dict]
    ) -> NoneType:
        """
        <b>Update<b>
        Updates the contents of a `DataBaseModel` instance in the database
            where the value of `DataBaseModel` primary key matches 
        ```
            models = await Model.filter(Model.id='abcd1234')
            model = models[0]
            model.data = '12345'
            await model.update()
        ```
        """
        self.__class__.get_table()

        table_name = self.__class__.__name__
        primary_key = self.__metadata__.tables[table_name]['primary_key']

        if not to_update:
            to_update = self.dict()
            del to_update[primary_key]

        where_ = dict(*where or {})
        if not where_:
            where_ = {primary_key: getattr(self, primary_key)}

        table = self.__metadata__.tables[table_name]['table']
        for column in to_update.copy():
            if column in self.__metadata__.tables[table_name]['foreign_keys']:
                continue
            if column not in table.c:
                raise Exception(f"{column} is not a valid column in {table}")

        query, _ = self.where(table.update(), where_)

        to_update, links = await self.serialize(to_update, insert=True, update=True)

        if to_update:
            query = query.values(**to_update)
            await self.__metadata__.database.execute(query, to_update)
        if links:
            try:
                await asyncio.gather(*[asyncio.shield(l) for l in links])
            except Exception as e:
                print(repr(e))

            
    async def delete(self) -> NoneType:
        """
        <b>Delete<b>
        Delete the contents of a `DataBaseModel` instance in the database
            where the value of `DataBaseModel` primary key matches 
        ```
            models = await Model.filter(Model.id='abcd1234')
            model = models[0]
            await model.delete()
        ```
        """
        table_name = self.__class__.__name__
        database = self.__metadata__.database
        
        table = self.__metadata__.tables[table_name]['table']

        primary_key = self.__metadata__.tables[table_name]['primary_key']
        
        query, _ = self.where(delete(table), {primary_key: getattr(self, primary_key)})

        return await database.execute(query, None)

    async def insert(
        self, 
        return_links=False
    ) -> Union[NoneType, List[Coroutine]]:
        """
        <b>Insert<b>
        Insert the contents of a `DataBaseModel` instance in the database
            if the values of the `DataBaseModel` primary key do not exist 
        ```
        model = Models(id='abcd1234', data='data')
        await model.insert()
        ```
        Internal Only:
            return_links - will request table_link insertions be returned to 
                run later, needed when inserting `DataBaseModel`s with related
                `DataBaseModel` attributes
        """
        table = self.__class__.get_table()
        database = self.__metadata__.database

        values, links = await self.serialize(self.dict(), insert=True)
        query = table.insert()
        try:
            await self.__metadata__.database.execute(
                query, values
            )
        except Exception as e:
            database.log.error(f"error inserting into {table.name} - error: {repr(e)}")
            for link in links:
                link.close()
            raise e
            
        if return_links:
            return links

        # run links in chain
        try:
            await asyncio.gather(*[asyncio.shield(l) for l in links])
        except Exception:
            database.log.exception(f"chain link insertion error")


    @classmethod
    async def get(
        cls, 
        *p_key_condition: DataBaseModelCondition, 
        backward_refs=True,
        **p_key: dict
    ) -> DataBaseModel:
        if not p_key_condition:
            for k in p_key:
                primary_key = cls.__metadata__.tables[cls.__name__]['primary_key']
                if k != cls.__metadata__.tables[cls.__name__]['primary_key']:
                    raise Exception(f"Expected primary key {primary_key}=<value>")
                p_key_condition = [getattr(cls, primary_key)  == p_key[k]]
            
        result = await cls.filter(*p_key_condition, backward_refs=backward_refs)
        return result[0] if result else None

    @classmethod
    async def create(cls, **model_kwargs) -> DataBaseModel:
        new_obj = cls(**model_kwargs)
        await new_obj.insert()
        return new_obj
    def __init__(self, **model_kwargs) -> DataBaseModel:
        return super().__init__(**model_kwargs)


class TableMeta(DataBaseModel):
    table_name: str = PrimaryKey()
    model: dict
    columns: list


class DatabaseInit(DataBaseModel):
    database_url: str = PrimaryKey()
    status: Optional[str]
    reservation: Optional[str]
