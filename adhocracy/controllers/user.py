import logging
import urllib
from operator import attrgetter

import formencode
from formencode import ForEach, htmlfill, validators

from pylons import config, request, session, tmpl_context as c
from pylons.controllers.util import redirect
from pylons.decorators import validate
from pylons.i18n import _

from repoze.what.plugins.pylonshq import ActionProtector

from adhocracy import forms, model
from adhocracy import i18n
from adhocracy.lib import democracy, event, helpers as h, pager
from adhocracy.lib import  sorting, search as libsearch, tiles, text
from adhocracy.lib.auth import require
from adhocracy.lib.auth.authorization import has_permission
from adhocracy.lib.auth.csrf import RequireInternalRequest
from adhocracy.lib.base import BaseController
from adhocracy.lib.instance import RequireInstance
import adhocracy.lib.mail as libmail
from adhocracy.lib.pager import (NamedPager, solr_global_users_pager,
                                 solr_instance_users_pager)
from adhocracy.lib.queue import post_update
from adhocracy.lib.templating import render, render_json
from adhocracy.lib.util import get_entity_or_abort, random_token


log = logging.getLogger(__name__)


class UserCreateForm(formencode.Schema):
    allow_extra_fields = True
    user_name = formencode.All(validators.PlainText(not_empty=True),
                               forms.UniqueUsername(),
                               forms.ContainsChar())
    email = formencode.All(validators.Email(),
                           forms.UniqueEmail())
    password = validators.String(not_empty=True)
    password_confirm = validators.String(not_empty=True)
    password_confirm = validators.String(not_empty=True)
    chained_validators = [validators.FieldsMatch(
         'password', 'password_confirm')]


class UserUpdateForm(formencode.Schema):
    allow_extra_fields = True
    display_name = validators.String(not_empty=False)
    email = validators.Email(not_empty=True)
    #locale = validators.String(not_empty=False)
    password_change = validators.String(not_empty=False)
    password_confirm = validators.String(not_empty=False)
    chained_validators = [validators.FieldsMatch(
        'password_change', 'password_confirm')]
    bio = validators.String(max=1000, min=0, not_empty=False)
    no_help = validators.StringBool(not_empty=False, if_empty=False,
                                    if_missing=False)
    page_size = validators.Int(min=1, max=100, not_empty=False,
                               if_empty=10, if_missing=10)
    email_priority = validators.Int(min=0, max=6, not_empty=False,
                                    if_missing=3)


class UserCodeForm(formencode.Schema):
    allow_extra_fields = True
    c = validators.String(not_empty=False)


class UserManageForm(formencode.Schema):
    allow_extra_fields = True
    group = forms.ValidGroup()


class UserResetApplyForm(formencode.Schema):
    allow_extra_fields = True
    email = validators.Email(not_empty=True)


class UserGroupmodForm(formencode.Schema):
    allow_extra_fields = True
    to_group = forms.ValidGroup()


class UserFilterForm(formencode.Schema):
    allow_extra_fields = True
    users_q = validators.String(max=255, not_empty=False, if_empty=u'',
                                if_missing=u'')
    users_group = validators.String(max=255, not_empty=False, if_empty=None,
                                    if_missing=None)


class UserBadgesForm(formencode.Schema):
    allow_extra_fields = True
    badge = ForEach(forms.ValidBadge())


