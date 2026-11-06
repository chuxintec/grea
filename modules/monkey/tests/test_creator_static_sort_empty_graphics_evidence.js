'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'src/monkey/targets/CreatorStaticSortQueueProxy.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const begin = source.indexOf('const CREATOR_BUILTIN_GRAPHICS_MATERIAL_UUID');
const marker = '\nfunction refId';
const end = source.indexOf(marker, begin);
assert.ok(begin >= 0 && end > begin && source.includes('export function creatorStaticEmptyGraphicsEvidence', begin), 'production proof function is present');

const compilerPath = '/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/resources/3d/engine/node_modules/typescript';
const ts = require(compilerPath);
const functionSource = source.slice(begin, end);
const compiled = ts.transpileModule(functionSource, {compilerOptions: {
    target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS,
}}).outputText;
const moduleObject = {exports: {}};
new Function('exports', 'module', compiled)(moduleObject.exports, moduleObject);
const proof = moduleObject.exports.creatorStaticEmptyGraphicsEvidence;
assert.equal(typeof proof, 'function');

const material = 'f0416e68-0200-4b77-a926-4f9d16e494da';
const effect = '1c02ae6f-4492-4915-b8f8-7492a3b1e4cd';
assert.equal(proof(false, 0, material, effect, false, false), true,
    'an empty disabled Graphics may have no transient renderer material instance');
assert.equal(proof(false, 0, material, effect, true, true), true,
    'a present renderer material is accepted only when it is the persistent custom material');
assert.equal(proof(false, 0, material, effect, true, false), false,
    'a conflicting active renderer material is rejected');
assert.equal(proof(true, 0, material, effect, false, false), false,
    'enabled Graphics cannot use the empty disabled-carrier rule');
assert.equal(proof(false, 1, material, effect, false, false), false,
    'non-empty drawing paths cannot use the empty disabled-carrier rule');
assert.equal(proof(false, 0, 'wrong-material', effect, false, false), false,
    'wrong custom material identity is rejected');
assert.equal(proof(false, 0, material, 'wrong-effect', false, false), false,
    'wrong effect identity is rejected');

console.log('Creator empty Graphics evidence contract checks passed');
