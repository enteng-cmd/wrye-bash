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

"""Links initialization functions. Each panel's UIList has main and items Links
attributes which are populated here. Therefore the layout of the menus is
also defined in these functions."""
from . import InstallersPanel, InstallersList, INIList, ModList, SaveList, \
    BSAList, ScreensList, MasterList, bEnableWizard, PeopleList, \
    BashStatusBar, BashNotebook
from .. import bass, balt, bush
from ..cint import CBashApi
from ..balt import MenuLink, SeparatorLink, UIList_OpenItems, \
    UIList_OpenStore, UIList_Hide
from ..env import init_app_links
from ..gui import Image
# modules below define the __all__ directive
from .app_buttons import *
from .mods_links import *
from .files_links import *
from .installers_links import *
from .installer_links import *
from .saves_links import *
from .settings_links import *
from .misc_links import *
from .ini_links import *
from .mod_links import *
from .bsa_links import *

#------------------------------------------------------------------------------
def InitStatusBar():
    """Initialize status bar links."""
    def imageList(template):
        return [Image(bass.dirs['images'].join(template % i)) for i in
                (16, 24, 32)]
    def _init_tool_buttons(): # tooldirs must have been initialized
        return (((bass.tooldirs['OblivionBookCreatorPath'],
                  bass.inisettings['OblivionBookCreatorJavaArg']),
                 imageList(u'tools/oblivionbookcreator%s.png'),
                 _(u"Launch Oblivion Book Creator"),
                 {'uid': u'OblivionBookCreator'}),
                ((bass.tooldirs['Tes4GeckoPath'],
                  bass.inisettings['Tes4GeckoJavaArg']),
                 imageList(u'tools/tes4gecko%s.png'),
                 _(u"Launch Tes4Gecko"), {'uid': u'Tes4Gecko'}),
                ((bass.tooldirs['Tes5GeckoPath']),
                imageList(u'tools/tesvgecko%s.png'),
                _(u"Launch TesVGecko"), {'uid': u'TesVGecko'}),
        )
    #--Bash Status/LinkBar
    BashStatusBar.obseButton = obseButton = Obse_Button(uid=u'OBSE')
    BashStatusBar.buttons.append(obseButton)
    BashStatusBar.laaButton = laaButton = LAA_Button(uid=u'LAA')
    BashStatusBar.buttons.append(laaButton)
    BashStatusBar.buttons.append(AutoQuit_Button(uid=u'AutoQuit'))
    BashStatusBar.buttons.append( # Game
        Game_Button(
            bass.dirs['app'].join(bush.game.launch_exe),
            bass.dirs['app'].join(*bush.game.version_detect_file),
            imageList(u'%s%%s.png' % bush.game.fsName.lower()),
            u' '.join((_(u"Launch"),bush.game.displayName)),
            u' '.join((_(u"Launch"),bush.game.displayName,u'%(version)s'))))
    BashStatusBar.buttons.append( #TESCS/CreationKit
        TESCS_Button(
            bass.dirs['app'].join(bush.game.Ck.exe),
            imageList(bush.game.Ck.image_name),
            u' '.join((_(u"Launch"),bush.game.Ck.ck_abbrev)),
            u' '.join((_(u"Launch"),bush.game.Ck.ck_abbrev,u'%(version)s')),
            bush.game.Ck.se_args))
    BashStatusBar.buttons.append( #OBMM
        app_button_factory(bass.dirs['app'].join(u'OblivionModManager.exe'),
                           imageList(u'obmm%s.png'), _(u"Launch OBMM"),
                           uid=u'OBMM'))
    from .constants import toolbar_buttons
    # Just an _App_Button whose path is in bass.tooldirs
    Tooldir_Button = lambda *args: app_button_factory(bass.tooldirs[args[0]],
                                                      *args[1:])
    for tb in toolbar_buttons:
        BashStatusBar.buttons.append(Tooldir_Button(*tb))
    for tb2 in _init_tool_buttons():
        BashStatusBar.buttons.append(app_button_factory(*tb2[:-1], **tb2[-1]))
    BashStatusBar.buttons.append( #Tes4View
        App_Tes4View(
            (bass.tooldirs['Tes4ViewPath'], u'-TES4'), #no cmd argument to force view mode
            imageList(u'tools/tes4view%s.png'),
            _(u"Launch TES4View"),
            uid=u'TES4View'))
    # TODO(inf) Refactor this! I made bush.game.Xe a class precisely for stuff
    #  like this - so add stuff like Xe.command_line_arg and drop these 30+
    #  braindead lines
    BashStatusBar.buttons.append( #Tes4Edit
        App_Tes4View((bass.tooldirs['Tes4EditPath'], u'-TES4 -edit'),
                     imageList(u'tools/tes4edit%s.png'),
                     _(u"Launch TES4Edit"),
                     uid=u'TES4Edit'))
    BashStatusBar.buttons.append( #Tes5Edit
        App_Tes4View((bass.tooldirs['Tes5EditPath'], u'-TES5 -edit'),
                     imageList(u'tools/tes4edit%s.png'),
                     _(u"Launch TES5Edit"),
                     uid=u'TES5Edit'))
    BashStatusBar.buttons.append( #EnderalEdit
        App_Tes4View((bass.tooldirs['EnderalEditPath'], u'-Enderal -edit'),
                     imageList(u'tools/tes4edit%s.png'),
                     _(u"Launch EnderalEdit"),
                     uid=u'EnderalEdit'))
    BashStatusBar.buttons.append(  #SSEEdit
        App_Tes4View((bass.tooldirs['SSEEditPath'], u'-SSE -edit'),
                     imageList(u'tools/tes4edit%s.png'), _(u"Launch SSEEdit"),
                     uid=u'SSEEdit'))
    BashStatusBar.buttons.append(  #Fo4Edit
        App_Tes4View((bass.tooldirs['Fo4EditPath'], u'-FO4 -edit'),
                     imageList(u'tools/tes4edit%s.png'), _(u"Launch FO4Edit"),
                     uid=u'FO4Edit'))
    BashStatusBar.buttons.append(  #Fo3Edit
        App_Tes4View((bass.tooldirs['Fo3EditPath'], u'-FO3 -edit'),
                     imageList(u'tools/tes4edit%s.png'), _(u"Launch FO3Edit"),
                     uid=u'FO3Edit'))
    BashStatusBar.buttons.append(  #FnvEdit
        App_Tes4View((bass.tooldirs['FnvEditPath'], u'-FNV -edit'),
                     imageList(u'tools/tes4edit%s.png'), _(u"Launch FNVEdit"),
                     uid=u'FNVEdit'))
    BashStatusBar.buttons.append(  #TesVGecko
        app_button_factory((bass.tooldirs['Tes5GeckoPath']),
                           imageList(u'tools/tesvgecko%s.png'),
                           _(u"Launch TesVGecko"), uid=u'TesVGecko'))
    BashStatusBar.buttons.append(  #Tes4Trans
        App_Tes4View((bass.tooldirs['Tes4TransPath'], u'-TES4 -translate'),
                     imageList(u'tools/tes4trans%s.png'),
                     _(u"Launch TES4Trans"), uid=u'TES4Trans'))
    BashStatusBar.buttons.append(  #Tes4LODGen
        App_Tes4View((bass.tooldirs['Tes4LodGenPath'], u'-TES4 -lodgen'),
                     imageList(u'tools/tes4lodgen%s.png'),
                     _(u"Launch Tes4LODGen"), uid=u'TES4LODGen'))
    BashStatusBar.buttons.append( #BOSS
        App_BOSS((bass.tooldirs['boss']),
                imageList(u'boss%s.png'),
                _(u"Launch BOSS"),
                uid=u'BOSS'))
    if bass.inisettings['ShowModelingToolLaunchers']:
        from .constants import modeling_tools_buttons
        for mb in modeling_tools_buttons:
            BashStatusBar.buttons.append(Tooldir_Button(*mb))
        BashStatusBar.buttons.append( #Softimage Mod Tool
            app_button_factory((bass.tooldirs['SoftimageModTool'], u'-mod'),
                               imageList(u'tools/softimagemodtool%s.png'),
                               _(u"Launch Softimage Mod Tool"),
                               uid=u'SoftimageModTool'))
    if bass.inisettings['ShowModelingToolLaunchers'] \
            or bass.inisettings['ShowTextureToolLaunchers']:
        BashStatusBar.buttons.append( #Nifskope
            Tooldir_Button('NifskopePath', imageList(u'tools/nifskope%s.png'),
                _(u"Launch Nifskope")))
    if bass.inisettings['ShowTextureToolLaunchers']:
        from .constants import texture_tool_buttons
        for tt in texture_tool_buttons:
            BashStatusBar.buttons.append(Tooldir_Button(*tt))
    if bass.inisettings['ShowAudioToolLaunchers']:
        from .constants import audio_tools
        for at in audio_tools:
            BashStatusBar.buttons.append(Tooldir_Button(*at))
    from .constants import misc_tools
    for mt in misc_tools: BashStatusBar.buttons.append(Tooldir_Button(*mt))
    #--Custom Apps
    dirApps = bass.dirs['mopy'].join(u'Apps')
    badIcons = [Image(bass.dirs['images'].join(u'error_cross_16.png'))] * 3
    def iconList(fileName):
        return [Image(fileName, Image.typesDict[u'ico'], x) for x in
                (16, 24, 32)]
    for pth, icon, description in init_app_links(dirApps, badIcons, iconList):
            BashStatusBar.buttons.append(
                app_button_factory((pth,()), icon, description, canHide=False))
    #--Final couple
    BashStatusBar.buttons.append(App_DocBrowser(uid=u'DocBrowser'))
    BashStatusBar.buttons.append(App_ModChecker(uid=u'ModChecker'))
    BashStatusBar.buttons.append(App_Settings(uid=u'Settings',canHide=False))
    BashStatusBar.buttons.append(App_Help(uid=u'Help',canHide=False))
    if bass.inisettings['ShowDevTools']:
        BashStatusBar.buttons.append(App_Restart(uid=u'Restart'))
        BashStatusBar.buttons.append(App_GenPickle(uid=u'Generate PKL File'))

