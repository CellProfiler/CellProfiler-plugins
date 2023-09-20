import base64
import functools
import io
import logging
import os
import queue
import string
import threading
import time

import requests
import wx
import cellprofiler.gui.plugins_menu
from cellprofiler_core.preferences import config_read_typed, config_write_typed, \
    set_omero_server, set_omero_port, set_omero_user

from .connect import CREDENTIALS, login

LOGGER = logging.getLogger(__name__)


def get_display_server():
    # Should we display the 'connection successful' message after using a token?
    return config_read_typed(f"Reader.OMERO.show_server", bool)


def set_display_server(value):
    config_write_typed(f"Reader.OMERO.show_server", value, key_type=bool)


def login_gui(connected, server=None):
    # Login via GUI or display a prompt notifying that we're already connected
    if connected:
        from cellprofiler.gui.errordialog import show_warning
        show_warning("Connected to OMERO",
                     f"A token was found and used to connect to the OMERO server at {CREDENTIALS.server}",
                     get_display_server,
                     set_display_server)
        return
    show_login_dlg(server=server)


def show_login_dlg(e=None, server=None):
    # Show the login GUI
    app = wx.GetApp()
    frame = app.GetTopWindow()
    with OmeroLoginDlg(frame, title="Login to OMERO", server=server) as dlg:
        dlg.ShowModal()
    if CREDENTIALS.client is not None:
        CREDENTIALS.create_temp_token()


def browse(e):
    # Show the browser dialog
    if CREDENTIALS.client is None:
        login()
    app = wx.GetApp()
    frame = app.GetTopWindow()
    # Only allow a single instance, raise the window if it already exists.
    if CREDENTIALS.browser_window is None:
        CREDENTIALS.browser_window = OmeroBrowseDlg(frame, title=f"Browse OMERO: {CREDENTIALS.server}")
        CREDENTIALS.browser_window.Show()
    else:
        CREDENTIALS.browser_window.Raise()


def inject_plugin_menu_entries():
    # Add plugin menu entries to the main CellProfiler GUI
    cellprofiler.gui.plugins_menu.PLUGIN_MENU_ENTRIES.extend([
        (login, wx.NewId(), "Connect to OMERO", "Establish an OMERO connection"),
        (show_login_dlg, wx.NewId(), "Connect to OMERO (no token)", "Establish an OMERO connection,"
                                                                    " but without using user tokens"),
        (browse, wx.NewId(), "Browse OMERO for images", "Browse an OMERO server and add images to the pipeline")
    ])


def configure_for_safe_shutdown():
    # When GUI is running we need to capture wx exit events and close the OMERO connection
    app = wx.GetApp()
    frame = app.GetTopWindow()
    frame.Bind(wx.EVT_CLOSE, CREDENTIALS.handle_exit)


