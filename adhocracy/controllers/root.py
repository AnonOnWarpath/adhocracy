from datetime import datetime
import logging

from pylons import response, tmpl_context as c
from pylons.controllers.util import redirect
from pylons.decorators import validate

from adhocracy import model
from adhocracy.lib import helpers as h
from adhocracy.lib.auth import require
from adhocracy.lib.base import BaseController
from adhocracy.lib.static import StaticPage
from adhocracy.lib.templating import render
from adhocracy.lib.util import get_entity_or_abort

from proposal import ProposalFilterForm


log = logging.getLogger(__name__)


class RootController(BaseController):

    @validate(schema=ProposalFilterForm(), post_only=False, on_get=True)
    def index(self, format='html'):
        require.proposal.index()
        if c.instance:
            redirect(h.entity_url(c.instance))

        c.instances = model.Instance.all()[:5]
        c.page = StaticPage('index')

        #query = self.form_result.get('proposals_q')
        #proposals = libsearch.query.run(query,
        #                                entity_type=model.Proposal)[:10]
        c.milestones = model.Milestone.all()
        #c.proposals_pager = pager.proposals(proposals)
        #c.proposals = c.proposals_pager.here()
        c.stats_global = {
                "members": model.User.all_q().count(),
                "comments": model.Comment.all_q().count(),
                "proposals": model.Proposal.all_q().count(),
                "votes": model.Vote.all_q().count(),
            }

        #if format == 'json':
        #    return render_json(c.proposals_pager)
        return render('index.html')

    #@RequireInstance
    def dispatch_delegateable(self, id):
        dgb = get_entity_or_abort(model.Delegateable, id,
                                  instance_filter=False)
        redirect(h.entity_url(dgb))

    def sitemap_xml(self):
        if c.instance:
            redirect(h.base_url(None, path="/sitemap.xml"))
        c.delegateables = model.Delegateable.all()
        c.change_time = datetime.utcnow()
        response.content_type = "text/xml"
        return render("sitemap.xml")

    def robots_txt(self):
        response.content_type = "text/plain"
        if not c.instance:
            return render("robots.txt")
        return render("instance/robots.txt")
