import os
import shutil
import json
import boto3
import logging
from botocore.exceptions import ClientError
from core.serializers import UserSerializer


REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
QUEUE = 'anhtt_clone_tasks.fifo'
MSG_GROUP_ID = "CloneTasks"
LAMBDA_CHECK_AND_CLONE = "arn:aws:lambda:ap-northeast-1:012881927014:function:anhtt_call_ssm"
LAMBDA_CHECK_AND_SCAN = "arn:aws:lambda:ap-northeast-1:012881927014:function:anhtt_check_and_scan"
LAMBDA_LISTEN_SSM = "arn:aws:lambda:ap-northeast-1:012881927014:function:anhtt_listen_ssm"

EFS_FOLDER = "/code/efs"
SAST_REPORT = 'gl-sast-report.json'
SECRET_REPORT = 'gl-secret-detection-report.json'
DAST_REPORT = "gl-dast-report.json"
CLOC_REPORT = "cloc_summary.json"
CLOC_COMPARISON_REPORT = "cloc_comparison_summary.json"
S3_RESULT = {
    'cloc': "cloc_detail.csv",
    'dast': "report.html"
}
BUCKET = "citool-scan-result"

logger = logging.getLogger(__name__)


def jwt_response_handler(token, user=None, request=None):
    return {
        'token': token,
        'user': UserSerializer(user, context={'request': request}).data
    }


def push_sqs_message(info):
    logger.info("Sending message")
    sqs = boto3.resource(
        'sqs',
        region_name=REGION,
    )
    queue = sqs.get_queue_by_name(QueueName=QUEUE)
    response = queue.send_message(
        MessageBody=json.dumps(info),
        MessageGroupId=MSG_GROUP_ID
    )
    return response


def call_lambda(function_name, payload=None):
    client = boto3.client(
        'lambda',
        region_name=REGION,
    )
    logger.info(f"Calling lambda: {function_name}")
    if payload:
        payload = json.dumps(payload)
    else:
        payload = '{}'
    return client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=payload
    )


def call_lambda_listen_ssm(payload):
    call_lambda(LAMBDA_LISTEN_SSM, payload)


def call_lambda_check_and_clone():
    call_lambda(LAMBDA_CHECK_AND_CLONE)


def call_lambda_check_and_scan():
    call_lambda(LAMBDA_CHECK_AND_SCAN)


def get_result_data(task_id, git_url=None, language=None, scan_type=None):
    logger.info("Getting data from result file")
    repo = git_url.split('/')[-1].split('.git')[0]
    if scan_type == "SAST" and language != 'secret':
        filename = SAST_REPORT
    elif language == 'secret':
        filename = SECRET_REPORT
    elif scan_type == "CLOC":
        cloc_report = '/'.join([EFS_FOLDER, task_id, repo, CLOC_COMPARISON_REPORT])
        if os.path.exists(cloc_report):
            filename = CLOC_COMPARISON_REPORT
        else:
            filename = CLOC_REPORT
    else:
        filename = DAST_REPORT

    if filename != DAST_REPORT:
        filepath = '/'.join([EFS_FOLDER, task_id, repo, filename])
    else:
        filepath = '/'.join([EFS_FOLDER, task_id, 'wrk', filename])
    try:
        with open(filepath) as f:
            data = json.load(f)
        # os.remove(filepath)
        return data
    except FileNotFoundError:
        logger.error(f"Result file not found: {filepath}")
        return {}


def remove_repo_folder(task_id):
    folder_path = '/'.join([EFS_FOLDER, task_id])
    try:
        shutil.rmtree(folder_path)
        logger.info("Deleted repo folder on server")
    except Exception as e:
        logger.info(f"Error when delete folder: {e}")


def remove_repo_task(efs_folder, task_id):
    if not efs_folder:
        efs_folder = EFS_FOLDER
    folder_path = '/'.join([efs_folder, task_id])
    try:
        shutil.rmtree(folder_path)
        logger.info("Deleted repo folder on server")
    except Exception as e:
        logger.info(f"Error when delete folder: {e}")


def upload_result_to_s3(folder, record_id, git_url=None):
    logger.info("Uploading file to S3")
    result = S3_RESULT.get(folder, 'ERROR')
    object_name = f"{folder}/{record_id}/{result}"
    if git_url:
        repo = git_url.split('/')[-1].split('.git')[0]
        filepath = '/'.join([EFS_FOLDER, record_id, repo, result])
    else:
        filepath = '/'.join([EFS_FOLDER, record_id, 'wrk', result])
    s3_client = boto3.client('s3', region_name=REGION)
    try:
        s3_client.upload_file(filepath, BUCKET, object_name)
        logger.info("Upload file successfully")
    except ClientError as e:
        logging.error(e)
        return False, e
    except FileNotFoundError as e:
        logging.error("No result file!")
        return False, e
    return True, object_name


def download_from_s3(object_name):
    logger.info("Downloading file from S3")
    s3_client = boto3.client('s3', region_name=REGION)
    return s3_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': BUCKET, 'Key': object_name},
        ExpiresIn=3600
    )


def delete_s3_object(object_name):
    s3_client = boto3.client('s3', region_name=REGION)
    s3_client.delete_object(
        Bucket=BUCKET,
        Key=object_name,
    )

def get_logs_cloudwatch(log_group, log_stream, next_token=""):
    log_client = boto3.client('logs', region_name=REGION)
    return log_client.get_log_events(
        logGroupName=log_group,
        logStreamName=log_stream,
        startFromHead=False
    )
