import logging
import markdown
import datetime

from google.appengine.ext import ndb

class UnauthorisedException(Exception):
    pass

class Note(ndb.Model):
    """Schema for Note entities"""
    title = ndb.StringProperty(required=True)    
    source = ndb.TextProperty()
    date_created = ndb.DateTimeProperty(auto_now_add=True)
    date_modified = ndb.DateTimeProperty(auto_now=True)
    owner = ndb.UserProperty() 
    public_flag = ndb.BooleanProperty(default=False)

    @classmethod
    def query_user_recent(cls, user):
        # TODO implement a cursor for pagination of results
        return cls.query(cls.owner == user).order(-cls.date_modified)

    @classmethod
    def query_public_recent(cls):
        # TODO implement a cursor for pagination of results
        return cls.query(cls.public_flag == True).order(-cls.date_modified)

class Page(ndb.Model):
    """Elevates a Note to a single page view on the Site"""
    url = ndb.StringProperty(required=True)
    title = ndb.StringProperty()
    content = ndb.StructuredProperty(Note)
        
class NotesManager(object):
    """Controller for the Notes App"""

    def __init__(self, handler, cmd='', key=''):
        self.HANDLER = handler
        self.CMD = cmd
        self.KEY, self.NOTE = self._validate_key(key)
        self.ERRORS = []
        self.WARNINGS = []

        if self.CMD == 'view':
            logging.info('----------------> view')
            self.render_view()
        elif self.CMD == 'new':
            logging.info('----------------> new')
            self.render_new()
        elif self.CMD == 'edit':
            logging.info('----------------> edit')
            self.render_edit()
        elif self.CMD == 'save':
            logging.info('----------------> save')
            self.save_or_update_note()
        elif self.CMD == 'delete':
            pass
        elif self.CMD == 'copy':
            pass
        elif self.CMD and key == '':
            logging.info('----------------> render page: %s' % self.CMD)
            self.render_page(url = self.CMD)
        else:
            self.render_home()

    def render_home(self):
        '''Landing page for Notes App'''
        results = {}
        # Collect all public notes made by anonymous users
        recent = Note.query_public_recent()
        for note in recent:
            results[note.key.urlsafe()]= dict(title=note.title, 
                                              editable=(note.owner==self.HANDLER.USER 
                                                        and note.owner != None), 
                                              key=note.key.urlsafe())
        # Collect all notes made by the current user
        if self.HANDLER.ACCESS_LEVEL == 'user':
            recent = Note.query_user_recent(self.HANDLER.USER)
            for note in recent:
                results[note.key.urlsafe()]= dict(title=note.title, 
                                                  editable=(note.owner==self.HANDLER.USER 
                                                            and note.owner != None), 
                                                  key=note.key.urlsafe())
        display_fields = dict( recent = results )
        self._render( template = 'notes/notes_index.html', **display_fields )

    def render_page(self, url=''):
        '''Render a note as a standalone page

        Note must be public.
        There must be a Page that refers to the Note.
        @url refers to the stub that follows the notes root: /notes/<url>
        @url must be unique across all pages on the site

        '''
        
        self._render( template = 'notes/notes_page.html' )

    def render_new(self):
        '''Offer a blank form for editing a new Note'''
        self._render( template = 'notes/notes_edit.html' )

    def render_view(self):
        '''Show the formatted version of the current note'''
        allow_viewing = False
        if self.HANDLER.ACCESS_LEVEL == 'user':
            if self.NOTE.owner == self.HANDLER.USER:
                allow_viewing = True # Allow viewing of user's own notes
            elif self.NOTE.public_flag == True:
                allow_viewing = True # Allow viewing of public notes
            else:
                # Disallow viewing of someone else's private notes
                self.ERRORS.append('You don\'t have access to that note.')
        else: # Grant guest level access
            if self.NOTE.public_flag == True:
                allow_viewing = True # Allow viewing of a public note
            else:
                # Disallow editing of a private note
                self.ERRORS.append('Guests cannot view or edit a private note.')
        if allow_viewing:
            display_fields = self._get_display_fields(note=self.NOTE)
            target, error = self._markdown_to_html(self.NOTE.source)
            display_fields['target'] = target
            display_fields['editable'] = (self.NOTE.owner==self.HANDLER.USER 
                                          and self.NOTE.owner != None)
            if error: self.WARNINGS.append(error)
        else:
            display_fields = self._get_display_fields(note='')

        self._render( template = 'notes/notes_view.html', **display_fields )

    def save_or_update_note(self):
        '''Save or update the current note, if access is authorised.

        This is called by a POST request from an edit form.
        It should respond to new data submitted by the user to
        update an existing note or create a new one.

        '''

        # This records whihc button was clicked 
        # on the edit form: the save or view button
        ACTION = self.HANDLER.request.get('save') or self.HANDLER.request.get('view')

        allow_saving = False

        # retrieve variables from form 
        title = self.HANDLER.request.get('title')
        source = self.HANDLER.request.get('source')
        key = self.HANDLER.request.get('key')
        self.KEY, self.NOTE = self._validate_key(key)
        public_flag = self.HANDLER.request.get('public_flag')

        # determine access rights
        if self.HANDLER.ACCESS_LEVEL == 'user':
            if key == '':
                # new note being submitted
                allow_saving = True
            elif self.NOTE.owner == self.HANDLER.USER:
                allow_saving = True # Allow updating of user's own notes
            else:
                # Disallow editing of someone else's notes
                self.ERRORS.append('You need to make a copy of this note, then edit it.')
        else: # Guests can edit/save public notes
            if key == '':
                # new note being submitted
                allow_saving = True
            else:
                # Disallow editing of a private note
                self.ERRORS.append('You can edit a copy of this note if you log in.')
        if allow_saving:
            self.NOTE = self._save_note(title, source, public_flag, key)
            if ACTION == 'save':
                next_page = 'edit'
            else:
                next_page = 'view'
            self.HANDLER.redirect('/notes/%s/%s' % (next_page,
                                                    self.NOTE.key.urlsafe())
                                 )
        else:
            self.HANDLER.redirect('/notes/new')


    def render_edit(self):
        '''Edit the current note, if access is authorised, else offer blank.

        Editing is only note for the personal notes of the current user.
        TODO All other cases to be offered the chance to make a copy and edit that one.

        '''
        allow_editing = False
        if self.HANDLER.ACCESS_LEVEL == 'user':
            if self.NOTE.owner == self.HANDLER.USER:
                allow_editing = True # Allow editing of user's own notes
            else:
                # Disallow editing of someone else's notes
                self.ERRORS.append('You need to make a copy of this note, then edit it.')
                # TODO redirect to viewing the note and flash error message on view
                # self.HANDLER.redirect('/notes/view/%s' % self.NOTE.key.urlsafe())
        else: # Grant guest level access
            # Disallow editing of a private note
            self.ERRORS.append('Guests cannot view or edit a private note.')
        if allow_editing:
            display_fields = self._get_display_fields(note=self.NOTE)
        else:
            display_fields = self._get_display_fields(note='')

        self._render(template = 'notes/notes_edit.html', **display_fields)

    def _render(self, template, **display_fields):
        self.HANDLER.render(template,
                            handler = self.HANDLER,
                            errors = self.ERRORS,
                            warnings = self.WARNINGS,
                            **display_fields
                            )

    def _save_note(self, title, source, public_flag, key=''):
        '''Validate the input, update or create the note'''

        note = '' # start with a blank

        # Check 1: is key a valid key, else set it to blank
        try:
            key = ndb.Key(urlsafe=key)
        except TypeError:
            key = ''

        # Check 2: if valid key, try and retrieve the relevant note
        if key:
            note = key.get()

        # Check 3: if retrieval unsuccessful, create empty note
        if not note:
            note = Note()

        # All checks passed, update or create the note
        note.title = title
        note.source = source
        # TODO do not change the original owner
        note.owner = self.HANDLER.USER
        note.public_flag = (public_flag == 'public')
        note.put()
        return note

    def _markdown_to_html(self, source=''):
        '''Convert source text to HTML5

        Uses Python-Markdown: http://packages.python.org/Markdown/
        Source is untrusted, hence use of safe mode, removing
        all HTML tags from the user's input.

        '''
        source = self._to_unicode_or_bust(source)
        replacer = '<em class="alert">No raw HTML please.</em>'
        target = markdown.markdown(source, 
                                   ['extra', 'toc', 'sane_lists', 'meta', 'nl2br'],
                                    safe_mode='replace',
                                    output_format = 'html5',
                                    html_replacement_text=replacer)
        if replacer in target:
            html_in_source = True
        else:
            html_in_source = False
        return target, html_in_source

    def _get_display_fields(self, target='', note=''):
        result = {}
        result['target'] = target
        if note:
            result['title'] = note.title
            result['source'] = note.source
            result['key'] = note.key.urlsafe()
            result['date_created'] = note.date_created.strftime("%d %b %Y at %H:%M:%S")
            result['date_modified'] = note.date_modified.strftime("%d %b %Y at %H:%M:%S")
            result['public_flag'] = note.public_flag
        else:
            result['title'] = ''
            result['source'] = ''
            result['key'] = ''
            result['date_created'] = ''
            result['date_modified'] = ''
            result['public_flag'] = True
        return result

    def _validate_key(self, key=''):
        """Check if key is valid. 

        If valid key, return it and associated note
        If not, return a blank key and new Note() object.

        """
        note = Note()
        try:
            key = ndb.Key(urlsafe=key)
            note = key.get()
        except:
            # either key was malformed or note does not exist
            key = None
        return key, note
    
    def _to_unicode_or_bust(self, obj, encoding='utf-8'):
        '''From "Unicode in Python, Completely Demystified" 
          by Kumar McMillan. http://farmdev.com/talks/unicode/

        '''
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj

    def _debug(self):
        title = self.HANDLER.request.get('title')
        source = self.HANDLER.request.get('source')
        key = self.HANDLER.request.get('key')
        self.KEY, self.NOTE = self._validate_key(key)
        public_flag = self.HANDLER.request.get('public_flag')
        self.HANDLER.debug(dict(CMD = self.CMD,
                                KEY = self.KEY.urlsafe(),
                                NOTE = self.NOTE,
                                title = title, 
                                source = source, 
                                key = key, 
                                public_flag = public_flag,
                                user = self.HANDLER.USER,
                                access = self.HANDLER.ACCESS_LEVEL,
                                note = self.NOTE
                                )
                          )