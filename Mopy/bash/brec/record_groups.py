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
"""Houses classes for reading, manipulating and writing groups of records."""

# Python imports
from __future__ import division, print_function
import struct
from itertools import chain
from operator import itemgetter
# Wrye Bash imports
from .mod_io import GrupHeader, ModReader, RecordHeader, TopGrupHeader
from .record_structs import MreRecord
from .utils_constants import group_types
from ..bolt import GPath, sio
from ..exception import AbstractError, ArgumentError, ModError

class MobBase(object):
    """Group of records and/or subgroups. This basic implementation does not
    support unpacking, but can report its number of records and be written."""

    __slots__ = ['header','size','label','groupType','stamp','debug','data',
                 'changed','numRecords','loadFactory','inName'] ##: nice collection of forbidden names, including header -> group_header

    def __init__(self, header, loadFactory, ins=None, do_unpack=False):
        self.header = header
        self.size = header.size
        if header.recType == b'GRUP':
            self.label, self.groupType, self.stamp = (
                header.label, header.groupType, header.stamp)
        else: # TODO(ut) should MobBase used for *non* GRUP headers??
            # Yes it's weird, but this is how it needs to work
            self.label, self.groupType, self.stamp = (
                header.flags1, header.fid, header.flags2)
        self.debug = False
        self.data = None
        self.changed = False
        self.numRecords = -1
        self.loadFactory = loadFactory
        self.inName = ins and ins.inName
        if ins: self.load(ins, do_unpack)

    def load(self, ins=None, do_unpack=False):
        """Load data from ins stream or internal data buffer."""
        if self.debug: print(u'GRUP load:',self.label)
        #--Read, but don't analyze.
        if not do_unpack:
            self.data = ins.read(self.size - RecordHeader.rec_header_size,
                                 type(self))
        #--Analyze ins.
        elif ins is not None:
            self.load_rec_group(ins,
                ins.tell() + self.size - RecordHeader.rec_header_size)
        #--Analyze internal buffer.
        else:
            with self.getReader() as reader:
                self.load_rec_group(reader, reader.size)
        #--Discard raw data?
        if do_unpack:
            self.data = None
            self.setChanged()

    def setChanged(self,value=True):
        """Sets changed attribute to value. [Default = True.]"""
        self.changed = value

    def getSize(self):
        """Returns size (including size of any group headers)."""
        if self.changed: raise AbstractError
        return self.size

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self (if plusSelf), unless
        there's no subrecords, in which case, it returns 0."""
        if self.changed:
            raise AbstractError
        elif self.numRecords > -1: #--Cached value.
            return self.numRecords
        elif not self.data: #--No data >> no records, not even self.
            self.numRecords = 0
            return self.numRecords
        else:
            numSubRecords = 0
            reader = self.getReader()
            errLabel = group_types[self.groupType]
            readerAtEnd = reader.atEnd
            readerRecHeader = reader.unpackRecHeader
            readerSeek = reader.seek
            while not readerAtEnd(reader.size,errLabel):
                header = readerRecHeader()
                recType,size = header.recType,header.size
                if recType == 'GRUP': size = 0
                readerSeek(size,1)
                numSubRecords += 1
            self.numRecords = numSubRecords + includeGroups
            return self.numRecords

    def dump(self,out):
        """Dumps record header and data into output file stream."""
        if self.changed:
            raise AbstractError
        if self.numRecords == -1:
            self.getNumRecords()
        if self.numRecords > 0:
            self.header.size = self.size
            out.write(self.header.pack_head())
            out.write(self.data)

    def getReader(self):
        """Returns a ModReader wrapped around self.data."""
        return ModReader(self.inName,sio(self.data))

    # Abstract methods --------------------------------------------------------
    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        raise AbstractError

    def get_all_signatures(self):
        """Returns a set of all signatures contained in this block."""
        raise AbstractError

    def indexRecords(self):
        """Indexes records by fid."""
        raise AbstractError

    def iter_records(self):
        """Flattens the structure of this record block into a linear sequence
        of records. Works as an iterator for memory reasons."""
        raise AbstractError

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        raise AbstractError

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        raise AbstractError

    ##: params here are not the prettiest
    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        """Merges records from the specified block into this block and performs
        merge filtering if doFilter is True.

        :param block: The block to merge records from.
        :param loadSet: The set of currently loaded plugins.
        :param mergeIds: A set into which the fids of all records that will be
            merged by this operation will be added.
        :param iiSkipMerge: If True, skip merging and only perform merge
            filtering. Used by IIM mode.
        :param doFilter: If True, perform merge filtering."""
        raise AbstractError

    def updateMasters(self, masters):
        """Updates set of master names according to masters actually used."""
        raise AbstractError

    def updateRecords(self,block,mapper,toLong):
        """Looks through all of the records in 'block', and updates any
        records in self that exist with the data in 'block'."""
        raise AbstractError

