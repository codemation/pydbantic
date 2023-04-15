import asyncio
import importlib
import sys
import typing
from pickle import dumps, loads
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    ForwardRef,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import sqlalchemy
from pydantic import BaseModel, PrivateAttr, ValidationError
from pydantic.fields import FieldInfo as PydanticFieldInfo
from pydantic.fields import PrivateAttr
from sqlalchemy import (
    ARRAY,
    JSON,
    VARCHAR,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Time,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Query, Session, relationship
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy.sql.expression import delete
from sqlalchemy.sql.functions import count
from sqlalchemy.util.langhelpers import NoneType

T = TypeVar("T")


def get_model_getter(model, primary_key, primary_key_value):
    return lambda: model.get(**{primary_key: primary_key_value})


class RelationshipRef(BaseModel):
    primary_key: str
    value: Any
    _method_: Callable = PrivateAttr()
    _default_: Optional[Callable] = PrivateAttr()
    _model_: Callable = PrivateAttr()

    def __init__(self, model, primary_key, value, default=None):

        super().__init__(primary_key=primary_key, value=value)
        self._method_ = get_model_getter(model, primary_key, value)
        self._default_ = default
        self._model_ = model

    def __repr__(self):
        return f"{self._model_.__name__}Ref({self.primary_key}={self.value})"

    def __call__(self) -> Coroutine:
        return self._method_()

    def dict(self, *args, **kwargs):
        return {f"{self.primary_key}": self.value}


def get_model_getter(model, primary_key, primary_key_value):
    return lambda: model.get(**{primary_key: primary_key_value})


class BaseMeta:
    def __init__(self):
        self.translations: dict = {
            str: sqlalchemy.String,
            int: sqlalchemy.Integer,
            float: sqlalchemy.Float,
            bool: sqlalchemy.Boolean,
            dict: sqlalchemy.LargeBinary,
            list: sqlalchemy.LargeBinary,
            tuple: sqlalchemy.LargeBinary,
        }
        self.tables: dict = {}


def Relationship(
    relationship_model: Any,
    relationship_local_column: str,
    relationship_model_column: str,
    default=[],
):
    return get_field_config(
        relationship_model=relationship_model,
        relationship_local_column=relationship_local_column,
        relationship_model_column=relationship_model_column,
        default=default,
    )


supported_sqlalchemy_types = [
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    Time,
    LargeBinary,
    Boolean,
    JSON,
    VARCHAR,
    Float,
]


def is_sqlalchemy_supported_type(sqlalchemy_type: Any) -> Optional[bool]:
    if sqlalchemy_type is None:
        return True
    if (
        sqlalchemy_type not in supported_sqlalchemy_types
        and sqlalchemy_type.__class__ not in supported_sqlalchemy_types
    ):
        raise Exception(
            f"{sqlalchemy_type} is not a supported type {supported_sqlalchemy_types}"
        )


def PrimaryKey(
    sqlalchemy_type: Any = None,
    default=...,
    autoincrement: Union[bool, None] = None,
) -> Any:

    return get_field_config(
        default=default,
        primary_key=True,
        autoincrement=autoincrement,
        sqlalchemy_type=sqlalchemy_type,
    )


def ForeignKey(
    foreign_model: Union[T, str], foreign_model_key: str, default=None
) -> Any:
    return get_field_config(
        foreign_model=foreign_model,
        foreign_model_key=foreign_model_key,
        default=default,
    )


def Default(
    sqlalchemy_type: Any = None, default=..., autoincrement: Optional[bool] = None
) -> Any:
    return get_field_config(
        default=default,
        autoincrement=autoincrement,
        sqlalchemy_type=sqlalchemy_type,
    )


def Unique(
    sqlalchemy_type: Any = None, default=..., autoincrement: Optional[bool] = None
) -> Any:
    return get_field_config(
        default=default,
        unique=True,
        sqlalchemy_type=sqlalchemy_type,
        autoincrement=autoincrement,
    )


def ModelField(
    sqlalchemy_type: Any = None,
    default=...,
    primary_key: Optional[bool] = None,
    unique: Optional[bool] = None,
    autoincrement: Optional[bool] = None,
) -> Any:
    return get_field_config(
        default=default,
        primary_key=primary_key,
        unique=unique,
        autoincrement=autoincrement,
        sqlalchemy_type=sqlalchemy_type,
    )


def get_field_config(
    default=...,
    primary_key: Optional[bool] = None,
    unique: Optional[bool] = None,
    sqlalchemy_type=None,
    autoincrement: Optional[bool] = None,
    foreign_model: Any = None,
    foreign_model_key: Optional[str] = None,
    relationship_model: Optional[str] = None,
    relationship_local_column: Optional[str] = None,
    relationship_model_column: Optional[str] = None,
) -> Any:
    config = {}
    if isinstance(default, type(lambda x: x)):
        config["default_factory"] = default
    if default is ...:
        config["default"] = default
    if primary_key is not None:
        config["primary_key"] = primary_key
    if unique is not None:
        config["unique"] = unique
    if sqlalchemy_type is not None:
        config["sqlalchemy_type"] = sqlalchemy_type
        is_sqlalchemy_supported_type(sqlalchemy_type)
    if autoincrement is not None:
        config["autoincrement"] = autoincrement
        config["default"] = None if default is ... else config["default"]
    if foreign_model is not None:
        config["foreign_model"] = foreign_model
        config["foreign_model_key"] = foreign_model_key
    if relationship_model is not None:
        config["relationship_model"] = relationship_model
        config["relationship_local_column"] = relationship_local_column
        config["relationship_model_column"] = relationship_model_column

    return Field(**config)


class Field(PydanticFieldInfo):
    def __init__(self, **kwargs: Any):
        supported_config = {"default_factory"}
        field_info_config = {k: kwargs[k] for k in supported_config if k in kwargs}
        super().__init__(**field_info_config)
        for k, v in kwargs.items():
            setattr(self, k, v)


class LinkTable:
    def __init__(
        self,
        link_table: sqlalchemy.Table,
        related_model,
        related_key,
        local_model,
        local_key,
    ):
        self.c = link_table.c
        self.link_table = link_table
        self.related_model = related_model
        self.related_key = related_key
        self.local_model = local_model
        self.local_key = local_key

    def setup_relationships(self, field_ref: str, related_model_ref: str):
        local_table = self.local_model.get_table()
        setattr(
            local_table,
            field_ref,
            relationship(
                self.related_model.__name__,
                secondary=self.link_table,
                backref=related_model_ref,
            ),
        )

    def outer_join(self, session_query):
        local_table = self.local_model.get_table()
        related_table = self.related_model.get_table()

        session_query = session_query.outerjoin(
            self.link_table,
            getattr(local_table.c, self.local_key)
            == getattr(
                self.link_table.c, f"{self.local_model.__tablename__}_{self.local_key}"
            ),
        ).outerjoin(
            related_table,
            getattr(
                self.link_table.c,
                f"{self.related_model.__tablename__}_{self.related_key}",
            )
            == getattr(related_table.c, self.related_key),
        )
        return session_query


class DataBaseModelCondition:
    def __init__(
        self,
        description: str,
        condition: Union[sqlalchemy.sql.expression.BinaryExpression, Any],
        values,
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
        column: sqlalchemy.Column,
        table,
        serialized: bool = False,
        is_array: bool = False,
        foreign_model=None,
    ):
        self.name = name
        self.column = column
        self.table = table
        self.serialized = serialized
        self.is_array = is_array

        self.foreign_model = foreign_model

    def process_value(self, value):
        if value.__class__ is self.table["model"]:
            primary_key = self.table["model"].__metadata__.tables[self.foreign_model][
                "primary_key"
            ]
            return getattr(value, primary_key)

        if self.serialized:
            return dumps(value)

        return value

    def __lt__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} < {values}",
            self.column < self.process_value(value),
            (values,),
        )

    def __le__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} <= {values}",
            self.column <= self.process_value(value),
            (values,),
        )

    def __gt__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} > {values}",
            self.column > self.process_value(value),
            (values,),
        )

    def __ge__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} >= {values}",
            self.column >= self.process_value(value),
            (values,),
        )

    def __eq__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} == {values}",
            self.column == self.process_value(value),
            (values,),
        )

    def __ne__(self, value) -> DataBaseModelCondition:
        values = self.process_value(value)
        return DataBaseModelCondition(
            f"{self.name} != {values}",
            self.column != self.process_value(value),
            (values,),
        )

    def inside(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} in {choices}", self.column.in_(choices), tuple(choices)
        )

    def not_inside(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} not in {choices}", self.column.not_in(choices), tuple(choices)
        )

    def matches(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} in {choices}", self.column.in_(choices), tuple(choices)
        )

    def not_matches(self, choices: List[Any]) -> DataBaseModelCondition:
        choices = [self.process_value(value) for value in choices]
        return DataBaseModelCondition(
            f"{self.name} not in {choices}", self.column.not_in(choices), tuple(choices)
        )

    def count(self) -> count:
        return count(self.column)


class DataBaseModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def check_if_subtype(cls, field):

        database_model = None

        if isinstance(field["type"], typing._GenericAlias):
            for sub in field["type"].__args__:

                if isinstance(sub, ForwardRef):
                    database_model = sub.__forward_value__

                elif issubclass(sub, DataBaseModel):
                    if database_model:
                        raise Exception(
                            f"Cannot Specify two DataBaseModels in Union[] for {field['name']}"
                        )
                    database_model = sub
        elif issubclass(field["type"], DataBaseModel):
            return field["type"]
        return database_model

    @classmethod
    def resolve_missing_module(cls, missing_error):
        cls.__metadata__.database.log.warning(
            f"detected {missing_error} - attempting to self correct"
        )
        missing_module = missing_error[38:-3]
        module = importlib.new_module(missing_module)
        sys.modules[missing_module] = module

    @classmethod
    def resolve_missing_attribute(cls, missing_error: str, expected_type=None):
        cls.__metadata__.database.log.warning(
            f"detected {missing_error} - attempting to self correct"
        )
        try:
            missing_attr = (
                "".join(
                    missing_error.split("Can't get attribute")[1].split("on <module")
                )
                .split("from")[0]
                .split(" ")[1][1:-1]
            )

            missing_mod = (
                "".join(
                    missing_error.split("Can't get attribute")[1].split("on <module")
                )
                .split("from")[0]
                .split(" ")[3][1:-4]
            )

            if not missing_mod in sys.modules:
                mod = imp.new_module(missing_mod)
            else:
                mod = sys.modules[missing_mod]

            if expected_type:
                (missing_class,) = [
                    v[1]
                    for _, v in cls.__metadata__.tables[expected_type][
                        "column_map"
                    ].items()
                    if hasattr(v[1], "__name__") and v[1].__name__ == missing_attr
                ]
            else:
                missing_class = cls.__metadata__.tables[cls.__name__]["column_map"][
                    missing_attr
                ][1]

            setattr(mod, missing_attr, missing_class)
        except Exception:
            raise Exception(
                f"Failed to resolve {missing_error} with expected_type of {expected_type}"
            )

    @classmethod
    def deserialize(cls, data, expected_type=None):
        while True:
            try:
                return loads(data) if data is not None else None
            except AttributeError as e:
                cls.resolve_missing_attribute(repr(e), expected_type=expected_type)
            except ModuleNotFoundError as e:
                cls.resolve_missing_module(repr(e))
            except Exception as e:
                raise e

    @classmethod
    def setup(cls, database):
        cls.__metadata__ = database.__metadata__
        cls.__tablename__ = getattr(cls, "__tablename__", cls.__name__)
        cls.update_backward_refs()

        if not hasattr(cls.__metadata__, "metadata"):
            cls.init_set_metadata(database.metadata)
            cls.init_set_database(database)
        # if cls.__name__ not in cls.__metadata__.tables:
        cls.generate_sqlalchemy_table()

    @classmethod
    def init_set_metadata(cls: Type[T], metadata) -> None:
        """
        Applies an instantiated sqlalchemy.MetaData() instance to __metadata__.metadata
        """
        cls.__metadata__.metadata = metadata

    @classmethod
    def init_set_database(cls: Type[T], database) -> None:
        """
        Applies an instantiated easydb.Database() instance to __metadata__.database
        """
        cls.__metadata__.database = database

    @classmethod
    def generate_sqlalchemy_table(cls) -> None:
        if not hasattr(cls.__metadata__, "metadata"):
            raise Exception(
                f"No connected sqlalchemy.MetaData() instance yet, first run {cls}.init_set_metadata()"
            )
        name = cls.__name__

        columns, link_tables = cls.convert_fields_to_columns()

        cls.__metadata__.tables[name]["table"] = sqlalchemy.Table(
            name if not hasattr(cls, "__tablename__") else cls.__tablename__,
            cls.__metadata__.metadata,
            *columns,
            extend_existing=cls.__tablename__ in cls.__metadata__.metadata.tables,
        )

        for data_base_model, field_name in link_tables:
            cls.generate_relationship_table(data_base_model, field_name)

    @classmethod
    def generate_relationship_table(cls: Type[T], related_model: T, field_ref: str):
        """
        creates a 2 column table that enables a link between
        cls primary_key & related_model primary key
        """

        name = cls.__name__

        related_model_ref = None
        relationship_definitions = None
        for f_name, field in related_model.__fields__.items():
            data_base_model = related_model.check_if_subtype(
                {"name": f_name, "type": field.type_}
            )
            if data_base_model is cls:
                related_model_ref = f_name
                relationship_definitions = cls.__metadata__.tables[name][
                    "relationship_definitions"
                ].get(related_model.__name__)

        if (
            related_model.__name__
            in cls.__metadata__.tables[cls.__name__]["relationships"]
        ):
            # link table already exists, initialize relationship on local table
            cls.__metadata__.tables[cls.__name__]["relationships"][
                related_model.__name__
            ].setup_relationships(field_ref, related_model_ref)
            return

        local_column = cls.__metadata__.tables[cls.__name__]["primary_key"]
        related_column = cls.__metadata__.tables[related_model.__name__]["primary_key"]

        relationship_definitions = cls.__metadata__.tables[name][
            "relationship_definitions"
        ].get(related_model.__name__)

        if relationship_definitions:
            local_column = relationship_definitions["local_column"]
            related_column = relationship_definitions["related_column"]

        relationship_table = sqlalchemy.Table(
            f"{cls.__tablename__}_to_{related_model.__tablename__}",
            cls.__metadata__.metadata,
            sqlalchemy.Column(
                f"{cls.__tablename__}_{local_column}",
                sqlalchemy.ForeignKey(
                    f"{cls.__tablename__}.{local_column}", ondelete="CASCADE"
                ),
                primary_key=True,
            ),
            sqlalchemy.Column(
                f"{related_model.__tablename__}_{related_column}",
                sqlalchemy.ForeignKey(
                    f"{related_model.__tablename__}.{related_column}",
                    ondelete="CASCADE",
                ),
                primary_key=True,
            ),
        )

        cls.__metadata__.tables[cls.__name__]["relationships"][
            related_model.__name__
        ] = LinkTable(
            relationship_table, related_model, related_column, cls, local_column
        )
        # initalize relationship on local table
        cls.__metadata__.tables[cls.__name__]["relationships"][
            related_model.__name__
        ].setup_relationships(field_ref, related_model_ref)

        cls.__metadata__.tables[related_model.__name__]["relationships"][
            cls.__name__
        ] = LinkTable(
            relationship_table, cls, local_column, related_model, related_column
        )

    @classmethod
    def generate_model_attributes(cls):
        name = cls.__name__
        for c, column in cls.__metadata__.tables[name]["column_map"].items():
            foreign_model = None
            if c in cls.__metadata__.tables[name]["foreign_keys"]:
                foreign_model = cls.__metadata__.tables[name]["foreign_keys"][c]
                table = cls.__metadata__.tables[foreign_model.__name__]
                foreign_pk = table["primary_key"]

                table_column = table["table"].c[foreign_pk]
            else:
                table = cls.__metadata__.tables[name]
                table_column = table["table"].c[c]

            setattr(
                cls,
                c,
                DataBaseModelAttribute(
                    c,
                    table_column,
                    table,
                    column[2],
                    column[3],
                    foreign_model=foreign_model.__name__ if foreign_model else None,
                ),
            )

    @classmethod
    def update_backward_refs(cls):
        """
        force update forward refs of all backward referncing DataBaseModels
        """
        for _, model_field in cls.__fields__.items():
            data_base_model = cls.check_if_subtype({"type": model_field.type_})
            if data_base_model:
                data_base_model.update_forward_refs()

    @classmethod
    def convert_fields_to_columns(
        cls,
        model_fields: Optional[list] = None,
        include: Optional[list] = None,
        alias: Optional[dict] = None,
        update: bool = False,
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

        name = cls.__name__
        primary_key = None
        unique_keys = set()
        array_fields = set()
        nullable_feilds = set()

        field_properties = {}

        try:
            model_schema = cls.schema()
        except TypeError:
            raise Exception(
                f"{cls.__name__} was referenced by DataBaseModel(s) not added in Database setup tables=[..,]"
            )

        if "title" in model_schema and model_schema["title"] == cls.__name__:
            field_properties = model_schema["properties"]
        elif (
            "definitions" in model_schema
            and cls.__name__ in model_schema["definitions"]
        ):
            field_properties = model_schema["definitions"][cls.__name__]["properties"]
        else:
            field_properties = model_schema["properties"]

        required_fields = model_schema.get("required", [])

        default_fields = {}
        autoincr_fields = {}
        sqlalchemy_type_config = {}
        field_constraints = {}
        relationship_definitions = {}
        for field_property, config in field_properties.items():
            if hasattr(cls.__fields__[field_property].field_info, "__dict__"):
                config.update(cls.__fields__[field_property].field_info.__dict__)
            field_constraints[field_property] = []
            if "primary_key" in config:

                if primary_key:
                    raise Exception(
                        f"Duplicate Primary Key Specified for {cls.__name__}"
                    )
                primary_key = field_property

            if "unique" in config:
                unique_keys.add(field_property)

            if (
                "type" in config
                and config["type"] == "array"
                and not primary_key == field_property
            ):
                array_fields.add(field_property)

            if "default" in config:
                default_fields[field_property] = config["default"]

            if "autoincrement" in config:

                autoincr_fields[field_property] = config["autoincrement"]

            if "sqlalchemy_type" in config:
                sqlalchemy_type_config[field_property] = config["sqlalchemy_type"]

            if "foreign_model" in config:
                foreign_model_name = config["foreign_model"].__name__
                foreign_table_name = config["foreign_model"].__tablename__
                foreign_model_key = (
                    cls.__metadata__.tables[foreign_model_name]["primary_key"]
                    if "foreign_model_key" not in config
                    else config["foreign_model_key"]
                )

                # foreign_model_sqlalchemy_type = cls.__metadata__.tables[foreign_model_name]['column_map'][foreign_model_key][0]
                # sqlalchemy_type_config[field_property] = foreign_model_sqlalchemy_type

                field_constraints[field_property].append(
                    sqlalchemy.ForeignKey(f"{foreign_table_name}.{foreign_model_key}")
                )
            if "relationship_model" in config:
                relationship_definitions[config["relationship_model"]] = {
                    "local_column": config["relationship_local_column"],
                    "related_column": config["relationship_model_column"],
                }

            if not field_property in required_fields:
                nullable_feilds.add(field_property)

        if not model_fields:
            model_fields_list = [
                f
                for _, f in cls.__fields__.items()
                if f.name in include or f.name in alias
            ]
            model_fields = []
            for field in model_fields_list:
                field_name = field.name
                if field.name in alias:
                    field_name = alias[field.name]
                model_fields.append(
                    {
                        "name": field_name,
                        "type": field.type_,
                        "required": field.required,
                    }
                )

        name = cls.__name__
        primary_key = model_fields[0]["name"] if not primary_key else primary_key
        if name not in cls.__metadata__.tables or update:

            cls.__metadata__.tables[name] = {
                "primary_key": primary_key,
                "column_map": {},
                "foreign_keys": {},
                "relationships": {}
                if name not in cls.__metadata__.tables
                else cls.__metadata__.tables[name]["relationships"],
                "relationship_definitions": relationship_definitions,
            }

        columns = []
        link_tables = []
        for i, field in enumerate(model_fields):

            data_base_model = cls.check_if_subtype(field)
            if data_base_model:
                # ensure DataBaseModel also exists in Database, even if not already
                # explicity added
                data_base_model.update_forward_refs()
                if data_base_model.__name__ not in cls.__metadata__.tables:
                    cls.__metadata__.database.add_table(data_base_model)

                # create a string or foreign table column to be used to reference
                # other table
                if not update:
                    link_tables.append((data_base_model, field["name"]))

                foreign_table_name = data_base_model.__name__
                foreign_primary_key_name = data_base_model.__metadata__.tables[
                    foreign_table_name
                ]["primary_key"]
                foreign_key_type = data_base_model.__metadata__.tables[
                    foreign_table_name
                ]["column_map"][foreign_primary_key_name][1]

                serialize = False

                cls.__metadata__.tables[name]["column_map"][field["name"]] = (
                    cls.__metadata__.database.get_translated_column_type(
                        foreign_key_type if not serialize else list
                    )[0],
                    data_base_model,
                    serialize,
                    field["name"] in array_fields,
                    False,
                )

                # store field name in map to quickly determine attribute is tied to
                # foreign table
                cls.__metadata__.tables[name]["foreign_keys"][
                    field["name"]
                ] = data_base_model

                continue

            # get sqlalchemy column type based on field type & if primary_key
            # as well as determine if data should be serialized & de-serialized
            if field["name"] not in sqlalchemy_type_config:
                (
                    sqlalchemy_model,
                    serialize,
                ) = cls.__metadata__.database.get_translated_column_type(
                    field["type"], primary_key=field["name"] == primary_key
                )
            else:
                sqlalchemy_model = sqlalchemy_type_config[field["name"]]
                serialize = sqlalchemy_model.__class__ == sqlalchemy.LargeBinary

            cls.__metadata__.tables[name]["column_map"][field["name"]] = (
                sqlalchemy_model,
                field["type"],
                serialize,
                False,  # field['name'] in array_fields
                field["name"] in autoincr_fields,
            )
            cls.__metadata__.tables[name]["model"] = cls
            server_default = {}
            if field["name"] in default_fields:
                server_default["default"] = default_fields[field["name"]]
                if serialize:
                    server_default["default"] = dumps(server_default["default"])

            if field["name"] in autoincr_fields:
                server_default["autoincrement"] = autoincr_fields[field["name"]]

            column_type_config = cls.__metadata__.tables[name]["column_map"][
                field["name"]
            ][0]
            columns.append(
                sqlalchemy.Column(
                    field["name"],
                    column_type_config["column_type"](
                        *column_type_config["args"], **column_type_config["kwargs"]
                    )
                    if field["name"] not in sqlalchemy_type_config
                    else sqlalchemy_model,
                    *field_constraints.get(field["name"], []),
                    primary_key=field["name"] == primary_key,
                    unique=field["name"] in unique_keys,
                    nullable=field["name"] in nullable_feilds
                    and field["name"] != primary_key,
                    **server_default,
                )
            )

        return columns, link_tables

    async def serialize(
        self, data: dict, insert: bool = False, update: bool = False, alias=None
    ) -> Tuple[dict, List[Awaitable]]:
        """
        expects
            `data` - data to be serialized
        """
        database = self.__metadata__.database
        name = self.__class__.__name__
        table_name = self.__class__.__tablename__
        if not alias:
            alias = {}

        values = {**data}
        primary_key = self.__metadata__.tables[name]["primary_key"]

        link_chain = []

        for k, v in data.items():

            serialize = self.__metadata__.tables[name]["column_map"][k][2]

            autoincrement = self.__metadata__.tables[name]["column_map"][k][4]
            if autoincrement:
                del values[k]
                continue

            if k in self.__metadata__.tables[name]["foreign_keys"]:

                # use the foreign DataBaseModel's primary key / value
                foreign_type = self.__metadata__.tables[name]["column_map"][k][1]
                foreign_name = foreign_type.__name__
                foreign_table_name = foreign_type.__tablename__
                foreign_primary_key = foreign_type.__metadata__.tables[foreign_name][
                    "primary_key"
                ]

                Link: LinkTable = self.__metadata__.tables[name]["relationships"][
                    foreign_name
                ]
                link_table = Link.link_table

                if foreign_primary_key != Link.related_key:
                    foreign_primary_key = Link.related_key
                if primary_key != Link.local_key:
                    primary_key = Link.local_key

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

                    serialize_local = self.__metadata__.tables[name]["column_map"][
                        primary_key
                    ][2]
                    serialize_foreign = self.__metadata__.tables[foreign_name][
                        "column_map"
                    ][foreign_primary_key][2]

                    if serialize_local:
                        local_value = dumps(local_value)

                    if serialize_foreign:
                        foreign_primary_key_value = dumps(foreign_primary_key_value)

                    link_values = {
                        f"{table_name}_{primary_key}": local_value,
                        f"{foreign_table_name}_{foreign_primary_key}": foreign_primary_key_value,
                    }
                    link_insert = database.execute(link_table.insert(), link_values)
                    link_chain.append(link_insert)

                    if insert:
                        exists = await foreign_type.filter(
                            **{
                                foreign_primary_key: foreign_primary_key_value,
                                "count_rows": True,
                                "join": False,
                            },
                        )
                        if exists == 0:

                            foreign_model = foreign_type(**v)
                            link_chain.extend(
                                await foreign_model._save(return_links=True)
                            )

                del values[k]

                # delete links between items not in fk_values

                if update and fk_values:
                    remove_deleted = delete(link_table).where(
                        and_(
                            link_table.c[f"{table_name}_{primary_key}"] == local_value,
                            link_table.c[
                                f"{foreign_table_name}_{foreign_primary_key}"
                            ].not_in(fk_values),
                        )
                    )
                    result = await database.execute(remove_deleted)

                # remove existing references, if any, to match removed
                if update and not fk_values:
                    link_chain.append(
                        database.execute(
                            delete(link_table).where(
                                link_table.c[f"{table_name}_{primary_key}"]
                                == local_value
                            )
                        )
                    )
                continue

            serialize = self.__metadata__.tables[name]["column_map"][k][2]

            if serialize:
                values[k] = dumps(getattr(self, k))
                continue

            values[k] = v

        return values, link_chain

    async def _save(self: T, return_links: bool = False) -> Optional[List[Coroutine]]:
        primary_key = self.__metadata__.tables[self.__class__.__name__]["primary_key"]
        count = await self.__class__.filter(
            **{primary_key: getattr(self, primary_key)}, count_rows=True
        )
        if count == 0:
            return await self._insert(return_links=return_links)
        await self.update()
        return []

    async def save(self: T) -> T:
        await self._save()
        return self

    @classmethod
    def where(
        cls, query: Query, where: dict, *conditions: List[DataBaseModelCondition]
    ) -> Tuple[Query, tuple]:

        table = cls.get_table()
        conditions = list(conditions)
        values = []

        # convert keyword arguments into DataBaseModelConditions
        for cond, value in where.items():
            is_serialized = cls.__metadata__.tables[cls.__name__]["column_map"][cond][2]
            if not isinstance(cond, DataBaseModelAttribute) and hasattr(cls, cond):
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
    def get_table(cls) -> sqlalchemy.Table:
        if cls.__name__ not in cls.__metadata__.tables:
            cls.generate_sqlalchemy_table()

        return cls.__metadata__.tables[cls.__name__]["table"]

    @classmethod
    def OR(
        cls,
        *conditions: List[Union[DataBaseModelCondition, List[DataBaseModelCondition]]],
        **filters: dict,
    ) -> DataBaseModelCondition:
        """
        combines input `conditions` and keyword argument filters
        into an OR separated conditional tied with associated values
        in a new `DataBaseModelCondition`
        """
        table = cls.get_table()
        conditions = list(conditions)

        for cond, value in filters.items():
            if not isinstance(cond, DataBaseModelAttribute) and hasattr(cls, cond):
                cond = getattr(cls, cond)
            else:
                raise Exception(f"{cond} is not a valid column in {table}")

            conditions.append(cond == value)

        parsed_conditions = []
        for cond in conditions:
            if isinstance(cond, list):
                cond_group_values = []
                # condition group, join values & conditions by AND
                for c_item in cond:
                    if not isinstance(c_item, DataBaseModelCondition):
                        raise Exception(
                            f"List items passed to OR must be List[DataBaseModelCondition]"
                        )

                    cond_group_values.extend(c_item.values)
                parsed_conditions.append(
                    DataBaseModelCondition(
                        " AND ".join([str(cnd) for cnd in cond]),
                        and_(*[cnd.condition for cnd in cond]),
                        values=tuple(cond_group_values),
                    )
                )
                continue
            else:
                parsed_conditions.append(cond)

        values = []
        for cond in parsed_conditions:
            if isinstance(cond.values, tuple):
                values.extend(cond.values)

        return DataBaseModelCondition(
            " OR ".join([str(cond) for cond in parsed_conditions]),
            or_(*[cond.condition for cond in parsed_conditions]),
            values=tuple(values),
        )

    @classmethod
    def gt(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")

        return DataBaseModelCondition(
            f"{column} > {value}", table.c[column] > value, value
        )

    @classmethod
    def gte(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} >= {value}", table.c[column] >= value, value
        )

    @classmethod
    def lt(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} < {value}", table.c[column] < value, value
        )

    @classmethod
    def lte(cls, column: str, value: Any) -> DataBaseModelCondition:
        table = cls.get_table()
        if not column in table.c:
            raise Exception(f"{column} is not a valid column in {table}")
        return DataBaseModelCondition(
            f"{column} <= {value}", table.c[column] >= value, value
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
            f"{value} in {column}", table.c[column].contains(value), value
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
    async def exists(cls, **column_values: dict) -> bool:

        table = cls.get_table()
        primary_key = cls.__metadata__.tables[cls.__name__]["primary_key"]

        for k in column_values:
            if k not in table.c:
                raise Exception(f"{k} is not a valid column in  {table} ")

        sel = select([table.c[primary_key]])

        sel, values = cls.where(sel, column_values)

        database = cls.__metadata__.database

        results = await database.fetch(sel, {cls.__tablename__}, values)

        return bool(results)

    @classmethod
    def deep_join(
        cls: Type[T],
        model_ref,
        model_ref_primary_key: str,
        column_ref: str,
        session_query: Query,
        tables_to_select: list,
        models_selected: set,
        root_model: T = None,
    ) -> Tuple[Query, List[Tuple[sqlalchemy.Table, T, str, T]]]:
        """
        Traverse a DataBaseModel relationship and add subsequent
        .join() clauses to active session_query, and append foreign tables
        to list
        """

        foreign_models = []
        for column_name in cls.__metadata__.tables[cls.__name__]["column_map"]:
            if column_name in cls.__metadata__.tables[cls.__name__]["foreign_keys"]:

                # foreign model
                foreign_model = cls.__metadata__.tables[cls.__name__]["column_map"][
                    column_name
                ][1]
                if foreign_model.__tablename__ in models_selected:
                    # skipping model, as is already selected in current query
                    continue
                foreign_models.append((foreign_model, column_name))

        ref_table = model_ref.get_table()
        table = cls.get_table()
        primary_key = cls.__metadata__.tables[cls.__name__]["primary_key"]

        _link_table = cls.__metadata__.tables[model_ref.__name__]["relationships"][
            cls.__name__
        ]
        link_table = _link_table.link_table

        session_query = _link_table.outer_join(session_query)

        if not cls is root_model:
            session_query = session_query.add_columns(*[c for c in table.c])
            tables_to_select.append((table, cls, column_ref, model_ref))
        models_selected.add(cls.__tablename__)
        models_selected.add(link_table.name)

        for foreign_model, column_ref in foreign_models:
            session_query, tables_to_select = foreign_model.deep_join(
                cls,
                primary_key,
                column_ref,
                session_query,
                tables_to_select,
                models_selected,
            )
        return session_query, tables_to_select

    @classmethod
    async def select(
        cls: Type[T],
        *selection,
        where: Optional[Union[dict, None]] = None,
        alias: Optional[dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = 0,
        order_by=None,
        primary_key: Optional[str] = None,
        backward_refs: bool = True,
    ) -> List[T]:
        if alias is None:
            alias = {}

        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)

        if selection[0] == "*":
            selection = [k for k in cls.__metadata__.tables[cls.__name__]["column_map"]]

        tables_to_select = []
        models_selected = set((cls.__tablename__,))

        primary_key = (
            cls.__metadata__.tables[cls.__name__]["primary_key"]
            if not primary_key
            else primary_key
        )

        sel = session.query(*[c for c in table.c if c.name in selection])

        for _sel in selection:
            column_name = _sel

            if column_name in cls.__metadata__.tables[cls.__name__]["foreign_keys"]:
                foreign_model = cls.__metadata__.tables[cls.__name__]["column_map"][
                    column_name
                ][1]
                sel, tables_to_select = foreign_model.deep_join(
                    cls,
                    primary_key,
                    column_name,
                    sel,
                    tables_to_select,
                    models_selected,
                    root_model=cls,
                )
                if not foreign_model.__tablename__ in models_selected:
                    models_selected.add(foreign_model.__tablename__)
                continue

            if column_name not in table.c:
                raise Exception(
                    f"{column_name} is not a valid column in {table} - columns: {[k for k in table.c]}"
                )

        values = None
        if where:
            sel, values = cls.where(sel, where)

        if order_by is not None:
            sel = sel.order_by(order_by)

        sel, values = cls.check_limit_offset(sel, values, limit, offset)
        results = await database.fetch(sel.statement, models_selected, values)

        # build results_map
        results_map = {}
        last_ind = -1
        for i, c in enumerate(table.c):
            if not c.name in selection:
                continue

            col_name = c.name if not c.name in alias else alias[c.name]
            last_ind = last_ind + 1
            if c.name in cls.__metadata__.tables[cls.__name__]["foreign_keys"]:
                continue
            if not cls in results_map:
                results_map[cls] = {}
            results_map[cls][col_name] = last_ind

        for f_table, f_model, _, _ in tables_to_select:
            for i, c in enumerate(f_table.c):
                last_ind = last_ind + 1
                if c.name in cls.__metadata__.tables[f_model.__name__]["foreign_keys"]:
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
                    serialized = cls.__metadata__.tables[cls.__name__]["column_map"][k][
                        2
                    ]
                    is_array = cls.__metadata__.tables[cls.__name__]["column_map"][k][3]
                    expected_type = cls.__metadata__.tables[cls.__name__]["column_map"][
                        k
                    ][1]
                    row_result = result[result_ind]

                    # allows default value to be used when row_result is None
                    # if defined, this value is client side only until saved
                    if not row_result and table.columns[k].default is not None:
                        row_result = table.columns[k].default.arg

                    if serialized:
                        row_result = cls.deserialize(
                            row_result, expected_type=expected_type
                        )

                        if row_result and expected_type in {set, list, tuple}:
                            row_result = expected_type(row_result)

                    if is_array:
                        if not k in decoded_results[result_key]:
                            decoded_results[result_key][k] = []

                        decoded_results[result_key][k].append(row_result)
                    else:
                        decoded_results[result_key][k] = row_result

            for f_table, f_model, column_name, parent in tables_to_select:
                f_p_key = cls.__metadata__.tables[f_model.__name__]["primary_key"]
                f_p_key_value = result[results_map[f_model][f_p_key]]
                new_data = False
                if not row_results.get(f_p_key) == f_p_key_value:
                    new_data = True
                    for k, result_ind in results_map[f_model].items():

                        serialized = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][2]
                        is_array = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][3]
                        row_result = result[result_ind]
                        expected_type = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][1]

                        if serialized:
                            row_result = (
                                cls.deserialize(row_result, expected_type=expected_type)
                                if not row_result is None
                                else None
                            )
                            row_results[k] = row_result

                        elif is_array:
                            if not k in row_results and not k == f_p_key:
                                row_results[k] = []
                            if row_result:
                                row_results[k].append(row_result)
                        else:
                            row_results[k] = row_result

                # build model with collected results
                is_array_in_parent = parent.__metadata__.tables[parent.__name__][
                    "column_map"
                ][column_name][3]

                parent_p_key = parent.__metadata__.tables[parent.__name__][
                    "primary_key"
                ]
                parent_p_key_val = result[results_map[parent][parent_p_key]]

                try:
                    model_ins = f_model(**row_results)

                    for k, foreign_model in cls.__metadata__.tables[f_model.__name__][
                        "foreign_keys"
                    ].items():
                        if (
                            not parent.__name__ == foreign_model.__name__
                            or not backward_refs
                        ):
                            continue
                        foreign_ref = getattr(model_ins, k)

                        if foreign_ref is None:
                            setattr(
                                model_ins,
                                k,
                                RelationshipRef(
                                    parent,
                                    parent_p_key,
                                    parent_p_key_val,
                                    default=foreign_ref,
                                ),
                            )
                        elif foreign_ref == []:
                            setattr(
                                model_ins,
                                k,
                                [
                                    RelationshipRef(
                                        parent,
                                        parent_p_key,
                                        parent_p_key_val,
                                        default=foreign_ref,
                                    )
                                ],
                            )

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

        parsed_results = [cls(**decoded_results[pk]) for pk in decoded_results]

        return parsed_results

    @classmethod
    def check_limit_offset(
        cls, query: Query, values: List[Any], limit: int, offset: int
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
        cls: Type[T],
        limit: Optional[int] = None,
        offset: int = 0,
        order_by=None,
        backward_refs: bool = True,
    ) -> List[T]:
        parameters = {}
        if limit:
            parameters["limit"] = limit
        if offset:
            parameters["offset"] = offset
        if order_by is not None:
            parameters["order_by"] = order_by

        return await cls.select("*", **parameters, backward_refs=backward_refs)

    @classmethod
    async def count(cls) -> int:
        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)
        sel = session.query(func.count()).select_from(table)
        results = await database.fetch(sel.statement, {cls.__tablename__})
        return results[0][0] if results else 0

    @classmethod
    async def filter(
        cls: Type[T],
        *conditions: List[DataBaseModelCondition],
        limit: int = None,
        offset: int = 0,
        order_by=None,
        count_rows: bool = False,
        join: bool = True,
        backward_refs: bool = True,
        **column_filters,
    ) -> List[T]:
        table = cls.get_table()
        database = cls.__metadata__.database
        session = Session(database.engine)

        columns = [k for k in cls.__fields__]
        if not column_filters and not conditions:
            raise Exception(
                f"{cls.__name__}.filter() expects keyword arguments for columns: {columns} or conditions"
            )

        selection = [k for k in cls.__metadata__.tables[cls.__name__]["column_map"]]

        tables_to_select = []
        models_selected = set((cls.__tablename__,))

        primary_key = cls.__metadata__.tables[cls.__name__]["primary_key"]
        sel = session.query(table)

        for _sel in selection:
            column_name = _sel
            if column_name in cls.__metadata__.tables[cls.__name__]["foreign_keys"]:
                foreign_model = cls.__metadata__.tables[cls.__name__]["column_map"][
                    column_name
                ][1]
                if not join:
                    continue
                sel, tables_to_select = foreign_model.deep_join(
                    cls,
                    primary_key,
                    column_name,
                    sel,
                    tables_to_select,
                    models_selected,
                )
                if not foreign_model.__tablename__ in models_selected:
                    models_selected.add(foreign_model.__tablename__)
                continue

        sel, values = cls.where(sel, column_filters, *conditions)

        sel, values = cls.check_limit_offset(sel.statement, values, limit, offset)

        if count_rows:
            row_count = await database.fetch(
                sel.with_only_columns(func.count()), models_selected
            )
            if row_count:
                if isinstance(row_count[0], dict):
                    return [v for _, v in row_count[0].items()][0]
                return row_count[0][0]
            return 0

        if not order_by is None:
            sel = sel.order_by(order_by)

        results = await database.fetch(sel, models_selected, tuple(values))
        return cls.parse_results(results, tables_to_select, backward_refs)

    @classmethod
    def parse_results(
        cls: Type[T], results: List[Tuple], tables_to_select, backward_refs
    ) -> List[T]:
        table = cls.get_table()
        results_map = {}
        last_ind = -1
        for i, c in enumerate(table.c):
            last_ind = last_ind + 1
            if c.name in cls.__metadata__.tables[cls.__name__]["foreign_keys"]:
                continue
            if not cls in results_map:
                results_map[cls] = {}
            results_map[cls][c.name] = last_ind

        for f_table, f_model, _, _ in tables_to_select:
            for i, c in enumerate(f_table.c):
                last_ind = last_ind + 1
                if c.name in cls.__metadata__.tables[f_model.__name__]["foreign_keys"]:
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
                    serialized = cls.__metadata__.tables[cls.__name__]["column_map"][k][
                        2
                    ]
                    is_array = cls.__metadata__.tables[cls.__name__]["column_map"][k][3]
                    row_result = result[result_ind]
                    expected_type = cls.__metadata__.tables[cls.__name__]["column_map"][
                        k
                    ][1]
                    if serialized:
                        if cls.__name__ == "TableMeta":
                            expected_type = cls.__metadata__.tables[result[0]][
                                "model"
                            ].__name__
                        row_result = cls.deserialize(
                            row_result, expected_type=expected_type
                        )
                        row_results[k] = row_result
                        decoded_results[result_key][k] = row_result

                    elif is_array:
                        if not k in decoded_results[result_key]:
                            decoded_results[result_key][k] = []

                        decoded_results[result_key][k].append(row_result)
                    else:
                        decoded_results[result_key][k] = row_result

            for f_table, f_model, column_name, parent in tables_to_select:
                f_p_key = cls.__metadata__.tables[f_model.__name__]["primary_key"]
                f_p_key_value = result[results_map[f_model][f_p_key]]
                new_data = False
                if not row_results.get(f_p_key) == f_p_key_value:
                    new_data = True
                    for k, result_ind in results_map[f_model].items():

                        serialized = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][2]
                        is_array = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][3]
                        row_result = result[result_ind]
                        expected_type = cls.__metadata__.tables[f_model.__name__][
                            "column_map"
                        ][k][1]
                        if serialized:
                            row_result = (
                                cls.deserialize(row_result, expected_type=expected_type)
                                if not row_result is None
                                else None
                            )

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
                is_array_in_parent = parent.__metadata__.tables[parent.__name__][
                    "column_map"
                ][column_name][3]

                parent_p_key = parent.__metadata__.tables[parent.__name__][
                    "primary_key"
                ]
                parent_p_key_val = result[results_map[parent][parent_p_key]]

                try:
                    model_ins = f_model(**row_results)

                    for k, foreign_model in cls.__metadata__.tables[f_model.__name__][
                        "foreign_keys"
                    ].items():
                        if (
                            not parent.__name__ == foreign_model.__name__
                            or not backward_refs
                        ):
                            continue
                        foreign_ref = getattr(model_ins, k)

                        if foreign_ref is None:
                            setattr(
                                model_ins,
                                k,
                                RelationshipRef(
                                    parent,
                                    parent_p_key,
                                    parent_p_key_val,
                                    default=foreign_ref,
                                ),
                            )
                        elif foreign_ref == []:
                            setattr(
                                model_ins,
                                k,
                                [
                                    RelationshipRef(
                                        parent,
                                        parent_p_key,
                                        parent_p_key_val,
                                        default=foreign_ref,
                                    )
                                ],
                            )

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

        parsed_results = [cls(**decoded_results[pk]) for pk in decoded_results]
        return parsed_results

    async def update(self, where: dict = None, **to_update: Optional[dict]) -> NoneType:
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

        model_name = self.__class__.__name__
        table_name = self.__class__.__tablename__
        database = self.__metadata__.database

        primary_key = self.__metadata__.tables[model_name]["primary_key"]

        if not to_update:
            to_update = self.dict()
            del to_update[primary_key]

        where_ = dict(*where or {})
        if not where_:
            where_ = {primary_key: getattr(self, primary_key)}

        table = self.__metadata__.tables[model_name]["table"]
        for column in to_update.copy():
            if column in self.__metadata__.tables[model_name]["foreign_keys"]:
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
                results = await asyncio.gather(
                    *[asyncio.shield(l) for l in links], return_exceptions=True
                )
            except Exception as e:
                pass

    @classmethod
    async def delete_many(cls: Type[T], rows: List[T]) -> int:
        table = cls.get_table()
        database = cls.__metadata__.database
        primary_key = cls.__metadata__.tables[cls.__name__]["primary_key"]
        primary_keys = [getattr(row, primary_key) for row in rows]
        primary_key_column: DataBaseModelAttribute = getattr(cls, primary_key)
        delete_condition: DataBaseModelCondition = primary_key_column.matches(
            primary_keys
        )

        query, _ = cls.where(delete(table), {}, delete_condition)
        return await database.execute(query, None)

    async def delete(self) -> int:
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
        model_name = self.__class__.__name__
        database = self.__metadata__.database

        table = self.__metadata__.tables[model_name]["table"]

        primary_key = self.__metadata__.tables[model_name]["primary_key"]

        query, _ = self.where(delete(table), {primary_key: getattr(self, primary_key)})

        return await database.execute(query, None)

    @classmethod
    async def insert_many(cls: Type[T], rows: List[T]) -> Optional[int]:
        table = cls.get_table()
        database = cls.__metadata__.database
        query = table.insert()
        data = [await row.serialize(row.dict(), insert=True) for row in rows]

        links = []
        values = []

        values = [d[0] for d in data]
        [links.extend(d[1]) for d in data]

        result = None
        try:
            result = await database.execute_many(query, values)
        except Exception as e:
            database.log.error(f"error inserting into {table.name} - error: {repr(e)}")
            for link in links:
                link.close()

        try:
            while links:
                await asyncio.gather(*[asyncio.shield(l) for l in links[:50]])
                del links[:50]

        except Exception:
            database.log.exception(f"chain link insertion error")

        return None

    async def _insert(
        self, return_links=False
    ) -> Union[Integer, List[Coroutine], None]:
        """
        Internal Only:
            return_links - will request table_link insertions be returned to
                run later, needed when inserting `DataBaseModel`s with related
                `DataBaseModel` attributes
        """
        table = self.__class__.get_table()
        database = self.__metadata__.database

        values, links = await self.serialize(self.dict(), insert=True)

        query = table.insert(values)
        result = None
        try:
            result = await self.__metadata__.database.execute(query, values)
        except Exception as e:
            database.log.error(f"error inserting into {table.name} - error: {repr(e)}")
            for link in links:
                link.close()
            if return_links:
                return []
            # raise e

        if return_links:
            return links

        # run links in chain
        try:
            await asyncio.gather(*[asyncio.shield(l) for l in links if l])
        except Exception:
            pass

        return result

    async def insert(self) -> Optional[int]:
        """
        <b>Insert<b>
        Insert the contents of a `DataBaseModel` instance in the database
            if the values of the `DataBaseModel` primary key do not exist
        ```
        model = Models(id='abcd1234', data='data')
        await model.insert()
        ```
        """
        result: int = await self._insert()
        return result

    @classmethod
    async def get(
        cls: Type[T],
        *p_key_condition: Tuple[DataBaseModelCondition],
        backward_refs=True,
        **primary_key_input,
    ) -> T:
        if not p_key_condition:
            for k in primary_key_input:
                primary_key = cls.__metadata__.tables[cls.__name__]["primary_key"]
                if k != cls.__metadata__.tables[cls.__name__]["primary_key"]:
                    raise Exception(f"Expected primary key {primary_key}=<value>")
                p_key_condition = [getattr(cls, primary_key) == primary_key_input[k]]

        result = await cls.filter(*p_key_condition, backward_refs=backward_refs)
        return result[0] if result else None

    @classmethod
    async def create(cls: Type[T], **kwargs) -> T:
        new_obj = cls(**kwargs)
        await new_obj.insert()
        return new_obj


class TableMeta(DataBaseModel):
    table_name: str = PrimaryKey()
    model: dict
    columns: list


class DatabaseInit(DataBaseModel):
    database_url: str = PrimaryKey()
    status: Optional[str] = None
    reservation: Optional[str]
