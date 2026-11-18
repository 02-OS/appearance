"""Validation suite for 02-OS/appearance (issues #1-#10)."""

import ast
import configparser
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "apply.sh"
BASE = ROOT / "base"
BACKGROUNDS = BASE / "backgrounds"
EXTENSIONS = BASE / "extensions"
SCHEMAS = BASE / "schemas"
GENERATOR = BASE / "icon-generator"
GALLERY_SCRIPT = GENERATOR / "generate_html_gallery.py"
GALLERY_HTML = BASE / "02-OS-icons-preview.html"
COMPIZ_SCHEMA = "org.gnome.shell.extensions.com.github.hermes83.compiz-windows-effect.gschema.xml"
ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pop_shell_content_sha256(root):
    digest = hashlib.sha256()
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name != "PROVENANCE.md"
    )
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class DconfTests(unittest.TestCase):
    def test_variant_keybindings_avoid_collisions(self):
        for variant in ("01", "02", "03"):
            with self.subTest(variant=variant):
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read(ROOT / variant / "dconf", encoding="utf-8")
                self.assertEqual(cfg["org/gnome/desktop/wm/keybindings"]["maximize"], "@as []")
                self.assertEqual(cfg["org/gnome/mutter/keybindings"]["toggle-tiled-left"], "@as []")
                self.assertEqual(cfg["org/gnome/mutter/keybindings"]["toggle-tiled-right"], "@as []")
                close = ast.literal_eval(cfg["org/gnome/desktop/wm/keybindings"]["close"])
                self.assertIn("<Alt>F4", close)
        cfg02 = configparser.ConfigParser(interpolation=None)
        cfg02.read(ROOT / "02" / "dconf", encoding="utf-8")
        self.assertEqual(
            ast.literal_eval(cfg02["org/gnome/desktop/wm/keybindings"]["close"]),
            ["<Super>q", "<Alt>F4"],
        )

    def test_base_00_02os_defaults_and_shortcuts(self):
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(BASE / "dconf/00-02os", encoding="utf-8")
        self.assertEqual(cfg["org/gnome/desktop/interface"]["cursor-theme"], "'capitaine-cursors'")
        enabled = ast.literal_eval(cfg["org/gnome/shell"]["enabled-extensions"])
        for uuid in (
            "dash-to-dock@micxgx.gmail.com",
            "pop-shell@system76.com",
            "flourish@orsso.github.io",
            "compiz-windows-effect@hermes83.github.com",
            "02-index-phase@02os",
            "02-agent-status@02os",
        ):
            self.assertIn(uuid, enabled)
        self.assertEqual(
            ast.literal_eval(cfg["org/gnome/shell/extensions/pop-shell"]["toggle-floating"]),
            ["<Super>g"],
        )
        self.assertEqual(
            ast.literal_eval(cfg["org/gnome/shell/extensions/pop-shell"]["focus-right"]),
            ["<Super>Right", "<Super>KP_Right"],
        )
        self.assertEqual(
            ast.literal_eval(cfg["org/gnome/settings-daemon/plugins/media-keys"]["screensaver"]),
            ["<Super>l"],
        )
        custom2 = cfg["org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom2"]
        self.assertEqual(custom2["command"], "'gnome-control-center'")
        self.assertEqual(custom2["binding"], "'<Super>i'")

        wm = "org/gnome/desktop/wm/keybindings"
        shell = "org/gnome/shell/keybindings"
        bindings = {(shell, f"switch-to-application-{n}"): [f"<Super>{n}"] for n in range(1, 5)}
        for section in (wm, shell):
            for key, value in cfg[section].items():
                bindings[(section, key)] = ast.literal_eval(re.sub(r"^@as\s+", "", value))
        for number in range(1, 5):
            accelerator = f"<Super>{number}"
            owners = [k for k, acc in bindings.items() if accelerator in acc]
            self.assertEqual(owners, [(wm, f"switch-to-workspace-{number}")])
            self.assertEqual(bindings[(shell, f"switch-to-application-{number}")], [])


