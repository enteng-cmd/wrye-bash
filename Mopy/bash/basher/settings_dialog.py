# -*- coding: utf-8 -*-
#
# GPL License and Copyright Notice ============================================
#  This file is part of Wrye Bash.
#
#  Wrye Bash is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  Wrye Bash is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Wrye Bash; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#  Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2020 Wrye Bash Team
#  https://github.com/wrye-bash
#
# =============================================================================
import os
import subprocess
import webbrowser

from . import BashStatusBar, tabInfo
from .constants import colorInfo, settingDefaults
from .. import balt, barb, bass, bosh, bush, env, exception
from ..balt import colors, Link, Resources
from ..bolt import deprint, GPath
from ..gui import ApplyButton, BusyCursor, Button, CancelButton, Color, \
    ColorPicker, DialogWindow, DropDown, HLayout, HorizontalLine, \
    LayoutOptions, OkButton, PanelWin, Stretch, TextArea, TreePanel, VLayout, \
    WrappingTextMixin, ListBox, Label, Spacer, HBoxedLayout, CheckBox, \
    RadioButton, TextField, OpenButton, ScrollableWindow, ClickableImage, \
    RevertButton, SaveButton, SaveAsButton, DoubleListBox, ATreeMixin
from ..localize import dump_translator

class SettingsDialog(DialogWindow):
    """A dialog for configuring settings, split into multiple pages."""
    _def_size = (700, 450)
    _min_size = (500, 300)

    def __init__(self):
        super(SettingsDialog, self).__init__(Link.Frame, title=_(u'Settings'),
            icon_bundle=Resources.bashBlue, sizes_dict=balt.sizes)
        # Used to keep track of the pages that have changed settings
        self._changed_state = {}
        # Used to keep track of a potential scheduled restart of Wrye Bash in
        # order to apply certain settings
        self._requesting_restart = set()
        self._restart_params = []
        # GUI/Layout Definition
        self._tab_tree = TreePanel(self, _settings_pages, _page_descriptions)
        for leaf_page in self._tab_tree.get_leaf_pages():
            self._changed_state[leaf_page] = False
            leaf_page._mark_changed = self._exec_mark_changed
            leaf_page._request_restart = self._exec_request_restart
##: Not yet ready, will need much more refactoring (#178). We'd need a way to
# have each page and each setting as an object, so that we can pass the search
# term along to each page. Plus TreeCtrl refactoring is needed to easily hide
# non-matching items, etc. Making this work is a very long-term goal.
#        self._search_bar = SearchBar(self)
#        self._search_bar.on_text_changed.subscribe(self._handle_search)
        help_btn = ClickableImage(self, balt.images[u'help.24'].GetBitmap(),
            btn_tooltip=_(u'Open the Wrye Bash readme in a browser.'))
        help_btn.on_clicked.subscribe(self._open_readme)
        ok_btn = OkButton(self)
        ok_btn.on_clicked.subscribe(self._send_ok)
        cancel_btn = CancelButton(self)
        # This will automatically be picked up for the top-right close button
        # by wxPython, due to us using CancelButton
        cancel_btn.on_clicked.subscribe(self._send_closing)
        self._apply_btn = ApplyButton(self)
        self._apply_btn.enabled = False
        self._apply_btn.on_clicked.subscribe(self._send_apply)
        VLayout(border=4, spacing=4, item_expand=True, items=[
#            self._search_bar,
            (self._tab_tree, LayoutOptions(weight=1)),
            HorizontalLine(self),
            HLayout(spacing=5, items=[
                help_btn, Stretch(), ok_btn, cancel_btn, self._apply_btn,
            ]),
        ]).apply_to(self)

    def _exec_mark_changed(self, requesting_page, is_changed):
        """Marks or unmarks the requesting page as changed, and enables or
        disables the Apply button accordingly."""
        self._changed_state[requesting_page] = is_changed
        self._apply_btn.enabled = any(self._changed_state.itervalues())

    def _exec_request_restart(self, requesting_setting, restart_params):
        """Schedules a restart request from the specified setting."""
        self._requesting_restart.add(requesting_setting)
        self._restart_params.extend(restart_params)

    def _open_readme(self):
        """Handles a click on the help button by opening the readme."""
        general_readme = bass.dirs[u'mopy'].join(
            u'Docs', u'Wrye Bash General Readme.html')
        if general_readme.isfile():
            webbrowser.open(general_readme.s)
        else:
            balt.showError(self, _(u'Cannot find General Readme file.'))

    def _send_apply(self):
        """Propagates an Apply button click to all child pages."""
        for leaf_page in self._tab_tree.get_leaf_pages():
            leaf_page.on_apply()
        if self._requesting_restart:
            # A restart has been requested, ask the user whether to do it now
            if balt.askYes(self,
                    _(u'The following settings require Wrye Bash to be '
                      u'restarted before they take effect:')
                    + u'\n\n' + u'\n'.join(
                        u' - %s' % r for r in sorted(self._requesting_restart))
                    + u'\n\n' + _(u'Do you want to restart now?'),
                    title=_(u'Restart Wrye Bash')):
                Link.Frame.Restart(self._restart_params)
            else:
                # User denied the restart, don't bother them again
                self._requesting_restart.clear()
                del self._restart_params[:]

    def _send_closing(self):
        """Propagates a Cancel button click to all child pages."""
        for leaf_page in self._tab_tree.get_leaf_pages():
            leaf_page.on_page_closing()

    def _send_ok(self):
        """Propagates an OK button click to all child pages."""
        self._send_closing()
        self._send_apply()

class _ASettingsPage(WrappingTextMixin, ATreeMixin):
    """Abstract class for all settings pages."""
    def __init__(self, parent, page_desc):
        super(_ASettingsPage, self).__init__(page_desc, parent)
        # Callback to a method that takes the settings page and a boolean,
        # marking the settings in the specified page as changed or not. Used
        # to automatically enable or disable the Apply button.
        self._mark_changed = None
        # Callback to a method that will ask the user to restart Wrye Bash
        # after the settings from all tabs have been applied. It takes two
        # parameters, a user-readable name for the setting that requires the
        # restart and a list of options to pass to the newly started process.
        # Note that the user can deny the restart, so you can't rely on the
        # next start definitely having these parameters passed to it
        ##: The restart parameters here are a smell, see usage in LanguagePage
        self._request_restart = None

    def on_apply(self):
        """Called when the OK or Apply button on the settings dialog is
        clicked. Should apply whatever changes have been made on this page."""

    def on_page_closing(self):
        """Called when the settings dialog is about to be closed."""

