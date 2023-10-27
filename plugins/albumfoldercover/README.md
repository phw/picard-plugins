# Album Folder Cover plugin for MusicBrainz Picard

This plugin sets the the parent folder icon of a file to show the album cover.

The plugin supports the following systems:


## macOS
Requires iconutil from Xcode Command Line Tools.


## GNOME
Sets the folder icon as a GIO attribute. If Picard is configured to save the
cover image as a file this file will get reused. Otherwise the cover art gets
saved as `.cover.png`.


## KDE (TODO)

Writes a `.directory` file with XDG Desktop Entry:

```
[Desktop Entry]
Icon=cover.png
```

TODO: Needs conversion to PNG format. Require pillow


## Windows

TODO: Requires conversion into .ico format. Could be done with Pillow. Afterwards
      a `desktop.ini` file can be written.

See also https://superuser.com/questions/410085/is-there-a-way-to-easily-set-the-icon-a-folder-uses
