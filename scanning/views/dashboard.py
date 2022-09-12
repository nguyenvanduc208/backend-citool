import logging
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from scanning.models import Task as SastTask
from cloc.models import Task as ClocTask
from dast.models import Task as DastTask, Result as DastResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
critical = "Critical"
high = "High"


class RecentRun(APIView):

    def get(self, request, format=None):
        logger.info("====== Getting overview")
        tasks = []
        sast_tasks = self.get_newest_records(SastTask, "timestamp", "SAST")
        dast_tasks = self.get_newest_records(DastTask, "created_at", "DAST")
        cloc_tasks = self.get_newest_records(ClocTask, "created_at", "CLOC")

        tasks.extend(sast_tasks)
        tasks.extend(dast_tasks)
        tasks.extend(cloc_tasks)
        tasks = sorted(tasks, key=lambda t: t["created_time"], reverse=True)[:10]
        date_format = "%Y-%m-%d %H:%M:%S"
        for t in tasks:
            t["created_time"] = datetime.strftime(t["created_time"], date_format)
        return Response(tasks)

    def get_newest_records(self, obj, key, scan_type):
        data = []
        records = get_records(obj, self.request.user)
        records = records.order_by(key).reverse()[:10]
        data.extend([
            {
                "id": r.id,
                "scan_type": scan_type,
                "url": getattr(r, "git_url", getattr(r, "target_url", "")),
                "branch": getattr(r, "branch", "-"),
                "created_time": getattr(r, "timestamp", getattr(r, "created_at", "")),
                "status": r.status,
                "user": r.user.email,
            }
            for r in records
        ])
        return data


class OverView(APIView):
    # permission_classes = (permissions.AllowAny, )
    def get(self, request, format=None):
        user = self.request.user
        sast_data = get_records(SastTask, user)
        dast_data = get_records(DastTask, user)
        cloc_data = get_records(ClocTask, user)
        number_of_cloc = get_number_cloc(cloc_data)

        sast_repo = {t.git_url for t in sast_data}
        cloc_repo = {t.git_url for t in cloc_data}

        repo_list = sast_repo | cloc_repo

        sast_critical, sast_hight = get_sast_critical(user)

        dast_critical, dast_high = get_dast_severity(user)

        data = {
            "repository": {
                "count": len(repo_list),
                "sast_repo": len(sast_repo),
                "cloc_repo": len(cloc_repo),
            },
            "sast": {
                "count": sast_data.count(),
                "critical": sast_critical,
                "high_risk": sast_hight,
            },
            "dast": {
                "count": dast_data.count(),
                "critical": dast_critical,
                "high_risk": dast_high,
            },
            "cloc": {
                "count": cloc_data.count(),
                "compared": number_of_cloc['cloc_compared'],
                "other": number_of_cloc['cloc_none']
            },
        }
        return Response(data)


def get_records(obj, user):
    records = obj.objects.all()
    if not user.is_superuser:
        records = records.filter(user=user)
    return records

def get_number_cloc(obj):
    cloc_none = 0
    cloc_compared = 0
    for cloc in obj:
        if not ((cloc.compared_branch1 == '' or cloc.compared_branch1 is None) or (cloc.compared_branch2 == '' or cloc.compared_branch2 is None)):
            cloc_compared = cloc_compared + 1
        elif not ((cloc.commit_id1 == '' or cloc.commit_id1 is None) or (cloc.commit_id2 == '' or cloc.commit_id2 is None)):
            cloc_compared = cloc_compared + 1
        else:
            cloc_none = cloc_none + 1
    data = {
        "cloc_compared": cloc_compared,
        "cloc_none" : cloc_none
    }
    return data

def get_sast_critical(user):
    crit_count = 0
    high_count = 0

    sast = get_records(SastTask, user)

    for task in sast:
        sub = task.subtasks.all()
        for s in sub:
            crit_count += s.results.filter(severity=critical).count()
            high_count += s.results.filter(severity=high).count()

    return crit_count, high_count


def get_dast_severity(user):
    crit_count = 0
    high_count = 0

    dast = get_records(DastTask, user)
    for task in dast:
        crit_count += DastResult.objects.filter(task=task, severity=critical).count()
        high_count += DastResult.objects.filter(task=task, severity=high).count()

    return crit_count, high_count
