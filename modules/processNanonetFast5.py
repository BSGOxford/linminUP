#!/usr/bin/python
# -*- coding: utf-8 -*-
# --------------------------------------------------
# File Name: processNanonetFast5.py
# Purpose:
# Creation Date: 2014 - 2015
# Last Modified: Fri, Aug 26, 2016 12:25:47 PM
# Author(s): The DeepSEQ Team, University of Nottingham UK
# Copyright 2015 The Author(s) All Rights Reserved
# Credits:
# --------------------------------------------------

import os
import sys
import time
#import datetime
from Bio import SeqIO
import hashlib
from StringIO import StringIO

#from align_bwa import *
from align_lastal import *
from hdf5HashUtils import *

from sql import upload_model_data
from telem import init_tel_threads2
from checkRead import check_read_type, getBasecalltype

from debug import debug

from hdf2SQL import explore

from processFast5Utils import *

#--------------------------------------------------------------------------------
def process_nanonet_readtypes(args, read_type, basename, basenameid, basecalldirs, tracking_id_hash, general_hash, read_info_hash, passcheck, hdf, db, cursor, fastqhash):
# Process Fasta basecall data ....

    events_hash = {}

    if basename is '': retuurn ()

    basecalldir = "/Analyses/Basecall_RNN_1D_000/"



    if args.verbose == "high": 
        print "basecalldir", basecalldir
        debug()

    #fastqhash = dict()

    # tel_sql_list=list()

    tel_data_hash = dict()

    readtypes = { 'basecalled_template': basecalldir + 'BaseCalled_template/' }

    tel_data_hash = dict()
    template_start = 0
    template_end = 0
    g_template_start = 0
    g_template_end = 0

    for (readtype, location) in readtypes.iteritems():
        if args.verbose == "high": print "LOCATION:" , location
        if location in hdf:
            fastq = hdf[location + 'Fastq'][()]
            try:
                rec = SeqIO.read(StringIO(fastq), 'fastq')
            except Exception, err:
                err_string = \
                    '%s:\tError reading fastq oject from base: %s type: %s error: %s' \
                    % (time.strftime('%Y-%m-%d %H:%M:%S'), basename,
                       readtype, err)
                print >> sys.stderr, err_string
                with open(dbcheckhash['logfile'][dbname], 'a') as \
                    logfilehandle:
                    logfilehandle.write(err_string + os.linesep)
                    logfilehandle.close()
                continue

            sequence = str(rec.seq)
            seqlen = len(sequence)
            rec.id = basename + '.' + readtype

            qual = chr_convert_array(db,
                    rec.letter_annotations['phred_quality'])
            fastqhash[rec.id] = \
                {'quals': rec.letter_annotations['phred_quality'],
                 'seq': sequence}


            sampling_rate = float(tracking_id_hash['sampling_rate'] )

            #---------------------------------------------
            # 2D read .....
            if location + 'Alignment' in hdf: # so its 2D

                if args.verbose is True:
                    print "we're looking at a 2D read",template_start,"\n\n"
                    debug()

                duration = float(read_info_hash['duration' ]) / 60.
                g_start_time = g_template_start
                g_end_time = g_template_end
                start_time = template_start
                end_time = template_end

                events_hash = {
                        'basename_id': basenameid,
                        'seqid': rec.id,
                        'sequence': sequence,
                        'qual': qual,
                        'seqlen': seqlen,
                        'start_time': template_start,
                        'exp_start_time': tracking_id_hash['exp_start_time' ],
                        'pass': passcheck,
                        'duration': duration,
                        'sampling_rate': sampling_rate
                        }

                events_hash = calcTimingWindows(events_hash, start_time, end_time
                                                    , g_start_time, g_end_time)

                mysql_load_from_hashes(args, db, cursor,
                                            readtype, events_hash)



                if args.telem is True:
                    alignment = hdf[location + 'Alignment'][()]
                    if args.verbose == "high":
                        print "ALIGNMENT", type(alignment)

                    channel = general_hash['channel'][-1]


                    tel_data_hash[readtype] = [basenameid, channel,
                            alignment]

                    # upload_2dalignment_data(basenameid,channel,alignment,db)
                    # tel_sql_list.append(t_sql)

            #---------------------------------------------

            complement_and_template_fields = []
            '''
                'basename',
                'seqid',
                'duration',
                'start_time',
                'scale',
                'shift',
                'gross_shift',
                'drift',
                'scale_sd',
                'var_sd',
                'var',
                'sequence',
                'qual',
                ]
            '''
            

            #if location + 'Events' in hdf and location + 'Model' in hdf:
            if location + 'Events' in hdf and location + 'Fastq' in hdf:
            # so its either template or complement
                '''
                events_hash = make_hdf5_object_attr_hash(args,
                        hdf[location + 'Events'],
                        complement_and_template_fields)
                if location + 'Model' in hdf:
                    model_hash = make_hdf5_object_attr_hash(args,
                        hdf[location + 'Model'],
                        complement_and_template_fields)
                    events_hash.update(model_hash)
                '''

                # #Logging the start time of a template read to pass to the 2d read in order to speed up mysql processing

                exp_start_time = float(tracking_id_hash['exp_start_time' ])

                duration = float(read_info_hash['duration' ]) / 60.
                start_time = float(read_info_hash['start_time' ]) / sampling_rate

                events_hash.update({
                        'basename_id': basenameid,
                        'seqid': rec.id,
                        'sequence': sequence,
                        'qual': qual,
                        'seqlen': seqlen,
                        'start_time': start_time, 
                        'exp_start_time': float(tracking_id_hash['exp_start_time' ]),
                        'pass': passcheck,
                        'sampling_rate': sampling_rate,
                        'duration': duration
                        })


                events_hash, timings = get_main_timings(events_hash, location, hdf)

                if readtype == 'basecalled_template':
                    _, template_start, template_end, g_template_start, \
                                                g_template_end = timings


                mysql_load_from_hashes(args, db, cursor, readtype,
                        events_hash)

