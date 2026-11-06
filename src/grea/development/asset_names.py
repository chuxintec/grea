"""Portable destination names; imported source names are never silently rewritten."""
from .errors import fail

# Windows file/directory rules are applied on every host for portable Unity assets.
# https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
_FORBIDDEN = frozenset('<>:"\\|?*')
_DEVICES = frozenset(('con','prn','aux','nul',*(f'com{x}' for x in '123456789¹²³'),*(f'lpt{x}' for x in '123456789¹²³')))


def validate_destination(path):
    if not isinstance(path,str):
        fail('UNITY_DESTINATION_NAME',str(path),'Destination must be an explicit asset path')
    for component in path.split('/'):
        if any(c in _FORBIDDEN or ord(c)<32 or ord(c)==127 for c in component):
            fail('UNITY_DESTINATION_NAME',path,'Destination component contains a nonportable character: '+repr(component))
        if component.endswith((' ','.')):
            fail('UNITY_DESTINATION_NAME',path,'Destination component ends with a space or dot: '+repr(component))
        if component.split('.',1)[0].casefold() in _DEVICES:
            fail('UNITY_DESTINATION_NAME',path,'Destination component is a reserved device name: '+repr(component))
