import logging

from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth.models import User

from scanning.models import Task, SubTask, Result, SastSchedule
from scanning.serializers import CreateTaskSerializer, UpdateReceiveTaskSerializer, UpdateSubTaskSerializer, \
    SastScheduleSerializer, ResultSerializer
from citool.utils import push_sqs_message, call_lambda_check_and_clone, call_lambda_check_and_scan, \
    get_result_data, remove_repo_folder
from scanning.utils import delete_downloaded_file, delete_cloudwatch_event, validate_language, \
    create_secure_string_for_password, create_cloudwatch_event, build_pattern, build_file_link, delete_secure_string, \
    valid_day_of_week, valid_datetime

from django.http.response import Http404
from django.core.exceptions import ValidationError, ObjectDoesNotExist


logger = logging.getLogger(__name__)


class TaskListCreate(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = CreateTaskSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset().order_by('timestamp').reverse()
        return super().get_queryset().filter(user=self.request.user).order_by('timestamp').reverse()

    def create(self, request, *args, **kwargs):
        """
        1. Create database record
        2. Push clone info to sqs
        3. Call lambda to check and clone
        """
        logger.info("========== Start creating a scanning task ==========")
        logger.info(f"Request user: {request.user.email}")
        data = request.data
        logger.debug(f"Request data: {data}")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        if "git_user" not in data:
            return Response({"git_user": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if "git_pass" not in data:
            return Response({"git_pass": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if 'language' in data:
            value = validate_language(data['language'])
            if value:
                return Response(data={"detail": f"Invalid language: {value}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"language": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        record = serializer.save()
        owner = data.get("owner")
        if owner:
            record.user = User.objects.get(id=owner)
        else:
            record.user = request.user
        record.save()
        logger.info(f"Created Task: {record.id}")

        sub_task_ids = ""
        languages = data['language'].split(",")
        languages.append("secret")
        for la in languages:
            if not la:
                continue
            st = SubTask(language=la, task_id=record.id)
            st.save()
            sub_task_ids += str(st.id) + ","

        sub_task_ids = sub_task_ids[:-1]
        try:
            exclude_path = data.get("exclude_path")
            if not exclude_path:
                exclude_path = "spec, test, tests, tmp"
            else:
                exclude_path += ",spec, test, tests, tmp"

            info = {
                "recordid": str(record.id),
                "taskids": sub_task_ids,
                "giturl": data["git_url"],
                "gituser": data["git_user"],
                "gitpassword": data["git_pass"],
                "repository": data["git_url"].strip('/').split('/')[-1].split('.git')[0],
                "gitbranch": data["branch"],
                "language": ','.join(languages),
                "type": "SAST",
                "excludepath": exclude_path,
            }
        except IndexError:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={"detail": f"Invalid git_url: {data['git_url']}"})

        response = push_sqs_message(info)
        if response.get("ResponseMetadata").get("HTTPStatusCode") != 200:
            logger.error(f"Unexpected error: {response}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.info("Sent message successfully")
        call_lambda_check_and_clone()
        headers = self.get_success_headers(serializer.data)
        logger.info("========== Finish creating a scanning task ==========")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskRetrieveDestroy(generics.RetrieveDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = UpdateReceiveTaskSerializer

    def get(self, request, *args, **kwargs):
        logger.info(f"========== Getting task info by: {request.user.email}")
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        logger.info(f"========== Deleting task {pk} by {request.user.email}")
        delete_downloaded_file(pk)
        return super().delete(request, *args, **kwargs)


class SubTaskUpdate(generics.UpdateAPIView):
    queryset = SubTask.objects.all()
    serializer_class = UpdateSubTaskSerializer

    def put(self, request, *args, **kwargs):
        logger.info("========== Start updating subtask ==========")
        logger.info(f"Request user: {request.user.email}")
        pk = self.kwargs.get('pk')
        logger.info(f"Updating status for sub task: {pk}")
        try:
            subtask = SubTask.objects.get(pk=pk)
        except ObjectDoesNotExist:
            logger.error("==== Subtask has been deleted!")
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            data = request.data
            logger.info(f"Request data: {data}")
            if data['status'] != "COMPLETED":
                logger.info("========== Updated subtask successfully ==========")
                return self.update(request, *args, **kwargs)

            git_url = subtask.task.git_url
            data = get_result_data(str(subtask.task.id), git_url, subtask.language, 'SAST')
            logger.info(f"Data from result file: {data}")
            for item in data.get("vulnerabilities", []):
                location = item.get('location')
                file_path = location.get('file')
                start_line = location.get('start_line')
                link = build_file_link(subtask.task.git_engine, git_url, subtask.task.branch, file_path, start_line)
                r = Result(
                    description=item.get("message"),
                    severity=item.get("severity"),
                    file_path=file_path,
                    start_line=start_line,
                    link=link,
                    subtask=subtask,
                )
                r.save()
            logger.info("========== Updated subtask successfully ==========")
            call_lambda_check_and_scan()
            return self.update(request, *args, **kwargs)
        except Http404:
            logger.error("Given SubTask ID not found")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response(data=e, status=status.HTTP_400_BAD_REQUEST)
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
            remove_repo_folder(task_id)

        task = Task.objects.get(pk=task_id)
        task.status = status
        logger.info(f"Task status: {status}")
        task.save()
        logger.info("========== Finish updating task status ===========")


class SastScheduleListCreate(generics.ListCreateAPIView):
    queryset = SastSchedule.objects.all()
    serializer_class = SastScheduleSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset().order_by('timestamp').reverse()
        return super().get_queryset().filter(user=self.request.user).order_by('timestamp').reverse()

    def create(self, request, *args, **kwargs):
        """
        1. Create database record
        2. Create secure string for password
        3. Create cloudwatch event
        """

        logger.info("========== Start creating SAST schedule ==========")
        logger.info(f"Request user: {request.user.email}")
        data = request.data
        logger.debug(f"Request data: {data}")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        if "git_user" not in data:
            return Response({"git_user": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if "git_pass" not in data:
            return Response({"git_pass": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if 'language' in data:
            value = validate_language(data['language'])
            if value:
                return Response(data={"detail": f"Invalid language: {value}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"language": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        data_day_of_week = data.get("day_of_week", None)
        data_date = data.get("date", None)
        data_time = data["time"]

        if data_day_of_week:
            if not valid_day_of_week(data_day_of_week):
                return Response({"day_of_week": ["Invalid day_of_week"]}, status=status.HTTP_400_BAD_REQUEST)

        if data_date:
            if not valid_datetime(data_date, data_time):
                return Response({"date": ["Invalid date time"]}, status=status.HTTP_400_BAD_REQUEST)

        if not data_date and not data_day_of_week:
            return Response({"details": ["Must select value date or day_of_week"]}, status=status.HTTP_400_BAD_REQUEST)

        record = serializer.save()
        record.user = request.user
        record.save()

        create_secure_string_for_password(str(record.id), data["git_pass"])

        info = {
            "schedule_id": str(record.id),   # used to naming secure string and delete schedule resource
            "git_engine": data["git_engine"],
            "git_url": data["git_url"],
            "git_user": data["git_user"],
            "branch": data["branch"],
            "language": data['language'],
            "exclude_path": data.get("exclude_path", ""),
            "owner": str(request.user.id),
            "run_type": data['run_type'],
        }

        pattern = build_pattern(data['time'], data_day_of_week, data_date)
        create_cloudwatch_event(info, pattern)

        headers = self.get_success_headers(serializer.data)
        logger.info("========== Finish creating SAST schedule ==========")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class SastScheduleDelete(generics.DestroyAPIView):
    queryset = SastSchedule.objects.all()
    serializer_class = SastScheduleSerializer

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        logger.info(f"========== Deleting schedule {pk} by {request.user.email}")
        delete_secure_string(pk)
        delete_cloudwatch_event(pk)
        return super().delete(request, *args, **kwargs)


class ResultUpdate(generics.UpdateAPIView):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
