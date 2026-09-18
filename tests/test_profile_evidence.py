"""Complete captures only; never treat an arbitrary sampler error as success."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from profile_evidence import assess_python_capture


class PythonCaptureTests(unittest.TestCase):
    def assess(self, rc=0, err='', raw=None, receipt_errors=(), stdout=None):
        return assess_python_capture(rc, stdout or 'Stopped sampling because process exited\nWrote raw flamegraph data. Samples: 10 Errors: 0',
            err, raw or 'main;run_measured_calls (/actual/workload.py:123);advance 8\nmain;importlib 2\n',
            receipt_errors, '/actual/workload.py')

    def test_success_separates_measured_stacks(self):
        result, roi = self.assess()
        self.assertTrue(result['usable'])
        self.assertEqual(result['measured_sample_count'], 8)
        self.assertEqual(result['excluded_sample_count'], 2)
        self.assertNotIn('importlib', roi)

    def test_known_child_exit_requires_complete_validated_capture(self):
        result, _ = self.assess(1, 'Error: No child process (os error 10)\n')
        self.assertTrue(result['usable'])
        self.assertEqual(result['returncode'], 1)
        self.assertTrue(result['warning'])
        for errors in (['partial workload'], ['source hash mismatch']):
            self.assertFalse(self.assess(1, 'Error: No child process (os error 10)', receipt_errors=errors)[0]['usable'])

    def test_other_errors_or_corrupt_samples_are_rejected(self):
        for rc, err in ((1, 'permission denied'), (2, 'Error: No child process (os error 10)'),
                        (1, 'Error: No child process (os error 10)\nOther failure')):
            self.assertFalse(self.assess(rc, err)[0]['usable'])
        for raw in ('main;run_measured_calls (/wrong/workload.py:123) 10\n',
                    'main;run_measured_calls (/actual/workload.py:123) -1\n',
                    'main;run_measured_calls (/actual/workload.py:123) 9\n'):
            self.assertFalse(self.assess(raw=raw)[0]['usable'])
        self.assertFalse(self.assess(stdout='Samples: 10 Errors: 2')[0]['usable'])


if __name__ == '__main__':
    unittest.main()
