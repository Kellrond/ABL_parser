''' This file hold various utility functions which may or may not haven a similar theme. 
'''
def generateIntegerSequence() -> int:
    ''' By creating a generator function we can generate a chain of executions in the performance log and 
        get a form of stack trace out of it. 
    '''
    i = -1
    while True:
        i += 1
        yield i