class OmeroLoginDlg(wx.Dialog):
    """
    A dialog pane to provide and use OMERO login credentials.
    """
    def __init__(self, *args, token=True, server=None, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.credentials = CREDENTIALS
        self.token = token
        self.SetSizer(wx.BoxSizer(wx.VERTICAL))
        if server is None:
            server = self.credentials.server or ""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.Sizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 6)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer, 0, wx.EXPAND)

        max_width = 0
        max_height = 0
        for label in ("Server:", "Port:", "Username:", "Password:"):
            w, h, _, _ = self.GetFullTextExtent(label)
            max_width = max(w, max_width)
            max_height = max(h, max_height)

        # Add extra padding
        lsize = wx.Size(max_width + 5, max_height)
        sub_sizer.Add(
            wx.StaticText(self, label="Server:", size=lsize),
            0, wx.ALIGN_CENTER_VERTICAL)
        self.omero_server_ctrl = wx.TextCtrl(self, value=server)
        sub_sizer.Add(self.omero_server_ctrl, 1, wx.EXPAND)

        sizer.AddSpacer(5)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer, 0, wx.EXPAND)
        sub_sizer.Add(
            wx.StaticText(self, label="Port:", size=lsize),
            0, wx.ALIGN_CENTER_VERTICAL)
        self.omero_port_ctrl = wx.lib.intctrl.IntCtrl(self, value=self.credentials.port)
        sub_sizer.Add(self.omero_port_ctrl, 1, wx.EXPAND)

        sizer.AddSpacer(5)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer, 0, wx.EXPAND)
        sub_sizer.Add(
            wx.StaticText(self, label="User:", size=lsize),
            0, wx.ALIGN_CENTER_VERTICAL)
        self.omero_user_ctrl = wx.TextCtrl(self, value=self.credentials.username or "")
        sub_sizer.Add(self.omero_user_ctrl, 1, wx.EXPAND)

        sizer.AddSpacer(5)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer, 0, wx.EXPAND)
        sub_sizer.Add(
            wx.StaticText(self, label="Password:", size=lsize),
            0, wx.ALIGN_CENTER_VERTICAL)
        self.omero_password_ctrl = wx.TextCtrl(self, value="", style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.omero_password_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_connect_pressed)
        if self.credentials.username is not None:
            self.omero_password_ctrl.SetFocus()
        sub_sizer.Add(self.omero_password_ctrl, 1, wx.EXPAND)

        sizer.AddSpacer(5)
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(sub_sizer, 0, wx.EXPAND)
        connect_button = wx.Button(self, label="Connect")
        connect_button.Bind(wx.EVT_BUTTON, self.on_connect_pressed)
        sub_sizer.Add(connect_button, 0, wx.EXPAND)
        sub_sizer.AddSpacer(5)

        self.message_ctrl = wx.StaticText(self, label="Not connected")
        sub_sizer.Add(self.message_ctrl, 1, wx.EXPAND)

        self.token_button = wx.Button(self, label="Set Token")
        self.token_button.Bind(wx.EVT_BUTTON, self.on_set_pressed)
        self.token_button.Disable()
        self.token_button.SetToolTip("Use these credentials to set a long-lasting token for automatic login")
        sub_sizer.Add(self.token_button, 0, wx.EXPAND)
        sub_sizer.AddSpacer(5)

        button_sizer = wx.StdDialogButtonSizer()
        self.Sizer.Add(button_sizer, 0, wx.EXPAND)

        cancel_button = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        self.ok_button = wx.Button(self, wx.ID_OK)
        button_sizer.AddButton(self.ok_button)
        self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        self.ok_button.Enable(False)
        button_sizer.Realize()

        self.omero_password_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
        self.omero_port_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
        self.omero_server_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
        self.omero_user_ctrl.Bind(wx.EVT_TEXT, self.mark_dirty)
        self.Layout()

    def mark_dirty(self, event):
        if self.ok_button.IsEnabled():
            self.ok_button.Enable(False)
            self.message_ctrl.Label = "Please connect with your new credentials"
            self.message_ctrl.ForegroundColour = "black"

    def on_connect_pressed(self, event):
        if self.credentials.client is not None and self.credentials.server == self.omero_server_ctrl.GetValue():
            # Already connected, accept another 'Connect' command as an ok to close
            self.EndModal(wx.OK)
        self.connect()

    def on_set_pressed(self, event):
        if self.credentials.client is None:
            return
        import omero_user_token
        token_path = omero_user_token.assert_and_get_token_path()
        if os.path.exists(token_path):
            dlg2 = wx.MessageDialog(self,
                                    "Existing omero_user_token will be overwritten. Proceed?",
                                    "Overwrite existing token?",
                                    wx.YES_NO | wx.CANCEL | wx.ICON_WARNING)
            result = dlg2.ShowModal()
            if result != wx.ID_YES:
                LOGGER.debug("Cancelled")
                return
        token = omero_user_token.setter(
            self.credentials.server,
            self.credentials.port,
            self.credentials.username,
            self.credentials.passwd,
            -1)
        if token:
            LOGGER.info("Set OMERO user token")
            self.message_ctrl.Label = "Connected. Token Set!"
            self.message_ctrl.ForegroundColour = "forest green"
        else:
            LOGGER.error("Failed to set OMERO user token")
            self.message_ctrl.Label = "Failed to set token."
            self.message_ctrl.ForegroundColour = "red"
        self.message_ctrl.Refresh()

    def connect(self):
        try:
            server = self.omero_server_ctrl.GetValue()
            port = self.omero_port_ctrl.GetValue()
            user = self.omero_user_ctrl.GetValue()
            passwd = self.omero_password_ctrl.GetValue()
        except:
            self.message_ctrl.Label = (
                "The port number must be an integer between 0 and 65535 (try 4064)"
            )
            self.message_ctrl.ForegroundColour = "red"
            self.message_ctrl.Refresh()
            return False
        self.message_ctrl.ForegroundColour = "black"
        self.message_ctrl.Label = "Connecting..."
        self.message_ctrl.Refresh()
        # Allow UI to update before connecting
        wx.Yield()
        success = self.credentials.login(server, port, user, passwd)
        if success:
            self.message_ctrl.Label = "Connected"
            self.message_ctrl.ForegroundColour = "forest green"
            self.token_button.Enable()
            self.message_ctrl.Refresh()
            set_omero_server(server)
            set_omero_port(port)
            set_omero_user(user)
            self.ok_button.Enable(True)
            return True
        else:
            self.message_ctrl.Label = "Failed to log onto server"
            self.message_ctrl.ForegroundColour = "red"
            self.message_ctrl.Refresh()
            self.token_button.Disable()
            return False

    def on_cancel(self, event):
        self.EndModal(wx.CANCEL)

    def on_ok(self, event):
        self.EndModal(wx.OK)


