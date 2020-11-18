from sqlalchemy import create_engine, MetaData, Integer, Column, String, Enum, Text, Table
import datetime

LAB_TABLE = "lab"
STUDENT_TABLE = "student"

TABLES = {
    LAB_TABLE: [
        Column("id", Integer(), primary_key=True, autoincrement=True, nullable=False),
        Column("cid", String(6), unique=True, index=True),
        Column("title", String(255), nullable=False),
        Column("student", String(16), nullable=True),
        Column("source", String(255), nullable=False, index=True),
        Column("status", Enum("SCHEDULED", "RUNNING", "HISTORIC", "SCHEDULING"), server_default="SCHEDULED", nullable=False, index=True),
        Column("start_time", Integer(), index=True, nullable=False),
        Column("end_time", Integer(), index=True),
        Column("duration", Integer(), server_default="2", nullable=False),
        Column("student_password", String(8)),
        Column("schedule_id", String(36), index=True),
        Column("device_password", Text()),
    ],
    STUDENT_TABLE: [
        Column("uname", String(16), primary_key=True, nullable=False),
        Column("email", String(255), nullable=False),
        Column("name", Text(), nullable=False),
    ],
}


class DB(object):
    _db_engine = None

    def __init__(self, dbname, username="" """Not used""", password="" """Not used"""):
        self._db_engine = create_engine(f"sqlite:///{dbname}")
        metadata = MetaData(self._db_engine)
        missing_table = False
        for table, tdef in TABLES.items():
            if not self._db_engine.dialect.has_table(self._db_engine, table):
                missing_table = True
                Table(table, metadata, *tdef)

        if missing_table:
            metadata.create_all()

    def get_scheduled_labs(self, starting=None):
        sql = f"SELECT * from {LAB_TABLE} WHERE status='SCHEDULED'"
        if starting:
            sql += f" AND start_time <= '{starting}'"

        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to get scheduled labs: {e}")
            else:
                return [row for row in result]

    def get_lab(self, lid):
        sql = f"SELECT * from lab WHERE id='{lid}'"
        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to get lab: {e}")
            else:
                return result.first()

    def get_expired_labs(self):
        now = datetime.datetime.now().strftime("%s")
        sql = f"SELECT * from {LAB_TABLE} WHERE status='RUNNING' AND end_time <= '{now}'"

        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to get expired labs: {e}")
            else:
                return [row for row in result]

    def get_labs_with_schedule_id(self, schedule_id):
        sql = f"SELECT * from {LAB_TABLE} WHERE schedule_id='{schedule_id}'"

        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to get labs with schedule ID: {e}")
            else:
                return [row for row in result]

    def get_student(self, student):
        sql = f"SELECT * FROM {STUDENT_TABLE} where uname='{student}'"
        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to query for student: {e}")
            else:
                return result.first()

    def remove_lab(self, lid, allow_running=False):
        sql = f"SELECT status FROM {LAB_TABLE} where id='{lid}'"
        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to get current lab status: {e}")
            else:
                row = result.first()
                if not row:
                    raise Exception(f"ERROR: Failed to find lab {lid}")

                if row["status"] == "RUNNING" and not allow_running:
                    raise Exception("ERROR: Lab is currently running")

                sql = f"DELETE FROM {LAB_TABLE} WHERE id='{lid}'"
                try:
                    conn.execute(sql)
                except Exception as e:
                    raise Exception(f"ERROR: Failed to delete lab: {e}")

    def schedule_lab(self, schedule_id, title, source, student, device_password, start_time, duration):
        sobj = self.get_student(student)
        if not sobj:
            raise Exception(f"ERROR: Failed to find student {student} in the DB")

        with self._db_engine.connect() as conn:
            sql = f"INSERT INTO lab (schedule_id, student, device_password, title, source, start_time, duration) VALUES ('{schedule_id}', \
                '{student}', '{device_password}', '{title}', '{source}', '{start_time}', '{duration}')"
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to schedule lab: {e}")
            else:
                return result.lastrowid

    def scheduling(self, lid):
        self._update_lab(lid, {"status": "SCHEDULING"})

    def unschedule(self, lid):
        self._update_lab(lid, {"status": "SCHEDULED"})

    def _update_lab(self, lid, props):
        sql = f"UPDATE {LAB_TABLE} SET "
        for p, v in props.items():
            if v is None:
                sql += f"{p}=NULL, "
            else:
                sql += f"{p}='{v}', "

        sql = sql.rstrip(", ") + f" WHERE id='{lid}'"
        with self._db_engine.connect() as conn:
            try:
                conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to update lab: {e}")

    def run_lab(self, lid, cid, pw):
        end_time = None
        sql = f"SELECT start_time, duration FROM {LAB_TABLE} WHERE id='{lid}'"
        with self._db_engine.connect() as conn:
            try:
                result = conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to query lab start time: {e}")
            else:
                row = result.first()
                now = int(datetime.datetime.now().strftime("%s"))
                end_time = now + (row["duration"] * 60 * 60)

        self._update_lab(lid, {"status": "RUNNING", "cid": cid, "end_time": end_time, "student_password": pw})
        return self.get_lab(lid)

    def stop_lab(self, lid):
        self._update_lab(lid, {"status": "HISTORIC", "cid": None})
        return self.get_lab(lid)

    def add_student(self, username, name, email):
        sql = f"INSERT INTO {STUDENT_TABLE} VALUES ('{username}', '{email}', '{name}')"
        with self._db_engine.connect() as conn:
            try:
                conn.execute(sql)
            except Exception as e:
                raise Exception(f"ERROR: Failed to add new student: {e}")
            else:
                return self.get_student(username)
