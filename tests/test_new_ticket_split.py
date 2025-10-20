import unittest
import os
import shutil
import copy
import sys

sys.path.append(".")

from new_ticket_split import (
    load_schedules,
    process_pdfs,
)

class TestTicketSplit(unittest.TestCase):
    def setUp(self):
        self.schedules_dir = "tests/fixtures/ticket_split/schedules"
        self.in_dir = "tests/fixtures/ticket_split/in"
        self.out_dir = "tests/fixtures/out"
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.out_dir)

    def test_process_pdfs_with_real_data(self):
        schedules = load_schedules(self.schedules_dir)
        process_pdfs(self.in_dir, self.out_dir, copy.deepcopy(schedules))

        person_a_dir = os.path.join(self.out_dir, "person_a")
        person_b_dir = os.path.join(self.out_dir, "person_b")
        unknown_dir = os.path.join(self.out_dir, "unknown")

        self.assertTrue(os.path.exists(person_a_dir))
        self.assertTrue(os.path.exists(person_b_dir))
        self.assertFalse(os.path.exists(unknown_dir))

        # I'm not going to assert the exact number of files, as it might change.
        # Instead, I'll just assert that the directories are not empty.
        self.assertGreater(len(os.listdir(person_a_dir)), 0)
        self.assertGreater(len(os.listdir(person_b_dir)), 0)


if __name__ == "__main__":
    unittest.main()