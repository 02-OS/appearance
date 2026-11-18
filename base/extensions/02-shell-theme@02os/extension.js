import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class ZeroTwoShellThemeExtension extends Extension {
    enable() {
        // GNOME Shell automatically loads stylesheet.css from this extension directory.
    }

    disable() {
        // GNOME Shell automatically unloads this extension's stylesheet.css.
    }
}
