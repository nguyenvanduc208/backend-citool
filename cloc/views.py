import logging
import os
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from cloc.models import Task, Result
from cloc.serializers import CreateTaskSerializer, UpdateDestroyTaskSerializer, ResultSerializer
from citool.utils import get_result_data, push_sqs_message, call_lambda_check_and_clone, call_lambda_check_and_scan, \
    remove_repo_folder, upload_result_to_s3, download_from_s3, delete_s3_object

from django.http.response import Http404
from django.core.exceptions import ValidationError, ObjectDoesNotExist


logger = logging.getLogger(__name__)


class TaskListCreate(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = CreateTaskSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset().order_by('created_at').reverse()
        return super().get_queryset().filter(user=self.request.user).order_by('created_at').reverse()

    def create(self, request, *args, **kwargs):
        """
        1. Create database record
        2. Push clone info to sqs
        3. Call lambda to check and clone
        """
        logger.info("========== Start creating a cloc task ==========")
        logger.info(f"Request user: {request.user.email}")
        data = request.data
        logger.debug(f"Request data: {data}")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        if "git_user" not in data:
            return Response({"git_user": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if "git_pass" not in data:
            return Response({"git_pass": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        record = serializer.save()
        record.user = request.user
        record.save()
        logger.info(f"Created Task: {record.id}")
        include_lang = data.get("include_lang", "*").strip()
        exclude_dir = data.get("exclude_dir", "*").strip()

        try:
            info = {
                "recordid": str(record.id),
                "giturl": data["git_url"],
                "gituser": data["git_user"],
                "gitpassword": data["git_pass"],
                "repository": data["git_url"].strip('/').split('/')[-1].split('.git')[0],
                "gitbranch": data["branch"],
                "includelang": include_lang,
                "excludedir": exclude_dir,
                "type": "CLOC",
                "commitid1": data.get("commit_id1", "None"),
                "commitid2": data.get("commit_id2", "None"),
                "comparedbranch1": data.get("compared_branch1", "None"),
                "comparedbranch2": data.get("compared_branch2", "None"),
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
        logger.info("========== Finish creating a cloc task ==========")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskRetrieveDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = UpdateDestroyTaskSerializer

    def put(self, request, *args, **kwargs):
        logger.info("========== Start updating cloc task ==========")
        pk = self.kwargs.get('pk')
        logger.info(f"Updating status for task: {pk}")
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            data = request.data
            logger.info(f"Request data: {data}")
            if data['status'] != "COMPLETED":
                logger.info("========== Updated task successfully ==========")
                return self.update(request, *args, **kwargs)

            git_url = task.git_url
            repo = git_url.split('/')[-1].split('.git')[0]
            efs_folder = "/code/efs"
            cloc_comparison_report_file = "cloc_comparison_summary.json"
            cloc_comparison_report_file_path = '/'.join([efs_folder, str(task.id), repo, cloc_comparison_report_file])
            data = get_result_data(str(task.id), git_url, '', 'CLOC')
            logger.info(f"Data from result file: {data}")

            if not data:
                return self.update(request, *args, **kwargs)
            data.pop("header")
            if os.path.exists(cloc_comparison_report_file_path):
                logger.info(f"====Start validate comparison report=====")
                logger.info(f"file path: {cloc_comparison_report_file_path}")
                for key, values in data.items():
                    logger.info(f"====Data key: {key}")
                    for language, details in values.items():
                        if key != "SUM":
                            r = Result(
                                action=key,
                                language=language,
                                comment=details.get('comment'),
                                files=details.get('nFiles'),
                                code=details.get('code'),
                                blank=details.get('blank'),
                                task=task,
                            )
                            r.save()
                    if key == "SUM":
                        for action, details in values.items():
                            r = Result(
                                tittle="SUM",
                                action=action,
                                comment=details.get('comment'),
                                files=details.get('nFiles'),
                                code=details.get('code'),
                                blank=details.get('blank'),
                                task=task,
                            )
                            r.save()
            else:
                logger.info(f"====Start validate standard report=====")
                for key, values in data.items():
                    r = Result(
                        language=key,
                        files=values.get('nFiles'),
                        code=values.get('code'),
                        comment=values.get('comment'),
                        blank=values.get('blank'),
                        task=task,
                    )
                    r.save()            
            success, object_name = upload_result_to_s3('cloc', str(task.id), git_url)
            if not success:
                logger.error(f"Cannot upload file to S3: {object_name}")
            else:
                task.s3_object = object_name
                task.save()
            call_lambda_check_and_scan()
            remove_repo_folder(str(task.id))
            logger.info("========== Updated task successfully ==========")
            return self.update(request, *args, **kwargs)
        except Http404:
            logger.error("Given Task ID not found")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response(data=e, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        logger.info(f"========== Deleting task {pk} by {request.user.email}")
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if task.s3_object:
            delete_s3_object(task.s3_object)
        return super().delete(request, *args, **kwargs)


class DowloadObject(APIView):
    def get(self, request, pk, format=None):
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)

        download_link = download_from_s3(task.s3_object)
        return Response(
            status=status.HTTP_200_OK,
            data={"download_link": download_link}
        )


class ResultView(APIView):
    def get(self, request, pk, format=None):
        logger.info("====== Getting cloc task result")
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ResultSerializer(task.results, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


def get_task(pk):
    try:
        return Task.objects.get(pk=pk)
    except ObjectDoesNotExist:
        logger.error("==== Task has been deleted!")
