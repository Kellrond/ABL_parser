''' In this file there must be at minimum a file keyword.py with a keyword variable in it. 
    It will generate a new file, but the existing one must be there. Any give the variable a 
    list while you are there. 
'''
import os, shutil

import conf
from language.keywords import keywords

def generateKeywords():
    keywords = __parseKeyword()
    keywords = __parseUrls(keywords)
    __rewriteKeywords(keywords)

def __parseKeyword() -> dict:
    ''' List of keywords grabbed from the Progress site to help with parsing.

        Reads the text file gathered from the link below and parses it into dictionary. 
        It then compares to the existing dictionary and takes the existing value if different.
        
        Returns a dictionary for further processing
    
        Source:
            https://docs.progress.com/bundle/openedge-abl-reference-117/page/Keyword-Index.html
    '''

    with open(conf.Language.scraped_keywords, 'r') as file:
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

    # Include any custom dictionary items from the existing dict
    for old_keywrd in keywords:
        if sum([1 for x in new_keywords if x.get('keyword') == old_keywrd['keyword']]) != 1:
            new_keywords.append(old_keywrd)
        
    # Sort the list 
    new_keywords = sorted(new_keywords, key=lambda d: d['keyword'])

    return new_keywords


def __parseUrls(keywords:list) -> list:
    ''' The links to the documentation are along the left hand side of the page. 
        Grab those and strip all but the line with the a href tag. 

        Returns a list of dictionaries to be used with the keyword list.

        Params:
            - keywords: the list of keywords generated with __parseKeywords
    '''
    with open(conf.Language.scraped_urls, 'r') as file:
        # Readlines leaves the \n character in. This is the cleanest way to get the lines
        lines = file.read().split('\n')
        
        links = []

        for l in lines:
            l = l[9:]
            url = 'https://docs.progress.com' + l[:l.find('"')]
            l = l[l.find('>')+1:]
            keyword = l[:l.find(' ')].replace('(', '').strip()
            l = l[l.find(' ')+1:]
            category = l[:l.find('<')].replace('(','').replace(')', '').strip()

            links.append(
                {
                    'docs_url': url,
                    'keyword': keyword,
                    'category': category
                }
            )

        ## Add URL data to inbound keywords dicts. 
        for kw in keywords:
            index = -1
            for i, link in enumerate(links):
                if kw['keyword'] == link['keyword']:
                    index = i
                    continue
            if index != -1:
                data = links.pop(index)
                kw['docs_url'] = data['docs_url']
                kw['category'] = data['category']

        return keywords


def __rewriteKeywords(keywords:list):
    ''' Writes the final list of keywords to keywords.py'''

    shutil.copy('language/keywords.py', 'language/keywords.py.old')
    sng_slash = '\\'
    dbl_slash = '\\\\'
    esc_quote = '\\"' 


    with open('language/keywords.py', 'w') as file:
        file.write('keywords = [\n')
        for kw in keywords:
            keyword = kw['keyword'].replace(sng_slash,dbl_slash).replace('"',esc_quote)+'"'
            flag    = "'"+ kw['flag'] + "'" if kw['flag'] else 'None'
            starts_block = str(kw['starts_block'])
            category = "'"+kw['category']+"'"
            docs_url = kw['docs_url']
            reserved = str(kw['reserved'])
            min_abr ="'"+kw['min_abr']+"'" if kw.get('min_abr', False) else 'None'
            abr_len = str(len(kw['min_abr'])) if kw.get('min_abr', False) else '0'
            # This looks odd because the commas are missing. Mostly they are added 
            file.write(f"""    {{ 'keyword':"{keyword: <35}, 'flag':{flag: <15}, 'starts_block': {starts_block: <6}, 'category': {category: <20}, 'docs_url':'{docs_url}', 'reserved':{reserved: <6}, 'min_abr':{min_abr},  'abr_len':{abr_len} }},\n""") 
        file.write(']\n\n')
