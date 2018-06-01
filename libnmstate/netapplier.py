#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import socket

from gi.repository import Gio, GLib

from libnmstate import nmclient
from libnmstate import validator
from libnmstate.nmclient import NM


main_loop = GLib.MainLoop()

def apply(desired_state):
    validator.verify(desired_state)

    _apply_ifaces_state(desired_state)




def _apply_ifaces_state(state):
    client = nmclient.client()

    for iface_state in state['interfaces']:
        nmdev = client.get_device_by_iface(iface_state['name'])
        active_connection = nmdev.get_active_connection()
        connection = None

        #import pdb; pdb.set_trace()
        if iface_state['state'] == 'up':
            ip4state = iface_state.get("ip")
            if ip4state:
                connection = active_connection.get_connection()
                ip4setting = nmclient.connection_ensure_setting(
                    connection, NM.SettingIP4Config)
                if not ip4state["enabled"]:
                    ip4setting.set_property(NM.SETTING_IP_CONFIG_METHOD,
                                            'disabled')
                else:
                    ip4setting.set_property(NM.SETTING_IP_CONFIG_METHOD,
                                            'manual')
                    ip4setting.clear_addresses()
                    for addr in ip4state["addresses"]:
                        naddr = NM.IPAddress.new(socket.AF_INET, addr["ip"],
                                                 addr["prefix-length"])
                        ip4setting.add_address(naddr)
                if not connection.commit_changes(True):
                    raise RuntimeError("Could not commit changes")

            if nmdev.get_state() != nmclient.NM.DeviceState.ACTIVATED:
                client.activate_connection_async(device=nmdev)
        elif iface_state['state'] == 'down':
            if active_connection:
                client.deactivate_connection_async(active_connection)
        else:
            raise UnsupportedIfaceStateError(iface_state)

    if connection:
        cancellable = Gio.Cancellable.new()
        cb_args = {}
        timeout = 10

        client.activate_connection_async(connection, None, None, cancellable, activate_cb, cb_args)
        main_loop.run()


def activate_cb(client, result, cb_args):
    active_connection = None
    try:
        active_connection = client.activate_connection_finish(result)
    except Exception as e:
        if isinstance(e, GLib.GError):
            print(e)
            if e.domain == 'g-io-error-quark' and \
                    e.code == Gio.IOErrorEnum.CANCELLED:
                return

        cb_args['error'] = str(e)
        cb_args['active_connection'] = active_connection
    finally:
        main_loop.quit()


class UnsupportedIfaceStateError(Exception):
    pass
