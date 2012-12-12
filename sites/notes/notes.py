import logging
import markdown
import datetime

class NotesManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler):
        self.handler = handler

    def convert(self):
        ''' Validate source text and output HTML5'''

        errors = []
        warnings = []

        # Check that title exists and convert to unicode if it does
        title = self.handler.request.get('title')
        if not title: 
            errors.append('Title is required.')
        else:
            title = self._to_unicode_or_bust(title)

        # Check source exists and convert to unicode if it does
        source = self.handler.request.get('source')
        target = ''
        if not source: 
            errors.append('Some markdown text is required for conversion.')
        else:
            source = self._to_unicode_or_bust(source)
            replacer = '<em class="alert">No raw HTML please.</em>'
            # Convert untrusted source to HTML5 
            # using Python-Markdown: http://packages.python.org/Markdown/
            target = markdown.markdown(source, 
                                       ['extra', 'toc'],
                                        safe_mode='replace',
                                        output_format = 'html5',
                                        html_replacement_text=replacer)
            if replacer in target:
                warnings.append('Avoid raw HTML tags in your source text.')

        if not self.handler.USER:
            warnings.append('Conversions cannot be saved unless you are signed in.')

        now = datetime.datetime.now()
        date_created = now.strftime("%Y-%m-%d %H:%M:%S")

        self.handler.render('notes/index.html', 
                       title = title,
                       source = source,
                       target = target,
                       date_created = date_created,
                       errors = errors,
                       warnings = warnings,
                       banner = False,
                       handler = self.handler)

    def render(self, frag=''):
        self.handler.render('notes/index.html', 
                       frag = frag,
                       banner = True,
                       handler = self.handler
                       )
    
    def _to_unicode_or_bust(self, obj, encoding='utf-8'):
        '''From "Unicode in Python, Completely Demystified" 
          by Kumar McMillan. http://farmdev.com/talks/unicode/

        '''
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj



