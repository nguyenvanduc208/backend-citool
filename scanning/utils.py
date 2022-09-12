import json
import shutil
import boto3
import logging
from datetime import datetime
from django.conf import settings
from scanning.models import LANGUAGE_CHOICES
from citool.utils import REGION


LAMBDA_CREATE_TASK = "arn:aws:lambda:ap-northeast-1:012881927014:function:anhtt_create_task"

logger = logging.getLogger(__name__)
ENGINE_LINK_MAPPING = {
    'github': '{link}/blob/{branch}/{file_path}#L{start_line}',
    'gitlab': '{link}/blob/{branch}/{file_path}#L{start_line}',
    'bitbucket': '{link}/src/{branch}/{file_path}#lines-{start_line}',
}


def delete_downloaded_file(folder_name):
    target = settings.MEDIA_ROOT + folder_name
    try:
        shutil.rmtree(target)
        logger.info("Deleted report files on server")
    except FileNotFoundError:
        logger.info(f"Folder not found: {target}")


def validate_language(value):
    valid_values = [key for key, _ in LANGUAGE_CHOICES]
    if not isinstance(value, str) or not value.islower():
        return value

    languages = value.split(',')
    invalid_la = []
    for la in languages:
        if la not in valid_values:
            invalid_la.append(la)
    return invalid_la


def create_secure_string_for_password(name, value):
    logger.info("Creating secure string")
    client = boto3.client('ssm', region_name=REGION)

    response = client.put_parameter(
        Name=f'/CustomResource/{name}',
        Description='For schedule scan',
        Value=value,
        Type='SecureString',
        Overwrite=True,
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        logger.info("Creating secure string successfully")
    else:
        logger.error(f"Error when creating secure string: {response}")


def create_cloudwatch_event(info, pattern):
    logger.info("Creating cloudwatch rule")
    client = boto3.client('events', region_name=REGION)
    response = client.put_rule(
        Name=info["schedule_id"],
        ScheduleExpression=pattern,
        Description='citool schedule scan',
    )
    if not response.get("RuleArn"):
        logger.error(f"Create cloudwatch rule failed: {response}")
        return

    client.put_targets(
        Rule=info["schedule_id"],
        Targets=[
            {
                'Id': str(int(datetime.now().timestamp())),
                'Arn': LAMBDA_CREATE_TASK,
                'Input': json.dumps(info),
            },
        ]
    )


def build_pattern(time, day_of_week=None, date=None):
    data_time = time.split(':')
    if not date:
        if not day_of_week:
            day_of_week = "*"

        # cron(Minutes Hours Day-of-month Month Day-of-week Year)
        return f"cron({data_time[1]} {data_time[0]} ? * {day_of_week} *)"

        # 2021-06-24
    data_date = date.split('-')
    return f"cron({data_time[1]} {data_time[0]} {data_date[2]} {data_date[1]} ? {data_date[0]})"


def build_file_link(git_engine, git_url, branch, file_path, start_line):
    link = git_url.split('.git')[0]
    link_format = ENGINE_LINK_MAPPING.get(git_engine)
    return link_format.format(link=link, branch=branch, file_path=file_path, start_line=start_line)


def delete_secure_string(name):
    logger.info("Deleting secure string")
    client = boto3.client('ssm', region_name=REGION)
    try:
        client.delete_parameter(
            Name=f'/CustomResource/{name}'
        )
        logger.info("Deleted parameter")
    except client.exceptions.ParameterNotFound:
        logger.info("Secure string not found!")


def delete_cloudwatch_event(name):
    client = boto3.client('events', region_name=REGION)
    try:
        logger.info("Removing target rule")
        res = client.list_targets_by_rule(Rule=name)
        target_id = res['Targets'][0]["Id"]
        client.remove_targets(
            Rule=name,
            Ids=[target_id]
        )

        logger.info("Deleting cloudwatch rule")
        client.delete_rule(
            Name=name
        )
        logger.info("Deleted rule")
    except client.exceptions.ResourceNotFoundException:
        logger.info("Rule not found!")


def valid_day_of_week(day_of_week):
    if day_of_week == '*':
        return True
    valid_data = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    days = day_of_week.split(",")
    for d in days:
        if d.strip() not in valid_data:
            return False
    return True


def valid_datetime(data_date, data_time):
    today = datetime.utcnow()
    date_format = "%Y-%m-%d"
    current_date = today.strftime(date_format)
    if data_date < current_date:
        return False

    time_format = "%H:%M"
    current_time = today.strftime(time_format)
    if data_time <= current_time:
        return False

    return True
