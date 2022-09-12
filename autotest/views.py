import os
import shutil
import logging
from datetime import datetime
from os import listdir
from os.path import isfile, join, isdir

from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.shortcuts import render
from rest_framework import generics, serializers, status

from rest_framework.response import Response
from autotest.serializers import AutoTestSerializer
from autotest.models import Task, SubTask
from autotest.serializers import SubtaskSerializer, SubtaskResultSerializer
from autotest.serializers import AutotestLogTaskSerializer, SubtaskLogSerializer
from citool.utils import call_lambda_check_and_clone, push_sqs_message, call_lambda_check_and_scan, \
    get_logs_cloudwatch, remove_repo_task
from autotest.utils import validate_browser

logger = logging.getLogger(__name__)

# Create your views here.
class AutotestAPIView(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = AutoTestSerializer

    def get(self, request, *args, **kwargs):
        if self.request.user.is_superuser:
            tasks = super().get_queryset().order_by('timestamp').reverse()

        else:
            tasks = super().get_queryset().filter(user=self.request.user).order_by('timestamp').reverse()

        res_serializer = []
        for task in tasks:
            # Get all subtasks of task
            sub_tasks = task.subtasks.all()

            sub_tasks_results = []
            for sub_task in sub_tasks:
                # Generate report link of subtask
                result_link = f'/api/media/{task.id}/{sub_task.id}/index.html'
                sub_task_result_serializer = SubtaskResultSerializer(sub_task, context={
                    "link": result_link
                })
                sub_tasks_results.append(sub_task_result_serializer.data)

            task_serializer = AutoTestSerializer(task, context={
                "sub_tasks": sub_tasks_results
            })

            res_serializer.append(task_serializer.data)

        return Response(data=res_serializer, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """
            1. Create database record
            2. Push clone info to sqs
            3. Call lambda to check and clone
        """

        logger.info("========== Start creating an automation task ==========")
        logger.info(f"Request user: {request.user.email}")
        request_data = request.data
        logger.debug(f"Request data: {request.data}")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        value = validate_browser(request_data['browser'])
        if value:
            return Response(data={"detail": f"Invalid browser: {value}"}, status=status.HTTP_400_BAD_REQUEST)

        record = serializer.save()
        owner = validated_data.get("owner")
        if owner:
            record.user = User.objects.get(id=owner)
        else:
            record.user = request.user
        record.save()
        
        logger.info(f"Created Task: {record.id}")
        sub_task_ids = ""
        browsers = request_data['browser'].split(",")
        for b in browsers:
            if not b:
                continue
            st = SubTask(browser=b, task_id=record.id)
            st.save()
            sub_task_ids += str(st.id) + ","
        sub_task_ids = sub_task_ids[:-1]

        info = {
            "recordid": str(record.id),
            "taskids": sub_task_ids,
            "giturl": request_data["git_url"],
            "gituser": request_data["git_user"],
            "gitpassword": request_data["git_pass"],
            "repository": request_data["git_url"].strip('/').split('/')[-1].split('.git')[0],
            "gitbranch": request_data["branch"],
            "browsers": ','.join(browsers),
            "type": "SELENIUM",
        }

        response = push_sqs_message(info)
        if response.get("ResponseMetadata").get("HTTPStatusCode") != 200:
            logger.error(f"Unexpected error: {response}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.info("Sent message successfully")
        call_lambda_check_and_clone()
        headers = self.get_success_headers(serializer.data)
        logger.info("========== Finish creating a scanning task ==========")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AutotestDeleteAPIVIew(generics.RetrieveDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = AutoTestSerializer

    def get(self, request, *args, **kwargs):
        logger.info(f"========== Getting task info by: {request.user.email}")
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        logger.info(f"========== Deleting task {pk} by {request.user.email}")
        remove_repo_task(efs_folder='efs/results', task_id=pk)
        return super().delete(request, *args, **kwargs)


class AutotestSubtaskAPIView(generics.UpdateAPIView):
    queryset = SubTask.objects.all()
    serializer_class = SubtaskSerializer

    def put(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        try:
            subtask = SubTask.objects.get(pk=pk)
        except SubTask.DoesNotExist:
            logger.info("========== PK not exist ==========")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info("========== Updated subtask starting ==========")
            data = request.data
            logger.info(f"Request data: {data}")
            if data['status'] == "COMPLETED":
                DIR_PROCESS = f'efs/results/{subtask.task.id}/{subtask.id}'
                repo_name = subtask.task.git_url.split('/')[-1].replace('.git', '')
                base_dir = f'efs/{subtask.task.id}/{repo_name}/target/site/serenity'
                self.clone_media(DIR_PROCESS, base_dir)
            
            logger.info("========== Updated subtask successfully ==========")
            call_lambda_check_and_scan()
            return self.update(request, *args, **kwargs)
        finally:
            self.update_task_status(str(subtask.task.id))

    @staticmethod
    def update_task_status(task_id):
        logger.info("========== Start updating task status ==========")
        logger.info(f"Task ID: {task_id}")
        subtasks = SubTask.objects.filter(task__id=task_id)
        sub_status = [st.status for st in subtasks]
        logger.info(f"SubTask status: {sub_status}")
        status = ""
        if "ERROR" in sub_status:
            status = "ERROR"
        elif "RUNNING" in sub_status:
            status = "RUNNING"
        elif "PENDING" in sub_status:
            return
        else:
            status = "COMPLETED"
            remove_repo_task(efs_folder='efs', task_id=task_id)

        task = Task.objects.get(pk=task_id)
        task.status = status
        logger.info(f"Task status: {status}")
        task.save()
        logger.info("========== Finish updating task status ===========")

    def clone_media(self, prefix, base_dir):
        logger.info(f"Start copy from {base_dir} to {prefix}")
        destination_dir = os.path.join(prefix)
        if not os.path.isdir(destination_dir):
            os.makedirs(destination_dir)
        folder_copy = [d for d in listdir(base_dir) if isdir(join(base_dir, d))]
        file_copy = [f for f in listdir(base_dir) if isfile(join(base_dir, f))]

        for file in file_copy:
            if os.path.isfile(os.path.join(destination_dir, file)):
                continue
            shutil.copy(os.path.join(base_dir, file), os.path.join(destination_dir, file))

        for folder in folder_copy:
            if os.path.isdir(os.path.join(destination_dir, folder)):
                continue
            shutil.copytree(os.path.join(base_dir, folder), os.path.join(destination_dir, folder))
        logger.info(f"End copy from {base_dir} to {prefix}")

class AutotestTaskLogRetrieve(generics.ListAPIView):
    queryset = Task.objects.all()
    serializer_class = AutotestLogTaskSerializer

    def get(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        logger.info(f"========== Getting subtask logs of task's {pk} by: {request.user.email}")
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        sub_tasks = task.subtasks.all()

        sub_task_logs = []
        for sub_task in sub_tasks:
            log_info = get_logs_cloudwatch(sub_task.log_group, sub_task.log_stream)
            events = log_info.get("events")
            log_messages = []
            for event in events:
                timestamp = event.get('timestamp') / 1000
                timestamp = datetime.fromtimestamp(timestamp)

                message = event.get("message")
                log_messages.append({"message": f'{timestamp}\t{message}'}) 

            sub_task_log_serializer = SubtaskLogSerializer(sub_task, context={
                    "results": log_messages
                })
            sub_task_logs.append(sub_task_log_serializer.data)

        res_serializer = AutotestLogTaskSerializer(task, context={
            "sub_tasks": sub_task_logs
        })

        return Response(data=res_serializer.data, status=status.HTTP_200_OK)