#------------------------------------------------------------------------------
def InitMasterLinks():
    """Initialize master list menus."""
    #--MasterList: Column Links
    MasterList.column_links.append(SortByMenu(
        sort_options=[Mods_EsmsFirst(), Mods_SelectedFirst()]))
    MasterList.column_links.append(Master_AllowEdit())
    MasterList.column_links.append(Master_ClearRenames())
    #--MasterList: Item Links
    MasterList.context_links.append(Master_ChangeTo())
    MasterList.context_links.append(Master_Disable())

#------------------------------------------------------------------------------
def InitInstallerLinks():
    """Initialize Installers tab menus."""
    #--Column links
    # Sorting and Columns
    InstallersList.column_links.append(SortByMenu(
        sort_options=[Installers_SortActive(), # Installers_SortStructure(),
                      Installers_SortProjects()]))
    InstallersList.column_links.append(ColumnsMenu())
    InstallersList.column_links.append(SeparatorLink())
    # Files Menu
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        files_menu.links.append(Files_Unhide(u'installer'))
        files_menu.links.append(SeparatorLink())
        files_menu.links.append(Installers_CreateNewProject())
        InstallersList.column_links.append(files_menu)
    InstallersList.column_links.append(SeparatorLink())
    #--Actions
    InstallersList.column_links.append(Installers_Refresh())
    InstallersList.column_links.append(Installers_Refresh(full_refresh=True))
    InstallersList.column_links.append(Installers_AddMarker())
    InstallersList.column_links.append(Installers_MonitorInstall())
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_ListPackages())
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_AnnealAll())
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_UninstallAllPackages())
    InstallersList.column_links.append(Installers_UninstallAllUnknownFiles())
    InstallersList.column_links.append(Installers_AutoApplyEmbeddedBCFs())
    #--Behavior
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_AvoidOnStart())
    InstallersList.column_links.append(Installers_Enabled())
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_AutoAnneal())
    if bEnableWizard:
        InstallersList.column_links.append(Installers_AutoWizard())
    InstallersList.column_links.append(Installers_AutoRefreshProjects())
    InstallersList.column_links.append(Installers_AutoRefreshBethsoft())
    InstallersList.column_links.append(Installers_BsaRedirection())
    InstallersList.column_links.append(Installers_RemoveEmptyDirs())
    InstallersList.column_links.append(
        Installers_ConflictsReportShowsInactive())
    InstallersList.column_links.append(Installers_ConflictsReportShowsLower())
    InstallersList.column_links.append(
        Installers_ConflictsReportShowBSAConflicts())
    InstallersList.column_links.append(Installers_WizardOverlay())
    InstallersList.column_links.append(SeparatorLink())
    InstallersList.column_links.append(Installers_GlobalSkips())
    InstallersList.column_links.append(Installers_RenameStrings())
    #--Item links
    if True: #--File Menu
        file_menu = MenuLink(_(u'File..'))
        file_menu.links.append(Installer_Open())
        file_menu.links.append(Installer_Rename())
        file_menu.links.append(Installer_Duplicate())
        file_menu.links.append(Installer_Hide())
        file_menu.links.append(balt.UIList_Delete())
        InstallersList.context_links.append(file_menu)
    if True: #--Open At...
        openAtMenu = InstallerOpenAt_MainMenu(oneDatumOnly=True)
        openAtMenu.links.append(Installer_OpenSearch())
        openAtMenu.links.append(Installer_OpenNexus())
        openAtMenu.links.append(Installer_OpenTESA())
        InstallersList.context_links.append(openAtMenu)
    #--Install, uninstall, etc.
    InstallersList.context_links.append(Installer_OpenReadme())
    InstallersList.context_links.append(Installer_Anneal())
    InstallersList.context_links.append(
        Installer_Refresh(calculate_projects_crc=False))
    InstallersList.context_links.append(Installer_Move())
    InstallersList.context_links.append(SeparatorLink())
    InstallersList.context_links.append(Installer_InstallSmart())
    if True: # Advanced Installation Menu
        installMenu = MenuLink(_(u'Advanced Installation..'))
        installMenu.links.append(Installer_Install())
        installMenu.links.append(Installer_Install('MISSING'))
        installMenu.links.append(Installer_Install('LAST'))
        installMenu.links.append(Installer_Fomod())
        if bEnableWizard:
            wizardMenu = MenuLink(_(u'Wizard Installer..'))
            wizardMenu.links.append(Installer_Wizard(False))
            wizardMenu.links.append(Installer_Wizard(True))
            wizardMenu.links.append(Installer_EditWizard())
            installMenu.links.append(wizardMenu)
        InstallersList.context_links.append(installMenu)
    InstallersList.context_links.append(Installer_Uninstall())
    InstallersList.context_links.append(SeparatorLink())
    if True:  # Package Menu
        packageMenu = MenuLink(_(u'Package..'))
        packageMenu.links.append(Installer_Refresh())
        packageMenu.links.append(SeparatorLink())
        if bush.game.has_achlist:
            packageMenu.links.append(Installer_ExportAchlist())
        packageMenu.links.append(InstallerProject_Pack())
        packageMenu.links.append(InstallerProject_ReleasePack())
        packageMenu.links.append(SeparatorLink())
        packageMenu.links.append(Installer_ListStructure())
        packageMenu.links.append(InstallerProject_Sync())
        packageMenu.links.append(InstallerArchive_Unpack())
        packageMenu.links.append(Installer_CopyConflicts())
        InstallersList.context_links.append(packageMenu)
    #--Build
    if True: #--BAIN Conversion
        conversionsMenu = InstallerConverter_MainMenu()
        conversionsMenu.links.append(InstallerConverter_Create())
        conversionsMenu.links.append(InstallerConverter_ConvertMenu())
        InstallersList.context_links.append(conversionsMenu)
    InstallersList.context_links.append(SeparatorLink())
    InstallersList.context_links.append(Installer_HasExtraData())
    InstallersList.context_links.append(Installer_OverrideSkips())
    InstallersList.context_links.append(Installer_SkipVoices())
    InstallersList.context_links.append(Installer_SkipRefresh())
    InstallersList.context_links.append(SeparatorLink())
    InstallersList.context_links.append(InstallerProject_OmodConfig())
    # Plugin Filter Main Menu
    InstallersPanel.espmMenu.append(Installer_Espm_SelectAll())
    InstallersPanel.espmMenu.append(Installer_Espm_DeselectAll())
    InstallersPanel.espmMenu.append(Installer_Espm_List())
    InstallersPanel.espmMenu.append(SeparatorLink())
    # Plugin Filter Item Menu
    InstallersPanel.espmMenu.append(Installer_Espm_Rename())
    InstallersPanel.espmMenu.append(Installer_Espm_Reset())
    InstallersPanel.espmMenu.append(Installer_Espm_ResetAll())
    InstallersPanel.espmMenu.append(SeparatorLink())
    InstallersPanel.espmMenu.append(Installer_Espm_JumpToMod())
    #--Sub-Package Main Menu
    InstallersPanel.subsMenu.append(Installer_Subs_SelectAll())
    InstallersPanel.subsMenu.append(Installer_Subs_DeselectAll())
    InstallersPanel.subsMenu.append(Installer_Subs_ToggleSelection())
    InstallersPanel.subsMenu.append(SeparatorLink())
    InstallersPanel.subsMenu.append(Installer_Subs_ListSubPackages())
    # InstallersList: Global Links
    # File Menu
    file_menu = InstallersList.global_links[_(u'File')]
    file_menu.append(UIList_OpenStore())
    file_menu.append(Files_Unhide(u'installer'))
    file_menu.append(SeparatorLink())
    file_menu.append(Installers_AddMarker())
    file_menu.append(Installers_CreateNewProject())
    # Edit Menu
    edit_menu = InstallersList.global_links[_(u'Edit')]
    edit_menu.append(Installers_MonitorInstall())
    edit_menu.append(SeparatorLink())
    edit_menu.append(Installers_AnnealAll())
    edit_menu.append(Installers_UninstallAllUnknownFiles())
    edit_menu.append(Installers_UninstallAllPackages())
    edit_menu.append(SeparatorLink())
    edit_menu.append(Installers_Refresh())
    edit_menu.append(Installers_Refresh(full_refresh=True))
    # View Menu
    view_menu = InstallersList.global_links[_(u'View')]
    view_menu.append(SortByMenu(
        sort_options=[Installers_SortActive(), # Installers_SortStructure(),
                      Installers_SortProjects()]))
    view_menu.append(ColumnsMenu())
    view_menu.append(SeparatorLink())
    view_menu.append(Installers_ListPackages())
    view_menu.append(Installers_WizardOverlay())
    # Settings Menu
    settings_menu = InstallersList.global_links[_(u'Settings')]
    settings_menu.append(Installers_Enabled())
    settings_menu.append(Installers_AvoidOnStart())
    settings_menu.append(SeparatorLink())
    settings_menu.append(Installers_AutoAnneal())
    if bEnableWizard:
        settings_menu.append(Installers_AutoWizard())
    settings_menu.append(Installers_AutoApplyEmbeddedBCFs())
    settings_menu.append(Installers_AutoRefreshProjects())
    settings_menu.append(SeparatorLink())
    settings_menu.append(Installers_ConflictsReportShowBSAConflicts())
    settings_menu.append(Installers_ConflictsReportShowsInactive())
    settings_menu.append(Installers_ConflictsReportShowsLower())
    settings_menu.append(SeparatorLink())
    settings_menu.append(Installers_BsaRedirection())
    settings_menu.append(Installers_RemoveEmptyDirs())
    settings_menu.append(SeparatorLink())
    settings_menu.append(Installers_AutoRefreshBethsoft())
    settings_menu.append(Installers_GlobalSkips())
    settings_menu.append(Installers_RenameStrings())
    settings_menu.append(SeparatorLink())
    append_global_settings(settings_menu)

