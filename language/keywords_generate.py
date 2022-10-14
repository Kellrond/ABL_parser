import os, shutil

from language.keywords import keywords

def parseKeyword(file_path:str):
    ''' List of keywords grabbed from the Progress site to help with parsing.

        Reads the text file gathered from the link below and parses it into dictionary. 
        It then compares to the existing dictionary and takes the existing value if different.
        Writes dictionary back to original python file. 
    
        Source:
            https://docs.progress.com/bundle/openedge-abl-reference-117/page/Keyword-Index.html
    '''

    with open(file_path, 'r') as file:
        lines = file.read()

    lines.replace('check mark', 'True')
    lines = lines.split('\n')

    new_keywords = []
    for ln in lines:
        new_keywords.append(ln.split('\t'))

    new_keywords = [ 
            {
                'keyword':x[0], 
                'flag': None,
                'starts_block': False,
                'category': '',
                'syntax': '',
                'note':'',
                'docs_url': '',
                'reserved': True if x[1] != '?' else False, 
                'min_abr': x[2] if x[2] != '?' else None
            } 
        for x in new_keywords ]

    for keywrd in new_keywords:
        old_kw = [ x for x in keywords if x['keyword'] == keywrd['keyword']]
        if len(old_kw) > 0:
            old_kw = old_kw[0]
            for k,v in keywrd.items():
                if v != old_kw.get(k, v):
                    keywrd[k] = old_kw.get(k)


    shutil.copy('language/keywords.py', 'temp/keywords.py.old')
    try:
        with open('language/keywords.py', 'w') as file:
            file.write('keywords = [\n')
            # for kw in 
            [file.write(f"""    {{ 'keyword':"{x['keyword']+'",': <35} 'flag':{ "'"+ x['flag'] + "'," if x['flag'] else 'None,': <8} 'starts_block': {str(x['starts_block'])+",": <6} 'category': {"'"+x['category']+"',": <12} 'syntax':'{x['syntax']}', 'note':'{x['note']}', 'docs_url':'{x['docs_url']}', 'reserved':{str(x['reserved'])+',': <6}'min_abr':{"'"+x['min_abr']+"'," if x.get('min_abr', False) else 'None,'} }},\n""") for x in new_keywords]
            file.write(']\n\n')
        os.remove('temp/keywords.py.old')
    except Exception as e:
        shutil.copy('temp/keywords.py.old', 'language/keywords.py')
        raise e
