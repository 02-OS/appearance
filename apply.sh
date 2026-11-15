#!/usr/bin/env bash
# Install the shared 02-OS glass base plus one chrome variant into an airootfs.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
variant="${1:-${APPEARANCE_VARIANT:-01}}"
dest="${2:-}"

if [[ ! "${variant}" =~ ^(01|02|03)$ ]]; then
  echo "Appearance variant must be 01, 02, or 03." >&2
  exit 1
fi
if [[ -z "${dest}" || ! -d "${dest}" ]]; then
  echo "Usage: apply.sh VARIANT AIROOTFS" >&2
  exit 1
fi

copy_tree() {
  local source="$1" target="$2"
  mkdir -p "${target}"
  cp -a "${source}/." "${target}/"
}

copy_tree "${root}/base/icons/02-OS" "${dest}/usr/share/icons/02-OS"
mkdir -p "${dest}/usr/share/icons/hicolor/scalable/apps" "${dest}/usr/share/pixmaps"
cp -a "${root}/base/hicolor/02os-logo.svg" "${dest}/usr/share/icons/hicolor/scalable/apps/02os-logo.svg"
cp -a "${root}/base/pixmaps/02os-logo.svg" "${dest}/usr/share/pixmaps/02os-logo.svg"
copy_tree "${root}/base/backgrounds" "${dest}/usr/share/backgrounds/02os"
mkdir -p "${dest}/usr/share/gnome-background-properties"
cp -a "${root}/base/gnome-background-properties/02os.xml" "${dest}/usr/share/gnome-background-properties/02os.xml"
copy_tree "${root}/base/extensions" "${dest}/usr/share/gnome-shell/extensions"
copy_tree "${root}/base/schemas" "${dest}/usr/share/glib-2.0/schemas"
copy_tree "${root}/base/keybindings" "${dest}/usr/share/gnome-control-center/keybindings"

mkdir -p "${dest}/etc/dconf/profile" "${dest}/etc/dconf/db/local.d" "${dest}/etc/dconf/db/gdm.d"
cp -a "${root}/base/dconf/profile/user" "${dest}/etc/dconf/profile/user"
cp -a "${root}/base/dconf/profile/gdm" "${dest}/etc/dconf/profile/gdm"
cp -a "${root}/base/dconf/00-02os" "${dest}/etc/dconf/db/local.d/00-02os"
cp -a "${root}/base/dconf/gdm-00-02os-branding" "${dest}/etc/dconf/db/gdm.d/00-02os-branding"
cp -a "${root}/${variant}/dconf" "${dest}/etc/dconf/db/local.d/10-variant"

rm -rf "${dest}/usr/share/02os/appearance"
mkdir -p "${dest}/usr/share/02os/appearance/${variant}" \
  "${dest}/etc/skel/.config/gtk-3.0" \
  "${dest}/etc/skel/.config/gtk-4.0" \
  "${dest}/etc/02os"
cp -a "${root}/${variant}/gtk.css" "${dest}/usr/share/02os/appearance/${variant}/gtk.css"
cp -a "${root}/${variant}/shell.css" "${dest}/usr/share/02os/appearance/${variant}/shell.css"
cp -a "${root}/${variant}/gtk.css" "${dest}/etc/skel/.config/gtk-3.0/gtk.css"
cp -a "${root}/${variant}/gtk.css" "${dest}/etc/skel/.config/gtk-4.0/gtk.css"
cp -a "${root}/${variant}/shell.css" "${dest}/etc/skel/.config/gnome-shell/gnome-shell.css" 2>/dev/null || {
  mkdir -p "${dest}/etc/skel/.config/gnome-shell"
  cp -a "${root}/${variant}/shell.css" "${dest}/etc/skel/.config/gnome-shell/gnome-shell.css"
}
printf '%s\n' "${variant}" > "${dest}/etc/02os/appearance"
echo "Installed appearance base + ${variant} into ${dest}"
