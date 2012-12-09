import logging

logging.info("notes.py module has been imported")

class NotesManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler, frag=''):
        handler.render('notes/index.html', 
                       frag = frag,
                       handler = handler)