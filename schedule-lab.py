#!/usr/bin/env python

from cml_auto import Config, DB, LabDef, LabConfig
import argparse
import time


def main():
    parser = argparse.ArgumentParser(description="Schedule a lab to run in the future")
    parser.add_argument("--config", "-c", help="Path to CML automation config file (default: ./config.json)", default="./config.json")
    parser.add_argument("--lab-config", "-l", help="Path to the lab config file", required=True)

    args = parser.parse_args()
    now = int(time.time())

    config = Config(args.config)
    lab_config = LabConfig(args.lab_config)
    labdef = LabDef(config.labs_directory + "/" + lab_config.labdef + ".yaml")
    db = DB(config.db_file)

    if lab_config.start_time < now:
        print("ERROR: Lab cannot be scheduled in the past")
        exit(1)

    labs = db.get_labs_with_schedule_id(lab_config.schedule_id)
    if len(labs) > 0:
        print("ERROR: This schedule has already been done.")
        exit(1)

    title = labdef.title.replace(" ", "_") + "-" + str(lab_config.start_time)

    for student in lab_config.students:
        try:
            db.schedule_lab(
                lab_config.schedule_id,
                title,
                lab_config.labdef,
                student,
                lab_config.device_password,
                lab_config.start_time,
                lab_config.duration,
            )
        except Exception as e:
            print(e)
            continue


if __name__ == "__main__":
    main()
