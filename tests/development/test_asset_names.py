import tempfile
import unittest
from pathlib import Path
from grea.development.asset_names import validate_destination
from grea.development.errors import BeaverError
from grea.development.io import write_json
from grea.development.batch import plan
from .test_adoption import candidate


class PortableDestinationTests(unittest.TestCase):
    def test_illegal_chars_in_filename_or_parent_and_device_names_are_rejected(self):
        names=['texture|compressed.png','bad<name.png','bad>name.png','bad:name.png','bad"name.png','bad\\name.png','bad?name.png','bad*name.png','bad\nname.png','bad\x00name.png','parent./image.png','parent /image.png','CON.png','aux.json','LPT1.png','COM².png']
        for name in names:
            with self.subTest(name=name),self.assertRaises(BeaverError) as error:
                validate_destination('Assets/Game/'+name)
            self.assertEqual(error.exception.code,'UNITY_DESTINATION_NAME')
            self.assertEqual(error.exception.location,'Assets/Game/'+name)

    def test_unicode_spaces_interior_and_device_prefixes_are_accepted(self):
        for name in ('普通图片.png','atlas compressed.png','concrete.png','COM10.png','folder/.hidden.png'):
            validate_destination('Assets/Game/'+name)

    def test_invalid_later_target_blocks_entire_plan_before_native_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=candidate(root/'Unity');spec=root/'spec.json';out=root/'plan'
            write_json(spec,dict(schemaVersion=2,operation='batch',steps=[dict(kind='asset.move',source='Assets/First.png',target='Assets/Game/First.png'),dict(kind='asset.move',source='Assets/Second.png',target='Assets/Game/texture|compressed.png')]))
            with self.assertRaises(BeaverError) as error:plan(project,spec,out)
            self.assertEqual(error.exception.code,'UNITY_DESTINATION_NAME');self.assertFalse(out.exists())

    def test_unity_file_and_directory_move_destinations_are_preflighted(self):
        from grea.development.unity import validate_spec
        for field in ('moves','directoryMoves'):
            with self.subTest(field=field),self.assertRaises(BeaverError) as error:
                validate_spec(dict(schemaVersion=1,operation='assets.move',**{field:[dict(source='Assets/Legacy',target='Assets/Game/bad|name')]}))
            self.assertEqual(error.exception.code,'UNITY_DESTINATION_NAME')

    def test_invalid_legacy_source_may_have_an_explicit_legal_target(self):
        from grea.development.batch import validate
        validate(dict(schemaVersion=2,operation='batch',steps=[dict(kind='asset.move',source='Assets/texture|compressed.png',target='Assets/Game/texture-compressed.png')]))

if __name__=='__main__':unittest.main()
