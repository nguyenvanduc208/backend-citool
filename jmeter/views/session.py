from multiprocessing.dummy import Pool

from rest_framework import generics, mixins
from rest_framework import status
from rest_framework.response import Response

from jmeter.models import Task
from jmeter.serializers import SessionSerializers
from jmeter.execute import perform_task, on_result, on_error


class SessionCreate(mixins.UpdateModelMixin,
                    generics.ListCreateAPIView):
    serializer_class = SessionSerializers

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user).order_by('timestamp').reverse()

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        record.user = request.user
        record.save()

        pool = Pool(1)
        pool.apply_async(perform_task, args=(record,), callback=on_result, error_callback=on_error)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class SessionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = SessionSerializers
