from datetime import datetime, timedelta
import random
import string

from adhocracy import i18n
from adhocracy import model

#  These functions should all go as convenience functions on the
#  respective models


def tt_get_admin():
    admin = model.User(tt_make_str(), u"admin@null.naught", u"password")
    model.meta.Session.add(admin)
    model.meta.Session.flush()
    return admin


def tt_get_instance():
    instance = model.Instance.find(u"test")
    if not instance:
        instance = model.Instance(u"test", u"foo schnasel", tt_make_user())
        model.meta.Session.add(instance)
        model.meta.Session.flush()
    # shouldn't setup_threads instance be returned if available?
    model.instance_filter.setup_thread(instance)
    return instance


def tt_make_str(length=20):
    return u''.join([random.choice(string.letters) for i in range(length)])


def tt_make_proposal(creator=None, voting=False):
    instance = tt_get_instance()
    if creator is None:
        creator = tt_make_user()
    proposal = model.Proposal(instance, tt_make_str(), creator)
    model.meta.Session.add(proposal)
    model.meta.Session.flush()

    if voting:
        an_hour_ago = datetime.utcnow() - timedelta(hours=2)
        poll = model.Poll.create(proposal, creator, model.Poll.ADOPT)
        poll.begin_time = an_hour_ago
        proposal.polls.append(poll)
        model.meta.Session.flush()

    return proposal


def tt_make_user(name=None, instance_group=None):
    if name is not None:
        name = unicode(name)
        user = model.meta.Session.query(model.User)
        user = user.filter(model.User.user_name == name).first()
        if user:
            return user

    if name is None:
        name = tt_make_str()
    user = model.User(name, u"test@test.test", u"test",
                      i18n.get_default_locale())

    default_group = model.Group.by_code(model.Group.CODE_DEFAULT)
    default_membership = model.Membership(user, None, default_group)
    memberships = [default_membership]
    if instance_group:
        instance = tt_get_instance()
        group_membership = model.Membership(user, instance, instance_group)
        memberships.append(group_membership)
    user.memberships = memberships
    model.meta.Session.add(user)
    model.meta.Session.flush()  # write to db and updated db
                                # generated attributes
    return user


def tt_drop_db():
    '''
    drop the data tables and if exists the migrate_version table
    '''
    model.meta.data.drop_all(bind=model.meta.engine)
    model.meta.engine.execute("DROP TABLE IF EXISTS migrate_version")


def tt_create_db():
    '''create the database tables'''
    model.meta.data.create_all(bind=model.meta.engine)
