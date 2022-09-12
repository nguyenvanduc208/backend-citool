import os
import logging
from datetime import datetime
from subprocess import run, PIPE

from django.conf import settings
from jmeter.config import FRONTEND_SERVER, JMETER, JMX_FILE, ZAP, ZAP_HOME, RESULT_FILE

logger = logging.getLogger(__name__)


def perform_task(record):
    try:
        output_dir = "{}{}/".format(settings.MEDIA_ROOT, record.id)
        output_link = "{}{}/".format(settings.MEDIA_URL, record.id)
        result_dir = "{}{}".format(output_dir, RESULT_FILE)
        link = "{}{}index.html".format(FRONTEND_SERVER, output_link)
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        if record.run_type == "SCRIPT":
            command = _script_cmd(record, result_dir, output_dir)
        elif record.run_type == "CONFIG":
            command = _config_cmd(record, result_dir, output_dir)
        else:
            now = datetime.now()
            timestamp = now.timestamp()
            command = _zap_cmd(timestamp, record)
            output = run(command, shell=True, stdout=PIPE, stderr=PIPE)
            if output.returncode != 0:
                return record, link, output, output_dir, output_link
            
            command = _zap_export(now, record, output_dir, timestamp)
            link = "{}{}{}.xhtml".format(FRONTEND_SERVER, output_link, timestamp)

        logger.info("============== Start running Jmeter task ============== ")
        logger.info(f"Command: {command}")
        output = run(command, shell=True, stdout=PIPE, stderr=PIPE)
        logger.info(f"Output: {output}")
        logger.info("============== Jmeter task has done ============== ")
        return record, link, output, output_dir, output_link
    except Exception as e:
        output_dir = "{}{}/".format(settings.MEDIA_ROOT, record.id)
        error_dir = "{}error.txt".format(output_dir)
        with open(error_dir, "w") as f:
            f.write(str(e))

        output_link = "{}{}/".format(settings.MEDIA_URL, record.id)
        error_link = "{}error.txt".format(output_link)
        record.status = 2
        record.report = "{}{}".format(FRONTEND_SERVER, error_link)
        record.save()
        raise

def on_result(result):
    record, link, output, output_dir, output_link = result

    if output.returncode == 0:
        record.status = 1
        record.report = link
    else:
        stdout = "{}stdout.txt".format(output_dir)
        stdout_link = "{}stdout.txt".format(output_link)
        with open(stdout, "wb") as f:
            f.write(output.stderr)
            f.write(output.stdout)
        record.status = 2
        record.report = "{}{}".format(FRONTEND_SERVER, stdout_link)
    
    record.save()

def on_error(e):
    print(e)

def _script_cmd(record, result_dir, output_dir):
    file_dir = "{}{}".format(settings.MEDIA_ROOT, record.file)
    command = "{} -n -t {} -f -l {} -e -o {}".format(JMETER, file_dir, result_dir, output_dir)
    return command

def _config_cmd(record, result_dir, output_dir):
    command = "{} -n -t {} -Jdomain={} -Jport={} -Jprotocol={} -Jramp_time={} -Jnum_threads={} -Jloops={} -f -l {} -e -o {}".format(
        JMETER, JMX_FILE,
        record.domain, record.port, record.protocol, record.ramp_time, record.num_threads, record.loops,
        result_dir, output_dir)
    return command

def _zap_cmd(timestamp, record):
    if "http" not in record.domain:
        record.domain = "http://{}".format(record.domain)
    command = "{} -dir {} -quickurl {} -newsession {} -cmd;".format(ZAP, ZAP_HOME, record.domain, timestamp)
    return command

def _zap_export(now, record, output_dir, timestamp):
    file_dir = "{}{}.xhtml".format(output_dir, timestamp)
    report_name="Vulnerability Report - " + record.domain
    prepared_by = "trananhkma"
    prepared_for = "CITool"
    scan_date = now.strftime("%x")
    report_date = now.strftime("%x")
    scan_version = "N/A"
    report_version = "N/A"
    report_description = "Check basic security"
    command = '{} -dir {} -export_report "{}" -source_info "{};{};{};{};{};{};{};{}" -alert_severity "t;t;f;t" -alert_details "t;t;t;t;t;t;f;f;f;f" -session "{}.session" -cmd'.format(
        ZAP, ZAP_HOME, file_dir, report_name, prepared_by, prepared_for, scan_date, report_date, scan_version, report_version, report_description, timestamp
    )

    return command