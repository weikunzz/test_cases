# pylint:disable=missing-docstring

import pytest
import mock
import unittest

from libvirt_ci.env.handler import HandlerSet
from libvirt_ci.env.handler import Trigger
from libvirt_ci.env.handler import Dependency
from libvirt_ci.env.handler import Parameter

def test_param_regist():
    external_params = {}
    params_to_regist = {
        "test_framework": 1,
        "pr": "",
    }
    handlers = HandlerSet(regist_cb=external_params.setdefault)
    for key, value in params_to_regist.items():
        @handlers.regist(key, value)
        def func():
            pass
    assert external_params == params_to_regist

def test_config():
    handlers = HandlerSet()
    @handlers.regist("test_framework", trigger=Trigger.on_change)
    def framework_handler(env, config, param):
        pass
    @handlers.regist("pr", trigger=Trigger.always)
    def pr_handler(env, config, param):
        return {"pr": {1: "timestamp"}}
    @handlers.regist("repo", trigger=Trigger.on_change)
    def repo_handler(env, config, param):
        yield {"repo": {"foo": "timestamp"}}
    config = {}
    param = {"test_framework": "avocado", "pr": "tp-libvirt 1", "repo": "foo"}
    config = handlers.perform_transfer(None, config, param)
    assert config == {
        "test_framework": "avocado",
        "pr": {1: "timestamp"},
        "repo": {"foo": "timestamp"}
    }

def test_trigger():
    handlers = HandlerSet()
    @handlers.regist("test_framework", trigger=Trigger.on_change)
    def framework_handler(env, config, param):
        pass
    @handlers.regist("pr", trigger=Trigger.always)
    def pr_handler(env, config, param):
        pass
    @handlers.regist("repo", trigger=Trigger.on_change)
    def repo_handler(env, config, param):
        pass
    steps = handlers.gen_steps(
        {"test_framework": None, "repo": ""},
        {"test_framework": "avocado-vt", "repo": ""},
        None
    )
    assert steps == [framework_handler, pr_handler]

def test_func_param():
    handlers = HandlerSet()
    old_param = {"k": "v"}
    new_param = {"new-k": "new-v"}
    test_target = {"target": "target"}

    def custom_trigger_parameters(old, new):
        assert old == old_param
        assert new == new_param
        return True

    def custom_trigger_parameters_with_target(old, new, target):
        assert old == old_param
        assert new == new_param
        assert target == test_target
        return True

    def custom_trigger_parameters_negetive(old, new):
        assert old == old_param
        assert new == new_param
        return False

    @handlers.regist(Parameter.all_parameters, trigger=custom_trigger_parameters)
    def framework_handler(env, config, param):
        pass

    @handlers.regist(Parameter.all_parameters_with_target,
                     trigger=custom_trigger_parameters_with_target)
    def pr_handler(env, config, param):
        pass

    @handlers.regist(Parameter.all_parameters,
                     trigger=custom_trigger_parameters_negetive)
    def repo_handler(env, config, param):
        pass

    steps = handlers.gen_steps(
        old_param,
        new_param,
        test_target
    )

    assert steps == [framework_handler, pr_handler]

def test_post_declearation():
    handlers = HandlerSet()
    actual_step = []

    @handlers.regist("pr", trigger=Trigger.always)
    @handlers.after("repo_handler")
    def pr_handler(env, config, param):
        env.append("pr_handler")

    @handlers.regist("repo", trigger=Trigger.always)
    @handlers.after("framework_handler")
    def repo_handler(env, config, param):
        env.append("repo_handler")

    @handlers.regist("test_framework", trigger=Trigger.always)
    def framework_handler(env, config, param):
        env.append("framework_handler")

    steps = handlers.gen_steps(
        {},
        {},
        None
    )
    handlers.perform_transfer(actual_step, {}, {})

    assert steps == [framework_handler, repo_handler, pr_handler]
    assert actual_step == ["framework_handler", "repo_handler", "pr_handler"]

def test_priority_after():
    handlers = HandlerSet()
    @handlers.regist("test_framework", trigger=Trigger.on_change)
    def framework_handler(env, config, param):
        pass

    @handlers.regist("repo", trigger=Trigger.on_change)
    @handlers.after(framework_handler)
    def repo_handler(env, config, param):
        pass

    @handlers.regist("pr", trigger=Trigger.on_change)
    @handlers.after(repo_handler)
    def pr_handler(env, config, param):
        pass

    steps = handlers.gen_steps(
        {"test_framework": None, "repo": None, "pr": None},
        {"test_framework": "avocado-vt", "repo": {}, "pr": "tp-libvirt 123"},
        None
    )

    assert steps == [framework_handler, repo_handler, pr_handler]

