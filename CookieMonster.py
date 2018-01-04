#
#   CookieMonster Burp extension
#
#   Copyright (C) 2017 Paul Taylor
#

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this output_file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
#    limitations under the License.

from burp import IBurpExtender, ISessionHandlingAction, ICookie, ITab

from javax.swing import \
    JScrollPane, Scrollable, JPanel, \
    Box, BoxLayout, BorderFactory, JSeparator, \
    JLabel, JTextField, JButton, JComboBox, \
    JList, DefaultListModel, ListSelectionModel, \
    JMenuItem, JPopupMenu, \
    JFileChooser

from java.awt import Desktop, Toolkit
from java.awt.event import ActionListener
from java.awt.datatransfer import DataFlavor, StringSelection

from java.net import URI
from java.io import File
from java.lang import System

from subprocess import Popen, PIPE

from json import loads as json_loads


class cb():

    callbacks = None

    def __init__(self, callbacks):
        cb.callbacks = callbacks


class PhantomJS():

    uri = "http://phantomjs.org/api/command-line.html"

    script_name = "BApp.CookieMonster.phantomjs.tmp"
    script_path = None
    script_data = """\
var system = require("system");
var output = [];
url = system.args[1];
timeout = parseInt(system.args[2]);

var page = require("webpage").create();
page.open(url, function(status) {
    setInterval(function() {
        output.push(phantom.cookies);
        var pageElements = [];
        output.push(pageElements);
        console.log(JSON.stringify(output));
        phantom.exit();
    }, timeout);
});
"""

    @staticmethod
    def find_binary(parent):
        fileChooser = JFileChooser()
        fileChooser.setCurrentDirectory(File(System.getProperty("user.home")))
        result = fileChooser.showOpenDialog(parent)
        if (result == JFileChooser.APPROVE_OPTION):
            return fileChooser.getSelectedFile().getAbsolutePath()

    @staticmethod
    def read(binary, args, url, timeout):
        cmdline = " ".join([binary, args, PhantomJS.script_path, url, timeout])
        cb.callbacks.printOutput("Executing: " + cmdline)
        result = Popen(cmdline, shell=True, stdout=PIPE)
        return json_loads(result.stdout.read().strip(' \t\n\r'))

    def __init__(self):

        PhantomJS.script_path = System.getProperty("java.io.tmpdir") + \
                                                    "/" + PhantomJS.script_name

        file = open(PhantomJS.script_path, "w")
        file.write(PhantomJS.script_data)
        file.close()

        cb.callbacks.printOutput("Script written to: " +
                                 PhantomJS.script_path)


class Cookie(ICookie):

    def getDomain(self):
        return self.cookie_domain

    def getPath(self):
        return self.cookie_path

    def getExpiration(self):
        return self.cookie_expiration

    def getName(self):
        return self.cookie_name

    def getValue(self):
        return self.cookie_value

    def __init__(self, cookie_domain=None, cookie_name=None, cookie_value=None,
                 cookie_path=None, cookie_expiration=None):
        self.cookie_domain = cookie_domain
        self.cookie_name = cookie_name
        self.cookie_value = cookie_value
        self.cookie_path = cookie_path
        self.cookie_expiration = cookie_expiration


class CookieCollection():

    def getNames(self):
        return list(self.cookies.keys())

    def listNames(self):
        return ",".join(self.getNames())

    def setValue(self, cookie_name, cookie_value):
        self.cookies[cookie_name].cookie_value = cookie_value

    def getValue(self, cookie_name):
        return self.cookies[cookie_name].getValue()

    def getCookie(self, cookie_name):
        return self.cookies[cookie_name]

    def setDomain(self, cookie_name, cookie_domain):
        self.cookies[cookie_name].cookie_domain = cookie_domain

    def setPath(self, cookie_name, cookie_path):
        self.cookies[cookie_name].cookie_path = cookie_path

    def setExpiration(self, cookie_name, cookie_expiration):
        self.cookies[cookie_name].cookie_expiration = cookie_expiration

    def __init__(self, cookie_domain, cookie_names):
        self.cookie_domain = cookie_domain
        self.cookies = {}
        for cookie_name in cookie_names:
            self.cookies[cookie_name] = Cookie(cookie_domain, cookie_name)


