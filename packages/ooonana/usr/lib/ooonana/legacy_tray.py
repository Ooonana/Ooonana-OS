"""Event-driven XEmbed overflow host; never replace an existing tray manager."""
import ctypes as C

from desktop_theme import XResources
from xsettings_session import ClientMessage, Event
from tray_model import MAX_LEGACY_ITEMS, dock_request, text


class Cookie(C.Structure):
    _fields_ = [("sequence", C.c_uint)]


class AtomReply(C.Structure):
    _fields_ = [("response", C.c_ubyte), ("pad", C.c_ubyte), ("sequence", C.c_ushort),
               ("length", C.c_uint), ("atom", C.c_uint)]


class PropertyReply(C.Structure):
    _fields_ = [("response", C.c_ubyte), ("format", C.c_ubyte), ("sequence", C.c_ushort),
               ("length", C.c_uint), ("type", C.c_uint), ("remaining", C.c_uint),
               ("count", C.c_uint), ("pad", C.c_ubyte * 12)]


class SelectionEvent(C.Structure):
    _fields_ = [("type", C.c_int), ("serial", C.c_ulong), ("send_event", C.c_int),
               ("display", C.c_void_p), ("window", C.c_ulong), ("subtype", C.c_int),
               ("owner", C.c_ulong), ("selection", C.c_ulong), ("timestamp", C.c_ulong),
               ("selection_timestamp", C.c_ulong)]


