import logging
import markdown

logging.info("notes.py module has been imported")

class NotesManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler):
        self.handler = handler

    def convert(self, content=''):
        html = markdown.markdown(content)
        self.handler.render('notes/index.html', 
                       html = html, 
                       content = content,
                       handler = self.handler)

    def render(self, frag=''):
        self.handler.render('notes/index.html', 
                       frag = frag,
                       handler = self.handler)