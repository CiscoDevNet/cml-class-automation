#!/usr/bin/env python

from cml_auto import Config, DB, CML, LabDef
import datetime
import argparse
import os
import smtplib
import ssl
import string
import random
import concurrent.futures
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

CREATED_USERS = {}


def email_student(student, pw, lab, lab_file, mgmtip, consoles, config):
    labdef = LabDef(lab_file)

    message = MIMEMultipart()
    message["Subject"] = "Your lab is ready"
    message["From"] = config.email_from
    message["To"] = f"{student['name']} <{student['email']}>"
    text = f"""\
Hello {student['name']},

Your lab "{labdef.title}" is now ready for use.  It will remain active
until {time.ctime(lab['end_time'])}.

Lab Jump Host: ssh://{student['uname']}@{mgmtip}
Password: {pw}

Consoles:

"""
    for node, port in consoles.items():
        text += f"  {node} : telnet://{mgmtip}:{port}\r\n"

    text += f"""

Topology:
Node Management IP telnet password: {lab["device_password"]}

"""

    message.attach(MIMEText(text, "plain"))
    lab_img = config.labs_directory + "/" + lab["source"] + ".png"
    if os.path.isfile(lab_img):
        with open(lab_img, "rb") as fd:
            img = MIMEImage(fd.read())
            img.add_header("Content-ID", "<topology.png>")
            message.attach(img)

    with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
        if config.smtp_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
        server.sendmail(message["From"], message["To"], message.as_string())


def get_student_password():
    chrs = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(chrs) for i in range(8))


def deploy_lab(lab, config, cml, db):
    global CREATED_USERS

    print(f"Deploying lab {lab['title']} for student {lab['student']}...")
    db.scheduling(lab["id"])

    try:
        lfile = config.labs_directory + "/" + lab["source"] + ".yaml"
        if not os.path.isfile(lfile):
            raise FileNotFoundError(f"ERROR: Failed to find lab definition file {lfile}")

        cfg_dir = config.configs_base + "/" + lab["source"]
        if not os.path.isdir(cfg_dir):
            raise Exception(f"ERROR: {cfg_dir} is not a directory")

        student = cml.get_student(lab["student"])
        if lab["student"] not in CREATED_USERS and student:
            cml.remove_student(lab["student"])

        sobj = db.get_student(lab["student"])
        if lab["student"] not in CREATED_USERS:
            pw = get_student_password()
            cml.add_student(lab["student"], sobj["name"], pw)
            CREATED_USERS[lab["student"]] = pw
        else:
            pw = CREATED_USERS[lab["student"]]

        scml = CML(config.cml_server, lab["student"], pw)
        lid = scml.import_lab(lfile, title=lab["title"])

        scml.configure_lab(lid, sobj["uname"], sobj["name"], pw, cfg_dir)
        scml.start_lab(lid)
        slab = db.run_lab(lab["id"], lid, pw)
        email_student(sobj, pw, slab, lfile, scml.get_lab_address(lid), scml.get_lab_consoles(), config)
    except Exception:
        db.unschedule(lab["id"])
        raise


def main():
    parser = argparse.ArgumentParser(description="Start a scheduled lab")
    parser.add_argument("--config", "-c", help="Path to CML automation config file (default: ./config.json)", default="./config.json")

    args = parser.parse_args()
    config = Config(args.config)
    db = DB(config.db_file)

    while True:

        now = datetime.datetime.strptime(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "%Y-%m-%d %H:%M").strftime("%s")
        labs = db.get_scheduled_labs(starting=now)
        if (labs and len(labs) == 0) or not labs:
            time.sleep(60)
            continue

        print(f"Deploying {len(labs)} new labs for {now}")

        cml = CML(config.cml_server, config.cml_username, config.cml_password)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_labs = {executor.submit(deploy_lab, lab, config, cml, db): lab for lab in labs}
            for fl in concurrent.futures.as_completed(future_labs):
                try:
                    fl.result()
                except Exception as e:
                    print(e)

        print(f"DONE deploying labs for {now}")


if __name__ == "__main__":
    main()
