"""Parser tests with synthetic copies of the real service field structure."""
import importlib.util
import pathlib
import unittest
from datetime import date

spec = importlib.util.spec_from_file_location('api', pathlib.Path(__file__).parents[1] / 'custom_components/historia_pojazdu/api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def event(kind, day, name='', details=None):
    return {'eventType': kind, 'eventDate': day, 'eventName': name, 'eventDetails': details or []}

def report(events, insurance='2031-05-06'):
    return {'timelineData': {'insuranceExpiryDate': insurance, 'events': events}}

def first():
    return event('pierwsza-rejestracja-w-polsce', '2022-04-05', details=[{'name':'Termin następnego badania technicznego', 'value':'07.05.2031'}])

class ParserTests(unittest.TestCase):
    def test_odometer_latest_inspection_not_max_or_road_check(self):
        def reading(kind, day, value):
            return event(kind, day, details=[{'name': 'Odczytany stan drogomierza', 'value': value}])
        values = [reading('badanie-techniczne-okresowe', '2024-01-01', '100 000 km'),
                  reading('badanie-techniczne-okresowe', '2025-01-01', '95\u00a0000 km'),
                  reading('odczyt-drogomierza-podczas-kontroli', '2026-01-01', '110000 km')]
        self.assertEqual(api.parse_report(report(values))[2], (95000, 'km', date(2025, 1, 1)))

    def test_odometer_missing_ambiguous_and_miles(self):
        def reading(day, value):
            return event('badanie-techniczne-okresowe', day, details=[{'name': 'Odczytany stan licznika', 'value': value}])
        self.assertIsNone(api.parse_report(report([]))[2])
        self.assertEqual(api.parse_report(report([reading('2025-01-01', '12345 mi')]))[2], (12345, 'mi', date(2025, 1, 1)))
        self.assertIsNone(api.parse_report(report([reading('2025-01-01', 'abc km')]))[2])
        self.assertIsNone(api.parse_report(report([reading('2025-01-01', '123 km'), reading('2025-01-01', '456 km')]))[2])

    def test_old_malformed_reading_does_not_hide_newer_one(self):
        def reading(day, value):
            return event('badanie-techniczne-okresowe', day, details=[{'name': 'Odczytany stan drogomierza', 'value': value}])
        events = [reading('2023-01-01', 'nieczytelny'), reading('2025-01-01', '95 000 km')]
        self.assertEqual(api.parse_report(report(events))[2], (95000, 'km', date(2025, 1, 1)))
        events = [reading('2025-01-01', '95 000 km'), reading('2025-06-01', 'nieczytelny')]
        self.assertIsNone(api.parse_report(report(events))[2])

    def test_first_registration(self):
        self.assertEqual(api.parse_report(report([first()])), (date(2031, 5, 6), date(2031, 5, 7), None))

    def test_latest_event_not_maximum_expiry(self):
        old = event('badanie-techniczne-okresowe', '2025-08-29', 'Okresowe badanie techniczne (ważne do 29.08.2029)')
        newer = event('badanie-techniczne', '2026-01-02', 'Badanie techniczne (ważne do 02.01.2027)')
        self.assertEqual(api.parse_report(report([first(), old, newer]))[1], date(2027, 1, 2))

    def test_newer_event_without_expiry_is_uncertain(self):
        ev = event('badanie-techniczne-okresowe', '2026-01-02', 'Badanie dnia 02.01.2026')
        self.assertIsNone(api.parse_report(report([first(), ev]))[1])

    def test_unorderable_inspection_is_uncertain(self):
        ev = event('badanie-techniczne', None, 'Badanie techniczne (ważne do 02.01.2027)')
        self.assertIsNone(api.parse_report(report([first(), ev]))[1])

    def test_same_day_disagreement_is_uncertain(self):
        ev = event('badanie-techniczne', '2022-04-05', 'Badanie techniczne (ważne do 02.01.2027)')
        self.assertIsNone(api.parse_report(report([first(), ev]))[1])

    def test_missing_or_invalid_fields(self):
        self.assertEqual(api.parse_report(report([], 'invalid')), (None, None, None))
        self.assertEqual(api.parse_report({'timelineData': {'insuranceExpiryDate': '2031-05-06'}}), (date(2031,5,6), None, None))
        with self.assertRaises(api.FetchError):
            api.parse_report({'error': 'unavailable'})

    def test_do_not_accept_incidental_dates_or_invalid_dates(self):
        for text in ['Badanie 01.02.2028', 'Badanie (ważne do 30.02.2028)', 'ważne do 01.02.2028 i ważne do 02.02.2028']:
            self.assertIsNone(api.parse_report(report([event('badanie-techniczne', '2026-01-02', text)]))[1])

if __name__ == '__main__':
    unittest.main()
