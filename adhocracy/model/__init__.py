"""The application's model objects"""
from sqlalchemy import orm
from sqlalchemy.orm import mapper, relation, backref, synonym

import meta
from adhocracy.model.update import SessionModificationExtension

from adhocracy.model.user import User, user_table
from adhocracy.model.openid import OpenID, openid_table
from adhocracy.model.twitter import Twitter, twitter_table
from adhocracy.model.badge import Badge, badge_table
from adhocracy.model.userbadges import UserBadge, user_badges_table
from adhocracy.model.delegateablebadge import (DelegateableBadge,
                                               delegateable_badge_table)
from adhocracy.model.group import Group, group_table
from adhocracy.model.permission import (Permission, group_permission_table,
                                        permission_table)
from adhocracy.model.delegateable import (Delegateable, delegateable_table,
                                          category_graph)
from adhocracy.model.delegation import Delegation, delegation_table
from adhocracy.model.proposal import Proposal, proposal_table
from adhocracy.model.poll import Poll, poll_table
from adhocracy.model.vote import Vote, vote_table
from adhocracy.model.revision import Revision, revision_table
from adhocracy.model.comment import Comment, comment_table
from adhocracy.model.instance import Instance, instance_table
from adhocracy.model.membership import Membership, membership_table
from adhocracy.model.watch import Watch, watch_table
from adhocracy.model.event import Event, event_topic_table, event_table
from adhocracy.model.tally import Tally, tally_table
from adhocracy.model.tag import Tag, tag_table
from adhocracy.model.tagging import Tagging, tagging_table
from adhocracy.model.page import Page, page_table
from adhocracy.model.text import Text, text_table
from adhocracy.model.milestone import Milestone, milestone_table
from adhocracy.model.selection import Selection, selection_table


mapper(User, user_table, properties={
    'email': synonym('_email', map_column=True),
    'locale': synonym('_locale', map_column=True),
    'password': synonym('_password', map_column=True)
    })


mapper(Twitter, twitter_table, properties={
    'user': relation(User, lazy=False,
                     primaryjoin=twitter_table.c.user_id == user_table.c.id,
                     backref=backref('twitters', cascade='delete'))
    })


mapper(UserBadge, user_badges_table,
       properties={
           'creator': relation(
               User, lazy=True,
               primaryjoin=user_badges_table.c.creator_id == user_table.c.id,
               backref=backref('badges_created')),
           'user': relation(
               User, lazy=True,
               primaryjoin=(user_badges_table.c.user_id ==
                            user_table.c.id),
               backref=backref('userbadges')),
           'badge': relation(Badge)})


mapper(DelegateableBadge, delegateable_badge_table,
       properties={
           'creator': relation(
               User, lazy=True,
               primaryjoin=(delegateable_badge_table.c.creator_id ==
                            user_table.c.id),
               backref=backref('delegateablebadges_created')),
           'delegateable': relation(
               Delegateable, lazy=True,
               primaryjoin=(delegateable_badge_table.c.delegateable_id ==
                         delegateable_table.c.id),
               backref=backref('delegateablebadges')),
           'badge': relation(Badge)})


mapper(Badge, badge_table,
       properties={
           'users': relation(
               User, secondary=user_badges_table,
               primaryjoin=(badge_table.c.id ==
                            user_badges_table.c.badge_id),
               secondaryjoin=(user_badges_table.c.user_id ==
                              user_table.c.id),
               backref=backref('badges', lazy='joined'),
               lazy=False),
           'delegateables': relation(
               Delegateable,
               secondary=delegateable_badge_table,
               primaryjoin=(badge_table.c.id ==
                            delegateable_badge_table.c.badge_id),
               secondaryjoin=(delegateable_badge_table.c.delegateable_id ==
                              delegateable_table.c.id),
               backref=backref('badges', lazy='joined'),
               lazy=False),
           'group': relation(
               Group, primaryjoin=(group_table.c.id ==
                                   badge_table.c.group_id),
               lazy=False)
           })


mapper(OpenID, openid_table, properties={
    'user': relation(User, lazy=False,
                     primaryjoin=openid_table.c.user_id == user_table.c.id,
                     backref=backref('_openids', cascade='delete'))
    })


