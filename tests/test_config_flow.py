"""Input normalisation and validation of the config flow form."""
import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import _stubs  # noqa: E402

flow = _stubs.load('config_flow')

VALID = {'name': ' Volvo ', 'registration': 'wa 12345', 'vin': 'yv1uzarv1j1234567', 'first_registration': '2018-03-15'}


class NormalizeTests(unittest.TestCase):
    def test_valid_input_is_normalised(self):
        data, errors = flow._normalize(VALID)
        self.assertEqual(errors, {})
        self.assertEqual(data, {'name': 'Volvo', 'registration': 'WA12345', 'vin': 'YV1UZARV1J1234567',
                                'first_registration': '2018-03-15'})

    def test_registration_card_date_format(self):
        self.assertEqual(flow._parse_date('15.03.2018'), date(2018, 3, 15))
        self.assertEqual(flow._parse_date('2018-03-15'), date(2018, 3, 15))
        for bad in ('', None, '31.02.2018', '2018/03/15', '15.03'):
            self.assertIsNone(flow._parse_date(bad), bad)

    def test_errors_are_reported_per_field(self):
        _, errors = flow._normalize({'name': ' ', 'registration': 'W', 'vin': 'YV1UZARV1J123456O',
                                     'first_registration': '2027-01-01'})
        self.assertEqual(errors, {'name': 'invalid_name', 'registration': 'invalid_registration',
                                  'vin': 'invalid_vin', 'first_registration': 'invalid_date'})


if __name__ == '__main__': unittest.main()
