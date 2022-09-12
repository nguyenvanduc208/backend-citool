import logging

from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from dast.models import Task, Result
from dast.serializers import CreateTaskSerializer, UpdateDestroyTaskSerializer, ResultSerializer
from citool.utils import call_lambda_listen_ssm, upload_result_to_s3, download_from_s3, delete_s3_object, \
    remove_repo_folder, get_result_data

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
        2. Call ssm to create folder
        """
        logger.info("========== Start creating a dast task ==========")
        logger.info(f"Request user: {request.user.email}")
        data = request.data
        logger.info(f"Request data: {data}")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        record = serializer.save()
        record.user = request.user
        record.save()
        logger.info(f"Created Task: {record.id}")

        try:
            filename = record.filename.path
        except Exception:
            filename = ""

        info = {
            "recordid": str(record.id),
            "targeturl": data.get("target_url"),
            "fullscan": data.get("full_scan", False),
            "dastpath": data.get("dast_path"),
            "type": "DAST",
            "filename": filename,
            "header_token": data.get("header_token"),
        }
        call_lambda_listen_ssm(info)
        headers = self.get_success_headers(serializer.data)
        logger.info("========== Finish creating a dast task ==========")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskRetrieveDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = UpdateDestroyTaskSerializer

    def put(self, request, *args, **kwargs):
        logger.info("========== Start updating dast task ==========")
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

            data = get_result_data(str(task.id), '', '', 'DAST')
            logger.info(f"Writing Data from result file to DB")
            start_time = data["scan"]["start_time"]
            end_time = data["scan"]["end_time"]

            # Remove duplicate item in json report
            datas_aft = process_dumplicate(data.get("vulnerabilities", []))

            for item in datas_aft:
                details = item.get("details")
                if details is not None:
                    href_url = get_url(details)
                else:
                    href_url = item.get("url")

                r = Result(
                    description=item.get("description"),
                    confidence=item.get("confidence"),
                    severity=item.get("severity"),
                    message=item.get("message"),
                    solution=item.get("solution"),
                    url=href_url,
                    cve=item.get("cve"),
                    task_id=str(task.id),
                    start_time=start_time,
                    end_time=end_time,
                )
                r.save()

            success, object_name = upload_result_to_s3('dast', str(task.id))
            if not success:
                logger.error(f"Cannot upload file to S3: {object_name}")
                task.status = "ERROR"
                task.save()
                return Response(status=status.HTTP_417_EXPECTATION_FAILED)

            task.s3_object = object_name
            task.save()
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
        logger.info(f"========== Deleting dast task {pk} by {request.user.email}")
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if task.s3_object:
            delete_s3_object(task.s3_object)
        return super().delete(request, *args, **kwargs)


class RetrieveResult(generics.RetrieveUpdateAPIView):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        task = get_task(pk)
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = Result.objects.filter(task=task)
        logger.info(f"========== Getting task info by: {request.user.email}")
        serializer = ResultSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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


def get_task(pk):
    try:
        return Task.objects.get(pk=pk)
    except ObjectDoesNotExist:
        logger.error("==== Task not found!")


def get_url(details):
    urls = details.get("urls")
    url_item = urls.get("items")
    href = [item['href'] for item in url_item]
    return ','.join(href)

def process_dumplicate(datas):
    # Return results
    results = []
    # Non-duplicate messages
    distinct_messages = []

    # Get non-duplicate messages
    for data in datas:
        if data.get("message") not in distinct_messages:
            distinct_messages.append(data.get("message"))
        else:
            continue
    
    # Merge duplicate items to one item
    for message in distinct_messages:
        items = [ d for d in datas if d.get("message") == message]

        result = {
            "description" : items[0].get("description"),
            "confidence": items[0].get("confidence"),
            "severity": items[0].get("severity"),
            "message": items[0].get("message"),
            "solution": items[0].get("solution"),
            "cve": items[0].get("cve"),
            "links": items[0].get("links"),
            "details": items[0].get("details")
        }

        url = []
        # Merge each item["url"] to one url string
        for item in items:
            url.append(item.get("evidence").get("request").get("url"))
        
        result["url"] = ",".join(url)

        results.append(result)
    
    return results


class ResultUpdate(generics.UpdateAPIView):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