mapper(Group, group_table)


mapper(Permission, permission_table, properties={
    'groups': relation(Group, secondary=group_permission_table, lazy=True,
                       backref=backref('permissions', lazy=False))
    })


mapper(
    Delegateable, delegateable_table,
    polymorphic_on=delegateable_table.c.type, properties={
    'parents': relation(
            Delegateable, lazy=True, secondary=category_graph,
            primaryjoin=delegateable_table.c.id == category_graph.c.parent_id,
            secondaryjoin=category_graph.c.child_id == delegateable_table.c.id
            ),
    'children': relation(
            Delegateable, lazy=True, secondary=category_graph,
            primaryjoin=delegateable_table.c.id == category_graph.c.child_id,
            secondaryjoin=category_graph.c.parent_id == delegateable_table.c.id
            ),
    'creator': relation(
            User,
            primaryjoin=delegateable_table.c.creator_id == user_table.c.id,
            backref=backref('delegateables', cascade='delete')),
    'instance': relation(
            Instance, lazy=True,
            primaryjoin=(delegateable_table.c.instance_id ==
                         instance_table.c.id),
            backref=backref('delegateables', cascade='delete')),
    'milestone': relation(
            Milestone, lazy=True,
            primaryjoin=(delegateable_table.c.milestone_id ==
                         milestone_table.c.id),
            backref=backref('delegateables'))
    })


mapper(Page, page_table, inherits=Delegateable, polymorphic_identity='page',
       properties={})


mapper(Proposal, proposal_table, inherits=Delegateable,
       polymorphic_identity='proposal', properties={
    'description': relation(
            Page,
            primaryjoin=proposal_table.c.description_id == page_table.c.id,
            uselist=False, lazy=True, backref=backref('_proposal')),
    'rate_poll': relation(
            Poll, primaryjoin=proposal_table.c.rate_poll_id == poll_table.c.id,
            uselist=False, lazy=False),
    'adopt_poll': relation(
            Poll,
            primaryjoin=proposal_table.c.adopt_poll_id == poll_table.c.id,
            uselist=False, lazy=True)
    })

mapper(Milestone, milestone_table, properties={
    'creator': relation(
            User, lazy=False, backref=backref('milestones', lazy=True)),
    'instance': relation(
            Instance, lazy=False,
            primaryjoin=milestone_table.c.instance_id == instance_table.c.id)
    })

mapper(Comment, comment_table, properties={
    'creator': relation(
            User, lazy=False, backref=backref('comments', lazy=True)),
    'topic': relation(
            Delegateable, backref=backref('comments', cascade='all')),
    'reply': relation(
            Comment, cascade='delete', remote_side=comment_table.c.id,
            backref=backref('replies', lazy=True)),
    'poll': relation(
            Poll, primaryjoin=comment_table.c.poll_id == poll_table.c.id,
            uselist=False, lazy=False)
    })


mapper(Revision, revision_table, properties={
    'user': relation(
            User, lazy=True,
            primaryjoin=revision_table.c.user_id == user_table.c.id,
            backref=backref('revisions', lazy=True, cascade='all')),
    'comment': relation(Comment, lazy=False, backref=backref(
                'revisions', cascade='all', lazy=False,
                order_by=revision_table.c.create_time.desc())),
    })


mapper(Delegation, delegation_table, properties={
    'agent': relation(
            User, primaryjoin=delegation_table.c.agent_id == user_table.c.id,
            backref=backref('agencies', cascade='all')),
    'principal': relation(
            User, primaryjoin=(delegation_table.c.principal_id ==
                               user_table.c.id),
            backref=backref('delegated', cascade='all')),
    'scope': relation(
            Delegateable, lazy=False,
            primaryjoin=delegation_table.c.scope_id == delegateable_table.c.id,
            backref=backref('delegations', cascade='all'))
    })


