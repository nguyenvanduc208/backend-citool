import uuid
import os
import shutil
from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import ForeignKey, Model, CharField, DateTimeField, PositiveIntegerField, PositiveSmallIntegerField, FileField, DO_NOTHING, UUIDField

STATUS_CHOICES = [
    (0, 'RUNNING'),
    (1, 'COMPLETED'),
    (2, 'ERROR'),
]

TYPE_CHOICES = [
    ('CONFIG', 'CONFIG'),
    ('SCRIPT', 'SCRIPT'),
    ('SECURITY', 'SECURITY'),
]

class Task(Model):
    def _get_upload_to(instance, filename):
        return '{}/{}'.format(datetime.now().strftime("%Y%m%d_%H%M%S"), filename)

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = ForeignKey(User, on_delete=DO_NOTHING, null=True, related_name="jmetertask")
    loops = PositiveIntegerField(null=True)
    num_threads = PositiveIntegerField(null=True)
    ramp_time = PositiveIntegerField(null=True)    
    protocol = CharField(max_length=10, null=True)
    domain = CharField(max_length=100, null=True)
    port = PositiveIntegerField(null=True)
    run_type = CharField(choices=TYPE_CHOICES, max_length=10)
    file = FileField(null=True, upload_to=_get_upload_to)
    status = PositiveSmallIntegerField(choices=STATUS_CHOICES, default=0)
    report = CharField(max_length=200, null=True)
    timestamp = DateTimeField(auto_now_add=True)

    def delete(self, *args, **kwargs):
        if self.file:
            f_dir = self.file.name.split("/")[0]
            shutil.rmtree(os.path.join(settings.MEDIA_ROOT, f_dir), ignore_errors=True)
        shutil.rmtree(os.path.join(settings.MEDIA_ROOT, str(self.id)), ignore_errors=True)
        super(Task, self).delete(*args,**kwargs)

    def __str__(self):
        return f"{self.loops}, {self.num_threads}, {self.domain}"