#------------------------------------------------------------------------------
def InitINILinks():
    """Initialize INI Edits tab menus."""
    #--Column Links
    # Sorting and Columns
    INIList.column_links.append(SortByMenu(sort_options=[INI_SortValid()]))
    INIList.column_links.append(ColumnsMenu())
    INIList.column_links.append(SeparatorLink())
    # Files Menu
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        INIList.column_links.append(files_menu)
    INIList.column_links.append(SeparatorLink())
    INIList.column_links.append(INI_AllowNewLines())
    INIList.column_links.append(INI_ListINIs())
    #--Item menu
    INIList.context_links.append(INI_Apply())
    INIList.context_links.append(INI_CreateNew())
    INIList.context_links.append(INI_ListErrors())
    INIList.context_links.append(SeparatorLink())
    INIList.context_links.append(INI_FileOpenOrCopy())
    INIList.context_links.append(INI_Delete())
    # INIList: Global Links
    # File Menu
    INIList.global_links[_(u'File')].append(UIList_OpenStore())
    # View Menu
    view_menu = INIList.global_links[_(u'View')]
    view_menu.append(SortByMenu(sort_options=[INI_SortValid()]))
    view_menu.append(ColumnsMenu())
    view_menu.append(SeparatorLink())
    view_menu.append(INI_ListINIs())
    # Settings Menu
    settings_menu = INIList.global_links[_(u'Settings')]
    settings_menu.append(INI_AllowNewLines())
    settings_menu.append(SeparatorLink())
    append_global_settings(settings_menu)

