from typing import Dict

from moto.cloudwatch.models import CloudWatchBackend as MotoCloudWatchBackend
from moto.cloudwatch.models import cloudwatch_backends as moto_cloudwatch_backend

from localstack.aws.api.cloudwatch import MetricAlarm
from localstack.services.stores import (
    AccountRegionBundle,
    BaseStore,
    CrossRegionAttribute,
    LocalAttribute,
)


def get_moto_logs_backend(account_id: str, region_name: str) -> MotoCloudWatchBackend:
    return moto_cloudwatch_backend[account_id][region_name]


class LocalStackMetricAlarm:
    region: str
    account_id: str

    alarm: MetricAlarm

    def __init__(self, account_id: str, region: str, alarm: MetricAlarm):
        self.account_id = account_id
        self.region = region
        self.alarm = alarm
        alarm[
            "AlarmArn"
        ] = f"arn:aws:cloudwatch:{self.region}:{self.account_id}:{self.alarm['AlarmName']}"


class CloudWatchStore(BaseStore):
    # maps resource ARN to tags
    TAGS: Dict[str, Dict[str, str]] = CrossRegionAttribute(default=dict)

    # maps resource ARN to alarms
    Alarms: Dict[str, LocalStackMetricAlarm] = LocalAttribute(default=dict)


cloudwatch_stores = AccountRegionBundle("cloudwatch", CloudWatchStore)
