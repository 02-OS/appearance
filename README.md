# 02 appearance

Desktop look for 02_OS. The 02-OS icon pack and the glassmorphic dock, wallpaper, and extension set are the shared base. Three variants change window chrome, dock layout, and keybinds. They are named only `01`, `02`, and `03`.

| Variant | Chrome and layout |
| --- | --- |
| `01` | Buttons on the right, bottom dock, square corners, Super+arrows tile |
| `02` | Buttons on the left, centered autohiding dock, round corners |
| `03` | Buttons on the right, left dock, modest corners |

## Install into an archiso profile

```bash
./apply.sh 01 /path/to/profile/airootfs
```

`APPEARANCE_VARIANT` is the default when the first argument is omitted. The image records the choice in `/etc/02os/appearance`. Session behavior comes from `etc/dconf/db/local.d/10-variant`, which overrides the shared `00-02os` base. GTK chrome is copied into `/etc/skel` and `/usr/share/02os/appearance/<variant>/`.

Regenerate the icon pack from `base/icon-generator/` when the mark changes. `base/02-logo.svg` is the same approved mark the boot animation uses.
