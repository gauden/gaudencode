import logging

class HomeManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler, frag=''):
        handler.render('home/index.html', 
            app = handler.REGISTER, 
            frag = frag,
            handler = handler,
            )
        