class _AScrollablePage(_ASettingsPage, ScrollableWindow): pass
class _AFixedPage(_ASettingsPage, PanelWin): pass

# Colors ----------------------------------------------------------------------
class ColorsPage(_AScrollablePage):
    """Color configuration page."""
    _keys_to_tabs = {
        'mods': _(u'[Mods] '),
        'screens': _(u'[Saves, Screens] '),
        'installers': _(u'[Installers] '),
        'ini': _(u'[INI Edits] '),
        'tweak': _(u'[INI Edits] '),
        'default': _(u'[All] '),
    }

    def __init__(self, parent, page_desc):
        super(ColorsPage, self).__init__(parent, page_desc)
        self.changes = dict()
        #--DropDown
        def _display_text(k):
            return _(self._keys_to_tabs[k.split('.')[0]]) + colorInfo[k][0]
        self.text_key = dict((_display_text(x), x) for x in colors)
        colored = self.text_key.keys()
        colored.sort(key=unicode.lower)
        combo_text = colored[0]
        choiceKey = self.text_key[combo_text]
        self.comboBox = DropDown(self, value=combo_text, choices=colored)
        self.comboBox.on_combo_select.subscribe(lambda _sel: self.OnComboBox())
        #--Color Picker
        self.picker = ColorPicker(self, colors[choiceKey])
        #--Description
        help_ = colorInfo[choiceKey][1]
        self.textCtrl = TextArea(self, init_text=help_, editable=False)
        #--Buttons
        self.default = Button(self, _(u'Reset Color'))
        self.default.on_clicked.subscribe(self.OnDefault)
        self.defaultAll = RevertButton(self, _(u'Reset All Colors'))
        self.defaultAll.on_clicked.subscribe(self.OnDefaultAll)
        self.export_config = SaveAsButton(self, _(u'Export Colors...'))
        self.export_config.on_clicked.subscribe(self.OnExport)
        self.importConfig = OpenButton(self, _(u'Import Colors...'))
        self.importConfig.on_clicked.subscribe(self.OnImport)
        #--Events
        self.picker.on_color_picker_evt.subscribe(self.OnColorPicker)
        #--Layout
        VLayout(border=6, item_expand=True, spacing=5, items=[
            self._panel_text,
            HLayout(items=[
                (self.comboBox, LayoutOptions(expand=True, weight=1)),
                self.picker]),
            (self.textCtrl, LayoutOptions(weight=1)),
            HLayout(spacing=5, item_expand=True, items=[
                Stretch(), self.default, self.defaultAll, self.export_config,
                self.importConfig,
            ]),
        ]).apply_to(self)
        self.comboBox.set_focus()
        self.UpdateUIButtons()

    def GetColorKey(self):
        """Return balt.colors dict key for current combobox selection."""
        return self.text_key[self.comboBox.get_value()]

    @staticmethod
    def UpdateUIColors():
        """Update the Bash Frame with the new colors"""
        with BusyCursor():
            for (className,title,panel) in tabInfo.itervalues():
                if panel is not None:
                    panel.RefreshUIColors()

    def UpdateUIButtons(self):
        # Apply All and Default All
        for key, val in self.changes.items():
            if val == colors[key]:
                del self.changes[key]
        anyChanged = bool(self.changes)
        allDefault = True
        for key in colors:
            if key in self.changes:
                color = self.changes[key]
            else:
                color = colors[key]
            default = color == Color(*settingDefaults['bash.colors'][key])
            if not default:
                allDefault = False
                break
        # Apply and Default
        color_key = self.GetColorKey()
        if color_key in self.changes:
            color = self.changes[color_key]
        else:
            color = colors[color_key]
        default = color == Color(*settingDefaults['bash.colors'][color_key])
        # Update the Buttons, DropDown, and ColorPicker
        if self._mark_changed:
            # If _mark_changed is None, then we're still in the construction
            # phase. The apply button is never going to be on without user
            # input, so this is fine
            self._mark_changed(self, is_changed=anyChanged)
        self.default.enabled = not default
        self.defaultAll.enabled = not allDefault
        self.picker.set_color(color)
        self.comboBox.set_focus_from_kb()

    def OnDefault(self):
        color_key = self.GetColorKey()
        newColor = Color(*settingDefaults['bash.colors'][color_key])
        self.changes[color_key] = newColor
        self.UpdateUIButtons()

    def OnDefaultAll(self):
        for key in colors:
            default = Color(*settingDefaults['bash.colors'][key])
            if colors[key] != default:
                self.changes[key] = default
        self.UpdateUIButtons()

    def on_apply(self):
        for key,newColor in self.changes.iteritems():
            bass.settings['bash.colors'][key] = newColor.to_rgb_tuple()
            colors[key] = newColor
        bass.settings.setChanged('bash.colors')
        self.UpdateUIButtons()
        self.UpdateUIColors()

    def OnExport(self):
        outDir = bass.dirs['patches']
        outDir.makedirs()
        #--File dialog
        outPath = balt.askSave(self, _(u'Export color configuration to:'),
                               outDir, _(u'Colors.txt'), u'*.txt')
        if not outPath: return
        try:
            with outPath.open('w') as out:
                for key in sorted(colors):
                    if key in self.changes:
                        color = self.changes[key]
                    else:
                        color = colors[key]
                    out.write(u'%s: %s\n' % (key, color.to_rgb_tuple()))
        except Exception as e:
            balt.showError(self, _(u'An error occurred writing to ') +
                           outPath.stail + u':\n\n%s' % e)

    def OnImport(self):
        inDir = bass.dirs['patches']
        inDir.makedirs()
        #--File dialog
        inPath = balt.askOpen(self, _(u'Import color configuration from:'),
                              inDir, _(u'Colors.txt'), u'*.txt',
                              mustExist=True)
        if not inPath: return
        try:
            with inPath.open('r') as ins:
                for line in ins:
                    # Format validation
                    if u':' not in line:
                        continue
                    split = line.split(u':')
                    if len(split) != 2:
                        continue
                    key = split[0]
                    # Verify color exists
                    if key not in colors:
                        continue
                    # Parse the color, verify that it's actually valid
                    color_tup = tuple([int(c.strip()) for c
                                       in split[1].strip()[1:-1].split(u',')])
                    if len(color_tup) not in (3, 4):
                        continue
                    for value in color_tup:
                        if value < 0 or value > 255:
                            break
                    else:
                        # All checks passed, save it
                        color = Color(*color_tup)
                        if color == colors[key] and key not in self.changes:
                            continue # skip, identical to our current state
                        self.changes[key] = color
        except Exception as e:
            balt.showError(self,
                _(u'An error occurred reading from ') + inPath.stail +
                u':\n\n%s' % e)
        self.UpdateUIButtons()

    def OnComboBox(self):
        self.UpdateUIButtons()
        color_key = self.GetColorKey()
        description = colorInfo[color_key][1]
        self.textCtrl.text_content = description

    def OnColorPicker(self):
        color_key = self.GetColorKey()
        newColor = self.picker.get_color()
        self.changes[color_key] = newColor
        self.UpdateUIButtons()

    def on_page_closing(self):
        self.comboBox.unsubscribe_handler_()

