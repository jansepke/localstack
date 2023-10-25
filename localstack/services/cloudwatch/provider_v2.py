import logging

from localstack.http import Request
from localstack.aws.api import RequestContext, handler
from localstack.aws.api.cloudwatch import (
    ActionPrefix,
    AlarmName,
    AlarmNamePrefix,
    AlarmNames,
    AlarmTypes,
    CloudwatchApi,
    DescribeAlarmsOutput,
    InvalidParameterValueException,
    MaxRecords,
    NextToken,
    PutMetricAlarmInput,
    StateValue,
)
from localstack.services.cloudwatch.alarm_scheduler import AlarmScheduler
from localstack.services.cloudwatch.models import (
    CloudWatchStore,
    LocalStackMetricAlarm,
    cloudwatch_stores,
)
from localstack.services.edge import ROUTER
from localstack.services.plugins import SERVICE_PLUGINS, ServiceLifecycleHook
from localstack.utils.sync import poll_condition
from localstack.utils.tagging import TaggingService
from localstack.utils.threads import start_worker_thread

PATH_GET_RAW_METRICS = "/_aws/cloudwatch/metrics/raw"
DEPRECATED_PATH_GET_RAW_METRICS = "/cloudwatch/metrics/raw"
MOTO_INITIAL_UNCHECKED_REASON = "Unchecked: Initial alarm creation"

LOG = logging.getLogger(__name__)


class CloudwatchProvider(CloudwatchApi, ServiceLifecycleHook):
    """
    Cloudwatch provider.

    LIMITATIONS:
        - no alarm rule evaluation
    """

    def __init__(self):
        self.tags = TaggingService()
        self.alarm_scheduler: AlarmScheduler = None
        self.store = None

    @staticmethod
    def get_store(account_id: str, region: str) -> CloudWatchStore:
        return cloudwatch_stores[account_id][region]

    def on_after_init(self):
        ROUTER.add(PATH_GET_RAW_METRICS, self.get_raw_metrics)
        self.start_alarm_scheduler()

    def on_before_state_reset(self):
        self.shutdown_alarm_scheduler()

    def on_after_state_reset(self):
        self.start_alarm_scheduler()

    def on_before_state_load(self):
        self.shutdown_alarm_scheduler()

    def on_after_state_load(self):
        self.start_alarm_scheduler()

        def restart_alarms(*args):
            poll_condition(lambda: SERVICE_PLUGINS.is_running("cloudwatch"))
            self.alarm_scheduler.restart_existing_alarms()

        start_worker_thread(restart_alarms)

    def on_before_stop(self):
        self.shutdown_alarm_scheduler()

    def start_alarm_scheduler(self):
        if not self.alarm_scheduler:
            LOG.debug("starting cloudwatch scheduler")
            self.alarm_scheduler = AlarmScheduler()

    def shutdown_alarm_scheduler(self):
        LOG.debug("stopping cloudwatch scheduler")
        self.alarm_scheduler.shutdown_scheduler()
        self.alarm_scheduler = None

    def delete_alarms(self, context: RequestContext, alarm_names: AlarmNames) -> None:
        """
        Delete alarms.
        """

        for alarm_name in alarm_names.alarm_names:
            alarm_arn = ""  # obtain alarm ARN from alarm name
            self.alarm_scheduler.delete_alarm(alarm_arn)


    def get_raw_metrics(self, request: Request):
        # TODO this needs to be read from the database
        # FIXME this is just a placeholder for now
        return {"metrics": []}
    @handler("PutMetricAlarm", expand=False)
    def put_metric_alarm(self, context: RequestContext, request: PutMetricAlarmInput) -> None:
        extended_statistic = request.get("ExtendedStatistic")
        if extended_statistic and not extended_statistic.startswith("p"):
            raise InvalidParameterValueException(
                f"The value {extended_statistic} for parameter ExtendedStatistic is not supported."
            )
        evaluate_low_sample_count_percentile = request.get("EvaluateLowSampleCountPercentile")
        if evaluate_low_sample_count_percentile and evaluate_low_sample_count_percentile not in (
            "evaluate",
            "ignore",
        ):
            # TODO: check exception type against AWS
            raise InvalidParameterValueException(
                f"Option {evaluate_low_sample_count_percentile} is not supported. "
                "Supported options for parameter EvaluateLowSampleCountPercentile are evaluate and ignore."
            )

        store = self.get_store(context.account_id, context.region)
        metric_alarm = LocalStackMetricAlarm(context.account_id, context.region, {**request})
        alarm_arn = metric_alarm.alarm["AlarmArn"]
        store.Alarms[alarm_arn] = metric_alarm

    def describe_alarms(
        self,
        context: RequestContext,
        alarm_names: AlarmNames = None,
        alarm_name_prefix: AlarmNamePrefix = None,
        alarm_types: AlarmTypes = None,
        children_of_alarm_name: AlarmName = None,
        parents_of_alarm_name: AlarmName = None,
        state_value: StateValue = None,
        action_prefix: ActionPrefix = None,
        max_records: MaxRecords = None,
        next_token: NextToken = None,
    ) -> DescribeAlarmsOutput:
        store = self.get_store(context.account_id, context.region)
        if action_prefix:
            alarms = self._get_alarms_by_action_prefix(action_prefix)
        elif alarm_name_prefix:
            alarms = self._get_alarms_by_alarm_name_prefix(alarm_name_prefix)
        elif alarm_names:
            alarms = self._get_alarms_by_alarm_names(alarm_names)
        elif state_value:
            alarms = self._get_alarms_by_state_value(state_value)
        else:
            alarms = list(store.Alarms.values())
        # TODO: differentiate metric and composite alarms
        # metric_alarms = [a.alarm for a in alarms if a.rule is None]
        # composite_alarms = [a.alarm for a in alarms if a.rule is not None]
        composite_alarms = []
        metric_alarms = [a.alarm for a in alarms]
        return DescribeAlarmsOutput(CompositeAlarms=composite_alarms, MetricAlarms=metric_alarms)

    def _get_alarms_by_action_prefix(self, action_prefix):
        pass

    def _get_alarms_by_alarm_name_prefix(self, alarm_name_prefix):
        pass

    def _get_alarms_by_alarm_names(self, alarm_names):
        pass

    def _get_alarms_by_state_value(self, state_value):
        pass
