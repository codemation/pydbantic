import asyncio
import logging
import time
import uuid
from copy import deepcopy
from pickle import dumps
from typing import Optional

import sqlalchemy
from alembic import context
from alembic.migration import MigrationContext
from alembic.operations import Operations
from databases import Database as _Database
from sqlalchemy import create_engine

from pydbantic.cache import Redis
from pydbantic.core import BaseMeta, DatabaseInit, DataBaseModel, TableMeta
from pydbantic.translations import DEFAULT_TRANSLATIONS


class Database:
    def __init__(
        self,
        db_url: str,
        tables: list,
        cache_enabled: bool = False,
        redis_url: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        debug: bool = False,
        testing: bool = False,
        use_alembic: bool = False,
    ):
        self.connection_map = {}
        self.DB_URL = db_url
        self.tables = []
        self.cache_enabled = cache_enabled
        if "sqlite" in self.DB_URL.lower():
            self.db_type = "SQLITE"
        elif "postgres" in self.DB_URL.lower():
            self.db_type = "POSTGRES"
        elif "mysql" in self.DB_URL.lower():
            self.db_type = "MYSQL"

        self.testing = testing
        self.engine = sqlalchemy.create_engine(
            self.DB_URL,
            connect_args={"check_same_thread": False}
            if "sqlite" in str(self.DB_URL)
            else {},
        )
        self.use_alembic = use_alembic
        self.__metadata__: BaseMeta = BaseMeta()

        self.DEFAULT_TRANSLATIONS = DEFAULT_TRANSLATIONS

        self.metadata = sqlalchemy.MetaData(self.engine)

        if self.cache_enabled:
            cache_config = {"redis_url": redis_url} if redis_url else {}
            self.cache = Redis(**cache_config)

        # logging setup #
        self.log: logging.Logger = logger
        self.debug = debug
        level = None if not self.debug else "DEBUG"
        self.setup_logger(logger=self.log, level=level)

        # setup table_metadata table
        self.TableMeta = TableMeta
        self.TableMeta.setup(self)
        self.TableMeta.generate_model_attributes()

        self.DatabaseInit = DatabaseInit
        self.DatabaseInit.setup(self)
        self.DatabaseInit.generate_model_attributes()

        for table in tables:
            table.update_forward_refs()

        for table in tables:
            self.add_table(table)

        for _, table in DatabaseInit.__metadata__.tables.items():
            table["model"].generate_model_attributes()

        if self.testing:
            self.testing_setup()

        # allow disabling of automatic migrations to allow
        # integration with alembic
        if not use_alembic:
            self.metadata.create_all(self.engine)
            if self.metadata is not self.tables[0].__metadata__.metadata:
                self.metadata = self.tables[0].__metadata__.metadata
            self.log.info(f"setup tables completed")

    def get_translated_column_type(self, input_type, primary_key: bool = False):
        """
        returns appropriate sqlalchemy.TYPE based on input_type, and indicate
        data should be serialized if sqlalchemy.LargeBinary is used
        """
        if input_type in self.DEFAULT_TRANSLATIONS[self.db_type]:
            column_config = self.DEFAULT_TRANSLATIONS[self.db_type][input_type]
        else:
            column_config = self.DEFAULT_TRANSLATIONS[self.db_type]["default"]

        if (
            self.db_type == "MYSQL"
            and column_config["column_type"] is sqlalchemy.LargeBinary
            and primary_key
        ):
            return self.DEFAULT_TRANSLATIONS[self.db_type]["default_primary"], True

        return column_config, column_config["column_type"] == sqlalchemy.LargeBinary

    def setup_logger(self, logger=None, level=None):
        if logger:
            return

        level = logging.DEBUG if level == "DEBUG" else logging.WARNING
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
            datefmt="%m-%d %H:%M",
        )
        self.log = logging.getLogger(f"pydbantic")
        self.log.propogate = False
        self.log.setLevel(level)

    async def update_table_meta(self, table: DataBaseModel, existing=False):
        table_fields = {}
        table_fields_list = []
        for _, field in table.__fields__.items():
            data_base_model = table.check_if_subtype({"type": field.type_})
            table_fields[field.name] = {
                "name": field.name,
                "type": field.type_ if not data_base_model else data_base_model,
                "required": field.required,
            }
            table_fields_list.append(table_fields[field.name])

        table_fields["primary_key"] = table.__metadata__.tables[table.__name__][
            "primary_key"
        ]

        table_meta = self.TableMeta(
            table_name=table.__name__,
            model=table_fields,
            columns=table.convert_fields_to_columns(
                model_fields=table_fields_list, update=True
            )[0],
        )

        if not existing:
            await table_meta.insert()
        else:
            await table_meta.update()

    def add_table(self, table: DataBaseModel):

        if not table in self.tables:
            self.tables.append(table)
        table.setup(self)

    def testing_setup(self):
        if self.testing:
            self.metadata.drop_all(self.engine)
            self.metadata.create_all(self.engine)

    @staticmethod
    def determine_migration_order(migrations_required: dict):
        migration_order = []
        for table_name, mig_details in migrations_required.copy().items():
            if not table_name in migrations_required:
                continue

            mig_details = migrations_required.pop(table_name)
            # determine if table has foreign references - if so, ensure foreign table is migrated
            # if required first

            # check if table was added already by dependent table
            if mig_details["table"] in migration_order:
                continue

            for foreign_key in mig_details["table"].__metadata__.tables[table_name][
                "foreign_keys"
            ]:
                migration_order.extend(
                    Database.determine_migration_order(migrations_required)
                )

            migration_order.append(mig_details["table"])
        return migration_order

    def alembic_migrate(self):
        """
        should be run from env.py with alembic
        """
        engine = create_engine(url=self.DB_URL)

        with engine.connect() as con:
            context.configure(
                connection=con, target_metadata=self.metadata, compare_type=True
            )

            with context.begin_transaction():
                context.run_migrations()

    async def compare_tables_and_migrate(self) -> None:
        """
        compare existing table schema's to current, migrate if required
        """
        if self.use_alembic:
            raise Exception(
                f"compare_tables_and_migrate cannot be called while using alembic"
            )

        reservation = str(uuid.uuid4())
        self.metadata.create_all(self.engine)

        # checkout database for migrations
        database_init = await DatabaseInit.get(database_url=self.DB_URL)

        if not database_init:
            database_init = DatabaseInit(
                database_url=self.DB_URL, reservation=reservation
            )
        else:
            database_init.reservation = reservation

        try:
            await database_init.save()
            await asyncio.sleep(3)
            check = await DatabaseInit.get(database_url=self.DB_URL)
            if check.reservation == reservation:
                check.status = "starting"
                await check.save()

        except Exception as e:
            self.log.warning(
                f"unable to reserve database for migration - perhaps another worker is running?"
            )

        if not database_init.reservation == reservation:
            while database_init.status != "ready":
                self.log.warning(
                    f"waiting for database migration to complete - status {database_init}"
                )
                await asyncio.sleep(5)
                database_init = await DatabaseInit.get(database_url=self.DB_URL)

        # get list of all tables in table_metadata table

        if self.testing and self.cache_enabled:
            await self.cache.redis.flushdb()

        meta_tables = {}

        for table in self.tables:
            table_meta = await self.TableMeta.get(table_name=table.__name__)
            if table_meta:
                meta_tables[table_meta.table_name] = table_meta

        # determine list of tables requiring migration
        migrations_required = {}

        for table in self.tables:
            is_migration_required = False
            migration_blame = []

            if not table.__name__ in meta_tables:
                table_ref = table.__metadata__.tables[table.__name__].get("table")
                await self.update_table_meta(table)
                if table_ref is not None:
                    table.__metadata__.tables[table.__name__]["table"] = table_ref
                continue

            existing_model = meta_tables[table.__name__].model
            # check for new columns
            aliases = (
                {column["new_name"]: column["old_name"] for column in table.__renamed__}
                if hasattr(table, "__renamed__")
                else {}
            )
            for field in table.__fields__:
                if not field in existing_model:
                    if "sqlite" in self.DB_URL:
                        is_migration_required = True
                        migration_blame.append(f"New Column: {field}")
                        continue

                    conn = self.engine.connect()
                    conn.dialect = self.engine.dialect
                    ctx = MigrationContext.configure(conn)
                    op = Operations(ctx)

                    if not field in aliases:
                        OP_str = "New"
                        if (
                            field
                            in table.__metadata__.tables[table.__name__][
                                "table"
                            ].columns
                        ):
                            new_column = table.__metadata__.tables[table.__name__][
                                "table"
                            ].columns[field]
                            result = op.add_column(table.__name__, new_column)
                    else:
                        OP_str = "Renamed"
                        existing_type_config = table.__metadata__.tables[
                            table.__name__
                        ]["column_map"][field][0]

                        result = op.alter_column(
                            table.__tablename__,
                            aliases[field],
                            nullable=False,
                            new_column_name=field,
                            type_=existing_type_config["column_type"](
                                *existing_type_config["args"],
                                **existing_type_config["kwargs"],
                            ),
                        )

                    await self.update_table_meta(table, existing=True)

                    new_table = sqlalchemy.Table(
                        table.__tablename__,
                        self.metadata,
                        *table.convert_fields_to_columns()[0],
                        extend_existing=True,
                    )
                    table.__metadata__.tables[table.__name__]["table"] = new_table

                    self.log.info(f"{OP_str} Column: {field} in {table.__tablename__}")
                    continue

                try:
                    issubclass(existing_model[field]["type"], DataBaseModel)
                except TypeError:
                    if (
                        not table.__fields__[field].type_
                        == existing_model[field]["type"]
                    ):
                        migration_blame.append(
                            f"Modified Column: {field} - from {existing_model[field]['type']} to {table.__fields__[field].type_}"
                        )
                        is_migration_required = True
                    continue

                if issubclass(existing_model[field]["type"], DataBaseModel):
                    current_model = DataBaseModel.check_if_subtype(
                        {"type": table.__fields__[field].type_}
                    )
                    if not current_model == existing_model[field]["type"]:
                        migration_blame.append(
                            f"Modified Column: {field} from {existing_model[field]['type']} -> {current_model}"
                        )
                        is_migration_required = True
                elif not table.__fields__[field].type_ == existing_model[field]["type"]:
                    migration_blame.append(
                        f"Modified Column: {field} - from {existing_model[field]['type']} to {table.__fields__[field].type_}"
                    )
                    is_migration_required = True

            table_p_key = table.__metadata__.tables[table.__name__]["primary_key"]
            if existing_model.get("primary_key") and (
                table_p_key != existing_model["primary_key"]
                and existing_model["primary_key"] in table.__fields__
            ):
                # Primary Key changed but previous key column still exists
                raise Exception(
                    f"Primary Key Changed from {existing_model['primary_key']} to {table_p_key}"
                    f"Modifying a table primary key with pydbantic is not allowed!"
                )

            # check for deleted columns
            for field in meta_tables[table.__name__].model:
                if field == "primary_key":
                    continue
                if not field in table.__fields__ and field not in aliases.values():
                    is_migration_required = True
                    migration_blame.append(f"Deleted Column: {field}")
            if is_migration_required:
                migrations_required[table.__name__] = {
                    "blame": migration_blame,
                    "table": table,
                }

        # determine order of migrations
        # migrations should run first against foreign tables, if needed so that dependent tables
        # are able to successfully migrated, if needed.
        migration_order = Database.determine_migration_order(migrations_required.copy())

        if migrations_required:
            self.log.info(
                f"Migrations may be required. Will attempt in order: {migration_order}"
            )

        for table in migration_order:
            migration_blame = migrations_required[table.__name__]["blame"]
            self.log.info(f"Migration Required: {migration_blame}")
            # migration required - re-create table with new schema
            to_select = [c for c in meta_tables[table.__name__].model]

            # create old table , named with timestamp
            self.metadata.remove(table.__metadata__.tables[table.__name__]["table"])

            old_table_columns = table.convert_fields_to_columns(
                include=to_select, alias=aliases
            )

            to_select = [
                c
                for c in meta_tables[table.__name__].model
                if (c in table.__fields__ or c in aliases.values())
            ]

            old_table = None
            if aliases and "sqlite" in self.DB_URL:
                self.metadata.remove(table.__metadata__.tables[table.__name__]["table"])

                old_table = sqlalchemy.Table(
                    table.__tablename__,
                    self.metadata,
                    *old_table_columns[0],
                )

                table.__metadata__.tables[table.__name__]["table"] = old_table

            if not "primary_key" in meta_tables[table.__name__].model:
                meta_tables[table.__name__].model["primary_key"] = [
                    *meta_tables[table.__name__].model.keys()
                ][0]

            migration_rows = await table.select(
                *to_select,
                alias={v: k for k, v in aliases.items()},
                primary_key=meta_tables[table.__name__].model["primary_key"],
                backward_refs=False,
            )

            # if table linked with relationship, drop link table
            for rel, link_table in table.__metadata__.tables[table.__name__][
                "relationships"
            ].items():
                self.log.info(
                    f"dropping related link-table {link_table.link_table.name}"
                )
                try:
                    link_table.link_table.drop(self.engine)
                except Exception:
                    pass
                self.metadata.remove(link_table.link_table)

            if old_table is None:
                old_table = sqlalchemy.Table(
                    table.__tablename__,
                    self.metadata,
                    *old_table_columns[0],
                )

            table.__metadata__.tables[table.__name__]["table"] = old_table

            # this is needed for tables migrated from 1.3.X -> 1.4.X
            [setattr(c, "identity", None) for c in meta_tables[table.__name__].columns]

            migration_table = sqlalchemy.Table(
                table.__tablename__ + f"_{int(time.time())}",
                self.metadata,
                *meta_tables[table.__name__].columns,
            )

            migration_table.create(self.engine)

            # read from existing table and feed into migration table
            # selecting only previously existing columns &&
            # columns which still exist in the current model.

            insert_into_migration = migration_table.insert()

            values = []
            for row in migration_rows:
                row_data = {}
                for k, v in row.dict().items():
                    row_data[k] = v
                    if k in aliases:
                        row_data[aliases[k]] = row_data.pop(k)
                        continue
                    if not k in migration_table.c:
                        del row_data[k]

                values.append(await row.serialize(row_data))

            for query_values, links in values:
                await self.execute(insert_into_migration, query_values)
                try:
                    await asyncio.gather(*links)
                except Exception:
                    pass

            # drop existing table
            old_config = deepcopy(table.__metadata__.tables[table.__name__])
            old_table = old_config["table"]
            table.__metadata__.tables[table.__name__]["table"].drop()
            self.metadata.remove(table.__metadata__.tables[table.__name__]["table"])

            # create new table with new schema
            table.__metadata__.tables[table.__name__]["table"] = migration_table
            new_table = sqlalchemy.Table(
                table.__tablename__,
                self.metadata,
                *table.convert_fields_to_columns()[0],
            )
            new_table.create(self.engine)

            # load new table with old data, feeding from table+timestamp & default value of new row(s)

            table.__metadata__.tables[table.__name__]["table"] = new_table

            for relationship, link_table in table.__metadata__.tables[table.__name__][
                "relationships"
            ].items():
                self.log.info(
                    f"re-creating related link-table {link_table.link_table.name}"
                )
                link_table.link_table.create()

            try:
                for row in migration_rows:
                    await row.insert()
            except Exception as e:
                self.log.exception(
                    (
                        f"Failed to migrate row {row} from old schema to {table.__name__} \n"
                        f"Consider annotating non-required fields with Optional[], set a default "
                        f"value or use factory method via Default(default=<callable>) \n\n"
                        f"Rolling back from {migration_table.fullname} to {table.__name__}"
                    )
                )

                # trigger rollback
                new_table.drop()
                self.metadata.remove(new_table)

                # get old columns from TableMeta
                meta_table = await self.TableMeta.get(table_name=table.__name__)

                rollback_table = sqlalchemy.Table(
                    table.__tablename__,
                    self.metadata,
                    *meta_table.columns,
                )

                rollback_table.create(self.engine)

                # using existing rows that originally built
                # previous migration table
                rollback_rows = migration_rows

                insert_into_rollback = rollback_table.insert()

                values = []
                for row in rollback_rows:
                    row_data = {}
                    for k, v in row.dict().items():
                        row_data[k] = v
                        if k in aliases:
                            row_data[aliases[k]] = row_data.pop(k)
                            continue
                        if not k in rollback_table.c:
                            del row_data[k]

                    values.append(row.serialize(row_data))

                values = await asyncio.gather(*values)

                for query_values, links in values:
                    await self.execute(insert_into_rollback, query_values)

                raise e

            # update TableMeta with new Model
            await self.update_table_meta(table, existing=True)

            table.__metadata__.tables[table.__name__]["table"] = new_table
            table.generate_model_attributes()

            self.metadata.create_all(self.engine)

        if reservation == database_init.reservation:
            database_init.status = "ready"
            await database_init.update()

    async def execute(self, query, values: dict = {}):
        """execute an insert, update, delete table query &
        invalidates cache for associated table if
        cache is enabled
        """
        if self.cache_enabled:
            await self.cache.invalidate(query.table.name)

        self.log.debug(f"database query: {query} - values {values}")

        async with self as conn:
            return await conn.execute(query=query, values=values)

    async def execute_many(self, query, values):
        """execute bulk insert"""
        if self.cache_enabled:
            await self.cache.invalidate(query.table.name)

        async with self as conn:
            return await conn.execute_many(query=query, values=values)

    async def fetch(self, query, table_name, values=None):
        """get a row from table matching query or pull from cache if enabled
        update cache with result if cache is enabled and database was used
        """
        cache_check = (str(query), values)
        if self.cache_enabled:
            cached_row = await self.cache.get(dumps(cache_check))
            if cached_row:
                self.log.debug(f"cache used - {cached_row}")
                return cached_row

        self.log.debug(f"running query: {query} with {values}")

        async with self as conn:
            row = await conn.fetch_all(query=query)

        if self.cache_enabled and row:
            # add to database cache with table name flag
            await self.cache.set(dumps(cache_check), (row, table_name))
        return row

    @classmethod
    def create(
        cls,
        DB_URL: str,
        tables: list,
        cache_enabled: bool = False,
        redis_url: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        debug: bool = False,
        testing: bool = False,
        use_alembic: bool = False,
    ):

        cache_config = {"cache_enabled": cache_enabled}
        if redis_url and cache_enabled:
            cache_config["redis_url"] = redis_url

        new_db = cls(
            DB_URL,
            tables,
            logger=logger,
            debug=debug,
            testing=testing,
            use_alembic=use_alembic,
            **cache_config,
        )

        return new_db

    def __await__(self):
        return self._migrate.__await__()

    async def _migrate(self):
        if self.use_alembic:
            return self

        async with self:
            self.log.info(f"starting migration check")
            await self.compare_tables_and_migrate()
            self.log.info(f"completed migration check")
        self.metadata.create_all(self.engine)

    async def db_connection(self):
        async with _Database(self.DB_URL) as connection:
            while True:
                status = yield connection
                if status == "finished":
                    self.log.debug(f"db_connection - closed")
                    break

    async def __aenter__(self):
        for conn_id in self.connection_map:
            if self.connection_map[conn_id]["conn"].ag_running:
                continue
            self.connection_map[conn_id]["last"] = time.time()
            return await self.connection_map[conn_id]["conn"].asend(None)

        conn_id = str(uuid.uuid4())
        db_connection = self.db_connection()
        self.connection_map[conn_id] = {"conn": db_connection, "last": time.time()}
        return await db_connection.asend(None)

    async def __aexit__(self, exc_type, exc, tb):
        for conn_id in self.connection_map.copy():
            if not self.connection_map[conn_id]["conn"].ag_running:
                if time.time() - self.connection_map[conn_id]["last"] > 120:
                    try:
                        await self.connection_map[conn_id]["conn"].asend("finished")
                    except StopAsyncIteration:
                        pass
                    del self.connection_map[conn_id]
