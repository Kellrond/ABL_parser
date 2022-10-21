# External dependencies
import  psycopg2, traceback
# Internal
from modules.logging import Log
import conf

log = Log(__name__)

class Db:
    ''' Database class that handles connection to the database. Much of this is
        a wrapper around psycopg2 so some methods are just mirroring 
        
        By default commits occur after every method call where needed. We want to 
        capture as much data as we can. A bad output from one function or sensor 
        should not prevent other data from being written. Transactions should be 
        as small as possible.

        conn:
            connection to the database. Or more accurately a connection to psycopg2
            This abstraction exists to make switching to another database vendor a 
            little easier. 

            `conn == None` is the tell that there is no connection to the database.
            That is not how to close a connection. Please use the close() method.

    '''
    @log.performance
    def __init__(self) -> None:
        self.conn = None
        log.verbose('Class instantiated')

    def __del__(self):
        ''' If the object is deleted via `del db` close the connection to avoid 
            leftover database connections. 
        '''
        if self.conn is not None:
            self.conn.close()

    @classmethod
    @log.performance
    def from_test_conf(cls, config):
        ''' Instantiates a class using the test configuration passed in. '''
        test_class = cls()
        test_class.config = config
        log.debug('Test class instantiated')
        return test_class

    # Connection controls
    @log.performance
    def commit(self):
        ''' Commit the last set of statements to the database '''
        self.conn.commit()
        log.verbose('Transaction committed')

    @log.performance
    def connect(self):
        ''' If inactive open a connection to the database '''
        if self.conn is None:
            try:
                self.conn = psycopg2.connect(
                    host=conf.Db.host,
                    user=conf.Db.user,
                    password=conf.Db.password,
                    port=conf.Db.port,
                    dbname=conf.Db.dbname
                )
                log.verbose('Connected')      
            except Exception as e:
                log.error(traceback.format_exc())
                raise e

    @log.performance
    def close(self):
        ''' If active close the database connection '''
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            log.verbose('Connection closed')

    @log.performance
    def initialize(self):
        ''' Drop all tables and load the schema.sql files '''
        with open('schema.sql', 'r') as sql:
            self.execute(sql.read())

    # Table functions
    
    @log.performance
    def createTable(self, table: dict, drop_if_exists=False) -> None:
        ''' Create a table from the dictionary passed in 
        
            The dictionary must contain the key value pair of
            `'__table__': 'example_name'`

            The rest of the items in the dictionary should be in key value pairs. 

            Usage:
                `dict = { 
                    '__table__': 'example_name',
                    'id': 'SERIAL PRIMARY KEY',
                    'col1': INTEGER,
                    'col2': TEXT  
                }
                db.createTable(dict)
                `

            Params:
                - table: the dictionary as described above 
                - drop_if_exists: drops an existing table. False by default to prevent 
                  accidental data loss
        '''
        table_name = ''     
        if table.get('__table__'):
            table_name = table.pop('__table__')
        else:
            log.performance('Db.createTable')
            raise Exception('Create table dict requires "__table__"')

        if drop_if_exists:
            sql = f"DROP TABLE IF EXISTS {table_name};"
            self.execute(sql)
        else:
            # If not dropping table check if table exists and leave if it exists
            sql = f"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            results = self.query(sql)
            results = [v.get('table_name') for v in results]
            if table_name in results:
                log.performance('Db.createTable')
                return

        # Build the create table statement
        sql = f'CREATE TABLE {table_name} ( '
        for column_name,meta in table.items():
            sql += f' {column_name} {meta},'
        
        # Remove the trailing comma or postgres throws error
        sql = sql[:-1] + ');'
        self.execute(sql)
        log.info(f'Table { table_name } created')


    @log.performance
    def nextId(self, table_name: str): 
        ''' Get the next id in a sequence. Be aware of table with serial or
            auto-incrementing primary keys. They do not get passed keys as they generate
            their own.  

            Returns None if passed a table with multiple primary keys, a serialized key,
            or the table does not exist.

            Params:
                - table_name: just pass in the table name and the rest will get discovered
        '''
        primary_keys = self.getPrimaryKeysFromTable(table_name)
        
        # Check for serialized and return non if found
        if sum([1 for pk in primary_keys if pk.get('autoInc') == True]) > 0:
            return None

        # If there is more than one key, it's a composite and the key is likely put together 
        # from two other primary keys 
        if len(primary_keys) == 1:
            sql = f'SELECT MAX({ primary_keys[0].get("col_name") }) FROM { table_name }'
            max_id = self.scalar(sql)
            # If no records exist then return 1 as the starting id
            if max_id == None:
                return 1
            return max_id + 1
        

    @log.performance
    def getPrimaryKeysFromTable(self, table_name: str) -> list:
        ''' The primary keys a good details to have when working with a table

            My recommendation for primary keys it to use SERIAL PRIMARY KEY
            This is more performant and saves having to get the next Id 
        
            Params:
                - table_name: just the name of a table
        '''
        self.connect()
        # Find the primary keys of the table
        sql = f'''
            SELECT c.column_name, c.data_type, c.column_default
            FROM information_schema.table_constraints tc 
            JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name) 
            JOIN information_schema.columns AS c ON c.table_schema = tc.constraint_schema
            AND tc.table_name = c.table_name AND ccu.column_name = c.column_name
            WHERE constraint_type = 'PRIMARY KEY' and tc.table_name = '{ table_name }';
            '''
        result = self.query(sql)

        primary_keys = []
        for pk in result:
            auto_inc_key = str(pk.get('column_default','')).find(table_name) != -1 
            primary_keys.append({
                'col_name': pk.get('column_name'),
                'data_type': pk.get('data_type'),
                'autoInc': auto_inc_key
            })
            
        return primary_keys

    # Queries with a return
    @log.performance
    def query(self, sql: str) -> list:
        ''' Query the database, returns a dictionary

            Some data types may need processing upon return. Notably JSON
            will get returned as a json string. 
        '''
        if sql.strip().upper()[0:6] != 'SELECT':
            raise Exception('Query must begin with SELECT. Use execute for other actions')
        
        self.connect()
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            records = [ dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()
            return records

    @log.performance
    def queryOne(self, sql: str) -> dict:
        ''' Like query() but returns a single record as a dictionary

            Params:
                - sql: Statement must start with SELECT 
        '''
        if sql.strip().upper()[0:6] != 'SELECT':
            raise Exception('Query must begin with SELECT')

        self.connect()
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            try:
                columns = [desc[0] for desc in cursor.description]
                records = dict(zip(columns, cursor.fetchone()))
                cursor.close()
                return records        
            except:
                return
 
    @log.performance
    def scalar(self, sql):
        ''' Returns a scalar (single element) result. SQL statement passed in must return 
            only one row. If multiple columns are returned it will return the value in the 
            first column.

            `db.scalar('SELECT sum(val) FROM examp_tbl')` 
            
            Params:
                -sql: SQL statement must only return a single value. If
        '''
        self.connect()
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            records = cursor.fetchall()
            
            if len(records) == 1:
                records = records[0]
            elif records == []:
                return None
            else:
                raise Exception('Scalar SQL statements must return only one result')
            cursor.close()
            return records[0] 

    @log.performance
    def execute(self, sql: str, autoCommit=True) -> bool:
        ''' Execute a SQL statement which does not return a result. ie. DELETE, UPDATE, etc. 
            
            Params:
                - sql: any SQL statement which does not return a result
                - autoCommit=True: set to false when you must ensure all events pass or none at all 
        '''
        self.connect()
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
        if autoCommit:
            self.commit()

    @log.performance
    def add(self, dbo: dict or list, single_transaction=True):
        ''' Add one or many row. Rows are inserted individually so in a list of
            records you may insert to multiple rows at a time. 

            Security note:
                Using `add()` will avoid SQL injection attacks due to the parameterization of the input values.
                If you are exposing this to the internet, you should always consider injection attacks. Taking 
                a reading from a sensor and writing that value directly to an insert statement is not dangerous.
                But you should think twice if dealing with anything with human input.  

            Params:
                - data: either a dict or a list of dicts. DICTIONARIES MUST HAVE '__table__': 'table_name'
                - single_transaction: when left at the True default, commits at the end of all the inserts
                  this is to help ensure data integrity. If keeping all data at all cost is your preference 
                  set this to False.       
        '''
        if type(dbo) == dict:
            dbo =[dbo]

        for row in dbo:
            table_name = ''     
            if row.get('__table__'):
                table_name = row.pop('__table__')
            else:
                raise Exception('Create table dict requires "__table__"')        

            # Check that the dict isn't missing a id when there should be one. 
            primary_keys = self.getPrimaryKeysFromTable(table_name)

            # Check if there is more than one primary key If there is it must be a composite
            # key and we shouldn't guess at what it is. 
            if len(primary_keys) > 1: 
                for pk in primary_keys:
                    if row.get(pk.get('col_name'), None) == None:
                        raise Exception('Composite key missing from dictionary passed into add()')
            # With only 1 key check it's serial and if exists pop it. 
            elif len(primary_keys) == 1: 
                pk = primary_keys[0]
                if pk.get('autoInc') == True:  
                    row[pk.get('col_name')] = 0
                    row.pop(pk.get('col_name'))
                else: 
                    # Check if the key exists in the data
                    if row.get(pk.get('col_name')) == None:
                        # If the key data type is integer then get the next key
                        if pk.get('data_type','').lower() == 'integer':
                            row[pk.get('col_name')] = self.nextId(table_name)
                        else:
                            raise Exception('Primary key missing from dictionary passed into add()')

            columns = ", ".join(row.keys())
            placeholders = ", ".join([ '%s' for x in row.values() ])  
            values = tuple(row.values())

            sql = f'''
                INSERT INTO { table_name } ({ columns })
                VALUES ({ placeholders })
            '''

            # After SQL statement written add the __table__ back to the row dict
            row['__table__'] = table_name

            self.connect()
            try:
                with self.conn.cursor() as cursor:
                    cursor.execute(sql, values)  
                if not single_transaction:
                    self.commit()
                log.verbose(f'Db.add() inserted row in {table_name}')
            except Exception as e:
                log.error(f'Db.add() failed to add data to table {table_name}')
                log.error(traceback.format_exc())
                self.close()
                raise e

        if single_transaction: 
            self.commit()   
        log.debug(f'Db.add() {len(dbo)} row(s) to database')  

    @log.performance
    def upsert(self, dbo: dict):
        ''' UP-dates or in-SERTs a record as necessary 
                Params:
                    - table: the table name you want to add / update 
                    - dbo: database object a.k.a. dict 
        '''
        table_name = dbo.pop('__table__')
        # Prepare the strings for insertion into query
        primary_keys = [ x.get('col_name') for x in self.getPrimaryKeysFromTable(table_name)] 
        primary_keys = ", ".join(primary_keys)
        columns = ", ".join(dbo.keys())
        excluded_cols = ", ".join([ f"EXCLUDED.{col}" for col in dbo.keys() ])
        placeholders  = ", ".join([ '%s' for x in dbo.values() ])  
        values = tuple(dbo.values())
        
        # If upserting only a single column the () would break the statement. Putting them back is len > 1
        columns_on_conf = ''
        if len(dbo) > 1:
            columns_on_conf = f'({ columns })'
            excluded_cols = f'({ excluded_cols })'

        sql = f'''
            INSERT INTO { table_name } ({ columns })
            VALUES ({ placeholders })
            ON CONFLICT ({ primary_keys }) DO UPDATE SET
            { columns_on_conf } = { excluded_cols }
        '''
        self.connect()
        with self.conn.cursor() as cursor:
            cursor.execute(sql, values)  
        log.verbose(f'Db.upsert() rows into { table_name }')
        # Restore the table name to the dbo incase it's being used again
        dbo['__table__'] = table_name
