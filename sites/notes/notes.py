import logging
import markdown
import datetime
import re

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
        self.SUCCESSES = []

        if self.CMD == 'view' or self.CMD == 'page' or self.CMD == 'slides':
            logging.info('----------------> %s' % self.CMD)
            self.render_view()
        elif self.CMD == 'pubreader':
            logging.info('----------------> pubreader')
            self.render_pubreader()
        elif self.CMD == 'new':
            logging.info('----------------> new')
            self.render_new()
        elif self.CMD == 'edit':
            logging.info('----------------> edit')
            self.render_edit()
        elif self.CMD == 'save':
            logging.info('----------------> save')
            self.save_or_update_note()
        elif self.CMD == 'trash':
            logging.info('----------------> trash')
            self.trash_note()
        elif self.CMD == 'copy':
            logging.info('----------------> copy')
            self.create_copy()
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

    def render_new(self):
        '''Offer a blank form for editing a new Note'''
        self._render( template = 'notes/notes_edit.html' )

    def create_copy(self):
        '''Create a copy of the current note in the current user's notebook.'''
        allow_copying = False
        if not self.KEY:
            self.ERRORS.append('No note to copy. We need a valid note ID.')

        # allow copying if we are in a user session:
        #     the logged in user is also the note owner
        #     OR the note is public
        if self.HANDLER.ACCESS_LEVEL == 'user':
            allow_copying = ((self.NOTE.owner == self.HANDLER.USER) 
                             or (self.NOTE.public_flag == True))

        if allow_copying:
            try:
                new_note = self._clone_entity(self.NOTE)
                new_note.title = '%s [COPY]' % new_note.title
                new_note.owner = self.HANDLER.USER
                new_key = new_note.put()
                self.SUCCESSES.append('Made: %s' % new_note.title)
                self.HANDLER.redirect('/notes/edit/%s' % new_key.urlsafe())
            except:
                self.ERRORS.append('Copy failed. Try again?')
        else:
            self.WARNINGS.append('Login to copy public notes or to clone your own notes.')
            self._render( template = '/notes/notes_index.html' )

    def render_pubreader(self):
        '''Show the PubReader version of the current note'''
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
            target, error, meta = self._markdown_to_html(self.NOTE.source)

            target = self._view_helper_purge_extra_markup(target)
            display_fields['target'] = target
            display_fields['editable'] = (self.NOTE.owner==self.HANDLER.USER 
                                          and self.NOTE.owner != None)
            for k, v in meta.iteritems(): display_fields[k] = v[0]
            if error: self.WARNINGS.append(error)
        else:
            display_fields = self._get_display_fields(note='')

        self._render( template = 'notes/notes_pubreader.html', **display_fields )

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
            display_fields, target, error = self._view_helper_markdown()
        else:
            display_fields = self._get_display_fields(note='')

        display_fields['bare_page'] = True
        if self.CMD == 'view':
            template = 'notes/notes_view.html'
            display_fields['bare_page'] = False
        elif self.CMD == 'slides':
            # separate the slides and put in temporary holder
            divider = re.compile(r'<p>{{\s+slide.+}}</p>')
            slides = [ slide for slide in divider.split(target) if slide.strip() ]

            # for each slide separate the slide material from the handout
            divider = re.compile(r'<p>{{\s+handout.+}}</p>')
            display_fields['slides'] = [ divider.split(slide)  for slide in slides ]

            template = 'notes/notes_s5.html'
        else: # self.CMD == 'page'
            display_fields['target'] = self._view_helper_purge_extra_markup(display_fields['target'])
            template = 'notes/notes_page.html'

        self._render( template = template, **display_fields )

    def _view_helper_markdown(self):
        display_fields = self._get_display_fields(note=self.NOTE)
        target, error, meta = self._markdown_to_html(self.NOTE.source)
        display_fields['target'] = target
        display_fields['editable'] = (self.NOTE.owner==self.HANDLER.USER 
                                      and self.NOTE.owner != None)
        for k, v in meta.iteritems(): display_fields[k] = v[0]
        if error: self.WARNINGS.append(error)
        return display_fields, target, error

    def _view_helper_purge_extra_markup(self, target):
        purge_pattern = re.compile(r'<p>{{\s+\w+.+}}</p>\n')
        target = re.sub(purge_pattern, '', target)
        return target

    def trash_note(self):
        '''Trash the current note, if access is authorised.

        - checks for access,
        - deletes note (no checking for confirmation),
        - then redirects home.

        TODO ask for confirmation of deletion and return to the calling page
        rather than redirecting home.

        '''

        allow_trashing = False

        # determine access rights
        if self.HANDLER.ACCESS_LEVEL == 'user':
            if self.NOTE.owner == self.HANDLER.USER:
                allow_trashing = True # Allow updating of user's own notes
            else:
                # Disallow deleting of someone else's notes
                self.ERRORS.append('You can only delete your own notes.')
        else: # Guests cannot delete notes
            self.ERRORS.append('Guests cannot delete notes.')
        if allow_trashing:
            try:
                self.KEY.delete()
            except:
                self.ERRORS.append('Deletion failed.')
        self.HANDLER.redirect('/notes/')

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
                            successes = self.SUCCESSES,
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
        md = markdown.Markdown( extensions = ['extra', 'toc', 
                                              'sane_lists', 'meta', 
                                              'nl2br'],
                                safe_mode='replace',
                                output_format = 'html5',
                                html_replacement_text=replacer)
        target = md.convert(source)
        if replacer in target:
            html_in_source = True
        else:
            html_in_source = False

        target = self._extra_formatting(target)
        return target, html_in_source, md.Meta

    def _extra_formatting(self, target):
        '''Adds extra attributes and does secondary formatting to the target.

        This is rudimentary at this stage as it simply uses regex brute force.
        TODO: use proper DOM analysis to analyse and format.
        TODO: give the user some control over the attributes to be selected.
        TODO: allow alternatives to Markdown e.g. Slideous or DZ slides format.

        '''

        # Add class="table" attribute to bare <table> tag, 
        # to get a prettier effect from Boostrap
        target = re.sub(r'(<table)(>)', r'\1 class="table table-bordered table-condensed table-hover"\2', target)
        return target

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

    def _clone_entity(self, e, **extra_args):
        """Clones an entity, adding or overriding constructor attributes.

        The cloned entity will have exactly the same property values as the original
        entity, except where overridden. By default it will have no parent entity or
        key name, unless supplied. 
        From: http://stackoverflow.com/a/2712401/1290420

        Args:
          e: The entity to clone
          extra_args: Keyword arguments to override from the cloned entity and pass
            to the constructor.
        Returns:
          A cloned, possibly modified, copy of entity e.

        """
        klass = e.__class__
        props = dict((k, v.__get__(e, klass)) for k, v in klass._properties.iteritems())
        props.update(extra_args)
        return klass(**props)

    def _debug(self):
        title = self.HANDLER.request.get('title')
        source = self.HANDLER.request.get('source')
        key = self.HANDLER.request.get('key')
        if key:
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