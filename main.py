import glob
# Internal
from modules.db import Db
import parse




db = Db()
db.initialize()

# Parse files and folders into the database. 
parse.file_paths.processFoldersAndFiles(db)
# parse.abl.parseFile('rn-newp2.p')

results = db.query('SELECT rel_path from files')
for x in results:
    parse.abl.parseFile(x.get('rel_path'))


# Generate keyword dict from scraped materials and edits to the list,. 
# from language import keywords_generate
# keywords_generate.generateKeywords()





