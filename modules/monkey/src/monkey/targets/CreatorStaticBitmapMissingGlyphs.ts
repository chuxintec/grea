// Typed provenance for a native Creator BitmapFont Label whose source text
// contains code units absent from the source fontDefDictionary. The cc.Label
// and cc.BitmapFont remain the actual renderer and font asset.
import { _decorator, BitmapFont, CCInteger, CCString, Component, Label } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('MonkeyStaticBitmapMissingGlyphs')
export class MonkeyStaticBitmapMissingGlyphs extends Component {
    @property public sourceComponentId = '';
    @property public sourceNodeId = '';
    @property public sourceFontId = '';
    @property public sourceText = '';
    @property public displayText = '';
    @property public sourceEnabled = false;
    @property public missingGlyphsAreVisibleTextRecovered = false;
    @property public policy = 'cocos24-bitmap-missing-glyph-skip-v1';
    @property public sourceCodeEvidence = 'cocos2d/core/renderer/utils/label/bmfont.js:235';
    @property({ type: [CCInteger] }) public sourceGlyphUnicode: number[] = [];
    @property({ type: [CCInteger] }) public missingGlyphUnicode: number[] = [];
    @property({ type: Label }) public targetLabel: Label | null = null;
    @property({ type: BitmapFont }) public targetFont: BitmapFont | null = null;
}
