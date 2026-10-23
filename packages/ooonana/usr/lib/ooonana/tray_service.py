"""Session-bus indicator registry/host. No polling, privileged commands or files."""
from dataclasses import dataclass, field
import os
from gi.repository import Gio, GLib
from tray_model import MAX_ITEMS, address, properties, pixmap

WATCHER = "org.kde.StatusNotifierWatcher"
WATCH_PATH = "/StatusNotifierWatcher"
ITEM = "org.kde.StatusNotifierItem"
PROPERTIES = "org.freedesktop.DBus.Properties"
XML = '''<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
<signal name="StatusNotifierHostRegistered"/>
<signal name="StatusNotifierHostUnregistered"/>
</interface></node>'''


@dataclass(eq=False)
class Indicator:
    identifier: str
    bus: str
    path: str
    owner: str
    props: dict = field(default_factory=dict)
    image: object = None
    pending: int = 0
    epoch: int = 0
    failed: bool = False
    cancel: object = field(default_factory=Gio.Cancellable)
    subscriptions: list = field(default_factory=list)


class TrayService:
    def __init__(self, changed, error, bus=None):
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION)
        self.changed, self.error = changed, error
        self.items, self.owned, self.closed, self.watcher_owner = {}, False, False, ""
        self.foreign_subscription = None
        peer = self.bus.get_unique_name().removeprefix(":").replace(".", "-")
        self.host_name = f"org.kde.StatusNotifierHost-ooonana-{os.getpid()}-{peer}"
        self.subscriptions = []
        self.registration = self.bus.register_object(WATCH_PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], self.method, self.property, None)
        self.request_name(self.host_name)
        self.subscriptions.append(self.bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, self.owner_changed))
        self.watcher_watch = Gio.bus_watch_name_on_connection(self.bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
                                                             self.appeared, self.vanished)
        self.claim()

    def request_name(self, name):
        return self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
            GLib.Variant("(su)", (name, 4)), GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0] in (1, 4)

    def claim(self):
        if not self.closed:
            self.owned = self.request_name(WATCHER)  # DO_NOT_QUEUE; never replace another watcher.

    def property(self, _bus, _sender, _path, _interface, name):
        return {"RegisteredStatusNotifierItems": GLib.Variant("as", list(self.items)),
                "IsStatusNotifierHostRegistered": GLib.Variant("b", True), "ProtocolVersion": GLib.Variant("i", 0)}[name]

    def emit(self, member, identifier=None):
        if self.owned and not self.closed:
            self.bus.emit_signal(None, WATCH_PATH, WATCHER, member, GLib.Variant("(s)", (identifier,)) if identifier else None)

    def owner(self, name):
        return self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner",
            GLib.Variant("(s)", (name,)), GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]

    def method(self, _bus, sender, _path, _interface, name, params, invocation):
        try:
            if not self.owned or self.closed:
                raise ValueError("Another watcher owns this session")
            service = params.unpack()[0]
            if name == "RegisterStatusNotifierItem":
                bus, path = address(service, sender)
                if self.owner(bus) != sender:
                    raise ValueError("Indicator registration must come from its owner")
                self.add(bus + path)
            elif name == "RegisterStatusNotifierHost":
                bus, _ = address(service)
                if self.owner(bus) != sender:
                    raise ValueError("Host registration must come from its owner")
                self.emit("StatusNotifierHostRegistered")
            else:
                raise ValueError("Unknown indicator method")
            invocation.return_value(GLib.Variant("()", ()))
        except (ValueError, GLib.Error) as error:
            invocation.return_dbus_error("org.ooonana.Tray.InvalidRegistration", str(error)[:256])

    def call(self, destination, path, interface, method, params, done, cancellable=None):
        def finished(bus, reply):
            try:
                result = bus.call_finish(reply)
                value, error = result.unpack() if result else (), None
            except GLib.Error as exception:
                value, error = None, exception
            if not self.closed:
                done(value, error)
        self.bus.call(destination, path, interface, method, params, None, Gio.DBusCallFlags.NO_AUTO_START,
                      1500, cancellable, finished)

    def appeared(self, _bus, _name, owner):
        if self.closed: return
        if self.foreign_subscription is not None:
            self.bus.signal_unsubscribe(self.foreign_subscription)
            self.foreign_subscription = None
        self.watcher_owner = owner
        if owner == self.bus.get_unique_name():
            self.owned = True
            self.emit("StatusNotifierHostRegistered")
            return
        self.owned = False
        self.call(owner, WATCH_PATH, WATCHER, "RegisterStatusNotifierHost", GLib.Variant("(s)", (self.host_name,)), lambda *_: None)
        def snapshot(value, error):
            if self.watcher_owner != owner or error: return
            values = value[0] if value else []
            if not isinstance(values, (tuple, list)): return
            for identifier in values[:MAX_ITEMS]:
                try: self.add(identifier)
                except (ValueError, GLib.Error): pass
        self.call(owner, WATCH_PATH, PROPERTIES, "Get", GLib.Variant("(ss)", (WATCHER, "RegisteredStatusNotifierItems")), snapshot)
        self.foreign_subscription = self.bus.signal_subscribe(owner, WATCHER, None, WATCH_PATH, None,
            Gio.DBusSignalFlags.NONE, self.foreign_signal)

    def vanished(self, *_args):
        self.watcher_owner = ""
        self.owned = False
        self.claim()

    def foreign_signal(self, _bus, sender, _path, _interface, name, params):
        if sender != self.watcher_owner: return
        identifier = params.unpack()[0] if params.n_children() else ""
        try:
            if name == "StatusNotifierItemRegistered": self.add(identifier)
            elif name == "StatusNotifierItemUnregistered": self.remove(identifier)
        except (ValueError, GLib.Error): pass

    def owner_changed(self, _bus, _sender, _path, _interface, _name, params):
        name, old, new = params.unpack()
        if old and old != new:
            for item in list(self.items.values()):
                if old == item.owner and (name == item.owner or name == item.bus):
                    self.remove(item.identifier)

    def add(self, identifier):
        bus, path = address(identifier)
        owner = self.owner(bus)
        identifier = bus + path
        previous = self.items.get(identifier)
        if previous is not None:
            if previous.owner == owner: return
            self.remove(identifier)
        # Aliases must not duplicate the same app/object.
        if any(item.owner == owner and item.path == path for item in self.items.values()): return
        if len(self.items) >= MAX_ITEMS:
            self.error("Background app limit reached. Close unused indicators.")
            raise ValueError("Indicator limit reached")
        item = self.items[identifier] = Indicator(identifier, bus, path, owner)
        for interface in (ITEM, PROPERTIES):
            item.subscriptions.append(self.bus.signal_subscribe(owner, interface, None, path, None, Gio.DBusSignalFlags.NONE,
                lambda *_args, item=item: self.schedule(item)))
        self.refresh(item)
        self.emit("StatusNotifierItemRegistered", identifier)
        self.changed()

    def current(self, item):
        return not self.closed and self.items.get(item.identifier) is item

    def schedule(self, item):
        if self.current(item) and not item.pending:
            item.pending = GLib.timeout_add(80, self.refresh, item)

    def refresh(self, item):
        item.pending = 0
        if not self.current(item): return False
        item.epoch += 1; epoch = item.epoch
        def done(value, error):
            if not self.current(item) or item.epoch != epoch: return
            item.failed = bool(error)
            if not error and value and isinstance(value[0], dict):
                item.props = properties(value[0])
                item.image = pixmap(value[0].get("AttentionIconPixmap" if item.props.get("Status") == "NeedsAttention" else "IconPixmap"))
            self.changed()
        self.call(item.owner, item.path, PROPERTIES, "GetAll", GLib.Variant("(s)", (ITEM,)), done, item.cancel)
        return False

    def remove(self, identifier):
        item = self.items.pop(identifier, None)
        if item is None: return
        item.cancel.cancel()
        if item.pending: GLib.source_remove(item.pending)
        for subscription in item.subscriptions: self.bus.signal_unsubscribe(subscription)
        self.emit("StatusNotifierItemUnregistered", identifier)
        self.changed()

    def action(self, item, method, x, y, done):
        if not self.current(item): return done(None, ValueError("App no longer available"))
        self.call(item.owner, item.path, ITEM, method, GLib.Variant("(ii)", (x, y)), done, item.cancel)

    def close(self):
        if self.closed: return
        self.closed = True
        Gio.bus_unwatch_name(self.watcher_watch)
        for item in list(self.items): self.remove(item)
        for subscription in self.subscriptions: self.bus.signal_unsubscribe(subscription)
        if self.foreign_subscription is not None: self.bus.signal_unsubscribe(self.foreign_subscription)
        self.bus.unregister_object(self.registration)
        for name in (WATCHER, self.host_name) if self.owned else (self.host_name,):
            self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ReleaseName",
                GLib.Variant("(s)", (name,)), None, Gio.DBusCallFlags.NONE, 1000, None)