def test_require_priority():
    handlers = HandlerSet()
    @handlers.handler
    def repo_handler(env, config, param):
        pass

    @handlers.handler
    @handlers.after(repo_handler)
    def replace_handler(env, config, param):
        pass

    @handlers.handler
    @handlers.after(replace_handler)
    def pr_handler(env, config, param):
        pass

    @handlers.regist("env", trigger=Trigger.on_change)
    @handlers.requires(pr_handler)
    @handlers.requires(replace_handler)
    @handlers.requires(repo_handler)
    @handlers.before(repo_handler)
    def env_handler(env, config, param):
        pass

    steps = handlers.gen_steps(
        {"env": None},
        {"env": "libvirt"},
        None
    )

    assert steps == [env_handler, repo_handler, replace_handler, pr_handler]

def test_contain():
    handlers = HandlerSet()
    @handlers.regist("repo", trigger=Trigger.on_change)
    @handlers.handler
    def repo_handler(env, config, param):
        pass

    @handlers.regist("pr", trigger=Trigger.on_change)
    @handlers.handler
    @handlers.after(repo_handler)
    def pr_handler(env, config, param):
        pass

    @handlers.regist("env", trigger=Trigger.on_change)
    @handlers.contains(repo_handler)
    @handlers.contains(pr_handler)
    def env_handler(env, config, param):
        pass

    steps = handlers.gen_steps(
        {"env": None, "pr": None, "repo": None},
        {"env": "libvirt", "pr": "tp-libvirt 1", "repo": "foo"},
        None
    )

    assert steps == [env_handler]

def test_priority_insert():
    handlers = HandlerSet()
    @handlers.regist("repo", trigger=Trigger.on_change)
    @handlers.handler
    def repo_handler(env, config, param):
        pass

    @handlers.regist("replace", trigger=Trigger.on_change)
    @handlers.handler
    @handlers.after(repo_handler)
    def replace_handler(env, config, param):
        pass

    @handlers.regist("env", trigger=Trigger.on_change)
    @handlers.after(repo_handler)
    @handlers.before(replace_handler)
    def env_handler(env, config, param):
        pass

    steps = handlers.gen_steps(
        {"env": None, "replace":None, "repo": None},
        {"env": "libvirt", "replace": "foo", "repo": "foo"},
        None
    )

    assert steps == [repo_handler, env_handler, replace_handler]

def test_dyn_dependency():
    actual_step = []
    handlers = HandlerSet()

    @handlers.regist("env", trigger=Trigger.always)
    def env_handler(ran_step, config, param):
        ran_step.append("env")

    @handlers.regist("repo", trigger=Trigger.always)
    @handlers.after(env_handler)
    def repo_handler(ran_step, config, param):
        ran_step.append("repo")

    @handlers.regist("replace", trigger=Trigger.always)
    @handlers.after(repo_handler)
    def replace_handler(ran_step, config, param):
        ran_step.append("replace")

    @handlers.regist("pr", trigger=Trigger.always)
    @handlers.after(replace_handler)
    def pr_handler(ran_step, config, param):
        ran_step.append("pr")

    @handlers.regist("img", trigger=Trigger.always)
    @handlers.after(pr_handler)
    def img_handler(ran_step, config, param):
        ran_step.append("img")

    @handlers.regist("backup", trigger=Trigger.never)
    @handlers.after(img_handler)
    def backup_handler(ran_step, config, param):
        ran_step.append("backup")

    @handlers.regist("type", trigger=Trigger.always)
    @handlers.after(replace_handler)
    @handlers.before(pr_handler)
    def type_handler(ran_step, config, param):
        ran_step.append("type")
        yield Dependency.Require(env_handler) # Nothing will happend to require a executed handler
        yield Dependency.Require(repo_handler, rerun=True) #force repo_handler to rerun
        yield Dependency.Require(replace_handler, immediately=True, rerun=True) #force repo_handler to rerun ignore priority
        yield Dependency.Require(backup_handler)
        yield Dependency.Contain(pr_handler)

    steps = handlers.gen_steps({}, {}, None)
    handlers.perform_transfer(actual_step, {}, {})

    assert steps == [env_handler, repo_handler, replace_handler, type_handler, pr_handler, img_handler]
    assert actual_step == ["env", "repo", "replace", "type", "replace", "repo", "img", "backup"]
