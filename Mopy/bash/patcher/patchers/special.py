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
import copy
from collections import Counter, defaultdict
from itertools import chain
from operator import itemgetter, attrgetter
# Internal
from .base import Patcher, CBash_Patcher, ListPatcher, CBash_ListPatcher
from ..base import Abstract_Patcher, AListPatcher
from ... import bush, load_order
from ...bolt import GPath, SubProgress
from ...cint import FormID
from ...exception import AbstractError

# Patchers: 40 ----------------------------------------------------------------
class _AListsMerger(AListPatcher):
    """Merges lists of objects, e.g. leveled lists or FormID lists."""
    group = _(u'Special')
    scanOrder = 45
    editOrder = 45
    iiMode = True

    def _overhaul_compat(self, mods, _skip_id):
        OOOMods = {GPath(u"Oscuro's_Oblivion_Overhaul.esm"),
                   GPath(u"Oscuro's_Oblivion_Overhaul.esp")}
        FransMods = {GPath(u"Francesco's Leveled Creatures-Items Mod.esm"),
                     GPath(u"Francesco.esp")}
        WCMods = {GPath(u"Oblivion Warcry.esp"),
                  GPath(u"Oblivion Warcry EV.esp")}
        TIEMods = {GPath(u"TIE.esp")}
        OverhaulCompat = GPath(u"Unofficial Oblivion Patch.esp") in mods and (
                (OOOMods | WCMods) & mods) or (
                                 FransMods & mods and not (TIEMods & mods))
        if OverhaulCompat:
            self.OverhaulUOPSkips = set(
                [_skip_id(x) for x in [
                    0x03AB5D,  # VendorWeaponBlunt
                    0x03C7F1,  # LL0LootWeapon0Magic4Dwarven100
                    0x03C7F2,  # LL0LootWeapon0Magic7Ebony100
                    0x03C7F3,  # LL0LootWeapon0Magic5Elven100
                    0x03C7F4,  # LL0LootWeapon0Magic6Glass100
                    0x03C7F5,  # LL0LootWeapon0Magic3Silver100
                    0x03C7F7,  # LL0LootWeapon0Magic2Steel100
                    0x03E4D2,  # LL0NPCWeapon0MagicClaymore100
                    0x03E4D3,  # LL0NPCWeapon0MagicClaymoreLvl100
                    0x03E4DA,  # LL0NPCWeapon0MagicWaraxe100
                    0x03E4DB,  # LL0NPCWeapon0MagicWaraxeLvl100
                    0x03E4DC,  # LL0NPCWeapon0MagicWarhammer100
                    0x03E4DD,  # LL0NPCWeapon0MagicWarhammerLvl100
                    0x0733EA,  # ArenaLeveledHeavyShield,
                    0x0C7615,  # FGNPCWeapon0MagicClaymoreLvl100
                    0x181C66,  # SQ02LL0NPCWeapon0MagicClaymoreLvl100
                    0x053877,  # LL0NPCArmor0MagicLightGauntlets100
                    0x053878,  # LL0NPCArmor0MagicLightBoots100
                    0x05387A,  # LL0NPCArmor0MagicLightCuirass100
                    0x053892,  # LL0NPCArmor0MagicLightBootsLvl100
                    0x053893,  # LL0NPCArmor0MagicLightCuirassLvl100
                    0x053894,  # LL0NPCArmor0MagicLightGauntletsLvl100
                    0x053D82,  # LL0LootArmor0MagicLight5Elven100
                    0x053D83,  # LL0LootArmor0MagicLight6Glass100
                    0x052D89,  # LL0LootArmor0MagicLight4Mithril100
                ]])
        else:
            self.OverhaulUOPSkips = set()

    def __init__(self, p_name, p_file, p_sources, remove_empty, tag_choices):
        """In addition to default parameters, accepts a boolean remove_empty,
        which determines whether or not the 'empty sublist removal' logic
        should run, and a defaultdict tag_choices, which maps each tagged
        plugin (represented as paths) to a set of the applied tags (as unicode
        strings, e.g. u'Delev'), defaulting to an empty set.

        :type remove_empty: bool
        :type tag_choices: defaultdict[bolt.Path, set[unicode]]"""
        super(_AListsMerger, self).__init__(p_name, p_file, p_sources)
        self.isActive |= bool(p_file.loadSet) # Can do meaningful work even without sources
        self.type_list = dict([(rec, {}) for rec in self._read_write_records])
        self.masterItems = defaultdict(dict)
        # Calculate levelers/de_masters first, using unmodified self.srcs
        self.levelers = [leveler for leveler in self.srcs if
                         leveler in self.patchFile.allSet]
        # de_masters is a set of all the masters of each leveler, i.e. each
        # tagged plugin. These are the masters we have to consider records from
        # when determining whether or not to carry forward removals done by a
        # 'De'-tagged plugin
        self.de_masters = set()
        for leveler in self.levelers:
            self.de_masters.update(p_file.p_file_minfos[leveler].get_masters())
        self.srcs = set(self.srcs) & p_file.loadSet
        self.remove_empty_sublists = remove_empty
        self.tag_choices = tag_choices