#------------------------------------------------------------------------------
def InitModLinks():
    """Initialize Mods tab menus."""
    #--ModList: Column Links
    # Sorting and Columns
    ModList.column_links.append(SortByMenu(
        sort_options=[Mods_EsmsFirst(), Mods_SelectedFirst()]))
    ModList.column_links.append(ColumnsMenu())
    ModList.column_links.append(SeparatorLink())
    # Files Menu
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        files_menu.links.append(Files_Unhide(u'mod'))
        if bush.game.Esp.canBash:
            files_menu.links.append(SeparatorLink())
            files_menu.links.append(Mods_CreateBlankBashedPatch())
            files_menu.links.append(Mods_CreateBlank())
            files_menu.links.append(Mods_CreateBlank(masterless=True))
        ModList.column_links.append(files_menu)
    ModList.column_links.append(SeparatorLink())
    if True: #--Load
        loadMenu = MenuLink(_(u'Active Mods'))
        loadMenu.links.append(Mods_LoadList())
        ModList.column_links.append(loadMenu)
    ModList.column_links.append(SeparatorLink())
    if bush.game.fsName == u'Oblivion': #--Versions
        versionsMenu = MenuLink(u"Oblivion.esm")
        versionsMenu.links.append(Mods_OblivionVersion(u'1.1'))
        versionsMenu.links.append(Mods_OblivionVersion(u'1.1b'))
        versionsMenu.links.append(Mods_OblivionVersion(u'GOTY non-SI'))
        versionsMenu.links.append(Mods_OblivionVersion(u'SI'))
        ModList.column_links.append(versionsMenu)
        ModList.column_links.append(SeparatorLink())
    ModList.column_links.append(Mods_ListMods())
    ModList.column_links.append(Mods_ListBashTags())
    ModList.column_links.append(Mods_CleanDummyMasters())
    ModList.column_links.append(SeparatorLink())
    ModList.column_links.append(Mods_AutoGhost())
    if bush.game.has_esl:
        ModList.column_links.append(Mods_AutoESLFlagBP())
    ModList.column_links.append(Mods_LockLoadOrder())
    ModList.column_links.append(Mods_LockActivePlugins())
    ModList.column_links.append(Mods_ScanDirty())
    ModList.column_links.append(SeparatorLink())
    ModList.column_links.append(Mods_CrcRefresh())
    #--ModList: Item Links
    if bass.inisettings['ShowDevTools'] and bush.game.Esp.canBash:
        ModList.context_links.append(Mod_FullLoad())
    if True: #--File
        file_menu = MenuLink(_(u'File..'))
        file_menu.links.append(File_Duplicate())
        file_menu.links.append(UIList_Hide())
        file_menu.links.append(Mod_Redate())
        file_menu.links.append(balt.UIList_Delete())
        file_menu.links.append(SeparatorLink())
        file_menu.links.append(File_Backup())
        file_menu.links.append(File_RevertToBackup())
        file_menu.links.append(SeparatorLink())
        file_menu.links.append(File_Snapshot())
        file_menu.links.append(File_RevertToSnapshot())
        ModList.context_links.append(file_menu)
    if True: #--Groups
        groupMenu = MenuLink(_(u"Groups"))
        groupMenu.links.append(Mod_Groups())
        ModList.context_links.append(groupMenu)
    if True: #--Ratings
        ratingMenu = MenuLink(_(u"Rating"))
        ratingMenu.links.append(Mod_Ratings())
        ModList.context_links.append(ratingMenu)
    #--------------------------------------------
    ModList.context_links.append(SeparatorLink())
    ModList.context_links.append(Mod_Move())
    ModList.context_links.append(Mod_OrderByName())
    ModList.context_links.append(SeparatorLink())
    if bush.game.Esp.canBash:
        ModList.context_links.append(Mod_Details())
    ModList.context_links.append(File_ListMasters())
    ModList.context_links.append(Mod_ShowReadme())
    ModList.context_links.append(Mod_ListBashTags())
    ModList.context_links.append(Mod_CreateBOSSReport())
    ModList.context_links.append(Mod_CopyModInfo())
    ModList.context_links.append(Mod_ListDependent())
    ModList.context_links.append(Mod_JumpToInstaller())
    #--------------------------------------------
    ModList.context_links.append(SeparatorLink())
    ModList.context_links.append(Mod_AllowGhosting())
    ModList.context_links.append(Mod_Ghost())
    if bush.game.Esp.canBash:
        ModList.context_links.append(SeparatorLink())
        ModList.context_links.append(Mod_MarkMergeable())
        if CBashApi.Enabled:
            ModList.context_links.append(Mod_MarkMergeable(doCBash=True))
        ModList.context_links.append(Mod_Patch_Update())
        if CBashApi.Enabled:
            ModList.context_links.append(Mod_Patch_Update(doCBash=True))
        ModList.context_links.append(Mod_ListPatchConfig())
        ModList.context_links.append(Mod_ExportPatchConfig())
        #--Advanced
        ModList.context_links.append(SeparatorLink())
        if True: #--Export
            exportMenu = MenuLink(_(u"Export"))
            if CBashApi.Enabled:
                exportMenu.links.append(CBash_Mod_CellBlockInfo_Export())
            exportMenu.links.append(Mod_EditorIds_Export())
            if bush.game.fsName in (u'Enderal', u'Skyrim'):
                exportMenu.links.append(Mod_FullNames_Export())
                exportMenu.links.append(Mod_Prices_Export())
            elif bush.game.fsName == u'FalloutNV':
                # exportMenu.links.append(Mod_Factions_Export())
                exportMenu.links.append(Mod_FullNames_Export())
                exportMenu.links.append(Mod_Prices_Export())
                exportMenu.links.append(Mod_FactionRelations_Export())
                # exportMenu.links.append(Mod_IngredientDetails_Export())
                # exportMenu.links.append(Mod_Scripts_Export())
                # exportMenu.links.append(Mod_SpellRecords_Export())
                exportMenu.links.append(Mod_Stats_Export())
            elif bush.game.fsName == u'Fallout3':
                exportMenu.links.append(Mod_FullNames_Export())
                exportMenu.links.append(Mod_Prices_Export())
                exportMenu.links.append(Mod_Stats_Export())
                exportMenu.links.append(Mod_FactionRelations_Export())
            elif bush.game.fsName == u'Oblivion':
                exportMenu.links.append(Mod_Factions_Export())
                exportMenu.links.append(Mod_FullNames_Export())
                exportMenu.links.append(Mod_ActorLevels_Export())
                exportMenu.links.append(CBash_Mod_MapMarkers_Export())
                exportMenu.links.append(Mod_Prices_Export())
                exportMenu.links.append(Mod_FactionRelations_Export())
                exportMenu.links.append(Mod_IngredientDetails_Export())
                exportMenu.links.append(Mod_Scripts_Export())
                exportMenu.links.append(Mod_SigilStoneDetails_Export())
                exportMenu.links.append(Mod_SpellRecords_Export())
                exportMenu.links.append(Mod_Stats_Export())
            ModList.context_links.append(exportMenu)
        if True: #--Import
            importMenu = MenuLink(_(u"Import"))
            importMenu.links.append(Mod_EditorIds_Import())
            if bush.game.fsName in (u'Enderal', u'Skyrim'):
                importMenu.links.append(Mod_FullNames_Import())
                importMenu.links.append(Mod_Prices_Import())
            elif bush.game.fsName == u'FalloutNV':
                importMenu.links.append(Mod_FullNames_Import())
                importMenu.links.append(Mod_Prices_Import())
                importMenu.links.append(Mod_FactionRelations_Import())
                # importMenu.links.append(Mod_IngredientDetails_Import())
                # importMenu.links.append(Mod_Scripts_Import())
                importMenu.links.append(Mod_Stats_Import())
                # importMenu.links.append(SeparatorLink())
                # importMenu.links.append(Mod_Face_Import())
                # importMenu.links.append(Mod_Fids_Replace())
            elif bush.game.fsName == u'Fallout3':
                importMenu.links.append(Mod_FullNames_Import())
                importMenu.links.append(Mod_Prices_Import())
                importMenu.links.append(Mod_Stats_Import())
                importMenu.links.append(Mod_FactionRelations_Import())
            elif bush.game.fsName == u'Oblivion':
                importMenu.links.append(Mod_Factions_Import())
                importMenu.links.append(Mod_FullNames_Import())
                importMenu.links.append(Mod_ActorLevels_Import())
                importMenu.links.append(CBash_Mod_MapMarkers_Import())
                importMenu.links.append(Mod_Prices_Import())
                importMenu.links.append(Mod_FactionRelations_Import())
                importMenu.links.append(Mod_IngredientDetails_Import())
                importMenu.links.append(Mod_Scripts_Import())
                importMenu.links.append(Mod_SigilStoneDetails_Import())
                importMenu.links.append(Mod_SpellRecords_Import())
                importMenu.links.append(Mod_Stats_Import())
                importMenu.links.append(SeparatorLink())
                importMenu.links.append(Mod_Face_Import())
                importMenu.links.append(Mod_Fids_Replace())
            ModList.context_links.append(importMenu)
        if True: #--Cleaning
            cleanMenu = MenuLink(_(u"Mod Cleaning"))
            cleanMenu.links.append(Mod_SkipDirtyCheck())
            cleanMenu.links.append(SeparatorLink())
            cleanMenu.links.append(Mod_ScanDirty())
            cleanMenu.links.append(Mod_RemoveWorldOrphans())
            if bush.game.fsName == u'Oblivion':
                cleanMenu.links.append(Mod_FogFixer())
            ModList.context_links.append(cleanMenu)
        ModList.context_links.append(Mod_CopyToEsmp())
        if bush.game.fsName == u'Oblivion':
            ModList.context_links.append(Mod_DecompileAll())
        ModList.context_links.append(Mod_FlipEsm())
        if bush.game.check_esl:
            ModList.context_links.append(Mod_FlipEsl())
        ModList.context_links.append(Mod_FlipMasters())
        if bush.game.Esp.canBash:
            ModList.context_links.append(Mod_CreateDummyMasters())
        if bush.game.fsName == u'Oblivion':
            ModList.context_links.append(Mod_SetVersion())
    # ModList: Global Links
    # File Menu
    file_menu = ModList.global_links[_(u'File')]
    file_menu.append(UIList_OpenStore())
    file_menu.append(Files_Unhide(u'mod'))
    if bush.game.Esp.canBash:
        file_menu.append(SeparatorLink())
        file_menu.append(Mods_CreateBlankBashedPatch())
        file_menu.append(Mods_CreateBlank())
        file_menu.append(Mods_CreateBlank(masterless=True))
    # Edit Menu
    edit_menu = ModList.global_links[_(u'Edit')]
    am_submenu = MenuLink(_(u'Active Mods'))
    am_submenu.append(Mods_LoadList())
    edit_menu.append(am_submenu)
    if bush.game.fsName == u'Oblivion':
        edit_menu.append(SeparatorLink())
        versions_menu = MenuLink(u'Oblivion.esm')
        versions_menu.links.append(Mods_OblivionVersion(u'1.1'))
        versions_menu.links.append(Mods_OblivionVersion(u'1.1b'))
        versions_menu.links.append(Mods_OblivionVersion(u'GOTY non-SI'))
        versions_menu.links.append(Mods_OblivionVersion(u'SI'))
        edit_menu.append(versions_menu)
    edit_menu.append(SeparatorLink())
    edit_menu.append(Mods_CleanDummyMasters())
    edit_menu.append(Mods_CrcRefresh())
    # View Menu
    view_menu = ModList.global_links[_(u'View')]
    view_menu.append(SortByMenu(
        sort_options=[Mods_EsmsFirst(), Mods_SelectedFirst()]))
    view_menu.append(ColumnsMenu())
    view_menu.append(SeparatorLink())
    view_menu.append(Mods_ListMods())
    view_menu.append(Mods_ListBashTags())
    # Settings Menu
    settings_menu = ModList.global_links[_(u'Settings')]
    settings_menu.append(Mods_AutoGhost())
    if bush.game.has_esl:
        settings_menu.append(Mods_AutoESLFlagBP())
    settings_menu.append(Mods_LockLoadOrder())
    settings_menu.append(Mods_LockActivePlugins())
    settings_menu.append(Mods_ScanDirty())
    settings_menu.append(SeparatorLink())
    append_global_settings(settings_menu)

