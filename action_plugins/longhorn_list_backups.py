#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

class ActionModule(ActionBase):
    def match_backups(self, match, data):
        backups = []

        for d in data:
            # find labels.KubernetesStatus
            kubestatus = d['labels']['KubernetesStatus']
            kubejson = json.loads(kubestatus)
            pvc_name = kubejson['pvcName']

            add_flag = False
            if not match:
                add_flag = True

            else:
                for m in match:
                    if not re.search(match, pvc_name):
                        continue

                    add_flag = True
                    break

            if add_flag:
                backups.append({
                  'volume': d['id'],
                  'last_backup': d['lastBackupName'],
                  'pvc_name': pvc_name
                })

        return backups

    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = ['hostname', 'match_pvc_names']
        module_args = self._task.args.copy()
        module_args['return_content'] = True
        module_args['url'] = "https://" + self._task.args.get('hostname', None) + "/v1/backupvolumes"

        for arg in extra_args:
            if arg in module_args:
                del module_args[arg]

        module_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        del tmp

        match_pvc_names = self._task.args.get('match_pvc_names', None)
        if match_pvc_names and type(match_pvc_names) is not list:
            match_pvc_names = [match_pvc_names]

        backups = []

        if module_return.get('failed'):
            return module_return

        backups = self.match_backups(
          match_pvc_names,
          module_return['json']['data']
        )

        return dict(
          backups=backups,
          match_pvc_names=match_pvc_names,
          url=module_args['url']
        )
