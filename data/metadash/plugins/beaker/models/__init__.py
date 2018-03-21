"""
ORM map for beaker
"""
import logging
import psycopg2

from datetime import datetime, timedelta

from metadash.exceptions import RemoteAuthError, RemoteServerError
from metadash.cache import get_or_create

from sqlalchemy import (
    Table, Column, Integer, String, Boolean, DateTime, ForeignKey,
    create_engine, func, text, and_, or_)
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.orm.interfaces import MapperOption
from sqlalchemy.orm.query import Query
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import registry

logger = logging.getLogger('beaker')

registry.register("postgresql.teiid", "metadash.plugins.beaker.models.teiid_dialect", "TeiidDialect")

BEAKER_URL = 'https://beaker.engineering.redhat.com/'
TEIID_URL = 'virtualdb.engineering.redhat.com'
TEIID_PORT = 5433

BEAKER_JOB_STATUS = ["Queued", "Installing", "Updating", "Running", "Canceled", "Aborted"]
BEAKER_JOB_RESULTS = ["New", "Pass", "Warn", "Panic"]

BEAKER_JOB_STATUS_CRIT = ["Cancelled", "Aborted"]
BEAKER_JOB_RESULTS_CRIT = ["Warn", "Panic"]

BeakerBase = declarative_base()


class BeakerJob(BeakerBase):
    """
    Presenting only part of columns
    all_columns = ['id', 'dirty_version', 'clean_version', 'owner_id', 'group_id', 'whiteboard', 'result', 'status', 'ttasks', 'ntasks', 'ptasks', 'wtasks', 'ftasks', 'ktasks', 'retention_tag_id', 'product_id', 'deleted', 'to_delete', 'submitter_id', 'extra_xml']
    """
    __tablename__ = "beaker.job"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("beaker.tg_user.user_id"))
    group_id = Column(Integer, ForeignKey("beaker.tg_group.group_id"))
    ttasks = Column(Integer)
    ntasks = Column(Integer)
    ptasks = Column(Integer)
    wtasks = Column(Integer)
    ftasks = Column(Integer)
    ktasks = Column(Integer)
    status = Column(String())
    result = Column(String())
    whiteboard = Column(String())

    owner = relationship('BeakerUser', back_populates='jobs')
    group = relationship('BeakerGroup', back_populates='jobs')
    recipe_set = relationship('BeakerRecipeSet', back_populates='job')

    def as_dict(self, detailed=False):
        ret = {}
        for c in self.__table__.columns:
            ret[c.name] = getattr(self, c.name)
        ret['group'] = self.group.group_name if self.group else ''
        ret['owner'] = self.owner.user_name if self.owner else ''
        ret['url'] = "%sjobs/%s" % (BEAKER_URL, self.id)
        return ret


BeakerGroupUser = \
    Table('beaker.user_group', BeakerBase.metadata,
          Column('group_id', Integer, ForeignKey("beaker.tg_group.group_id"), primary_key=True),
          Column('user_id', Integer, ForeignKey("beaker.tg_user.user_id"), primary_key=True),
          Column('is_owner', Boolean()),
          )


class BeakerUser(BeakerBase):
    __tablename__ = "beaker.tg_user"
    user_id = Column(Integer, primary_key=True)
    user_name = Column(String())
    email_address = Column(String())
    display_name = Column(String())
    disabled = Column(Boolean())
    removed = Column(DateTime())
    created = Column(DateTime())
    rootpw_changed = Column(DateTime())
    use_old_job_page = Column(Boolean())

    systems = relationship('BeakerSystem', back_populates='user', foreign_keys='BeakerSystem.user_id')
    recipes = relationship('BeakerRecipe', back_populates='user')
    groups = relationship('BeakerGroup', secondary=BeakerGroupUser, back_populates='users', lazy='dynamic')
    jobs = relationship('BeakerJob', back_populates='owner', lazy='dynamic')

    lab_controllers = relationship('BeakerLabController', back_populates='user')


class BeakerGroup(BeakerBase):
    __tablename__ = "beaker.tg_group"
    group_id = Column(Integer, primary_key=True)
    group_name = Column(String())
    display_name = Column(String())
    created = Column(DateTime())
    membership_type = Column(String())
    description = Column(String())

    users = relationship('BeakerUser', secondary=BeakerGroupUser, back_populates='groups', lazy='dynamic')
    jobs = relationship('BeakerJob', back_populates='group', lazy='dynamic')


BeakerSystemArchMap = \
    Table('beaker.system_arch_map', BeakerBase.metadata,
          Column('system_id', Integer, ForeignKey("beaker.system.id"), primary_key=True),
          Column('arch_id', Integer, ForeignKey("beaker.arch.id"), primary_key=True),
          )


