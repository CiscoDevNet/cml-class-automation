#!/usr/bin/env python

from cml_auto import Config, DB, CML
import argparse
import os
import errno
import concurrent.futures
import time


# Taken from https://stackoverflow.com/a/600612/119527
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise  # noqa


def stop_lab(lab, config, db):
    print(f"Stopping lab {lab['title']} for student {lab['student']}")
    archive_dir = config.archives_base + "/" + lab["title"] + "-" + lab["student"]
    scml = CML(config.cml_server, lab["student"], lab["student_password"])
    cml = CML(config.cml_server, config.cml_username, config.cml_password)
    mkdir_p(archive_dir)
    scml.archive_lab(lab["cid"], archive_dir + "/lab.yaml", lab["device_password"])
    scml.remove_lab(lab["cid"])
    try:
        cml.remove_student(lab["student"])
    except Exception:
        # Student may have labs assigned still.
        pass
    db.stop_lab(lab["id"])


def main():
    parser = argparse.ArgumentParser(description="Stop a running lab")
    parser.add_argument("--config", "-c", help="Path to CML automation config file (default: ./config.json)", default="./config.json")

    args = parser.parse_args()

    config = Config(args.config)
    db = DB(config.db_file)

    while True:
        labs = db.get_expired_labs()
        if (labs and len(labs) == 0) or not labs:
            time.sleep(60)
            continue

        print(f"Stopping {len(labs)} labs")

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_labs = {executor.submit(stop_lab, lab, config, db): lab for lab in labs}
            for fl in concurrent.futures.as_completed(future_labs):
                try:
                    fl.result()
                except Exception as e:
                    print(e)

        print("DONE stopping labs; sleeping")


if __name__ == "__main__":
    main()