#------------------------------------------------------------------------------
class MobObjects(MobBase):
    """Represents a top level group consisting of one type of record only. I.e.
    all top groups except CELL, WRLD and DIAL."""

    def __init__(self, header, loadFactory, ins=None, do_unpack=False):
        self.records = []
        self.id_records = {}
        MobBase.__init__(self, header, loadFactory, ins, do_unpack)

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        expType = self.label
        recClass = self.loadFactory.getRecClass(expType)
        errLabel = expType + u' Top Block'
        records = self.records
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        recordsAppend = records.append
        while not insAtEnd(endPos,errLabel):
            #--Get record info and handle it
            header = insRecHeader()
            recType = header.recType
            if recType != expType:
                raise ModError(ins.inName,u'Unexpected %s record in %s group.'
                               % (recType,expType))
            record = recClass(header,ins,True)
            recordsAppend(record)
        self.setChanged()

    def getActiveRecords(self):
        """Returns non-ignored records."""
        return [record for record in self.records if not record.flags1.ignored]

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self."""
        numRecords = len(self.records)
        if numRecords: numRecords += includeGroups #--Count self
        self.numRecords = numRecords
        return numRecords

    def getSize(self):
        """Returns size (including size of any group headers)."""
        if not self.changed:
            return self.size
        else:
            hsize = RecordHeader.rec_header_size
            return hsize + sum(
                (hsize + record.getSize()) for record in self.records)

    def dump(self,out):
        """Dumps group header and then records."""
        if not self.changed:
            out.write(TopGrupHeader(self.size, self.label, 0, ##: self.header.pack_head() ?
                                    self.stamp).pack_head())
            out.write(self.data)
        else:
            size = self.getSize()
            if size == RecordHeader.rec_header_size: return
            out.write(TopGrupHeader(size,self.label,0,self.stamp).pack_head())
            for record in self.records:
                record.dump(out)

    def updateMasters(self,masters):
        """Updates set of master names according to masters actually used."""
        for record in self.records:
            record.updateMasters(masters)

    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        for record in self.records:
            record.convertFids(mapper,toLong)
        self.id_records.clear()

    def get_all_signatures(self):
        return {self.label}

    def indexRecords(self):
        """Indexes records by fid."""
        self.id_records.clear()
        for record in self.records:
            self.id_records[record.fid] = record

    def getRecord(self,fid,default=None):
        """Gets record with corresponding id.
        If record doesn't exist, returns None."""
        if not self.records: return default
        if not self.id_records: self.indexRecords()
        return self.id_records.get(fid,default)

    def setRecord(self,record):
        """Adds record to record list and indexed."""
        from .. import bosh
        if self.records and not self.id_records:
            self.indexRecords()
        record_id = record.fid
        if record.isKeyedByEid:
            if record_id == (bosh.modInfos.masterName, 0):
                record_id = record.eid
        if record_id in self.id_records:
            oldRecord = self.id_records[record_id]
            index = self.records.index(oldRecord)
            self.records[index] = record
        else:
            self.records.append(record)
        self.id_records[record_id] = record

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        from .. import bosh
        self.records = [record for record in self.records if (record.fid == (
            record.isKeyedByEid and bosh.modInfos.masterName,
            0) and record.eid in p_keep_ids) or record.fid in p_keep_ids]
        self.id_records.clear()
        self.setChanged()

    def updateRecords(self,srcBlock,mapper,mergeIds):
        """Looks through all of the records in 'srcBlock', and updates any
        records in self that exist within the data in 'block'."""
        fids = set([record.fid for record in self.records])
        for record in srcBlock.getActiveRecords():
            if mapper(record.fid) in fids:
                record = record.getTypeCopy(mapper)
                self.setRecord(record)
                mergeIds.discard(record.fid)

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        # YUCK, drop these local imports!
        from ..bosh import modInfos
        from ..mod_files import MasterSet
        bad_form = (GPath(u'Oblivion.esm'), 0xA31D) # DarkPCB record
        _null_fid = (modInfos.masterName, 0)
        filtered = []
        filteredAppend = filtered.append
        loadSetIsSuperset = loadSet.issuperset
        mergeIdsAdd = mergeIds.add
        copy_to_self = self.setRecord
        for record in block.getActiveRecords():
            fid = record.fid
            if fid == bad_form: continue
            #--Include this record?
            if doFilter:
                # If we're Filter-tagged, perform merge filtering. Then, check
                # if the record has any FormIDs with masters that are on disk
                # left. If it does not, skip the whole record (because all of
                # its contents have been merge-filtered out).
                record.mergeFilter(loadSet)
                masters = MasterSet()
                record.updateMasters(masters)
                if not loadSetIsSuperset(masters):
                    continue
            # We're either not Filter-tagged or we want to keep this record
            filteredAppend(record)
            # If we're IIM-tagged and this is not one of the IIM-approved
            # record types, skip merging
            if iiSkipMerge: continue
            # We're past all hurdles - stick a copy of this record into
            # ourselves and mark it as merged
            if record.isKeyedByEid and fid == _null_fid:
                mergeIdsAdd(record.eid)
            else:
                mergeIdsAdd(fid)
            copy_to_self(record.getTypeCopy())
        # Apply any merge filtering we've done above to the record block in
        # question. That way, patchers won't see the records that have been
        # filtered out here.
        block.records = filtered
        block.indexRecords()

    def iter_records(self):
        return iter(self.records)

    def __repr__(self):
        return u'<%s GRUP: %u record(s)>' % (self.label, len(self.records))

