#!/usr/bin/env bash
# Install the shared 02-OS glass base plus one chrome variant into an airootfs.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat >&2 <<'EOF'
Usage: apply.sh [VARIANT] AIROOTFS
       apply.sh --variant VARIANT --dest AIROOTFS

Install the shared 02-OS appearance base and one variant (01, 02, or 03) into AIROOTFS.
When VARIANT is omitted, ${APPEARANCE_VARIANT:-01} is used.
EOF
}

variant="${APPEARANCE_VARIANT:-01}"
variant_set=false
dest=""
positional=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --variant)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      variant="$2"
      variant_set=true
      shift 2
      ;;
    --variant=*)
      variant="${1#*=}"
      variant_set=true
      shift
      ;;
    --dest)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      dest="$2"
      shift 2
      ;;
    --dest=*)
      dest="${1#*=}"
      shift
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        positional+=("$1")
        shift
      done
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done

if [[ -n "${dest}" ]]; then
  if [[ ${#positional[@]} -eq 1 && "${variant_set}" == false ]]; then
    variant="${positional[0]}"
  elif [[ ${#positional[@]} -gt 0 ]]; then
    usage
    exit 1
  fi
else
  case ${#positional[@]} in
    1)
      dest="${positional[0]}"
      ;;
    2)
      variant="${positional[0]}"
      dest="${positional[1]}"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
fi

if [[ ! "${variant}" =~ ^(01|02|03)$ ]]; then
  echo "Appearance variant must be 01, 02, or 03." >&2
  exit 1
fi

if [[ -z "${dest}" || ! -d "${dest}" ]]; then
  usage
  exit 1
fi

dest_abs="$(cd "${dest}" && pwd)"
if [[ "${dest_abs}" == "${root}" || "${dest_abs}" == "${root}/01" || "${dest_abs}" == "${root}/02" || "${dest_abs}" == "${root}/03" ]]; then
  echo "Refusing to install into source directory: ${dest_abs}" >&2
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
if ! grep -q "'02-shell-theme@02os'" "${dest}/etc/dconf/db/local.d/00-02os"; then
  sed -i -E "s|^(enabled-extensions=\[.*)\]$|\1,'02-shell-theme@02os']|" "${dest}/etc/dconf/db/local.d/00-02os"
fi
cp -a "${root}/base/dconf/gdm-00-02os-branding" "${dest}/etc/dconf/db/gdm.d/00-02os-branding"
cp -a "${root}/${variant}/dconf" "${dest}/etc/dconf/db/local.d/10-variant"

rm -rf "${dest}/usr/share/02os/appearance"
mkdir -p "${dest}/usr/share/02os/appearance/${variant}" \
  "${dest}/usr/share/gnome-shell/theme/02os" \
  "${dest}/usr/share/gnome-shell/extensions/02-shell-theme@02os" \
  "${dest}/etc/skel/.config/gtk-3.0" \
  "${dest}/etc/skel/.config/gtk-4.0" \
  "${dest}/etc/skel/.config/gnome-shell" \
  "${dest}/etc/02os"

cp -a "${root}/base/gtk-window-controls.css" "${dest}/usr/share/02os/appearance/gtk-window-controls.css"
cp -a "${root}/base/gtk-window-controls.css" "${dest}/usr/share/02os/appearance/${variant}/gtk-window-controls.css"
cp -a "${root}/base/gtk-window-controls.css" "${dest}/etc/skel/.config/gtk-3.0/gtk-window-controls.css"
cp -a "${root}/base/gtk-window-controls.css" "${dest}/etc/skel/.config/gtk-4.0/gtk-window-controls.css"

cp -a "${root}/${variant}/gtk.css" "${dest}/usr/share/02os/appearance/${variant}/gtk.css"
cp -a "${root}/${variant}/gtk.css" "${dest}/etc/skel/.config/gtk-3.0/gtk.css"
cp -a "${root}/${variant}/gtk.css" "${dest}/etc/skel/.config/gtk-4.0/gtk.css"

cp -a "${root}/${variant}/shell.css" "${dest}/usr/share/02os/appearance/${variant}/shell.css"
cp -a "${root}/${variant}/shell.css" "${dest}/usr/share/gnome-shell/theme/02os/gnome-shell.css"
cp -a "${root}/${variant}/shell.css" "${dest}/usr/share/gnome-shell/extensions/02-shell-theme@02os/stylesheet.css"
cp -a "${root}/${variant}/shell.css" "${dest}/etc/skel/.config/gnome-shell/gnome-shell.css"

printf '%s\n' "${variant}" > "${dest}/etc/02os/appearance"

if command -v glib-compile-schemas >/dev/null 2>&1; then
  glib-compile-schemas --strict "${dest}/usr/share/glib-2.0/schemas"
  while IFS= read -r -d '' schema_dir; do
    glib-compile-schemas --strict "${schema_dir}"
  done < <(find "${dest}/usr/share/gnome-shell/extensions" -type d -name schemas -print0)
fi

if command -v dconf >/dev/null 2>&1; then
  dconf compile "${dest}/etc/dconf/db/local" "${dest}/etc/dconf/db/local.d"
  dconf compile "${dest}/etc/dconf/db/gdm" "${dest}/etc/dconf/db/gdm.d"
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "${dest}/usr/share/icons/02-OS"
fi

echo "Installed appearance base + ${variant} into ${dest}"
