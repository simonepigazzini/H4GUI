#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import OrderedDict

def configure(self):

    self.debug=False # turn on for network messaging debugging
    self.activatesounds=True # turn on to play sounds
    self.sumptuous_browser=True # turn on to use browser tabs for DQM display

    self.pubsocket_bind_address='tcp://*:5566' # address of GUI PUB socket

    self.nodes=[ # addresses of connected nodes
        ('RC','tcp://localhost:6002'),
        #('RO1','tcp://pcethtb1.cern.ch:6002'),
        #        ('RO2','tcp://cms-h4-03:6002'),
        ('EVTB','tcp://localhost:6502'),
#        ('DRCV1','tcp://cms-h4-04.cern.ch:6502'),
#        ('DRCV2','tcp://pcethtb2.cern.ch:6502'),
#        ('table','tcp://cms-h4-01:6999')
        ]

    self.keepalive={} # nodes to monitor (comment to remove, never put False)
    self.keepalive['RC']=True
#    self.keepalive['RO1']=True
#    self.keepalive['RO2']=False
    self.keepalive['EVTB']=True
#    self.keepalive['DRCV1']=True
#    self.keepalive['DRCV2']=True
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
        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=localhost --eb=localhost --vmecontroller=0 --norecompile --daqhome=/home/MiB-CMS-ECAL',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb1 --dr=pcethtb1 --drcv=cms-h4-05 --drcvrecompile',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --dr=pcethtb1 --drcv=cms-h4-04,cms-h4-05 --drcvrecompile',
#        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1,cms-h4-03',
        'kill_daemons': '../H4DAQ/scripts/killall.sh'
        }
    
    self.tableposdictionary = OrderedDict()
    
    
    