class SchemaAndMetadataTests(unittest.TestCase):
    def test_compiz_schema_ranges_and_byte_parity(self):
        ext_schema = EXTENSIONS / "compiz-windows-effect@hermes83.github.com/schemas" / COMPIZ_SCHEMA
        base_schema = SCHEMAS / COMPIZ_SCHEMA
        self.assertEqual(ext_schema.read_bytes(), base_schema.read_bytes())
        tree = ET.parse(base_schema)
        expected_ranges = {
            "friction": (1.0, 10.0),
            "spring-k": (1.0, 10.0),
            "speedup-factor-divider": (2.0, 40.0),
            "mass": (1.0, 99.0),
            "x-tiles": (3.0, 20.0),
            "y-tiles": (3.0, 20.0),
        }
        for name, (expected_min, expected_max) in expected_ranges.items():
            with self.subTest(key=name):
                key = tree.find(f".//key[@name='{name}']")
                self.assertIsNotNone(key)
                bounds = key.find("range")
                self.assertIsNotNone(bounds)
                self.assertEqual(float(bounds.get("min")), expected_min)
                self.assertEqual(float(bounds.get("max")), expected_max)

    def test_all_extension_schemas_match_base_and_compile_strict(self):
        for schema_path in EXTENSIONS.rglob("*.gschema.xml"):
            base_copy = SCHEMAS / schema_path.name
            self.assertTrue(base_copy.is_file(), f"Missing base schema {schema_path.name}")
            self.assertEqual(schema_path.read_bytes(), base_copy.read_bytes(), schema_path.name)
        if shutil.which("glib-compile-schemas"):
            res = subprocess.run(
                ["glib-compile-schemas", "--strict", "--dry-run", str(SCHEMAS)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_extensions_declare_gnome_51_support(self):
        for meta_path in sorted(EXTENSIONS.glob("*/metadata.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertIn("51", meta["shell-version"], str(meta_path))


class BackgroundTests(unittest.TestCase):
    def test_backgrounds_deduplicated_and_valid(self):
        self.assertFalse((BACKGROUNDS / "desktop.png").exists())
        self.assertTrue((BACKGROUNDS / "desktop.jpg").is_file())
        halo = BACKGROUNDS / "portal-halo.png"
        self.assertTrue(halo.is_file())
        self.assertLess(halo.stat().st_size, 400 * 1024)
        self.assertEqual(halo.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        xml_text = (BASE / "gnome-background-properties/02os.xml").read_text(encoding="utf-8")
        refs = set(re.findall(r"/usr/share/backgrounds/02os/([^<\s'\"]+)", xml_text))
        dconf_text = (BASE / "dconf/00-02os").read_text(encoding="utf-8")
        refs.update(re.findall(r"/usr/share/backgrounds/02os/([^<\s'\"]+)", dconf_text))
        self.assertEqual(refs, {"desktop.jpg", "portal-halo.png"})
        for ref in refs:
            self.assertTrue((BACKGROUNDS / ref).is_file(), ref)


class CssTests(unittest.TestCase):
    def test_shared_gtk_window_controls_and_variant_radii(self):
        shared = (BASE / "gtk-window-controls.css").read_text(encoding="utf-8")
        self.assertIn("min-width: 24px;", shared)
        self.assertIn("min-height: 24px;", shared)
        self.assertIn(":focus-visible", shared)
        for variant, expected in (("01", "border-radius: 2px;"), ("02", "border-radius: 999px;"), ("03", "border-radius: 4px;")):
            css = (ROOT / variant / "gtk.css").read_text(encoding="utf-8")
            self.assertIn('@import url("gtk-window-controls.css");', css)
            self.assertIn(expected, css)
            self.assertNotIn("min-width:", css)
            self.assertNotIn("min-height:", css)


class ApplyScriptTests(unittest.TestCase):
    def test_no_aerootfs_typo_and_cli_validation(self):
        apply_src = APPLY.read_text(encoding="utf-8")
        self.assertNotIn("AEROOTFS", apply_src)
        res = subprocess.run([str(APPLY)], capture_output=True, text=True, check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("AIROOTFS", res.stderr)
        res_bad = subprocess.run([str(APPLY), "04", "/tmp"], capture_output=True, text=True, check=False)
        self.assertNotEqual(res_bad.returncode, 0)

    def test_apply_all_variants_and_env_form(self):
        cases = [
            ("01", lambda d: ([str(APPLY), "01", str(d)], os.environ.copy())),
            ("02", lambda d: ([str(APPLY), str(d)], {**os.environ, "APPEARANCE_VARIANT": "02"})),
            ("03", lambda d: ([str(APPLY), "--variant", "03", "--dest", str(d)], os.environ.copy())),
        ]
        for variant, cmd_fn in cases:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix=f"02os-app-{variant}-") as tmp:
                dest = Path(tmp)
                cmd, env = cmd_fn(dest)
                res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertEqual((dest / "etc/02os/appearance").read_text(encoding="utf-8").strip(), variant)
                self.assertFalse((dest / "usr/share/backgrounds/02os/desktop.png").exists())
                self.assertTrue((dest / "usr/share/backgrounds/02os/portal-halo.png").is_file())
                self.assertTrue((dest / "usr/share/backgrounds/02os/desktop.jpg").is_file())

                expected_shell = (ROOT / variant / "shell.css").read_text(encoding="utf-8")
                for rel in (
                    f"usr/share/02os/appearance/{variant}/shell.css",
                    "usr/share/gnome-shell/theme/02os/gnome-shell.css",
                    "usr/share/gnome-shell/extensions/02-shell-theme@02os/stylesheet.css",
                    "etc/skel/.config/gnome-shell/gnome-shell.css",
                ):
                    self.assertEqual((dest / rel).read_text(encoding="utf-8"), expected_shell, rel)

                dconf_base = (dest / "etc/dconf/db/local.d/00-02os").read_text(encoding="utf-8")
                self.assertIn("'02-shell-theme@02os'", dconf_base)

                for rel_dir in (
                    f"usr/share/02os/appearance/{variant}",
                    "etc/skel/.config/gtk-3.0",
                    "etc/skel/.config/gtk-4.0",
                ):
                    self.assertTrue((dest / rel_dir / "gtk.css").is_file())
                    self.assertTrue((dest / rel_dir / "gtk-window-controls.css").is_file())

                if shutil.which("glib-compile-schemas"):
                    self.assertTrue((dest / "usr/share/glib-2.0/schemas/gschemas.compiled").is_file())
                    self.assertTrue((dest / f"usr/share/gnome-shell/extensions/compiz-windows-effect@hermes83.github.com/schemas/gschemas.compiled").is_file())
                if shutil.which("dconf"):
                    for db_name in ("local", "gdm"):
                        db_path = dest / "etc/dconf/db" / db_name
                        self.assertTrue(db_path.is_file())
                        self.assertEqual(db_path.read_bytes()[:8], b"GVariant")
                if shutil.which("gtk-update-icon-cache"):
                    self.assertTrue((dest / "usr/share/icons/02-OS/icon-theme.cache").is_file())

                # Validate installed GTK CSS with real GTK 3/4 CssProviders if available
                for ver, subdir in (("3.0", "gtk-3.0"), ("4.0", "gtk-4.0")):
                    check_gtk = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            (
                                f"import gi; gi.require_version('Gtk', '{ver}'); "
                                "from gi.repository import Gtk; "
                                "errs = []; p = Gtk.CssProvider(); "
                                "p.connect('parsing-error', lambda _p, _s, err: errs.append(err.message)); "
                                f"p.load_from_path({str(dest / 'etc/skel/.config' / subdir / 'gtk.css')!r}); "
                                "assert not errs, errs"
                            ),
                        ],
                        capture_output=True, text=True, check=False,
                    )
                    if "ValueError: Namespace Gtk not available" not in check_gtk.stderr:
                        self.assertEqual(check_gtk.returncode, 0, f"GTK {ver}: {check_gtk.stdout + check_gtk.stderr}")


class IconGeneratorAndGalleryTests(unittest.TestCase):
    def test_dead_scripts_and_raster_pngs_removed(self):
        self.assertFalse((GENERATOR / "build_02os_theme.py").exists())
        self.assertFalse((GENERATOR / "generate_02os_icons.py").exists())
        self.assertEqual(list((GENERATOR / "assets").glob("*.png")), [])

    def test_icons_are_pure_vector_with_trimmed_defs(self):
        icons_root = BASE / "icons/02-OS/scalable"
        for svg_path in icons_root.rglob("*.svg"):
            if svg_path.is_symlink():
                self.assertTrue(svg_path.resolve().is_file(), f"Broken symlink {svg_path}")
                continue
            text = svg_path.read_text(encoding="utf-8")
            self.assertNotIn("data:image/png", text, str(svg_path))
            ET.fromstring(text)

        trash_empty = (icons_root / "places/user-trash.svg").read_text(encoding="utf-8")
        trash_full = (icons_root / "places/user-trash-full.svg").read_text(encoding="utf-8")
        self.assertNotEqual(trash_empty, trash_full)
        self.assertTrue((icons_root / "apps/org.gnome.Settings.svg").is_symlink())

        install_svg = (icons_root / "apps/02os-install.svg").read_text(encoding="utf-8")
        self.assertNotIn('id="folder-shadow"', install_svg)
        self.assertNotIn('id="pocket-shadow"', install_svg)
        self.assertNotIn('id="glow"', install_svg)

    def test_html_gallery_matches_generator_and_is_offline_searchable(self):
        gallery = load_module("generate_html_gallery", GALLERY_SCRIPT)
        html = GALLERY_HTML.read_text(encoding="utf-8")
        self.assertEqual(html, gallery.build_gallery())
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("Arch Linux Hyprland", html)
        self.assertIn('id="gallery-search"', html)
        self.assertIn('id="gallery-filters"', html)
        ids = ID_RE.findall(html)
        self.assertGreater(len(ids), 0)
        self.assertEqual(len(ids), len(set(ids)))

    def test_icon_generator_fails_on_unwritable_target(self):
        with tempfile.TemporaryDirectory(prefix="02os-icons-fail-") as tmp:
            root = Path(tmp)
            dest_gen = root / "base/icon-generator"
            shutil.copytree(GENERATOR, dest_gen)
            shutil.copy2(BASE / "02-logo.svg", root / "base/02-logo.svg")
            (root / "base/icons").write_text("not a directory\n", encoding="utf-8")
            res = subprocess.run(
                [sys.executable, str(dest_gen / "generate_full_icon_pack.py")],
                cwd=root, capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Error generating", res.stderr)


class JsAndProvenanceTests(unittest.TestCase):
    def test_relative_js_imports_resolve(self):
        import_re = re.compile(r"""from\s*(['"])(\.{1,2}/[^'"]+)\1""")
        scripts = sorted(EXTENSIONS.rglob("*.js"))
        self.assertGreater(len(scripts), 0)
        for path in scripts:
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in import_re.finditer(text):
                spec = match.group(2)
                target = path.parent / spec
                candidates = [target]
                if target.suffix != ".js":
                    candidates.append(Path(str(target) + ".js"))
                self.assertTrue(
                    any(candidate.is_file() for candidate in candidates),
                    f"{path.relative_to(EXTENSIONS)} imports missing {spec}",
                )

    def test_all_extension_js_pass_node_check(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required on PATH")
        for js_file in sorted(EXTENSIONS.rglob("*.js")):
            with self.subTest(file=str(js_file.relative_to(ROOT))):
                res = subprocess.run([node, "--check", str(js_file)], capture_output=True, text=True, check=False)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_node_js_regressions(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "node is required on PATH")
        res = subprocess.run(
            [node, str(ROOT / "tests/desktop_js_regressions.mjs")],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_provenance_and_docs(self):
        manifest = json.loads((ROOT / "docs/desktop-motion-vendor.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["target_shell"], "51")
        entry = manifest["existing_extension_patches"][0]
        pop = EXTENSIONS / "pop-shell@system76.com"
        self.assertEqual(entry["uuid"], "pop-shell@system76.com")
        self.assertEqual(entry["version"], 2)
        self.assertEqual(entry["license"], "GPL-3.0-only")
        self.assertTrue((pop / entry["license_file"]).is_file())
        self.assertTrue((pop / "PROVENANCE.md").is_file())
        self.assertEqual(pop_shell_content_sha256(pop), entry["content_sha256"])
        motion_doc = (ROOT / "docs/desktop-motion.md").read_text(encoding="utf-8")
        self.assertIn("GNOME Shell 51", motion_doc)


if __name__ == "__main__":
    unittest.main()
