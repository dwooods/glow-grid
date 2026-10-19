"""Firmware 20: SCHED <on HHMM> <off HHMM> switches the panel on and off at set times (local time, America/Los_Angeles), learned over NTP.
Runs the compiled firmware simulator from test_gg.py:   python3 -m unittest tests.test_sched -v   (from the c3 folder)

The simulator's clock starts at $GG_FAKE_EPOCH and runs with the test's $GG_TIME_SCALE; the stand-in configTzTime() records the zone
and time servers in the Wi-Fi log, and the zone string is checked against the real C library here.
"""
import calendar
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_gg as _tg  # noqa: E402

sample_frames = _tg.sample_frames
TZ = "PST8PDT,M3.2.0,M11.1.0"


def la_epoch(y, mo, d, h, mi, s=0, dst=True):
    """UNIX time of a Los Angeles wall-clock moment (the offset is passed in; dst=True is UTC-7, else UTC-8)."""
    return calendar.timegm((y, mo, d, h, mi, s)) + (7 if dst else 8) * 3600


class Sched(_tg.Board):
    def boot(self, epoch=None, scale="1"):
        """Fresh board on Wi-Fi with the clock set (epoch=None: no time yet, as before the first NTP answer)."""
        self.extra_env = {"GG_TIME_SCALE": scale}
        if epoch is not None:
            self.extra_env["GG_FAKE_EPOCH"] = str(epoch)
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        self.board.put(self.write_gg("lamp", sample_frames(91, 1)))
        return self.board

    def reboot(self):
        return self.restart()

    def panel(self, board=None):
        for tok in (board or self.board).simple("INFO").split():
            if tok.startswith("panel="):
                return tok[6:]

    def info(self, key, board=None):
        for tok in (board or self.board).simple("INFO").split():
            if tok.startswith(key + "="):
                return tok[len(key) + 1:]

    def test_commands_and_bad_input(self):
        self.boot()
        self.assertEqual(self.info("schedule"), "off")
        self.assertEqual(self.board.simple("SCHED 0700 2000"), "OK schedule 0700-2000")
        self.assertEqual(self.info("schedule"), "0700-2000")
        for bad in ("SCHED", "SCHED 0700", "SCHED 07:00 20:00", "SCHED 0700 0700", "SCHED 2400 0100", "SCHED 0760 0800", "SCHED abcd 2000", "SCHED 700 2000"):
            self.board.send(bad)
            with self.assertRaisesRegex(RuntimeError, "usage"):
                self.board.expect(["OK"])
        self.assertEqual(self.info("schedule"), "0700-2000", "a refused value changes nothing")
        self.assertEqual(self.board.simple("SCHED off"), "OK schedule off")
        self.assertEqual(self.info("schedule"), "off")

    def test_no_time_means_the_schedule_waits(self):
        board = self.boot(epoch=None)
        self.assertEqual(board.simple("SCHED 0700 2000"), "OK schedule 0700-2000")
        time.sleep(2.3)
        self.assertEqual(self.info("clock"), "-")
        self.assertEqual(self.panel(), "on", "without a clock the panel is left alone")

    def test_clock_zone_and_ntp_start(self):
        # 2026-10-18 12:34 PDT and 2026-12-01 12:34 PST: the zone string gives the right local time in both seasons (checked with the real C library)
        for stamp, (y, mo, d), dst in (("1234", (2026, 10, 18), True), ("1234", (2026, 12, 1), False)):
            out = subprocess.run(["date", "-d", f"@{la_epoch(y, mo, d, 12, 34, dst=dst)}", "+%H%M"], env=dict(os.environ, TZ=TZ), capture_output=True, text=True).stdout.strip()
            self.assertEqual(out, stamp)
        board = self.boot(epoch=la_epoch(2026, 12, 1, 12, 34, dst=False))
        time.sleep(1.5)
        self.assertEqual(self.info("clock"), "1234")
        self.assertIn(f"ntp {TZ} pool.ntp.org", self.wifi_log())
        board = self.boot(epoch=la_epoch(2026, 10, 18, 12, 34, dst=True))
        time.sleep(1.5)
        self.assertEqual(self.info("clock"), "1234", "daylight saving time in October")

    def test_window_applies_at_once_then_follows_the_edges(self):
        # 19:59:50 inside 07:00-20:00; time runs 20x so the 20:00 edge comes after about half a second
        board = self.boot(epoch=la_epoch(2026, 10, 18, 19, 59, 50), scale="20")
        self.assertEqual(board.simple("SCHED 0700 2000"), "OK schedule 0700-2000")
        time.sleep(1.5)
        self.assertEqual(self.panel(), "off", "it crossed 20:00 and switched off")
        # a manual On after that holds until the next change (07:00 tomorrow is far away at this speed)
        self.assertEqual(board.simple("ON"), "OK panel on")
        time.sleep(1.5)
        self.assertEqual(self.panel(), "on", "a manual On holds until the next scheduled change")

    def test_saving_the_schedule_applies_the_window_state_immediately(self):
        board = self.boot(epoch=la_epoch(2026, 10, 18, 22, 0, 0))     # 22:00, outside 07:00-20:00
        self.assertEqual(self.panel(), "on")
        board.simple("SCHED 0700 2000")
        time.sleep(1.5)
        self.assertEqual(self.panel(), "off", "outside the window the panel goes dark when the schedule is saved")
        board.simple("SCHED 2100 2300")                                # now 22:00 is inside
        time.sleep(1.5)
        self.assertEqual(self.panel(), "on")

    def test_overnight_window(self):
        board = self.boot(epoch=la_epoch(2026, 10, 18, 23, 30, 0))
        board.simple("SCHED 2200 0600")
        time.sleep(1.5)
        self.assertEqual(self.panel(), "on", "23:30 is inside 22:00-06:00")
        board.simple("SCHED 0600 2200")
        time.sleep(1.5)
        self.assertEqual(self.panel(), "off", "the opposite window puts 23:30 outside")

    def test_survives_a_power_cycle_and_applies_at_power_up(self):
        board = self.boot(epoch=la_epoch(2026, 10, 18, 22, 0, 0))
        board.simple("SCHED 0700 2000")
        board.simple("ON")                      # manual On outside the window...
        board = self.reboot()                   # ...then a power cycle: the saved schedule decides again once the time is known
        self.assertEqual(self.info("schedule", board), "0700-2000")
        time.sleep(2.0)
        self.assertEqual(self.panel(board), "off")

    def test_command_names_fit_the_serial_buffer(self):
        # doCommand() reads the name with %7s into cmd[8]: a longer name is cut and never matches (SCHEDULE became SCHEDUL once)
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "c3_player", "c3_player.ino")).read()
        body = src[src.index("void doCommand(char* line)"):src.index("void handleSerial()")]
        size = int(re.search(r"char cmd\[(\d+)\]", body).group(1))
        self.assertIn("%" + str(size - 1) + "s", body, "the scanf width must be one less than the buffer")
        names = re.findall(r'c == "([A-Z0-9]+)"', body)
        self.assertGreaterEqual(len(names), 12, "the command list was not found: update this test")
        for n in names:
            self.assertLessEqual(len(n), size - 1, n + " does not fit the command buffer")
        self.assertIn("SCHED", names)
        self.boot()
        self.board.send("SCHEDULE 0700 2000")      # the long spelling is simply unknown, and changes nothing
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            self.board.expect(["OK"])
        self.assertEqual(self.info("schedule"), "off")

    def test_spring_forward_does_not_skip_an_edge(self):
        # 2026-03-08 01:59:55 PST -> 03:00 PDT: a window that opens at 02:30 (an hour that does not exist) still opens
        board = self.boot(epoch=la_epoch(2026, 3, 8, 1, 59, 55, dst=False), scale="20")
        board.simple("SCHED 0230 0600")
        time.sleep(0.2)
        self.assertEqual(self.panel(), "off", "01:59 is outside 02:30-06:00")
        time.sleep(1.5)
        self.assertEqual(self.info("clock"), "0300", "the clock jumped over the missing hour (30 s of fake time after 01:59:55)")
        self.assertEqual(self.panel(), "on", "the window is open at 03:00")

    def test_fall_back_repeated_hour(self):
        # 2026-11-01 01:59:55 PDT -> 01:00 PST again: the repeated hour is read as clock time, so 01:00-01:30 opens a second time
        board = self.boot(epoch=la_epoch(2026, 11, 1, 1, 59, 55, dst=True), scale="20")
        board.simple("SCHED 0100 0130")
        time.sleep(0.2)
        self.assertEqual(self.panel(), "off", "01:59 is outside 01:00-01:30")
        time.sleep(1.5)
        self.assertEqual(self.info("clock"), "0100", "the clock went back an hour")
        self.assertEqual(self.panel(), "on", "the window opens again in the repeated hour")

    def test_over_http(self):
        self.boot(epoch=la_epoch(2026, 10, 18, 12, 0, 0))
        self.http_base()
        self.assertEqual(self.http("POST", "/sched?v=0700-2000")[2], b"OK schedule 0700-2000\n")
        self.assertEqual(self.info("schedule"), "0700-2000")
        self.assertEqual(self.http("POST", "/sched?v=off")[2], b"OK schedule off\n")
        self.assertEqual(self.http("POST", "/sched?v=0700")[0], 400)
        for bad in ("0700-0700", "2400-0100", "0760-0800", "abcd-2000", "07:00-20:00", "0700-", "-2000", ""):
            self.assertEqual(self.http("POST", "/sched?v=" + bad)[0], 400, bad)
        self.assertEqual(self.info("schedule"), "off", "refused values change nothing")
        st, hd, out = self.http("POST", "/sched?v=0700-2000", b"", {"Origin": "https://evil.example"})
        self.assertEqual((st, out), (403, b"ERR not allowed from this page or address\n"))
        self.assertEqual(self.info("schedule"), "off")


for _n in dir(_tg.Board):                 # inherit the harness, not test_gg's own tests
    if _n.startswith("test_"):
        setattr(Sched, _n, None)


if __name__ == "__main__":
    unittest.main()
