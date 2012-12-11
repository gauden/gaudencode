import logging
import markdown

logging.info("notes.py module has been imported")

class NotesManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler):
        self.handler = handler

    def convert(self):
        title = self.handler.request.get('title')

        source = self.handler.request.get('source')
        target = markdown.markdown(source)

        self.handler.render('notes/index.html', 
                       title = title,
                       source = source,
                       target = target,
                       handler = self.handler)

    def render(self, frag=''):
        self.handler.render('notes/index.html', 
                       frag = frag,
                       handler = self.handler)