#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

import requests
from airbyte_cdk.sources.declarative.interpolation.interpolated_boolean import InterpolatedBoolean
from airbyte_cdk.sources.declarative.requesters.retriers.retrier import Retrier
from airbyte_cdk.sources.streams.http.http import HttpStream


class HttpResponseFilter:
    TOO_MANY_REQUESTS_ERRORS = [429]
    DEFAULT_RETRIABLE_ERRORS = [x for x in range(500, 600)] + TOO_MANY_REQUESTS_ERRORS

    def __init__(self, http_codes: List[int] = None, error_message_contain: str = None, predicate: str = ""):
        self._http_codes = http_codes or HttpResponseFilter.DEFAULT_RETRIABLE_ERRORS
        self._predicate = InterpolatedBoolean(predicate)
        self._error_message_contains = error_message_contain

    def matches(self, response: requests.Response) -> bool:
        return (
            response.status_code in self._http_codes
            or (self._response_matches_predicate(response))
            or (self._response_contains_error_message(response))
        )

    def _response_matches_predicate(self, response: requests.Response) -> bool:
        return self._predicate and self._predicate.eval(None, decoded_response=response.json())

    def _response_contains_error_message(self, response: requests.Response) -> bool:
        print(f"self._error_message_contains: {self._error_message_contains}")
        if not self._error_message_contains:
            return False
        else:
            return self._error_message_contains in HttpStream.parse_response_error_message(response)


class NonRetriableResponseStatus(Enum):
    Ok = ("OK",)
    FAIL = ("FAIL",)
    IGNORE = ("IGNORE",)


@dataclass
class RetryResponseStatus:
    retry_in: Optional[float]


ResponseStatus = Union[NonRetriableResponseStatus, RetryResponseStatus]


class DefaultRetrier(Retrier):
    def __init__(
        self,
        retry_response_filter: HttpResponseFilter = None,
        ignore_response_filter: HttpResponseFilter = None,
        max_retries: Optional[int] = 5,
        retry_factor: float = 5,
    ):
        self._max_retries = max_retries
        self._retry_factor = retry_factor
        self._retry_response_filter = retry_response_filter or HttpResponseFilter()
        self._ignore_response_filter = ignore_response_filter or HttpResponseFilter([])

    @property
    def max_retries(self) -> Union[int, None]:
        return self._max_retries

    @property
    def retry_factor(self) -> float:
        return self._retry_factor

    def should_retry(self, response: requests.Response) -> ResponseStatus:
        if self._retry_response_filter.matches(response):
            return RetryResponseStatus(self.backoff_time(response))
        elif self._ignore_response_filter.matches(response):
            return NonRetriableResponseStatus.IGNORE
        elif response.ok:
            return NonRetriableResponseStatus.Ok
        else:
            return NonRetriableResponseStatus.FAIL

    def backoff_time(self, response: requests.Response) -> Optional[float]:
        return None
