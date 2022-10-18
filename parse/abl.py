import conf
from modules.db import Db
from modules.logging import Log
from language.keywords import keywords

log = Log(__name__)
db = Db()

def debugParserOutput(parsed_lines, start=0, stop=None, second_col='line'):
    ''' Helps to debug the parser 

        Params:
            - parsed_lines: the output from parseFile
            - start: line to start on
            - stop: line to stop on
            - second_col: sets the content for the second column
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
            print(f"{p['line_no']: <5}│{scnd_col: <80}│{p['trim_line']: <80}│{p['first_word']: <20}│{' '.join(p['flags']): <10}")


def parseFile(rel_path):
    ''' Parses ABL '''
    file_meta = db.queryOne(f"SELECT * FROM files f WHERE f.rel_path = '{rel_path}' ")

    kw_list = [x.get('keyword') for x in keywords ]

    if not file_meta:
        return

    with open(f"pos/{rel_path}", 'r', encoding='latin_1') as file:
        lines = file.readlines()

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
            
            if first_word in kw_list:
                kw = [ x for x in keywords if x['keyword'] == first_word ][0]

                if kw.get('flag') != None:
                    flags.append(kw['flag'])


            ##
            finished_line = True
            ##
        
        if len(gathered['code']) == 0:
            parsed_lines.append({'line_no':line_no, 'gathered': {**gathered}, 'flags': flags, 'first_word': first_word, 'trim_line':trim_line, 'line': line})
        
    debugParserOutput(parsed_lines)

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