# Languages -------------------------------------------------------------------
class ConfigureEditorDialog(DialogWindow):
    """A dialog for configuring a localization file editor."""
    _min_size = _def_size = (400, 240)

    def __init__(self, parent):
        del balt.sizes[self.__class__.__name__]
        super(ConfigureEditorDialog, self).__init__(parent,
            title=_(u'Configure Editor'), icon_bundle=Resources.bashBlue,
            sizes_dict=balt.sizes)
        self._editor_location = TextField(self,
            init_text=bass.settings[u'bash.l10n.editor.path'])
        browse_editor_btn = OpenButton(self, _(u'Browse...'),
            btn_tooltip=_(u'Launch a file dialog to interactively choose the '
                          u'editor binary.'))
        browse_editor_btn.on_clicked.subscribe(self._handle_browse)
        self._params_field = TextField(self,
            init_text=bass.settings[u'bash.l10n.editor.param_fmt'])
        self._po_rename_box = CheckBox(self, _(u'Rename to .po'),
            checked=bass.settings[u'bash.l10n.editor.rename_to_po'],
            chkbx_tooltip=_(u"Some gettext editors will not open Wrye Bash's "
                            u'.txt localization files. With this ticked, the '
                            u'file will be renamed to .po before it is opened '
                            u'by the editor, and renamed back to .txt when '
                            u'it is closed.'))
        ok_btn = OkButton(self)
        ok_btn.on_clicked.subscribe(self._handle_ok)
        VLayout(border=6, spacing=4, item_expand=True, items=[
            HBoxedLayout(self, title=_(u'Editor:'), spacing=4, items=[
                (self._editor_location, LayoutOptions(expand=True, weight=1)),
                browse_editor_btn,
            ]),
            Spacer(12),
            HBoxedLayout(self, title=_(u'Parameters:'), item_expand=True,
                item_weight=1, items=[
                VLayout(spacing=4, items=[
                    (self._params_field, LayoutOptions(expand=True, weight=1)),
                    Label(self, _(u"Note: '%s' will be replaced by the path "
                                  u'to the localization file.')),
                    Spacer(4), self._po_rename_box,
                ]),
            ]),
            Stretch(), HLayout(spacing=5, items=[
                Stretch(), ok_btn, CancelButton(self),
            ]),
        ]).apply_to(self)

    def _handle_browse(self):
        """Opens a file dialog to choose the editor."""
        # Don't use mustExist, we want to show an error message for that below
        chosen_editor = balt.askOpen(self, title=_(u'Choose Editor'),
            defaultDir=os.environ.get('ProgramFiles', u''), wildcard=u'*.exe',
            mustExist=True)
        if chosen_editor:
            self._editor_location.text_content = chosen_editor.s

    def _handle_ok(self):
        """Stores all changes that have been made."""
        bass.settings[u'bash.l10n.editor.path'] = \
            self._editor_location.text_content
        bass.settings[u'bash.l10n.editor.param_fmt'] = \
            self._params_field.text_content
        bass.settings[u'bash.l10n.editor.rename_to_po'] = \
            self._po_rename_box.is_checked

