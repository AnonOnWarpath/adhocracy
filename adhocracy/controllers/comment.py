import logging

import formencode
from formencode import htmlfill, Invalid, validators

from pylons import request, tmpl_context as c
from pylons.controllers.util import redirect
from pylons.decorators import validate
from pylons.i18n import _

from repoze.what.plugins.pylonshq import ActionProtector

from adhocracy import forms, model
from adhocracy.lib import democracy
from adhocracy.lib import event, helpers as h, sorting, tiles, watchlist
from adhocracy.lib.auth import can, csrf, require
from adhocracy.lib.auth.authorization import has_permission
from adhocracy.lib.base import BaseController
from adhocracy.lib.instance import RequireInstance
from adhocracy.lib.pager import NamedPager
from adhocracy.lib.templating import (render, render_json, ret_abort,
                                      ret_success)
from adhocracy.lib.util import get_entity_or_abort

log = logging.getLogger(__name__)


class CommentNewForm(formencode.Schema):
    allow_extra_fields = True
    topic = forms.ValidDelegateable()
    reply = forms.ValidComment(if_empty=None, if_missing=None)
    wiki = validators.StringBool(not_empty=False, if_empty=False,
                                 if_missing=False)
    variant = forms.VariantName(not_empty=False, if_empty=model.Text.HEAD,
                                if_missing=model.Text.HEAD)


class CommentCreateForm(CommentNewForm):
    text = validators.String(max=21000, min=4, not_empty=True)
    sentiment = validators.Int(min=model.Comment.SENT_CON,
                               max=model.Comment.SENT_PRO, if_empty=0,
                               if_missing=0)


class CommentUpdateForm(formencode.Schema):
    allow_extra_fields = True
    text = validators.String(max=21000, min=4, not_empty=True)
    sentiment = validators.Int(min=model.Comment.SENT_CON,
                               max=model.Comment.SENT_PRO, if_empty=0,
                               if_missing=0)


class CommentRevertForm(formencode.Schema):
    allow_extra_fields = True
    to = forms.ValidRevision()


