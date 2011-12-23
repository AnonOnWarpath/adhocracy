import logging

import formencode
from formencode import htmlfill, Invalid

from pylons import request, tmpl_context as c
from pylons.controllers.util import redirect
from pylons.i18n import _

from adhocracy import forms, model
from adhocracy.lib import helpers as h, tiles
from adhocracy.lib.auth import require
from adhocracy.lib.auth.csrf import RequireInternalRequest
from adhocracy.lib.base import BaseController
from adhocracy.lib.instance import RequireInstance
from adhocracy.lib.templating import render
from adhocracy.lib.util import get_entity_or_abort

log = logging.getLogger(__name__)


class SelectionCreateForm(formencode.Schema):
    allow_extra_fields = True
    page = forms.ValidPage()


class SelectionController(BaseController):

    @RequireInstance
    def index(self, proposal_id, format="html"):
        return self.not_implemented()

    @RequireInstance
    def propose(self, proposal_id, errors=None):
        require.norm.propose()
        return self._new(proposal_id, '/selection/propose.html', errors)

    @RequireInstance
    def include(self, proposal_id, errors={}):
        return self._new(proposal_id, '/selection/include.html', errors)

    def _new(self, proposal_id, template, errors):
        c.proposal = get_entity_or_abort(model.Proposal, proposal_id)
        require.selection.create(c.proposal)
        defaults = dict(request.params)
        c.proposal_tile = tiles.proposal.ProposalTile(c.proposal)
        return htmlfill.render(render(template), defaults=defaults,
                               errors=errors, force_defaults=False)

    @RequireInstance
    @RequireInternalRequest(methods=['POST'])
    def create(self, proposal_id, format='html'):
        c.proposal = get_entity_or_abort(model.Proposal, proposal_id)
        require.selection.create(c.proposal)
        try:
            self.form_result = SelectionCreateForm().to_python(request.params)
        except Invalid, i:
            return self.propose(proposal_id, errors=i.unpack_errors())

        page = self.form_result.get('page')
        selection = model.Selection.create(c.proposal, page,
                                           c.user)
        model.meta.Session.commit()
        # TODO implement:
        # TODO emit an event

        if len(page.variants) < 2:
            return redirect(h.entity_url(page, member='branch',
                                         query={'proposal': c.proposal.id}))
        return redirect(h.entity_url(selection))

    def edit(self, proposal_id, id, errors={}):
        return self.not_implemented()

    def update(self, proposal_id, id, format='html'):
        return self.not_implemented()

    @RequireInstance
    def show(self, proposal_id, id, format='html'):
        c.selection = get_entity_or_abort(model.Selection, id)
        redirect(h.selection.url(c.selection))

    @RequireInstance
    def ask_delete(self, proposal_id, id):
        c.proposal = get_entity_or_abort(model.Proposal, proposal_id)
        c.selection = get_entity_or_abort(model.Selection, id)
        require.selection.delete(c.selection)
        c.proposal_tile = tiles.proposal.ProposalTile(c.proposal)

        return render("/selection/ask_delete.html")

    @RequireInstance
    @RequireInternalRequest()
    def delete(self, proposal_id, id):
        c.proposal = get_entity_or_abort(model.Proposal, proposal_id)
        c.selection = get_entity_or_abort(model.Selection, id)
        require.selection.delete(c.selection)

        # TODO implement
        #event.emit(event.T_PROPOSAL_DELETE, c.user, instance=c.instance,
        #           topics=[c.proposal], proposal=c.proposal)
        c.selection.delete()
        model.meta.Session.commit()
        h.flash(_("The inclusion of %s has been deleted.") %
                c.selection.page.title,
                'success')

        redirect(h.entity_url(c.proposal))
