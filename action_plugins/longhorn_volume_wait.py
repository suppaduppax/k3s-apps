#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from datetime import datetime

from ansible.module_utils.json_utils import json
import re, time

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        extra_args = ['hostname', 'volume', 'state']
        module_args = self._task.args.copy()
        module_args['return_content'] = True
        module_args['url'] = "https://" + self._task.args.get('hostname', None) + "/v1/volumes"

        for arg in extra_args:
            if arg in module_args:
                del module_args[arg]

        state = self._task.args.get('state', 'detached')

        retry_count = 0
        retries = 20
        delay = 10

        while True:
            module_return = self._execute_module(module_name='uri',
                                                 module_args=module_args,
                                                 task_vars=task_vars, tmp=tmp)


            if module_return.get('failed'):
                return module_return

            if module_return['json']['data'][0]['state'] == state:
                break

            time.sleep(delay)

            retry_count = retry_count + 1
            if retry_count >= retries:
                break

        del tmp

        match = self._task.args.get('match', None)

        ret = dict()
        volumes = []
        ids = []
        workloads = []
        volumes_map = {}

        return module_return