class SHA_panel(JPanel):

    def button_remove_pressed(self, msg):
        selected_indices = self.List.getSelectedIndices()
        selected_elements = []

        for selected_index in selected_indices:
            selected_elements.append(
                                self.listModel.getElementAt(selected_index)
                                )

        for sha in cb.callbacks.getSessionHandlingActions():
            actionname = sha.getActionName()
            if actionname in selected_elements:
                    cb.callbacks.removeSessionHandlingAction(sha)
                    self.listModel.removeElement(actionname)

    def getAllElements(self):
        listElements = []
        for x in range(self.listModel.getSize()):
            listElements.append(self.listModel.getElementAt(x))
        return listElements

    def __init__(self):

        self.setBorder(
            BorderFactory.createTitledBorder(
                            "Registered session handling actions"
                            )
            )

        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))
        self._rowpanel1 = JPanel()
        self._rowpanel1.setLayout(BoxLayout(self._rowpanel1, BoxLayout.X_AXIS))

        self.listModel = DefaultListModel()

        self.List = JList(self.listModel)

        self.List.setSelectionMode(
                    ListSelectionModel.MULTIPLE_INTERVAL_SELECTION
                    )
        self.List.setSelectedIndex(0)
        self.List.setVisibleRowCount(5)

        self.ScrollPane = JScrollPane(self.List)

        self.remove_button = JButton(
                                "De-register selected",
                                actionPerformed=self.button_remove_pressed
                            )

        self._rowpanel1.add(self.ScrollPane)
        self._rowpanel1.add(self.remove_button)

        self.add(self._rowpanel1)


class SHA(ISessionHandlingAction):

    sha_panel = SHA_panel()

    def __init__(self):

        if self.getActionName() in SHA.sha_panel.getAllElements():
            return

        cb.callbacks.registerSessionHandlingAction(self)

        action_name = self.getActionName()

        SHA.sha_panel.listModel.addElement(action_name)


class SHA_Fetch_Update_Cookies(SHA):

    def __init__(self, phantomjs_bin, phantomjs_args, url,
                 timeout, cookie_domain, cookie_names):
        self.phantomjs_bin = phantomjs_bin
        self.phantomjs_args = phantomjs_args
        self.url = url
        self.timeout = timeout
        self.cookie_domain = cookie_domain
        self.cookies_to_update = CookieCollection(cookie_domain, cookie_names)

        super(SHA_Fetch_Update_Cookies, self).__init__()

    def getActionName(self):
        return "Get cookies (" + self.cookie_domain + "): " + \
                self.cookies_to_update.listNames()

    def performAction(self, currentRequest, macroItems):
        cookies_from_phantom = PhantomJS.read(
                                              self.phantomjs_bin,
                                              self.phantomjs_args,
                                              self.url,
                                              self.timeout
                                            )[0]
        for cookie in cookies_from_phantom:
            cookie_name = cookie[u"name"]
            if cookie_name in self.cookies_to_update.getNames():
                self.cookies_to_update.setValue(cookie_name, cookie[u"value"])
                cb.callbacks.printOutput(
                                        "Cookie set: " +
                                        cookie_name + "=" +
                                        cookie[u"value"]
                                        )
                cb.callbacks.updateCookieJar(
                    self.cookies_to_update.getCookie(cookie_name)
                    )


