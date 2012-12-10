# -*- coding: utf-8 -*-

import os
import webapp2
import jinja2
import logging

from google.appengine.ext import db
from google.appengine.api import users

from collections import namedtuple

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

App = namedtuple('App', ['name', 'url', 'description'])

class Handler(webapp2.RequestHandler):
    """Generic request handler with templating utility methods"""

    def __init__(self, request, response):
        super(Handler, self).__init__(request, response)
        self.USER = users.get_current_user()
        if self.USER:
            self.GREETING = ("<a href=\"%s\">sign out</a>" % 
                        users.create_logout_url(dest_url = self.request.url))
            self.NICKNAME = self.USER.nickname()
        else:
            self.GREETING = ("<a href=\"%s\">Sign in or register</a>" %
                        users.create_login_url(dest_url = self.request.url))
            self.NICKNAME = None
        self.APPS = self._register_apps()

    def _register_apps(self):
        ''' Get the descriptors of all Apps in current module 
        and return them as a set of namedtuples '''
        g = globals().copy()
        g = [ obj for name, obj in g.iteritems() 
              if name[-3:] == 'App' and len(name) > 3 ]
        result = {}
        for app in g:
            result[ app.REGISTER.name ] = app.REGISTER
        return result

    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

class UrlApp(Handler):
    from sites.url import url

    REGISTER = App(name='url', 
                   description=u"store a personal list of short URLs", 
                   url='url')

    def get(self, frag=''):
        self.url.URLManager(self, frag)

class NotesApp(Handler):
    from sites.notes import notes

    REGISTER = App(name='notes', 
                   description=u"store and edit random notes in reStructuredText", 
                   url='notes')

    def get(self, frag=''):
        manager = self.notes.NotesManager(self)
        manager.render(frag)

    def post(self, frag=''):
        manager = self.notes.NotesManager(self)
        manager.convert(self.request.get('content'))

class MainPage(Handler):
    from sites.home import home

    REGISTER = App(name='home', 
                   description=u"coding projects and web sandbox", 
                   url='home')

    def get(self, frag=''):
        self.home.HomeManager(self, frag=frag)

app = webapp2.WSGIApplication([('/url', UrlApp),
                               ('/url/(.*)', UrlApp),
                               ('/notes', NotesApp),
                               ('/notes/(.*)', NotesApp),
                               ('/home', MainPage),
                               ('/home/(.*)', MainPage),
                               ('/(.*)', MainPage),
                               ('/', MainPage),
                               ],
                               debug = True)
