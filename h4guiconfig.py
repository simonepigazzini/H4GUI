#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import OrderedDict

def configure(self):

    self.debug=False # turn on for network messaging debugging
    self.activatesounds=True # turn on to play sounds
    self.sumptuous_browser=True # turn on to use browser tabs for DQM display

    self.pubsocket_bind_address='tcp://*:5566' # address of GUI PUB socket

    self.nodes=[ # addresses of connected nodes
        ('RC','tcp://pcethtb2.cern.ch:6002'),
        #        ('RO1','tcp://pcethtb1.cern.ch:6002'),
        #        ('RO2','tcp://cms-h4-03:6002'),
        ('EVTB','tcp://pcethtb2.cern.ch:6502'),
        #        ('table','tcp://cms-h4-01:6999')
        ]

    self.keepalive={} # nodes to monitor (comment to remove, never put False)
    self.keepalive['RC']=True
#    self.keepalive['RO1']=False
#    self.keepalive['RO2']=False
    self.keepalive['EVTB']=True
#    self.keepalive['table']=False

    self.temperatureplot=None # 'http://blabla/tempplot.png' to be displayed for temperature history

# DQM plots, to be filled if not using tabbed browsing support
#        self.dqmplots=[] # [('tabname','http://plotname','http://largeplotname.png'),...]
#        self.dqmplots=[
#            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv11.png','/home/cmsdaq/DAQ/H4GUI/plots/canv21.png')
#            ]


    self.scripts={ # scripts linked to GUI buttons
        'sync_clocks': '../H4DAQ/scripts/syncclocks.sh',
        'free_space': None,
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1',
        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --drcv=cms-h4-04 --drcvrecompile',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1,cms-h4-03',
        'kill_daemons': '../H4DAQ/scripts/killall.sh'
        }

    self.tableposdictionary = OrderedDict()
    self.tableposdictionary['ZERO']=(0.0,0.0)
#    self.tableposdictionary['CEF3_CENTER']=(194.0,254.0)

    otherxtals = OrderedDict() # coordinates seen from the rear face
#    otherxtals['BGO_CRY_1']= (-20.0,25.1)
#    otherxtals['BGO_CRY_2']= (2.0,25.0)
#    otherxtals['BGO_CRY_3']= (25.0,22.0)
#    otherxtals['BGO_CRY_4']= (-25.0,2.0)
#    otherxtals['BGO_CRY_5']= (25.0,-2.0)
#    otherxtals['BGO_CRY_6']= (-24.0,-20.0)
#    otherxtals['BGO_CRY_7']= (-2.0,-25.0)
#    otherxtals['BGO_CRY_8']= (21.0,-25.0)
#    otherxtals['BGO_CRY_9']= (-47.0,51.0)
#    otherxtals['BGO_CRY_10']= (-22.0,49.0)
#    otherxtals['BGO_CRY_11']= (2.0,48.0)
#    otherxtals['BGO_CRY_12']= (27.0,45.0)
#    otherxtals['BGO_CRY_13']= (51.0,47.0)
#    otherxtals['BGO_CRY_14']= (-46.0,28.0)
#    otherxtals['BGO_CRY_15']= (50.0,22.0)
#    otherxtals['BGO_CRY_16']= (-50.0,3.0)
#    otherxtals['BGO_CRY_17']= (50.0,0.0)
#    otherxtals['BGO_CRY_18']= (-49.0,-22.0)
#    otherxtals['BGO_CRY_19']= (46.0,-24.0)
#    otherxtals['BGO_CRY_20']= (-49.0,-46.0)
#    otherxtals['BGO_CRY_21']= (-25.0,-45.0)
#    otherxtals['BGO_CRY_22']= (0.0,-49.0)
#    otherxtals['BGO_CRY_23']= (24.0,-49.0)
#    otherxtals['BGO_CRY_24']= (49.0,-49.0)
#
#    otherxtals['CEF3_UP2']= (0.0,10.0)
#    otherxtals['CEF3_UP1']= (0.0,5.0)
#    otherxtals['CEF3_DOWN1']= (0.0,-5.0)
#    otherxtals['CEF3_DOWN2']= (0.0,-10.0)
#
#    otherxtals['CEF3_LEFT2']= (-10.0,0.0)
#    otherxtals['CEF3_LEFT1']= (-5.0,0.0)
#    otherxtals['CEF3_RIGHT1']= (5.0,0.0)
#    otherxtals['CEF3_RIGHT2']= (10.0,0.0)
#
#    otherxtals['CEF3_DIAG_SW3']= (-9.0,-9.0)
#    otherxtals['CEF3_DIAG_SW2']= (-6.0,-6.0)
#    otherxtals['CEF3_DIAG_SW1']= (-3.0,-3.0)
#    otherxtals['CEF3_DIAG_NE1']= (3.0,3.0)
#    otherxtals['CEF3_DIAG_NE2']= (6.0,6.0)
#    otherxtals['CEF3_DIAG_NE3']= (9.0,9.0)
#
#    otherxtals['CEF3_DIAG_NW3']= (-9.0,9.0)
#    otherxtals['CEF3_DIAG_NW2']= (-6.0,6.0)
#    otherxtals['CEF3_DIAG_NW1']= (-3.0,3.0)
#    otherxtals['CEF3_DIAG_SE1']= (3.0,-3.0)
#    otherxtals['CEF3_DIAG_SE2']= (6.0,-6.0)
#    otherxtals['CEF3_DIAG_SE3']= (9.0,-9.0)

#    for i,j in otherxtals.iteritems():
#        self.tableposdictionary[i]=(self.tableposdictionary['CEF3_CENTER'][0]+j[0],self.tableposdictionary['CEF3_CENTER'][1]-j[1])
