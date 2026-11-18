import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import * as Ecs from '../base/extensions/pop-shell@system76.com/ecs.js';
import * as NodeMod from '../base/extensions/pop-shell@system76.com/node.js';
import {
    exception_applies,
    literal_rule_field,
} from '../base/extensions/pop-shell@system76.com/float_pattern.js';
import { WobblyModel } from '../base/extensions/compiz-windows-effect@hermes83.github.com/src/effects/wobbly_model.js';
import {
    safe_speedup_divider,
    settings_for_effect,
    DEFAULT_SPEEDUP_FACTOR,
} from '../base/extensions/compiz-windows-effect@hermes83.github.com/settings_data.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const pop = join(root, 'base/extensions/pop-shell@system76.com');
const compiz = join(root, 'base/extensions/compiz-windows-effect@hermes83.github.com');
const flourish = join(root, 'base/extensions/flourish@orsso.github.io');

function assertFloatLiterals() {
    const titles = ['Compile (', 'Compile [draft]', 'file.txt', 'a+b', 'C:\\Program Files\\App'];
    const impostors = {
        'Compile (': 'Compile X',
        'Compile [draft]': 'Compile d',
        'file.txt': 'fileXtxt',
        'a+b': 'aaab',
        'C:\\Program Files\\App': 'C:Program FilesApp',
    };
    for (const title of titles) {
        const stored = {
            class: literal_rule_field('org.gnome.Console'),
            title: literal_rule_field(title),
        };
        assert.equal(exception_applies([stored], 'org.gnome.Console', title), true, title);
        assert.equal(exception_applies([stored], 'org.gnome.Console', impostors[title]), false, title);
        assert.equal(exception_applies([stored], 'orgXgnomeXConsole', title), false, title);
    }

    assert.equal(
        exception_applies([{ class: 'org.gnome.Console', title: 'Compile (' }], 'org.gnome.Console', 'Compile ('),
        true,
    );
    assert.equal(
        exception_applies([{ class: 'ibus-.*' }], 'ibus-daemon', 'x'),
        true,
    );
    assert.equal(
        exception_applies([{ class: 'Steam', title: '^.*(Guard|Login).*' }], 'Steam', 'Steam Guard'),
        true,
    );

    for (const name of ['config.js', 'floating_exceptions/config.js']) {
        const source = readFileSync(join(pop, name), 'utf8');
        assert.match(source, /literal_rule_field\(wmclass/);
        assert.match(source, /literal_rule_field\(title\)/);
        assert.match(source, /exception_applies\(/);
        assert.doesNotMatch(source, /new RegExp\(rule\./);
    }
}

function assertEntities() {
    assert.equal(Ecs.entity_eq([1, 0], [1, 99]), false);
    assert.equal(Ecs.entity_eq([1, 99], [1, 99]), true);
    assert.equal(NodeMod.Node.window([1, 99]).is_window([1, 0]), false);
    assert.equal(NodeMod.stack_find({ entities: [[1, 99]] }, [1, 0]), null);
    assert.equal(NodeMod.stack_find({ entities: [[1, 99], [2, 0]] }, [2, 0]), 1);

    const world = new Ecs.World();
    const windows = world.register_storage();
    world.create_entity();
    const old = world.create_entity();
    windows.insert(old, 'old window');
    world.delete_entity(old);
    const replacement = world.create_entity();
    windows.insert(replacement, 'replacement window');
    assert.deepEqual(old, [1, 0]);
    assert.equal(windows.get(old), null);
    assert.deepEqual(replacement, [1, 1]);
    assert.equal(windows.get(replacement), 'replacement window');

    // Slot 0 reuse and double-delete safety
    const slotWorld = new Ecs.World();
    const slotWindows = slotWorld.register_storage();
    const slotOld = slotWorld.create_entity();
    slotWindows.insert(slotOld, 'zero');
    slotWorld.delete_entity(slotOld);
    const slotNext = slotWorld.create_entity();
    slotWindows.insert(slotNext, 'next');
    assert.deepEqual(slotOld, [0, 0]);
    assert.deepEqual(slotNext, [0, 1]);
    assert.equal(slotWindows.get(slotOld), null);
    assert.equal(slotWindows.get(slotNext), 'next');
    slotWorld.delete_entity(slotOld);
    assert.equal(slotWindows.get(slotNext), 'next');

    // Storage.insert bounds check: inserting past current length fills gaps with null
    const sparseStorage = slotWorld.register_storage();
    sparseStorage.insert([4, 0], 'sparse');
    assert.equal(sparseStorage.store.length, 5);
    for (let idx = 0; idx < 4; idx += 1) {
        assert.equal(sparseStorage.store[idx], null, `slot ${idx} should be null`);
    }
    assert.equal(sparseStorage.get([4, 0]), 'sparse');

    // World.unregister_storage handles index 0 and missing (-1) safely
    const regWorld = new Ecs.World();
    const firstStorage = regWorld.register_storage();
    const secondStorage = regWorld.register_storage();
    const orphanStorage = new Ecs.Storage();
    regWorld.unregister_storage(orphanStorage);
    assert.equal(regWorld.storages.length, 2);
    regWorld.unregister_storage(firstStorage);
    assert.equal(regWorld.storages.length, 1);
    assert.equal(regWorld.storages[0], secondStorage);
    regWorld.unregister_storage(secondStorage);
    assert.equal(regWorld.storages.length, 0);
}

async function assertLauncherService() {
    const raw = readFileSync(join(pop, 'launcher_service.js'), 'utf8');
    let timeoutCb = null;
    let readCb = null;
    const closedEvents = [];
    const source = raw
        .replace(/^import \* as log from '\.\/log\.js';$/m, 'const log = { error() {} };')
        .replace(/^import Gio from 'gi:\/\/Gio';$/m, 'const Gio = { IOErrorEnum: { CANCELLED: 1 } };')
        .replace(
            /^import GLib from 'gi:\/\/GLib';$/m,
            'const GLib = { PRIORITY_DEFAULT: 0, timeout_add(_p, _ms, cb) { globalThis.__launcherTimeoutCb = cb; return 1; } };',
        )
        .replace(/^const \{ byteArray \} = imports;$/m, 'const byteArray = { toString: (b) => String(b) };');

    const mod = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
    const mkStream = (name) => ({
        closes: 0,
        has_pending() { return false; },
        close() { this.closes += 1; },
        write_all() {},
        read_line_async(_p, _c, cb) { readCb = cb; },
        read_line_finish() { return [null]; },
        name,
    });
    const serviceObj = {
        stdin: mkStream('stdin'),
        stdout: mkStream('stdout'),
        cancellable: { cancel() {} },
    };
    const svc = new mod.LauncherService(serviceObj, () => {}, () => closedEvents.push('closed'));
    readCb(serviceObj.stdout, {});
    assert.equal(closedEvents.length, 1);
    svc.exit();
    timeoutCb = globalThis.__launcherTimeoutCb;
    assert.equal(typeof timeoutCb, 'function');
    assert.equal(timeoutCb(), false);
    assert.equal(serviceObj.stdin.closes, 1, 'stdin should be closed once');
    assert.equal(serviceObj.stdout.closes, 1, 'stdout should be closed once');
}

async function assertCompizFixes() {
    assert.equal(safe_speedup_divider(0), DEFAULT_SPEEDUP_FACTOR);
    assert.equal(safe_speedup_divider(-4), DEFAULT_SPEEDUP_FACTOR);
    assert.equal(safe_speedup_divider(Number.POSITIVE_INFINITY), DEFAULT_SPEEDUP_FACTOR);
    assert.equal(safe_speedup_divider(Number.NaN), DEFAULT_SPEEDUP_FACTOR);
    assert.equal(safe_speedup_divider(8), 8);

    const prepared = settings_for_effect({
        SPEEDUP_FACTOR: { key: 'speedup-factor-divider', get() { return 0; }, set() {} },
    });
    assert.equal(prepared.SPEEDUP_FACTOR.get(), DEFAULT_SPEEDUP_FACTOR);

    // mass=100 must clamp to >= 1 and springs array length must be 24
    const model = new WobblyModel({ sizeX: 200, sizeY: 120, friction: 3.5, springK: 3.8, mass: 100 });
    assert.equal(model.mass, 1);
    assert.equal(model.springs.length, 24);
    assert.ok(model.springs.every((s) => s && s.a && s.b));
    model.grab(10, 10);
    model.move(25, 15);
    model.step(16 / 0);
    model.step(Number.POSITIVE_INFINITY);
    model.step(Number.NaN);
    model.step(2);
    for (const obj of model.objects) {
        assert.ok(Number.isFinite(obj.x) && Number.isFinite(obj.y), 'object coords remain finite');
    }

    // wobbly.js: guard 0x0 actor without throwing or producing NaN
    const wobblyRaw = readFileSync(join(compiz, 'src/effects/wobbly.js'), 'utf8')
        .replace(/^import Clutter from 'gi:\/\/Clutter';$/m, 'const Clutter = { DeformEffect: class { _init() {} set_n_tiles() {} vfunc_set_actor() {} get_actor() { return null; } } };')
        .replace(/^import Cogl from 'gi:\/\/Cogl';$/m, 'const Cogl = { Color: class { init_from_4f() {} } };')
        .replace(/^import GObject from 'gi:\/\/GObject';$/m, 'const GObject = { registerClass() {} };')
        .replace(/^import \* as Main from 'resource:\/\/\/org\/gnome\/shell\/ui\/main\.js';$/m, 'const Main = { overview: { connect() { return 1; }, disconnect() {} } };')
        .replace(/from '\.\/wobbly_model\.js';/, `from '${pathToFileURL(join(compiz, 'src/effects/wobbly_model.js')).href}';`)
        .replace(/from '\.\.\/\.\.\/settings_data\.js';/, `from '${pathToFileURL(join(compiz, 'settings_data.js')).href}';`);

    const { WobblyEffect } = await import('data:text/javascript;base64,' + Buffer.from(wobblyRaw).toString('base64'));
    const effect = new WobblyEffect();
    effect._init({
        op: 'move',
        settingsData: {
            FRICTION: { get: () => 3.5 },
            SPRING_K: { get: () => 3.8 },
            SPEEDUP_FACTOR: { get: () => 12 },
            MASS: { get: () => 70 },
            X_TILES: { get: () => 6 },
            Y_TILES: { get: () => 6 },
        },
    });
    effect.vfunc_set_actor({ get_size: () => [0, 0] });
    assert.equal(effect.initialized, false, 'zero-size actor should not initialize');
    const vertex = { tx: 0.5, ty: 0.5, x: 10, y: 20 };
    effect.vfunc_deform_vertex(100, 100, vertex);
    assert.deepEqual(vertex, { tx: 0.5, ty: 0.5, x: 10, y: 20 });

    // resize.js: single-argument Math.exp and 0x0 guard
    const resizeSrc = readFileSync(join(compiz, 'src/effects/resize.js'), 'utf8');
    assert.doesNotMatch(resizeSrc, /Math\.exp\([^)]*,/);
    assert.match(resizeSrc, /w > 0 && h > 0/);

    // extension.js: reduced-motion gate
    const compizExtSrc = readFileSync(join(compiz, 'extension.js'), 'utf8');
    assert.match(compizExtSrc, /notify::reduced-motion/);
    assert.match(compizExtSrc, /St\.ReducedMotion\.REDUCE/);
}

async function assertFlourishFixes() {
    const motionPrefRaw = readFileSync(join(flourish, 'lib/runtime/motionPreference.js'), 'utf8')
        .replace("import St from 'gi://St';", 'const St = globalThis.__flourishSt;');
    const settings = { enable_animations: true, reduced_motion: 0 };
    globalThis.__flourishSt = { Settings: { get: () => settings }, ReducedMotion: { REDUCE: 1 } };
    const { motionEnabled } = await import('data:text/javascript;base64,' + Buffer.from(motionPrefRaw).toString('base64'));
    assert.equal(motionEnabled(), true);
    settings.reduced_motion = 1;
    assert.equal(motionEnabled(), false);
    settings.reduced_motion = 0;
    settings.enable_animations = false;
    assert.equal(motionEnabled(), false);

    const extSrc = readFileSync(join(flourish, 'extension.js'), 'utf8');
    assert.match(extSrc, /notify::reduced-motion/);

    const surfaceSrc = readFileSync(join(flourish, 'lib/runtime/motionSurface.js'), 'utf8');
    assert.match(surfaceSrc, /#disposed/);
    assert.match(surfaceSrc, /actor\.disconnectObject\(this\);\s*(?:\/\/[^\n]*\n\s*)*actor\[property\] = original;/);

    const decSrc = readFileSync(join(flourish, 'lib/runtime/iconDecorations.js'), 'utf8');
    assert.match(decSrc, /this\.#label\?\.visible/);
    assert.match(decSrc, /this\.#iconBox\?\.connectObject/);

    const decInline = decSrc.replace(/^import .*?;\n/gm, '');
    const decUrl = 'data:text/javascript;base64,' + Buffer.from(
        'const St = { Bin: class {}, Label: class {} };\n' + decInline,
    ).toString('base64');
    const { IconDecorations } = await import(decUrl);
    let disposed = false;
    const actor = new Proxy(
        { connectObject() {}, disconnectObject() {}, get_children: () => [] },
        {
            get(target, key) {
                assert.equal(disposed, false, 'actor accessed after label hide');
                return target[key];
            },
        },
    );
    let decorations;
    const label = {
        connectObject() {},
        disconnectObject() {},
        hide() {
            disposed = true;
            decorations.dispose();
            decorations.update();
        },
    };
    decorations = new IconDecorations({
        container: { label },
        bin: actor,
        icon: { icon: { get_parent: () => actor } },
        onChanged() {},
    });
    decorations.dispose();
    decorations.dispose();
}

assertFloatLiterals();
assertEntities();
await assertLauncherService();
await assertCompizFixes();
await assertFlourishFixes();
console.log('appearance js regressions ok');