#------------------------------------------------------------------------------
def InitSaveLinks():
    """Initialize save tab menus."""
    #--SaveList: Column Links
    # Sorting and Columns
    SaveList.column_links.append(SortByMenu())
    SaveList.column_links.append(ColumnsMenu())
    SaveList.column_links.append(SeparatorLink())
    # Files Menu
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        files_menu.links.append(Files_Unhide(u'save'))
    SaveList.column_links.append(files_menu)
    SaveList.column_links.append(SeparatorLink())
    if True: #--Save Profiles
        subDirMenu = MenuLink(_(u"Profile"))
        subDirMenu.links.append(Saves_Profiles())
        SaveList.column_links.append(subDirMenu)
    if bush.game.fsName == u'Oblivion': #--Versions
        SaveList.column_links.append(SeparatorLink())
        versionsMenu = MenuLink(u"Oblivion.esm")
        versionsMenu.links.append(Mods_OblivionVersion(u'1.1',setProfile=True))
        versionsMenu.links.append(Mods_OblivionVersion(u'1.1b',setProfile=True))
        versionsMenu.links.append(Mods_OblivionVersion(u'GOTY non-SI',setProfile=True))
        versionsMenu.links.append(Mods_OblivionVersion(u'SI',setProfile=True))
        SaveList.column_links.append(versionsMenu)
    #--SaveList: Item Links
    if True: #--File
        file_menu = MenuLink(_(u'File..'))
        file_menu.links.append(Save_Rename())
        file_menu.links.append(File_Duplicate())
        file_menu.links.append(UIList_Hide())
        file_menu.links.append(balt.UIList_Delete())
        file_menu.links.append(SeparatorLink())
        file_menu.links.append(File_Backup())
        file_menu.links.append(File_RevertToBackup())
        SaveList.context_links.append(file_menu)
    if True: #--Move to Profile
        moveMenu = MenuLink(_(u"Move To"))
        moveMenu.links.append(Save_Move())
        SaveList.context_links.append(moveMenu)
    if True: #--Copy to Profile
        copyMenu = MenuLink(_(u"Copy To"))
        copyMenu.links.append(Save_Move(True))
        SaveList.context_links.append(copyMenu)
    #--------------------------------------------
    SaveList.context_links.append(SeparatorLink())
    SaveList.context_links.append(Save_LoadMasters())
    SaveList.context_links.append(File_ListMasters())
    SaveList.context_links.append(Save_DiffMasters())
    if bush.game.Ess.canEditMore:
        SaveList.context_links.append(Save_Stats())
    SaveList.context_links.append(Save_StatObse())
    SaveList.context_links.append(Save_StatPluggy())
    if bush.game.Ess.canEditMore:
        #--------------------------------------------
        SaveList.context_links.append(SeparatorLink())
        SaveList.context_links.append(Save_EditPCSpells())
        SaveList.context_links.append(Save_RenamePlayer())
        SaveList.context_links.append(Save_EditCreatedEnchantmentCosts())
        SaveList.context_links.append(Save_ImportFace())
        SaveList.context_links.append(Save_EditCreated('ENCH'))
        SaveList.context_links.append(Save_EditCreated('ALCH'))
        SaveList.context_links.append(Save_EditCreated('SPEL'))
        SaveList.context_links.append(Save_ReweighPotions())
        SaveList.context_links.append(Save_UpdateNPCLevels())
    #--------------------------------------------
    SaveList.context_links.append(SeparatorLink())
    SaveList.context_links.append(Save_ExportScreenshot())
    SaveList.context_links.append(Save_Renumber())
    #--------------------------------------------
    if bush.game.Ess.canEditMore:
        SaveList.context_links.append(SeparatorLink())
        SaveList.context_links.append(Save_Unbloat())
        SaveList.context_links.append(Save_RepairAbomb())
        SaveList.context_links.append(Save_RepairHair())
    # SaveList: Global Links
    # File Menu
    file_Menu = SaveList.global_links[_(u'File')]
    file_Menu.append(UIList_OpenStore())
    file_Menu.append(Files_Unhide(u'save'))
    # Edit Menu
    edit_menu = SaveList.global_links[_(u'Edit')]
    if bush.game.fsName == u'Oblivion':
        versions_menu = MenuLink(u'Oblivion.esm')
        versions_menu.links.append(Mods_OblivionVersion(
            u'1.1', setProfile=True))
        versions_menu.links.append(Mods_OblivionVersion(
            u'1.1b', setProfile=True))
        versions_menu.links.append(Mods_OblivionVersion(
            u'GOTY non-SI', setProfile=True))
        versions_menu.links.append(Mods_OblivionVersion(
            u'SI', setProfile=True))
        edit_menu.append(versions_menu)
    profile_menu = MenuLink(_(u'Profile'))
    profile_menu.append(Saves_Profiles())
    edit_menu.append(profile_menu)
    # View Menu
    view_menu = SaveList.global_links[_(u'View')]
    view_menu.append(SortByMenu())
    view_menu.append(ColumnsMenu())
    # Settings Menu
    append_global_settings(SaveList.global_links[_(u'Settings')])