class _PListsMerger(_AListsMerger, ListPatcher):
    """Common code from PBash _AListsMerger subclasses."""
    # De/Re Tags - None means the patcher does not have such a tag
    _de_tag = None
    _re_tag = None
    # Maps record type (str) to translated label (unicode)
    _type_to_label = {}
    _de_re_header = None

    def annotate_plugin(self, ann_plugin):
        """Returns the name of the specified plugin, with any Relev/Delev tags
        appended as [ADR], similar to how the patcher GUI displays it.

        :param ann_plugin: The plugin to return the name for, as a path.
        :type ann_plugin: bolt.Path"""
        applied_tags = [t[0] for t in self.tag_choices[ann_plugin]]
        return ann_plugin.s + (u' [%s]' % u''.join(sorted(applied_tags))
                               if applied_tags else u'')

    def scanModFile(self, modFile, progress):
        #--Begin regular scan
        sc_name = modFile.fileInfo.name
        modFile.convertToLongFids(self._read_write_records)
        #--PreScan for later Relevs/Delevs?
        if sc_name in self.de_masters:
            for list_type in self._read_write_records:
                for de_list in getattr(modFile, list_type).getActiveRecords():
                    self.masterItems[de_list.fid][sc_name] = set(
                        self._get_entries(de_list))
        #--Relev/Delev setup
        applied_tags = self.tag_choices[sc_name]
        is_relev = self._re_tag in applied_tags
        is_delev = self._de_tag in applied_tags
        #--Scan
        for list_type in self._read_write_records:
            stored_lists = self.type_list[list_type]
            new_lists = getattr(modFile, list_type)
            for new_list in new_lists.getActiveRecords():
                list_fid = new_list.fid
                # FIXME(inf) This is hideous and slows everything down
                if (sc_name == u'Unofficial Oblivion Patch.esp' and
                        list_fid in self.OverhaulUOPSkips):
                    stored_lists[list_fid].mergeOverLast = True
                    continue
                is_list_owner = (list_fid[0] == sc_name)
                #--Items, delevs and relevs sets
                new_list.items = items = set(self._get_entries(new_list))
                if not is_list_owner:
                    #--Relevs
                    new_list.re_records = items.copy() if is_relev else set()
                    #--Delevs: all items in masters minus current items
                    new_list.de_records = delevs = set()
                    if is_delev:
                        id_master_items = self.masterItems.get(list_fid)
                        if id_master_items:
                            for de_master in modFile.tes4.masters:
                                if de_master in id_master_items:
                                    delevs |= id_master_items[de_master]
                            # TODO(inf) Double-check that this works correctly,
                            #  this line (delevs -= items) seems a noop here
                            delevs -= items
                            new_list.items |= delevs
                #--Cache/Merge
                if is_list_owner:
                    de_list = copy.deepcopy(new_list)
                    de_list.mergeSources = []
                    stored_lists[list_fid] = de_list
                elif list_fid not in stored_lists:
                    de_list = copy.deepcopy(new_list)
                    de_list.mergeSources = [sc_name]
                    stored_lists[list_fid] = de_list
                else:
                    stored_lists[list_fid].mergeWith(new_list, sc_name)

    def buildPatch(self, log, progress):
        keep = self.patchFile.getKeeper()
        # Relevs/Delevs List
        log.setHeader(u'= ' + self._patcher_name, True)
        log.setHeader(u'=== ' + self._de_re_header)
        for leveler in self.levelers:
            log(u'* ' + self.annotate_plugin(leveler))
        # Save to patch file
        for list_type, list_label in self._type_to_label.iteritems():
            if list_type not in self._read_write_records: continue
            log.setHeader(u'=== ' + _(u'Merged %s Lists') % list_label)
            patch_block = getattr(self.patchFile, list_type)
            stored_lists = self.type_list[list_type]
            for stored_list in sorted(stored_lists.values(),
                                      key=attrgetter('eid')):
                if not stored_list.mergeOverLast: continue
                list_fid = keep(stored_list.fid)
                patch_block.setRecord(stored_lists[list_fid])
                log(u'* ' + stored_list.eid)
                for merge_source in stored_list.mergeSources:
                    log(u'  * ' + self.annotate_plugin(merge_source))
                self._check_list(stored_list, log)
        #--Discard empty sublists
        if not self.remove_empty_sublists: return
        for list_type, list_label in self._type_to_label.iteritems():
            if list_type not in self._read_write_records: continue
            patch_block = getattr(self.patchFile, list_type)
            stored_lists = self.type_list[list_type]
            empty_lists = []
            # Build a dict mapping leveled lists to other leveled lists that
            # they are sublists in
            sub_supers = dict((x, []) for x in stored_lists.keys())
            for stored_list in sorted(stored_lists.values()):
                list_fid = stored_list.fid
                if not stored_list.items:
                    empty_lists.append(list_fid)
                else:
                    sub_lists = [x for x in stored_list.items
                                if x in sub_supers]
                    for sub_list in sub_lists:
                        sub_supers[sub_list].append(list_fid)
            #--Clear empties
            removed_empty_sublists = set()
            cleaned_lists = set()
            while empty_lists:
                empty_list = empty_lists.pop()
                if empty_list not in sub_supers: continue
                # We have an empty list, look if it's a sublist in any other
                # list
                for sub_super in sub_supers[empty_list]:
                    stored_list = stored_lists[sub_super]
                    # Remove the emtpy list from this sublist
                    old_entries = stored_list.entries
                    stored_list.entries = [x for x in stored_list.entries
                                           if x.listId != empty_list]
                    stored_list.items.remove(empty_list)
                    patch_block.setRecord(stored_list)
                    # If removing the empty list made this list empty too, then
                    # we should investigate it as well - could clean up even
                    # more lists
                    if not stored_list.items:
                        empty_lists.append(sub_super)
                    removed_empty_sublists.add(stored_lists[empty_list].eid)
                    # We don't need to write out records where another mod has
                    # already removed the empty sublist - that would just make
                    # an ITPO
                    if old_entries != stored_list.entries:
                        cleaned_lists.add(stored_list.eid)
                        keep(sub_super)
            log.setHeader(u'=== ' + _(u'Empty %s Sublists') % list_label)
            for list_eid in sorted(removed_empty_sublists, key=unicode.lower):
                log(u'* ' + list_eid)
            log.setHeader(u'=== ' + _(u'Empty %s Sublists Removed') %
                          list_label)
            for list_eid in sorted(cleaned_lists, key=unicode.lower):
                log(u'* ' + list_eid)

    # Methods for patchers to override
    def _check_list(self, record, log):
        """Checks if any warnings for the specified list have to be logged.
        Default implementation does nothing."""

    def _get_entries(self, target_list):
        """Retrieves a list of the items in the specified list. No default
        implementation, every patcher needs to override this."""
        raise AbstractError()

