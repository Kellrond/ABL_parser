class Parser:
    debug = True

class Db:
    host = 'localhost'
    user = 'jordan'
    password = 'webhostPsa#1'
    dbname = 'pos' 
    port = 5432

class Documentation:
    docs_folder_list = ['./pos'] 

class Language:
    scraped_keywords = 'language/scraped/keywords.txt'
    scraped_urls = 'language/scraped/keyword_links.txt'

class Logging:
    # Set what level of logging you want. Level 2 includes 0 and 1 etc. 
    #   0 = Fatal   1 = Error   2 = Warn    3 = Info    4 = Debug   5 = Verbose
    log_terminal_level = 1
    log_database_level = -1
    log_flatfile_level = 1

    # Location of gro.log and any other log flat files
    log_dir  = "logs"
    log_file = 'parser.log'
    performance_file = 'performance.log'

    # Performance testing can give you insights as to possible issues in the code. ie. things taking way 
    # too long to execute in one section of code.
    test_performance = True  

    # Minimal testing reduces the verbosity of the performance logs
    minimal_test = False # Currently not implemented!! Need to pass the minimal = True parameter in the decorator

    # When both db and file are selected there is a significant performance hit. So use one or the other
    # or fix this. Possibly by caching writes to the file and/or db to reduce the transactions. 
    performance_to_db   = False
    performance_to_file = False