##: Quite a bit of duplicate code with the Backups page here (esp. rename)
class LanguagePage(_AScrollablePage):
    """Change the language that the GUI is displayed in."""
    languageMap = {
        u'chinese (simplified)': _(u'Chinese (Simplified)') + u' (简体中文)',
        u'chinese (traditional)': _(u'Chinese (Traditional)') + u' (繁体中文)',
        u'de': _(u'German') + u' (Deutsch)',
        u'pt_opt': _(u'Portuguese') + u' (português)',
        u'italian': _(u'Italian') + u' (italiano)',
        u'japanese': _(u'Japanese') + u' (日本語)',
        u'russian': _(u'Russian') + u' (ру́сский язы́к)',
        u'english': _(u'English') + u' (English)',
    }

    def __init__(self, parent, page_desc):
        super(LanguagePage, self).__init__(parent, page_desc)
        # Used to map localized radio button names back to internal language
        # names
        self._button_to_lang = {}
        all_langs = [l.body for l in self._gather_l10n()
                     if l.csbody[-3:] != u'new']
        # Insert English since there's no localization file for that
        if GPath('english') not in all_langs:
            all_langs.append(GPath(u'english'))
        localized_langs = [self.languageMap.get(l.s.lower(), l.s)
                           for l in all_langs]
        lang_layouts = []
        is_first_button = True
        active_lang = u'' # For tooltip further down
        for internal_name, localized_name in sorted(zip(
                all_langs, localized_langs), key=lambda lng: lng[1]):
            # Build the radio button for this language, check it if it's for
            # the current language
            lang_button = RadioButton(self, localized_name,
                is_group=is_first_button)
            lang_button.on_checked.subscribe(self._handle_lang_button)
            if self._is_active_lang(internal_name):
                active_lang = self.languageMap[internal_name].split(u' ')[0]
                lang_button.is_checked = True
            is_first_button = False
            # Remember the language that this button corresponds to
            self._button_to_lang[lang_button] = internal_name
            lang_layouts.append(HLayout(items=[Spacer(4), lang_button]))
        self._l10n_list = ListBox(self, isSort=True, isHScroll=True,
            onSelect=self._handle_select_l10n)
        configure_editor_btn = Button(self, _(u'Configure Editor...'),
            btn_tooltip=_(u'Choose the editor to use for editing '
                          u'localizations.'))
        configure_editor_btn.on_clicked.subscribe(self._handle_editor_cfg_btn)
        is_standalone_warning = Label(self,
            _(u'Note: You are using the standalone version and will not able '
              u'to dump localizations.'))
        is_standalone_warning.set_foreground_color(colors.RED)
        is_standalone_warning.visible = bass.is_standalone
        dump_localization_btn = Button(self, _(u'Dump Localization...'),
            btn_tooltip=_(u'Generates an up-to-date version of the '
                          u'localization file for the currently active '
                          u'language (%s).') % active_lang)
        dump_localization_btn.enabled = not bass.is_standalone
        dump_localization_btn.on_clicked.subscribe(self._dump_localization)
        self._edit_l10n_btn = OpenButton(self, _(u'Edit...'),
            btn_tooltip=_(u'Opens the selected localization in an editor. You '
                          u'can configure which editor to use via the '
                          u"'Configure Editor...' button."))
        self._edit_l10n_btn.on_clicked.subscribe(self._edit_l10n)
        self._rename_l10n_btn = Button(self, _(u'Rename...'),
            btn_tooltip=_(u'Rename the selected localization.'))
        self._rename_l10n_btn.on_clicked.subscribe(self._rename_l10n)
        # Populate the list and disable the context buttons by default
        self._populate_l10n_list()
        self._set_context_buttons(btns_enabled=False)
        VLayout(border=6, item_expand=True, spacing=4, items=[
            self._panel_text,
            HBoxedLayout(self, title=_(u'Change Language'),
                items=[VLayout(items=lang_layouts)]),
            (HBoxedLayout(self, title=_(u'Manage Localizations'),
                item_expand=True, item_weight=1, items=[
                    VLayout(spacing=4, item_expand=True, items=[
                        is_standalone_warning,
                        (HLayout(spacing=4, item_expand=True, items=[
                            (self._l10n_list, LayoutOptions(weight=1)),
                            VLayout(spacing=4, item_expand=True, items=[
                                configure_editor_btn, dump_localization_btn,
                                HorizontalLine(self), self._edit_l10n_btn,
                                self._rename_l10n_btn,
                            ]),
                        ]), LayoutOptions(weight=1)),
                    ]),
                ]), LayoutOptions(weight=1)),
        ]).apply_to(self)

    @property
    def _chosen_l10n(self):
        """Returns the localization file that the user has selected. Note that
        this will raise an error if no hidden icon has been selected, so it is
        only safe to call if that has already been checked."""
        return self._l10n_list.lb_get_selected_strings()[0]

    def _dump_localization(self):
        """Dumps out an up-to-date version of the current l10n file."""
        message = _(u'Generate Bash program translator file?') + u'\n\n' + _(
            u'This function is for translating Bash itself (NOT mods) into '
            u'non-English languages. For more info, '
            u'see the Internationalization section of the Advanced Readme.')
        if not balt.askContinue(self, message, 'bash.dump_translator.continue',
                _(u'Dump Localization')): return
        outPath = bass.dirs[u'l10n']
        with BusyCursor():
            outFile = dump_translator(outPath.s, bass.active_locale)
        balt.showOk(self, _(u'Translation keys written to %s') % outFile,
                     _(u'Dump Localization: %s') % outPath.stail)
        # Make the new localization show up in the list
        self._populate_l10n_list()
        # wx unselects here, so disable the context buttons
        self._set_context_buttons(btns_enabled=False)

    def _edit_l10n(self):
        """Opens the selected localization file in an editor."""
        chosen_editor = GPath(bass.settings[u'bash.l10n.editor.path'])
        editor_arg_fmt = bass.settings[u'bash.l10n.editor.param_fmt']
        rename_po = bass.settings[u'bash.l10n.editor.rename_to_po']
        # First, verify that the chosen editor is valid
        if not chosen_editor:
            balt.showError(self, _(u'No localization editor has been chosen. '
                                   u"Please click on 'Configure Editor' to "
                                   u'set one up.'), title=_(u'Invalid Editor'))
            return
        elif not chosen_editor.isfile():
            balt.showError(self, _(u'The chosen editor (%s) does not exist or '
                                   u'is not a file.') % chosen_editor,
                title=_(u'Invalid Editor'))
            return
        # Now we can move on to actually opening the editor
        selected_l10n = bass.dirs[u'l10n'].join(self._chosen_l10n)
        l10n_po_path = selected_l10n.root + u'.po'
        # This is what we'll actually be opening, changed below if rename_po
        final_l10n_path = selected_l10n
        if rename_po:
            # If we have to rename to .po, do that now
            selected_l10n.moveTo(l10n_po_path)
            final_l10n_path = l10n_po_path
        # Construct the final command and pass it to subprocess
        try:
            subprocess.Popen([chosen_editor.s] + [
                (a % final_l10n_path if u'%s' in a else a)
                for a in editor_arg_fmt.split(u' ')], close_fds=True)
            # Tell the user that we've launched the editor and wait until they
            # confirm that they're done using it
            balt.showOk(self, _(u'Your localization editor has been launched '
                                u"to edit '%s'. Once you are done with "
                                u"editing, please close it and click 'OK'.")
                              % selected_l10n, title=_(u'Editor Launched'))
        finally:
            if rename_po:
                # Always undo the .po rename if we did that
                l10n_po_path.moveTo(selected_l10n)

    @staticmethod
    def _gather_l10n():
        """Returns a list of all localization files in the l10n directory."""
        all_l10n_files = []
        for f in bass.dirs[u'l10n'].list():
            if f.cext == u'.txt':
                all_l10n_files.append(f.tail)
        return all_l10n_files

    def _handle_editor_cfg_btn(self):
        """Internal callback, called when the 'Configure Editor...' button has
        been clicked. Shows a dialog for configuring the editor."""
        ConfigureEditorDialog.display_dialog(self)

    def _handle_lang_button(self, _checked):
        """Internal callback, called when one of the language buttons has been
        checked. Marks this page as changed or not."""
        for lang_btn, internal_name in self._button_to_lang.iteritems():
            if lang_btn.is_checked:
                self._mark_changed(self,
                    not self._is_active_lang(internal_name))
                break

    def _handle_select_l10n(self, _lb_dex, _item_text):
        """Internal callback, enables the context buttons once a localization
        has been selected."""
        self._set_context_buttons(btns_enabled=True)

    @staticmethod
    def _is_active_lang(internal_name):
        """Returns True if the specified language is currently active."""
        return bass.active_locale.lower() in internal_name.s.lower()

    @property
    def _l10n_dir(self):
        """Returns the directory in which localizations are stored."""
        return bass.dirs[u'l10n']

    def on_apply(self):
        self._mark_changed(self, False)
        for lang_btn, internal_name in self._button_to_lang.iteritems():
            if lang_btn.is_checked:
                ##: #26, our oldest open issue; This should be a
                # parameterless restart request, with us having saved the
                # new language to some 'early boot' info file
                if self._is_active_lang(internal_name): continue # unchanged
                lang_str = internal_name.s
                self._request_restart(
                    _(u'Language: %s') % self.languageMap[lang_str.lower()],
                    ['--Language', lang_str])

    def _populate_l10n_list(self):
        """Clears and repopulates the localization list."""
        self._l10n_list.lb_set_items([l.s for l in self._gather_l10n()])

    def _rename_l10n(self):
        """Renames the currently selected localization file."""
        new_l10n_name = balt.askText(self,
            _(u'Please enter the new name for this localization file.'),
            title=_(u'Rename Localization'), default=self._chosen_l10n)
        if not new_l10n_name or new_l10n_name == self._chosen_l10n:
            return # user canceled or entered identical name
        new_l10n = self._l10n_dir.join(new_l10n_name)
        old_l10n = self._l10n_dir.join(self._chosen_l10n)
        try:
            env.shellMove(old_l10n, new_l10n, parent=self._native_widget)
        except (exception.CancelError, exception.SkipError):
            return # user canceled
        self._populate_l10n_list()
        # This is equivalent to removing the selected entry and adding a new
        # one, so we need to disable localization-specific buttons
        self._set_context_buttons(btns_enabled=False)

    def _set_context_buttons(self, btns_enabled):
        """Enables or disables all l10n-specific buttons."""
        for ctx_btn in (self._edit_l10n_btn, self._rename_l10n_btn):
            ctx_btn.enabled = btns_enabled