BeakerSystemActivity = \
    Table('beaker.system_activity', BeakerBase.metadata,
          Column('system_id', Integer, ForeignKey("beaker.system.id"), primary_key=True),
          Column('id', Integer, ForeignKey("beaker.activity.id"), primary_key=True),
          )


class BeakerActivity(BeakerBase):
    __tablename__ = "beaker.activity"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    created = Column(DateTime())
    type = Column(String())
    field_name = Column(String())
    service = Column(String())
    action = Column(String())
    old_value = Column(String())
    new_value = Column(String())

    user = relationship('BeakerUser')
    systems = relationship('BeakerSystem', secondary=BeakerSystemActivity, back_populates='activities')

    def as_dict(self, detailed=False):
        ret = {}
        for c in self.__table__.columns:
            ret[c.name] = getattr(self, c.name)
        # ret['url'] = "%sview/%s" % (BEAKER_URL, self.fqdn) TODO
        return ret


class BeakerSystem(BeakerBase):
    __tablename__ = "beaker.system"
    id = Column(Integer, primary_key=True)
    fqdn = Column(String())
    serial = Column(String())
    date_added = Column(DateTime())
    date_modified = Column(DateTime())
    date_lastcheckin = Column(DateTime())
    location = Column(String())
    vendor = Column(String())
    model = Column(String())
    lender = Column(String())
    owner_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    user_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    type = Column(String())
    status = Column(String())
    private = Column(Boolean())
    # deleted = Column(Boolean()) Not longer present ?
    memory = Column(Integer())
    checksum = Column(String())
    lab_controller_id = Column(Integer())  # TODO: ForeignKey
    mac_address = Column(String())
    loan_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    reprovision_distro_tree_id = Column(Integer())  # TODO: ForeignKey
    release_action = Column(String())
    status_reason = Column(String())
    hypervisor_id = Column(Integer())  # TODO: ForeignKey
    kernel_type_id = Column(Integer())  # TODO: ForeignKey
    loan_comment = Column(String())
    custom_access_policy_id = Column(Integer(), ForeignKey("beaker.system_access_policy_rule.policy_id"))
    active_access_policy_id = Column(Integer(), ForeignKey("beaker.system_access_policy_rule.policy_id"))

    custom_access_policies = relationship('BeakerSystemAccessPolicyRule', back_populates='custom_systems',
                                          primaryjoin="BeakerSystem.custom_access_policy_id == BeakerSystemAccessPolicyRule.policy_id")
    active_access_policies = relationship('BeakerSystemAccessPolicyRule', back_populates='active_systems',
                                          primaryjoin="BeakerSystem.active_access_policy_id == BeakerSystemAccessPolicyRule.policy_id")

    activities = relationship('BeakerActivity', secondary=BeakerSystemActivity, back_populates='systems')
    user = relationship('BeakerUser', back_populates='systems', foreign_keys='BeakerSystem.user_id')
    arches = relationship('BeakerArch', secondary=BeakerSystemArchMap, back_populates='systems')

    def as_dict(self, detailed=False):
        ret = {}
        for c in self.__table__.columns:
            ret[c.name] = getattr(self, c.name)
        ret['url'] = "%sview/%s" % (BEAKER_URL, self.fqdn)
        return ret


class BeakerArch(BeakerBase):
    __tablename__ = "beaker.arch"
    id = Column(Integer, primary_key=True)
    arch = Column(String())

    systems = relationship('BeakerSystem', secondary=BeakerSystemArchMap, back_populates='arches')


class BeakerLabController(BeakerBase):
    __tablename__ = "beaker.lab_controller"
    id = Column(Integer, primary_key=True)
    fqdn = Column(String())
    disabled = Column(Boolean())
    removed = Column(DateTime())
    user_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))

    user = relationship('BeakerUser', back_populates='lab_controllers')


class BeakerSystemAccessPolicyRule(BeakerBase):
    __tablename__ = "beaker.system_access_policy_rule"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Integer())  # TODO: ?
    user_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    group_id = Column(Integer())
    permission = Column(String())

    custom_systems = relationship('BeakerSystem', back_populates='custom_access_policies',
                                  primaryjoin="BeakerSystem.custom_access_policy_id == BeakerSystemAccessPolicyRule.policy_id")
    active_systems = relationship('BeakerSystem', back_populates='active_access_policies',
                                  primaryjoin="BeakerSystem.active_access_policy_id == BeakerSystemAccessPolicyRule.policy_id")


