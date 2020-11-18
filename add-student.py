#!/usr/bin/env python

from cml_auto import Config, DB
import argparse


def main():
    parser = argparse.ArgumentParser(description="Add a student to the database")
    parser.add_argument("--config", "-c", help="Path to CML automation config file (default: ./config.json)", default="./config.json")
    parser.add_argument("--username", "-u", help="Username of the student to add (this must be unique in the databse)", required=True)
    parser.add_argument("--name", "-n", help="Full name of the student to add", required=True)
    parser.add_argument("--email", "-e", help="Email of the student (this does not have to be unique per student)", required=True)

    args = parser.parse_args()

    config = Config(args.config)
    db = DB(config.db_file)

    try:
        db.add_student(args.username, args.name, args.email)
    except Exception as e:
        print(e)
        exit(1)
    else:
        print(f"Successfully added student {args.username}")


if __name__ == "__main__":
    main()