class UserController(BaseController):

    @RequireInstance
    @validate(schema=UserFilterForm(), post_only=False, on_get=True)
    def index(self, format='html'):
        require.user.index()

        c.users_pager = solr_instance_users_pager(c.instance)

        #if format == 'json':
        ##    return render_json(c.users_pager)

        return render("/user/index.html")

    def all(self):
        require.user.index()
        c.users_pager = solr_global_users_pager()
        return render("/user/all.html")

    def new(self):
        captacha_enabled = config.get('recaptcha.public_key', "")
        c.recaptcha = captacha_enabled and h.recaptcha.displayhtml() 
        return render("/user/register.html")

    @RequireInternalRequest(methods=['POST'])
    @validate(schema=UserCreateForm(), form="new", post_only=True)
    def create(self):
        require.user.create()
        # SPAM protection recaptcha
        captacha_enabled = config.get('recaptcha.public_key', "")
        if captacha_enabled:
            recaptcha_response = h.recaptcha.submit()
            if not recaptcha_response.is_valid:
                c.recaptcha = h.recaptcha.displayhtml(error=recaptcha_response.error_code) 
                redirect("/register")
        # SPAM protection hidden input
        input_css = self.form_result.get("input_css")
        input_js = self.form_result.get("input_js")
        if input_css or input_js:
            redirect("/")

        #create user
        user = model.User.create(self.form_result.get("user_name"),
                                 self.form_result.get("email").lower(),
                                 password=self.form_result.get("password"),
                                 locale=c.locale)
        model.meta.Session.commit()

        event.emit(event.T_USER_CREATE, user)
        libmail.send_activation_link(user)

        if c.instance:
            membership = model.Membership(user, c.instance,
                                          c.instance.default_group)
            model.meta.Session.expunge(membership)
            model.meta.Session.add(membership)
            model.meta.Session.commit()

        # info message
        h.flash(_("You have successfully registered as user %s.") % user.name,
                'success')
        redirect("/perform_login?%s" % urllib.urlencode({
                 'login': self.form_result.get("user_name").encode('utf-8'),
                 'password': self.form_result.get("password").encode('utf-8')
                }))

    @ActionProtector(has_permission("user.edit"))
    def edit(self, id):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.edit(c.page_user)
        c.locales = i18n.LOCALES
        return render("/user/edit.html")

    @RequireInternalRequest(methods=['POST'])
    @ActionProtector(has_permission("user.edit"))
    @validate(schema=UserUpdateForm(), form="edit", post_only=True)
    def update(self, id):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.edit(c.page_user)
        if self.form_result.get("password_change"):
            c.page_user.password = self.form_result.get("password_change")
        c.page_user.display_name = self.form_result.get("display_name")
        c.page_user.page_size = self.form_result.get("page_size")
        c.page_user.no_help = self.form_result.get("no_help")
        c.page_user.bio = self.form_result.get("bio")
        email = self.form_result.get("email").lower()
        email_changed = email != c.page_user.email
        c.page_user.email = email
        c.page_user.email_priority = self.form_result.get("email_priority")
        #if c.page_user.twitter:
        #    c.page_user.twitter.priority = \
        #        self.form_result.get("twitter_priority")
        #    model.meta.Session.add(c.page_user.twitter)
        #locale = Locale(self.form_result.get("locale"))
        #if locale and locale in i18n.LOCALES:
        #    c.page_user.locale = locale
        model.meta.Session.add(c.page_user)
        model.meta.Session.commit()
        if email_changed:
            libmail.send_activation_link(c.page_user)

        if c.page_user == c.user:
            event.emit(event.T_USER_EDIT, c.user)
        else:
            event.emit(event.T_USER_ADMIN_EDIT, c.page_user, admin=c.user)
        redirect(h.entity_url(c.page_user))

    def reset_form(self):
        return render("/user/reset_form.html")

    @validate(schema=UserResetApplyForm(), form="reset", post_only=True)
    def reset_request(self):
        c.page_user = model.User.find_by_email(self.form_result.get('email'))
        if c.page_user is None:
            msg = _("There is no user registered with that email address.")
            return htmlfill.render(self.reset_form(), errors=dict(email=msg))
        c.page_user.reset_code = random_token()
        model.meta.Session.add(c.page_user)
        model.meta.Session.commit()
        url = h.base_url(c.instance,
                         path="/user/%s/reset?c=%s" % (c.page_user.user_name,
                                                       c.page_user.reset_code))
        body = _("you have requested that your password be reset. In order "
                 "to confirm the validity of your claim, please open the "
                 "link below in your browser:") + "\r\n\r\n  " + url
        libmail.to_user(c.page_user, _("Reset your password"), body)
        return render("/user/reset_pending.html")

    @validate(schema=UserCodeForm(), form="reset_form", post_only=False,
              on_get=True)
    def reset(self, id):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        try:
            if c.page_user.reset_code != self.form_result.get('c'):
                raise ValueError()
            new_password = random_token()
            c.page_user.password = new_password
            model.meta.Session.add(c.page_user)
            model.meta.Session.commit()
            body = (_("your password has been reset. It is now:") +
                    "\r\n\r\n  " + new_password + "\r\n\r\n" +
                    _("Please login and change the password in your user "
                      "settings."))
            libmail.to_user(c.page_user, _("Your new password"), body)
            h.flash(_("Success. You have been sent an email with your new "
                      "password."), 'success')
        except Exception:
            h.flash(_("The reset code is invalid. Please repeat the password"
                      " recovery procedure."), 'error')
        redirect('/login')

    @validate(schema=UserCodeForm(), form="edit", post_only=False, on_get=True)
    def activate(self, id):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        #require.user.edit(c.page_user)
        try:
            if c.page_user.activation_code != self.form_result.get('c'):
                raise ValueError()
            c.page_user.activation_code = None
            model.meta.Session.commit()
            h.flash(_("Your email has been confirmed."), 'success')
        except Exception:
            log.exception("Invalid activation code")
            h.flash(_("The activation code is invalid. Please have it "
                      "resent."), 'error')
        redirect(h.entity_url(c.page_user))

    @RequireInternalRequest()
    def resend(self, id):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.edit(c.page_user)
        libmail.send_activation_link(c.page_user)
        h.flash(_("The activation link has been re-sent to your email "
                  "address."), 'notice')
        redirect(h.entity_url(c.page_user, member='edit'))

    def show(self, id, format='html'):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)

        if format == 'json':
            return render_json(c.page_user)

        query = model.meta.Session.query(model.Event)
        query = query.filter(model.Event.user == c.page_user)
        query = query.order_by(model.Event.time.desc())
        query = query.limit(10)
        if format == 'rss':
            return event.rss_feed(
                query.all(), "%s Latest Actions" % c.page_user.name,
                h.base_url(None, path='/user/%s' % c.page_user.user_name),
                c.page_user.bio)
        c.events_pager = pager.events(query.all())
        c.tile = tiles.user.UserTile(c.page_user)
        self._common_metadata(c.page_user, add_canonical=True)
        return render("/user/show.html")

    def login(self):
        session['came_from'] = request.params.get('came_from',
                                                  h.base_url(c.instance))
        session.save()
        return render('/user/login.html')

    def perform_login(self):
        pass  # managed by repoze.who

    def post_login(self):
        if c.user:
            url = h.base_url(c.instance)
            if 'came_from' in session:
                url = session.get('came_from')
                del session['came_from']
                session.save()
            h.flash(_("You have successfully logged in."), 'success')
            redirect(str(url))
        else:
            session.delete()
            return formencode.htmlfill.render(
                render("/user/login.html"),
                errors={"login": _("Invalid user name or password")})

    def logout(self):
        pass  # managed by repoze.who

    def post_logout(self):
        session.delete()
        redirect(h.base_url(c.instance))

    @ActionProtector(has_permission("user.view"))
    def complete(self):
        prefix = unicode(request.params.get('q', u''))
        users = model.User.complete(prefix, 15)
        results = []
        for user in users:
            if user == c.user:
                continue
            display = "%s (%s)" % (user.user_name, user.name) if \
                      user.display_name else user.name
            results.append(dict(display=display, user=user.user_name))
        return render_json(results)

    @RequireInstance
    def votes(self, id, format='html'):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)
        decisions = democracy.Decision.for_user(c.page_user, c.instance)

        if format == 'json':
            return render_json(list(decisions))

        decisions = filter(lambda d: d.poll.action != model.Poll.RATE,
                           decisions)
        c.decisions_pager = pager.user_decisions(decisions)
        self._common_metadata(c.page_user, member='votes')
        return render("/user/votes.html")

    @RequireInstance
    def delegations(self, id, format='html'):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)
        scope_id = request.params.get('scope', None)

        if format == 'json':
            delegations = model.Delegation.find_by_principal(c.page_user)
            scope = model.Delegateable.find(scope_id) if scope_id else None
            if scope is not None:
                delegations = [d for d in delegations if d.is_match(scope)]
            delegations_pager = pager.delegations(delegations)
            return render_json(delegations_pager)

        c.dgbs = []
        if scope_id:
            c.scope = forms.ValidDelegateable().to_python(scope_id)
            c.dgbs = [c.scope] + c.scope.children
        else:
            c.dgbs = model.Delegateable.all(instance=c.instance)
        c.nodeClass = democracy.DelegationNode
        self._common_metadata(c.page_user, member='delegations')
        return render("/user/delegations.html")

    def instances(self, id, format='html'):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)
        instances = [i for i in c.page_user.instances if i.is_shown()]
        c.instances_pager = pager.instances(instances)

        if format == 'json':
            return render_json(c.instances_pager)

        self._common_metadata(c.page_user, member='instances',
                              add_canonical=True)
        return render("/user/instances.html")

    @RequireInstance
    def proposals(self, id, format='html'):
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)
        proposals = model.Proposal.find_by_creator(c.page_user)
        c.proposals_pager = pager.proposals(proposals)

        if format == 'json':
            return render_json(c.proposals_pager)

        self._common_metadata(c.page_user, member='proposals')
        return render("/user/proposals.html")

    def watchlist(self, id, format='html'):
        require.watch.index()
        c.page_user = get_entity_or_abort(model.User, id,
                                          instance_filter=False)
        require.user.show(c.page_user)
        watches = model.Watch.all_by_user(c.page_user)
        entities = [w.entity for w in watches if (w.entity is not None) \
            and (not isinstance(w.entity, unicode))]

        c.entities_pager = NamedPager(
            'watches', entities, tiles.dispatch_row_with_comments,
            sorts={_("oldest"): sorting.entity_oldest,
                   _("newest"): sorting.entity_newest},
            default_sort=sorting.entity_newest)

        if format == 'json':
            return render_json(c.entities_pager)

        self._common_metadata(c.page_user, member='watchlist')
        return render("/user/watchlist.html")

    @RequireInstance
    @RequireInternalRequest()
    @validate(schema=UserGroupmodForm(), form="edit",
              post_only=False, on_get=True)
    def groupmod(self, id):
        c.page_user = get_entity_or_abort(model.User, id)
        require.user.supervise(c.page_user)
        to_group = self.form_result.get("to_group")
        if not to_group.code in model.Group.INSTANCE_GROUPS:
            h.flash(_("Cannot make %(user)s a member of %(group)s") % {
                        'user': c.page_user.name,
                        'group': to_group.group_name},
                    'error')
            redirect(h.entity_url(c.page_user))
        had_vote = c.page_user._has_permission("vote.cast")
        for membership in c.page_user.memberships:
            if (not membership.is_expired() and
                membership.instance == c.instance):
                membership.group = to_group
        model.meta.Session.commit()
        event.emit(event.T_INSTANCE_MEMBERSHIP_UPDATE, c.page_user,
                   instance=c.instance, group=to_group, admin=c.user)
        if had_vote and not c.page_user._has_permission("vote.cast"):
            # user has lost voting privileges
            c.page_user.revoke_delegations(c.instance)
        model.meta.Session.commit()
        redirect(h.entity_url(c.page_user))

    @RequireInstance
    @RequireInternalRequest()
    def ban(self, id):
        c.page_user = get_entity_or_abort(model.User, id)
        require.user.manage(c.page_user)
        c.page_user.banned = True
        model.meta.Session.commit()
        h.flash(_("The account has been suspended."), 'success')
        redirect(h.entity_url(c.page_user))

    @RequireInstance
    @RequireInternalRequest()
    def unban(self, id):
        c.page_user = get_entity_or_abort(model.User, id)
        require.user.manage(c.page_user)
        c.page_user.banned = False
        model.meta.Session.commit()
        h.flash(_("The account has been re-activated."), 'success')
        redirect(h.entity_url(c.page_user))

    def ask_delete(self, id):
        c.page_user = get_entity_or_abort(model.User, id)
        require.user.delete(c.page_user)
        return render('/user/ask_delete.html')

    @RequireInternalRequest()
    def delete(self, id):
        c.page_user = get_entity_or_abort(model.User, id)
        require.user.delete(c.page_user)
        c.page_user.delete()
        model.meta.Session.commit()
        h.flash(_("The account has been deleted."), 'success')
        if c.instance is not None:
            redirect(h.instance.url(c.instance))
        else:
            redirect(h.site.base_url(None))

    @validate(schema=UserFilterForm(), post_only=False, on_get=True)
    def filter(self):
        require.user.index()
        query = self.form_result.get('users_q')
        users = libsearch.query.run(query + u"*", entity_type=model.User,
                                    instance_filter=True)
        c.users_pager = pager.users(users, has_query=True)
        return c.users_pager.here()

    @ActionProtector(has_permission("global.admin"))
    def badges(self, id, errors=None):
        c.badges = model.Badge.all()
        c.badges = filter(lambda x: not x.badge_delegateable, c.badges)
        c.badges = sorted(c.badges, key=attrgetter('title'))
        c.page_user = get_entity_or_abort(model.User, id)
        defaults = {'badge': [str(badge.id) for badge in c.page_user.badges]}
        return formencode.htmlfill.render(
            render("/user/badges.html"),
            defaults=defaults)

    @RequireInternalRequest()
    @validate(schema=UserBadgesForm(), form='badges')
    @ActionProtector(has_permission("global.admin"))
    def update_badges(self, id):
        user = get_entity_or_abort(model.User, id)
        badges = self.form_result.get('badge')
        creator = c.user

        added = []
        removed = []
        for badge in user.badges:
            if badge not in badges:
                removed.append(badge)
                user.badges.remove(badge)

        for badge in badges:
            if badge not in user.badges:
                model.UserBadge(user, badge, creator)
                added.append(badge)

        model.meta.Session.commit()
        post_update(user, model.update.UPDATE)
        redirect(h.entity_url(user))

    def _common_metadata(self, user, member=None, add_canonical=False):
        bio = user.bio
        if not bio:
            bio = _("%(user)s is using Adhocracy, a democratic "
                    "decision-making tool.") % {'user': c.page_user.name}
        description = h.truncate(text.meta_escape(bio), length=200,
                                 whole_word=True)
        h.add_meta("description", description)
        h.add_meta("dc.title", text.meta_escape(user.name))
        h.add_meta("dc.date", user.access_time.strftime("%Y-%m-%d"))
        h.add_meta("dc.author", text.meta_escape(user.name))
        h.add_rss(_("%(user)ss Activity") % {'user': user.name},
                  h.entity_url(user, format='rss'))
        if c.instance and not user.is_member(c.instance):
            h.flash(_("%s is not a member of %s") % (user.name,
                                                     c.instance.label),
                    'notice')
        if user.banned:
            h.flash(_("%s is banned from the system.") % user.name, 'notice')
