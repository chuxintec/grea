"""Actual imported kind -> monkey-project/2.0.0 type folder (PROJECT-SPEC 4.2). Extensions only break ties."""
IMAGE={'.png','.jpg','.jpeg','.webp','.tga','.psd','.bmp'}
AUDIO={'.mp3','.ogg','.wav','.m4a','.aac'}
VIDEO={'.mp4','.webm','.mov'}
MODEL={'.fbx','.obj','.dae','.blend'}
SHADER={'.shader','.hlsl','.cginc','.glsl','.shadergraph','.effect'}
MUSIC_WORDS={'bgm','music','musics','bg_music','bgmusic'}
VOICE_WORDS={'voice','voices','vo','dub'}
SFX_WORDS={'sfx','se','sound','sounds','effect_sound','audioeffect'}
STRING_STEMS={'label','labels','lang','language','languages','i18n','text','texts','strings','localization','locale'}
KINDS={'sprite':'sprite','cc.SpriteFrame':'sprite','bitmap-atlas':'font','cc.TTFFont':'font','ttf':'font','font':'font','font-asset':'font',
    'bitmap':'font','cc.BitmapFont':'font','cc.Prefab':'prefab','prefab':'prefab','cc.AnimationClip':'animation','animation':'animation',
    'controller':'animation','material':'material','cc.Material':'material','spine':'spine','sp.SkeletonData':'spine','scene':'scene',
    'cc.SceneAsset':'scene','effect':'effect','atlas':'atlas','cc.Texture2D':'texture','texture':'texture','data':'data','model':'model',
    'shader':'shader','video':'video','config':'config','strings':'strings'}


def audio_category(folders,stem):
    """Music/Sfx/Voice from the first remaining folder or the stem prefix; the category folder itself is dropped."""
    if folders:
        first=folders[0].lower()
        for words,kind in ((MUSIC_WORDS,'music'),(VOICE_WORDS,'voice'),(SFX_WORDS,'sfx')):
            if first in words:return kind,folders[1:]
    head=str(stem or '').lower().split('_')[0]
    if head in MUSIC_WORDS or str(stem or '').lower().startswith('bgm'):return 'music',folders
    if head in VOICE_WORDS:return 'voice',folders
    return 'sfx',folders


def is_strings(stem,locale):
    return bool(locale) or str(stem or '').lower() in STRING_STEMS


def target_type(kind,suffix):
    """Type key for an object. Audio/config refinement happens in the planner with source folders."""
    suffix=(suffix or '').lower()
    if kind=='cc.AudioClip' or suffix in AUDIO:return 'audio'
    if kind=='cc.JsonAsset':return 'json'
    if kind in KINDS:return KINDS[kind]
    if suffix=='.json':return 'json'
    if suffix in IMAGE:return 'texture'
    if suffix in VIDEO:return 'video'
    if suffix in MODEL:return 'model'
    if suffix in SHADER:return 'shader'
    if suffix in ('.ttf','.otf','.fnt'):return 'font'
    if suffix=='.prefab':return 'prefab'
    if suffix=='.anim':return 'animation'
    return 'data'