#------------------------------------------------------------------------------
##: This should be refactored (alongside MreDialBase) to eventually expand it
# to FO4's QUST groups
class MobDials(MobObjects):
    """DIAL top block of mod file."""

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        expType = self.label
        recClass = MreRecord.type_class[b'DIAL']
        errLabel = expType + u' Top Block'
        records = self.records
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        recordsAppend = records.append
        loadGetRecClass = self.loadFactory.getRecClass
        record = None
        recordLoadInfos = None
        while not insAtEnd(endPos,errLabel):
            #--Get record info and handle it
            header = insRecHeader()
            recType = header.recType
            if recType == expType:
                record = recClass(header,ins,True)
                recordLoadInfos = record.loadInfos
                recordsAppend(record)
            elif recType == 'GRUP':
                (size, groupType, stamp) = (header.size, header.groupType,
                                            header.stamp)
                if groupType == 7:
                    try: # record/recordLoadInfos should be initialized in 'if'
                        record.infoStamp = stamp
                        infoClass = loadGetRecClass('INFO')
                        hsize = RecordHeader.rec_header_size
                        if infoClass:
                            recordLoadInfos(ins, ins.tell() + size - hsize,
                                            infoClass)
                        else:
                            ins.seek(ins.tell() + size - hsize)
                    except AttributeError:
                        raise ModError(self.inName, u'Malformed Plugin: '
                            u'Exterior CELL subblock before worldspace GRUP')
                else:
                    raise ModError(self.inName,
                                   u'Unexpected subgroup %d in DIAL group.'
                                   % groupType)
            else:
                raise ModError(self.inName,
                               u'Unexpected %s record in %s group.'
                               % (recType,expType))
        self.setChanged()

    def getSize(self):
        """Returns size of records plus group and record headers."""
        if not self.changed:
            return self.size
        hsize = RecordHeader.rec_header_size
        size = hsize
        for record in self.records:
            # Resynchronize the stamps (##: unsure if needed)
            record.infoStamp = self.stamp
            size += hsize + record.getSize()
            if record.infos:
                size += hsize + sum(
                    hsize + info.getSize() for info in record.infos)
        return size

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self plus info records."""
        self.numRecords = (
            len(self.records) + includeGroups * bool(self.records) +
            sum((includeGroups + len(x.infos)) for x in self.records if
                x.infos)
        )
        return self.numRecords

    def get_all_signatures(self):
        return super(MobDials, self).get_all_signatures() | {b'INFO'}

    def iter_records(self):
        return chain(iter(self.records), chain.from_iterable(
            r.infos for r in self.records))

    def keepRecords(self, p_keep_ids):
        super(MobDials, self).keepRecords(p_keep_ids)
        for record in self.records:
            record.infos = [i for i in record.infos if i.fid in p_keep_ids]

    def updateRecords(self, srcBlock, mapper, mergeIds):
        id_dials = {r.fid: r for r in self.records}
        merge_ids_discard = mergeIds.discard
        for record in srcBlock.getActiveRecords():
            src_dial_fid = mapper(record.fid)
            # First check if we have a corresponding DIAL record and, if so,
            # retrieve it
            if src_dial_fid in id_dials:
                patch_dial = id_dials[src_dial_fid]
                updated_infos = patch_dial.infos
                # Build up a dict mapping INFO fids to their positions in the
                # INFO list of this DIAL record in the patch file
                id_patch_infos = {}
                for i, p in enumerate(updated_infos):
                    id_patch_infos[p.fid] = i
                # Now, update each INFO child that's present in both the source
                # mod and the patch file individually
                for src_info in record.infos:
                    info_fid = mapper(src_info.fid)
                    if info_fid in id_patch_infos:
                        updated_infos[id_patch_infos[info_fid]] = \
                            src_info.getTypeCopy(mapper)
                        merge_ids_discard(info_fid)
                # We always have to make a copy of the main DIAL record to
                # carry forward changes, but we assign the already updated
                # INFOs to it after doing that
                record = record.getTypeCopy(mapper)
                self.setRecord(record)
                record.infos = updated_infos
                # Note that we can only discard the DIAL record from mergeIds
                # if none of its children are marked as merged, since otherwise
                # we'd end up wanting to keep a child but not its parent
                if not any(i.fid in mergeIds for i in updated_infos):
                    merge_ids_discard(record.fid)

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        from ..mod_files import MasterSet # YUCK
        filtered_dials = []
        filtered_dials_append = filtered_dials.append
        loadSetIsSuperset = loadSet.issuperset
        mergeIdsAdd = mergeIds.add
        copy_to_self = self.setRecord
        # We'll need an up-to-date self.id_records, see usage below
        self.indexRecords()
        for record in block.getActiveRecords():
            # A list of the INFO children that were previously in the patch
            # file's version of this DIAL record
            patch_infos = []
            # Maps the FormID of each INFO child in patch_infos to its position
            # in that list
            id_patch_infos = {}
            # Check if we want this DIAL record before we start checking the
            # INFO children
            if doFilter:
                # Filter the DIAL record, skip it (and by extension all its
                # INFO children) if filtered out
                record.mergeFilter(loadSet)
                masters = MasterSet()
                record.updateMasters(masters)
                if not loadSetIsSuperset(masters):
                    continue
            # Not Filter-tagged or we want this DIAL record
            filtered_dials_append(record)
            # In IIM, we can't just skip to the next record since we also need
            # to filter the INFO children that came with this DIAL record
            if not iiSkipMerge:
                # We're past all hurdles - mark the record as merged, but
                # before we can stick a copy into ourselves we need to preserve
                # the current INFO children for later merging
                mergeIdsAdd(record.fid)
                old_dial = self.id_records.get(record.fid)
                if old_dial:
                    patch_infos = old_dial.infos
                    for i, p in enumerate(patch_infos):
                        id_patch_infos[p.fid] = i
                new_dial = record.getTypeCopy()
                new_dial.infos = patch_infos
                copy_to_self(new_dial)
            # Now we're ready to filter and merge the INFO children
            filtered_infos = []
            filtered_infos_append = filtered_infos.append
            for info_rec in record.infos:
                if info_rec.flags1.ignored: continue
                if doFilter:
                    # Filter the INFO child, skip if filtered out
                    info_rec.mergeFilter(loadSet)
                    masters = MasterSet()
                    info_rec.updateMasters(masters)
                    if not loadSetIsSuperset(masters):
                        continue
                # Not Filter-tagged or we want this INFO child
                filtered_infos_append(info_rec)
                # In IIM, skip all merging (duh)
                if iiSkipMerge: continue
                # We're past all hurdles - stick a copy of this INFO child into
                # the current DIAL record and mark it as merged
                mergeIdsAdd(info_rec.fid)
                info_fid = info_rec.fid
                new_info_rec = info_rec.getTypeCopy()
                if info_fid in id_patch_infos:
                    patch_infos[id_patch_infos[info_fid]] = new_info_rec
                else:
                    patch_infos.append(new_info_rec)
            record.infos = filtered_infos
        block.records = filtered_dials
        block.indexRecords()

#------------------------------------------------------------------------------
class MobCell(MobBase):
    """Represents cell block structure -- including the cell and all
    subrecords."""
    __slots__ = ['cell','persistent','distant','temp', 'land','pgrd']

    def __init__(self, header, loadFactory, cell, ins=None, do_unpack=False):
        self.cell = cell
        self.persistent = []
        self.distant = []
        self.temp = []
        self.land = None
        self.pgrd = None
        MobBase.__init__(self, header, loadFactory, ins, do_unpack)

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        cellType_class = self.loadFactory.getCellTypeClass()
        persistent,temp,distant = self.persistent,self.temp,self.distant
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        cellGet = cellType_class.get
        persistentAppend = persistent.append
        tempAppend = temp.append
        distantAppend = distant.append
        insSeek = ins.seek
        while not insAtEnd(endPos,'Cell Block'):
            subgroupLoaded = [False,False,False]
            header = insRecHeader()
            recType = header.recType
            recClass = cellGet(recType)
            if recType == 'GRUP':
                groupType = header.groupType
                if groupType not in (8, 9, 10):
                    raise ModError(self.inName,
                                   u'Unexpected subgroup %d in cell children '
                                   u'group.' % groupType)
                if subgroupLoaded[groupType - 8]:
                    raise ModError(self.inName,
                                   u'Extra subgroup %d in cell children '
                                   u'group.' % groupType)
                else:
                    subgroupLoaded[groupType - 8] = True
            elif recType not in cellType_class:
                raise ModError(self.inName,
                               u'Unexpected %s record in cell children '
                               u'group.' % recType)
            elif not recClass:
                insSeek(header.size,1)
            elif recType in ('REFR','ACHR','ACRE'):
                record = recClass(header,ins,True)
                if   groupType ==  8: persistentAppend(record)
                elif groupType ==  9: tempAppend(record)
                elif groupType == 10: distantAppend(record)
            elif recType == 'LAND':
                self.land = recClass(header,ins,False)
            elif recType == 'PGRD':
                self.pgrd = recClass(header,ins,False)
        self.setChanged()

    def getSize(self):
        """Returns size (including size of any group headers)."""
        return RecordHeader.rec_header_size + self.cell.getSize() + \
               self.getChildrenSize()

    def getChildrenSize(self):
        """Returns size of all children, including the group header.  This
        does not include the cell itself."""
        size = self.getPersistentSize() + self.getTempSize() + \
               self.getDistantSize()
        return size + RecordHeader.rec_header_size * bool(size)

    def getPersistentSize(self):
        """Returns size of all persistent children, including the persistent
        children group."""
        hsize = RecordHeader.rec_header_size
        size = sum(hsize + x.getSize() for x in self.persistent)
        return size + hsize * bool(size)

    def getTempSize(self):
        """Returns size of all temporary children, including the temporary
        children group."""
        hsize = RecordHeader.rec_header_size
        size = sum(hsize + x.getSize() for x in self.temp)
        if self.pgrd: size += hsize + self.pgrd.getSize()
        if self.land: size += hsize + self.land.getSize()
        return size + hsize * bool(size)

    def getDistantSize(self):
        """Returns size of all distant children, including the distant
        children group."""
        hsize = RecordHeader.rec_header_size
        size = sum(hsize + x.getSize() for x in self.distant)
        return size + hsize * bool(size)

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self and all children."""
        count = 1 + includeGroups # Cell GRUP and CELL record
        if self.persistent:
            count += len(self.persistent) + includeGroups
        if self.temp or self.pgrd or self.land:
            count += len(self.temp) + includeGroups
            count += bool(self.pgrd) + bool(self.land)
        if self.distant:
            count += len(self.distant) + includeGroups
        return count

    def getBsb(self):
        """Returns tesfile block and sub-block indices for cells in this group.
        For interior cell, bsb is (blockNum,subBlockNum). For exterior cell,
        bsb is ((blockY,blockX),(subblockY,subblockX))."""
        cell = self.cell
        #--Interior cell
        if cell.flags.isInterior:
            baseFid = cell.fid & 0x00FFFFFF
            return baseFid%10, baseFid%100//10
        #--Exterior cell
        else:
            x,y = cell.posY,cell.posX
            if x is None: x = 0
            if y is None: y = 0
            return (x//32, y//32), (x//8, y//8)

    def dump(self,out):
        """Dumps group header and then records."""
        self.cell.getSize()
        self.cell.dump(out)
        childrenSize = self.getChildrenSize()
        if not childrenSize: return
        self._write_group_header(out, childrenSize, 6)
        if self.persistent:
            self._write_group_header(out, self.getPersistentSize(), 8)
            for record in self.persistent:
                record.dump(out)
        if self.temp or self.pgrd or self.land:
            self._write_group_header(out, self.getTempSize(), 9)
            if self.pgrd:
                self.pgrd.dump(out)
            if self.land:
                self.land.dump(out)
            for record in self.temp:
                record.dump(out)
        if self.distant:
            self._write_group_header(out, self.getDistantSize(), 10)
            for record in self.distant:
                record.dump(out)

    def _write_group_header(self, out, group_size, group_type):
        out.write(GrupHeader(group_size, self.cell.fid, group_type,
                             self.stamp).pack_head()) # FIXME was TESIV only - self.extra??

    #--Fid manipulation, record filtering ----------------------------------
    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        self.cell.convertFids(mapper,toLong)
        for record in self.temp:
            record.convertFids(mapper,toLong)
        for record in self.persistent:
            record.convertFids(mapper,toLong)
        for record in self.distant:
            record.convertFids(mapper,toLong)
        if self.land:
            self.land.convertFids(mapper,toLong)
        if self.pgrd:
            self.pgrd.convertFids(mapper,toLong)

    def get_all_signatures(self):
        cell_sigs = {self.cell.recType}
        cell_sigs.update(r.recType for r in self.temp)
        cell_sigs.update(r.recType for r in self.persistent)
        cell_sigs.update(r.recType for r in self.distant)
        if self.land: cell_sigs.add(self.land.recType)
        if self.pgrd: cell_sigs.add(self.pgrd.recType)
        return cell_sigs

    def updateMasters(self,masters):
        """Updates set of master names according to masters actually used."""
        self.cell.updateMasters(masters)
        for record in self.persistent:
            record.updateMasters(masters)
        for record in self.distant:
            record.updateMasters(masters)
        for record in self.temp:
            record.updateMasters(masters)
        if self.land:
            self.land.updateMasters(masters)
        if self.pgrd:
            self.pgrd.updateMasters(masters)

    def updateRecords(self,srcBlock,mapper,mergeIds):
        """Updates any records in 'self' that exist in 'srcBlock'."""
        mergeDiscard = mergeIds.discard
        selfGetter = self.__getattribute__
        srcGetter = srcBlock.__getattribute__
        for attr in ('cell','pgrd','land'):
            myRecord = selfGetter(attr)
            record = srcGetter(attr)
            if myRecord and record:
                if myRecord.fid != mapper(record.fid):
                    raise ArgumentError(u"Fids don't match! %08x, %08x" % (
                        myRecord.fid,record.fid))
                if not record.flags1.ignored:
                    record = record.getTypeCopy(mapper)
                    setattr(self, attr, record)
                    mergeDiscard(record.fid)
        for attr in ('persistent','temp','distant'):
            recordList = selfGetter(attr)
            fids = {record.fid: i for i, record in enumerate(recordList)}
            for record in srcGetter(attr):
                if not record.flags1.ignored and mapper(record.fid) in fids:
                    record = record.getTypeCopy(mapper)
                    recordList[fids[record.fid]] = record
                    mergeDiscard(record.fid)

    def iter_records(self):
        single_recs = [x for x in (self.cell, self.pgrd, self.land) if x]
        return chain(single_recs, self.persistent, self.distant, self.temp)

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        if self.pgrd and self.pgrd.fid not in p_keep_ids:
            self.pgrd = None
        if self.land and self.land.fid not in p_keep_ids:
            self.land = None
        self.temp       = [x for x in self.temp if x.fid in p_keep_ids]
        self.persistent = [x for x in self.persistent if x.fid in p_keep_ids]
        self.distant    = [x for x in self.distant if x.fid in p_keep_ids]
        if self.pgrd or self.land or self.persistent or self.temp or \
                self.distant:
            p_keep_ids.add(self.cell.fid)
        self.setChanged()

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        from ..mod_files import MasterSet # YUCK
        loadSetIsSuperset = loadSet.issuperset
        mergeIdsAdd = mergeIds.add
        for single_attr in (u'cell', u'pgrd', u'land'):
            # Grab the version that we're trying to merge, and check if there's
            # even one present
            src_rec = getattr(block, single_attr)
            if src_rec and not src_rec.flags1.ignored:
                # If we're Filter-tagged, perform merge filtering first
                if doFilter:
                    src_rec.mergeFilter(loadSet)
                    masters = MasterSet()
                    src_rec.updateMasters(masters)
                    if not loadSetIsSuperset(masters):
                        # Filtered out, discard this record and skip to next
                        setattr(block, single_attr, None)
                        continue
                # In IIM, skip all merging (duh)
                if iiSkipMerge: continue
                dest_rec = getattr(self, single_attr)
                if dest_rec and dest_rec.fid != src_rec.fid:
                    raise ArgumentError(u"Fids don't match! %08x, %08x" % (
                        dest_rec.fid, src_rec.fid))
                # We're past all hurdles - stick a copy of this record into
                # ourselves and mark it as merged
                mergeIdsAdd(src_rec.fid)
                setattr(self, single_attr, src_rec.getTypeCopy())
        for list_attr in (u'temp', u'persistent', u'distant'):
            filtered_list = []
            filtered_append = filtered_list.append
            # Build a mapping from fids in the current list to the index at
            # which they're stored ##: cache? see also updateRecords above
            dest_list = getattr(self, list_attr)
            append_to_dest = dest_list.append
            id_fids = {record.fid: i for i, record
                       in enumerate(dest_list)}
            for src_rec in getattr(block, list_attr):
                if src_rec.flags1.ignored: continue
                # If we're Filter-tagged, perform merge filtering first
                if doFilter:
                    src_rec.mergeFilter(loadSet)
                    masters = MasterSet()
                    src_rec.updateMasters(masters)
                    if not loadSetIsSuperset(masters):
                        continue
                # We're either not Filter-tagged or we want to keep this record
                filtered_append(src_rec)
                # In IIM, skip all merging (duh)
                if iiSkipMerge: continue
                # We're past all hurdles - stick a copy of this record into
                # ourselves and mark it as merged
                src_fid = src_rec.fid
                rec_copy = src_rec.getTypeCopy()
                mergeIdsAdd(src_fid)
                if rec_copy.fid in id_fids:
                    dest_list[id_fids[src_fid]] = rec_copy
                else:
                    append_to_dest(rec_copy)
            # Apply any merge filtering we've done here
            setattr(block, list_attr, filtered_list)

#------------------------------------------------------------------------------
class MobCells(MobBase):
    """A block containing cells. Subclassed by MobWorld and MobICells.

    Note that "blocks" here only roughly match the file block structure.

    "Bsb" is a tuple of the file (block,subblock) labels. For interior
    cells, bsbs are tuples of two numbers, while for exterior cells, bsb labels
    are tuples of grid tuples."""

    def __init__(self, header, loadFactory, ins=None, do_unpack=False):
        self.cellBlocks = [] #--Each cellBlock is a cell and its related
        # records.
        self.id_cellBlock = {}
        MobBase.__init__(self, header, loadFactory, ins, do_unpack)

    def indexRecords(self):
        """Indexes records by fid."""
        self.id_cellBlock = dict((x.cell.fid,x) for x in self.cellBlocks)

    def setCell(self,cell):
        """Adds record to record list and indexed."""
        if self.cellBlocks and not self.id_cellBlock:
            self.indexRecords()
        fid = cell.fid
        if fid in self.id_cellBlock:
            self.id_cellBlock[fid].cell = cell
        else:
            cellBlock = MobCell(GrupHeader(0, 0, 6, self.stamp), ##: Note label is 0 here - specialized GrupHeader subclass?
                                self.loadFactory, cell)
            cellBlock.setChanged()
            self.cellBlocks.append(cellBlock)
            self.id_cellBlock[fid] = cellBlock

    def remove_cell(self, cell):
        """Removes the specified cell from this block. The exact cell object
        must be present, otherwise a ValueError is raised."""
        if self.cellBlocks and not self.id_cellBlock:
            self.indexRecords()
        self.cellBlocks.remove(cell)
        del self.id_cellBlock[cell.fid]

    def getUsedBlocks(self):
        """Returns a set of blocks that exist in this group."""
        return set(x.getBsb()[0] for x in self.cellBlocks)

    def getUsedSubblocks(self):
        """Returns a set of block/sub-blocks that exist in this group."""
        return set(x.getBsb() for x in self.cellBlocks)

    def getBsbSizes(self):
        """Returns the total size of the block, but also returns a
        dictionary containing the sizes of the individual block,subblocks."""
        bsbCellBlocks = [(x.getBsb(),x) for x in self.cellBlocks]
        bsbCellBlocks.sort(key = lambda y: y[1].cell.fid)
        bsbCellBlocks.sort(key = itemgetter(0))
        bsb_size = {}
        hsize = RecordHeader.rec_header_size
        totalSize = hsize
        bsb_setDefault = bsb_size.setdefault
        for bsb,cellBlock in bsbCellBlocks:
            cellBlockSize = cellBlock.getSize()
            totalSize += cellBlockSize
            bsb0 = (bsb[0],None) #--Block group
            bsb_setDefault(bsb0,hsize)
            if bsb_setDefault(bsb, hsize) == hsize:
                bsb_size[bsb0] += hsize
            bsb_size[bsb] += cellBlockSize
            bsb_size[bsb0] += cellBlockSize
        totalSize += hsize * len(bsb_size)
        return totalSize,bsb_size,bsbCellBlocks

    def dumpBlocks(self,out,bsbCellBlocks,bsb_size,blockGroupType,
                   subBlockGroupType):
        """Dumps the cell blocks and their block and sub-block groups to
        out."""
        curBlock = None
        curSubblock = None
        stamp = self.stamp
        outWrite = out.write
        for bsb,cellBlock in bsbCellBlocks:
            (block,subblock) = bsb
            bsb0 = (block,None)
            if block != curBlock:
                curBlock,curSubblock = bsb0
                outWrite(GrupHeader(bsb_size[bsb0], block, blockGroupType, ##: Here come the tuples - specialized GrupHeader subclass?
                                    stamp).pack_head())
            if subblock != curSubblock:
                curSubblock = subblock
                outWrite(GrupHeader(bsb_size[bsb], subblock, subBlockGroupType, ##: Here come the tuples - specialized GrupHeader subclass?
                                    stamp).pack_head())
            cellBlock.dump(out)

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self and all children."""
        count = sum(x.getNumRecords(includeGroups) for x in self.cellBlocks)
        if count and includeGroups:
            count += 1 + len(self.getUsedBlocks()) + len(
                self.getUsedSubblocks())
        return count

    #--Fid manipulation, record filtering ----------------------------------
    def get_all_signatures(self):
        return set(chain.from_iterable(c.get_all_signatures()
                                       for c in self.cellBlocks))

    def iter_records(self):
        return chain.from_iterable(c.iter_records() for c in self.cellBlocks)

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        #--Note: this call will add the cell to p_keep_ids if any of its
        # related records are kept.
        for cellBlock in self.cellBlocks: cellBlock.keepRecords(p_keep_ids)
        self.cellBlocks = [x for x in self.cellBlocks if x.cell.fid in p_keep_ids]
        self.id_cellBlock.clear()
        self.setChanged()

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        from ..mod_files import MasterSet # YUCK
        if self.cellBlocks and not self.id_cellBlock:
            self.indexRecords()
        lookup_cell_block = self.id_cellBlock.get
        filtered_cell_blocks = []
        filtered_append = filtered_cell_blocks.append
        loadSetIsSuperset = loadSet.issuperset
        for src_cell_block in block.cellBlocks:
            was_newly_added = False
            src_fid = src_cell_block.cell.fid
            # Check if we already have a cell with that FormID
            dest_cell_block = lookup_cell_block(src_fid)
            if not dest_cell_block:
                # We do not, add it and then look up again
                ##: Shouldn't all the setCell calls use getTypeCopy?
                self.setCell(src_cell_block.cell)
                dest_cell_block = lookup_cell_block(src_fid)
                was_newly_added = True
            # Delegate merging to the (potentially newly added) child cell
            dest_cell_block.merge_records(src_cell_block, loadSet,
                mergeIds, iiSkipMerge, doFilter)
            # In IIM, skip all merging - note that we need to remove the child
            # cell again if it was newly added in IIM mode.
            if iiSkipMerge:
                if was_newly_added:
                    self.remove_cell(dest_cell_block.cell)
                continue
            # If we're Filter-tagged, check if the child cell got filtered out
            if doFilter:
                masters = MasterSet()
                src_cell_block.updateMasters(masters)
                if not loadSetIsSuperset(masters):
                    # The child cell got filtered out. If it was newly added,
                    # we need to remove it from this block again. Otherwise, we
                    # can just skip forward to the next child cell.
                    if was_newly_added:
                        self.remove_cell(dest_cell_block.cell)
                    continue
            # We're either not Filter-tagged or we want to keep this cell
            filtered_append(src_cell_block)
        # Apply any merge filtering we've done above to the record block
        block.cellBlocks = filtered_cell_blocks
        block.indexRecords()

    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        for cellBlock in self.cellBlocks:
            cellBlock.convertFids(mapper,toLong)

    def updateRecords(self,srcBlock,mapper,mergeIds):
        """Updates any records in 'self' that exist in 'srcBlock'."""
        if self.cellBlocks and not self.id_cellBlock:
            self.indexRecords()
        id_cellBlock = self.id_cellBlock
        id_Get = id_cellBlock.get
        for srcCellBlock in srcBlock.cellBlocks:
            fid = mapper(srcCellBlock.cell.fid)
            cellBlock = id_Get(fid)
            if cellBlock:
                cellBlock.updateRecords(srcCellBlock,mapper,mergeIds)

    def updateMasters(self,masters):
        """Updates set of master names according to masters actually used."""
        for cellBlock in self.cellBlocks:
            cellBlock.updateMasters(masters)

#------------------------------------------------------------------------------
class MobICells(MobCells):
    """Tes4 top block for interior cell records."""

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        expType = self.label
        recCellClass = self.loadFactory.getRecClass(expType)
        errLabel = expType + u' Top Block'
        cellBlocks = self.cellBlocks
        cell = None
        endBlockPos = endSubblockPos = 0
        unpackCellBlocks = self.loadFactory.getUnpackCellBlocks('CELL')
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        cellBlocksAppend = cellBlocks.append
        selfLoadFactory = self.loadFactory
        insTell = ins.tell
        insSeek = ins.seek
        while not insAtEnd(endPos,errLabel):
            header = insRecHeader()
            recType = header.recType
            if recType == expType:
                if cell:
                    cellBlock = MobCell(header,selfLoadFactory,cell)
                    cellBlocksAppend(cellBlock)
                cell = recCellClass(header,ins,True)
                if insTell() > endBlockPos or insTell() > endSubblockPos:
                    raise ModError(self.inName,
                                   u'Interior cell <%X> %s outside of block '
                                   u'or subblock.' % (
                                       cell.fid,cell.eid))
            elif recType == 'GRUP':
                size,groupFid,groupType = header.size,header.label, \
                                          header.groupType
                delta = size - RecordHeader.rec_header_size
                if groupType == 2: # Block number
                    endBlockPos = insTell() + delta
                elif groupType == 3: # Sub-block number
                    endSubblockPos = insTell() + delta
                elif groupType == 6: # Cell Children
                    if cell:
                        if groupFid != cell.fid:
                            raise ModError(self.inName,
                                           u'Cell subgroup (%X) does not '
                                           u'match CELL <%X> %s.' %
                                           (groupFid,cell.fid,cell.eid))
                        if unpackCellBlocks:
                            cellBlock = MobCell(header,selfLoadFactory,cell,
                                                ins,True)
                        else:
                            cellBlock = MobCell(header,selfLoadFactory,cell)
                            insSeek(delta,1)
                        cellBlocksAppend(cellBlock)
                        cell = None
                    else:
                        raise ModError(self.inName,
                                       u'Extra subgroup %d in CELL group.' %
                                       groupType)
                else:
                    raise ModError(self.inName,
                                   u'Unexpected subgroup %d in CELL group.'
                                   % groupType)
            else:
                raise ModError(self.inName,
                               u'Unexpected %s record in %s group.' % (
                                   recType,expType))
        self.setChanged()

    def dump(self,out):
        """Dumps group header and then records."""
        if not self.changed:
            out.write(self.header.pack_head())
            out.write(self.data)
        elif self.cellBlocks:
            (totalSize, bsb_size, blocks) = self.getBsbSizes()
            self.header.size = totalSize
            out.write(self.header.pack_head())
            self.dumpBlocks(out,blocks,bsb_size,2,3)

#------------------------------------------------------------------------------
class MobWorld(MobCells):
    def __init__(self, header, loadFactory, world, ins=None, do_unpack=False):
        self.world = world
        self.worldCellBlock = None
        self.road = None
        MobCells.__init__(self, header, loadFactory, ins, do_unpack)

    def load_rec_group(self, ins, endPos, __packer=struct.Struct(u'I').pack,
                       __unpacker=struct.Struct(u'2h').unpack):
        """Loads data from input stream. Called by load()."""
        cellType_class = self.loadFactory.getCellTypeClass()
        errLabel = u'World Block'
        cell = None
        block = None
        # subblock = None # unused var
        endBlockPos = endSubblockPos = 0
        cellBlocks = self.cellBlocks
        unpackCellBlocks = self.loadFactory.getUnpackCellBlocks('WRLD')
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        cellGet = cellType_class.get
        insSeek = ins.seek
        insTell = ins.tell
        selfLoadFactory = self.loadFactory
        cellBlocksAppend = cellBlocks.append
        from .. import bush
        isFallout = bush.game.fsName != u'Oblivion'
        cells = {}
        while not insAtEnd(endPos,errLabel):
            curPos = insTell()
            if curPos >= endBlockPos:
                block = None
            if curPos >= endSubblockPos:
                pass # subblock = None # unused var
            #--Get record info and handle it
            header = insRecHeader()
            recType,size = header.recType,header.size
            delta = size - RecordHeader.rec_header_size
            recClass = cellGet(recType)
            if recType == 'ROAD':
                if not recClass: insSeek(size,1)
                else: self.road = recClass(header,ins,True)
            elif recType == 'CELL':
                if cell:
                    cellBlock = MobCell(header,selfLoadFactory,cell)
                    if block:
                        cellBlocksAppend(cellBlock)
                    else:
                        if self.worldCellBlock:
                            raise ModError(self.inName,
                                           u'Extra exterior cell <%s> %s '
                                           u'before block group.' % (
                                               hex(cell.fid),cell.eid))
                        self.worldCellBlock = cellBlock
                cell = recClass(header,ins,True)
                if isFallout: cells[cell.fid] = cell
                if block:
                    if cell:
                        cellBlock = MobCell(header, selfLoadFactory, cell)
                        if block:
                            cellBlocksAppend(cellBlock)
                        else:
                            if self.worldCellBlock:
                                raise ModError(self.inName,
                                               u'Extra exterior cell <%s> %s '
                                               u'before block group.' % (
                                                   hex(cell.fid), cell.eid))
                            self.worldCellBlock = cellBlock
                    elif insTell() > endBlockPos or insTell() > endSubblockPos:
                        raise ModError(self.inName,
                                       u'Exterior cell <%s> %s after block or'
                                       u' subblock.' % (
                                           hex(cell.fid),cell.eid))
            elif recType == 'GRUP':
                groupFid,groupType = header.label,header.groupType
                if groupType == 4: # Exterior Cell Block
                    block = __unpacker(__packer(groupFid))
                    block = (block[1],block[0])
                    endBlockPos = insTell() + delta
                elif groupType == 5: # Exterior Cell Sub-Block
                    # we don't actually care what the sub-block is, since
                    # we never use that information here. So below was unused:
                    # subblock = structUnpack('2h',structPack('I',groupFid))
                    # subblock = (subblock[1],subblock[0]) # unused var
                    endSubblockPos = insTell() + delta
                elif groupType == 6: # Cell Children
                    if isFallout: cell = cells.get(groupFid,None)
                    if cell:
                        if groupFid != cell.fid:
                            raise ModError(self.inName,
                                           u'Cell subgroup (%s) does not '
                                           u'match CELL <%s> %s.' %
                                           (hex(groupFid),hex(cell.fid),
                                            cell.eid))
                        if unpackCellBlocks:
                            cellBlock = MobCell(header,selfLoadFactory,cell,
                                                ins,True)
                        else:
                            cellBlock = MobCell(header,selfLoadFactory,cell)
                            insSeek(delta,1)
                        if block:
                            cellBlocksAppend(cellBlock)
                        else:
                            if self.worldCellBlock:
                                raise ModError(self.inName,
                                               u'Extra exterior cell <%s> %s '
                                               u'before block group.' % (
                                                   hex(cell.fid),cell.eid))
                            self.worldCellBlock = cellBlock
                        cell = None
                    else:
                        raise ModError(self.inName,
                                       u'Extra cell children subgroup in '
                                       u'world children group.')
                else:
                    raise ModError(self.inName,
                                   u'Unexpected subgroup %d in world '
                                   u'children group.' % groupType)
            else:
                raise ModError(self.inName,
                               u'Unexpected %s record in world children '
                               u'group.' % recType)
        self.setChanged()

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self and all children."""
        if not self.changed:
            return MobBase.getNumRecords(self)
        count = 1 # self.world, always present
        count += bool(self.road)
        if self.worldCellBlock:
            count += self.worldCellBlock.getNumRecords(includeGroups)
        count += MobCells.getNumRecords(self,includeGroups)
        return count

    def dump(self,out):
        """Dumps group header and then records.  Returns the total size of
        the world block."""
        hsize = RecordHeader.rec_header_size
        worldSize = self.world.getSize() + hsize
        self.world.dump(out)
        if not self.changed:
            out.write(self.header.pack_head())
            out.write(self.data)
            return self.size + worldSize
        elif self.cellBlocks or self.road or self.worldCellBlock:
            (totalSize, bsb_size, blocks) = self.getBsbSizes()
            if self.road:
                totalSize += self.road.getSize() + hsize
            if self.worldCellBlock:
                totalSize += self.worldCellBlock.getSize()
            self.header.size = totalSize
            self.header.label = self.world.fid
            self.header.groupType = 1
            out.write(self.header.pack_head())
            if self.road:
                self.road.dump(out)
            if self.worldCellBlock:
                self.worldCellBlock.dump(out)
            self.dumpBlocks(out,blocks,bsb_size,4,5)
            return totalSize + worldSize
        else:
            return worldSize

    #--Fid manipulation, record filtering ----------------------------------
    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        self.world.convertFids(mapper,toLong)
        if self.road:
            self.road.convertFids(mapper,toLong)
        if self.worldCellBlock:
            self.worldCellBlock.convertFids(mapper,toLong)
        MobCells.convertFids(self,mapper,toLong)

    def updateMasters(self,masters):
        """Updates set of master names according to masters actually used."""
        self.world.updateMasters(masters)
        if self.road:
            self.road.updateMasters(masters)
        if self.worldCellBlock:
            self.worldCellBlock.updateMasters(masters)
        MobCells.updateMasters(self,masters)

    def updateRecords(self,srcBlock,mapper,mergeIds):
        """Updates any records in 'self' that exist in 'srcBlock'."""
        for attr in ('world','road'):
            myRecord = getattr(self, attr)
            record = getattr(srcBlock, attr)
            if myRecord and record:
                if myRecord.fid != mapper(record.fid):
                    raise ArgumentError(u"Fids don't match! %08x, %08x" % (
                        myRecord.fid,record.fid))
                if not record.flags1.ignored:
                    record = record.getTypeCopy(mapper)
                    setattr(self, attr, record)
                    mergeIds.discard(record.fid)
        if self.worldCellBlock and srcBlock.worldCellBlock:
            self.worldCellBlock.updateRecords(srcBlock.worldCellBlock,mapper,
                                              mergeIds)
        MobCells.updateRecords(self,srcBlock,mapper,mergeIds)

    def get_all_signatures(self):
        all_sigs = super(MobWorld, self).get_all_signatures()
        all_sigs.add(self.world.recType)
        if self.road: all_sigs.add(self.road.recType)
        if self.worldCellBlock:
            all_sigs |= self.worldCellBlock.get_all_signatures()
        return all_sigs

    def iter_records(self):
        single_recs = [x for x in (self.world, self.road) if x]
        c_recs = (self.worldCellBlock.iter_records() if self.worldCellBlock
                  else [])
        return chain(single_recs, c_recs, super(MobWorld, self).iter_records())

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        if self.road and self.road.fid not in p_keep_ids:
            self.road = None
        if self.worldCellBlock:
            self.worldCellBlock.keepRecords(p_keep_ids)
            if self.worldCellBlock.cell.fid not in p_keep_ids:
                self.worldCellBlock = None
        MobCells.keepRecords(self, p_keep_ids)
        if self.road or self.worldCellBlock or self.cellBlocks:
            p_keep_ids.add(self.world.fid)

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        from ..mod_files import MasterSet # YUCK
        mergeIdsAdd = mergeIds.add
        loadSetIsSuperset = loadSet.issuperset
        for single_attr in (u'world', u'road'):
            src_rec = getattr(block, single_attr)
            if src_rec and not src_rec.flags1.ignored:
                # If we're Filter-tagged, perform merge filtering first
                if doFilter:
                    src_rec.mergeFilter(loadSet)
                    masters = MasterSet()
                    src_rec.updateMasters(masters)
                    if not loadSetIsSuperset(masters):
                        # Filtered out, discard this record and skip to next
                        setattr(block, single_attr, None)
                        continue
                # In IIM, skip all merging (duh)
                if iiSkipMerge: continue
                dest_rec = getattr(self, single_attr)
                if dest_rec and dest_rec.fid != src_rec.fid:
                    raise ArgumentError(u"Fids don't match! %08x, %08x" % (
                        dest_rec.fid, src_rec.fid))
                # We're past all hurdles - stick a copy of this record into
                # ourselves and mark it as merged
                mergeIdsAdd(src_rec.fid)
                setattr(self, single_attr, src_rec.getTypeCopy())
        if block.worldCellBlock:
            was_newly_added = False
            # If we don't have a world cell block yet, make a new one to merge
            # the source's world cell block into
            if not self.worldCellBlock:
                self.worldCellBlock = MobCell(GrupHeader(0, 0, 6, self.stamp),
                    self.loadFactory, None) # cell will be set in merge_records
                was_newly_added = True
            # Delegate merging to the (potentially newly added) block
            self.worldCellBlock.merge_records(block.worldCellBlock, loadSet,
                mergeIds, iiSkipMerge, doFilter)
            # In IIM, skip all merging - note that we need to remove the world
            # cell block again if it was newly added in IIM mode.
            if iiSkipMerge:
                if was_newly_added:
                    self.worldCellBlock = None
            elif doFilter:
                # If we're Filter-tagged, check if the world cell block got
                # filtered out
                masters = MasterSet()
                self.worldCellBlock.updateMasters(masters)
                if not loadSetIsSuperset(masters):
                    # The cell block got filtered out. If it was newly added,
                    # we need to remove it from this block again.
                    if was_newly_added:
                        self.worldCellBlock = None
        super(MobWorld, self).merge_records(block, loadSet, mergeIds,
            iiSkipMerge, doFilter)

#------------------------------------------------------------------------------
class MobWorlds(MobBase):
    """Tes4 top block for world records and related roads and cells. Consists
    of world blocks."""

    def __init__(self, header, loadFactory, ins=None, do_unpack=False):
        self.worldBlocks = []
        self.id_worldBlocks = {}
        self.orphansSkipped = 0
        MobBase.__init__(self, header, loadFactory, ins, do_unpack)

    def load_rec_group(self, ins, endPos):
        """Loads data from input stream. Called by load()."""
        expType = self.label
        recWrldClass = self.loadFactory.getRecClass(expType)
        errLabel = expType + u' Top Block'
        worldBlocks = self.worldBlocks
        world = None
        insAtEnd = ins.atEnd
        insRecHeader = ins.unpackRecHeader
        insSeek = ins.seek
        selfLoadFactory = self.loadFactory
        worldBlocksAppend = worldBlocks.append
        from .. import bush
        isFallout = bush.game.fsName != u'Oblivion'
        worlds = {}
        header = None
        while not insAtEnd(endPos,errLabel):
            #--Get record info and handle it
            prev_header = header
            header = insRecHeader()
            recType = header.recType
            if recType == expType:
                # FIXME(inf) The getattr here has to go
                if (prev_header and
                        getattr(prev_header, u'recType', None) == b'WRLD'):
                    # We hit a WRLD directly after another WRLD, so there are
                    # no children to read - just finish this WRLD
                    worldBlocksAppend(MobWorld(prev_header, selfLoadFactory,
                        world))
                world = recWrldClass(header,ins,True)
                if isFallout: worlds[world.fid] = world
            elif recType == 'GRUP':
                groupFid,groupType = header.label,header.groupType
                if groupType != 1:
                    raise ModError(ins.inName,
                                   u'Unexpected subgroup %d in CELL group.'
                                   % groupType)
                if isFallout: world = worlds.get(groupFid,None)
                if not world:
                    #raise ModError(ins.inName,'Extra subgroup %d in WRLD
                    # group.' % groupType)
                    #--Orphaned world records. Skip over.
                    insSeek(header.size - RecordHeader.rec_header_size,1)
                    self.orphansSkipped += 1
                    continue
                if groupFid != world.fid:
                    raise ModError(ins.inName,
                                   u'WRLD subgroup (%s) does not match WRLD '
                                   u'<%s> %s.' % (
                                   hex(groupFid),hex(world.fid),world.eid))
                worldBlock = MobWorld(header,selfLoadFactory,world,ins,True)
                worldBlocksAppend(worldBlock)
                world = None
            else:
                raise ModError(ins.inName,
                               u'Unexpected %s record in %s group.' % (
                                   recType,expType))
        if world:
            # We have a last WRLD without children lying around, finish it
            worldBlocksAppend(MobWorld(header, selfLoadFactory, world))

    def getSize(self):
        """Returns size (including size of any group headers)."""
        return RecordHeader.rec_header_size + sum(
            x.getSize() for x in self.worldBlocks)

    def dump(self,out):
        """Dumps group header and then records."""
        if not self.changed:
            out.write(self.header.pack_head())
            out.write(self.data)
        else:
            if not self.worldBlocks: return
            worldHeaderPos = out.tell()
            header = TopGrupHeader(0, self.label, 0, self.stamp)
            out.write(header.pack_head())
            totalSize = RecordHeader.rec_header_size + sum(
                x.dump(out) for x in self.worldBlocks)
            out.seek(worldHeaderPos + 4)
            out.pack(u'I', totalSize)
            out.seek(worldHeaderPos + totalSize)

    def getNumRecords(self,includeGroups=True):
        """Returns number of records, including self and all children."""
        count = sum(x.getNumRecords(includeGroups) for x in self.worldBlocks)
        return count + includeGroups * bool(count)

    def convertFids(self,mapper,toLong):
        """Converts fids between formats according to mapper.
        toLong should be True if converting to long format or False if
        converting to short format."""
        for worldBlock in self.worldBlocks:
            worldBlock.convertFids(mapper,toLong)

    def indexRecords(self):
        """Indexes records by fid."""
        self.id_worldBlocks = dict((x.world.fid,x) for x in self.worldBlocks)

    def updateMasters(self,masters):
        """Updates set of master names according to masters actually used."""
        for worldBlock in self.worldBlocks:
            worldBlock.updateMasters(masters)

    def updateRecords(self,srcBlock,mapper,mergeIds):
        """Updates any records in 'self' that exist in 'srcBlock'."""
        if self.worldBlocks and not self.id_worldBlocks:
            self.indexRecords()
        id_worldBlocks = self.id_worldBlocks
        idGet = id_worldBlocks.get
        for srcWorldBlock in srcBlock.worldBlocks:
            worldBlock = idGet(mapper(srcWorldBlock.world.fid))
            if worldBlock:
                worldBlock.updateRecords(srcWorldBlock,mapper,mergeIds)

    def setWorld(self, world, worldcellblock=None):
        """Adds record to record list and indexed."""
        if self.worldBlocks and not self.id_worldBlocks:
            self.indexRecords()
        fid = world.fid
        if fid in self.id_worldBlocks:
            self.id_worldBlocks[fid].world = world
            self.id_worldBlocks[fid].worldCellBlock = worldcellblock
        else:
            worldBlock = MobWorld(GrupHeader(0, 0, 1, self.stamp), ##: groupType = 1
                                  self.loadFactory, world)
            worldBlock.setChanged()
            self.worldBlocks.append(worldBlock)
            self.id_worldBlocks[fid] = worldBlock

    def remove_world(self, world):
        """Removes the specified world from this block. The exact world object
        must be present, otherwise a ValueError is raised."""
        if self.worldBlocks and not self.id_worldBlocks:
            self.indexRecords()
        self.worldBlocks.remove(world)
        del self.id_worldBlocks[world.fid]

    def get_all_signatures(self):
        return set(chain.from_iterable(w.get_all_signatures()
                                       for w in self.worldBlocks))

    def iter_records(self):
        return chain.from_iterable(w.iter_records() for w in self.worldBlocks)

    def keepRecords(self, p_keep_ids):
        """Keeps records with fid in set p_keep_ids. Discards the rest."""
        for worldBlock in self.worldBlocks: worldBlock.keepRecords(p_keep_ids)
        self.worldBlocks = [x for x in self.worldBlocks if
                            x.world.fid in p_keep_ids]
        self.id_worldBlocks.clear()
        self.setChanged()

    def merge_records(self, block, loadSet, mergeIds, iiSkipMerge, doFilter):
        from ..mod_files import MasterSet # YUCK
        if self.worldBlocks and not self.id_worldBlocks:
            self.indexRecords()
        lookup_world_block = self.id_worldBlocks.get
        filtered_world_blocks = []
        filtered_append = filtered_world_blocks.append
        loadSetIsSuperset = loadSet.issuperset
        for src_world_block in block.worldBlocks:
            was_newly_added = False
            src_fid = src_world_block.world.fid
            # Check if we already have a world with that FormID
            dest_world_block = lookup_world_block(src_fid)
            if not dest_world_block:
                # We do not, add it and then look up again
                ##: Shouldn't all the setWorld calls use getTypeCopy?
                self.setWorld(src_world_block.world)
                dest_world_block = lookup_world_block(src_fid)
                was_newly_added = True
            # Delegate merging to the (potentially newly added) child world
            dest_world_block.merge_records(src_world_block, loadSet,
                mergeIds, iiSkipMerge, doFilter)
            # In IIM, skip all merging - note that we need to remove the child
            # world again if it was newly added in IIM mode.
            if iiSkipMerge:
                if was_newly_added:
                    self.remove_world(dest_world_block.world)
                continue
            # If we're Filter-tagged, check if the child world got filtered out
            if doFilter:
                masters = MasterSet()
                src_world_block.updateMasters(masters)
                if not loadSetIsSuperset(masters):
                    # The child world got filtered out. If it was newly added,
                    # we need to remove it from this block again. Otherwise, we
                    # can just skip forward to the next child world.
                    if was_newly_added:
                        self.remove_world(dest_world_block.world)
                    continue
            # We're either not Filter-tagged or we want to keep this world
            filtered_append(src_world_block)
        # Apply any merge filtering we've done above to the record block
        block.worldBlocks = filtered_world_blocks
        block.indexRecords()