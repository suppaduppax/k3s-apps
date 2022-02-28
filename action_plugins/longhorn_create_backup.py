#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

class ActionModule(ActionBase):
    def get_volumes(self, match, data):
        volumes = []

        for d in data:
            kubestatus = d['kubernetesStatus']
            backupstatus = d['backupStatus']

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
                  'state': state,
                  'snapshot': backupstatus['snapshot']
                })

        return volumes

    def get_snapshot(self, hostname, uri_module_args, task_vars, tmp, volume):
        module_args = uri_module_args.copy()
        module_args['url'] = "https://" + hostname + "/v1/volumes"
        volumes_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        snapshot = None
        data = volumes_return['json']['data']
        for d in data:
            if d['id'] == volume:
                if d['backupStatus'][0]['snapshot']:
                    snapshot = d['backupStatus']['snapshot']
                    break

        return volumes_return, snapshot

    def create_snapshot(self, hostname, uri_module_args, task_vars, tmp,
                       volume):

        module_args = uri_module_args.copy()
        module_args['method'] = "POST"
        module_args['body_format'] = "json"
        module_args['body'] = {}

        module_args['url'] = "https://" + hostname + "/v1/volumes/" + volume + "?action=snapshotCreate"

        module_return = self._execute_module(module_name='uri',
                                    module_args=module_args,
                                    task_vars=task_vars, tmp=tmp)

        return module_return

    def create_backup(self, hostname, uri_module_args, task_vars, tmp,
                       volume, snapshot, labels=None):

        module_args = uri_module_args.copy()

#        snapshot_return, snapshot = self.get_snapshot(hostname, uri_module_args, task_vars, tmp, volume)
#        if snapshot_return.get('failed') or not snapshot:
#            return backup_target

        module_args['method'] = "POST"
        module_args['body_format'] = "json"
        module_args['body'] = {
            "name": snapshot
        }

        if labels:
            module_args['body']['labels'] = {}
            for key in labels:
                module_args['body']['labels'][key] = labels[key]

        module_args['url'] = "https://" + hostname + "/v1/volumes/" + volume + "?action=snapshotBackup"
        module_return = self._execute_module(module_name='uri',
                                    module_args=module_args,
                                    task_vars=task_vars, tmp=tmp)

        return module_return

    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = [
            'hostname',
            'volume',
            'labels'
        ]

        uri_module_args = self._task.args.copy()

        for arg in extra_args:
            if arg in uri_module_args:
                del uri_module_args[arg]

        uri_module_args['return_content'] = True

        hostname = self._task.args.get('hostname', None)
        volume = self._task.args.get('volume', None)
        labels = self._task.args.get('labels')

        snapshot_return = self.create_snapshot(hostname, uri_module_args, task_vars, tmp, volume)

        if snapshot_return.get('failed'):
            return snapshot_return

        snapshot = snapshot_return['json']['id']
        backup_return = self.create_backup(hostname, uri_module_args, task_vars, tmp, volume, snapshot, labels)

        return backup_return