# Status Bar ------------------------------------------------------------------
class StatusBarPage(_AScrollablePage):
    """Settings related to the status bar."""
    def __init__(self, parent, page_desc):
        super(StatusBarPage, self).__init__(parent, page_desc)
        # Used to keep track of each setting's 'changed' state
        self._setting_states = {
            u'app_ver': False,
            u'icon_size': False,
            u'hidden_icons': False,
        }
        # Used to retrieve the Link object for hiding/unhiding a button
        self._tip_to_links = {}
        # GUI/Layout definition
        self._show_app_ver_chk = CheckBox(self, label=_(u'Show App Version'),
            chkbx_tooltip=_(u'Show/hide version numbers for buttons on the '
                            u'status bar.'),
            checked=bass.settings['bash.statusbar.showversion'])
        self._show_app_ver_chk.on_checked.subscribe(self._handle_app_ver)
        self._icon_size_dropdown = DropDown(self,
            value=unicode(bass.settings['bash.statusbar.iconSize']),
            choices=(u'16', u'24', u'32'), auto_tooltip=False)
        self._icon_size_dropdown.tooltip = _(u'Sets the status bar icons to '
                                             u'the selected size in pixels.')
        self._icon_size_dropdown.on_combo_select.subscribe(
            self._handle_icon_size)
        # FIXME(inf) Disabled for now because it doesn't work correctly.
        #  Supposedly crashes too, but for me it just glitches the status bar
        self._icon_size_dropdown.enabled = False
        ##: Create a variant of DoubleListBox that can actually show the icons
        self._icon_lists = DoubleListBox(self,
            left_label=_(u'Visible Buttons'), right_label=_(u'Hidden Buttons'),
            left_btn_tooltip=_(u'Make the selected button visible again.'),
            right_btn_tooltip=_(u'Hide the selected button.'))
        self._icon_lists.move_btn_callback = self._on_move_btn
        self._populate_icon_lists()
        VLayout(border=6, spacing=6, item_expand=True, items=[
            self._panel_text, Spacer(3),
            HBoxedLayout(self, item_border=3, title=_(u'General'), items=[
                VLayout(spacing=6, items=[
                    self._show_app_ver_chk,
                    HLayout(spacing=6, items=[
                        Label(self, _(u'Icon Size:')),
                        self._icon_size_dropdown,
                        Label(self, _(u'(currently disabled due to unsolved '
                                      u'glitches and crashes)'))
                    ]),
                ]),
            ]),
            (HBoxedLayout(self, item_expand=True,
                title=_(u'Manage Hidden Buttons'), items=[self._icon_lists]),
             LayoutOptions(weight=1)),
        ]).apply_to(self)

    def _get_chosen_hidden_icons(self):
        """Returns a set of UIDs that have been chosen for hiding by the
        user."""
        return {self._tip_to_links[x].uid
                for x in self._icon_lists.right_items}

    def _handle_app_ver(self, checked):
        """Internal callback, called when the version checkbox is changed."""
        self._mark_setting_changed(u'app_ver',
            checked != bass.settings['bash.statusbar.showversion'])

    def _handle_icon_size(self, new_selection):
        """Internal callback, called when the icon size dropdown is changed."""
        self._mark_setting_changed(u'icon_size',
            int(new_selection) != bass.settings['bash.statusbar.iconSize'])

    def _is_changed(self, setting_id):
        """Checks if the setting with the specified ID has been changed."""
        return self._setting_states[setting_id]

    def _link_by_uid(self, link_uid):
        """Returns the status bar Link with the specified UID."""
        for link_candidate in self._tip_to_links.itervalues():
            if link_candidate.uid == link_uid:
                return link_candidate
        return None

    ##: This whole API should probably move into _ASettingsPage
    def _mark_setting_changed(self, setting_id, is_changed):
        """Marks the setting with the specified ID as changed or unchanged."""
        self._setting_states[setting_id] = is_changed
        self._mark_changed(self, any(self._setting_states.itervalues()))

    def on_apply(self):
        # Note we skip_refresh all status bar changes in order to do them all
        # at once at the end
        # Show App Version
        if self._is_changed(u'app_ver'):
            bass.settings['bash.statusbar.showversion'] ^= True
            for button in BashStatusBar.buttons:
                button.set_sb_button_tooltip()
            if BashStatusBar.obseButton.button_state:
                BashStatusBar.obseButton.UpdateToolTips()
            # Will change tooltips, so need to repopulate these
            self._populate_icon_lists()
        # Icon Size
        icon_size_changed = self._is_changed(u'icon_size')
        if icon_size_changed:
            bass.settings['bash.statusbar.iconSize'] = \
                int(self._icon_size_dropdown.get_value())
            Link.Frame.statusBar.UpdateIconSizes(skip_refresh=True)
        # Hidden Icons
        hidden_icons_changed = self._is_changed(u'hidden_icons')
        if hidden_icons_changed:
            # Compare old and new hidden, then hide the newly hidden buttons
            # and unhide the newly visible ones
            old_hidden = bass.settings['bash.statusbar.hide']
            new_hidden = self._get_chosen_hidden_icons()
            hidden_added = new_hidden - old_hidden
            hidden_removed = old_hidden - new_hidden
            for to_hide in hidden_added:
                Link.Frame.statusBar.HideButton(
                    self._link_by_uid(to_hide).gButton, skip_refresh=True)
            for to_unhide in hidden_removed:
                Link.Frame.statusBar.UnhideButton(self._link_by_uid(to_unhide),
                    skip_refresh=True)
        # Perform a single update of the status bar if needed
        if hidden_icons_changed or icon_size_changed:
            Link.Frame.statusBar.refresh_status_bar(
                refresh_icon_size=icon_size_changed)
        for setting_key in self._setting_states:
            self._setting_states[setting_key] = False
        self._mark_changed(self, False)

    def _on_move_btn(self):
        """Mark our setting as changed if the hidden icons list no longer
        matches the list of icons that are currently hidden."""
        self._mark_setting_changed(u'hidden_icons',
             self._get_chosen_hidden_icons() != bass.settings[
                 'bash.statusbar.hide'])

    def _populate_icon_lists(self):
        """Clears and repopulates the two icon lists."""
        # Here be dragons, of the tooltip-related kind
        self._tip_to_links.clear()
        hide = bass.settings['bash.statusbar.hide']
        hidden = []
        visible = []
        for link in BashStatusBar.buttons:
            if not link.IsPresent() or not link.canHide: continue
            button = link.gButton
            # Get a title for the hidden button
            if button:
                # If the wx.Button object exists (it was hidden this
                # session), use the tooltip from it
                tip_ = button.tooltip
            else:
                # If the link is an _App_Button, it will have a
                # 'sb_button_tip' attribute
                tip_ = getattr(link, 'sb_button_tip', None) # YAK YAK YAK
            if tip_ is None:
                # No good, use its uid as a last resort
                tip_ = link.uid
            target_link_list = hidden if link.uid in hide else visible
            target_link_list.append(tip_)
            self._tip_to_links[tip_] = link
        self._icon_lists.left_items = visible
        self._icon_lists.right_items = hidden

