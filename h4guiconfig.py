#!/usr/bin/env python
# -*- coding: utf-8 -*-

def configure(self):

    self.debug=False # turn on for network messaging debugging
    self.activatesounds=False # turn on to play sounds
    self.sumptuous_browser=True # turn on to use browser tabs for DQM display

    self.pubsocket_bind_address='tcp://*:5566' # address of GUI PUB socket

    self.nodes=[ # addresses of connected nodes
        ('RC','tcp://pcethtb2.cern.ch:6002'),
        ('RO1','tcp://pcethtb1.cern.ch:6002'),
        #            ('RO2','tcp://cms-h4-03:6002'),
        ('EVTB','tcp://pcethtb2.cern.ch:6502'),
        #            ('table','tcp://cms-h4-01:6999')
        ]

    self.keepalive={} # nodes to monitor (comment to remove, never put False)
    self.keepalive['RC']=True
    self.keepalive['RO1']=True
#    self.keepalive['RO2']=True
    self.keepalive['EVTB']=True
#    self.keepalive['table']=True

    self.temperatureplot=None # 'http://blabla/tempplot.png' to be displayed for temperature history

# DQM plots, to be filled if not using tabbed browsing support
#        self.dqmplots=[] # [('tabname','http://plotname','http://largeplotname.png'),...]
#        self.dqmplots=[
#            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv11.png','/home/cmsdaq/DAQ/H4GUI/plots/canv21.png'),
#            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv12.png','/home/cmsdaq/DAQ/H4GUI/plots/canv22.png'),
#            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv13.png','/home/cmsdaq/DAQ/H4GUI/plots/canv23.png'),
#            ('tab2','/home/cmsdaq/DAQ/H4GUI/plots/canv14.png','/home/cmsdaq/DAQ/H4GUI/plots/canv24.png'),
#            ('tab2','/home/cmsdaq/DAQ/H4GUI/plots/canv15.png','/home/cmsdaq/DAQ/H4GUI/plots/canv25.png')
#            ]


    self.scripts={ # scripts linked to GUI buttons
        'sync_clocks': '../H4DAQ/scripts/syncclocks.sh',
        'free_space': None,
        'start_daemons': '../H4DAQ/scripts/startall.sh -v3 --rc=pcethtb2 --eb=pcethtb2 --dr=pcethtb1',
        'kill_daemons': '../H4DAQ/scripts/killall.sh'
        }