class SHA_Remove_Cookies(SHA):

    def __init__(self, cookie_names=None):
        if cookie_names is not None:
            self.empty_all = False
            self.cookies_to_remove = CookieCollection(None, cookie_names)
        else:
            self.empty_all = True

        super(SHA_Remove_Cookies, self).__init__()

    def getActionName(self):
        return "Empty cookie jar" \
            if self.empty_all is True \
            else "Remove cookies: " + self.cookies_to_remove.listNames()

    def performAction(self, currentRequest, macroItems):
        cookies = cb.callbacks.getCookieJarContents()

        cookies_to_remove_names = self.cookies_to_remove.getNames()

        for cookie in cookies:
            cookie_name = cookie.getName()
            if cookies_to_remove_names is None \
                    or cookie_name in cookies_to_remove_names:
                self.cookies_to_remove.setDomain(
                                        cookie_name,
                                        cookie.getDomain()
                                        )
                self.cookies_to_remove.setPath(
                                        cookie_name,
                                        cookie.getPath()
                                        )
                self.cookies_to_remove.setExpiration(
                                        cookie_name,
                                        cookie.getExpiration()
                                        )
                cb.callbacks.updateCookieJar(
                                self.cookies_to_remove.getCookie(cookie_name)
                                )
                cb.callbacks.stdOutput("Removed cookie: " + cookie_name)


class PTTextField(JPanel):

    def getName(self):
        return self._name

    def setText(self, text):
        self._textfield.setText(text)

    def getText(self):
        return self._textfield.getText()

    def __init__(self, name, label, text, function=None, button=None):

        length = 1000
        self._name = name
        self._label = JLabel(label)
        self._textfield = JTextField(length) \
            if function is None \
            else JTextField(length, actionPerformed=function)
        self.add(self._label)
        self.add(self._textfield)
        if button is not None:
            self._button = button
            self.add(self._button)
        self.setBorder(BorderFactory.createEmptyBorder(5, 5, 5, 5))
        self._textfield.setText("0" * length)
        self._textfield.setMaximumSize(self._textfield.getPreferredSize())
        self.setMaximumSize(self.getPreferredSize())
        self.setText(text)
        self.setLayout(BoxLayout(self, BoxLayout.X_AXIS))


class PTPopUpMenu(JPopupMenu):

    def __init__(self, target):
        self.target = target
        for item in self.getItems():
            self.add(item)


class ListPopUpMenu(PTPopUpMenu):

    def actioncut(self, msg):
        self.actioncopy(msg)
        self.target.removeSelected()

    def actioncopy(self, msg):
        self.target.copySelected()

    def actionpaste(self, msg):
        clipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
        transferable = clipboard.getContents(self)
        pasted_text = transferable.getTransferData(DataFlavor.stringFlavor)

        # input checking in addelements and addelement will filter
        # trim whitespace, filter blank lines, etc

        self.target.addelements(pasted_text, True)

    def getItems(self):
        return [
                JMenuItem("Cut", actionPerformed=self.actioncut),
                JMenuItem("Copy", actionPerformed=self.actioncopy),
                JMenuItem("Paste", actionPerformed=self.actionpaste)
            ]