# Backups ---------------------------------------------------------------------
class BackupsPage(_AFixedPage):
    """Create, manage and restore backups."""
    def __init__(self, parent, page_desc):
        super(BackupsPage, self).__init__(parent, page_desc)
        self._backup_list = ListBox(self, isSort=True, isHScroll=True,
            onSelect=self._handle_backup_selected)
        save_settings_btn = SaveButton(self, _(u'Save Data'),
            btn_tooltip=_(u"Save all of Wrye Bash's settings/data now."))
        save_settings_btn.on_clicked.subscribe(self._save_settings)
        new_backup_btn = Button(self, _(u'New Backup...'),
            btn_tooltip=_(u"Backup all of Wrye Bash's settings/data to an "
                          u'archive file.'))
        new_backup_btn.on_clicked.subscribe(self._new_backup)
        self.restore_backup_btn = Button(self, _(u'Restore...'),
            btn_tooltip=_(u"Restore all of Wrye Bash's settings/data from the "
                          u'selected backup.'))
        self.restore_backup_btn.on_clicked.subscribe(self._restore_backup)
        self.rename_backup_btn = Button(self, _(u'Rename...'),
            btn_tooltip=_(u'Rename the selected backup archive.'))
        self.rename_backup_btn.on_clicked.subscribe(self._rename_backup)
        self.delete_backup_btn = Button(self, _(u'Delete...'),
            btn_tooltip=_(u'Delete the selected backup archive.'))
        self.delete_backup_btn.on_clicked.subscribe(self._delete_backup)
        # These start out disabled, because nothing is selected by default
        self._set_context_buttons(btns_enabled=False)
        self._populate_backup_list()
        VLayout(border=6, spacing=3, item_expand=True, items=[
            self._panel_text,
            (HLayout(spacing=4, item_expand=True, items=[
                (self._backup_list, LayoutOptions(weight=1)),
                VLayout(item_expand=True, spacing=4, items=[
                    save_settings_btn, new_backup_btn, HorizontalLine(self),
                    self.restore_backup_btn, self.rename_backup_btn,
                    self.delete_backup_btn,
                ]),
            ]), LayoutOptions(weight=1)),
        ]).apply_to(self)

    @property
    def _backup_dir(self):
        """Returns the directory into which backups will be saved."""
        return bass.settings['bash.backupPath'] or bass.dirs['modsBash']

    @property
    def _chosen_backup(self):
        """Returns the name of the backup that is currently selected by the
        user. Note that this will raise an error if no backup has been selected
        yet, so it is only safe to call if that has already been checked."""
        return self._backup_list.lb_get_selected_strings()[0]

    def _delete_backup(self):
        """Deletes the currently selected backup."""
        settings_file = self._backup_dir.join(self._chosen_backup)
        try:
            env.shellDelete(settings_file, parent=self._native_widget,
                confirm=True, recycle=True)
        except (exception.CancelError, exception.SkipError): pass
        finally:
            self._populate_backup_list()
            self._set_context_buttons(btns_enabled=False)

    def _handle_backup_selected(self, _lb_dex, _item_text):
        """Internal callback, enables the backup-specific buttons as soon as a
        backup has been selected. There is no way to unselect besides removing
        the selected entry, which is handled in _delete_backup and
        _populate_backup_list."""
        self._set_context_buttons(btns_enabled=True)

    @balt.conversation
    def _new_backup(self):
        """Saves the current settings and data to create a new backup."""
        with BusyCursor(): Link.Frame.SaveSettings()
        settings_file = balt.askSave(self,
            title=_(u'Backup Bash Settings'), defaultDir=self._backup_dir,
            wildcard=u'*.7z', defaultFile=barb.BackupSettings.backup_filename(
                bush.game.fsName))
        if not settings_file: return
        with BusyCursor():
            backup = barb.BackupSettings(settings_file, bush.game.fsName,
                                         bush.game.mods_dir)
        try:
            with BusyCursor(): backup.backup_settings(balt)
        except exception.StateError:
            deprint(u'Backup settings failed', traceback=True)
            backup.warn_message(balt)
        finally:
            self._populate_backup_list()

    def _populate_backup_list(self):
        """Clears and repopulates the backups list."""
        all_backups = [x.s for x in self._backup_dir.list()
                       if barb.BackupSettings.is_backup(x)]
        self._backup_list.lb_set_items(all_backups)
        if not all_backups:
            # If there are no more backups left, we need to disable all
            # backup-specific buttons again
            self._set_context_buttons(btns_enabled=False)

    def _rename_backup(self):
        """Renames the currently selected backup."""
        new_backup_name = balt.askText(self,
            _(u'Please enter the new name for this backup.'),
            title=_(u'Rename Backup'), default=self._chosen_backup)
        if not new_backup_name or new_backup_name == self._chosen_backup:
            return # user canceled or entered identical name
        new_backup = self._backup_dir.join(new_backup_name)
        old_backup = self._backup_dir.join(self._chosen_backup)
        try:
            env.shellMove(old_backup, new_backup, parent=self._native_widget)
        except (exception.CancelError, exception.SkipError):
            return # user canceled
        self._populate_backup_list()
        # This is equivalent to removing the selected entry and adding a new
        # one, so we need to disable backup-specific buttons
        self._set_context_buttons(btns_enabled=False)

    @balt.conversation
    def _restore_backup(self):
        """Restores the currently selected backup."""
        if not balt.askYes(self, u'\n\n'.join([
            _(u"Are you sure you want to restore your Bash settings from "
              u"'%s'?") % self._chosen_backup,
            _(u'This will force a restart of Wrye Bash once your settings are '
              u'restored.')]), _(u'Restore Bash Settings?')):
            return
        # former may be None
        settings_file = self._backup_dir.join(self._chosen_backup)
        with BusyCursor():
            restore_ = barb.RestoreSettings(settings_file)
        backup_dir = None
        restarting = False
        try:
            with BusyCursor():
                backup_dir = restore_.extract_backup()
            error_msg, error_title = restore_.incompatible_backup_error(
                bush.game.fsName)
            if error_msg:
                balt.showError(self, error_msg, error_title)
                return
            error_msg, error_title = restore_.incompatible_backup_warn()
            if error_msg and not balt.askWarning(self, error_msg, error_title):
                return
            restarting = True
            balt.showInfo(self, '\n'.join([
                _(u'Your Bash settings have been successfully extracted.'),
                _(u'Backup Path: ') + settings_file.s, u'', _(u'Before the '
                  u'settings can take effect, Wrye Bash must restart.'), _(
                u'Click OK to restart now.')]), _(u'Bash Settings Extracted'))
            try: # we currently disallow backup and restore on the same boot
                bass.sys_argv.remove('--backup')
            except ValueError:
                pass
            Link.Frame.Restart(['--restore'], ['--filename', backup_dir.s])
        except exception.BoltError as e:
            deprint(u'Restore settings failed:', traceback=True)
            restore_.warn_message(balt, e.message)
        finally:
            if not restarting and backup_dir is not None:
                barb.RestoreSettings.remove_extract_dir(backup_dir)

    @staticmethod
    def _save_settings():
        """Saves all settings and data right now."""
        with BusyCursor():
            Link.Frame.SaveSettings()

    def _set_context_buttons(self, btns_enabled):
        """Enables or disables all backup-specific buttons."""
        for ctx_btn in (self.restore_backup_btn, self.rename_backup_btn,
                        self.delete_backup_btn):
            ctx_btn.enabled = btns_enabled

