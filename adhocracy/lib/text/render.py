import cgi
import re

from markdown2 import Markdown

from adhocracy import model
from adhocracy.lib.cache.util import memoize

SUB_USER = re.compile("@([a-zA-Z0-9_\-]{3,255})")


def user_sub(match):
    from adhocracy.lib import helpers as h
    user = model.User.find(match.group(1))
    if user is not None:
        return h.user.link(user)
    return match.group(0)


SUB_PAGE = re.compile("\[\[([^(\]\])]{3,255})\]\]", re.M)


def page_sub(match):
    from adhocracy.lib import helpers as h
    page_name = match.group(1)
    variant = model.Text.HEAD
    if '/' in page_name:
        page_name, variant = page_name.split('/', 1)
    page = model.Page.find_fuzzy(page_name, include_deleted=True)
    if page is not None:
        if page.is_deleted():
            return page_name
        return h.page.link(page, variant=variant, icon=True)
    else:
        return page_name


@memoize('render')
def render(text, substitutions=True, escape=True):
    '''
    Render markdown as html.

    *substitutions*
        If `True`, substitude text reference, e.g. member refs like
        @(pudo), to html.
    *escape*
        Do an cgi escape befor the text is converted to html
    '''
    if text is None:
        return ""
    if escape:
        text = cgi.escape(text)
    text = Markdown().convert(text)
    if substitutions:
        text = SUB_USER.sub(user_sub, text)
        text = SUB_PAGE.sub(page_sub, text)
    return text


def _line_table(lines):
    _out = "<table class='line_based'>"
    for num, line in enumerate(lines):
        _out += """\t<tr>
                        <td class='line_number'>%s</td>
                        <td class='line_text'><pre>%s</pre></td>
                     </tr>\n""" % (num + 1, line)
    _out += "</table>\n"
    return _out


@memoize('text_render')
def render_line_based(text_obj):
    if not text_obj.text:
        return ""
    return _line_table([cgi.escape(l) for l in text_obj.lines])


def truncate(text, length):
    if len(text) <= length:
        return text

    break_point = None
    in_tag = False
    count = 0
    for i, c in enumerate(text):
        if count == length:
            if break_point:
                return text[:break_point + 1]
            return text[:i]

        if c.isspace():
            break_point = i

        if c == '<':
            in_tag = True
            continue
        if c == '>':
            in_tag = False
            continue

        if not in_tag:
            count += 1

    return text


def linify(text, length):
    for in_line in text.strip().split("\n"):
        while True:
            line = truncate(in_line, length)
            yield line
            in_line = in_line[len(line):]
            if not len(in_line):
                break