class BeakerRecipe(BeakerBase):
    __tablename__ = "beaker.recipe"
    id = Column(Integer, primary_key=True)
    recipe_set_id = Column(Integer(), ForeignKey("beaker.recipe_set.id"))
    user_id = Column(Integer(), ForeignKey("beaker.tg_user.user_id"))
    distro_tree_id = Column(Integer())  # TODO Foreign
    result = Column(String())
    status = Column(String())
    start_time = Column(DateTime())
    finish_time = Column(DateTime())
    finish_time = Column(DateTime())
    _host_requires = Column(String())
    _distro_requires = Column(String())
    kickstart = Column(String())
    type = Column(String())
    ttasks = Column(Integer)
    ntasks = Column(Integer)
    ptasks = Column(Integer)
    wtasks = Column(Integer)
    ftasks = Column(Integer)
    ktasks = Column(Integer)
    whiteboard = Column(String())
    ks_meta = Column(String())
    kernel_options = Column(String())
    kernel_options_post = Column(String())
    role = Column(String())
    panic = Column(String())
    _partitions = Column(String())
    autopick_random = Column(Boolean())
    log_server = Column(String())
    virt_status = Column(String())

    user = relationship('BeakerUser', back_populates='recipes')
    recipe_set = relationship('BeakerRecipeSet', back_populates='recipes')


class BeakerRecipeSet(BeakerBase):
    __tablename__ = "beaker.recipe_set"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer(), ForeignKey("beaker.job.id"))
    priority = Column(String())
    queue_time = Column(DateTime())
    result = Column(String())
    status = Column(String())
    lab_controller_id = Column(Integer())
    ttasks = Column(Integer)
    ntasks = Column(Integer)
    ptasks = Column(Integer)
    wtasks = Column(Integer)
    ftasks = Column(Integer)
    ktasks = Column(Integer)
    waived = Column(Boolean())

    job = relationship('BeakerJob', back_populates='recipe_set')
    recipes = relationship('BeakerRecipe', back_populates='recipe_set')


class CachingQuery(Query):
    """
    Very simple query class with cache enabled.
    """
    def __init__(self, *args, **kw):
        self._caching = None
        self._cache_expire = 0
        Query.__init__(self, *args, **kw)

    def __iter__(self):
        """override __iter__ to pull results from dogpile
           if particular attributes have been configured.
        """
        if self._caching:
            ret = iter(get_or_create(
                self._cache_key,
                lambda: list(Query.__iter__(self)),
                expiration_time=self._cache_expire
            ))
            # Add cached object into session again.
            ret = self.merge_result(ret, load=False)
            return ret
        return Query.__iter__(self)

    def invalidate(self):
        raise NotImplementedError()

    @property
    def _cache_key(self):
        stmt = self.with_labels().statement
        compiled = stmt.compile()
        params = compiled.params

        return {'module': 'beaker', 'compiled': str(compiled), 'params': params}


class CustomQuery(CachingQuery):
    """
    Based on CachingQuery but return the exception we wanted on failure
    """
    def __iter__(self):
        return CachingQuery.__iter__(self)


class SetCache(MapperOption):
    propagate_to_loaders = False

    def __init__(self, caching: bool, expire: int):
        self.caching = caching
        self.expire = expire

    def process_query(self, query):
        query._caching = self.caching
        query._cache_expire = self.expire


class Beaker(object):
    """
    Stored common queries for Beaker.
    """
    cache_expiration_time = 1200
    beaker_url = BEAKER_URL

    def __init__(self):
        self.engine = create_engine("postgresql+teiid://%s:%s/public?sslmode=require&krbsrvname=postgres"
                                    % (TEIID_URL, TEIID_PORT))
        self.session = scoped_session(
            sessionmaker(
                query_cls=CustomQuery,
                autoflush=False,
                autocommit=False
            )
        )
        self.session.configure(bind=self.engine)

    def query(self, *args, **kwargs):
        expiration_time = self.cache_expiration_time
        if 'expiration_time' in kwargs:
            expiration_time = kwargs.pop('expiration_time')
        return self.session.query(*args, **kwargs).options(SetCache(True, expiration_time))

    def query_cachefree(self, *args, **kwargs):
        return self.session.query(*args, **kwargs).options(SetCache(False, 1))

    def get_loaned_systems(self, user_name, limit=100):
        ret = []
        systems = self.query(BeakerSystem)\
            .filter(BeakerSystem.user.has(BeakerUser.user_name == user_name))\
            .limit(limit)
        #   .join(BeakerSystemActivity, BeakerActivity)\ Query is very slow will timeout \

        for _s in systems:
            _system_json = _s.as_dict()
            _system_json['recent_activities'] = [_a.as_dict() for _a in _s.activities[0:20]]
            ret.append(_system_json)
        return ret

    def get_user_jobs(self, user_name, start_time=None):
        # TODO: limited, use paging
        jobs = self.query(BeakerJob)\
            .filter(BeakerJob.owner.has(BeakerUser.user_name == user_name)).limit(100).all()
        return [j.as_dict() for j in jobs]

    def get_user_group_running_jobs(self, user_name, start_time=None):
        # TODO: limited, use paging
        groups = self.query_cachefree(BeakerGroup.group_id)\
            .filter((BeakerGroup.users.any(BeakerUser.user_name == user_name))).subquery()
        jobs = self.query_cachefree(BeakerJob)\
            .filter(BeakerJob.group_id.in_(groups))\
            .filter(BeakerJob.status.in_(["Running", "Queued", "Installing"]))\
            .order_by(BeakerJob.id.desc()).limit(128).all()
        return [j.as_dict() for j in jobs]

    def get_user_group_jobs(self, user_name, start_time=None):
        # TODO: limited, use paging
        groups = self.query(BeakerGroup.group_id)\
            .filter((BeakerGroup.users.any(BeakerUser.user_name == user_name))).subquery()
        jobs = self.query(BeakerJob)\
            .filter(BeakerJob.group_id.in_(groups))\
            .order_by(BeakerJob.id.desc()).limit(128).all()
        return [j.as_dict() for j in jobs]

    def get_baremetal_free_systems(self):
        data = self.query(BeakerArch.arch, func.count(BeakerSystem.id), expiration_time=3600)\
            .select_from(BeakerSystem)\
            .filter((BeakerSystem.status == 'Automated') & # noqa
                    (BeakerSystem.loan_id == None) &
                    (BeakerSystem.hypervisor_id == None) &
                    (BeakerSystem.type == 'Machine') &
                    (BeakerSystem.user_id == None) &
                    (BeakerSystem.custom_access_policies.has(
                        (BeakerSystemAccessPolicyRule.group_id == None) &
                        (BeakerSystemAccessPolicyRule.permission == 'reserve')
                    )))\
            .join(BeakerSystemArchMap)\
            .join(BeakerArch)\
            .group_by(BeakerArch.arch)
        return [[arch, count] for arch, count in data.all()]

    def get_queue_length(self, time):
        """
        """
        ret = {}
        if time > (datetime.utcnow() - timedelta(hours=0.5)):
            return self.get_current_queue_length()

        time = func.PARSETIMESTAMP(time.strftime('%Y%m%d%H'), "yyyyMMddHH")

        for arch in self.query(BeakerArch, expiration_time=604800).all():
            data = self.query(func.count(BeakerRecipe.id), expiration_time=604800)\
                .select_from(BeakerRecipe)\
                .join(BeakerRecipeSet)\
                .filter((BeakerRecipeSet.queue_time < time) &
                        (BeakerRecipe.start_time > time) &
                        BeakerRecipe._distro_requires.op('similar to')('%s%s%s' % ('%%', arch.arch, '%%')) &
                        BeakerRecipe._host_requires.op('!~')('.*hypervisor value="(VM|Xen|HyperV).*'))
            ret[arch.arch] = data.first()[0]
        return ret

    def get_current_queue_length(self):
        """
        Get current queue lenght of different Arch,
        return a dict
        """
        ret = {}

        for arch in self.query(BeakerArch, expiration_time=604800).all():
            data = self.query(func.count(BeakerRecipe.id), expiration_time=300)\
                .select_from(BeakerRecipe)\
                .filter((BeakerRecipe.status == 'Queued') &
                        (BeakerRecipe.result == 'New') &
                        BeakerRecipe._distro_requires.op('similar to')('%s%s%s' % ('%%', arch.arch, '%%')) &
                        BeakerRecipe._host_requires.op('!~')('.*hypervisor value="(VM|Xen|HyperV).*'))\
                .first()

            ret[arch.arch] = data[0]

        return ret

    def get_average_queue_wait_time(self, days=30, granularity=None):
        if not granularity:
            granularity = "YD"  # Year, Day of Year
        date_group = func.formattimestamp(BeakerRecipeSet.queue_time, granularity)

        recipe_start = self.query(BeakerRecipe.start_time)\
            .filter(BeakerRecipe.recipe_set_id == BeakerRecipeSet.id)\
            .order_by(BeakerRecipe.start_time.asc())\
            .limit(1)

        data = self.query(date_group,
                          func.count(BeakerRecipeSet.id),
                          (func.sum(func.timestampdiff(text('sql_tsi_second'), BeakerRecipeSet.queue_time, recipe_start.label('start_time'))) /
                           func.count(BeakerRecipeSet.id))
                          )\
            .select_from(BeakerRecipeSet)\
            .filter((BeakerRecipeSet.status == 'Completed') &
                    (BeakerRecipeSet.queue_time >= func.PARSETIMESTAMP(
                        (datetime.today() - timedelta(days=days)).strftime('%Y%m%d'), "yyyyMMdd"))
                    )\
            .group_by(date_group)

        return data.all()