class TrustedBinariesPage(_AFixedPage):
    """Change which binaries are trusted and which aren't."""
    def __init__(self, parent, page_desc):
        super(TrustedBinariesPage, self).__init__(parent, page_desc)
        self._binaries_list = DoubleListBox(self,
            left_label=_(u'Trusted Binaries'),
            right_label=_(u'Untrusted Binaries'),
            left_btn_tooltip=_(u'Mark the selected binary as trusted.'),
            right_btn_tooltip=_(u'Mark the selected binary as untrusted.'))
        self._binaries_list.move_btn_callback = self._check_changed
        import_btn = OpenButton(self, _(u'Import...'),
            btn_tooltip=_(u'Import list of allowed/disallowed binaries from a '
                          u'.txt file. This also allows more fine-grained '
                          u'control over trusted binary versions.'))
        import_btn.on_clicked.subscribe(self._import_lists)
        export_btn = SaveAsButton(self, _(u'Export...'),
            btn_tooltip=_(u'Export list of allowed/disallowed binaries to a '
                          u'.txt file. This also allows more fine-grained '
                          u'control over trusted binary versions.'))
        export_btn.on_clicked.subscribe(self._export_lists)
        self._populate_binaries()
        VLayout(border=6, spacing=3, item_expand=True, items=[
            self._panel_text,
            (self._binaries_list, LayoutOptions(weight=1)),
            HLayout(spacing=4, items=[Stretch(), import_btn, export_btn]),
        ]).apply_to(self)

    def _check_changed(self):
        good_changed = self._binaries_list.left_items != bass.settings[
            u'bash.installers.goodDlls'].keys()
        bad_changed = self._binaries_list.right_items != bass.settings[
            u'bash.installers.badDlls'].keys()
        self._mark_changed(self, good_changed or bad_changed)
        self.pnl_layout()

    ##: Here be dragons, especially in the import method
    def _export_lists(self):
        textDir = bass.dirs['patches']
        textDir.makedirs()
        #--File dialog
        title = _(u'Export list of allowed/disallowed plugin DLLs to:')
        file_ = bush.game.Se.se_abbrev + u' ' + _(u'DLL permissions') + u'.txt'
        textPath = balt.askSave(self, title=title, defaultDir=textDir,
            defaultFile=file_, wildcard=u'*.txt')
        if not textPath: return
        with textPath.open('w',encoding='utf-8-sig') as out:
            out.write(u'goodDlls '+_(u'(those dlls that you have chosen to allow to be installed)')+u'\r\n')
            if bass.settings['bash.installers.goodDlls']:
                for dll in bass.settings['bash.installers.goodDlls']:
                    out.write(u'dll:'+dll+u':\r\n')
                    for index, version in enumerate(bass.settings['bash.installers.goodDlls'][dll]):
                        out.write(u'version %02d: %s\r\n' % (index, version))
            else: out.write(u'None\r\n')
            out.write(u'badDlls '+_(u'(those dlls that you have chosen to NOT allow to be installed)')+u'\r\n')
            if bass.settings['bash.installers.badDlls']:
                for dll in bass.settings['bash.installers.badDlls']:
                    out.write(u'dll:'+dll+u':\r\n')
                    for index, version in enumerate(bass.settings['bash.installers.badDlls'][dll]):
                        out.write(u'version %02d: %s\r\n' % (index, version))
            else: out.write(u'None\r\n')

    def _import_lists(self):
        textDir = bass.dirs['patches']
        textDir.makedirs()
        #--File dialog
        defFile = bush.game.Se.se_abbrev + u' ' + _(
            u'dll permissions') + u'.txt'
        title = _(u'Import list of allowed/disallowed plugin DLLs from:')
        textPath = balt.askOpen(self, title=title, defaultDir=textDir,
            defaultFile=defFile, wildcard=u'*.txt', mustExist=True)
        if not textPath: return
        message = (_(u'Merge permissions from file with current dll permissions?')
                   + u'\n' +
                   _(u"('No' Replaces current permissions instead.)")
                   )
        replace = not balt.askYes(Link.Frame, message,
                                  _(u'Merge permissions?'))
        try:
            with textPath.open('r',encoding='utf-8-sig') as ins:
                Dlls = {'goodDlls':{},'badDlls':{}}
                for line in ins:
                    line = line.strip()
                    if line.startswith(u'goodDlls'):
                        current = Dlls['goodDlls']
                    if line.startswith(u'badDlls'):
                        current = Dlls['badDlls']
                    elif line.startswith(u'dll:'):
                        dll = line.split(u':',1)[1].strip().rstrip(u':')
                        current.setdefault(dll,[])
                    elif line.startswith(u'version'):
                        ver = line.split(u':',1)[1]
                        ver = eval(ver)
                        current[dll].append(ver)
            # FIXME don't update immediately
            if not replace:
                self._binaries_list.left_items = list(
                    set(self._binaries_list.left_items) |
                    set(Dlls['goodDlls']))
                self._binaries_list.right_items = list(
                    set(self._binaries_list.right_items) |
                    set(Dlls['badDlls']))
            else:
                self._binaries_list.left_items = Dlls['goodDlls'].keys()
                self._binaries_list.right_items = Dlls['badDlls'].keys()
        except UnicodeError:
            balt.showError(self,
                _(u'Wrye Bash could not load %s, because it is not saved in '
                  u'UTF-8 format.  Please resave it in UTF-8 format and try '
                  u'again.') % textPath.s)
        except Exception:
            deprint(u'Error reading', textPath.s, traceback=True)
            balt.showError(self,
                _(u'Wrye Bash could not load %s, because there was an error '
                  u'in the format of the file.') % textPath.s)
        finally:
            self._check_changed()

    def on_apply(self):
        def merge_versions(dll_source, target_dict, source_dict):
            """Helper function to merge versions for each DLL in dll_source
            from source_dict into target_dict. Can't just use sets for this
            since lists aren't hashable."""
            for d in dll_source:
                # Merge the new good versions with the old ones, if any
                prev_vers = target_dict.get(d, [])
                new_vers = [x for x in source_dict[d] if x not in prev_vers]
                target_dict[d] = prev_vers + new_vers
                # Finally, remove the entry from the dict it was previously in
                del source_dict[d]
        bad_dlls_dict = bass.settings['bash.installers.badDlls']
        good_dlls_dict = bass.settings['bash.installers.goodDlls']
        # Determine which have been moved to/from the bad DLLs list
        old_bad = set(bad_dlls_dict)
        new_bad = set(self._binaries_list.right_items)
        bad_added = new_bad - old_bad
        bad_removed = old_bad - new_bad
        merge_versions(dll_source=bad_added, target_dict=bad_dlls_dict,
            source_dict=good_dlls_dict)
        merge_versions(dll_source=bad_removed, target_dict=good_dlls_dict,
            source_dict=bad_dlls_dict)
        # Force the settings to be saved and BAIN to update its good/bad caches
        bass.settings.setChanged('bash.installers.badDlls')
        bass.settings.setChanged('bash.installers.goodDlls')
        bosh.bain.Installer.badDlls(force_recalc=True)
        bosh.bain.Installer.goodDlls(force_recalc=True)
        self._mark_changed(self, False)

    def _populate_binaries(self):
        self._binaries_list.left_items = bass.settings[
            u'bash.installers.goodDlls'].keys()
        self._binaries_list.right_items = bass.settings[
            u'bash.installers.badDlls'].keys()

    @staticmethod
    def should_appear():
        # Currently we only allow a few special types of binaries
        return bool(bush.game.Sd.sd_abbrev or
                    bush.game.Se.se_abbrev or
                    bush.game.Sp.sp_abbrev)

