"""Helper functions

Consists of functions to typically be used within templates, but also
available to Controllers. This module is available to templates as 'h'.
"""
import cgi
import hashlib
import urllib

from pylons import tmpl_context as c, config, request
from pylons.i18n import _
from webhelpers.pylonslib import Flash as _Flash
from webhelpers.text import truncate

from adhocracy.lib import cache
from adhocracy.lib import democracy
from adhocracy.lib import sorting
from adhocracy.lib.auth.authorization import has as has_permission
from adhocracy.lib.auth.csrf import url_token, field_token
from adhocracy.lib.helpers import site_helper as site
from adhocracy.lib.helpers import user_helper as user
from adhocracy.lib.helpers import proposal_helper as proposal
from adhocracy.lib.helpers import text_helper as text
from adhocracy.lib.helpers import page_helper as page
from adhocracy.lib.helpers import delegateable_helper as delegateable
from adhocracy.lib.helpers import tag_helper as tag
from adhocracy.lib.helpers import poll_helper as poll
from adhocracy.lib.helpers import comment_helper as comment
from adhocracy.lib.helpers import selection_helper as selection
from adhocracy.lib.helpers import delegation_helper as delegation
from adhocracy.lib.helpers import instance_helper as instance
from adhocracy.lib.helpers import abuse_helper as abuse
from adhocracy.lib.helpers import milestone_helper as milestone
from adhocracy.lib.helpers import recaptcha_helper as recaptcha
from adhocracy.lib.helpers.site_helper import base_url
from adhocracy.lib.watchlist import make_watch, find_watch
from adhocracy import model
from adhocracy.i18n import countdown_time, format_date
from adhocracy.i18n import relative_date, relative_time


flash = _Flash()
recaptcha = recaptcha.Recaptcha()


def immutable_proposal_message():
    return _("This proposal is currently being voted on and cannot "
             "be modified.")


def comments_sorted(comments, root=None, variant=None):
    from adhocracy.lib.tiles.comment_tiles import CommentTile
    comments = [c for c in comments if
                (c.variant == variant and c.reply == root)]
    _comments = []
    for comment in sorting.comment_order(comments):
        tile = CommentTile(comment)
        _comments.append((comment, tile))
    return _comments


def contains_delegations(user, delegateable, recurse=True):
    for delegation in user.agencies:
        if (not delegation.revoke_time and
            (delegation.scope == delegateable or
            (delegation.scope.is_sub(delegateable) and recurse))):
            return True
    for delegation in user.delegated:
        if (not delegation.revoke_time and
            (delegation.scope == delegateable or
            (delegation.scope.is_sub(delegateable) and recurse))):
            return True
    return False


def poll_position_css(poll):
    @cache.memoize('poll_position_css')
    def _cached(user, poll):
        pos = user.position_on_poll(poll)
        if pos == 1:
            return "upvoted"
        elif pos == -1:
            return "downvoted"
        else:
            return ""
    if c.user:
        return _cached(c.user, poll)
    return u""


def add_meta(name, content):
    '''
    Add information to be rendered as a meta tag
    by a template in the html head. *value* will be used for the
    name attribute, *content* for the content attribute of the
    meta tag.
    '''
    if not c.html_meta:
        c.html_meta = dict()
    c.html_meta[name] = content


def add_html_head_link(title, link, rel, type):
    '''
    Add information to be rendered as a link tag
    by a template in the html head. The parameters
    correspondent to the attributes of the link tag.
    '''
    if not c.html_head_links:
        c.html_head_links = []
    c.html_head_links.append({'title': title,
                              'href': link,
                              'rel': rel,
                              'type': type})


def add_rss(title, link):
    '''
    Add information to be rendered as a link tag in the html
    head with rel="alternate" and type="application/rss+xml"
    '''
    add_html_head_link(title, link, rel='alternate',
                       type='application/rss+xml')


def help_link(text, page, anchor=None):
    url = base_url(None, path="/static/%s.%s")
    if anchor is not None:
        url += "#" + anchor
    full_url = url % (page, 'html')
    return (u"<a target='_new' class='staticlink_%s' href='%s' "
            u">%s</a>") % (page, full_url, text)


def entity_url(entity, **kwargs):
    if isinstance(entity, model.User):
        return user.url(entity, **kwargs)
    elif isinstance(entity, model.Proposal):
        return proposal.url(entity, **kwargs)
    elif isinstance(entity, model.Page):
        return page.url(entity, **kwargs)
    elif isinstance(entity, model.Text):
        return text.url(entity, **kwargs)
    elif isinstance(entity, model.Delegateable):
        return delegateable.url(entity, **kwargs)
    elif isinstance(entity, model.Poll):
        return poll.url(entity, **kwargs)
    elif isinstance(entity, model.Selection):
        return selection.url(entity, **kwargs)
    elif isinstance(entity, model.Comment):
        return comment.url(entity, **kwargs)
    elif isinstance(entity, model.Instance):
        return instance.url(entity, **kwargs)
    elif isinstance(entity, model.Delegation):
        return delegation.url(entity, **kwargs)
    elif isinstance(entity, model.Milestone):
        return milestone.url(entity, **kwargs)
    elif isinstance(entity, model.Tag):
        return tag.url(entity, **kwargs)
    raise ValueError("No URL maker for: %s" % repr(entity))


