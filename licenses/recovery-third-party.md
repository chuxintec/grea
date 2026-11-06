# Third-party notices

monkey distributes independent Python implementations adapted from GREA and the vendored Acorn parser. Their MIT license texts are included in `src/monkey/licenses/` in the source distribution and `monkey/licenses/` in the wheel:

- GREA adaptations: `GREA-MIT.txt`.
- Acorn 8.15.0: `ACORN-MIT.txt`.

Pillow12.2.0 and pypinyin0.55.0 (MIT, https://pypi.org/project/pypinyin/0.55.0/) are external runtime dependencies; texture2ddecoder1.0.6 is optional. Their distributions supply their own license texts. Node.js, Unity and Cocos Creator are external tools and are not bundled.

No private game source/assets, editor binaries or private tool implementations are distributed. Descriptions of independently implemented behavior do not extend this repository's license to external private tools. Algorithm provenance and limitations are recorded in `docs/PROVENANCE.md`.


## Cocos engine Layout geometry reference

The retired NativeFlowLayoutGroup implementation from the frozen dev3 tool is retained verbatim as an offline migration reference in `src/monkey/licenses/native-flow-reference.cs.txt`, together with `cocos-layout-mit.txt`. It is no longer emitted into generated production Assets. The original source reference is https://github.com/cocos/cocos-engine/blob/v3.8.7/cocos/ui/layout.ts . Copyright and license notices remain with the archived reference and in frozen history. This records provenance and artifact placement, not a legal determination.
