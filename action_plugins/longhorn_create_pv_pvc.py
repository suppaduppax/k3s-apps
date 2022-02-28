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
            'namespace',
            'match_pvc_names'
        ]

        uri_module_args = self._task.args.copy()

        for arg in extra_args:
            if arg in uri_module_args:
                del uri_module_args[arg]

        hostname = self._task.args.get('hostname', None)
        match_pvc_names = self._task.args.get('match_pvc_names', None)

        volumes_return, volumes = self.get_volumes(
            hostname, uri_module_args, task_vars, tmp,
            match_pvc_names
        )

        if volumes_return.get('failed'):
            return volumes_return

        pvs = []
        pvcs = []

        for v in volumes['volumes']:
            if v['pv_status'].lower() == "bound" or v['pv_status'].lower() == "released":
                continue

            pv_return = self.create_pv(
                hostname, uri_module_args, task_vars, tmp,
                volume=v['volume'],
                pv_name=v['pv_name'],
            )

            if pv_return.get('failed'):
                return pv_return

            pvc_return = self.create_pvc(
                hostname, uri_module_args, task_vars, tmp,
                volume = v['volume'],
                pvc_name = v['pvc_name'],
                namespace = v['namespace']
            )

            if pvc_return.get('failed'):
                return pvc_return

            pvs.append({
                'volume': v['volume'],
                'pv_name': v['pv_name'],
                'pvc_name': v['pvc_name']
            })

            pvcs.append({
                'volume': v['volume'],
                'pv_name': v['pv_name'],
                'pvc_name': v['pvc_name'],
                'namespace': v['namespace']
            })

        return dict(pvs=pvs, pvcs=pvcs)

    def create_pv (self, hostname, uri_module_args, task_vars, tmp,
                   volume=None, pv_name=None):

        fs_type = self._task.args.get('fs_type', 'ext4')

        module_args = uri_module_args.copy()
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

        return pv_return

    def create_pvc (self, hostname, uri_module_args, task_vars, tmp,
                   volume=None, pvc_name=None, namespace='default'):

        module_args = uri_module_args.copy()
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

        return pvc_return

    def match_volumes(self, match, data):
        volumes = []

        for d in data:
            kubestatus = d['kubernetesStatus']
            pvc_name = kubestatus['pvcName']
            state = d['state']

            add_flag = False

            if not match:
                add_flag = True

            else:
                for m in match:
                    if re.search(m, pvc_name):
                        add_flag = True
                        break

            if add_flag:
                volumes.append({
                  'volume': d['id'],
                  'pv_name': kubestatus['pvName'],
                  'pv_status': kubestatus['pvStatus'],
                  'pvc_name': pvc_name,
                  'namespace': kubestatus['namespace'],
                  'state': state
                })

        return volumes

    def get_volumes(self, hostname, uri_module_args, task_vars, tmp, match_pvc_names):
        module_args = uri_module_args.copy()
        module_args['url'] = "https://" + self._task.args.get('hostname', None) + "/v1/volumes"
        module_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        del tmp

        volumes = []

        if module_return.get('failed'):
            return module_return, None

        volumes  = self.match_volumes(
            match_pvc_names,
            module_return['json']['data']
        )

        return module_return, dict(volumes=volumes)
