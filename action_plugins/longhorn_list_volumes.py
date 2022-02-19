#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

class ActionModule(ActionBase):
    def match_volumes(self, match, data):
        volumes = []
        ids = []

        for d in data:
            kubestatus = d['kubernetesStatus']
            pvc_name = kubestatus['pvcName']
            state = d['state']

            if not match or re.search(match, pvc_name):
                volumes.append({
                  'volume': d['id'],
                  'pv_name': kubestatus['pvName'],
                  'pv_status': kubestatus['pvStatus'],
                  'pvc_name': pvc_name,
                  'namespace': kubestatus['namespace'],
                  'state': state
                })
                ids.append(d['id'])

        return volumes, ids

    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = ['hostname', 'match_pvc_name']
        module_args = self._task.args.copy()
        module_args['return_content'] = True
        module_args['url'] = "https://" + self._task.args.get('hostname', None) + "/v1/volumes"

        for arg in extra_args:
            if arg in module_args:
                del module_args[arg]

        module_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        del tmp

#        return dict(blah=module_return['json']['data'][0])

        match_pvc_name = self._task.args.get('match_pvc_name', None)

        ret = dict()
        volumes = []
        ids = []
        volumes_map = {}

        if module_return.get('failed'):
            return module_return

        volumes, ids = self.match_volumes(
          match_pvc_name,
          module_return['json']['data']
        )

        return dict(
          volumes=volumes,
          #volumes_map=volumes_map,
          ids=ids,
          match_pvc_name=match_pvc_name,
          #workloads=workloads,
          url=module_args['url']
        )
