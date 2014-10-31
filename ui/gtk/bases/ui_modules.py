import sys

import gi

from Bases.BaseObject import GLOBAL_CONFIG

use_gi = False
if GLOBAL_CONFIG.get('arg_parse_dict', {}).get('no_gi', False) is False:
    if hasattr(gi, 'require_version'):
        try:
            gi.require_version('Gtk', '3.0')
            use_gi = True
        except:
            use_gi = False
    else:
        use_gi = False

if use_gi:
    #sys.path.append('..')
    if type(sys.argv[0]) == unicode:
        sys.argv[0] = str(sys.argv[0])
        
    from gi.repository import GLib, Gdk
    GLib.threads_init()
    Gdk.threads_init()
    from gi.repository import Gtk, Gio, GObject, Pango#, Clutter, GtkClutter
    Gtk.gdk = Gdk
    gtk = Gtk
    gio = Gio
    gdk = Gdk
    gobject = GObject
    glib = GLib
    pango = Pango
    #clutter = Clutter
    #cluttergtk = GtkClutter
else:
    import gtk as _gtk
    import glib as _glib
    import gio as _gio
    import gobject as _gobject
    import pango as _pango
    gtk = _gtk
    glib = _glib
    gio = _gio
    gobject = _gobject
    pango = _pango
    gtk.gdk.threads_init()
    gdk = gtk.gdk

def get_gtk_version():
    if hasattr(gtk, 'MAJOR_VERSION'):
        return gtk.MAJOR_VERSION
    if hasattr(gtk, '_version'):
        return int(gtk._version.split('.')[0])
    if hasattr(gtk, 'gtk_version'):
        return gtk.gtk_version[0]
    return False
    
GLOBAL_CONFIG['gtk_version'] = get_gtk_version()
