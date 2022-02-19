#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = [
            'hostname',
            'wait',
            'backup',
            'volume',
            'name',
            'replicas',
            'encrypted',
            'node_selector',
            'disk_selector',
            'stale_replica_timeout'
        ]

        module_args = self._task.args.copy()
        module_args['return_content'] = True

        hostname = self._task.args.get('hostname', None)

        for arg in extra_args:
            if arg in module_args:
                del module_args[arg]

        module_args['url'] = "https://" + hostname + "/v1/backuptargets"

        # get backuptarget
        backup_targets_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        wait = self._task.args.get('wait', None)
        backup = self._task.args.get('backup', None)
        volume = self._task.args.get('volume', None)
        name = self._task.args.get('name', volume)
        replicas = self._task.args.get('replicas', 3)
        encrypted = self._task.args.get('encrypted', False)
        node_selector = self._task.args.get('node_selector', [])
        disk_selector = self._task.args.get('disk_selector', [])
        stale_replica_timeout = self._task.args.get('stale_replica_timeout', 20)

        backup_target = backup_targets_return['json']['data'][0]['backupTargetURL']

#        module_args['headers'] = {}
#        module_args['headers']['Content-Type'] = "application/json"
        module_args['method'] = "POST"
        module_args['body_format'] = "json"
        module_args['body'] = {
            "name": name,
            "numberOfReplicas": replicas,
            "encrypted": encrypted,
            "nodeSelector": node_selector,
            "diskSelector": disk_selector,
            "fromBackup": backup_target + "?backup=" + backup + "&volume=" + volume,
            "staleReplicaTimeout": stale_replica_timeout
        }

        module_args['url'] = "https://" + hostname + "/v1/volumes"

        module_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        del tmp

        return module_return
