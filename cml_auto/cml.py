import os
from virl2_client import ClientLibrary
from virl2_client.models.cl_pyats import ClPyats
from virl2_client.exceptions import LabNotFound
import logging
import time
import concurrent.futures
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

CONSOLE_BASE_PORT = 9000


class LabDef(object):
    def __init__(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Cached lab {filename} not found")

        with open(filename, "rb") as fd:
            lab = load(fd, Loader=Loader)

            self.__title = lab["lab"]["title"]

    @property
    def title(self):
        return self.__title


class CML(object):
    def __init__(self, host, username, password):
        logger = logging.getLogger("virl2_client.virl2_client")
        level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)

        # Remove VIRL2 envvars if they exist.  These would conflict with the virlutils config.
        os.environ.pop("VIRL2_USER", None)
        os.environ.pop("VIRL2_PASS", None)
        os.environ.pop("VIRL2_URL", None)

        self._host = host
        self._username = username
        self._password = password
        self._consoles = {}
        self._student = None
        self._student_password = None
        self._student_name = None

        self._client = ClientLibrary(host, username, password, raise_for_auth_failure=True, ssl_verify=False)
        logger.setLevel(level)

    def import_lab(self, filename, title):
        lab = self._client.import_lab_from_path(filename, title=title)
        return lab.id

    def configure_lab(self, lid, student, name, passwd, cfg_dir):
        self._student = student
        self._student_password = passwd
        self._student_name = name
        lab = self._client.join_existing_lab(lid)
        for node in lab.nodes():
            if node.label == "jump-host":
                continue
            nconfig = cfg_dir + "/" + node.label + ".cfg"
            if os.path.isfile(nconfig):
                with open(nconfig, "r") as fd:
                    node.config = fd.read()

    def _configure_breakout(self, lab):
        jump_host = lab.get_node_by_label("jump-host")
        config = f"""\
#cloud-config
password: cisco
chpasswd: {{ expire: False }}
hostname: jump-host
ssh_pwauth: True
users:
    - default
    - name: {self._student}
      gecos: {self._student_name}
      plain_text_passwd: '{self._student_password}'
      lock_passwd: false
      password: '{self._student_password}'
      shell: /bin/bash
write_files:
    - content: |
        console_start_port: {CONSOLE_BASE_PORT}
        controller: https://{self._host}
        username: {self._student}
        password: '{self._student_password}'
        populate_all: false
        verify_tls: false
        listen_address: '0.0.0.0'
      path: /etc/breakout/config.yaml
    - content: |
        {lab.id}:
            enabled: true
            lab_description: ""
            lab_title: {lab.title}
            nodes:
"""
        base_port = CONSOLE_BASE_PORT
        i = 0
        ignore_nodes = ["jump-host", "Mgmt-net"]
        for node in lab.nodes():
            if node.label in ignore_nodes or node.node_definition == "external_connector":
                continue

            self._consoles[node.label] = base_port + i
            config += f"""
                {node.id}:
                    devices:
                        - enabled: true
                          listen_port: {self._consoles[node.label]}
                          name: serial0
                          running: true
                          status: ""
                    label: {node.label}
"""
            i += 1
        config += f"""
      path: /etc/breakout/labs.yaml
    - content: |
        #!/bin/bash

        nohup /usr/bin/cml_breakout -config /etc/breakout/config.yaml -extralf -labs /etc/breakout/labs.yaml -listen 0.0.0.0 -noverify run &
      path: /etc/breakout/breakout.sh
      permissions: '0755'
runcmd:
    - [ ip, addr, add, 192.168.1.1/24, dev, ens3 ]
    - [ ip, link, set, up, dev, ens3 ]
    - [ curl, -L, --output, /usr/bin/cml_breakout, -k, 'https://{self._host}/breakout/breakout-linux-x86_amd64' ]
    - [ chmod, '0555', /usr/bin/cml_breakout ]
    - [ /etc/breakout/breakout.sh ]
"""
        jump_host.config = config

    def start_lab(self, lid):
        lab = self._client.join_existing_lab(lid)
        mnets = []
        for node in lab.nodes():
            if node.label != "jump-host":
                node.start()

            if node.node_definition == "external_connector":
                mnets.append(node)

        if len(mnets) > 0:
            ready = False
            while not ready:
                for n in mnets:
                    if not n.is_booted():
                        ready = False
                        break
                    ready = True
                time.sleep(1)

        self._configure_breakout(lab)
        jump_host = lab.get_node_by_label("jump-host")
        jump_host.start()
        while not jump_host.is_booted():
            time.sleep(1)

    def get_lab_address(self, lid):
        lab = self._client.join_existing_lab(lid)
        jump_host = lab.get_node_by_label("jump-host")
        mgmtip = None
        retries = 0
        while mgmtip is None:
            if retries > 10:
                break

            for i in jump_host.interfaces():
                if i.discovered_ipv4 and len(i.discovered_ipv4) > 0:
                    mgmtip = i.discovered_ipv4[0]
                    break

            retries += 1
            time.sleep(1)

        return mgmtip

    def get_lab_consoles(self):
        if len(self._consoles) == 0:
            raise Exception("ERROR: Consoles have not been generated yet")

        return self._consoles

    @staticmethod
    def _extract_configuration_task(node, pylab):
        if node.is_booted() and node.label != "jump-host":
            # We do this to ensure the extract is at the enable prompt.
            try:
                pylab.run_command(node.label, "show version")
            except Exception:
                pass
            node.extract_configuration()

    def archive_lab(self, lid, filename, node_password):
        try:
            lab = self._client.join_existing_lab(lid)
        except LabNotFound:
            return
        # The client library prints "API Error" warnings when a node doesn't support extraction.  Quiet these.
        logger = logging.getLogger("virl2_client.models.authentication")
        level = logger.getEffectiveLevel()
        logger.setLevel(logging.CRITICAL)
        pylab = ClPyats(lab)
        os.environ["PYATS_USERNAME"] = node_password
        os.environ["PYATS_PASSWORD"] = node_password
        os.environ["PYATS_AUTH_PASS"] = node_password
        pylab.sync_testbed(self._username, self._password)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_nodes = {executor.submit(CML._extract_configuration_task, node, pylab): node for node in lab.nodes()}
            for fn in concurrent.futures.as_completed(future_nodes):
                try:
                    fn.result()
                except Exception:
                    pass

        logger.setLevel(level)
        with open(filename, "w") as fd:
            fd.write(lab.download())

    def remove_lab(self, lid):
        try:
            lab = self._client.join_existing_lab(lid)
        except LabNotFound:
            return
        lab.stop(wait=True)
        lab.wipe(wait=True)
        lab.remove()

    def get_student(self, student):
        session = self._client.session
        try:
            r = session.get(f"{self._client._base_url}users/{student}")
            r.raise_for_status()
        except Exception as e:
            if r.status_code == 404:
                return None

            raise Exception(f"ERROR: Failed to query for student: {e}")
        else:
            return r.json()

    def add_student(self, student, name, password):
        session = self._client.session
        try:
            payload = {"password": password, "fullname": name}
            r = session.post(f"{self._client._base_url}users/{student}", json=payload)
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"ERROR: Failed to add new student: {e}")

    def remove_student(self, student):
        session = self._client.session
        try:
            r = session.delete(f"{self._client._base_url}users/{student}")
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"ERROR: Failed to remove student: {e}")
