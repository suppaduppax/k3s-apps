#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re

class ActionModule(ActionBase):
    def get_backup_target(self, hostname, uri_module_args, task_vars, tmp):
        module_args = uri_module_args.copy()
        module_args['url'] = "https://" + hostname + "/v1/backuptargets"
        backup_targets_return = self._execute_module(module_name='uri',
                                             module_args=module_args,
                                             task_vars=task_vars, tmp=tmp)

        if backup_targets_return.get('failed'):
            return backup_targets_return

        return backup_targets_return

    def restore_backup(self, hostname, uri_module_args, task_vars, tmp,
                       backup=None, volume=None):

        backup_target = self.get_backup_target(hostname, uri_module_args, task_vars, tmp)
        module_args = uri_module_args.copy()

        if backup_target.get('failed'):
            return backup_target

        backup_target = backup_target['json']['data'][0]['backupTargetURL']

        wait = self._task.args.get('wait', None)

        if not backup:
            backup = self._task.args.get('backup', None)

        if not volume:
            volume = self._task.args.get('volume', None)

        name = self._task.args.get('name', volume)
        replicas = self._task.args.get('replicas', 3)
        encrypted = self._task.args.get('encrypted', False)
        node_selector = self._task.args.get('node_selector', [])
        disk_selector = self._task.args.get('disk_selector', [])
        stale_replica_timeout = self._task.args.get('stale_replica_timeout', 20)

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

        return module_return

    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = [
            'hostname',

            # restore backup
            'wait',
            'backup',
            'volume',
            'name',
            'replicas',
            'encrypted',
            'node_selector',
            'disk_selector',
            'stale_replica_timeout',

            # list volumes/backups
            'match_pvc_names'
        ]

        uri_module_args = self._task.args.copy()

        for arg in extra_args:
            if arg in uri_module_args:
                del uri_module_args[arg]

        uri_module_args['return_content'] = True
        hostname = self._task.args.get('hostname', None)
        volume = self._task.args.get('volume', None)
        backup = self._task.args.get('backup', None)
        match_pvc_names = self._task.args.get('match_pvc_names', None)

        # force list
        if match_pvc_names and type(match_pvc_names) is not list:
            match_pvc_names = [match_pvc_names]


        if volume and match_pvc_names:
            return dict(failed=True, msg="Conflicting task args. Cannot have both volume and match_pvc_names.")

        if type(volume) is list and backup:
            return dict(failed=True, msg="Conflicting task args. Cannot have both volume and match_pvc_names.")

        if backup and match_pvc_names:
            return dict(failed=True, msg="Conflicting task args. Volumes cannot be list when backup is set.")

        volumes = self.get_volumes(hostname, uri_module_args, task_vars, tmp, match_pvc_names)
        if volumes.get('failed'):
            return volumes

        if match_pvc_names:
            # match volumes to pvc names using regex
            backups = self.get_backups(hostname, uri_module_args, task_vars, tmp, match_pvc_names)
#            return dict(backups=backups)

            if backups.get('failed'):
                return backups

            results = []
            restored_backups = []

            for backup in backups['backups']:
                backup_vol = backup['volume'];
                last_backup = backup['last_backup']
                if self.find_volume(backup_vol, volumes['volumes']):
                    continue

                restored_backups.append({
                    'volume': backup_vol,
                    'backup': last_backup,
                    'labels': backup['labels']
                })

                restore = self.restore_backup(
                    hostname, uri_module_args, task_vars, tmp,
                    volume=backup_vol,
                    backup=last_backup
                )

                if restore.get('failed'):
                    return restore

                results.append(restore)


            return dict(uri_results=results, restored_backups=restored_backups)

        else:
            # restore specific pvcs
            if type(volume) is list:
                results = []
                restored_backups = []

                for v in volume:
                    if self.find_volume(v, volumes['volumes']):
                        continue


                    restore = self.restore_backup(hostname,
                                                  uri_module_args,
                                                  task_vars,
                                                  tmp,
                                                  volume=v,
                                                  backup=self.get_last_backup(v)
                    )

                    if restore.get('failed'):
                        return restore

                    results.append(restore)

                    restored_backups.append({
                        'volume': backup_vol,
                        'backup': last_backup
                    })

                return dict(results=results, restored_backups=restored_backups)

            elif not self.find_volume(volume, volumes['volumes']):
                if not backup:
                    backup = self.get_last_backup(volume)

                module_result = restore_backup(hostname,
                                               uri_module_args,
                                               task_vars,
                                               tmp,
                                               volume=volume,
                                               backup=backup)

                if module_result.get('failed'):
                    return module_result

                return dict(uri_results=[module_result],
                            restored_backups=[{
                                'volume': volume,
                                'backup': backup
                            }])

        return dict()

    def find_volume(self, volume, volumes):
        for v in volumes:
            if v['volume'] == volume:
                return v

        return None

    def match_backups(self, match, data):
        backups = []

        for d in data:
            # find labels.KubernetesStatus
            kubestatus = d['labels']['KubernetesStatus']
            labels = d['labels']
            kubejson = json.loads(kubestatus)
            pvc_name = kubejson['pvcName']

            add_flag = False
            if not match:
                add_flag = True

            else:
                for m in match:
                    if re.search(m, pvc_name):
                        add_flag = True
                        break

            if add_flag:
                backups.append({
                  'volume': d['id'],
                  'last_backup': d['lastBackupName'],
                  'pvc_name': pvc_name,
                  'labels': labels
                })

        return backups

    # returns: {
    #   backups: [
    #     { volume: string, last_backup: string, pvc_Name: string },
    #     { ... }
    #   ],
    #   url: string,
    #   match_pvc_names: string
    # }
    def get_backups(self, hostname, uri_module_args, task_vars, tmp, match_pvc_names):
        uri_module_args['url'] = "https://" + hostname + "/v1/backupvolumes"
        module_return = self._execute_module(module_name='uri',
                                             module_args=uri_module_args,
                                             task_vars=task_vars, tmp=tmp)

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
          url=uri_module_args['url']
        )

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

    # returns: {
    #   volumes: [
    #     { volume: string,
    #       last_backup: string,
    #       pvc_name: string,
    #       pv_name: string,
    #       pv_status: string,
    #       namespace: string,
    #       state: string,
    #     },
    #     { ... }
    #   ],
    #   url: string,
    #   match_pvc_names: string
    # }
    def get_volumes(self, hostname, uri_module_args, task_vars, tmp, match_pvc_names):
        uri_module_args['url'] = "https://" + self._task.args.get('hostname', None) + "/v1/volumes"
        module_return = self._execute_module(module_name='uri',
                                             module_args=uri_module_args,
                                             task_vars=task_vars, tmp=tmp)

        volumes = []

        if module_return.get('failed'):
            return module_return

        volumes = self.match_volumes(
          match_pvc_names,
          module_return['json']['data']
        )

        return dict(
          volumes=volumes,
          match_pvc_names=match_pvc_names,
          url=uri_module_args['url']
        )
