"""Unofficial Historia Pojazdu protocol and conservative timeline parser.

Based on Korea77/historia-pojazdu-sdk, commit 1f4c496ef728011903b308dfa90d74409da05740.
GPL-3.0; see the repository LICENSE.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_URL = 'https://moj.gov.pl/nforms/engine/ng/index?xFormsAppName=HistoriaPojazdu'
_API = 'https://moj.gov.pl/nforms/api/HistoriaPojazdu/1.0.20/data/timeline-data'
_EXPIRY = re.compile(r'ważne\s+do\s+(\d{2}\.\d{2}\.\d{4})', re.IGNORECASE)
_INSPECTIONS = ('badanie-techniczne-okresowe', 'badanie-techniczne')
_ATTEMPTS = 3

Report = tuple[date | None, date | None, tuple[int, str, date] | None]


class FetchError(Exception):
    """Sanitized failure; never includes credentials or server response."""


class VehicleRejected(FetchError):
    """The service refused the vehicle data (HTTP 4xx); retrying will not help."""


def _date(value: Any, fmt: str) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), fmt).date()
    except ValueError:
        return None


def _event_date(event: dict) -> date | None:
    return _date(event.get('eventDate'), '%Y-%m-%d') or _date(event.get('eventDate'), '%d.%m.%Y')


def _inspection_odometer(events: list) -> tuple[int, str, date] | None:
    """Return the latest unambiguous inspection reading, never road checks.

    A malformed reading only matters when it is on or after the newest valid
    reading date; an old malformed entry no longer hides a valid newer one.
    """
    readings: list[tuple[date, int, str]] = []
    bad_days: set[date] = set()
    for event in events:
        if not isinstance(event, dict) or event.get('eventType') not in _INSPECTIONS:
            continue
        details = event.get('eventDetails')
        if not isinstance(details, list):
            continue
        fields = [item.get('value') for item in details if isinstance(item, dict)
                  and item.get('name') in ('Odczytany stan drogomierza', 'Odczytany stan licznika')]
        if not fields:
            continue
        day = _event_date(event)
        if day is None:
            return None  # cannot tell whether this reading is the newest one
        match = None
        if len(fields) == 1 and isinstance(fields[0], str):
            match = re.fullmatch(r'\s*(\d+(?:[\s  ]\d+)*)\s*(km|mi|mil|mile)\s*', fields[0], re.IGNORECASE)
        if not match:
            bad_days.add(day)
            continue
        number = int(re.sub(r'\s', '', match.group(1)))
        unit = 'km' if match.group(2).lower() == 'km' else 'mi'
        readings.append((day, number, unit))
    if not readings:
        return None
    latest = max(day for day, _, _ in readings)
    if any(day >= latest for day in bad_days):
        return None
    values = {(number, unit) for day, number, unit in readings if day == latest}
    if len(values) != 1:
        return None
    number, unit = values.pop()
    return number, unit, latest


def parse_report(report: Any) -> Report:
    """Return independent dates, or None for missing/ambiguous values.

    A newer inspection without a valid expiry invalidates an older expiry.
    Select the latest event by event date, not latest expiry.
    """
    if not isinstance(report, dict) or not isinstance(report.get('timelineData'), dict):
        raise FetchError('Nieprawidłowa odpowiedź usługi')
    timeline = report['timelineData']
    insurance = _date(timeline.get('insuranceExpiryDate'), '%Y-%m-%d')
    events = timeline.get('events')
    if not isinstance(events, list):
        return insurance, None, None
    odometer = _inspection_odometer(events)
    candidates: list[tuple[date, date | None]] = []
    ambiguous = False
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get('eventType')
        if kind != 'pierwsza-rejestracja-w-polsce' and kind not in _INSPECTIONS:
            continue
        event_date = _event_date(event)
        expiry = None
        if kind == 'pierwsza-rejestracja-w-polsce':
            details = event.get('eventDetails')
            if isinstance(details, list):
                dates = [_date(item.get('value'), '%d.%m.%Y') for item in details
                         if isinstance(item, dict) and item.get('name') == 'Termin następnego badania technicznego']
                valid = [d for d in dates if d is not None]
                if len(dates) == 1 and len(valid) == 1:
                    expiry = valid[0]
        else:
            name = event.get('eventName')
            matches = _EXPIRY.findall(name) if isinstance(name, str) else []
            if len(matches) == 1:
                expiry = _date(matches[0], '%d.%m.%Y')
        if event_date is None:
            # An unorderable relevant event may be newer than the known event.
            ambiguous = True
        else:
            candidates.append((event_date, expiry))
    if ambiguous or not candidates:
        return insurance, None, odometer
    newest = max(d for d, _ in candidates)
    same_day = [expiry for event_day, expiry in candidates if event_day == newest]
    # Multiple contradictory events on the same date cannot be ordered safely.
    inspection = same_day[0] if same_day and all(x == same_day[0] for x in same_day) else None
    return insurance, inspection, odometer


async def fetch_report(registration: str, vin: str, first_registration: str,
                       session_factory: Callable[[], aiohttp.ClientSession] | None = None) -> Report:
    """Fetch and parse the report with bounded timeouts and retries.

    Each attempt uses a new, short-lived session so the XSRF cookie never
    leaks between attempts or vehicles. session_factory exists for tests.
    """
    timeout = aiohttp.ClientTimeout(total=15, connect=6)
    factory = session_factory or (lambda: aiohttp.ClientSession(timeout=timeout))
    for attempt in range(_ATTEMPTS):
        try:
            async with factory() as session:
                wid = f'HistoriaPojazdu:{int(time.time() * 1000)}'
                headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://moj.gov.pl', 'Referer': _URL}
                async with session.post(_URL, data={'NF_WID': wid}, headers=headers, timeout=timeout) as response:
                    response.raise_for_status()
                    cookie = response.cookies.get('XSRF-TOKEN')
                    if cookie is None or not cookie.value:
                        raise FetchError('Brak tokenu usługi')
                    token = cookie.value
                headers.update({'X-XSRF-TOKEN': token, 'NF_WID': wid})
                async with session.post(_API, json={'registrationNumber': registration, 'VINNumber': vin,
                                        'firstRegistrationDate': first_registration},
                                        headers=headers, timeout=timeout) as response:
                    if 400 <= response.status < 500 and response.status not in (408, 429):
                        _LOGGER.debug('Service rejected vehicle data with HTTP %s', response.status)
                        raise VehicleRejected(f'Usługa odrzuciła dane pojazdu (HTTP {response.status})')
                    response.raise_for_status()
                    report = await response.json(content_type=None)
                return parse_report(report)
        except VehicleRejected:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, FetchError) as exc:
            # Log only the failure type and HTTP status, never request data or the body.
            status = getattr(exc, 'status', None)
            _LOGGER.debug('Attempt %s/%s failed: %s%s', attempt + 1, _ATTEMPTS, type(exc).__name__,
                          f' (HTTP {status})' if status else '')
            if attempt == _ATTEMPTS - 1:
                raise FetchError('Nie udało się pobrać lub odczytać danych usługi') from None
            await asyncio.sleep(2 ** attempt)
    raise FetchError('Nie udało się pobrać danych')
