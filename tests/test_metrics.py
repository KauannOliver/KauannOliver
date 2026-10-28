import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('metrics', Path(__file__).resolve().parents[1] / 'scripts/update_metrics.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)

def repo(name, **overrides):
    return dict(name=name, owner={'login': 'KauannOliver'}, private=False, fork=False,
                stargazers_count=3, forks_count=1, language='Python', **overrides)

class MetricsTests(unittest.TestCase):
    def test_public_owned_nonfork_totals(self):
        data = [repo('a'), {**repo('b'), 'private': True}, {**repo('c'), 'fork': True}]
        result = metrics.collect(lambda _: data)
        self.assertEqual((result['repositories'], result['stars'], result['forks']), (1, 3, 1))
        self.assertEqual(result['primary_languages'], {'Python': 1})

    def test_pagination(self):
        pages = [[repo(str(i)) for i in range(100)], [repo('last')]]
        result = metrics.collect(lambda _: pages.pop(0))
        self.assertEqual(result['repositories'], 101)

    def test_collection_failure_preserves_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'assets').mkdir()
            asset = root / 'assets/overview.svg'
            asset.write_text('last valid', encoding='utf-8')
            with self.assertRaises(ValueError):
                metrics.update(lambda _: [], root)
            self.assertEqual(asset.read_text(encoding='utf-8'), 'last valid')

    def test_unchanged_metrics_do_not_rewrite_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metrics.update(lambda _: [repo('a')], root)
            asset = root / 'assets/metrics.json'
            before = asset.stat().st_mtime_ns
            metrics.update(lambda _: [repo('a')], root)
            self.assertEqual(asset.stat().st_mtime_ns, before)

    def test_invalid_numbers_and_duplicate_repos_are_rejected(self):
        with self.assertRaises(ValueError):
            metrics.collect(lambda _: [{**repo('a'), 'forks_count': -1}])
        with self.assertRaises(ValueError):
            metrics.collect(lambda _: [repo('a'), repo('a')])

if __name__ == '__main__':
    unittest.main()