#------------------------------------------------------------------------------
def InitBSALinks():
    """Initialize BSA tab menus."""
    #--BSAList: Column Links
    # Sorting and Columns
    BSAList.column_links.append(SortByMenu())
    BSAList.column_links.append(ColumnsMenu())
    BSAList.column_links.append(SeparatorLink())
    # Files Menu
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        files_menu.links.append(Files_Unhide(u'BSA'))
    BSAList.column_links.append(files_menu)
    BSAList.column_links.append(SeparatorLink())
    #--BSAList: Item Links
    if True: #--File
        file_menu = MenuLink(_(u'File..'))
        file_menu.links.append(File_Duplicate())
        file_menu.links.append(UIList_Hide())
        file_menu.links.append(File_Redate())
        file_menu.links.append(balt.UIList_Delete())
        file_menu.links.append(SeparatorLink())
        file_menu.links.append(File_Backup())
        file_menu.links.append(File_RevertToBackup())
    BSAList.context_links.append(file_menu)
    BSAList.context_links.append(BSA_ExtractToProject())
    BSAList.context_links.append(BSA_ListContents())
    # BSAList: Global Links
    # File Menu
    file_menu = BSAList.global_links[_(u'File')]
    file_menu.append(UIList_OpenStore())
    file_menu.append(Files_Unhide(u'BSA'))
    # View Menu
    view_menu = BSAList.global_links[_(u'View')]
    view_menu.append(SortByMenu())
    view_menu.append(ColumnsMenu())
    # Settings Menu
    append_global_settings(BSAList.global_links[_(u'Settings')])

