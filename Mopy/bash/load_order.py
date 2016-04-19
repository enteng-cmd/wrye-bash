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
#  Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2015 Wrye Bash Team
#  https://github.com/wrye-bash
#
# =============================================================================
"""Load order management, features caching.

Notes:
- _current_lo is meant to eventually become a cache exported to the rest of
Bash. Must be valid at all times. Should be updated on tabbing out and back
in to Bash and on setting lo/active from inside Bash.
- active mods must always be manipulated having a valid load order at hand:
 - all active mods must be present and have a load order and
 - especially for skyrim the relative order of entries in plugin.txt must be
 the same as their relative load order in loadorder.txt
- corrupted files do not have a load order

Double underscores and dirty comments are no accident - BETA, I need a Game
classes hierarchy to handle differences between the games.
"""
import re
import time
import bass
import bolt
import bush
import bosh
# Game instance providing load order operations API
from games import game_factory
game_handle = None # type: games.Game # we need the modInfos singleton

def get_game():
    global  game_handle
    if game_handle is None:
        game_handle = game_factory(bush.game.fsName, bosh.modInfos,
                                   _plugins_txt_path, _loadorder_txt_path)
    return game_handle

class LoadOrder(object):
    """Immutable class representing a load order."""
    __empty = ()
    __none = frozenset()

    def __init__(self, loadOrder=__empty, active=__none):
        if set(active) - set(loadOrder):
            raise bolt.BoltError(
                u'Active mods with no load order: ' + u', '.join(
                    [x.s for x in (set(active) - set(loadOrder))]))
        self._loadOrder = tuple(loadOrder)
        self._active = frozenset(active)
        self.__mod_loIndex = dict((a, i) for i, a in enumerate(loadOrder))
        # below would raise key error if active have no loadOrder
        self._activeOrdered = tuple(
            sorted(active, key=self.__mod_loIndex.__getitem__))
        self.__mod_actIndex = dict(
            (a, i) for i, a in enumerate(self._activeOrdered))

    @property
    def loadOrder(self): return self._loadOrder # test if empty
    @property
    def active(self): return self._active  # test if none
    @property
    def activeOrdered(self): return self._activeOrdered

    def __eq__(self, other):
        return isinstance(other, LoadOrder) and self._active == other._active \
               and self._loadOrder == other._loadOrder
    def __ne__(self, other): return not self == other
    def __hash__(self): return hash((self._loadOrder, self._active))

    def lindex(self, path): return self.__mod_loIndex[path] # KeyError
    def lorder(self, paths):
        """Return a tuple containing the given paths in their load order.
        :param paths: iterable of paths that must all have a load order
        :type paths: collections.Iterable[bolt.Path]
        :rtype: tuple
        """
        return tuple(sorted(paths, key=self.__mod_loIndex.__getitem__))
    def activeIndex(self, path): return self.__mod_actIndex[path]

# Module level cache
__empty = LoadOrder()
_current_lo = __empty # must always be valid (or __empty)

# liblo calls - they include fixup code (which may or may not be
# needed/working). __fix methods accept lists as output parameters
def _get_load_order(cached_load_order=None, cached_active=None):
    """:rtype: list[bolt.Path]"""
    return get_game().get_load_order(cached_load_order, cached_active)

def _indexFirstEsp(lord):
    indexFirstEsp = 0
    while indexFirstEsp < len(lord) and bosh.modInfos[
        lord[indexFirstEsp]].isEsm():
        indexFirstEsp += 1
    return indexFirstEsp

