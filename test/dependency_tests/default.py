# ruff: noqa: F401

import sys
import unittest

import jbpy
import jbpy.core
import jbpy.image_data


class TestDefaultDeps(unittest.TestCase):
    def test_no_numpy_module(self):
        """Make sure numpy hasn't been imported"""
        self.assertNotIn("numpy", sys.modules)

    def test_graceful_handling(self):
        """Check interfaces that require numpy"""
        with self.assertRaises(ModuleNotFoundError) as exc:
            jbpy.image_data.write_uncompressed_image_data(None, 0, None, None, None)
        self.assertIn("numpy is required", str(exc.exception))

        with self.assertRaises(ModuleNotFoundError) as exc:
            jbpy.image_data.read_uncompressed_image_data(None, 0, None)
        self.assertIn("numpy is required", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