class CommentController(BaseController):

    @RequireInstance
    def index(self, format='html'):
        require.comment.index()
        comments = model.Comment.all()
        c.comments_pager = NamedPager(
            'comments', comments, tiles.comment.row, count=10,
            sorts={_("oldest"): sorting.entity_oldest,
                   _("newest"): sorting.entity_newest},
            default_sort=sorting.entity_newest)
        if format == 'json':
            return render_json(c.comments_pager)

        return self.not_implemented(format=format)

    @RequireInstance
    @validate(schema=CommentNewForm(), form="bad_request",
              post_only=False, on_get=True)
    def new(self, errors=None):
        c.topic = self.form_result.get('topic')
        c.reply = self.form_result.get('reply')
        c.wiki = self.form_result.get('wiki')
        c.variant = self.form_result.get('variant')
        defaults = dict(request.params)
        if c.reply:
            require.comment.reply(c.reply)
        else:
            require.comment.create_on(c.topic)
        return htmlfill.render(render('/comment/new.html'), defaults=defaults,
                               errors=errors, force_defaults=False)

    @RequireInstance
    @csrf.RequireInternalRequest(methods=['POST'])
    def create(self, format='html'):
        require.comment.create()
        try:
            self.form_result = CommentCreateForm().to_python(request.params)
        except Invalid, i:
            return self.new(errors=i.unpack_errors())

        topic = self.form_result.get('topic')
        reply = self.form_result.get('reply')

        if reply:
            require.comment.reply(reply)
        else:
            require.comment.create_on(topic)

        variant = self.form_result.get('variant')
        if hasattr(topic, 'variants') and not variant in topic.variants:
            return ret_abort(_("Comment topic has no variant %s") % variant,
                             code=400)

        comment = model.Comment.create(
            self.form_result.get('text'),
            c.user, topic,
            reply=reply,
            wiki=self.form_result.get('wiki'),
            variant=variant,
            sentiment=self.form_result.get('sentiment'),
            with_vote=can.user.vote())

        # watch comments by default!
        model.Watch.create(c.user, comment)
        model.meta.Session.commit()
        #watchlist.check_watch(comment)
        event.emit(event.T_COMMENT_CREATE, c.user, instance=c.instance,
                   topics=[topic], comment=comment, topic=topic,
                   rev=comment.latest)
        if len(request.params.get('ret_url', '')):
            redirect(request.params.get('ret_url') + "#c" + str(comment.id))
        if format != 'html':
            return ret_success(entity=comment, format=format)
        return ret_success(entity=comment, format='fwd')

    @RequireInstance
    def edit(self, id):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.edit(c.comment)
        return render('/comment/edit.html')

    @RequireInstance
    @csrf.RequireInternalRequest(methods=['POST'])
    @validate(schema=CommentUpdateForm(), form="edit", post_only=True)
    def update(self, id, format='html'):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.edit(c.comment)
        rev = c.comment.create_revision(
            self.form_result.get('text'),
            c.user,
            sentiment=self.form_result.get('sentiment'))
        model.meta.Session.commit()
        if can.user.vote():
            decision = democracy.Decision(c.user, c.comment.poll)
            if not decision.result == model.Vote.YES:
                decision.make(model.Vote.YES)
        model.meta.Session.commit()
        watchlist.check_watch(c.comment)
        #watch = model.Watch.create(c.user, c.comment)
        event.emit(event.T_COMMENT_EDIT, c.user, instance=c.instance,
                   topics=[c.comment.topic], comment=c.comment,
                   topic=c.comment.topic, rev=rev)
        if len(request.params.get('ret_url', '')):
            redirect(request.params.get('ret_url') + "#c" + str(c.comment.id))
        if format != 'html':
            return ret_success(entity=c.comment, format=format)
        return ret_success(entity=c.comment, format='fwd')

    @RequireInstance
    def show(self, id, format='html'):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.show(c.comment)
        if format == 'fwd':
            redirect(h.entity_url(c.comment))
        elif format == 'json':
            return render_json(c.comment)
        return render('/comment/show.html')

    @RequireInstance
    def ask_delete(self, id):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.delete(c.comment)
        return render('/comment/ask_delete.html')

    @RequireInstance
    @csrf.RequireInternalRequest()
    def delete(self, id, format='html'):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.delete(c.comment)
        c.comment.delete()
        model.meta.Session.commit()

        event.emit(event.T_COMMENT_DELETE, c.user, instance=c.instance,
                   topics=[c.comment.topic], comment=c.comment,
                   topic=c.comment.topic)
        return ret_success(message=_("The comment has been deleted."),
                           entity=c.comment.topic,
                           format=format)

    @RequireInstance
    def history(self, id, format='html'):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.show(c.comment)
        c.revisions_pager = NamedPager(
            'revisions', c.comment.revisions, tiles.revision.row, count=10,
            sorts={_("oldest"): sorting.entity_oldest,
                   _("newest"): sorting.entity_newest},
                                     default_sort=sorting.entity_newest)
        if format == 'json':
            return render_json(c.revisions_pager)
        return render('/comment/history.html')

    @RequireInstance
    @csrf.RequireInternalRequest()
    @ActionProtector(has_permission("comment.edit"))
    @validate(schema=CommentRevertForm(), form="history",
              post_only=False, on_get=True)
    def revert(self, id, format='html'):
        c.comment = get_entity_or_abort(model.Comment, id)
        require.comment.revert(c.comment)
        revision = self.form_result.get('to')
        if revision.comment != c.comment:
            return ret_abort(_("You're trying to revert to a revision which "
                               "is not partri of this comments history"),
                             code=400, format=format)
        rev = c.comment.create_revision(revision.text,
                                        c.user,
                                        sentiment=revision.sentiment)
        model.meta.Session.commit()
        event.emit(event.T_COMMENT_EDIT, c.user, instance=c.instance,
                   topics=[c.comment.topic], comment=c.comment,
                   topic=c.comment.topic, rev=rev)
        return ret_success(message=_("The comment has been reverted."),
                           entity=c.comment, format=format)
