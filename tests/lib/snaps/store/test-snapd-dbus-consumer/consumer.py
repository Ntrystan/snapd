#!/usr/bin/env python3
import dbus
import sys


def run(bus):
    obj = bus.get_object("com.dbustest.HelloWorld", "/com/dbustest/HelloWorld")
    print(obj.SayHello(dbus_interface="com.dbustest.HelloWorld"))


if __name__ == "__main__":
    bus = dbus.SystemBus() if sys.argv[1] == "system" else dbus.SessionBus()
    run(bus)