#------------------------------------------------------------------------------
def InitScreenLinks():
    """Initialize screens tab menus."""
    #--ScreensList: Column Links
    # Sorting and Columns
    ScreensList.column_links.append(SortByMenu())
    ScreensList.column_links.append(ColumnsMenu())
    ScreensList.column_links.append(SeparatorLink())
    if True:
        files_menu = MenuLink(_(u'Files..'))
        files_menu.links.append(UIList_OpenStore())
        ScreensList.column_links.append(files_menu)
    ScreensList.column_links.append(SeparatorLink())
    ScreensList.column_links.append(Screens_NextScreenShot())
    #--JPEG Quality
    if True:
        qualityMenu = MenuLink(_(u'JPEG Quality'))
        for i in range(100, 80, -5):
            qualityMenu.links.append(Screens_JpgQuality(i))
        qualityMenu.links.append(Screens_JpgQualityCustom())
        ScreensList.column_links.append(SeparatorLink())
        ScreensList.column_links.append(qualityMenu)
    #--ScreensList: Item Links
    if True: #--File
        file_menu = MenuLink(_(u'File..'))
        file_menu.links.append(UIList_OpenItems())
        file_menu.links.append(Screen_Rename())
        file_menu.links.append(File_Duplicate())
        file_menu.links.append(balt.UIList_Delete())
        ScreensList.context_links.append(file_menu)
    if True: #--Convert
        convertMenu = MenuLink(_(u'Convert'))
        image_type = Image.typesDict
        convertMenu.links.append(Screen_ConvertTo(u'jpg', image_type['jpg']))
        convertMenu.links.append(Screen_ConvertTo(u'png', image_type['png']))
        convertMenu.links.append(Screen_ConvertTo(u'bmp', image_type['bmp']))
        convertMenu.links.append(Screen_ConvertTo(u'tif', image_type['tif']))
        ScreensList.context_links.append(convertMenu)
    # ScreensList: Global Links
    # File Menu
    ScreensList.global_links[_(u'File')].append(UIList_OpenStore())
    # View Menu
    view_menu = ScreensList.global_links[_(u'View')]
    view_menu.append(SortByMenu())
    view_menu.append(ColumnsMenu())
    # Settings Menu
    settings_menu = ScreensList.global_links[_(u'Settings')]
    settings_menu.append(Screens_NextScreenShot())
    jpeg_quality_menu = MenuLink(_(u'JPEG Quality'))
    for i in range(100, 80, -5):
        jpeg_quality_menu.links.append(Screens_JpgQuality(i))
    jpeg_quality_menu.links.append(Screens_JpgQualityCustom())
    settings_menu.append(qualityMenu)
    settings_menu.append(SeparatorLink())
    append_global_settings(settings_menu)