# Page Definitions ------------------------------------------------------------
_settings_pages = {
    _(u'Appearance'): {
        _(u'Colors'): ColorsPage,
        _(u'Language'): LanguagePage,
        _(u'Status Bar'): StatusBarPage,
    },
    _(u'Backups'): BackupsPage,
    _(u'Trusted Binaries'): TrustedBinariesPage,
}

_page_descriptions = {
    _(u'Appearance'):
        _(u'Personalize various aspects of how Wrye Bash looks, including '
          u'colors and some GUI options.'),
    _(u'Appearance') + u'/' + _(u'Colors'):
        _(u'Change colors of various GUI components.'),
    _(u'Appearance') + u'/' + _(u'Language'):
        _(u'Change the language that Wrye Bash is displayed in and manage '
          u'localizations.'),
    _(u'Appearance') + u'/' + _(u'Status Bar'):
        _(u'Change settings related to the status bar at the bottom and '
          u'manage hidden buttons.'),
    _(u'Backups'):
        _(u'Create, manage and restore backups of Wrye Bash settings and '
          u'other data. Click on a backup to manage it.'),
    _(u'Confirmations'):
        _(u"Enable or disable popups with a 'Don't show this in the future' "
          u'option.'),
    _(u'Trusted Binaries'):
        _(u'Change which binaries (DLLs, EXEs, etc.) you trust. Untrusted '
          u'binaries will be skipped by BAIN when installing packages.')
}