class PTListPanel(JPanel):

    def copySelected(self):
        selected = self.getSelectedElements(True)
        if len(selected) > 0:
            cb.callbacks.printOutput("Copied to clipboard:")
            cb.callbacks.printOutput(selected)
            clipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
            clipboard.setContents(StringSelection(selected), None)

    def getSelectedElements(self, asString=False):
        SelectedElements = []
        selected = self.Selected()
        for element in selected:
            SelectedElements.append(self.getElementByPos(element))
        return SelectedElements \
            if not asString else "\n".join(SelectedElements)

    def getAllElements(self, asString=False):
        listElements = []
        listModel = self.List.getModel()
        for x in range(listModel.getSize()):
            listElements.append(listModel.getElementAt(x))
        return listElements if not asString else "\n".join(listElements)

    def getElementByPos(self, pos):
        return self.List.getModel().getElementAt(pos)

    def Selected(self, reverse=False):
        selected = sorted(self.List.getSelectedIndices())
        return selected if not reverse else list(reversed(selected))

    def remove(self, pos):
        model = self.List.getModel()
        model.remove(pos)

    def removeAllElements(self):
        model = self.List.getModel()
        model.removeAllElements()

    def addelement(self, entry):
        to_add = entry.strip(' \t\n\r')
        if to_add not in self.getAllElements() and len(to_add) > 0:
            self.List.getModel().addElement(to_add)

    def addelements(self, entries, lines=False):
        if entries is not None:
            if lines:
                entries = entries.splitlines()
            for element in entries:
                self.addelement(element)

    def removeSelected(self):
        selected = self.Selected(True)
        for index in selected:
            self.remove(index)

    def _button_add_pressed(self, msg):
        to_add = self._addtextbox.getText()
        self.addelement(to_add)

    def _button_del_pressed(self, msg):
        selected = self.Selected(True)
        if len(selected) == 1:
            self._addtextbox.setText(self.getElementByPos(selected[0]))
        self.removeSelected()

    def _button_clear_pressed(self, msg):
        self.removeAllElements()

    def __init__(self, title, listElements):

        self.setBorder(
                BorderFactory.createTitledBorder(
                                BorderFactory.createEmptyBorder(),
                                title
                            )
            )
        listModel = DefaultListModel()

        self.List = JList(listModel)

        self.List.setComponentPopupMenu(ListPopUpMenu(self))

        self.List.setSelectionMode(
                    ListSelectionModel.MULTIPLE_INTERVAL_SELECTION
                    )
        self.List.setSelectedIndex(0)
        self.List.setVisibleRowCount(5)

        self.addelements(listElements)

        ScrollPane = JScrollPane(self.List)
        addButton = JButton(
                        "^ Add ^",
                        actionPerformed=self._button_add_pressed
                        )
        delButton = JButton(
                        "v Remove selected v",
                        actionPerformed=self._button_del_pressed
                        )
        clearButton = JButton(
                        "Clear all",
                        actionPerformed=self._button_clear_pressed
                        )

        self._addtextbox = PTTextField(
                            "add",
                            "Enter cookie name: ",
                            "", self._button_add_pressed
                            )

        self._addtextbox.setBorder(BorderFactory.createEmptyBorder(5, 5, 5, 5))

        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))
        self.add(ScrollPane)

        self._buttonspanel = JPanel()

        self._buttonspanel.setLayout(BoxLayout(
                                        self._buttonspanel,
                                        BoxLayout.LINE_AXIS
                                     ))
        self._buttonspanel.add(self._addtextbox)

        self._addtextbox.add(addButton)
        self._addtextbox.add(delButton)
        self._addtextbox.add(clearButton)

        self.add(self._buttonspanel)

        model = self.List.getModel()
        model.addElement("0"*500)
        self.List.setMaximumSize(
                              self.List.getPreferredSize()
                                )
        self.setMaximumSize(self.getPreferredSize())
        model.removeElement("0"*500)


class PTSeparator(JSeparator):

    def __init__(self):
        self.setBorder(BorderFactory.createEmptyBorder(0, 0, 10, 0))


