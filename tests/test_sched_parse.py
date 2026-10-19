"""The editor's schedule time fields: schedParse() in web/js/board.js turns what is typed into HHMM, or '' when it is not a 24-hour time.
A wrong value that got through would reach the board; a right one that is refused would block a valid schedule.

Run from the repo root:  python3 -m unittest tests.test_sched_parse -v   (needs Node)
"""
import json, os, subprocess, unittest

HERE = os.path.dirname(os.path.abspath(__file__))

GOOD = {'07:00': '0700', '7:05': '0705', '0705': '0705', '00:00': '0000', '0:00': '0000', '23:59': '2359', '2359': '2359', '12:30': '1230',
        ' 7:05 ': '0705', '19:07': '1907', '1907': '1907', '09:09': '0909', '705': '0705'}   # three digits are read as H:MM
BAD = ['', ' ', 'abc', '24:00', '2400', '25:00', '12:60', '1260', '7:5', '7', '07:0', '1:2:3', '07-00', '07:00pm', '-1:00', '07:000', '١٢:٣٠', 'null']


def run(values):
    out = subprocess.run(['node', os.path.join(HERE, 'sched_parse.js'), json.dumps(values)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


class SchedParse(unittest.TestCase):
    def test_good_times_become_hhmm(self):
        got = run(list(GOOD))
        for text, hhmm in zip(GOOD, got):
            self.assertEqual(hhmm, GOOD[text], repr(text))

    def test_everything_else_is_refused(self):
        got = run(BAD)
        for text, hhmm in zip(BAD, got):
            self.assertEqual(hhmm, '', repr(text))

    def test_non_strings_are_refused(self):
        self.assertEqual(run([None, True, {}, []]), ['', '', '', ''])


if __name__ == '__main__':
    unittest.main()
