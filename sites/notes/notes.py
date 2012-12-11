import logging
import markdown

logging.info("notes.py module has been imported")

class NotesManager(object):
    """docstring for NotesManager"""
    def __init__(self, handler):
        self.handler = handler

    def convert(self):
        ''' Validate source text and output HTML5'''

        errors = []
        warnings = []

        # Check that title exists and convert to unicode if so
        title = self.handler.request.get('title')
        if not title: 
            errors.append('Title is required.')
        else:
            title = self._to_unicode_or_bust(title)

        # Check source exists and convert to unicode
        source = self.handler.request.get('source')
        target = ''
        if not source: 
            errors.append('Some markdown text is required for conversion.')
        else:
            source = self._to_unicode_or_bust(source)
            target = markdown.markdown(source, 
                   ['extra', 'toc'],
                    safe_mode='replace',
                    output_format = "html5",
                    html_replacement_text='<em class="alert">No raw HTML please.</em>')
            if '<em class="alert">No raw HTML please.</em>' in target:
                warnings.append('Avoid raw HTML tags in your source text.')

        if not self.handler.USER:
            warnings.append('Conversions cannot be saved unless you are signed in.')

        self.handler.render('notes/index.html', 
                       title = title,
                       source = source,
                       target = target,
                       errors = errors,
                       warnings = warnings,
                       handler = self.handler)

    def render(self, frag=''):
        self.handler.render('notes/index.html', 
                       frag = frag,
                       handler = self.handler
                       )

    # From "Unicode in Python, Completely Demystified" by Kumar McMillan.
    # http://farmdev.com/talks/unicode/
    
    def _to_unicode_or_bust(self, obj, encoding='utf-8'):
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj



