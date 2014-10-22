#!/usr/bin/env python
# -*- coding: utf-8 -*-

def configure(self):

    self.debug=False # turn on for network messaging debugging
    self.activatesounds=True # turn on to play sounds
    self.sumptuous_browser=True # turn on to use browser tabs for DQM display

    self.pubsocket_bind_address='tcp://*:5566' # address of GUI PUB socket

    self.nodes=[ # addresses of connected nodes
        ('RC','tcp://pcethtb2.cern.ch:6002'),
        ('RO1','tcp://pcethtb1.cern.ch:6002'),
        ('RO2','tcp://cms-h4-03:6002'),
        ('EVTB','tcp://pcethtb2.cern.ch:6502'),
        ('table','tcp://cms-h4-01:6999')
        ]

    self.keepalive={} # nodes to monitor (comment to remove, never put False)
    self.keepalive['RC']=True
    self.keepalive['RO1']=True
    self.keepalive['RO2']=True
    self.keepalive['EVTB']=True
    self.keepalive['table']=True

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
        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1,cms-h4-03',
        'kill_daemons': '../H4DAQ/scripts/killall.sh'
        }

    self.tableposdictionary={
        'HOME': (200.0,250.0)
        }

#    otherxtals={
#        'CRY_1': (,),
#        'CRY_2': (,),
#        'CRY_3': (,),
#        'CRY_4': (,),
#        'CRY_5': (,),
#        'CRY_6': (,),
#        'CRY_7': (,),
#        'CRY_8': (,),
#        'CRY_9': (,),
#        'CRY_10': (,),
#        'CRY_11': (,),
#        'CRY_12': (,),
#        'CRY_13': (,),
#        'CRY_14': (,),
#        'CRY_15': (,),
#        'CRY_16': (,),
#        'CRY_17': (,),
#        'CRY_18': (,),
#        'CRY_19': (,),
#        'CRY_20': (,),
#        'CRY_21': (,),
#        'CRY_22': (,),
#        'CRY_23': (,),
#        'CRY_24': (,)
#        }
#
#    for i,j in otherxtals.iteritems():
#        self.tableposdictionary[i]=(self.tableposdictionary['HOME']+j[0],self.tableposdictionary['HOME']+j[1])