class ListsMerger(_PListsMerger):
    """Merges leveled lists."""
    _read_write_records = bush.game.listTypes # bush.game must be set!
    _de_tag = u'Delev'
    _re_tag = u'Relev'
    _type_to_label = {
        'LVLC': _(u'Creature'),
        'LVLN': _(u'Actor'),
        'LVLI': _(u'Item'),
        'LVSP': _(u'Spell'),
    }
    _de_re_header = _(u'Delevelers/Relevelers')

    def __init__(self, p_name, p_file, p_sources, remove_empty, tag_choices):
        super(ListsMerger, self).__init__(p_name, p_file, p_sources,
                                          remove_empty, tag_choices)
        self.empties = set()
        _skip_id = lambda x: (GPath(u'Oblivion.esm'), x)
        self._overhaul_compat(self.srcs, _skip_id)

    def _check_list(self, record, log):
        # Emit a warning for lists that may have exceeded 255
        if len(record.entries) == 255:
            log(u'  * __%s__' % _(u'Warning: Now has 255 entries, may '
                                  u'have been truncated - check and '
                                  u'fix manually!'))

    def _get_entries(self, target_list):
        return [list_entry.listId for list_entry in target_list.entries]

class CBash_ListsMerger(_AListsMerger, CBash_ListPatcher):
    allowUnloaded = False
    scanRequiresChecked = False # same as CBash_Patcher.scanRequiresChecked
    applyRequiresChecked = False # same as CBash_Patcher.applyRequiresChecked

    def __init__(self, p_name, p_file, p_sources, remove_empty, tag_choices):
        super(_AListsMerger, self).__init__(p_name, p_file, p_sources)
        self.isActive = True
        self.id_delevs = {}
        self.id_list = {}
        self.id_attrs = {}
        self.empties = set()
        self.remove_empty_sublists = remove_empty
        self.tag_choices = tag_choices
        importMods = set(self.srcs) & p_file.loadSet
        _skip_id = lambda x: FormID(GPath(u'Oblivion.esm'),x)
        self._overhaul_compat(importMods, _skip_id)

    def getTypes(self):
        return ['LVLC','LVLI','LVSP']

    def scan(self, modFile, record, bashTags, __empty=frozenset()):
        """Records information needed to apply the patch."""
        recordId = record.fid
        if recordId in self.OverhaulUOPSkips and modFile.GName == GPath(
                'Unofficial Oblivion Patch.esp'):
            return
        script = record.script
        if script and not script.ValidateFormID(self.patchFile):
            script = None
        template = record.template
        if template and not template.ValidateFormID(self.patchFile):
            template = None
        curList = [(level, listId, count) for level, listId, count in
                   record.entries_list if
                   listId.ValidateFormID(self.patchFile)]
        if recordId not in self.id_list:
            #['level', 'listId', 'count']
            self.id_list[recordId] = curList
            self.id_attrs[recordId] = [record.chanceNone, script, template,
                                       (record.flags or 0)]
        else:
            mergedList = self.id_list[recordId]
            applied_tags = self.tag_choices[modFile.GName]
            isRelev = u'Relev' in applied_tags
            isDelev = u'Delev' in applied_tags
            delevs = self.id_delevs.setdefault(recordId, __empty)
            curItems = set([listId for level, listId, count in curList])
            if isRelev:
                # Can add and set the level/count of items, but not delete
                # items
                #Ironically, the first step is to delete items that the list
                #  will add right back
                #This is an easier way to update level/count than actually
                # checking if they need changing

                #Filter out any records that may have their level/count updated
                mergedList = [entry for entry in mergedList if
                              entry[1] not in curItems]  # entry[1] = listId
                #Add any new records as well as any that were filtered out
                mergedList += curList
                #Remove the added items from the deleveled list
                delevs -= curItems
                self.id_attrs[recordId] = [record.chanceNone, script, template,
                                           (record.flags or 0)]
            else:
                #Can add new items, but can't change existing ones
                items = set([entry[1] for entry in mergedList])  # entry[1]
                # = listId
                mergedList += [(level, listId, count) for level, listId, count
                               in curList if listId not in items]
                mergedAttrs = self.id_attrs[recordId]
                self.id_attrs[recordId] =[record.chanceNone or mergedAttrs[0],
                                         script or mergedAttrs[1],
                                         template or mergedAttrs[2],
                                         (record.flags or 0) | mergedAttrs[3]]
            #--Delevs: all items in masters minus current items
            if isDelev:
                deletedItems = set([listId for master in record.History() for
                                    level, listId, count in master.entries_list
                                    if listId.ValidateFormID(
                        self.patchFile)]) - curItems
                delevs |= deletedItems
            #Remove any items that were deleveled
            mergedList = [entry for entry in mergedList if
                          entry[1] not in delevs]  # entry[1] = listId
            self.id_list[recordId] = mergedList
            self.id_delevs[recordId] = delevs

    def apply(self,modFile,record,bashTags):
        """Edits patch file as desired."""
        recordId = record.fid
        merged_ = recordId in self.id_list
        if merged_:
            self.scan(modFile,record,bashTags)
            mergedList = self.id_list[recordId]
            mergedAttrs = self.id_attrs[recordId]
            newList = [(level, listId, count) for level, listId, count in
                       record.entries_list if
                       listId.ValidateFormID(self.patchFile)]
            script = record.script
            if script and not script.ValidateFormID(self.patchFile):
                script = None
            template = record.template
            if template and not template.ValidateFormID(self.patchFile):
                template = None
            newAttrs = [record.chanceNone, script, template,
                        (record.flags or 0)]
        # Can't tell if any sublists are actually empty until they've all
        # been processed/merged
        #So every level list gets copied into the patch, so that they can be
        #  checked after the regular patch process
        #They'll get deleted from the patch there as needed.
        override = record.CopyAsOverride(self.patchFile)
        if override:
            if merged_ and (newAttrs != mergedAttrs or sorted(newList,
                key=itemgetter(1)) != sorted(mergedList, key=itemgetter(1))):
                override.chanceNone, override.script, override.template, \
                override.flags = mergedAttrs
                override.entries_list = mergedList
                self.mod_count[modFile.GName] += 1
            record.UnloadRecord()
            record._RecordID = override._RecordID

    def finishPatch(self,patchFile, progress):
        """Edits the bashed patch file directly."""
        if self.empties is None: return
        subProgress = SubProgress(progress)
        subProgress.setFull(len(self.getTypes()) * 2)
        pstate = 0
        #Clean up any empty sublists
        empties = self.empties
        emptiesAdd = empties.add
        emptiesDiscard = empties.discard
        # Only do this if 'Remove Empty Sublists' is checked
        if self.remove_empty_sublists:
            for type in self.getTypes():
                subProgress(pstate, _(u'Looking for empty %s sublists...') %
                            type + u'\n')
                #Remove any empty sublists
                madeChanges = True
                while madeChanges:
                    madeChanges = False
                    oldEmpties = empties.copy()
                    for record in getattr(patchFile,type):
                        recordId = record.fid
                        items = set([entry.listId for entry in record.entries])
                        if items:
                            emptiesDiscard(recordId)
                        else:
                            emptiesAdd(recordId)
                        toRemove = empties & items
                        if toRemove:
                            madeChanges = True
                            cleanedEntries = [entry for entry in record.entries
                                              if entry.listId not in toRemove]
                            record.entries = cleanedEntries
                            if cleanedEntries:
                                emptiesDiscard(recordId)
                            else:
                                emptiesAdd(recordId)
                    madeChanges |= oldEmpties != empties
                    pstate += 1
        # Still need to clean this, even if 'Remove Empty Sublists' is off
        # TODO(inf) We could avoid this if we rewrote apply() above
        for type in self.getTypes():
            subProgress(pstate,
                        _(u'Cleaning %s ITPOs...') % type + u'\n')
            # Remove any identical to winning lists, except those that were
            # merged into the patch
            for record in getattr(patchFile,type):
                conflicts = record.Conflicts()
                numConflicts = len(conflicts)
                if numConflicts:
                    curConflict = 1  # Conflict at 0 will be the patchfile.
                    # No sense comparing it to itself.
                    #Find the first conflicting record that wasn't merged
                    while curConflict < numConflicts:
                        prevRecord = conflicts[curConflict]
                        if prevRecord.GetParentMod().GName not in \
                                patchFile.mergeSet:
                            break
                        curConflict += 1
                    else:
                        continue
                    # If the record in the patchfile matches the previous
                    # non-merged record, delete it.
                    #Ordering doesn't matter, hence the conversion to sets
                    if set(prevRecord.entries_list) == set(
                            record.entries_list) and [record.chanceNone,
                                                      record.script,
                                                      record.template,
                                                      record.flags] == [
                        prevRecord.chanceNone, prevRecord.script,
                        prevRecord.template, prevRecord.flags]:
                        record.DeleteRecord()
            pstate += 1
        self.empties = None

    def buildPatchLog(self,log):
        """Will write to log."""
        #--Log
        mod_count = self.mod_count
        log.setHeader(u'= ' + self._patcher_name)
        log(u'* '+_(u'Modified LVL') + u': %d' % (sum(mod_count.values()),))
        for srcMod in load_order.get_ordered(mod_count.keys()):
            log(u'  * %s: %d' % (srcMod.s,mod_count[srcMod]))
        self.mod_count = Counter()

