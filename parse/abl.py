import conf
from modules.db import Db
from modules.logging import Log
from language.keywords import keywords

log = Log(__name__)
db = Db()

def debugParserOutput(parsed_lines, start=0, stop=None, second_col='line', one_col=False):
    ''' Helps to debug the parser 

        Params:
            - parsed_lines: the output from parseFile
            - start: line to start on
            - stop: line to stop on
            - second_col: sets the content for the second column
            - one_col: if not false, must select 'trimmed' or 'gathered'
    '''
    if conf.Parser.debug:
        if stop == None:
            stop = len(parsed_lines)

        gathering = True if second_col == 'gathered' else False

        for p in parsed_lines[start:stop]:
            if gathering:
                gDict = p[second_col]
                scnd_col = ', '.join([f'{k}:{v}' for k,v in gDict.items() if k != 'lines' and k != 'file_id'])
            else:
                scnd_col = str(p.get(second_col))

            if one_col != False:
                if one_col == 'gathered':
                    print(f"{p['line_no']: <5}│{scnd_col: <80}│{p['first_word']: <20}│{' '.join(p['flags']): <10}")
                else:
                    print(f"{p['line_no']: <5}│{p['trim_line']: <80}│{p['first_word']: <20}│{' '.join(p['flags']): <10}")
            else:   
                print(f"{p['line_no']: <5}│{scnd_col: <80}│{p['trim_line']: <80}│{p['first_word']: <20}│{' '.join(p['flags']): <10}")


def parseFile(rel_path):
    ''' Parses ABL '''
    file_meta = db.queryOne(f"SELECT * FROM files f WHERE f.rel_path = '{rel_path}' ")


    if not file_meta:
        return

    with open(f"pos/{rel_path}", 'r', encoding='latin_1') as file:
        lines = file.readlines()

    # Get a file list to use ahead
    file_list = [ x['rel_path'] for x in db.query('SELECT rel_path FROM files;')]

    parsed_lines = []      
    in_comment = False  
    gathered = {'code':'', 'lines':[], 'file_id': file_meta['file_id']}
    for line_no, line in enumerate(lines):
        ld = {}
        # Clean up the line and set any initial variables
        line = line.replace('\n','')
        trim_line = line.lstrip()
        flags = []
        first_word = ''

        # Look for comments before anything else
        if not in_comment and trim_line.find('/*') != -1:
            flags.append('com_s')
            in_comment = True
            gathered['code'] = trim_line[trim_line.find('/*'):] + '\n'
            # Close comment 
            if gathered['code'].find('*/') != -1:
                flags.append('com_e')
                in_comment = False

                gathered['lines'].append(line_no)
                gathered['code'] = gathered['code'][:gathered['code'].find('*/') + 2]
                commentETL(gathered)
                gathered = {'code':'', 'lines':[], 'file_id': file_meta['file_id']}

                trim_line = trim_line[:trim_line.find('/*')] + trim_line[trim_line.find('*/')+2:].lstrip()
            else:
                gathered['lines'].append(line_no)
                trim_line = trim_line[:trim_line.find('/*')].lstrip()
        elif in_comment:
            flags.append('com')
            # Close comment
            if trim_line.find('*/') != -1:
                flags.append('com_e')
                in_comment = False   

                gathered['lines'].append(line_no)
                gathered['code'] += line[:line.find('*/') + 2]
                commentETL(gathered)
                gathered = {'code':'', 'lines':[], 'file_id': file_meta['file_id']}

                trim_line = trim_line[trim_line.find('*/')+2:].lstrip()
            else:
                gathered['lines'].append(line_no)
                gathered['code'] += line + '\n'
                trim_line = ''
        
        # If line is blank append now and leave
        if trim_line.strip() == '':
            parsed_lines.append({'line_no':line_no,'gathered':gathered, 'flags': flags, 'first_word': '', 'trim_line':trim_line, 'line': line})
            continue

        # Check the first word to see how to treat the 
        finished_line = False
        gathered = {'code':'', 'lines':[], 'file_id': file_meta['file_id']}
        while not finished_line:
            first_spc = trim_line.find(' ')
            if first_spc != -1:
                first_word = trim_line[:trim_line.find(' ')].upper()
            elif len(trim_line) > 0:
                first_word = trim_line.upper()
            else:
                first_word = ''
            
            # Flag ABL keywords
            flag_keywords = [ x for x in keywords if x['flag'] != None ]
            for kw in flag_keywords:
                if first_word == kw['keyword']:
                    flags.append(kw['flag'])
                    break
                elif kw['abr_len'] != 0 and first_word[:kw['abr_len']] == kw['min_abr'] and first_word in kw['keyword']:
                    flags.append(kw['flag'])
                    break

            # Look for imports 
            if first_word[0] == '{':
                close_pos = first_word.find('}')
                if close_pos != -1:
                    seek = first_word[1:close_pos].lower()
                else:
                    seek = first_word[1:].lower()

                if seek in file_list:
                    flags.append('import')
                    includeETL(line, file_id=file_meta['file_id'], line_start=line_no)
                    ln_before = line[:line.find('{')]
                    trim_line = ln_before + line[line.find('}')+1:].strip()

            # Look for runs
            if 'run' in flags:
                runETL(trim_line, file_id=file_meta['file_id'], line_start=line_no)


            # if kw.get('flag') != None:


            ##
            finished_line = True
            ##
        
        if len(gathered['code']) == 0:
            parsed_lines.append({'line_no':line_no, 'gathered': {**gathered}, 'flags': flags, 'first_word': first_word, 'trim_line':trim_line, 'line': line})
        
    # debugParserOutput(parsed_lines, one_col='trimmed')