class OmeroBrowseDlg(wx.Dialog):
    """
    An OMERO server browser intended for browsing images and adding them to the main file list
    """
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args,
                                             style=wx.RESIZE_BORDER | wx.CAPTION | wx.CLOSE_BOX,
                                             size=(900, 600),
                                             **kwargs)
        self.credentials = CREDENTIALS
        self.admin_service = self.credentials.session.getAdminService()
        self.url_loader = self.Parent.pipeline.add_urls

        self.Bind(wx.EVT_CLOSE, self.close_browser)

        ec = self.admin_service.getEventContext()
        # Exclude sys groups
        self.groups = [self.admin_service.getGroup(v) for v in ec.memberOfGroups if v > 1]
        self.group_names = [group.name.val for group in self.groups]
        self.current_group = self.groups[0].id.getValue()
        self.users_in_group = {'All Members': -1}
        self.users_in_group.update({
            x.omeName.val: x.id.val for x in self.groups[0].linkedExperimenterList()
        })
        self.current_user = -1
        self.levels = {'projects': 'datasets',
                       'datasets': 'images',
                       'screens': 'plates',
                       'plates': 'wells',
                       'orphaned': 'images'
                       }

        splitter = wx.SplitterWindow(self, -1, style=wx.SP_BORDER)
        self.browse_controls = wx.Panel(splitter, -1)
        b = wx.BoxSizer(wx.VERTICAL)

        self.groups_box = wx.Choice(self.browse_controls, choices=self.group_names)
        self.groups_box.SetSelection(0)
        self.groups_box.Bind(wx.EVT_CHOICE, self.switch_group)

        self.members_box = wx.Choice(self.browse_controls, choices=list(self.users_in_group.keys()))
        self.members_box.SetSelection(0)
        self.members_box.Bind(wx.EVT_CHOICE, self.switch_member)

        b.Add(self.groups_box, 0, wx.EXPAND)
        b.Add(self.members_box, 0, wx.EXPAND)
        self.container = self.credentials.session.getContainerService()

        self.tree = wx.TreeCtrl(self.browse_controls, style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT)
        image_list = wx.ImageList(16, 13)
        image_data = {
            'projects': 'iVBORw0KGgoAAAANSUhEUgAAABAAAAANCAYAAACgu+4kAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpFNjZDNDcxNzc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDpFNjZDNDcxNjc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+vd9MhwAAALhJREFUeNpi/P//P0NEXsd/BhxgxaQKRgY8gAXGMNbVwpA8e/kaAyHAGJhWe5iNnctGVkoaQ/Lxs6cMv35+w6f/CMvfP39svDytscrqaijgtX3t5u02IAMYXrx5z0AOAOll+fPnF8Ov37/IMgCkl+XP799Af5JpAFAv0IBfDD9//STTAKALfgMJcl0A0gvxwi8KvPAXFIhkGvAXHIjAqPjx4zuZsQCMxn9//my9eOaEFQN54ChAgAEAzRBnWnEZWFQAAAAASUVORK5CYII=',
            'datasets': 'iVBORw0KGgoAAAANSUhEUgAAABAAAAANCAYAAACgu+4kAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpFNjZGMDA2ODc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDpFNjZDNDcxQTc5NEUxMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+l9tKdwAAAKZJREFUeNpi/P//P0NUm+d/BhxgWdV2RgY8gAXGMNMwwpA8deMcAyHAEljsdJhTmJ3h1YfnWBUA5f/j0X+E5d+//zYhrv5YZU108du+cNlKG6AB/xjefn7FQA4A6WX59/cfw5/ff8gz4C/IAKApf/78pswFv3/9Jt8Ff8FeIM+AvzAv/KbUC/8oC8T/DN9//iLTBf8ZWP7/+7f18MELVgzkgaMAAQYAgLlmT8qQW/sAAAAASUVORK5CYII=',
            'screens': 'iVBORw0KGgoAAAANSUhEUgAAABEAAAANCAYAAABPeYUaAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA5NpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpDNDk5ODU0N0U5MjA2ODExODhDNkJBNzRDM0U2QkE2NyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo5NkU0QUUzNjc4NEExMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo5NkU0QUUzNTc4NEExMUUxOTY2OEJEQjhGOUExQ0Y3RCIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ1M2ICgxMy4wIDIwMTIwMzA1Lm0uNDE1IDIwMTIvMDMvMDU6MjE6MDA6MDApICAoTWFjaW50b3NoKSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOkM1NzAxRDEzMjkyMTY4MTE4OEM2QkE3NEMzRTZCQTY3IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOkM0OTk4NTQ3RTkyMDY4MTE4OEM2QkE3NEMzRTZCQTY3Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+wkwZRwAAAQxJREFUeNpi/P//PwMjIyODqbHhfwYc4PTZ84y45ED6WZAFPFxdwQYig+27djEQAowgk6wtLcGu4GBnY0C38vvPX3gNOHr8OCPcJaHh4QwsLCwYiv78+YNV87+/fxnWrlkDZsN1PXr0iGHPnj1wRS4uLnj5jg4OcDYTjPH7928w3WxmhcJ3zmtC4Zc2mUH4SC6EG/LrF8TvtaeOofD3TqpD4XfXnULho3gHJOjt7Q2XePHiBV7+s6dPsRuydetWuISuri5evra2Nm7vVKUZoPDTratR+EZV1RjewTCkbdYFFP7Mo60o/HNtrSgBjeEdMzMzuMRToJ/x8Z88eYJpyKcPH8AYGRDiwwBAgAEAvXKdXsBF6t8AAAAASUVORK5CYII=',
            'plates': 'iVBORw0KGgoAAAANSUhEUgAAAA8AAAANCAYAAAB2HjRBAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAASBJREFUeNpiZAACRVXNhnfv3tX//v2bgQjwAIgDv316d4FR38hM4MHDh++trSwZ+Pn4COr8+OkTw4GDhx4ANSuygARANj59+ozhxNFDKAplFVQYHj+4gyEGBAogguniuVMfkCUf7Z4IxsjgyqOJYIwOWGCM////g+mfj68woIt9/Ikphqr53z8wrZo0mwFdzFoVUwxF8z+giRbWDijOevjwAVYxrDafOHoARaGElBxWMRhgQvgF4px98x+BMbLYPSD/HpoYqrP/QQLi2Y2fDOhi37CIoYU2xMSYTlUGdDEdLGIgwAgiNHUM/r9//55BR1sbxX+PHj1kkJOTR43zq1cZBAUFGa5fuQDWy3D69Jn7IAO4+IQIYpA6kHqQPoAAAwCQE6mYLjTwJwAAAABJRU5ErkJggg=='
        }
        self.image_codes = {}
        for name, dat in image_data.items():
            decodedImgData = base64.b64decode(dat)
            bio = io.BytesIO(decodedImgData)
            img = wx.Image(bio)
            img = img.Scale(16, 13)
            self.image_codes[name] = image_list.Add(img.ConvertToBitmap())
        self.tree.AssignImageList(image_list)

        self.tree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.fetch_children)
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGING, self.select_tree)
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.update_thumbnails)
        self.tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.process_drag)

        data = self.fetch_containers()

        self.populate_tree(data)
        b.Add(self.tree, 1, wx.EXPAND)

        self.browse_controls.SetSizer(b)

        self.image_controls = wx.Panel(splitter, -1)

        vert_sizer = wx.BoxSizer(wx.VERTICAL)

        self.tile_panel = TilePanel(self.image_controls, 1)
        self.tile_panel.url_loader = self.url_loader

        self.tiler_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.tile_panel.SetSizer(self.tiler_sizer)
        self.tile_panel.SetScrollbars(0, 20, 0, 20)

        self.update_thumbnails()
        vert_sizer.Add(self.tile_panel, wx.EXPAND)

        add_button = wx.Button(self.image_controls, wx.NewId(), "Add to file list")
        add_button.Bind(wx.EVT_BUTTON, self.add_selected_to_pipeline)
        vert_sizer.Add(add_button, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        self.image_controls.SetSizer(vert_sizer)
        splitter.SplitVertically(self.browse_controls, self.image_controls, 300)

        self.Layout()

    def close_browser(self, event):
        # Disconnect the browser window from the login helper
        self.credentials.browser_window = None
        # Tell the thumbnail generator to shut down
        self.tile_panel.active = False
        event.Skip()

    def add_selected_to_pipeline(self, e=None):
        # Add selected images to the pipeline as URLs
        displayed = self.tile_panel.GetChildren()
        all_urls = []
        selected_urls = []
        for item in displayed:
            if isinstance(item, ImagePanel):
                all_urls.append(item.url)
                if item.selected:
                    selected_urls.append(item.url)
        if selected_urls:
            self.url_loader(selected_urls)
        else:
            self.url_loader(all_urls)

    def process_drag(self, event):
        # CellProfiler's file list uses a custom handler.
        # This will mimic dropping actual files onto it.
        data = wx.FileDataObject()
        for file_url in self.fetch_file_list_from_tree(event):
            data.AddFile(file_url)
        drop_src = wx.DropSource(self)
        drop_src.SetData(data)
        drop_src.DoDragDrop(wx.Drag_CopyOnly)

    def fetch_file_list_from_tree(self, event):
        # Generate a list of OMERO URLs when the user tries to drag an entry.
        files = []

        def recurse_for_images(tree_id):
            # Search the tree for images and add to a list of URLs
            if not self.tree.IsExpanded(tree_id):
                self.tree.Expand(tree_id)
            data = self.tree.GetItemData(tree_id)
            item_type = data['type']
            if item_type == 'images':
                files.append(f"https://{self.credentials.server}/webclient/?show=image-{data['id']}")
            elif 'images' in data:
                for omero_id, _ in data['images'].items():
                    files.append(f"https://{self.credentials.server}/webclient/?show=image-{omero_id}")
            else:
                child_id, cookie = self.tree.GetFirstChild(tree_id)
                while child_id.IsOk():
                    recurse_for_images(child_id)
                    child_id, cookie = self.tree.GetNextChild(tree_id, cookie)

        recurse_for_images(event.GetItem())
        return files

    def select_tree(self, event):
        # The tree is fetched as it's being expanded. Clicking on an object needs to trigger child expansion.
        target_id = event.GetItem()
        self.tree.Expand(target_id)

    def switch_group(self, e=None):
        # Change OMERO group
        new_group = self.groups_box.GetCurrentSelection()
        self.current_group = self.groups[new_group].id.getValue()
        self.current_user = -1
        self.refresh_group_members()
        data = self.fetch_containers()
        self.populate_tree(data)

    def switch_member(self, e=None):
        # Change OMERO user filter
        new_member = self.members_box.GetStringSelection()
        self.current_user = self.users_in_group.get(new_member, -1)
        data = self.fetch_containers()
        self.populate_tree(data)

    def refresh_group_members(self):
        # Update the available user list when the group changes
        self.users_in_group = {'All Members': -1}
        group = self.groups[self.groups_box.GetCurrentSelection()]
        self.users_in_group.update({
            x.omeName.val: x.id.val for x in group.linkedExperimenterList()
        })
        self.members_box.Clear()
        self.members_box.AppendItems(list(self.users_in_group.keys()))
        self.members_box.SetSelection(0)

    def fetch_children(self, event):
        # Load the next level in the tree for a target object.
        target_id = event.GetItem()
        if self.tree.GetChildrenCount(target_id, recursively=False) > 0:
            # Already loaded
            return
        data = self.tree.GetItemData(target_id)
        subject_type = data['type']
        target_type = self.levels.get(subject_type, None)
        if target_type is None:
            # We're at the bottom level already
            return
        subject = data['id']
        if subject == -1:
            sub_str = "orphaned=true&"
        else:
            sub_str = f"id={subject}&"
        if target_type == 'wells':
            url = f"https://{self.credentials.server}/api/v0/m/plates/{subject}/wells/?bsession={self.credentials.session_key}"
        else:
            url = f"https://{self.credentials.server}/webclient/api/{target_type}/?{sub_str}experimenter_id=-1&page=0&group={self.current_group}&bsession={self.credentials.session_key}"
        LOGGER.debug(f"Fetching {url}")
        try:
            result = requests.get(url, timeout=15)
        except requests.exceptions.Timeout:
            LOGGER.error("Server request timed out")
            return
        result = result.json()
        if 'images' in result:
            image_map = {entry['id']: entry['name'] for entry in result['images']}
            data['images'] = image_map
            self.tree.SetItemData(target_id, data)
        if 'meta' in result:
            # This is the plates API
            self.populate_tree_screen(result, target_id)
            result = result['data']
        else:
            self.populate_tree(result, target_id)

    def fetch_containers(self):
        # Grab the base project/dataset structure for the tree view.
        url = f"https://{self.credentials.server}/webclient/api/containers/?id={self.current_user}&page=0&group={self.current_group}&bsession={self.credentials.session_key}"
        try:
            data = requests.get(url, timeout=5)
        except requests.exceptions.Timeout:
            LOGGER.error("Server request timed out")
            return {}
        data.raise_for_status()
        return data.json()

    def update_thumbnails(self, event=None):
        # Show image previews when objects in the tree are clicked on.
        self.tiler_sizer.Clear(delete_windows=True)
        # Empty out any pending tile thumbnails
        with self.tile_panel.thumbnail_queue.mutex:
            self.tile_panel.thumbnail_queue.queue.clear()
        if not event:
            return
        target_id = event.GetItem()
        item_data = self.tree.GetItemData(target_id)
        if item_data.get('type', None) == 'images':
            # We're displaying a single image
            image_id = item_data['id']
            img_name = item_data['name']
            tile = ImagePanel(self.tile_panel, image_id, img_name, self.credentials.server, size=450)
            tile.selected = True
            self.tiler_sizer.Add(tile, 0, wx.ALL, 5)
        else:
            # We're displaying a series of images
            image_targets = item_data.get('images', {})
            if not image_targets:
                return
            for image_id, image_name in image_targets.items():
                tile = ImagePanel(self.tile_panel, image_id, image_name, self.credentials.server)
                self.tiler_sizer.Add(tile, 0, wx.ALL, 5)
        self.tiler_sizer.Layout()
        self.image_controls.Layout()
        self.image_controls.Refresh()

    def populate_tree(self, data, parent=None):
        # Build the tree view
        if parent is None:
            self.tree.DeleteAllItems()
            parent = self.tree.AddRoot("Server")
        for item_type, items in data.items():
            image = self.image_codes.get(item_type, None)
            if not isinstance(items, list):
                items = [items]
            for entry in items:
                entry['type'] = item_type
                new_id = self.tree.AppendItem(parent, f"{entry['name']}", data=entry)
                if image is not None:
                    self.tree.SetItemImage(new_id, image, wx.TreeItemIcon_Normal)
                if entry.get('childCount', 0) > 0 or item_type == 'plates':
                    self.tree.SetItemHasChildren(new_id)

    def populate_tree_screen(self, data, parent=None):
        # Fill the tree data from the screens API
        wells = data['data']
        rows = string.ascii_uppercase
        for well_dict in wells:
            name = f"Well {rows[well_dict['Row']]}{well_dict['Column'] + 1:02}"
            well_dict['type'] = 'wells'
            well_id = self.tree.AppendItem(parent, name)
            well_dict['images'] = {}
            for field_dict in well_dict['WellSamples']:
                image_data = field_dict['Image']
                image_id = image_data['@id']
                image_name = image_data['Name']
                refined_image_data = {
                    'type': 'images',
                    'id': image_id,
                    'name': image_name
                }
                well_dict['images'][image_id] = image_name
                self.tree.AppendItem(well_id, image_name, data=refined_image_data)
            self.tree.SetItemData(well_id, well_dict)


class ImagePanel(wx.Panel):
    """
    The ImagePanel displays an image's name and a preview thumbnail as a wx.Bitmap.

    Tiles are initialised with a loading icon, call update_thumbnail once image data has arrived for display.
    """

    def __init__(self, parent, omero_id, name, server, size=128):
        """
        parent - parent window to the wx.Panel
        omero_id - OMERO id of the image
        name - name to display
        server - the server the image lives on
        size - int dimension of the thumbnail to display
        """
        self.parent = parent
        self.bitmap = None
        self.selected = False
        self.omero_id = omero_id
        self.url = f"https://{server}/webclient/?show=image-{omero_id}"
        self.name = name
        max_len = int(17 / 128 * size)
        if len(name) > max_len:
            self.shortname = name[:max_len - 3] + '...'
        else:
            self.shortname = name
        self.size_x = size
        self.size_y = size + 30
        wx.Panel.__init__(self, parent, wx.NewId(), size=(self.size_x, self.size_y))
        indicator_size = 64
        self.loading = wx.ActivityIndicator(self,
                                            size=wx.Size(indicator_size, indicator_size),
                                            pos=((self.size_x - indicator_size) // 2,
                                                 ((self.size_x - indicator_size) // 2) + 20)
                                            )
        self.loading.Start()
        self.parent.thumbnail_queue.put((omero_id, size, self.update_thumbnail))
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.select)
        self.Bind(wx.EVT_RIGHT_DOWN, self.right_click)
        self.SetClientSize((self.size_x, self.size_y))
        # We need to pass these events up to the parent panel.
        self.Bind(wx.EVT_MOTION, self.pass_event)
        self.Bind(wx.EVT_LEFT_UP, self.pass_event)

    def select(self, e):
        # Mark a panel as selected
        self.selected = not self.selected
        self.Refresh()
        e.StopPropagation()
        e.Skip()

    def pass_event(self, e):
        # We need to pass mouse events up to the containing TilePanel.
        # To do this we need to correct the event position to be relative to the parent.
        x, y = e.GetPosition()
        w, h = self.GetPosition()
        e.SetPosition((x + w, y + h))
        # Now we send the event upwards to be caught by the parent.
        e.ResumePropagation(1)
        e.Skip()

    def right_click(self, event):
        # Show right click menu
        popupmenu = wx.Menu()
        add_file_item = popupmenu.Append(-1, "Add to file list")
        self.Bind(wx.EVT_MENU, self.add_to_pipeline, add_file_item)
        add_file_item = popupmenu.Append(-1, "Show in OMERO.web")
        self.Bind(wx.EVT_MENU, self.open_in_browser, add_file_item)
        # Show menu
        self.PopupMenu(popupmenu, event.GetPosition())

    def add_to_pipeline(self, e):
        # Add image to the pipeline
        self.parent.url_loader([self.url])

    def open_in_browser(self, e):
        # Open in OMERO.web
        wx.LaunchDefaultBrowser(self.url)

    def update_thumbnail(self, bitmap):
        # Replace the temporary loading icon with a thumbnail image
        if not self.__nonzero__() or self.IsBeingDeleted():
            # Skip update if the tile has already been deleted from the panel
            return
        if self.loading is not None:
            # Remove the loading widget
            self.loading.Destroy()
        self.bitmap = bitmap
        self.Refresh()

    def OnPaint(self, evt):
        # Custom paint handler to display image/label/selection marker.
        dc = wx.PaintDC(self)
        dc.Clear()
        if self.bitmap is not None:
            dc.DrawBitmap(self.bitmap, (self.size_x - self.bitmap.Width) // 2,
                          ((self.size_x - self.bitmap.Height) // 2) + 20)
        rect = wx.Rect(0, 0, self.size_x, self.size_x + 20)
        dc.DrawLabel(self.shortname, rect, alignment=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_TOP)
        if self.selected:
            dc.SetPen(wx.Pen("SLATE BLUE", 3, style=wx.PENSTYLE_SOLID))
        else:
            dc.SetPen(wx.Pen("GREY", 1, style=wx.PENSTYLE_SOLID))
        dc.SetBrush(wx.Brush("BLACK", wx.TRANSPARENT))
        dc.DrawRectangle(rect)
        return dc


class TilePanel(wx.ScrolledWindow):
    """
    A scrollable window which will contain image panels and allow selection of them by drawing a rectangle.
    """

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.select_source = None
        self.select_box = None

        self.credentials = CREDENTIALS

        self.active = True
        self.thumbnail_queue = queue.Queue()
        self.thumbnail_thread = threading.Thread(name="ThumbnailProvider", target=self.thumbnail_loader, daemon=True)
        self.thumbnail_thread.start()

        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_UP, self.on_release)

    def thumbnail_loader(self):
        # Spin and monitor queue
        # Jobs will arrive as tuples of (omero id, thumbnail size, tile update function).
        chunk_size = 10
        LOGGER.debug("Starting thumbnail loader")
        size = 0
        callback_map = {}
        while self.active:
            if self.thumbnail_queue.empty():
                time.sleep(0.1)
            for _ in range(chunk_size):
                if not self.thumbnail_queue.empty():
                    omero_id, size, callback = self.thumbnail_queue.get()
                    callback_map[str(omero_id)] = callback
                else:
                    break
            if callback_map:
                ids_to_fetch = list(callback_map.keys())
                ids_str = '&id='.join(ids_to_fetch)
                url = f"https://{self.credentials.server}/webclient/get_thumbnails/{size}/?&bsession={self.credentials.session_key}&id={ids_str}"
                LOGGER.debug(f"Fetching {url}")
                result = {}
                try:
                    data = requests.get(url, timeout=10)
                    if data.status_code != 200:
                        LOGGER.warning(f"Server error: {data.status_code} - {data.reason}")
                    else:
                        result.update(data.json())
                except requests.exceptions.Timeout:
                    LOGGER.error("URL fetch timed out")
                except Exception:
                    LOGGER.error("Unable to retrieve data", exc_info=True)
                for omero_id, callback in callback_map.items():
                    image_data = result.get(omero_id, "")
                    start_data = image_data.find('/9')
                    if start_data == -1:
                        LOGGER.info(f"No thumbnail data was returned for image {omero_id}")
                        img = self.get_error_thumbnail(size)
                    else:
                        decoded = base64.b64decode(image_data[start_data:])
                        bio = io.BytesIO(decoded)
                        img = wx.Image(bio)
                        if not img.IsOk():
                            LOGGER.info(f"Thumbnail data was invalid for image {omero_id}")
                            img = self.get_error_thumbnail(size)
                        else:
                            img = img.ConvertToBitmap()
                    # Update the tile in question. This must be scheduled on the main GUI thread to avoid crashes.
                    wx.CallAfter(callback, img)
                callback_map = {}

    def deselect_all(self):
        for child in self.GetChildren():
            if isinstance(child, ImagePanel):
                child.selected = False

    def OnMotion(self, evt):
        # Handle drag selection
        if not evt.LeftIsDown():
            # Not dragging
            self.select_source = None
            self.select_box = None
            return
        self.SetFocusIgnoringChildren()
        if self.select_source is None:
            self.select_source = evt.Position
            return
        else:
            self.select_box = wx.Rect(self.select_source, evt.Position)
        if self.select_box.Width < 5 and self.select_box.Height < 5:
            # Don't start selecting until a reasonable box size is drawn
            return
        for child in self.GetChildren():
            if isinstance(child, ImagePanel):
                if not evt.ShiftDown():
                    child.selected = False
                if child.GetRect().Intersects(self.select_box):
                    child.selected = True
        self.Refresh()

    def on_release(self, e):
        # Cease dragging
        self.select_source = None
        self.select_box = None
        self.Refresh()

    def OnPaint(self, e):
        # Draw selection box.
        dc = wx.PaintDC(self)
        dc.SetPen(wx.Pen("BLUE", 3, style=wx.PENSTYLE_SHORT_DASH))
        dc.SetBrush(wx.Brush("BLUE", style=wx.TRANSPARENT))
        if self.select_box is not None:
            dc.DrawRectangle(self.select_box)

    @functools.lru_cache(maxsize=10)
    def get_error_thumbnail(self, size):
        # Draw an image with an error icon. Cache the result since we may need the error icon repeatedly.
        artist = wx.ArtProvider()
        size //= 2
        return artist.GetBitmap(wx.ART_WARNING, size=(size, size))

# TODO: Paginate well loading