#------------------------------------------------------------------------------
class FidListsMerger(_PListsMerger):
    """Merges FormID lists."""
    scanOrder = 46
    editOrder = 46
    _read_write_records = ('FLST',)
    _de_tag = u'Deflst'
    _type_to_label = {'FLST': _(u'FormID')}
    _de_re_header = _(u'Deflsters')

    def _get_entries(self, target_list):
        return target_list.formIDInList

#------------------------------------------------------------------------------
class _AContentsChecker(Abstract_Patcher):
    """Checks contents of leveled lists, inventories and containers for
    correct content types."""
    group = _(u'Special')
    scanOrder = 50
    editOrder = 50
    contType_entryTypes = bush.game.cc_valid_types
    contTypes = set(contType_entryTypes)
    entryTypes = set(chain.from_iterable(contType_entryTypes.itervalues()))

class ContentsChecker(_AContentsChecker,Patcher):

    def __init__(self, p_name, p_file):
        super(ContentsChecker, self).__init__(p_name, p_file)
        self.fid_to_type = {}
        self.id_eid = {}

    def getReadClasses(self):
        """Returns load factory classes needed for reading."""
        return tuple(self.contTypes | self.entryTypes) if self.isActive else ()

    def getWriteClasses(self):
        """Returns load factory classes needed for writing."""
        return tuple(self.contTypes) if self.isActive else ()

    def scanModFile(self, modFile, progress):
        """Scan modFile."""
        modFile.convertToLongFids(self.contTypes | self.entryTypes)
        # First, map fids to record type for all records for the valid record
        # types. We need to know if a given fid belongs to one of the valid
        # types, otherwise we want to remove it.
        id_type = self.fid_to_type
        for entry_type in self.entryTypes:
            if entry_type not in modFile.tops: continue
            for record in modFile.tops[entry_type].getActiveRecords():
                fid = record.fid
                if fid not in id_type:
                    id_type[fid] = entry_type
        # Second, make sure the Bashed Patch contains all records for all the
        # types we may end up patching
        for cont_type in self.contTypes:
            if cont_type not in modFile.tops: continue
            patchBlock = getattr(self.patchFile, cont_type)
            pb_add_record = patchBlock.setRecord
            id_records = patchBlock.id_records
            for record in modFile.tops[cont_type].getActiveRecords():
                if record.fid not in id_records:
                    pb_add_record(record.getTypeCopy())

    def buildPatch(self,log,progress):
        """Make changes to patchfile."""
        if not self.isActive: return
        modFile = self.patchFile
        keep = self.patchFile.getKeeper()
        fid_to_type = self.fid_to_type
        id_eid = self.id_eid
        log.setHeader(u'= ' + self._patcher_name)
        # Execute each pass - one pass is needed for every distinct record
        # class layout, e.g. leveled list classes generally share the same
        # layout (LVLI.entries[i].listId, LVLN.entries[i].listId, etc.)
        # whereas CONT, NPC_, etc. have a different layout (CONT.items[i].item,
        # NPC_.items[i].item)
        for cc_pass in bush.game.cc_passes:
            # Validate our pass syntax first
            if len(cc_pass) not in (2, 3):
                raise RuntimeError(u'Unknown Contents Checker pass type %s' %
                                   repr(cc_pass))
            # See explanation below (entry_fid definition)
            needs_entry_attr = len(cc_pass) == 3
            # First entry in the pass is always the record types this pass
            # applies to
            for rec_type in cc_pass[0]:
                if rec_type not in modFile.tops: continue
                # Set up a dict to track which entries we have removed per fid
                id_removed = defaultdict(list)
                # Grab the types that are actually valid for our current record
                # types
                valid_types = set(self.contType_entryTypes[rec_type])
                for record in modFile.tops[rec_type].records:
                    group_attr = cc_pass[1]
                    # Set up two lists, one containing the current record
                    # contents, and a second one that we will be filling with
                    # only valid entries.
                    new_entries = []
                    current_entries = getattr(record, group_attr)
                    for entry in current_entries:
                        # If len(cc_pass) == 3, then this is a list of
                        # MelObject instances, so we have to take an additional
                        # step to retrieve the fids (e.g. for MelGroups or
                        # MelStructs)
                        entry_fid = getattr(entry, cc_pass[2]) \
                            if needs_entry_attr else entry
                        # Actually check if the fid has the correct type. If
                        # it's not valid, then this will return None, which is
                        # obviously not in the valid_types.
                        if fid_to_type.get(entry_fid, None) in valid_types:
                            # The type is valid, so grow our new list
                            new_entries.append(entry)
                        else:
                            # The type is wrong, so discard the entry. At this
                            # point, we know that the lists have diverged - but
                            # we need to keep going, there may be more invalid
                            # entries for this record.
                            id_removed[record.fid].append(entry_fid)
                            id_eid[record.fid] = record.eid
                    # Check if after filtering using the code above, our two
                    # lists have diverged and, if so, keep the changed record
                    if len(new_entries) != len(current_entries):
                        setattr(record, group_attr, new_entries)
                        keep(record.fid)
                # Log the result if we removed at least one entry
                if id_removed:
                    log(u"\n=== " + rec_type)
                    for contId in sorted(id_removed):
                        log(u'* ' + id_eid[contId])
                        for removedId in sorted(id_removed[contId]):
                            log(u'  . %s: %06X' % (removedId[0].s,
                                                   removedId[1]))