def __fixLoadOrder(lord, _selected=None):
    """HACK: Fix inconsistencies between given loadorder and actually installed
    mod files as well as impossible load orders - save the fixed order. We
    need a refreshed bosh.modInfos reflecting the contents of Data/.

    Called in _get_load_order() to fix a newly fetched LO and in
    SaveLoadOrder() to check if a load order passed in is valid. Needs
    rethinking as save load and active should be an atomic operation -
    leads to hacks (like the _selected parameter).
    :type lord: list[bolt.Path]
    """
    oldLord = lord[:]
    # game's master might be out of place (if using timestamps for load
    # ordering or a manually edited loadorder.txt) so move it up
    masterName = bosh.modInfos.masterName
    try:
        masterDex = lord.index(masterName)
    except ValueError:
        raise bolt.BoltError(u'%s is missing or corrupted' % masterName)
    if masterDex > 0:
        bolt.deprint(u'%s has index %d (must be 0)' % (masterName, masterDex))
        lord.remove(masterName)
        lord.insert(0, masterName)
        _reordered = True
    else: _reordered = False
    loadOrder = set(lord)
    modFiles = set(bosh.modInfos.keys())
    _removedFiles = loadOrder - modFiles # may remove corrupted mods returned
    # from liblo (text file), we are supposed to take care of that
    _addedFiles = modFiles - loadOrder
    # Remove non existent plugins from load order
    lord[:] = [x for x in lord if x not in _removedFiles]
    indexFirstEsp = _indexFirstEsp(lord)
    # See if any esm files are loaded below an esp and reorder as necessary
    for mod in lord[indexFirstEsp:]:
        if mod in bosh.modInfos and bosh.modInfos[mod].isEsm():
            lord.remove(mod)
            lord.insert(indexFirstEsp, mod)
            indexFirstEsp += 1
            _reordered = True
    # Append new plugins to load order
    for mod in _addedFiles:
        if bosh.modInfos[mod].isEsm():
            lord.insert(indexFirstEsp, mod)
            indexFirstEsp += 1
        else: lord.append(mod)
    if _addedFiles and not usingTxtFile(): # should not occur
        bolt.deprint(u'Incomplete load order passed in to SaveLoadOrder')
        lord[:] = bosh.modInfos.calculateLO(mods=lord)
    # Save changes if necessary
    if _removedFiles or _addedFiles or _reordered:
        active_saved = False
        if _removedFiles or _reordered: # must fix the active too
            # If _selected is not None we come from SaveLoadOrder which needs
            # to save _selected too - so fix this list instead of
            # _current_lo.activeOrdered. If fixed and saved, empty it so we do
            # not resave it. If selected was empty to begin with we need extra
            # hacks (wasEmpty in SaveLoadOrder)
            # fallout 4 adds the further complication that may provide the
            # active mods from the get_load_order path
            if _selected is None:
                if _current_lo is not __empty: # else we are on first refresh
                    _selected = list(_current_lo.activeOrdered)
            if _selected is not None and __fixActive(_selected, lord):
                _selected[:] = [] # avoid resaving
                active_saved = True
        bolt.deprint(u'Fixed Load Order: added(%s), removed(%s), reordered(%s)'
             % (_pl(_addedFiles) or u'None', _pl(_removedFiles) or u'None',
             u'No' if not _reordered else _pl(oldLord, u'from:\n') +
                                          _pl(lord, u'\nto:\n')))
        if bush.game.fsName != u'Fallout4':
            SaveLoadOrder(lord, _fixed=True)
        elif not active_saved:
            SaveLoadOrder(lord, acti=_selected, _fixed=True)
            if _selected is not None: _selected[:] = [] # avoid resaving
        return True # changes, saved
    return False # no changes, not saved

def __fixActive(acti, lord):
    # filter plugins not present in modInfos - this will disable corrupted too!
    actiFiltered = [x for x in acti if x in bosh.modInfos] #preserve acti order
    _removed = set(acti) - set(actiFiltered)
    if _removed: # take note as we may need to rewrite plugins txt
        msg = u'__fixActive: active list contains mods not present ' \
              u'in Data/ directory or corrupted: ' + _pl(_removed) + u'\n'
        bosh.modInfos.selectedBad = _removed
    else: msg = u''
    if not bush.game.deactivate_master_esm:
        game_master = bolt.GPath(bush.game.masterFiles[0])
        if not game_master in actiFiltered:
            actiFiltered.insert(0, game_master)
            msg += (u'__fixActive: %s not present in active mods' % game_master) + u'\n'
    addUpdateEsm = False
    if bush.game.fsName == u'Skyrim':
        updateEsm = bolt.GPath(u'Update.esm')
        if updateEsm in lord and not updateEsm in actiFiltered:
            msg += (u'__fixActive: Update.esm not present in active list '
                    u'while present in Data folder') + u'\n'
            addUpdateEsm = True
    dexDict = {mod:index for index, mod in enumerate(lord)}
    if usingTxtFile(): # unneeded for oblivion (or for fallout 4 really either)
        actiSorted = actiFiltered[:]
        actiSorted.sort(key=dexDict.__getitem__) # all present in lord
        if actiFiltered != actiSorted: # were mods in an order that disagrees with lord ?
            msg += (u'__fixActive: active list order of plugins (%s) differs '
                    u'from supplied load order (%s)') % (
                _pl(actiFiltered), _pl(actiSorted))
    else: actiSorted = sorted(actiFiltered, key=dexDict.__getitem__)
    if addUpdateEsm: # insert after the last master (as does liblo)
        actiSorted.insert(_indexFirstEsp(actiSorted), updateEsm)
    # check if we have more than 256 active mods
    if len(actiSorted) > 255:
        msg += u'__fixActive: active list contains more than 255 plugins' \
               u' - the following plugins will be deactivated: '
        bosh.modInfos.selectedExtra = actiSorted[255:]
        msg += _pl(bosh.modInfos.selectedExtra)
    # Check for duplicates
    mods, duplicates, j = set(), set(), 0
    for i, mod in enumerate(actiSorted[:]):
        if mod in mods:
            del actiSorted[i - j]
            j += 1
            duplicates.add(mod)
        else:
            mods.add(mod)
    if duplicates:
        msg += u'__fixActive: removed duplicate entries from active list : '
        msg += _pl(duplicates)
    acti[:] = actiSorted[:255] # chop off extra, and update acti in place
    if msg:
        # Notify user - ##: maybe backup previous plugin txt ?
        bolt.deprint(u'Invalid Plugin txt corrected' + u'\n' + msg)
        SetActivePlugins(acti, lord, _fixed=True)
        return True # changes, saved
    return False # no changes, not saved