class Properties:
    """Checked XCB replies keep stale/invalid client XIDs out of Xlib's fatal handler."""
    def __init__(self):
        self.lib = C.CDLL("libxcb.so.1")
        self.free = C.CDLL(None).free; self.free.argtypes = [C.c_void_p]
        signatures = {
            "xcb_connect": ([C.c_char_p, C.POINTER(C.c_int)], C.c_void_p),
            "xcb_connection_has_error": ([C.c_void_p], C.c_int),
            "xcb_disconnect": ([C.c_void_p], None),
            "xcb_intern_atom": ([C.c_void_p, C.c_ubyte, C.c_ushort, C.c_char_p], Cookie),
            "xcb_intern_atom_reply": ([C.c_void_p, Cookie, C.c_void_p], C.POINTER(AtomReply)),
            "xcb_get_property": ([C.c_void_p, C.c_ubyte, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_uint], Cookie),
            "xcb_get_property_reply": ([C.c_void_p, Cookie, C.c_void_p], C.POINTER(PropertyReply)),
            "xcb_get_property_value": ([C.POINTER(PropertyReply)], C.c_void_p),
            "xcb_get_property_value_length": ([C.POINTER(PropertyReply)], C.c_int),
            "xcb_unmap_window_checked": ([C.c_void_p, C.c_uint], Cookie),
            "xcb_reparent_window_checked": ([C.c_void_p, C.c_uint, C.c_uint, C.c_short, C.c_short], Cookie),
            "xcb_clear_area_checked": ([C.c_void_p, C.c_ubyte, C.c_uint, C.c_short, C.c_short, C.c_ushort, C.c_ushort], Cookie),
            "xcb_request_check": ([C.c_void_p, Cookie], C.c_void_p),
        }
        for name, (arguments, result) in signatures.items():
            method = getattr(self.lib, name); method.argtypes, method.restype = arguments, result
        self.connection = self.lib.xcb_connect(None, None)
        if not self.connection or self.lib.xcb_connection_has_error(self.connection):
            self.close(); raise OSError("Legacy tray X11 connection unavailable")
        self.atoms = {}

    def atom(self, name):
        if name not in self.atoms:
            data = name.encode("ascii")
            reply = self.lib.xcb_intern_atom_reply(self.connection, self.lib.xcb_intern_atom(self.connection, 0, len(data), data), None)
            if not reply: raise OSError("Legacy tray atom unavailable")
            try: self.atoms[name] = reply.contents.atom
            finally: self.free(reply)
        return self.atoms[name]

    def read(self, xid, name, limit=512):
        reply = self.lib.xcb_get_property_reply(self.connection,
            self.lib.xcb_get_property(self.connection, 0, xid, self.atom(name), 0, 0, (limit + 3) // 4), None)
        if not reply: return None
        try:
            size = self.lib.xcb_get_property_value_length(reply)
            if reply.contents.remaining or size < 0 or size > limit: return None
            return reply.contents.format, reply.contents.type, C.string_at(self.lib.xcb_get_property_value(reply), size)
        finally: self.free(reply)

    def embeddable(self, xid):
        value = self.read(xid, "_XEMBED_INFO", 8)
        return bool(value and value[0] == 32 and value[1] == self.atom("_XEMBED_INFO") and len(value[2]) == 8)

    def title(self, xid):
        for name in ("_NET_WM_NAME", "WM_NAME", "WM_CLASS"):
            value = self.read(xid, name)
            if value and value[0] == 8:
                title = text(value[2].replace(b"\0", b" ").decode("utf-8", "replace"), 128)
                if title: return title
        return "Legacy app"

    def detach(self, xid, root):
        for cookie in (self.lib.xcb_unmap_window_checked(self.connection, xid),
                       self.lib.xcb_reparent_window_checked(self.connection, xid, root, -1, -1)):
            error = self.lib.xcb_request_check(self.connection, cookie)
            if error: self.free(error)  # App can disappear between notification and detach.

    def close(self):
        if self.connection: self.lib.xcb_disconnect(self.connection); self.connection = None

    def repaint(self, xid):
        error = self.lib.xcb_request_check(self.connection, self.lib.xcb_clear_area_checked(self.connection, 1, xid, 0, 0, 0, 0))
        if error: self.free(error)


class LegacyTray(XResources):
    socket_type = None
    def __init__(self, window, changed):
        from gi.repository import Gdk, GdkX11, GLib, Gtk
        if not isinstance(Gdk.Display.get_default(), GdkX11.X11Display):
            raise OSError("Legacy tray requires X11; modern indicators remain available")
        self.Gdk, self.GdkX11, self.GLib, self.Gtk = Gdk, GdkX11, GLib, Gtk
        self.window, self.changed, self.items = window, changed, {}
        self.closed, self.watch, self.drain_source, self.owned, self.owner_window = False, None, None, False, 0
        self.properties = None
        self.style_watch = None
        super().__init__()
        signatures = {
            "XDefaultScreen": ([C.c_void_p], C.c_int),
            "XDefaultVisual": ([C.c_void_p, C.c_int], C.c_void_p),
            "XVisualIDFromVisual": ([C.c_void_p], C.c_ulong),
            "XCreateSimpleWindow": ([C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong], C.c_ulong),
            "XGetSelectionOwner": ([C.c_void_p, C.c_ulong], C.c_ulong),
            "XSetSelectionOwner": ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong], C.c_int),
            "XSelectInput": ([C.c_void_p, C.c_ulong, C.c_long], C.c_int),
            "XWindowEvent": ([C.c_void_p, C.c_ulong, C.c_long, C.POINTER(Event)], C.c_int),
            "XSendEvent": ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)], C.c_int),
            "XConnectionNumber": ([C.c_void_p], C.c_int), "XPending": ([C.c_void_p], C.c_int),
            "XNextEvent": ([C.c_void_p, C.POINTER(Event)], C.c_int),
            "XDestroyWindow": ([C.c_void_p, C.c_ulong], C.c_int),
        }
        for name, (arguments, result) in signatures.items():
            method = getattr(self.lib, name); method.argtypes, method.restype = arguments, result
        try: self.properties = Properties()
        except OSError:
            super().close(); raise
        self.screen = self.lib.XDefaultScreen(self.display)
        self.selection, self.opcode = self.atom(f"_NET_SYSTEM_TRAY_S{self.screen}"), self.atom("_NET_SYSTEM_TRAY_OPCODE")
        self.watcher = self.lib.XCreateSimpleWindow(self.display, self.root, -1, -1, 1, 1, 0, 0, 0)
        try: self.fixes = C.CDLL("libXfixes.so.3")
        except OSError:
            self.close(); raise
        self.fixes.XFixesQueryExtension.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.fixes.XFixesSelectSelectionInput.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong]
        self.selection_event, error = C.c_int(), C.c_int()
        if not self.fixes.XFixesQueryExtension(self.display, C.byref(self.selection_event), C.byref(error)):
            self.close(); raise OSError("Legacy tray requires XFixes selection events")
        self.fixes.XFixesSelectSelectionInput(self.display, self.watcher, self.selection, 7)
        self.style_watch = window.connect("style-updated", self.palette)
        self.claim()
        self.watch = GLib.io_add_watch(self.lib.XConnectionNumber(self.display), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.events)

    def atom(self, name):
        return self.lib.XInternAtom(self.display, name.encode(), 0)

    def claim(self):
        if self.closed or self.owned: return
        self.lib.XGrabServer(self.display)
        try:
            if self.lib.XGetSelectionOwner(self.display, self.selection): return
            self.owner_window = self.lib.XCreateSimpleWindow(self.display, self.root, -1, -1, 1, 1, 0, 0, 0)
            stamp = self.atom("_OOONANA_TRAY_TIME")
            self.lib.XSelectInput(self.display, self.owner_window, 1 << 22)
            self.lib.XChangeProperty(self.display, self.owner_window, stamp, stamp, 8, 0, C.create_string_buffer(b"0"), 1)
            event = Event(); self.lib.XWindowEvent(self.display, self.owner_window, 1 << 22, C.byref(event))
            timestamp = event.property.time
            self.lib.XSetSelectionOwner(self.display, self.selection, self.owner_window, timestamp)
            self.owned = self.lib.XGetSelectionOwner(self.display, self.selection) == self.owner_window
            if self.owned:
                for name, kind, value in (("_NET_SYSTEM_TRAY_ORIENTATION", "CARDINAL", 1),
                        ("_NET_SYSTEM_TRAY_ICON_SIZE", "CARDINAL", 24 * self.window.get_scale_factor()),
                        ("_NET_SYSTEM_TRAY_PADDING", "CARDINAL", 0),
                        ("_NET_SYSTEM_TRAY_VISUAL", "VISUALID", self.lib.XVisualIDFromVisual(self.lib.XDefaultVisual(self.display, self.screen)))):
                    data = (C.c_ulong * 1)(value)
                    self.lib.XChangeProperty(self.display, self.owner_window, self.atom(name), self.atom(kind), 32, 0, data, 1)
                event.message = ClientMessage(33, 0, 1, self.display, self.root, self.atom("MANAGER"), 32,
                                              (C.c_long * 5)(timestamp, self.selection, self.owner_window, 0, 0))
                self.lib.XSendEvent(self.display, self.root, 0, 1 << 17, C.byref(event))
                self.palette()
        finally:
            self.lib.XUngrabServer(self.display); self.lib.XFlush(self.display)

    def palette(self, *_args):
        if self.closed: return
        context = self.window.get_style_context()
        foreground = context.get_color(self.Gtk.StateFlags.NORMAL)
        if self.owned:
            # GTK legacy clients default to black symbolic ink without this hint.
            colors = [foreground.red, foreground.green, foreground.blue,
                      .7968, 0, 0, .9570, .4726, .2421, .3047, .6016, .0234]
            values = (C.c_ulong * 12)(*(round(value * 65535) for value in colors))
            self.lib.XChangeProperty(self.display, self.owner_window, self.atom("_NET_SYSTEM_TRAY_COLORS"),
                                     self.atom("CARDINAL"), 32, 0, values, 12)
            self.lib.XFlush(self.display)
        for xid, item in self.items.items():
            self.paint_socket(item["socket"])
            self.properties.repaint(xid)

    def paint_socket(self, socket):
        native = socket.get_window()
        if native:
            # ParentRelative clients need a defined X background, not GTK's
            # transient drawing buffer. Keep the host itself fully opaque.
            background = self.window.get_style_context().get_background_color(self.Gtk.StateFlags.NORMAL)
            native.set_background_rgba(background)
    def release(self):
        self.owned = False
        for xid, item in list(self.items.items()): self.remove(xid, item, True)
        if self.owner_window:
            window, self.owner_window = self.owner_window, 0
            self.lib.XDestroyWindow(self.display, window); self.lib.XFlush(self.display)

    def events(self, _fd=None, condition=0):
        if self.closed: return False
        if condition & (self.GLib.IO_HUP | self.GLib.IO_ERR): self.close(); return False
        for _ in range(128):
            if not self.lib.XPending(self.display): break
            event = Event(); self.lib.XNextEvent(self.display, C.byref(event))
            if event.type == 29:
                if event.message.window == self.owner_window: self.release()
            elif event.type == self.selection_event.value:
                selection = C.cast(C.byref(event), C.POINTER(SelectionEvent)).contents
                if selection.selection == self.selection:
                    owner = self.lib.XGetSelectionOwner(self.display, self.selection)
                    if not owner: self.claim()
                    elif owner != self.owner_window and self.owned: self.release()
            elif self.owned and event.type == 33 and event.message.message_type == self.opcode:
                xid = dock_request(event.type, event.message.format, list(event.message.data))
                if xid: self.add(xid)
        if self.lib.XPending(self.display) and self.drain_source is None:
            self.drain_source = self.GLib.idle_add(self.drain)
        return True

    def drain(self):
        self.drain_source = None
        if not self.closed: self.events()
        return False

    def add(self, xid):
        if self.closed or not self.owned or xid in self.items or xid in (self.root, self.owner_window, self.watcher) or len(self.items) >= MAX_LEGACY_ITEMS:
            return
        if not self.properties.embeddable(xid): return
        display = self.Gdk.Display.get_default()
        display.error_trap_push()
        try:
            foreign = self.GdkX11.X11Window.foreign_new_for_display(display, xid)
        except TypeError: foreign = None
        finally: error = display.error_trap_pop()
        if error or foreign is None: return
        Gtk = self.Gtk
        if LegacyTray.socket_type is None:
            class BoundedSocket(Gtk.Socket):
                def do_get_preferred_width(self):
                    Gtk.Socket.do_get_preferred_width(self)
                    return 24, 24
                def do_get_preferred_height(self):
                    Gtk.Socket.do_get_preferred_height(self)
                    return 24, 24
            LegacyTray.socket_type = BoundedSocket
        socket = LegacyTray.socket_type(); socket.set_can_focus(True); socket.set_valign(Gtk.Align.CENTER)
        name = self.properties.title(xid)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(10); row.set_margin_end(10); row.set_margin_top(4); row.set_margin_bottom(4)
        title = Gtk.Label(label=name, xalign=0)
        from gi.repository import Pango
        title.set_ellipsize(Pango.EllipsizeMode.END); title.set_max_width_chars(32); title.set_hexpand(True)
        socket.set_tooltip_text(name); socket.get_accessible().set_name(name + " legacy tray icon")
        row.pack_start(socket, False, False, 0); row.pack_start(title, True, True, 0)
        self.window.list.pack_start(row, False, False, 0)
        item = {"row": row, "socket": socket, "title": title, "foreign": foreign, "deadline": None}
        self.items[xid] = item
        def removed(*_args):
            self.GLib.idle_add(self.remove, xid, item, False); return True
        def embedded(*_args):
            if item["deadline"]: self.GLib.source_remove(item["deadline"]); item["deadline"] = None
        socket.connect("plug-removed", removed); socket.connect("plug-added", embedded)
        self.window.realize(); row.show_all(); socket.realize()
        self.paint_socket(socket)
        display.error_trap_push()
        try: socket.add_id(xid)
        finally: error = display.error_trap_pop()
        if error: self.remove(xid, item, False); return
        # The bounded request can remain 24px before/after docking. Force the
        # allocation pass that GtkSocket uses to map/configure a new plug.
        socket.queue_allocate()
        if socket.get_plug_window() is None:
            item["deadline"] = self.GLib.timeout_add(1500, self.expired, xid, item)
        self.changed()

    def expired(self, xid, item):
        item["deadline"] = None
        if self.items.get(xid) is item and item["socket"].get_plug_window() is None: self.remove(xid, item, False)
        return False

    def remove(self, xid, item, detach=False):
        if self.items.get(xid) is not item: return False
        self.items.pop(xid)
        if item["deadline"]: self.GLib.source_remove(item["deadline"]); item["deadline"] = None
        if detach and item["socket"].get_plug_window() is not None: self.properties.detach(xid, self.root)
        item["row"].destroy(); self.changed()
        return False

    def close(self):
        if self.closed: return False
        self.closed = True
        if self.style_watch: self.window.disconnect(self.style_watch); self.style_watch = None
        if self.watch: self.GLib.source_remove(self.watch); self.watch = None
        if self.drain_source: self.GLib.source_remove(self.drain_source); self.drain_source = None
        self.release()
        if self.properties: self.properties.close()
        super().close()  # Destroy only our selection window; never another owner.
        return False
