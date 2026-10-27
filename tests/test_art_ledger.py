import json
import unittest
from pathlib import Path


class ArtLedgerTests(unittest.TestCase):
    def test_optional_provenance_does_not_replace_existing_art_identity(self):
     from grea.change_contracts import validate_ledger
     ledger=json.loads((Path(__file__).resolve().parents[1]/'plugin/skills/grea-develop/assets/art-ledger.example.json').read_text())
     validate_ledger(ledger)
     ledger['records'][0]['provenance']=dict(creator='owned-fixture',license='unknown',restrictions=['not cleared for distribution'],generation_tool='not used')
     validate_ledger(ledger)
     del ledger['records'][0]['design_source']
     with self.assertRaises(ValueError):validate_ledger(ledger)


if __name__ == '__main__':
    unittest.main()
