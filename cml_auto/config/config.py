import json
import os
import datetime


class Config(object):
    def __init__(self, filename):
        with open(filename, "r") as fd:
            config = json.load(fd)

        self._host = config.get("cml_server")
        self._username = config.get("cml_username")
        self._password = config.get("cml_password")
        self._lab_dir = config.get("labs_directory")
        self._config_base = config.get("configs_base")
        self._archive_base = config.get("archives_base")
        self._smtp_server = config.get("smtp_server")
        self._db_file = config.get("db_file")
        self._email_from = config.get("email_from")
        self._smtp_tls = config.get("smtp_tls", False)
        self._smtp_port = config.get("smtp_port", 25)

        if not all([self._host, self._username, self._password]):
            raise Exception(
                "ERROR: Failed to determine CML access (not all of cml_server, cml_username, \
                and cml_password in config)"
            )

        if not self._lab_dir or not os.path.isdir(self._lab_dir):
            raise Exception("ERROR: labs_directory has either not been specified or is not a directory")

        if not self._config_base or not os.path.isdir(self._config_base):
            raise Exception("ERROR: configs_base has either not been specified or is not a directory")

        if not self._archive_base or not os.path.isdir(self._archive_base):
            raise Exception("ERROR: archives_base has either not been specified or is not a directory")

        if not self._smtp_server:
            raise Exception("ERROR: smtp_server has not been specified")

        if not self._db_file or not os.path.isfile(self._db_file):
            raise Exception("ERROR: db_file has either not been specified or is not a file")

        if not self._email_from:
            raise Exception("ERROR: email_from has not been specified")

        try:
            self._smtp_tls = bool(self._smtp_tls)
        except TypeError:
            raise Exception("ERROR: smtp_tls must either be true or false")

        try:
            self._smtp_port = int(self._smtp_port)
        except TypeError:
            raise Exception("ERROR: smtp_port must be an integer")

    @property
    def cml_server(self):
        return self._host

    @property
    def cml_username(self):
        return self._username

    @property
    def cml_password(self):
        return self._password

    @property
    def labs_directory(self):
        return self._lab_dir

    @property
    def configs_base(self):
        return self._config_base

    @property
    def archives_base(self):
        return self._archive_base

    @property
    def smtp_server(self):
        return self._smtp_server

    @property
    def db_file(self):
        return self._db_file

    @property
    def email_from(self):
        return self._email_from

    @property
    def smtp_tls(self):
        return self._smtp_tls

    @property
    def smtp_port(self):
        return self._smtp_port


class LabConfig(object):
    def __init__(self, filename):
        with open(filename, "r") as fd:
            config = json.load(fd)

        self._students = config.get("students")
        self._lab = config.get("labdef")
        self._start_time = config.get("start_time")
        self._duration = config.get("duration")
        self._id = config.get("id")
        self._device_password = config.get("device_password")

        if not self._students or not isinstance(self._students, list):
            raise Exception("ERROR: students is either not specified or is not a list")

        if not self._lab:
            raise Exception("ERROR: labdef has not been specified")

        if not self._start_time:
            raise Exception("ERROR: start_time has not been specified")
        else:
            try:
                self._start_time = datetime.datetime.strptime(self._start_time, "%Y-%m-%d %H:%M")
            except ValueError:
                raise Exception("ERROR: Invalid start_time; should be in the format YYYY-MM-DD HH:MM")

        if not self._duration or not isinstance(self._duration, int):
            raise Exception("ERROR: duration has not been specified or is not an integer")

        if not self._id:
            raise Exception("ERROR: id has not been specified")

        if not self._device_password:
            raise Exception("ERROR: device_password has not been specified")

    @property
    def students(self):
        return self._students

    @property
    def labdef(self):
        return self._lab

    @property
    def start_time(self):
        return int(self._start_time.strftime("%s"))

    @property
    def duration(self):
        return self._duration

    @property
    def schedule_id(self):
        return self._id

    @property
    def device_password(self):
        return self._device_password
