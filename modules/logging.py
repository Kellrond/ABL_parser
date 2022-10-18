import  datetime as dt
from    glob import glob
import  os 
from    time import perf_counter
# External
import  psycopg2
#Internal
import  conf
from    modules import utilities

# The generator object should be in the files scope so that all the log instances share the generator
perf_exec_start = utilities.generateIntegerSequence()
perf_exec_end   = utilities.generateIntegerSequence()

# TODO: This should be made more performant. Ideas include caching Db writes to be able to do more in bulk. 
# Should speed test and see what is the best option for speed / memory use. Perhaps write to file then ingest 

class Log():
    ''' Handles logging throughout the app. There are 6 levels of logging currently

            - 0: Fatal
            - 1: Error
            - 2: Warn
            - 3: Info
            - 4: Debug
            - 5: Verbose

        There is a database connection in the dbLog method. This is here because the database will
        create logs when writing and depending on configuration it would be possible to end up in 
        an endless loop. Python will throw a maximum recursion error before you fill up the storage
        so it's not going to destroy your machine, but should be left. 

        Usage: 
            `log = logging.Log(__name__)`
    '''

    log_files_exist = False
    # While testing we want to silence logging globally except when testing logging 
    test_mode = False

    def __init__(self, src_name: str) -> None:
        self.src_name = src_name
        self.config = conf.Logging
        self.db_config = conf.Db
        self.pid = os.getpid()

        if not Log.log_files_exist:
            Log.log_files_exist = (self.__check_for_log_folder() and self.__check_for_log_files())
            if not Log.log_files_exist:
                self.init_logs()
                Log.log_files_exist = True
        
    @classmethod
    def from_test_conf(cls, config, db_config, src_name:str):
        ''' Instantiates a class using the test configuration passed in. Normal or test instances
            of Log will check for their files at instantiation. 

            
            Params: 
                - config: a config file loaded from the test/config dir or otherwise
                - db_config: since the logger writes to the db and the db logs, it's better to pass
                  in a connection config
                - src_name: __name__. Use that every time. 
        '''
        test_class = cls(src_name)
        test_class.config = config
        test_class.db_config = db_config
        # Set logger to testing to mute all output 
        cls.test_mode = True
        
        # Make sure the test log file is there
        with open(f'{config.log_dir}/{config.log_file}', 'a'):
            pass 
        with open(f'{config.log_dir}/{config.performance_file}', 'a'):
            pass 

        return test_class

    def fatal(self, txt: str) -> None:
        ''' Log level: 0 - FATAL
        
            This log level is for fatal errors which cause the application to crash or would have
            if they were not in a try: block
        '''
        log = self.__return_log_dict(0,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)
        
    def error(self, txt: str) -> None:
        ''' Log level: 1 - ERROR 

            Use error for significant but recoverable errors
        '''
        log = self.__return_log_dict(1,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)

    def warn(self, txt: str) -> None:
        ''' Log level: 2 - WARN
        
            Something seems off or some configuration is unsafe
        '''
        log = self.__return_log_dict(2,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)

    def info(self, txt: str) -> None:
        ''' Log level: 3 - INFO
        
            Things you just might want to know
        '''
        log = self.__return_log_dict(3,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)

    def debug(self, txt: str) -> None:
        ''' Log level: 4 - DEBUG
        
            This should be for development level message. Try not to make it too verbose, 
            there's a level for that.
        '''
        log = self.__return_log_dict(4,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)

    def verbose(self, txt: str) -> None:
        ''' Log level: 5 - VERBOSE
        
            Warning: Very noisy
            
            When you absolutely must know everything that's going on. 
        '''
        log = self.__return_log_dict(5,txt)
        if self.test_mode == False:
            self.__log_console_write(log)
            self.__log_db_write(log)
            self.__log_file_write(log)   
    
    def performance(self, func):
        ''' This function is a decorator. At some point it might be worth splitting it into it's own class 
            that way we can include logger performance. 

            Usage:
                `@log.performance`
        '''
        def performance_wrapper(*args, **kwargs):
            ''' Performance testing is an expensive operation and can slow the operation of the system.
                However the knowledge you can gleam from this is worth the expense. But it doesn't need
                to run all the time.  
            ''' 
            if not self.config.test_performance:
                return func(*args, **kwargs)

            is_minimal_log = kwargs.get('minimal', False)
            if self.config.minimal_test and not is_minimal_log:
                return func(*args, **kwargs)

            # Setup
            start_time = perf_counter()
            start_id   = next(perf_exec_start)
            # Function
            result = func(*args, **kwargs)
            # Wrap up
            end_time = perf_counter()
            end_id   = next(perf_exec_end)
            duration = end_time - start_time
            log = {
                'start_id': start_id,
                'end_id': end_id,
                'pid': self.pid,
                'timestamp': dt.datetime.now(),
                'module': self.src_name,
                'name': func.__name__,
                'duration': duration,
                } 
            
            self.__perf_db_write(log)
            self.__perf_file_write(log)
            return result
        return performance_wrapper


    def init_logs(self) -> None:
        ''' Ensure that the required folders and files are in place to start logging '''
        if self.__check_for_log_folder() == False:
            os.makedirs(self.config.log_dir)
        log_list = [self.config.log_file, self.config.performance_file]
        for log in log_list:
            with open(f'{self.config.log_dir}/{log}', 'a'):
                pass         

    def delete_dot_logs(self) -> None:
        ''' Remove all .log files created '''
        os.remove(f'{self.config.log_dir}/{self.config.log_file}')
        os.remove(f'{self.config.log_dir}/{self.config.performance_file}')


    # Helper functions

    def __return_log_dict(self, level:int, log_txt:str) -> dict:
        ''' The function helps to reduce error by producing log dictionaries 

            Params: 
                - level: gives the level and text name to the log
                - log_txt: the message to be logged
        '''
        log_names = {0:'FATAL', 1:'ERROR', 2:'WARN', 3:'INFO', 4:'DEBUG', 5:'VERBOSE'}
        return {
            'timestamp': dt.datetime.now(),
            'pid': self.pid,
            'level': level,
            'name': log_names.get(level),
            'module': self.src_name,
            'log': str(log_txt),
        }

    def __check_for_log_folder(self) -> bool:
        ''' Before we can have a log file there must be a log folder '''
        folder_list = glob('**/', recursive=True)
        return ('logs\\' in folder_list)

    def __check_for_log_files(self) -> bool:
        ''' If the log file does not exist, it will may throw and error when accessed. '''
        file_list = glob(f'{self.config.log_dir}/**/*.*', recursive=True)
        x = [ 1 for file in file_list if file == self.config.log_file ]
        return sum(x) > 0


    # Output logs
    def __log_console_write(self, log: dict):
        ''' Outputs the log information to terminal. 

            Params:
                - log: a dictionary created from the methods above
        '''
        if log.get('level') <= self.config.log_terminal_level:
            log_lines = log.get('log','').split('\n')
            for line in log_lines:
                if line != '': 
                    print(f"{log.get('timestamp')}  {log.get('name')}\t{log.get('module'): <20}\t{line}")
 
    def __log_file_write(self, log: dict): 
        ''' Writes the log to flat file 
        
            Params:
                - log: a dictionary created from the methods above
        '''
        if log.get('level') <= self.config.log_flatfile_level:
            with open(f'{self.config.log_dir}/{self.config.log_file}', 'a') as file:
                log_lines = log.get('log','').split('\n')
                for line in log_lines: 
                    file.write(f"{log.get('timestamp')}\t{log.get('pid')}\t{log.get('name')}\t{log.get('module')}\t{line}\n")

    def __log_db_write(self, log: dict): 
        ''' Writes the log to the database. This has a basic pattern to create the db connection and
            should be left this way. The database creates logs and can end up in a recursive loop.

            Params:
                - log: a dictionary created from the methods above
        '''
        if log.get('level') <= self.config.log_database_level:
            # Log must be manually input to avoid a feedback loop of db adds triggering logs which get added to db
            db_conn = psycopg2.connect(
                    host=self.db_config.host,
                    user=self.db_config.user,
                    password=self.db_config.password,
                    port=self.db_config.port,
                    dbname=self.db_config.dbname
                )

            tempLog = { k:v for k, v in log.items() if k != 'name'}

            columns = ", ".join(tempLog.keys())
            placeholders = ", ".join([ '%s' for x in tempLog.values() ])  
            values = tuple(tempLog.values())
            sql = f'''
                INSERT INTO logs ({ columns })
                VALUES ({ placeholders })
            '''
            try:
                with db_conn.cursor() as cursor:
                    cursor.execute(sql, values)   
                    db_conn.commit()    
                db_conn.close()
            except Exception as e:
                db_conn.close()
                raise e

    def __perf_db_write(self, log:dict):
        ''' Write the performance data to database. The database connection is created on the spot

            Params:
                - log: a dictionary created from the methods above
        '''
        if self.config.performance_to_db:
            # Log must be manually input to avoid a feedback loop of db adds triggering logs which get added to db
            db_conn = psycopg2.connect(
                    host=self.db_config.host,
                    user=self.db_config.user,
                    password=self.db_config.password,
                    port=self.db_config.port,
                    dbname=self.db_config.dbname
                )

            tempLog = log
            # tempLog = { k:v for k, v in log.items() if k != 'name'}

            columns = ", ".join(tempLog.keys())
            placeholders = ", ".join([ '%s' for x in tempLog.values() ])  
            values = tuple(tempLog.values())
            sql = f'''
                INSERT INTO performance_logs ({ columns })
                VALUES ({ placeholders })
            '''
            try:
                with db_conn.cursor() as cursor:
                    cursor.execute(sql, values)   
                    db_conn.commit()    
                db_conn.close()
            except Exception as e:
                db_conn.close()
                raise e

    def __perf_file_write(self, log:dict):
        if self.config.performance_to_file:
            line = f"{log.get('timestamp')}\t{log.get('pid')}\t{log.get('start_id')}\t{log.get('end_id')}\t{log.get('module')}\t{log.get('name')}\t{log.get('duration'):10.10f}\n"
            with open(f'{self.config.log_dir}/{self.config.performance_file}', 'a') as file:
                file.write(line)


