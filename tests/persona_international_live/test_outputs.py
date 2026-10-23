"""Validate real CLI outputs; failed attempts fail, never-run cases are skipped."""
from datetime import date
import argparse
import json
from pathlib import Path
import unittest
import sys

HERE = Path(__file__).resolve().parent
KEYS = ('name birth age nationality home_address birth_place gender education job occupation '
        'workplace belief salary body family personality hobbies favorite_foods memory_date aim '
        'healthy_desc lifestyle_desc economic_desc work_desc experience_desc description relation').split()


class RealPersonaOutputs(unittest.TestCase):
    def check_case(self, case):
        path = HERE / case / 'persona_list.json'
        if not path.exists():
            summary_path = HERE / case / 'run_summary.json'
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding='utf-8'))
                self.fail(f"{case}: real generation exited {summary['exit_code']} without a complete persona; see generation.log")
            self.skipTest(f'{case}: real generation has not produced an output')
        people = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(people), 1)
        person = people[0]
        self.assertEqual(list(person), KEYS)
        birthday = date.fromisoformat(person['birth'])
        as_of = date(2025, 12, 31)
        self.assertEqual(person['age'], as_of.year - birthday.year - ((as_of.month, as_of.day) < (birthday.month, birthday.day)))
        contacts = [contact for group in person['relation'] for contact in group]
        self.assertGreaterEqual(len(contacts), 16)
        self.assertLessEqual(len(contacts), 28)
        self.assertTrue(all(isinstance(c['home_address'], dict) for c in contacts))
        for key in ('healthy_desc', 'lifestyle_desc', 'economic_desc', 'work_desc', 'experience_desc', 'description'):
            self.assertTrue(person[key].strip(), key)
        locations_path = HERE / case / 'persona_list_locations.json'
        self.assertTrue(locations_path.exists(), 'real location sidecar missing')
        locations = json.loads(locations_path.read_text(encoding='utf-8'))
        self.assertEqual(len(locations), 1)
        self.assertTrue(locations[0], 'no grounded locations')
        if case == 'gb':
            self.assertEqual(person['home_address']['country_code'], 'GB')
            self.assertEqual(person['home_address']['timezone'], 'Europe/London')
            self.assertEqual(person['home_address']['currency'], 'GBP')
            for contact in contacts:
                self.assertTrue(contact['home_address'].get('country_code'), contact['name'])
                self.assertTrue(contact['birth_place'].get('country_code'), contact['name'])
            for point in locations[0]:
                self.assertTrue(point.get('country_code'))
                self.assertEqual(point.get('coordinate_system'), 'WGS-84')

    def test_cn(self):
        self.check_case('cn')

    def test_gb(self):
        self.check_case('gb')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output-root', type=Path, default=HERE)
    args, rest = parser.parse_known_args()
    HERE = args.output_root.resolve()
    unittest.main(argv=[sys.argv[0]] + rest, verbosity=2)