#--------------------------------------------------------------------------------

def getNanonetBasenameData(args, read_type, hdf):
    for element in hdf['/Raw/Reads']:

        read_id_fields = [
            'duration',
            'read_number',
            'start_mux',
            'start_time',
            ]

        read_info_hash = make_hdf5_object_attr_hash(args,
                hdf['/Raw/Reads/' + element],
                read_id_fields)

    configdatastring = ''

    x = read_info_hash['read_number']
    string = '/Raw/Reads/Read_%s' % x
    if args.verbose == "high":
        print string
        debug()
    if string in hdf:
        configdatastring = string
        configdata = hdf[configdatastring]

    if args.verbose == "high":
        print configdata
        debug()

    return '',[string,string,string],configdata, read_info_hash


#--------------------------------------------------------------------------------
def process_nanonet_basecalledSummary_data(basecalldir, args, read_type, basename, basenameid, basecalldirs, passcheck, tracking_id_hash, general_hash, hdf, db,cursor):


    basecall_summary_hash = {}

    basecall_summary_fields = []
    '''
    # # get all the basecall summary split hairpin data
        'abasic_dur',
        'abasic_index',
        'abasic_peak',
        'duration_comp',
        'duration_temp',
        'end_index_comp',
        'end_index_temp',
        'hairpin_abasics',
        'hairpin_dur',
        'hairpin_events',
        'hairpin_peak',
        'median_level_comp',
        'median_level_temp',
        'median_sd_comp',
        'median_sd_temp',
        'num_comp',
        'num_events',
        'num_temp',
        'pt_level',
        'range_comp',
        'range_temp',
        'split_index',
        'start_index_comp',
        'start_index_temp',
        ]

    basecall_summary_hash = make_hdf5_object_attr_hash(args,
                                            hdf[basecalldir],
                                            basecall_summary_fields)
    '''

    if basecalldir + '/BaseCalled_template' in hdf:
        hdf5object = hdf[basecalldir + '/BaseCalled_template']

        # print "Got event location"

        for x in (
            'drift',
            'mean_qscore',
            'num_skips',
            'num_stays',
            'scale',
            'scale_sd',
            'sequence_length', ####
            'shift',
            'strand_score',
            'var',
            'var_sd',
            ):
            if x in hdf5object.attrs.keys():
                value = str(hdf5object.attrs[x])
                basecall_summary_hash.update({x + 'T': value})

    # # load basecall summary hash into mysql

    basecall_summary_hash.update({'basename_id': basenameid})
    basecall_summary_hash.update({'pass': passcheck})
    basecall_summary_hash.update({'exp_start_time': tracking_id_hash['exp_start_time' ]})

    basecall_summary_hash = copy_timings(basecall_summary_hash, general_hash)
    if args.verbose is True:
        print basecall_summary_hash
        print general_hash
        debug()

    mysql_load_from_hashes(args, db, cursor, 'basecall_summary',
                           basecall_summary_hash)


# ---------------------------------------------------------------------------


def process_nanonet_configGeneral_data(args, configdata, basename, basenameid, basecalldirs, read_type, passcheck, hdf, tracking_id_hash, db, cursor):


    if len(configdata) > 0:
        general_fields = [
            'duration',
            'read_id',
            'read_number',
            'start_mux',
            'start_time',
            ]

        general_hash = make_hdf5_object_attr_hash(args, configdata,
                general_fields)

        sampling_hash = make_hdf5_object_attr_hash(args,
                hdf['/UniqueGlobalKey/channel_id']
                , ['sampling_rate'])

        sampling_rate = float(sampling_hash['sampling_rate' ])

        start_time = float(general_hash['start_time'] ) / sampling_rate
        exp_start_time = float(tracking_id_hash['exp_start_time'] )

        general_hash.update(
                    { 'sampling_rate': sampling_rate
                    , 'start_time': start_time
                    , 'basename_id': basenameid
                    , 'basename': basename
                    , 'read_type': getBasecalltype(args, read_type)
                    , 'exp_start_time': exp_start_time
                    })

        # ------------------------------------------
    location = '/Raw/Reads/Read_%s' % general_hash['read_number']

    if location in hdf:
        hdf5object = hdf[location]

        for x in (
            'duration',
            'read_number',
            'start_time',
            ):
            if x in hdf5object.attrs.keys():
                value = str(hdf5object.attrs[x])
                general_hash.update({x: value})


        # Specific to catch read_id as different class:
        general_hash.update({'read_type': \
                            getBasecalltype(args, read_type)} )

        for x in 'read_id':
            if x in hdf5object.attrs.keys():
                value = str(hdf5object.attrs[x])
                general_hash.update({'read_name': value})


        general_hash, _ = get_main_timings(general_hash, location, hdf)
        channel = int(tracking_id_hash['channel_number'])
        general_hash.update({'channel': channel})

    mysql_load_from_hashes(args, db, cursor, 'config_general',
                                                        general_hash)
    return general_hash

