import logging

logging.info("url.py module has been imported")

class URLManager(object):
    """docstring for URLManager"""
    def __init__(self, handler, frag):
        handler.render('url/index.html', 
                       frag = frag,
                       handler = handler)