def SaveLoadOrder(lord, acti=None, _fixed=False):
    """Save the Load Order (rewrite loadorder.txt or set modification times).

    Will update plugins.txt too if using the textfile method to reorder it
    as loadorder.txt, and of course rewrite it completely for fallout 4 (
    asterisk method)."""
    actiList = list(acti) if acti is not None else None
    wasEmpty = acti is not None and actiList == []
    saved = False
    if not _fixed: saved = __fixLoadOrder(lord, _selected=actiList)
    if not saved: # __fixLoadOrder may have saved, avoid resaving
        if not usingTxtFile():
            __save_timestamps_load_order(lord)
        elif bush.game.fsName != u'Fallout4':
            _write_plugins_txt(_loadorder_txt_path, [], lord, _star=False)
            _setLoTxtModTime()
        else:
            _write_plugins_txt(_plugins_txt_path, lord, actiList or _current_lo.active, _star=True)
        _reset_mtimes_cache() # Rename this to _notify_modInfos_change_intentional()
    # but go on saving active (if __fixLoadOrder > __fixActive saved them
    # condition below should be False)
    if actiList or wasEmpty: SetActivePlugins(actiList, lord)
    else: _updateCache(lord=lord, actiSorted=_current_lo.activeOrdered)
    return _current_lo

def __save_timestamps_load_order(lord):
    """Save timestamps (as few as possible) - modInfos must contain all mods
    :type lord: list[bolt.Path]
    """
    assert set(bosh.modInfos.keys()) == set(lord)
    if len(lord) == 0: return
    current = bosh.modInfos.calculateLO()
    # break conflicts
    older = bosh.modInfos[current[0]].mtime
    for i, mod in enumerate(current[1:]):
        info = bosh.modInfos[mod]
        if info.mtime == older: break
        older = info.mtime
    else: mod = i = None # define i to avoid warning below
    if mod is not None: # respace all in 60 sec intervals
        for mod in current[i + 1:]:
            info = bosh.modInfos[mod]
            older += 60
            info.setmtime(older)
    restamp = []
    for ordered, mod in zip(lord, current):
        if ordered == mod: continue
        restamp.append((ordered, bosh.modInfos[mod].mtime))
    for ordered, mtime in restamp:
        bosh.modInfos[ordered].setmtime(mtime)

def _reset_mtimes_cache():
    """Reset the mtimes cache or LockLO feature will revert intentional
    changes."""
    if usingTxtFile(): return
    for name in bosh.modInfos.mtimes:
        path = bosh.modInfos[name].getPath()
        if path.exists(): bosh.modInfos.mtimes[name] = path.mtime

def _updateCache(lord=None, actiSorted=None):
    """
    :type lord: tuple[bolt.Path] | list[bolt.Path]
    :type actiSorted: tuple[bolt.Path] | list[bolt.Path]
    """
    global _current_lo
    try:
        if lord is actiSorted is None:
            lord, actiSorted = _get_load_order(cached_load_order=lord, cached_active=actiSorted)
            _setLoTxtModTime()
        elif actiSorted is None: # got a valid load order - now to active...
            _lo, actiSorted = _get_load_order(cached_load_order=lord, cached_active=actiSorted)
        elif lord is None:
            lord, _act = _get_load_order(cached_load_order=lord, cached_active=actiSorted)
            _setLoTxtModTime()
        _current_lo = LoadOrder(lord, actiSorted)
    except Exception:
        bolt.deprint('Error updating load_order cache from liblo')
        _current_lo = __empty
        raise

