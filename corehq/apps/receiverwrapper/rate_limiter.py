from django.conf import settings

from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition
from corehq.toggles import RATE_LIMIT_SUBMISSIONS, NAMESPACE_DOMAIN
from corehq.util.datadog.gauges import datadog_counter, datadog_gauge
from corehq.util.datadog.utils import bucket_value
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext

# Danny promised in an Aug 2019 email not to enforce limits that were lower than this.
#   RateDefinition(
#       per_week=115,
#       per_day=23,
#       per_hour=3,
#       per_minute=0.07,
#       per_second=0.005,
#   ) == get_standard_ratio_rate_definition(events_per_day=23)
# If we as a team end up regretting this decision, we'll have to reset expectations
# with the Dimagi NDoH team.

SUBMISSIONS_PER_DAY = 46

submission_rate_limiter = RateLimiter(
    feature_key='submissions',
    get_rate_limits=PerUserRateDefinition(
        per_user_rate_definition=get_standard_ratio_rate_definition(
            events_per_day=SUBMISSIONS_PER_DAY),
        constant_rate_definition=RateDefinition(
            per_week=100,
            per_day=50,
            per_hour=30,
            per_minute=10,
            per_second=1,
        ),
    ).get_rate_limits
)

global_submission_rate_limiter = RateLimiter(
    feature_key='global_submissions',
    get_rate_limits=lambda: get_dynamic_rate_definition(
        'global_submissions',
        default=RateDefinition(
            per_hour=17000,
            per_minute=400,
            per_second=30,
        )
    ).get_rate_limits(),
    scope_length=0,
)


SHOULD_RATE_LIMIT_SUBMISSIONS = not settings.ENTERPRISE_MODE and not settings.UNIT_TESTING


@run_only_when(SHOULD_RATE_LIMIT_SUBMISSIONS)
@silence_and_report_error("Exception raised in the submission rate limiter",
                          'commcare.xform_submissions.rate_limiter_errors')
def rate_limit_submission(domain):
    should_allow_usage = (
        global_submission_rate_limiter.allow_usage()
        or submission_rate_limiter.allow_usage(domain))

    if should_allow_usage:
        allow_usage = True
    elif RATE_LIMIT_SUBMISSIONS.enabled(domain, namespace=NAMESPACE_DOMAIN):
        allow_usage = False
        _report_rate_limit_submission(domain)
    else:
        allow_usage = True
        _delay_and_report_rate_limit_submission_test(domain, max_wait=15)

    if allow_usage:
        submission_rate_limiter.report_usage(domain)
        global_submission_rate_limiter.report_usage()
        _report_current_global_submission_thresholds()

    return not allow_usage


def _report_rate_limit_submission(domain):
    datadog_counter('commcare.xform_submissions.rate_limited', tags=[
        'domain:{}'.format(domain),
    ])


def _delay_and_report_rate_limit_submission_test(domain, max_wait):
    with TimingContext() as timer:
        acquired = submission_rate_limiter.wait(domain, timeout=max_wait)
    if acquired:
        duration_tag = bucket_value(timer.duration, [1, 5, 10, 15, 20], unit='s')
    else:
        duration_tag = 'timeout'
    datadog_counter('commcare.xform_submissions.rate_limited.test', tags=[
        'domain:{}'.format(domain),
        'duration:{}'.format(duration_tag)
    ])


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_submission_thresholds():
    for window, value, threshold in global_submission_rate_limiter.iter_rates():
        datadog_gauge('commcare.xform_submissions.global_threshold', threshold, tags=[
            'window:{}'.format(window)
        ])
        datadog_gauge('commcare.xform_submissions.global_usage', value, tags=[
            'window:{}'.format(window)
        ])
