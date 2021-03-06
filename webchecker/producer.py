import logging
import time
from multiprocessing.dummy import Pool as ThreadPool

import requests

from webchecker import settings
from webchecker.database import db
from webchecker.kafka import producer
from webchecker.schemas import Metric, Site

log = logging.getLogger(__name__)


def check_site(site: Site):
    try:
        result = requests.get(site.url, timeout=settings.SITE_CHECK_TIMEOUT)
    except Exception as e:
        metric = Metric(
            site_id=site.id,
            error=e.__class__.__name__,
        )
    else:
        metric = Metric(
            status_code=result.status_code,
            site_id=site.id,
            request_time=result.elapsed.total_seconds(),
        )
    log.info(metric)
    return metric


def get_sites():
    with db.cursor() as c:
        c.execute("select id, url from sites")
        for site_data in c:
            yield Site(**site_data)


def run_producer(args):
    while True:
        pool = ThreadPool(settings.PRODUCER_THREAD_POOL_SIZE)

        metrics = pool.map(check_site, get_sites())

        for metric in metrics:
            producer.send(settings.KAFKA_METRICS_TOPIC, metric.json().encode("utf-8"))

        time.sleep(settings.SLEEP_AFTER_CHECK)