#------------------------------------------------------------------------------
def InitPeopleLinks():
    """Initialize people tab menus."""
    #--Header links
    # Sorting and Columns
    PeopleList.column_links.append(SortByMenu())
    PeopleList.column_links.append(ColumnsMenu())
    PeopleList.column_links.append(SeparatorLink())
    PeopleList.column_links.append(People_AddNew())
    PeopleList.column_links.append(People_Import())
    #--Item links
    PeopleList.context_links.append(People_Karma())
    PeopleList.context_links.append(SeparatorLink())
    PeopleList.context_links.append(People_AddNew())
    PeopleList.context_links.append(balt.UIList_Delete())
    PeopleList.context_links.append(People_Export())
    # PeopleList: Global Links
    # Edit Menu
    edit_menu = PeopleList.global_links[_(u'Edit')]
    edit_menu.append(People_AddNew())
    edit_menu.append(People_Import())
    # View Menu
    view_menu = PeopleList.global_links[_(u'View')]
    view_menu.append(SortByMenu())
    view_menu.append(ColumnsMenu())
    # Settings Menu
    append_global_settings(PeopleList.global_links[_(u'Settings')])

#------------------------------------------------------------------------------
def InitSettingsLinks(SettingsMenu):
    """Initialize settings menu."""
    #--User settings
    SettingsMenu.append(Settings_BackupSettings())
    SettingsMenu.append(Settings_RestoreSettings())
    SettingsMenu.append(Settings_SaveSettings())
    #--OBSE Dll info
    if bush.game.Se.se_abbrev:
        SettingsMenu.append(SeparatorLink())
        SettingsMenu.append(Settings_ExportDllInfo())
        SettingsMenu.append(Settings_ImportDllInfo())
    #--Color config
    SettingsMenu.append(SeparatorLink())
    SettingsMenu.append(Settings_Colors())
    if True:
        tabsMenu = BashNotebook.tabLinks(MenuLink(_(u'Tabs')))
        SettingsMenu.append(tabsMenu)
    #--StatusBar
    if True:
        sbMenu = MenuLink(_(u'Status bar'))
        #--Icon size
        # FIXME(inf) Either fix these or remove them entirely
        # if True:
        #     sizeMenu = MenuLink(_(u'Icon size'))
        #     for size in (16,24,32):
        #         sizeMenu.links.append(Settings_IconSize(size))
        #     sbMenu.links.append(sizeMenu)
        sbMenu.links.append(Settings_UnHideButtons())
        sbMenu.links.append(Settings_StatusBar_ShowVersions())
        SettingsMenu.append(sbMenu)
    SettingsMenu.append(Settings_Languages())
    SettingsMenu.append(Settings_PluginEncodings())
    SettingsMenu.append(Settings_Games())
    SettingsMenu.append(SeparatorLink())
    SettingsMenu.append(Settings_UseAltName())
    SettingsMenu.append(Settings_ShowGlobalMenu())
    SettingsMenu.append(Settings_Deprint())
    SettingsMenu.append(Settings_DumpTranslator())
    SettingsMenu.append(Settings_UAC())

def append_global_settings(settings_menu):
    """Creates the 'Global Settings' link for each tab's 'Settings'
    category."""
    global_settings = MenuLink(_(u'Global Settings'))
    InitSettingsLinks(global_settings)
    settings_menu.append(global_settings)

def InitLinks():
    """Call other link initializers."""
    InitStatusBar()
    InitSettingsLinks(BashStatusBar.SettingsMenu)
    InitMasterLinks()
    InitInstallerLinks()
    InitINILinks()
    InitModLinks()
    InitSaveLinks()
    InitScreenLinks()
    InitPeopleLinks()
    # InitBSALinks()
