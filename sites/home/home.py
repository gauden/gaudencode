import logging

logging.info("home.py module has been imported")

class HomeManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler, frag=''):
        handler.render('home/index.html', 
            app = handler.REGISTER, 
            frag = frag,
            handler = handler,
            )
        