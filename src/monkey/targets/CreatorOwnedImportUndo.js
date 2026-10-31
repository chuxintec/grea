'use strict';

// Imported by the Creator editor extension only. This module deliberately
// depends on the Undo diagnostics helper, while the helper never imports it.
let undoDiagnostics;
try { undoDiagnostics = require('./editor-undo-diagnostics.js'); }
catch (_) { undoDiagnostics = require('./CreatorEditorUndoDiagnostics.js'); }

function noScope(reason, details = {}) {
    const summary = () => ({installed: false, reason, ...details});
    return {
        installed: false, reason, summary,
        registerOwnedRoot() { return {registered: false, reason}; },
        registerOwnedObject() { return {registered: false, reason}; },
        retireDestroyedRoot() { return {retired:false,reason}; },
        finish() { return summary(); },
    };
}

function resolveManager(cce) {
    try {
        const manager = cce && cce.SceneFacadeManager && cce.SceneFacadeManager._facadeFSM &&
            cce.SceneFacadeManager._facadeFSM.generalSceneFacade &&
            cce.SceneFacadeManager._facadeFSM.generalSceneFacade._undoMgr;
        if (!manager) return {manager: null, reason: 'general-scene-undo-manager-unavailable'};
        const prototype = Object.getPrototypeOf(manager);
        const ctor = prototype && prototype.constructor;
        if (!ctor || ctor.name !== 'SceneUndoManager')
            return {manager: null, reason: 'general-scene-undo-manager-class-mismatch'};
        if (typeof manager.record !== 'function' || !Array.isArray(manager.records))
            return {manager: null, reason: 'general-scene-undo-manager-record-shape-mismatch'};
        const dumpMap = manager._uuidDumpMap;
        if (!dumpMap || typeof dumpMap !== 'object' || Array.isArray(dumpMap))
            return {manager: null, reason: 'general-scene-undo-manager-dump-shape-mismatch'};
        return {manager, reason: null};
    } catch (error) {
        return {manager: null, reason: 'general-scene-undo-manager-inspection-failed',
            errorName: String(error && error.name || 'Error').slice(0, 96)};
    }
}

function makeResolver(cce) {
    return uuid => {
        if (typeof uuid !== 'string' || !uuid) return null;
        let value = null;
        if (cce && cce.Node && typeof cce.Node.query === 'function') value = cce.Node.query(uuid);
        if (value) return value;
        if (cce && cce.Component && typeof cce.Component.query === 'function') value = cce.Component.query(uuid);
        return value || null;
    };
}

function makeValidityCallback(requireFn) {
    if (typeof requireFn !== 'function') return null;
    try {
        const cc = requireFn('cc');
        if (!cc || typeof cc.isValid !== 'function') return null;
        return (object, strict) => cc.isValid(object, strict);
    } catch (_) { return null; }
}

function begin(cce, realm = globalThis, requireFn = require, options = {}) {
    const found = resolveManager(cce);
    if (!found.manager) return noScope(found.reason);
    if (typeof cce?.Node?.query !== 'function' || typeof cce?.Component?.query !== 'function')
        return noScope('creator-node-component-query-api-unavailable');

    const probe = undoDiagnostics.install({realm, requireFn, recordOnly: true,
        maxUndoMethods: options.maxUndoMethods || 32,
        maxUndoMethodSourceLength: options.maxUndoMethodSourceLength || 2500});
    if (!probe.installed || !probe.ownedRecordIsolationAvailable) {
        try { probe.uninstall(); } catch (_) {}
        return noScope(probe.reason || 'creator-owned-record-hook-unavailable',
            {diagnostics: probe.summary ? probe.summary() : null});
    }

    let scope;
    const isValidObject = makeValidityCallback(requireFn);
    try { scope = probe.beginOwnedImportScope(found.manager, makeResolver(cce), isValidObject); }
    catch (error) {
        try { probe.uninstall(); } catch (_) {}
        return noScope('creator-owned-record-scope-rejected', {
            errorName: String(error && error.name || 'Error').slice(0, 96),
            diagnostics: probe.summary ? probe.summary() : null,
        });
    }

    let closed = false;
    const summary = () => ({installed: true, managerClass: 'SceneUndoManager',
        scope: scope.summary(), diagnostics: probe.summary()});
    return {
        installed: true,
        registerOwnedRoot(root) { return closed ? {registered: false, reason: 'scope-closed'} : scope.registerOwnedRoot(root); },
        registerOwnedObject(object) { return closed ? {registered: false, reason: 'scope-closed'} : scope.registerOwnedObject(object); },
        retireDestroyedRoot(root, entries) { return closed ? {retired:false,reason:'scope-closed'} : scope.retireDestroyedOwnedRoot(root, entries); },
        summary,
        finish() {
            if (closed) return summary();
            let result;
            try { result = scope.finish(); }
            finally {
                closed = true;
                probe.uninstall();
            }
            return {installed: true, managerClass: 'SceneUndoManager', scope: result,
                diagnostics: probe.summary()};
        },
    };
}

let activeScope = null;
function start(cce, realm = globalThis, requireFn = require) {
    if (activeScope) throw new Error('CREATOR_OWNED_IMPORT_UNDO_SCOPE_ALREADY_ACTIVE');
    const scope = begin(cce, realm, requireFn);
    if (!scope.installed) throw new Error('CREATOR_OWNED_IMPORT_UNDO_UNAVAILABLE:' + scope.reason);
    activeScope = scope;
    return scope.summary();
}
function registerRoot(root) {
    return activeScope ? activeScope.registerOwnedRoot(root) : {registered: false, reason: 'no-owned-import'};
}
function retireDestroyedRoot(root, entries) {
    return activeScope ? activeScope.retireDestroyedRoot(root, entries) : {retired:false,reason:'no-owned-import'};
}
function finish() {
    if (!activeScope) return {installed: false, reason: 'no-owned-import'};
    const scope = activeScope;
    activeScope = null;
    return scope.finish();
}
module.exports = {begin, start, registerRoot, retireDestroyedRoot, finish};