class Panel_Fetch_Update_Cookies(JPanel):

    def _load_values(self):
        for field in self.fields:
            if "setText" in dir(field) \
                    and "getName" in dir(field) \
                    and field.getName() in self.values.keys():
                value = self.values[field.getName()]
                field.setText(value)

    def _update_values(self):
        for field in self.fields:
            if "getText" in dir(field) and "getName" in dir(field):
                value = field.getText()
                self.values[field.getName()] = value

    def _set_value(self, field_name, value):
        for field in self.fields:
            if "setText" in dir(field) \
                    and "getName" in dir(field) \
                    and field.getName() == field_name:
                self.values[field_name] = value
                field.setText(value)

    def _button_update_pressed(self, msg):
        self._update_values()
        listElements = self._rowpanel2.getAllElements()
        if len(listElements) > 0:
            self.sha_fetch_update = SHA_Fetch_Update_Cookies(
                self.values["phantomJS_path"],
                self.values["phantomJS_args"],
                self.values["url"],
                self.values["duration"],
                self.values["domain"],
                listElements
            )

    def _button_browse_pressed(self, msg):
        binary = PhantomJS.find_binary(self)
        if binary is not None:
            self._set_value("phantomJS_path", binary)

    def _button_args_pressed(self, msg):

        Desktop.getDesktop().browse(URI(PhantomJS.uri))

    def __init__(self):

        self.fields = [
                    PTTextField(
                            "domain",
                            "Set cookies to be valid for domain: ",
                            "bao7uo.com", None
                        ),
                    PTSeparator(),
                    PTTextField(
                            "phantomJS_path", "Path to PhantomJS binary: ",
                            "/usr/bin/phantomjs", None,
                            JButton(
                                "Browse for binary...",
                                actionPerformed=self._button_browse_pressed
                            )
                        ),
                    PTTextField(
                            "phantomJS_args", "Optional PhantomJS arguments: ",
                            "--ignore-ssl-errors=true" +
                            " --web-security=false",
                            None,
                            JButton(
                                PhantomJS.uri,
                                actionPerformed=self._button_args_pressed
                            )
                        ),
                    PTTextField(
                            "url",
                            "Obtain cookies from this URL: ",
                            "https://pages.bao7uo.com/CookieMonster_test.html", None
                        ),
                    PTTextField(
                            "duration",
                            "Milliseconds that PhantomJs should wait " +
                            "for cookies to be set: ",
                            "500", None
                        )
                ]

        self.values = {}

        bordertitle = "Setup a session handling action which uses PhantomJS" +\
            " to obtain named cookies to add to Burp's cookie jar"

        self.setBorder(BorderFactory.createTitledBorder(bordertitle))

        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))

        self._rowpanel1 = JPanel()
        self._rowpanel1.setLayout(BoxLayout(self._rowpanel1, BoxLayout.Y_AXIS))
        self._rowpanel1.setBorder(
                            BorderFactory.createTitledBorder(
                                            BorderFactory.createEmptyBorder(),
                                            "Settings"
                                        )
                        )

        self._rowpanel2 = PTListPanel("Cookies to obtain", ["ClientSideCookie"])

        self._rowpanel3 = JPanel()
        self._rowpanel3.setLayout(BoxLayout(self._rowpanel3, BoxLayout.X_AXIS))

        self._button_update = JButton(
                                "Add a new \"Get cookies\" session handler " +
                                "with these settings for these cookies",
                                actionPerformed=self._button_update_pressed
                            )

        for field in self.fields:
            self._rowpanel1.add(field)

        self._rowpanel3.add(Box.createHorizontalGlue())
        self._rowpanel3.add(self._button_update)

        self.add(self._rowpanel1)
        self.add(self._rowpanel2)
        self.add(self._rowpanel3)


class Panel_Remove_Cookies(JPanel):

    def _button_update_pressed(self, msg):

        listElements = self._rowpanel1.getAllElements()
        if len(listElements) > 0:
            self.SHA_Remove_Cookies = SHA_Remove_Cookies(listElements)

    def __init__(self):

        self.setBorder(BorderFactory.createTitledBorder(
                                        "Setup a session handling action to" +
                                        " remove named cookies from Burp's" +
                                        " cookie jar"))

        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))

        self._rowpanel1 = PTListPanel("Cookies to remove", [])

        self._rowpanel2 = JPanel()
        self._rowpanel2.setLayout(BoxLayout(self._rowpanel2, BoxLayout.X_AXIS))

        self._button_update = JButton(
                                "Add a new \"Remove cookies\" session handler"
                                " for these cookies",
                                actionPerformed=self._button_update_pressed
                            )

        self._rowpanel2.add(Box.createHorizontalGlue())
        self._rowpanel2.add(self._button_update)

        self.add(self._rowpanel1)
        self.add(self._rowpanel2)


class actionlistener(ActionListener):

    def actionPerformed(self, msg):
        selectedItem = self.target._profiles_combo.getSelectedItem()
        if selectedItem is not None:
            self.target.load_fields(selectedItem)

    def __init__(self, target):
        self.target = target


class Panel_Extension(JPanel):

    def get_combo_items(self, combo):

        itemcount = combo.getItemCount()
        items = []
        for i in range(itemcount):
            items.append(combo.getItemAt(i))

        return items

    def load_profiles(self):
        loaded_profiles = cb.callbacks.loadExtensionSetting("Profiles")
        if loaded_profiles is not None:
            self.profiles = loaded_profiles.splitlines()

            items = self.get_combo_items(self._profiles_combo)

            for profile in self.profiles:
                if profile not in items:
                    self._profiles_combo.addItem(profile)
        if len(self.profiles) > 0:
            self.load_fields(
                            "bao7uo WAF bypass" if "bao7uo WAF bypass" in self.profiles
                            else self.profiles[0]
                            )
        else:
            self.save_fields("bao7uo WAF bypass")

    def save_profiles(self):
        cb.callbacks.saveExtensionSetting(
                                            "Profiles",
                                            "\n".join(self.profiles)
                                            if len(self.profiles) > 0
                                            else None
                                           )

    def load_fields(self, profile):
        self.parent.panel_update_cookies._update_values()
        values = self.parent.panel_update_cookies.values
        for key in values.keys():
            loaded = cb.callbacks.loadExtensionSetting(profile + "_" + key)
            if loaded is None:
                break
            self.parent.panel_update_cookies.values[key] = loaded
            self.parent.panel_extension._profile_textfield.setText(profile)
        self.parent.panel_update_cookies._load_values()

        Update_cookies = cb.callbacks.loadExtensionSetting(
                                        profile + "_" + "Update_cookies"
                                        )

        if Update_cookies is not None:
            self.parent.panel_update_cookies._rowpanel2.removeAllElements()
            if len(Update_cookies) > 0:
                self.parent.panel_update_cookies._rowpanel2.addelements(
                                                           Update_cookies, True
                                                        )

        Remove_cookies = cb.callbacks.loadExtensionSetting(
                                        profile + "_" + "Remove_cookies"
                                        )

        if Remove_cookies is not None:
            self.parent.panel_remove_cookies._rowpanel1.removeAllElements()
            if len(Remove_cookies) > 0:
                self.parent.panel_remove_cookies._rowpanel1.addelements(
                                                        Remove_cookies, True
                                                        )

    def save_fields(self, profile, delete=False):

        items = self.get_combo_items(self._profiles_combo)

        if delete:
            if len(items) == 0:
                return
            items_profile_index = items.index(profile)
            if profile in self.profiles:
                self.profiles.remove(profile)
                self.save_profiles()
            if profile in items:
                self._profiles_combo.removeItem(profile)
        else:
            if profile not in self.profiles:
                self.profiles.append(profile)
                self.save_profiles()
            if profile not in items:
                self._profiles_combo.addItem(profile)
                items = self.get_combo_items(self._profiles_combo)
            items_profile_index = items.index(profile)

        self.parent.panel_update_cookies._update_values()

        values = self.parent.panel_update_cookies.values

        if delete:
            values = dict.fromkeys(values.iterkeys(), None)

        for key in values.keys():
            cb.callbacks.saveExtensionSetting(
                            profile + "_" + key, values[key]
                            )

        if delete:
            Update_cookies = None
            Remove_cookies = None
        else:
            Update_cookies = \
                self.parent.panel_update_cookies._rowpanel2.getAllElements(
                                                                    True
                                                                    )
            Remove_cookies = \
                self.parent.panel_remove_cookies._rowpanel1.getAllElements(
                                                                    True
                                                                    )

        cb.callbacks.saveExtensionSetting(
                                            profile + "_" + "Update_cookies",
                                            Update_cookies
                                          )
        cb.callbacks.saveExtensionSetting(
                                            profile + "_" + "Remove_cookies",
                                            Remove_cookies
                                        )

        if self._profiles_combo.getItemCount() > 0:
            if delete:
                select_index = items_profile_index - 1 \
                                if items_profile_index > 0 else 0
            else:
                select_index = items_profile_index

            self._profiles_combo.setSelectedIndex(select_index)

    def _button_delete_profile_pressed(self, msg):
        self.save_fields(self._profiles_combo.getSelectedItem(), True)

    def _button_save_fields_pressed(self, msg):
        self.save_fields(self._profile_textfield.getText())

    def _button_quit_pressed(self, msg):
        cb.callbacks.unloadExtension()

    def __init__(self):

        self.profiles = []

        self.setBorder(
            BorderFactory.createTitledBorder("Profiles")
            )
        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))
        self._rowpanel1 = JPanel()
        self._rowpanel1.setLayout(BoxLayout(self._rowpanel1, BoxLayout.X_AXIS))

        self._profiles_combo = \
            JComboBox(
                      self.profiles
                      )
        self._profiles_combo.addItem("0"*40)
        self._profiles_combo.setMaximumSize(
                                self._profiles_combo.getPreferredSize()
                                )
        self._profiles_combo.removeItem("0" * 40)

        self._profiles_combo_panel = JPanel()
        self._profiles_combo_panel.setLayout(
                                    BoxLayout(
                                        self._profiles_combo_panel,
                                        BoxLayout.X_AXIS
                                        )
                                    )
        self._profiles_combo_panel.setBorder(
                                    BorderFactory.createEmptyBorder(5, 5, 5, 5)
                                    )

        self._quit_panel = JPanel()
        self._quit_panel.setLayout(
                                BoxLayout(self._quit_panel, BoxLayout.X_AXIS)
                            )
        self._quit_panel.setBorder(BorderFactory.createEmptyBorder(5, 5, 5, 5))

        self._profile_textfield = \
            PTTextField(
                        "profile",
                        "Profile name: ",
                        "bao7uo WAF bypass", None,
                        JButton(
                               "Save profile",
                               actionPerformed=self._button_save_fields_pressed
                            )
                    )

        self._profiles_combo_panel.add(self._profiles_combo)

        self._button_delete_profile = \
            JButton(
                    "Delete profile",
                    actionPerformed=self._button_delete_profile_pressed
                    )

        self._profiles_combo_panel.add(self._button_delete_profile)

        self._button_quit = \
            JButton(
                    "Unload CookieMonster extension",
                    actionPerformed=self._button_quit_pressed
                    )

        self._quit_panel.add(self._button_quit)

        self._profiles_combo.addActionListener(actionlistener(self))

        self._rowpanel1.add(self._profiles_combo_panel)
        self._rowpanel1.add(Box.createHorizontalGlue())
        self._rowpanel1.add(self._profile_textfield)

        self._rowpanel1.add(Box.createHorizontalGlue())

        self._rowpanel1.add(self._quit_panel)

        self.add(self._rowpanel1)


