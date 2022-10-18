import glob

from modules         import utilities
from modules.logging import Log

log= Log(__name__)

@log.performance
def processFoldersAndFiles(db):
    ''' Globs all files and folders then writes to file and db
    
        Params:
            - db: instance of Db class
    '''
    log.debug('Process folders and files')
    # Glob the folders and write data
    folders = generateFolderList()
    folderToTxt(folders)
    folderToDb(folders, db)

    # Using folders, glob for files and write to db
    files = generateFileList(folders)
    fileToTxt(files)
    fileToDb(files, db)
    log.info('Complete folder and file processing')

@log.performance
def generateFolderList() -> list:
    ''' Folder list is glob readable and not ready for the db '''
    log.debug('Generate folder list')
    glob_list = glob.glob(".\\pos\\**\\ ", recursive=True)
    folders = []
    for i, folder in enumerate(glob_list):
        rel_path = folder.replace('\\','/')[5:].strip()

        name = rel_path[:-1]
        while name.find('/') != -1:
            name = name[name.find('/')+1:]

        folders.append(
            {   
                '__table__': 'folders',
                'folder_id': i,
                'abs_path': folder,
                'rel_path': rel_path,
                'name': name 
            }
        )

    # Find parents for folders
    for folder in folders:
        split_path = rel_path.split('/')[:-1]
        if len(split_path) > 1:
            parent_folder_path = '/'.join(split_path[:-1]) + '/'
            folder['parent_id'] = None
            result_of_parent_search = [ x for x in folders if x['rel_path'] == parent_folder_path]
            if len(result_of_parent_search) > 0:
                folder['parent_id'] = result_of_parent_search[0]['folder_id']
    return folders

@log.performance
def folderToTxt(folders:list) -> None:
    log.debug('Write folders to txt')
    # Clear existing contents
    with open('txt/folders.txt', 'w') as f:
        pass

    for fld in folders:
        with open('txt/folders.txt', 'a') as f:
            f.write(f"{fld['folder_id']} - {fld['parent_id']}\t{fld['name']}\t\t{fld['rel_path']}\t{fld['abs_path']}\n")

@log.performance
def folderToDb(folders:list, db) -> None:
    log.debug('Write folders to db')
    db.add(folders)

@log.performance
def generateFileList(folders:list) -> list:
    ''' Taking the folders list that returns from generateFolderList() glob files to create 
        dictionaries to add the the db. 
    '''
    log.debug('Generate file list')
    files = []

    id_gen = utilities.generateIntegerSequence()

    for folder in folders:
        folder_path = folder['rel_path']
        glob_list = glob.glob(f"pos{folder_path}*.*")
        for file in glob_list:
            rel_path = file.replace('\\','/')[4:].strip()

            name = rel_path
            while name.find('/') != -1:
                name = name[name.find('/')+1:]

            ext = rel_path
            while ext.find('.') != -1:
                ext = ext[ext.find('.')+1:]

            file_details = {   
                    '__table__': 'files',
                    'file_id': next(id_gen),
                    'folder_id': folder['folder_id'],
                    'rel_path': rel_path,
                    'name': name, 
                    'ext': ext
                }
            meta = getFileMeta(rel_path)
            
            files.append({**file_details, **meta})
    return files

@log.performance
def getFileMeta(file_path:str) -> dict:
    ''' Reads the file to get metadata and returns a dictionary to combine with the file dict '''
    log.verbose('Get file metadata')

    with open(f"pos/{file_path}", 'r', encoding='latin_1') as file:
        lines = file.readlines()
        char_count = 0
        for line in lines:
            char_count += len(line)
            
    return { 
        'line_count': len(lines),
        'char_count': char_count
    }


@log.performance
def fileToTxt(files) -> None:
    ''' Writes the files dictionary to txt for ease of debugging'''
    log.debug('Write files to txt')
    with open('txt/files.txt', 'w') as fp:
        for f in files:
            fp.write(f"{f['file_id']}\t{f['folder_id']}\t{f['ext']: <6}\t{f['name']: <30}\t{f['rel_path']}\n")
        

@log.performance
def fileToDb(files:list, db) -> None:
    ''' Adds file records to the db '''
    log.debug('Write files to Db')
    db.add(files)