class CBash_ContentsChecker(_AContentsChecker,CBash_Patcher):
    allowUnloaded = False # avoid the srcs check in CBash_Patcher.initData

    def __init__(self, p_name, p_file):
        super(CBash_ContentsChecker, self).__init__(p_name, p_file)
        self.listTypes = {'LVSP', 'LVLC', 'LVLI'}
        self.containerTypes = {'CONT', 'CREA', 'NPC_'}
        self.mod_type_id_badEntries = {}
        self.knownGood = set()

    def getTypes(self):
        """Returns the group types that this patcher checks"""
        return ['CONT','CREA','NPC_','LVLI','LVLC','LVSP']

    def apply(self,modFile,record,bashTags):
        """Edits patch file as desired."""
        rec_type = record._Type
        Current = self.patchFile.Current
        badEntries = set()
        goodEntries = []
        knownGood = self.knownGood
        knownGoodAdd = knownGood.add
        goodAppend = goodEntries.append
        badAdd = badEntries.add
        validEntries = self.contType_entryTypes[rec_type]
        if rec_type in self.listTypes:
            topattr, subattr = ('entries','listId')
        else: #Is a container type
            topattr, subattr = ('items','item')

        for entry in getattr(record,topattr):
            entryId = getattr(entry,subattr)
            #Cache known good entries to decrease execution time
            if entryId in knownGood:
                goodAppend(entry)
            else:
                if entryId.ValidateFormID(self.patchFile):
                    entryRecords = Current.LookupRecords(entryId)
                else:
                    entryRecords = None
                if not entryRecords:
                    badAdd((_(u'NONE'),entryId,None,_(u'NONE')))
                else:
                    entryRecord = entryRecords[0]
                    if entryRecord.recType in validEntries:
                        knownGoodAdd(entryId)
                        goodAppend(entry)
                    else:
                        badAdd((entryRecord.eid, entryId,
                                entryRecord.GetParentMod().GName,
                                entryRecord.recType))
                        entryRecord.UnloadRecord()

        if badEntries:
            override = record.CopyAsOverride(self.patchFile)
            if override:
                setattr(override, topattr, goodEntries)
                type_id_badEntries = self.mod_type_id_badEntries.setdefault(
                    modFile.GName, {})
                id_badEntries = type_id_badEntries.setdefault(rec_type, {})
                id_badEntries[record.eid] = badEntries.copy()
                record.UnloadRecord()
                record._RecordID = override._RecordID

    def buildPatchLog(self,log):
        """Will write to log."""
        if not self.isActive: return
        #--Log
        mod_type_id_badEntries = self.mod_type_id_badEntries
        log.setHeader(u'= ' + self._patcher_name)
        for mod, type_id_badEntries in mod_type_id_badEntries.iteritems():
            log(u'\n=== %s' % mod.s)
            for type,id_badEntries in type_id_badEntries.iteritems():
                log(u'  * '+_(u'Cleaned %s: %d') % (type,len(id_badEntries)))
                for id, badEntries in id_badEntries.iteritems():
                    log(u'    * %s : %d' % (id,len(badEntries)))
                    for entry in sorted(badEntries, key=itemgetter(0)):
                        longId = entry[1]
                        if entry[2]:
                            modName = entry[2].s
                        else:
                            try:
                                modName = longId[0].s
                            except:
                                log(u'        . ' + _(
                                    u'Unloaded Object or Undefined Reference'))
                                continue
                        log(u'        . ' + _(
                            u'Editor ID: "%s", Object ID %06X: Defined in '
                            u'mod "%s" as %s') % (
                                entry[0], longId[1], modName, entry[3]))
        self.mod_type_id_badEntries = {}
