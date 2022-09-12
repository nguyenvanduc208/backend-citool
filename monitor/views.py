import logging
import boto3
import datetime
import requests
import ast
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timedelta
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response

from monitor.models import Task
from monitor.serializers import CreateTaskSerializer

from django.core.exceptions import ValidationError, ObjectDoesNotExist

ssm_param_name = "/citools/monitoring/url"
dynamodb_table = "citool-monitoring-url"
logger = logging.getLogger(__name__)
REGION = "ap-northeast-1"


def get_task(pk):
    try:
        return Task.objects.get(pk=pk)
    except ObjectDoesNotExist:
        logger.error("==== Task not found!")


def get_parameter():
    """
    1. Get SSM Parameter
    :return:
    """
    client = boto3.client('ssm', region_name=REGION)
    response = client.get_parameter(
        Name=ssm_param_name
    )
    parameter = response.get("Parameter")
    value = parameter.get("Value")
    return value


def delete_parameter(pk):
    client = boto3.client('ssm', region_name=REGION)
    values = get_parameter()
    convert = ast.literal_eval(values)
    remove_item = tuple(item for item in convert if item['ID'] != pk)
    new_values = str(remove_item).strip("()")
    response = client.put_parameter(
        Name=ssm_param_name,
        Value=str(new_values),
        Type='StringList',
        Overwrite=True
    )


class TaskListCreate(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = CreateTaskSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset().order_by('timestamp').reverse()
        return super().get_queryset().filter(user=self.request.user).order_by('timestamp').reverse()

    def create(self, request, *args, **kwargs):
        """
        1. Put URL and ID to SSM Parameter
        :param request:
        :return:
        """
        client = boto3.client('ssm', region_name=REGION)
        values = get_parameter()
        data = request.data
        logger.debug(f"Request data: {data}")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        info = {
            "URL": record.url,
            "ID": str(record.id)
        }
        try:
            validate_url = requests.get(record.url).status_code
        except Exception:
            return Response(data={"detail": f"Invalid URL: {record.url}"}, status=status.HTTP_400_BAD_REQUEST)
        new_values = values + "," + str(info)
        logging.info(" ==== Put New Url To SSM Param ==== ")
        if str(info) not in values:
            response = client.put_parameter(
                Name=ssm_param_name,
                Value=str(new_values),
                Type='StringList',
                Overwrite=True
            )
        else:
            logging.info("==== URL Existing ====")
        logger.info("Successfully create SSM parameter for monitoring")
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskRetrieveDestroyStatus(generics.RetrieveDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = CreateTaskSerializer

    def get(self, request, *args, **kwargs):
        """
        1. Query Dynamo DB with conditions are Key and Attribute
        2. Return results success, failed and total status
        3. Delete URL is monitoring by ID and results stored in database
        :param request:
        :return:
        """
        pk = self.kwargs.get('pk')
        task = get_task(pk)
        if not task:
            return Response(data={task}, status=status.HTTP_404_NOT_FOUND)
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
        table = dynamodb.Table(dynamodb_table)
        last_day = (datetime.now() - timedelta(hours=24)).strftime("%d-%m-%YT%H:%M:%SZ")
        today = (datetime.now()).strftime("%d-%m-%YT%H:%M:%SZ")
        data_test = Task.objects.filter(id=pk)
        serializer = CreateTaskSerializer(data_test, many=True)
        try:
            success_status = table.query(
                FilterExpression=Attr('status').eq(200),
                KeyConditionExpression=Key('id').eq(pk) & Key('start_time').between(last_day, today),
                Select='COUNT'
            )
            all_status = table.query(
                KeyConditionExpression=Key('id').eq(pk) & Key('start_time').between(last_day, today),
                Select='COUNT'
            )
            failed_status = (all_status.get('Count')) - (success_status.get('Count'))
            results = {
                "success_percent": str(round((success_status.get('Count') / all_status.get('Count')) * 100, 2)) + "%",
                "failed_count": failed_status,
                "all_status_count": all_status.get('Count'),
                "success_count": success_status.get('Count'),
                "url": serializer.data[0]['url'],
                "timestamp": serializer.data[0]['timestamp'],
                "sitename": serializer.data[0]['sitename'],
            }
        except ClientError as e:
            return Response(data={e.response['Error']['Message']}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(data=results, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)
        logger.info(f"========== Deleting task {pk} by {request.user.email}")
        delete_parameter(pk)
        return super().delete(request, *args, **kwargs)


class GetResponseTime(generics.ListAPIView):

    def get(self, request, *args, **kwargs):
        """
        1. Query Dynamo DB with conditions are Key and Attribute
        2. Return response time in 24 hours
        :param request:
        :return:
        """
        pk = self.kwargs.get('pk')
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
        table = dynamodb.Table(dynamodb_table)
        last_day = (datetime.now() - timedelta(hours=24)).strftime("%d-%m-%YT%H:%M:%SZ")
        today = (datetime.now()).strftime("%d-%m-%YT%H:%M:%SZ")
        try:
            response = table.query(
                KeyConditionExpression=Key('id').eq(pk) & Key('start_time').between(last_day, today),
            )
            results = []
            for item in response['Items']:
                result = {
                    "start_time": item.get("start_time"),
                    "response_time": item.get("response_time"),
                    "status_code": int(item.get("status"))
                }
                results.append(result)
        except ClientError as e:
            return Response(data={e.response['Error']['Message']}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(data=results, status=status.HTTP_200_OK)
