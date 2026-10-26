import contextlib
import io
import json
import unittest
from unittest.mock import patch

from beaver.cli import main


class MigrationResultContractTests(unittest.TestCase):
    def invoke(self, result):
        output = io.StringIO()
        argv = ['server', 'migration-apply', '--project', '/candidate', '--plan', '/plan',
                '--compose', '/compose', '--project-name', 'beaver-go-contract',
                '--owner', 'server', '--expected-state', '0' * 64]
        with patch('beaver.cli.dispatch', return_value=result), contextlib.redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def test_stale_database_state_is_nonzero_and_has_no_write_claim(self):
        code, result = self.invoke(dict(status='stale_plan', execution='not_run'))
        self.assertEqual(code, 3)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['actualChanges'], [])

    def test_unknown_ddl_result_retains_possible_mutation(self):
        code, result = self.invoke(dict(status='execution_unknown_or_partial',
                                        execution='attempted; inspect before retry',
                                        database='beaver_go_example_server'))
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['actualChanges'][0]['owner'], 'server')
        self.assertEqual(result['actualChanges'][0]['status'], 'execution_unknown_or_partial')

    def test_verified_migration_exposes_database_effect(self):
        code, result = self.invoke(dict(status='applied', execution='verified_migration_ledger_and_schema_state',
                                        database='beaver_go_example_server',
                                        stateBeforeSha256='1' * 64, stateAfterSha256='2' * 64))
        self.assertEqual(code, 0)
        self.assertEqual(result['actualChanges'][0]['stateAfterSha256'], '2' * 64)


if __name__ == '__main__':
    unittest.main()
