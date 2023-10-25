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


class LocalStackMetricAlarm(MetricAlarm):
    name: str
    region: str
    account_id: str

    def __int__(
        self,
        name,
        region,
        account_id,
        alarm_name,
        alarm_description=None,
        alarm_configuration_updated_timestamp=None,
        actions_enabled=None,
        ok_actions=None,
        alarm_actions=None,
        insufficient_data_actions=None,
        state_value=None,
        state_reason=None,
        state_reason_data=None,
        state_updated_timestamp=None,
        metric_name=None,
        namespace=None,
        statistic=None,
        extended_statistic=None,
        dimensions=None,
        period=None,
        unit=None,
        evaluation_periods=None,
        datapoints_to_alarm=None,
        threshold=None,
        comparison_operator=None,
        treat_missing_ata=None,
        evaluate_low_sample_count_percentile=None,
        metrics=None,
        threshold_metric_id=None,
        evaluation_state=None,
        state_transitioned_timestamp=None,
    ):
        self.name = name
        self.region = region
        self.account_id = account_id

    @property
    def arn(self):
        return f"arn:aws:sqs:{self.region}:{self.account_id}:{self.name}"


class CloudWatchStore(BaseStore):
    # maps resource ARN to tags
    TAGS: Dict[str, Dict[str, str]] = CrossRegionAttribute(default=dict)

    # maps resource ARN to alarms
    Alarms: Dict[str, LocalStackMetricAlarm] = LocalAttribute(default=dict)


cloudwatch_stores = AccountRegionBundle("cloudwatch", CloudWatchStore)
