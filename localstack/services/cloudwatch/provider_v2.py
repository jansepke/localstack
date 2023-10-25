import logging
from typing import List

from localstack.aws.api import RequestContext
from localstack.aws.api.cloudwatch import (
    AlarmNames,
    CloudwatchApi,
    GetMetricDataMaxDatapoints,
    GetMetricDataOutput,
    LabelOptions,
    MetricData,
    MetricDataQueries,
    MetricDataResultMessages,
    MetricDataResults,
    Namespace,
    NextToken,
    ScanBy,
    Timestamp,
)
from localstack.http import Request
from localstack.services.cloudwatch.alarm_scheduler import AlarmScheduler
from localstack.services.cloudwatch.cloudwatch_database_helper import CloudwatchDatabase
from localstack.services.edge import ROUTER
from localstack.services.plugins import SERVICE_PLUGINS, ServiceLifecycleHook
from localstack.utils.sync import poll_condition
from localstack.utils.tagging import TaggingService
from localstack.utils.threads import start_worker_thread

PATH_GET_RAW_METRICS = "/_aws/cloudwatch/metrics/raw"
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
        self.cloudwatch_database = CloudwatchDatabase()

    def on_after_init(self):
        ROUTER.add(PATH_GET_RAW_METRICS, self.get_raw_metrics)
        self.start_alarm_scheduler()

    def on_before_state_reset(self):
        self.shutdown_alarm_scheduler()
        self.cloudwatch_database.clear_tables()

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
        self.cloudwatch_database.shutdown()

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

    def put_metric_data(
        self, context: RequestContext, namespace: Namespace, metric_data: MetricData
    ) -> None:
        # TODO add validation
        self.cloudwatch_database.add_metric_data(
            context.account_id, context.region, namespace, metric_data
        )

    def get_metric_data(
        self,
        context: RequestContext,
        metric_data_queries: MetricDataQueries,
        start_time: Timestamp,
        end_time: Timestamp,
        next_token: NextToken = None,
        scan_by: ScanBy = None,
        max_datapoints: GetMetricDataMaxDatapoints = None,
        label_options: LabelOptions = None,
    ) -> GetMetricDataOutput:
        results: List[MetricDataResults] = []
        for query in metric_data_queries:
            query_result = self.cloudwatch_database.get_metric_data_stat(
                account_id=context.account_id,
                region=context.region,
                query=query,
                start_time=start_time,
                end_time=end_time,
                scan_by=scan_by,
            )
            results.append(query_result)

        # TODO pagination
        # from localstack.utils.collections import PaginatedList
        #
        # aliases_list = PaginatedList(results)
        # limit = max_datapoints or 100_800
        # page, nxt = aliases_list.get_page(
        #     lambda metric_result: metric_result.get("Id"),
        #     next_token=next_token,
        #     page_size=limit,
        # )
        #
        nxt: NextToken = None
        # TODO might contain error messages if data could not be retrieved, needs testing
        messages: MetricDataResultMessages = None  # TODO
        # TODO parse dataresults
        return GetMetricDataOutput(MetricDataResults=[], NextToken=nxt, Messages=messages)

    def get_raw_metrics(self, request: Request):
        # TODO this needs to be read from the database
        # FIXME this is just a placeholder for now
        return {"metrics": []}