class tabpanel(JPanel, Scrollable):

    def getScrollableTracksViewportWidth(self):
        return True

    def getScrollableTracksViewportHeight(self):
        return False

    def getScrollableBlockIncrement(self, a, b, c):
        return 200

    def getScrollableUnitIncrement(self, a, b, c):
        return 200

    def getPreferredScrollableViewportSize(self):
        return self.getPreferredSize()

    def __init__(self):
        self.panel_update_cookies = Panel_Fetch_Update_Cookies()
        self.panel_remove_cookies = Panel_Remove_Cookies()
        self.panel_extension = Panel_Extension()

        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))
        self.setBorder(BorderFactory.createEmptyBorder(20, 20, 20, 20))

        self.add(self.panel_extension)
        self.add(SHA.sha_panel)
        self.add(self.panel_update_cookies)
        self.add(self.panel_remove_cookies)

        self.panel_extension.load_profiles()


class PTTab(ITab):

    def getTabCaption(self):
        return "CookieMonster"

    def getUiComponent(self):
        return self.scrollpane

    def __init__(self):
        self.masterpanel = tabpanel()

        self.scrollpane = JScrollPane(
                            self.masterpanel,
                            JScrollPane.VERTICAL_SCROLLBAR_ALWAYS,
                            JScrollPane.HORIZONTAL_SCROLLBAR_NEVER
                            )

        cb.callbacks.customizeUiComponent(self.masterpanel)
        cb.callbacks.addSuiteTab(self)


class BurpExtender(IBurpExtender):

    extension_name = "CookieMonster"

    def registerExtenderCallbacks(self, callbacks):

        cb(callbacks)
        cb.callbacks.setExtensionName(self.extension_name)

        PhantomJS()
        PTTab()

        cb.callbacks.printOutput(self.extension_name + " extension loaded")

        SHA_Remove_Cookies()