rePluginsTxtComment = re.compile(u'#.*', re.U)
def _parse_plugins_txt(path, _star):
    with path.open('r') as ins:
        #--Load Files
        active, modNames = [], []
        for line in ins:
            # Oblivion/Skyrim saves the plugins.txt file in cp1252 format
            # It wont accept filenames in any other encoding
            try:
                modName = rePluginsTxtComment.sub(u'', line).strip()
                if not modName: continue
                is_active = not _star or modName.startswith(u'*')
                if _star and is_active: modName = modName[1:]
                test = bolt.decode(modName)
            except UnicodeError: continue
            if bolt.GPath(test) not in bosh.modInfos:
                # The automatic encoding detector could have returned
                # an encoding it actually wasn't.  Luckily, we
                # have a way to double check: modInfos.data
                for encoding in bolt.encodingOrder:
                    try:
                        test2 = unicode(modName, encoding)
                        if bolt.GPath(test2) not in bosh.modInfos:
                            continue
                        modName = bolt.GPath(test2)
                        break
                    except UnicodeError:
                        pass
                else:
                    modName = bolt.GPath(test)
            else:
                modName = bolt.GPath(test)
            modNames.append(modName)
            if is_active: active.append(modName)
    return active, modNames

def _write_plugins_txt(path, lord, active, _star=False):
    with path.open('wb') as out:
        #--Load Files
        def asterisk(active_set=set(active)):
            return '*' if _star and (mod in active_set) else ''
        for mod in (_star and lord) or active:
            # Ok, this seems to work for Oblivion, but not Skyrim
            # Skyrim seems to refuse to have any non-cp1252 named file in
            # plugins.txt.  Even activating through the SkyrimLauncher
            # doesn't work.
            try:
                out.write(asterisk() + bolt.encode(mod.s))
                out.write('\r\n')
            except UnicodeEncodeError:
                pass

def GetLo(cached=False):
    if not cached or _current_lo is __empty:
        if _current_lo is not __empty:
            loadOrder = _current_lo.loadOrder if not get_game(
                ).load_order_changed() else None
            active = _current_lo.activeOrdered if not get_game(
                ).active_changed() else None
        else: active = loadOrder = None
        _updateCache(loadOrder, active)
    return _current_lo

def SetActivePlugins(act, lord, _fixed=False): # we need a valid load order to set active
    act = list(act) # should be ordered to begin with !
    if not _fixed: saved = __fixActive(act, lord)
    else: saved =  False
    if not saved:
        _write_plugins_txt(_plugins_txt_path, lord, act,
                           _star=bush.game.fsName == u'Fallout4')
        _updateCache(lord=lord, actiSorted=act)
    return _current_lo

def usingTxtFile():
    return bush.game.fsName == u'Fallout4' or bush.game.fsName == u'Skyrim'

def haveLoFilesChanged(): # YAK !
    """True if plugins.txt or loadorder.txt file has changed."""
    return get_game().active_changed() or _loadorder_txt_changed()

def _loadorder_txt_changed():
    return _loadorder_txt_path.exists() and (
            mtimeOrder != _loadorder_txt_path.mtime or
            sizeOrder  != _loadorder_txt_path.size)

def swap(oldPath, newPath):
    """Save current plugins into oldPath directory and load plugins from
    newPath directory (if present)."""
    # Save plugins.txt and loadorder.txt inside the old (saves) directory
    if _plugins_txt_path.exists():
        _plugins_txt_path.copyTo(oldPath.join(u'plugins.txt'))
    if _loadorder_txt_path.exists():
        _loadorder_txt_path.copyTo(oldPath.join(u'loadorder.txt'))
    # Move the new plugins.txt and loadorder.txt here for use
    move = newPath.join(u'plugins.txt')
    if move.exists():
        move.copyTo(_plugins_txt_path)
        _plugins_txt_path.mtime = time.time() # copy will not change mtime, bad
    move = newPath.join(u'loadorder.txt')
    if move.exists():
        move.copyTo(_loadorder_txt_path)
        _loadorder_txt_path.mtime = time.time()#update mtime to trigger refresh

#------------------------------------------------------------------------------

if bass.dirs['saveBase'] == bass.dirs['app']:
#--If using the game directory as rather than the appdata dir.
    _dir = bass.dirs['app']
else:
    _dir = bass.dirs['userApp']
_plugins_txt_path = _dir.join(u'plugins.txt')
_loadorder_txt_path = _dir.join(u'loadorder.txt')
mtimeOrder = 0
sizeOrder = 0

def _setLoTxtModTime():
    if usingTxtFile() and _loadorder_txt_path.exists():
        global mtimeOrder, sizeOrder
        mtimeOrder, sizeOrder = _loadorder_txt_path.mtime, \
                                _loadorder_txt_path.size

# helper - print a list
def _pl(aList, legend=u''):
    return legend + u', '.join(u'%s' % x for x in aList) # use Path.__unicode__
