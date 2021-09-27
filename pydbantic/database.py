import time
import asyncio
import sqlalchemy
from pickle import dumps
from typing import List

from databases import Database as _Database
from pydbantic.core import DataBaseModel, TableMeta
from pydbantic.cache import Cache, Redis
import logging

class Database():
    def __init__(self,
        database: _Database,
        tables: list,
        cache_enabled: bool = False,
        redis_url: str = None,
        logger: logging.Logger = None,
        debug: bool = False,
    ):
        self.database = database
        self.tables = []
        self.cache_enabled = cache_enabled
        self.engine = sqlalchemy.create_engine(
            str(self.database.url),
            connect_args={'check_same_thread': False}
            if 'sqlite' in str(self.database.url) else {}
        )

        self.metadata = sqlalchemy.MetaData(self.engine)

        if self.cache_enabled:
            cache_config = {'redis_url': redis_url} if redis_url else {}
            self.cache = Redis(**cache_config)

        # logging setup # 
        self.log = logger
        self.debug = debug
        level = None if not self.debug else 'DEBUG'
        self.setup_logger(logger=self.log, level=level)

        # setup table_metadata table
        self.TableMeta = TableMeta
        self.TableMeta.setup(self)

        for table in tables:
            self.add_table(table)

        setattr(self, table.__name__, table)

        self.metadata.create_all(self.engine)

    def setup_logger(self, logger=None, level=None):
        if logger:
            return

        level = logging.DEBUG if level == 'DEBUG' else logging.WARNING
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            datefmt='%m-%d %H:%M'
        )
        self.log = logging.getLogger(f'pydb')
        self.log.propogate = False
        self.log.setLevel(level)
        
    async def update_table_meta(self, table: DataBaseModel, existing=False):
        table_fields = {}
        table_fields_list = []
        for _, field in table.__fields__.items():
            table_fields[field.name] = {
                'name': field.name,
                'type': field.type_,
                'required': field.required
            }
            table_fields_list.append(table_fields[field.name])
        
        
        table_meta = self.TableMeta(
            table_name=table.__name__, 
            model=table_fields, 
            columns=table.convert_fields_to_columns(model_fields=table_fields_list, update=True)
        )
        
        if not existing:
            await table_meta.insert()
        else:
            await table_meta.update()
    def add_table(self, table: DataBaseModel):
        
        if not table in self.tables:
            self.tables.append(table)
        table.setup(self)

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
            if mig_details['table'] in migration_order:
                continue 

            for foreign_key in mig_details['table'].__metadata__.tables[table_name]['foreign_keys']:
                migration_order.extend(Database.determine_migration_order(migrations_required))
            
            migration_order.append(mig_details['table'])
        return migration_order

    async def compare_tables_and_migrate(self) -> None:
        """
        compare existing table schema's to current, migrate if required
        """

        # get list of all tables in table_metadata table

        _meta_tables = await self.TableMeta.select('*')

        # determine list of tables requiring migration
        migrations_required = {}

        meta_tables = {table.table_name: table for table in _meta_tables}

        for table in self.tables:
            is_migration_required = False
            migration_blame = []
            
            if not table.__name__ in meta_tables:
                table_ref = table.__metadata__.tables[table.__name__].get('table') 
                await self.update_table_meta(table)
                if table_ref is not None:
                    table.__metadata__.tables[table.__name__]['table'] = table_ref
                continue

            # check for new columns
            for field in table.__fields__:
                existing_model = meta_tables[table.__name__].model
                if not field in existing_model:
                    is_migration_required = True
                    
                    migration_blame.append(f"New Column: {field}")
                    continue

                if not table.__fields__[field].type_ == existing_model[field]['type']:
                    migration_blame.append(f"Modified Column: {field}")
                    is_migration_required = True

            # check for deleted columns
            for field in meta_tables[table.__name__].model:
                if not field in table.__fields__:
                    is_migration_required = True
                    migration_blame.append(f"Deleted Column: {field}")
            if is_migration_required:
                migrations_required[table.__name__] = {'blame': migration_blame, 'table': table}

        # determine order of migrations 
        # migrations should run first against foreign tables, if needed so that dependent tables 
        # are able to successfully migrated, if needed. 
        migration_order = Database.determine_migration_order(migrations_required.copy())
        
        if migrations_required:
            self.log.warning(f"Migrations may be required. Will attempt in order: {migration_order}")

        for table in migration_order:
            migration_blame = migrations_required[table.__name__]['blame']
            self.log.warning(f"Migration Required: {migration_blame}")
            # migration required - re-create table with new schema
            to_select =[c for c in meta_tables[table.__name__].model]

            # create old table , named with timestamp 
            self.metadata.remove(table.__metadata__.tables[table.__name__]['table'])

            aliases = {
                column['new_name']:  column['old_name']
                for column in table.__renamed__
            } if hasattr(table, '__renamed__') else {}

            old_table_columns = table.convert_fields_to_columns(include=to_select, alias=aliases)
            
            old_table = sqlalchemy.Table(
                table.__name__,
                self.metadata,
                *old_table_columns
            )

            table.__metadata__.tables[table.__name__]['table'] = old_table

            migration_table = sqlalchemy.Table(
                table.__name__ + f'_{int(time.time())}',
                self.metadata,
                *meta_tables[table.__name__].columns
            )
            
            migration_table.create(self.engine)

            # read from existing table and feed into migration table 
            # selecting only previously existing columns &&
            # columns which still exist in the current model.
            
            to_select = [
                c for c in meta_tables[table.__name__].model 
                if c in table.__fields__ or c in aliases.values()
            ]

            
            rows = await table.select(*to_select, alias={v: k for k,v in aliases.items()})

            insert_into_migration = migration_table.insert()

            values = []
            for row in rows:
                row_data = {}
                for k,v in row.dict().items():
                    row_data[k] = v
                    if k in aliases:
                        row_data[aliases[k]] = row_data.pop(k)
                        continue
                    if not k in migration_table.c:
                        del row_data[k]
                    
                values.append(
                    row.serialize(row_data)
                )

            values = await asyncio.gather(*values)
            
            for query_values in values:
                await self.execute(insert_into_migration, query_values)
        
            # drop existing table
            table.__metadata__.tables[table.__name__]['table'].drop()
            self.metadata.remove(table.__metadata__.tables[table.__name__]['table'])

            # create new table with new schema 
            table.__metadata__.tables[table.__name__]['table'] = migration_table
            new_table = sqlalchemy.Table(
                table.__name__,
                self.metadata,
                *table.convert_fields_to_columns()
            )
            new_table.create(self.engine)

            # load new table with old data, feeding from table+timestamp & default value of new row(s)
            rows = await table.select(*to_select, alias={v: k for k,v in aliases.items()})
            table.__metadata__.tables[table.__name__]['table'] = new_table
            
            for row in rows:
                await row.insert()
            
            # update TableMeta with new Model
            await self.update_table_meta(table, existing=True)

            table.__metadata__.tables[table.__name__]['table'] = new_table
            


    async def execute(self, query, values):
        """execute an insert, update, delete table query &
            invalidates cache for associated table if 
            cache is enabled
        """
        if self.cache_enabled:
            await self.cache.invalidate(query.table.name)

        self.log.debug(f"database query: {query} - values {values}")
        return await self.database.execute(query=query, values=values)

    async def execute_many(self, query, values):
        """execute bulk insert"""
        if self.cache_enabled:
            await self.cache.invalidate(query.table.name)

        return await self.database.execute(query=query, values=values)
    
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
        row = await self.database.fetch_all(query=query)

        if self.cache_enabled and row:
            # add to database cache with table name flag
            await self.cache.set(dumps(cache_check), (row, table_name))
        return row

    @classmethod
    async def create(cls,
        DB_URL: str,
        tables: list,
        cache_enabled: bool = False,
        redis_url: str = None,
        logger: logging.Logger = None,
        debug: bool = False,
    ):
        database = _Database(DB_URL)
        await database.connect()

        cache_config = {'cache_enabled': cache_enabled}
        if redis_url and cache_enabled:
            cache_config['redis_url'] = redis_url

        easy_db = cls(
            database,
            tables,
            logger=logger,
            debug=debug,
            **cache_config
        )
        
        await easy_db.compare_tables_and_migrate()
        
        return easy_db