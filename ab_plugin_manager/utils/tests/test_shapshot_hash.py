import hashlib
import unittest
from typing import Any

from ab_plugin_manager.utils.snapshot_hash import snapshot_hash, make_stable_hash_fn


class SnapshotHashTest(unittest.TestCase):
    def test_hash_dict(self):
        self.assertEqual(
            snapshot_hash({'foo': {'bar': 42}}),
            snapshot_hash({'foo': {'bar': 42}}),
        )

    def test_hash_list(self):
        self.assertEqual(
            snapshot_hash([[42, ], 'foo']),
            snapshot_hash([[42, ], 'foo']),
        )

    def test_hash_difference(self):
        self.assertNotEqual(
            snapshot_hash({'foo': [{}, {'bar': 'baz'}]}),
            snapshot_hash({'foo': [{}, {'bar': 'buz'}]}),
        )

    def test_hash_stable(self):
        self.assertEqual(
            snapshot_hash({'foo': ['bar']}),
            37133252672926233695994809505992682454371366431544797706692903489691835070470
        )

        self.assertEqual(
            snapshot_hash({'foo': ['bar']}, make_stable_hash_fn(hashlib.md5)),
            59139101794391242901173294103234746387
        )

    def test_hash_pydantic_model(self):
        from pydantic import BaseModel

        class M(BaseModel):
            x: int
            d: dict[str, Any]

        self.assertEqual(
            snapshot_hash(M(x=1, d={'z': 2})),
            snapshot_hash(M(x=1, d={'z': 2})),
        )

        self.assertNotEqual(
            snapshot_hash(M(x=1, d={'z': 2})),
            {'x': 1, 'd': {'z': 2}},
        )

        self.assertNotEqual(
            snapshot_hash(M(x=2, d={'z': 2})),
            snapshot_hash(M(x=1, d={'z': 2})),
        )
        self.assertNotEqual(
            snapshot_hash(M(x=1, d={'z': 2})),
            snapshot_hash(M(x=1, d={'Z': 2})),
        )


if __name__ == '__main__':
    unittest.main()