@log.performance
def commentETL(gathered_line:dict):
    ''' Adds comment to the db '''
    db.add(
        {
            '__table__': 'comments',
            'file_id': gathered_line['file_id'],
            'comment':gathered_line['code'],
            'line_start': gathered_line['lines'][0],
            'line_end': gathered_line['lines'][-1],
        }
    )

@log.performance
def includeETL(line, file_id, line_start):
    ''' Adds the include to the database'''
    line = line[1:line.find('}')]
    arguments = ''
    if line.find(' ') != -1:
        arguments = line[line.find(' ')+1:].strip()
        line = line[:line.find(' ')]

    inc_file_id = db.scalar(f"SELECT f.file_id FROM files f WHERE f.rel_path = '{line}'; ")
    db.add({
        '__table__': 'includes',
        'file_id': file_id,
        'inc_file_id': inc_file_id,
        'line_start': line_start,
        'arguments': arguments   
    })

@log.performance
def runETL(line, file_id, line_start):
    ''' Currently just handles the extensions below in runs. Does not capture multi line runs yet '''
    # TODO make this work with multi line runs
    
    # TODO deal with local and included procedures
    
    # If there are parameters grab those
    parameters = ''
    if line.find('(') != -1:
        parameters = line[line.find('(')+1:]
        line = line[:line.find('(')]
        if parameters.find(')') != -1:
            parameters = parameters[:parameters.find(')')].strip()
    # Remove 'RUN ' from the trimmed line
    line = line[4:].strip()

    extensions = ['.p', '.i','.w','.cls','.v','.f','.o','.d']
    for ext in extensions:
        if line.find(ext) != -1:
            procedure = ''
            if line.find(' ') != -1:
                procedure = line[line.find(' ')+1:]
                line = line[:line.find(' ')].strip()
            # If no parameters the line may end with a period. 
            if line[-1] == '.':
                line = line[:-1]
            run_file_id = db.scalar(f"SELECT f.file_id FROM files f WHERE f.rel_path = '{line}'; ")
            print(line)

            db.add({
                '__table__': 'runs',
                'file_id': file_id, 
                'run_file_id': run_file_id, 
                'line_start': line_start,
                'procedure': procedure,    
                'parameters': parameters
            })
                
    
