#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

# pv
# curl 'https://longhorn.k3s.home/v1/volumes/pvc-6119873d-6102-4521-9497-a05f97a8b421?action=pvCreate' \
# --data-raw '{"pvName":"pvc-6119873d-6102-4521-9497-a05f97a8b421","fsType":"ext4"}' \

# pvc
# curl 'https://longhorn.k3s.home/v1/volumes/pvc-6119873d-6102-4521-9497-a05f97a8b421?action=pvcCreate' \
#  --data-raw '{"pvcName":"data-harbor-trivy-0","namespace":"awx-ee"}' \

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = [
            'hostname',
            'volume',
            'pv_name',
            'pvc_name',
            'fs_type',
            'namespace'
        ]

        module_args = self._task.args.copy()

        for arg in extra_args:
            if arg in module_args:
                del module_args[arg]

        hostname = self._task.args.get('hostname', None)
        volume = self._task.args.get('volume')
        pv_name = self._task.args.get('pv_name')
        pvc_name = self._task.args.get('pvc_name')
        fs_type = self._task.args.get('fs_type')
        namespace = self._task.args.get('namespace')

        module_args['return_content'] = True
        module_args['url'] = "https://" + hostname + "/v1/volumes/" + volume + "?action=pvCreate"
        module_args['method'] = "POST"
        module_args['body_format'] = "json"
        module_args['body'] = {
            'pvName': pv_name,
            'fsType': fs_type
        }

        pv_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        module_args['return_content'] = True
        module_args['url'] = "https://" + hostname + "/v1/volumes/" + volume + "?action=pvcCreate"
        module_args['method'] = "POST"
        module_args['body_format'] = "json"
        module_args['body'] = {
            'pvcName': pvc_name,
            'namespace': namespace
        }

        pvc_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        del tmp

        return dict(pv=pv_return, pvc=pvc_return)