mapper(Poll, poll_table, properties={
    'user': relation(
            User,
            primaryjoin=poll_table.c.user_id == user_table.c.id,
            lazy=True),
    'subject': synonym('_subject', map_column=True),
    'scope': relation(
            Delegateable,
            primaryjoin=poll_table.c.scope_id == delegateable_table.c.id,
            lazy=True,
            backref=backref('polls', cascade='all', lazy=True,
                            order_by=poll_table.c.begin_time.desc()))
    })


mapper(Vote, vote_table, properties={
    'user': relation(
            User, primaryjoin=vote_table.c.user_id == user_table.c.id,
            backref=backref('votes', cascade='delete',
                            order_by=vote_table.c.create_time.desc())),
    'poll': relation(
            Poll,
            backref=backref('votes',
                            order_by=vote_table.c.create_time.desc())),
    'delegation': relation(
            Delegation,
            primaryjoin=vote_table.c.delegation_id == delegation_table.c.id,
            backref=backref('votes', cascade='delete'))
    })


mapper(Instance, instance_table, properties={
    'creator': relation(
            User,
            primaryjoin=instance_table.c.creator_id == user_table.c.id,
                        backref=backref('created_instances')),
    'locale': synonym('_locale', map_column=True),
    'default_group': relation(Group, lazy=True)
    })


mapper(Membership, membership_table, properties={
    'user': relation(
            User, lazy=True,
            primaryjoin=membership_table.c.user_id == user_table.c.id,
            backref=backref('memberships', lazy=True)),
    'instance': relation(Instance, backref=backref('memberships'), lazy=True),
    'group': relation(Group, backref=backref('memberships'), lazy=False)
    })


mapper(Watch, watch_table, properties={
    'user': relation(User,
                     primaryjoin=watch_table.c.user_id == user_table.c.id)
    })


mapper(Event, event_table, properties={
    'data': synonym('_data', map_column=True),
    'event': synonym('_event', map_column=True),
    'user': relation(
            User, lazy=False,
            primaryjoin=event_table.c.user_id == user_table.c.id),
    'instance': relation(
            Instance, lazy=True,
            primaryjoin=event_table.c.instance_id == instance_table.c.id),
    'topics': relation(Delegateable, secondary=event_topic_table, lazy=True)
    })


mapper(Tally, tally_table, properties={
    'poll': relation(
            Poll, backref=backref('tallies',
                                  order_by=tally_table.c.create_time.desc(),
                                  lazy=True)),
    'vote': relation(Vote, backref=backref('tally', uselist=False))
    })


mapper(Tag, tag_table)


mapper(Tagging, tagging_table, properties={
    'creator': relation(
            User, lazy=True,
            primaryjoin=tagging_table.c.creator_id == user_table.c.id,
            backref=backref('tagged')),
    'delegateable': relation(
            Delegateable, lazy=True,
            primaryjoin=(tagging_table.c.delegateable_id ==
                         delegateable_table.c.id),
            backref=backref('taggings')),
    'tag': relation(
            Tag, lazy=False,
            primaryjoin=tagging_table.c.tag_id == tag_table.c.id,
            backref=backref('taggings', lazy=True))
    })


mapper(Text, text_table, properties={
    'user': relation(
            User, lazy=True,
            primaryjoin=text_table.c.user_id == user_table.c.id),
    'parent': relation(
            Text, lazy=True, uselist=False,
            primaryjoin=text_table.c.parent_id == text_table.c.id),
    'page': relation(
            Page, lazy=True, backref=backref(
                '_texts', lazy=False,
                order_by=text_table.c.create_time.desc()),
            primaryjoin=text_table.c.page_id == page_table.c.id)
    })


mapper(Selection, selection_table, properties={
    'proposal': relation(
            Proposal, lazy=True, backref=backref('_selections'),
            primaryjoin=selection_table.c.proposal_id == proposal_table.c.id),
    'page': relation(
            Page, lazy=True, backref=backref('_selections'),
            primaryjoin=selection_table.c.page_id == page_table.c.id)
    })


def init_model(engine):
    """Call me before using any of the tables or classes in the model"""
    if meta.Session is not None:
        return
    sm = orm.sessionmaker(autoflush=True,
                          bind=engine,
                          extension=SessionModificationExtension())
    meta.engine = engine
    meta.Session = orm.scoped_session(sm)
