import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from schedview.collect.resources import find_file_resources


class TestResources(unittest.TestCase):
    def test_find_file_resources(self):
        # Generate some test files
        test_file_names = ["foo/bar.txt", "foo/baz.txt", "foo/qux/moo.txt"]
        made_files = []
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            for file_name in test_file_names:
                file_path = temp_dir.joinpath(file_name)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                made_files.append(file_path.as_uri())
                with open(file_path, "w") as file_io:
                    file_io.write("Test content.")

            # Verify that we found exactly the files we made
            found_files = find_file_resources(temp_dir)

        self.assertListEqual(made_files, found_files)
