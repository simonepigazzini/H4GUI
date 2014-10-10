#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pygst
import gst
import datetime
import urllib
import webkit
from subprocess import *
from zmq import *
from h4dbclasses import *

class H4GtkGui:

    def configure(self):

        self.debug=False
        self.activatesounds=False
        self.sumptuous_browser=False

        self.pubsocket_bind_address='tcp://*:5566'

        self.nodes=[
            ('RC','tcp://pcethtb2.cern.ch:6002'),
            ('RO1','tcp://pcethtb1.cern.ch:6002'),
#            ('RO2','tcp://cms-h4-03:6002'),
            ('EVTB','tcp://pcethtb2.cern.ch:6502'),
#            ('table','tcp://cms-h4-01:6999')
            ]

        self.keepalive={}
        self.keepalive['RC']=True
        self.keepalive['RO1']=True
#        self.keepalive['RO2']=True
        self.keepalive['EVTB']=True
#        self.keepalive['table']=True

        self.gui_out_messages={
            'startrun': 'GUI_STARTRUN',
            'pauserun': 'GUI_PAUSERUN',
            'restartrun': 'GUI_RESTARTRUN',
            'stoprun': 'GUI_STOPRUN',
            'die': 'GUI_DIE'
            }
        self.gui_in_messages={
            'status': 'STATUS',
            'log': 'GUI_LOG',
            'error': 'GUI_ERROR',
            'tablepos': 'TABLE_IS',
            'transfer': 'TRANSFER',
            'spillduration': 'SPILLDURATION'
            }
        self.rsdict={ #imported from H4DAQ/interface/Command.hpp 
            0:'START',
            1:'INIT',
            2:'INITIALIZED',
            3:'BEGINSPILL',
            4:'CLEARED',
            5:'WAITFORREADY',
            6:'CLEARBUSY',
            7:'WAITTRIG',
            8:'READ',
            9:'ENDSPILL',
            10:'RECVBUFFER',
            11:'SENTBUFFER',
            12:'SPILLCOMPLETED',
            13:'BYE',
            14:'ERROR'
            }
        self.remotestatus_juststarted=0
        self.remotestatus_betweenruns=2
        self.remotestatus_betweenspills=3
        self.remotestatus_endofspill=9
        self.remotestatuses_datataking=[6,7,8]
        self.remotestatuses_running=[4,5,6,7,8,9,10,11,12]
        self.remotestatuses_stopped=[0,1,2,13,14]

        self.globalstopconsent=False
        self.wanttostop=False
        self.wanttopause=False

        self.temperatureplot=None # 'http://blabla/tempplot.png'
#        self.dqmplots=[] # [('tabname','http://plotname','http://largeplotname.png'),...]
        self.dqmplots=[
            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv11.png','/home/cmsdaq/DAQ/H4GUI/plots/canv21.png'),
            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv12.png','/home/cmsdaq/DAQ/H4GUI/plots/canv22.png'),
            ('tab1','/home/cmsdaq/DAQ/H4GUI/plots/canv13.png','/home/cmsdaq/DAQ/H4GUI/plots/canv23.png'),
            ('tab2','/home/cmsdaq/DAQ/H4GUI/plots/canv14.png','/home/cmsdaq/DAQ/H4GUI/plots/canv24.png'),
            ('tab2','/home/cmsdaq/DAQ/H4GUI/plots/canv15.png','/home/cmsdaq/DAQ/H4GUI/plots/canv25.png')
            ]
        self.scripts={
            'sync_clocks': None, #' /scripts/blabla.sh'
            'free_space': None,
            'start_daemons': None,
            'kill_daemons': None
        }

    def __init__(self):

        self.configure()

        self.status={
            'localstatus': 'STARTED',
            'runnumber': 0,
            'spillnumber': 0,
            'evinrun': 0,
            'evinspill': 1,
            'table_status': (0,0,'TAB_DONE'),
            'badspills': 0,
            'spillsize': 0,
            'transferRate': 0,
            'spillduration': 0,
            'trigrate': 0,
            'temperatures': [],
            'humidity': 0,
            'dewpoint': 0,
            'laudatemp': 0
            }

        self.remote={}
        for node,addr in self.nodes:
            self.remote[('statuscode',node)]=self.remotestatus_juststarted
            self.remote[('status',node)]=self.rsdict[self.remote[('statuscode',node)]]
            self.remote[('runnumber',node)]=0
            self.remote[('spillnumber',node)]=0
            self.remote[('evinspill',node)]=0
            self.remote[('gentriginspill',node)]=0
            self.remote[('evinrun',node)]=0
            self.remote[('paused',node)]=0

        self.allbuttons=['createbutton','startbutton','pausebutton','stopbutton']
        self.allrunblock=['runtypebutton','runnumberspinbutton','tablexspinbutton','tableyspinbutton','movetablebutton',
                          'runstarttext','runstoptext','runtext','daqstringentry','pedfrequencyspinbutton',
                          'beamparticlebox','beamenergyentry','beamsigmaxentry','beamsigmayentry',
                          'beamintensityentry','beamtiltxentry','beamtiltyentry']
        self.playlevel=0
        self.global_veto_alarm=False
        self.autostop_max_events=-1
        self.locdqmplots={}
        self.loclargedqmplots={}
        self.dqmplotsimgb_={}

        gtk.rc_parse('.h4gtkrc')
        self.gm = gtk.Builder()
        self.gm.add_from_file("H4GtkGui.glade")
        self.gm.connect_signals(self)
        self.mainWindow = self.gm.get_object("MainWindow")
        self.mainWindow.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        self.set_spinbuttons_properties()
        self.mywaiter = waiter(self.gm)

        if self.sumptuous_browser:
            self.btabs=[]
            BrowserTab(self.gm.get_object('dqmnotebook'),self.btabs,'http://www.google.com')
            BrowserTab(self.gm.get_object('dqmnotebook'),self.btabs,'http://www.cern.ch')
        else:
            self.init_dqm_plots()
            gobject.timeout_add(5000,self.update_dqm_plots)

        self.confdb = DataTakingConfigHandler()
        self.confblock = DataTakingConfig()
        self.confdb.confblock = self.confblock
        self.start_network()

        self.gotostatus('INIT')
        self.mainWindow.connect('destroy',gtk.main_quit)
        self.mainWindow.show_all()

        self.aliveblinkstatus=False
        gobject.timeout_add(1000,self.change_color_blinkingalive)
        self.alarms={}
        self.alarmblinkstatus=False
        gobject.timeout_add(500,self.check_alarm)

        gobject.idle_add(self.update_gui_statuscounters)
        gobject.timeout_add(500,self.update_temperature)


# NETWORKING
    def start_network(self):
        self.context = Context()
        self.poller = Poller()
        self.sub={}
        for node,addr in self.nodes:
            self.sub[node] = self.context.socket(SUB)
            self.sub[node].connect(addr)
            self.sub[node].setsockopt(SUBSCRIBE,'')
            self.poller.register(self.sub[node],POLLIN)
        self.pub = self.context.socket(PUB)
        self.pub.bind(self.pubsocket_bind_address)
        gobject.idle_add(self.poll_sockets)
        gobject.timeout_add(5000,self.check_keepalive)
        return False
    def poll_sockets(self):
        socks = dict(self.poller.poll(1))
        for node,sock in self.sub.iteritems():
            if (socks.get(sock)):
                message = sock.recv()
                if node in self.keepalive.keys():
                    self.keepalive[node]=True
                self.proc_message(node,message)
        return True
    def check_keepalive(self):
        for node,val in self.keepalive.iteritems():
            if not val:
                self.set_alarm('Lost connection with '+str(node),1)
            else:
                self.unset_alarm('Lost connection with '+str(node))
            self.keepalive[node]=False
        return True
    def send_message(self,msg,param='',forcereturn=None):
        mymsg=msg
        if not param=='':
            mymsg=str().join([str(mymsg),' ',str(param)])
        if (self.debug):
            self.Log(str(' ').join(('Sending message:',str(mymsg))))
        self.pub.send(mymsg)
        if not forcereturn==None:
            return forcereturn
    def proc_message(self,node,msg):
        if (self.debug):
            newmsg=str(msg)
            self.Log(str(' ').join(('Processing message from',str(node),':',newmsg)))
        if node in self.keepalive.keys():
            self.keepalive[node]=True
        parts = msg.split(' ')
        if len(parts)<1:
            return
        tit = parts[0]
        parts = parts[1:]
        if tit==self.gui_in_messages['status']:
            oldstatus=self.remote[('status',node)]
            for part in parts:
                if part.find('=')<0:
                    continue
                key,val=part.split('=')
                try:
                    self.remote[(key,node)]=int(val)
                except ValueError:
                    self.Log('Impossible to interpret message: <'+msg+'>')
                    True
            self.remote[('status',node)]=self.rsdict[self.remote[('statuscode',node)]]
            if self.remote[('statuscode',node)] in self.remotestatuses_datataking:
                self.remote[('status',node)]='DATATAKING'
            self.update_gui_statuscounters()
            if not oldstatus==self.remote[('status',node)]:
#                self.Log('Status change for '+str(node)+': '+str(oldstatus)+' -> '+str(self.remote[('status',node)]))
                if self.remote[('status',node)]=='ERROR':
                    self.set_alarm('Node %s in ERROR'%(node,),2)
                if node=='RC':
                    self.processrccommand(self.remote[('status',node)])
        elif tit=='GUI_LOG':
            print 'GUI_LOG TO BE IMPLEMENTED'
#            self.Log(str().join(['[',str(node),']: '].extend(parts)) #IMPL
        elif tit=='GUI_ERROR':
            print 'GUI_ERROR TO BE IMPLEMENTED'
#            level = int(parts[0])
#            parts=parts[1:]
#            message=str().join(['[',str(node),' ERROR]: ']).extend(parts)
#            self.Log(message)
#            self.set_alarm(message,level)
        elif tit=='GUI_SPS':
            print 'GUI_SPS TO BE IMPLEMENTED'
            self.flash_sps(str(parts[0])) #IMPL
        elif tit==self.gui_in_messages['tablepos']:
            self.status['table_position']=(float(parts[0]),float(parts[1]),str(parts[2]))
        elif tit==self.gui_in_messages['transfer']:
            if node=='EVTB':
                for part in parts:
                    if part.find('=')<0:
                        continue
                    key,val=part.split('=')
                    if key=='badspills':
                        self.status[key]=int(val)
                    elif key=='transferTime':
                        transferTime=val # in usec
                    elif key=='transrate_size':
                        transferSize=val # in bytes
                rate = float(transferSize)/1.048576/float(transferTime) # MB/s
                self.status['spillsize']=float(transferSize)/1048576. # MB
                self.status['transferRate']=rate
        elif tit==self.gui_in_messages['spillduration']:
            if node=='RC':
                for part in parts:
                    if part.find('=')<0:
                        continue
                    key,val=part.split('=')
                    if key=='runnumber' and self.status[key]!=int(val):
                        break
                    if key=='spillnumber' and self.status[key]!=int(val):
                        break
                    if key=='spillduration':
                        self.status[key]=float(val)/1000000. # in seconds
                        if val!=0:
                            self.status['trigrate']=float(self.remote[('evinspill',node)])/self.status[key]
                        else:
                            self.status['trigrate']=0

# RUN STATUS AND COUNTERS, GUI ELEMENTS SENSITIVITY AND MANIPULATION
    def update_gui_statuscounters(self):
        self.status['runnumber']=self.remote[('runnumber','RC')]
        self.status['spillnumber']=self.remote[('spillnumber','RC')]
        self.status['evinspill']=self.remote[('evinspill','RC')]
        self.status['evinrun']=self.remote[('evinrun','RC')]
        if self.remote[('gentriginspill','RC')]>0:
            self.status['deadtime']=100.*float(self.remote[('evinspill','RC')])/float(self.remote[('gentriginspill','RC')])
        else:
            self.status['deadtime']=100.
        if not self.gm.get_object('runstatuslabel').get_text().split(' ')[-1]==self.remote[('status','RC')]:
            self.gm.get_object('runstatuslabel').set_text(str(' ').join(('Run controller:',self.remote[('status','RC')])))
            self.flash_widget(self.gm.get_object('runstatusbox'),'green')
        if 'RO1' in [x[0] for x in self.nodes]:
            self.gm.get_object('ro1label').set_text( str(' ').join(('Data readout unit 1:',self.remote[('status','RO1')])))
        if 'RO2' in [x[0] for x in self.nodes]:
            self.gm.get_object('ro2label').set_text( str(' ').join(('Data readout unit 2:',self.remote[('status','RO2')])))
        if 'EVTB' in [x[0] for x in self.nodes]:
            self.gm.get_object('evtblabel').set_text(str(' ').join(('Event builder:',self.remote[('status','EVTB')])))
        self.gm.get_object('runnumberlabel').set_text(str().join(['Run number: ',str(self.status['runnumber'])]))
        self.gm.get_object('spillnumberlabel').set_text(str().join(['Spill number: ',str(self.status['spillnumber'])]))
        self.gm.get_object('badspillslabel').set_text(str().join(['Nr. of bad spills: ',str(self.status['badspills'])]))
        self.gm.get_object('evinrunlabel').set_text(str().join(['Total #events in run: ',str(self.status['evinrun'])]))
        self.gm.get_object('evinspilllabel').set_text(str().join(['Nr. of events in spill: ',str(self.status['evinspill'])]))
        self.gm.get_object('gentriglabel').set_text(str().join([ 'Dead time: %.2f'%(self.status['deadtime'],)      ,' %'      ]))
        self.gm.get_object('spillsizelabel').set_text(str().join(['Spill size (MB): ',str('%.1f'%(self.status['spillsize'],))]))
        self.gm.get_object('transfratelabel').set_text(str().join(['Transfer rate (MB/s): ',str('%.1f'%(self.status['transferRate'],))]))
        self.gm.get_object('spilldurationlabel').set_text(str().join(['Spill duration (s): ',str('%.3f'%(self.status['spillduration'],))]))
        self.gm.get_object('trigratelabel').set_text(str().join(['Trigger rate (Hz): ',str('%.1f'%(self.status['trigrate'],))]))
        temptext = ' Sensors temp. (°C): '
        for i in xrange(len(self.status['temperatures'])):
            if i>0:
                temptext+='/ '
            mytemp = ''
            if self.status['temperatures'][i]!=None:
                mytemp = '%.2f '%(self.status['temperatures'][i],)
            temptext+=mytemp
        self.gm.get_object('templabel').set_text(temptext)
        temptext='Humidity ('+'%'+'): '
        if self.status['humidity']:
            temptext+='%.2f'%(self.status['humidity'],)
        self.gm.get_object('humlabel').set_text(temptext)
        temptext='Dew point (°C): '
        if self.status['dewpoint']:
            temptext+='%.2f'%(self.status['dewpoint'],)
        self.gm.get_object('dewpointlabel').set_text(temptext)
        temptext='Lauda temp. (°C): '
        if self.status['laudatemp']:
            temptext+='%.2f '%(self.status['laudatemp'],)
        self.gm.get_object('laudatemplabel').set_text(temptext)
        return True

    def set_sens(self,wids,value):
        for wid in wids:
            if not self.gm.get_object(str(wid)):
                self.Log(str().join(('ERROR ',wid)))
            self.gm.get_object(str(wid)).set_sensitive(value)
    def set_label(self,wid,value):
        self.gm.get_object(str(wid)).set_label(str(value))

    def set_spinbuttons_properties(self):
        button = self.gm.get_object('runnumberspinbutton')
        button.set_value(0)
        button.set_numeric(True)
        button.set_increments(1,10)
        button.set_range(0,100000)
        button.set_wrap(False)
        button = self.gm.get_object('pedfrequencyspinbutton')
        button.set_value(0)
        button.set_numeric(True)
        button.set_increments(100,1000)
        button.set_range(0,1000000)
        button.set_wrap(False)
        tablebuttons=[self.gm.get_object('tablexspinbutton'),self.gm.get_object('tableyspinbutton')]
        for button in tablebuttons:
            button.set_value(0)
            button.set_numeric(True)
            button.set_increments(0.1,1)
            button.set_range(-1000,1000)
            button.set_wrap(False)
        self.init_gtkcombobox(self.gm.get_object('runtypebutton'),['PHYSICS','PEDESTAL','LED'])
        self.init_gtkcombobox(self.gm.get_object('beamparticlebox'),['Electron','Positron','Pion','Muon'])
        gobject.idle_add(self.define_sensitivity_runtext)

    def define_sensitivity_runtext(self):
        if (self.status['localstatus'] in ['RUNNING','PAUSED','STOPPED']) and int(self.gm.get_object('runnumberspinbutton').get_value())==self.status['runnumber']:
                self.gm.get_object('runtext').set_sensitive(True)
        else:
            self.gm.get_object('runtext').set_sensitive(False)
        return True

     # GtkComboBoxEntry (deprecated)
#    def read_gtkcomboboxentry_string(self,button):
#        return str(button.child.get_text())
#    def update_comboboxentry(self,button):
#        output = self.read_gtkcombobox_status(button)
#        if output:
#            newtext=str(output)
#            button.child.set_text(newtext)


    # GtkSpinButton
    def set_gtkspinbutton(self,button,value):
        button.set_value(value or 0)

    # GtkEntry
    def set_gtkentry(self,button,value):
        out = ''
        myval=str(value)
        if myval!='' and myval!='None':
            out=myval
        button.set_text(out)
    def get_gtkentry(self,button):
        return button.get_text()

    # GtkTextBuffer
    def get_text_from_textbuffer(self,bufname):
        buf=self.gm.get_object(bufname)
        out=buf.get_text(buf.get_start_iter(),buf.get_end_iter())
        return out

    # GtkComboBox
    def set_gtkcombobox_entry(self,button,newentry):
        for index in xrange(len(button.get_model())):
            if newentry==button.get_model()[index][0]:
                button.set_active(index)
    def read_gtkcombobox_status(self,button):
        tree_iter = button.get_active_iter()
        thisentry=None
        if tree_iter:
            model = button.get_model()
            thisentry = model[tree_iter][0]
        return thisentry
    def set_gtkcombobox_options(self,button,mylist):
        entrylist = gtk.ListStore(str)
        for entry in mylist:
            entrylist.append([entry])
        button.set_model(entrylist)
        button.set_active(-1)
    def init_gtkcombobox(self,button,mylist):
        self.set_gtkcombobox_options(button,mylist) 
        renderer_text = gtk.CellRendererText()
        button.pack_start(renderer_text, True)
        button.add_attribute(renderer_text, "text", 0)       



# ALARMS
    def Log(self,mytext):
        mytext_=str(' ').join((datetime.datetime.now().strftime('%d.%m.%y %H:%M:%S'),mytext))
        mybuffer=self.gm.get_object('rclogbuffer')
        mybuffer.insert(mybuffer.get_end_iter(),str(mytext_)+'\n')
    def on_rclogview_size_allocate(self,*args):
        adj=self.gm.get_object('scrolledwindow3').get_vadjustment()
        adj.set_value(adj.get_upper()-adj.get_page_size()) 
    def set_alarm(self,msg='Error_Generic',level=1):
        if self.global_veto_alarm:
            return
        if level==0:
            self.unset_alarm(msg)
            return
        else:
            setit=False
            if msg not in self.alarms.keys():
                setit=True
            elif self.alarms[msg]!=level:
                setit=True
            if setit:
                self.Log('Setting alarm %d: '%(level,)+msg)
                if level>=2:
                    if self.activatesounds:
                        self.bark(20)
                elif level>=1:
                    if self.activatesounds:
                        self.beep(2)
        self.alarms[msg]=level
    def unset_alarm(self,msg):
        if msg in self.alarms.keys():
            self.Log('Clearing alarm: '+msg)
        self.alarms.pop(msg,None)
    def clear_alarms(self):
        self.alarms.clear()
        self.barktimes=0
        self.beeptimes=0
        self.playlevel=0
    def check_alarm(self):
        if self.alarmblinkstatus==False:
            color=None
            mylevel=0
            if not len(self.alarms)==0:
                mylevel = max(self.alarms.itervalues())
                if mylevel>=2:
                    color=gtk.gdk.color_parse('red')
                elif mylevel>=1:
                    color=gtk.gdk.color_parse('yellow')
            self.gm.get_object('alarmbox').modify_bg(gtk.STATE_NORMAL,color)
            if mylevel>=1:
                self.gm.get_object('MainWindow').modify_bg(gtk.STATE_NORMAL,color)
        else:
            self.gm.get_object('alarmbox').modify_bg(gtk.STATE_NORMAL,None)
            self.gm.get_object('MainWindow').modify_bg(gtk.STATE_NORMAL,None)
        self.alarmblinkstatus=not self.alarmblinkstatus
        return True
    def change_color_blinkingalive(self):
        if self.aliveblinkstatus==False:
            self.gm.get_object('alivebox').modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse("green"))
        else:
            self.gm.get_object('alivebox').modify_bg(gtk.STATE_NORMAL,None)
        self.aliveblinkstatus = not self.aliveblinkstatus
        return True
    def color_widget(self,widget,color=None,forcereturn=None):
        if (color=='' or color==None):
            widget.modify_bg(gtk.STATE_NORMAL,None)
        else:
            widget.modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse(color))
    def flash_widget(self,widget,color,duration=300):
        self.color_widget(widget,color)
        gobject.timeout_add(300,self.color_widget,widget,None,False)
    def flash_sps(self,signal):
        signal+='box'
        self.flash_widget(self.gm.get_object(signal),'orange')


# EXEC ACTIONS
    def send_stop_pause_messages(self):
        if rc in self.remotestatuses_running:
            if self.wanttostop:
                self.stoprun()
            elif self.wanttopause:
                self.pauserun()
    def processrccommand(self,command):
        rc=self.remote[('statuscode','RC')]
        if rc in self.remotestatuses_stopped:
            if self.status['localstatus'] in ['RUNNING','PAUSED']:
                if not self.globalstopconsent:
                    self.set_alarm('RUN STOPPED WITHOUT USER REQUEST',2)
                self.gotostatus('STOPPED')
                self.globalstopconsent=False
            else:
                self.gotostatus('INIT')
        else:
            if not self.remote[('paused','RC')]:
                self.gotostatus('RUNNING')
            else:
                self.gotostatus('PAUSED')
        if rc==self.remotestatus_endofspill:
            if self.autostop_max_events>0 and self.status['evinrun']>=self.autostop_max_events:
                self.on_stopbutton_clicked()
    def remotecheckpaused(self,whatiwant):
        return (self.remote[('paused','RC')]==whatiwant)

    def createrun(self):
        if self.status['localstatus']=='CREATED':
            self.gotostatus('INIT')
            return
        self.get_gui_confblock()
        self.confblock = self.confdb.read_from_db(runnr=self.confblock.r['run_number'])
        self.gotostatus('CREATED')
        self.confblock.r['run_end_user_comment']=''
        self.confblock.r['run_comment']=''
        self.update_gui_confblock()

    def startrun(self):
        self.get_gui_confblock()
        if not self.table_is_ok(self.confblock.r['table_horizontal_position'],self.confblock.r['table_vertical_position']):
            self.Log('Table condition does not allow to start run: have you forgotten to actually move the table? Current situation:')
            self.Log(str(self.status['table_status']))
            return
        for key,node,val in [(a[0],a[1],b) for a,b in self.remote.iteritems()]:
            if key!='statuscode':
                continue
            if node in ['RC','RO1','RO2','EVTB']:
                if val!=self.remotestatus_betweenruns:
                    self.Log('Node %s not ready for STARTRUN'%(str(node),))
                    return
        self.status['evinrun']=0
        self.confblock.d['daq_gitcommitid']=self.get_latest_commit()
        self.confblock=self.confdb.add_into_db(self.confblock)
        self.update_gui_confblock()
        self.Log('Sending START for run '+str(self.confblock.r['run_number']))
        self.send_message(str(' ').join([str(self.gui_out_messages['startrun']),str(self.confblock.r['run_number']),str(self.confblock.t['run_type_description']),str(self.confblock.t['ped_frequency'])]))        

    def pauserun(self):
        if self.status['localstatus']=='RUNNING':
            self.Log('Sending PAUSE for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['pauserun'])

    def resumerun(self):
        if self.status['localstatus']=='PAUSED':
            self.Log('Sending RESUME for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['restartrun'])

    def remstatus_is(self,whichstatus):
        return (self.remote[('statuscode','RC')] in whichstatus)

    def stoprun(self):
        self.globalstopconsent=True
        self.autostop_max_events=-1
        self.gm.get_object('maxevtoggle').set_active(False)
        self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_NORMAL,None)
        self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_PRELIGHT,None)
        self.Log('Sending STOP for run '+str(self.confblock.r['run_number']))
        self.send_message(self.gui_out_messages['stoprun'])
        self.gui_go_to_runnr(self.status['runnumber'])

    def closerun(self):
        self.get_gui_confblock()
        self.confblock.r['run_exit_code']=0 # IMPL
        self.confblock.r['run_nevents']=self.remote[('evinrun','RC')]
        self.confblock.r['run_deadtime']=self.status['deadtime']
        self.confblock=self.confdb.update_to_db(self.confblock)
        self.gotostatus('INIT')

# PROCESS SIGNALS
    def on_buttonquit_clicked(self,*args):
        self.mywaiter.reset()
        self.mywaiter.set_layout('Do you want to quit the GUI?','Cancel','Yes',color='yellow')
        self.mywaiter.set_exit_func(gtk.main_quit,[])
        self.mywaiter.run()        
    def on_quitbuttonRC_clicked(self,*args):
        self.Log("Request to quit run controller from GUI user")
        self.mywaiter.reset()
        self.mywaiter.set_layout('<b>Do you want to quit the DAQ?</b>','Cancel','Yes',color='red')
        self.mywaiter.set_exit_func(self.send_message,[self.gui_out_messages['die']])
        self.mywaiter.run()        
    def on_createbutton_clicked(self,*args):
        self.createrun()
    def on_startbutton_clicked(self,*args):
        message = 'Do you want to start?'
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Cancel','Start',color='green')
        self.mywaiter.set_exit_func(self.startrun,[])
        self.mywaiter.run()


    def on_pausebutton_clicked(self,*args):
        if self.status['localstatus']=='RUNNING':
            message = 'Do you want to pause?'
        elif self.status['localstatus']=='PAUSED':
            message = 'Do you want to resume?'
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Cancel','Yes')
        if self.status['localstatus']=='RUNNING':
            self.mywaiter.set_exit_func(self.set_true,[self.wanttopause])
        elif self.status['localstatus']=='PAUSED':
            self.mywaiter.set_exit_func(self.resumerun,[])
        self.mywaiter.run()
    def on_stopbutton_clicked(self,*args):
        if self.status['localstatus']=='STOPPED':
            self.closerun()
        else:
            self.mywaiter.reset()
            self.mywaiter.set_layout('Do you want to stop?','Cancel','Yes',color='orange')
            self.mywaiter.set_exit_func(self.set_true,[self.wanttostop])
            self.mywaiter.run()
    def set_true(self,*args):
        for arg in args:
            arg = True
    def gui_go_to_runnr(self,newrunnr):
        if not self.confdb.run_exists(newrunnr):
            return False
        self.confblock=self.confdb.read_from_db(runnr=newrunnr)
        self.update_gui_confblock()
        return True
    def on_runnumberspinbutton_value_changed(self,*args):
        newnr=int(self.gm.get_object('runnumberspinbutton').get_value())
        if newnr>=0:
            isgood = self.gui_go_to_runnr(newnr)
            if not isgood:
                self.Log('Run %s does not exist' % str(newnr))
    def on_runtextbuffer_end_user_action(self,*args):
        self.get_gui_confblock()
        if not self.confblock.r['run_number']==self.status['runnumber']:
            return
        self.confblock=self.confdb.update_to_db(self.confblock,onlycomment=True)

# DATATAKINGCONFIG MANIPULATION
    def update_gui_confblock(self):
        self.set_gtkcombobox_entry(self.gm.get_object('runtypebutton'),self.confblock.t['run_type_description'])
        self.set_gtkspinbutton(self.gm.get_object('runnumberspinbutton'),(self.confblock.r['run_number']))
        self.set_gtkspinbutton(self.gm.get_object('tablexspinbutton'),(self.confblock.r['table_horizontal_position']))
        self.set_gtkspinbutton(self.gm.get_object('tableyspinbutton'),(self.confblock.r['table_vertical_position']))
        self.set_gtkspinbutton(self.gm.get_object('pedfrequencyspinbutton'),(self.confblock.t['ped_frequency']))
        self.set_gtkentry(self.gm.get_object('runstarttext'),(self.confblock.r['run_start_user_comment']))
        self.set_gtkentry(self.gm.get_object('runstoptext'),(self.confblock.r['run_end_user_comment']))
        self.set_gtkentry(self.gm.get_object('daqstringentry'),(self.confblock.d['daq_type_description']))
        self.set_gtkentry(self.gm.get_object('beamenergyentry'   ),(self.confblock.b['beam_energy']))
        self.set_gtkentry(self.gm.get_object('beamsigmaxentry'   ),(self.confblock.b['beam_horizontal_width']))
        self.set_gtkentry(self.gm.get_object('beamsigmayentry'   ),(self.confblock.b['beam_vertical_width']))
        self.set_gtkentry(self.gm.get_object('beamintensityentry'),(self.confblock.b['beam_intensity']))
        self.set_gtkentry(self.gm.get_object('beamtiltxentry'    ),(self.confblock.b['beam_horizontal_tilt']))
        self.set_gtkentry(self.gm.get_object('beamtiltyentry'    ),(self.confblock.b['beam_vertical_tilt']))
        self.set_gtkcombobox_entry(self.gm.get_object('beamparticlebox'),self.confblock.b['beam_particle'])    
        self.set_gtkentry(self.gm.get_object('runtextbuffer'),self.confblock.r['run_comment'])
    def get_gui_confblock(self):
        self.confblock.r['run_number']=int(self.gm.get_object('runnumberspinbutton').get_value())
        self.confblock.r['table_horizontal_position']=self.gm.get_object('tablexspinbutton').get_value()
        self.confblock.r['table_vertical_position']=self.gm.get_object('tableyspinbutton').get_value()
        self.confblock.r['run_start_user_comment']=self.gm.get_object('runstarttext').get_text()
        self.confblock.r['run_end_user_comment']=self.gm.get_object('runstoptext').get_text()
        self.confblock.t['run_type_description']=self.read_gtkcombobox_status(self.gm.get_object('runtypebutton'))
        self.confblock.t['ped_frequency']         =self.gm.get_object('pedfrequencyspinbutton').get_value()
        self.confblock.d['daq_type_description']=self.gm.get_object('daqstringentry').get_text()
        self.confblock.b['beam_particle']         =self.read_gtkcombobox_status(self.gm.get_object('beamparticlebox'))
        self.confblock.b['beam_energy']           =self.gm.get_object('beamenergyentry'   ).get_text()
        self.confblock.b['beam_horizontal_width'] =self.gm.get_object('beamsigmaxentry'   ).get_text()
        self.confblock.b['beam_vertical_width']   =self.gm.get_object('beamsigmayentry'   ).get_text()
        self.confblock.b['beam_intensity']        =self.gm.get_object('beamintensityentry').get_text()
        self.confblock.b['beam_horizontal_tilt']  =self.gm.get_object('beamtiltxentry'    ).get_text()
        self.confblock.b['beam_vertical_tilt']    =self.gm.get_object('beamtiltyentry'    ).get_text()
        self.confblock.r['run_comment'] = self.get_text_from_textbuffer('runtextbuffer')

# FSM
    def gotostatus(self,status):
#        self.Log(str().join(['Local status:',self.status['localstatus'],'->',status]))
        self.status['localstatus']=status
        if status=='INIT':
            self.confblock=self.confdb.read_from_db(runnr=self.confdb.get_highest_run_number())
            self.update_gui_confblock()
        if status=='INIT':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['createbutton'],True)
            self.set_label('createbutton','CREATE RUN')
            self.set_label('startbutton','START RUN')
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('stopbutton','STOP RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)
        elif status=='CREATED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,True)
            self.set_sens(['runnumberspinbutton','runstoptext'],False)
            self.set_sens(['createbutton','startbutton','movetablebutton'],True)
            self.set_label('createbutton','CANCEL')
            self.set_label('startbutton','START RUN')
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('stopbutton','STOP RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(False)
        elif status=='RUNNING':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['pausebutton','stopbutton'],True)
            self.set_label('createbutton','CREATE RUN')
            self.set_label('startbutton','START RUN')
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('stopbutton','STOP RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)
        elif status=='PAUSED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['pausebutton','stopbutton'],True)
            self.set_label('createbutton','CREATE RUN')
            self.set_label('startbutton','START RUN')
            self.set_label('pausebutton','RESUME RUN')
            self.set_label('stopbutton','STOP RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)
        elif status=='STOPPED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['stopbutton'],True)
            self.set_sens(['runstoptext'],True)
            self.set_label('createbutton','CREATE RUN')
            self.set_label('startbutton','START RUN')
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('stopbutton','CLOSE RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)


# TABLE POSITION HANDLING
    def get_table_position(self):
        return self.status['table_status']
    def set_table_position(self,newx,newy):
        if self.get_table_position()[2]!='TAB_DONE':
            self.Log('ERROR: trying to move table while table is not stopped')
            return False
        if self.status['table_status']!=(newx,newy,'TAB_DONE'):
            self.status['table_status']=(self.status['table_status'][0],self.status['table_status'][1],'SENT_MOVE_ORDER')
#            self.send_message('SET_TABLE_POSITION %s %s' % (newx,newy,)) #SAFETY
        message='Waiting for table to move to '+str(newx)+' '+str(newy)
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,None,'Force ACK table moving')
        self.mywaiter.set_condition(self.table_is_ok,[newx,newy])
        self.mywaiter.run()
    def on_movetablebutton_clicked(self,*args):
        x=self.gm.get_object('tablexspinbutton').get_value()
        y=self.gm.get_object('tableyspinbutton').get_value()
        self.set_table_position(x,y)
    def table_is_ok(self,newx,newy):
        if self.get_table_position()==(newx,newy,'TAB_DONE'):
            return True
        return False


# GENERAL INPUT WINDOW
    def generalinputwindow(self,label,func):
        self.set_label('inputwindowlabel',label)
        self.set_gtkentry(self.gm.get_object('inputwindowentry'),'')
        self.gm.get_object('InputWindow').show()
        self.inputwindowentryfunction=func
    def on_inputwindowentry_activate(self,*args):
        message = self.gm.get_object('inputwindowentry').get_text()
        self.inputwindowentryfunction(message)
    def on_inputwindowquit_clicked(self,*args):
        self.gm.get_object('InputWindow').hide()

    def on_dummyguibutton_clicked(self,*args):
        self.generalinputwindow('Send command with DummyGUI',self.send_message)
    def on_clearalarmbutton_clicked(self,*args):
        self.clear_alarms()
    def on_vetoalarmbutton_toggled(self,*args):
        self.global_veto_alarm=self.gm.get_object('vetoalarmbutton').get_active()
        color=None
        if self.global_veto_alarm:
            color=gtk.gdk.color_parse('orange')
            self.clear_alarms()
        self.gm.get_object('vetoalarmbutton').modify_bg(gtk.STATE_ACTIVE,color)
        self.gm.get_object('vetoalarmbutton').modify_bg(gtk.STATE_PRELIGHT,color)



# SOUNDS
    def bark(self,times):
        self.barktimes=3*times
        gobject.timeout_add(600,self.bark_helper)
    def bark_helper(self):
        if self.playlevel>2:
            return False
        if self.barktimes<=0:
            self.playlevel=0
            return False
        self.playlevel=2
        if not self.barktimes%3==1:
            soundcom = ('filesrc location=%s ! decodebin2 ! autoaudiosink') % \
            '/usr/share/sounds/gnome/default/alerts/bark.ogg'
            self.play = gst.parse_launch(soundcom)
            self.play.set_state(gst.STATE_PLAYING)
        self.barktimes-=1;
        return True
    def beep(self,times,freq=400):
        self.beeptimes=2*times
        soundcom = ('audiotestsrc freq=%d ! decodebin2 ! autoaudiosink') % freq
        self.play = gst.parse_launch(soundcom)
        self.playlevel=1
        gobject.timeout_add(2000,self.beep_helper,self.play,self.beeptimes)
    def beep_helper(self,p,beeptimes):
        if self.playlevel>1:
            return False
        if self.beeptimes<=0:
            self.playlevel=0
            return False
        if self.beeptimes%2==0:
            p.set_state(gst.STATE_PLAYING)
        else:
            p.set_state(gst.STATE_PAUSED)
        self.beeptimes-=1;
        return True


# WAITING WINDOW
    def on_waitbutton1_clicked(self,*args):
        self.mywaiter.on_waitbutton1_clicked_(args)
    def on_waitbutton2_clicked(self,*args):
        self.mywaiter.on_waitbutton2_clicked_(args)

# PLOT DISPLAY WINDOW
    def on_maxevtoggle_toggled(self,button,*args):
        if button.get_active():
            self.autostop_max_events=int(self.gm.get_object('maxeventry').get_text())
            self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_ACTIVE,gtk.gdk.color_parse('orange'))
            self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_PRELIGHT,gtk.gdk.color_parse('orange'))
        else:
            self.autostop_max_events=-1
            self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_NORMAL,None)
            self.gm.get_object('maxevtoggle').modify_bg(gtk.STATE_PRELIGHT,None)

    def update_temperature(self):
        myenv = self.confdb.get_latest_environment()
        self.status['temperatures']=[myenv['T1'],myenv['T2'],myenv['T3'],myenv['T4'],myenv['T5']]
        self.status['humidity']=myenv['Humidity']
        self.status['dewpoint']=myenv['DewPoint']
        myenv2 = self.confdb.get_latest_laudareading()
        self.status['laudatemp']=myenv2['lauda_temp_mon']
        return True

    def get_latest_commit(self):
        p1 = Popen(['git','--work-tree=../H4DAQ','log','--pretty=format:\"%H\"'], stdout=PIPE)
        p2 = Popen(['head', '-n 1'], stdin=p1.stdout, stdout=PIPE)
        p1.stdout.close()
        output = p2.communicate()[0]
        output=output.replace('\n','')
        output=output.replace('\"','')
        return str(output)

    def init_dqm_plots(self):
        nb = self.gm.get_object('dqmnotebook')
        tabnames=[]
        scrollwin={}
        myindex=0
        for tabname,plotname,largeplotname in self.dqmplots:
            if tabname not in tabnames:
                scrollwin[tabname] = gtk.ScrolledWindow()
                scrollwin[tabname].set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
                mylabel = gtk.Label(tabname)
                nb.append_page(scrollwin[tabname],mylabel)
                tabnames.append(tabname)
                scrw=scrollwin[tabname]
                tab = gtk.Table(1,3,True)
                scrw.add_with_viewport(tab)
                myindex=0
            evtb = gtk.EventBox()
            imgb = gtk.Image()
            evtb.add(imgb)
            x=int(myindex)%3
            y=int(myindex)/3
            if y>=int(tab.get_property('n-rows')):
                tab.resize(y+1,3)
            tab.attach(evtb,x,x+1,y,y+1)
            locname=plotname.split('/')[-1]
            loclargename=largeplotname.split('/')[-1]
            self.dqmplotsimgb_[plotname]=imgb
            self.locdqmplots[plotname]=self.geturlfile(plotname)
            self.loclargedqmplots[plotname]=self.geturlfile(largeplotname)
            handler_id = evtb.connect('button-press-event',self.open_window_image_clicked,self.loclargedqmplots[plotname])
            myindex+=1
        self.update_dqm_plots()


    def update_dqm_plots(self):
        for tabname,plotname,largeplotname in self.dqmplots:
            self.locdqmplots[plotname]=self.geturlfile(plotname)
            self.loclargedqmplots[plotname]=self.geturlfile(largeplotname)
            self.dqmplotsimgb_[plotname].set_from_file(self.locdqmplots[plotname])

    def geturlfile(self,path):
        if not path:
            return None
        if path.find('http://')!=-1:
            newname='tmp/'+path.split('/')[-1]
            urllib.urlretrieve(path,newname)
        else:
            newname=path
        return newname


    def on_tempeventbox_button_press_event(self,*args):
        self.open_window_image_clicked(imagefile=self.geturlfile(self.temperatureplot))
    def on_image_clicked_buttonpressev(self,wid,ev,im=None):
        self.open_window_image_clicked(imagefile=im)

    def open_window_image_clicked(self,wid=None,ev=None,imagefile=None,*args):
        if imagefile==None or imagefile=='':
            return
        win = gtk.Window()
        win.set_position(gtk.WIN_POS_MOUSE)
        evtb = gtk.EventBox()
        win.add(evtb)
        imgb = gtk.Image()
        imgb.set_from_file(imagefile)
        evtb.add(imgb)
        evtb.connect('button-press-event',self.closewinparent)
        win.show_all()
    def closewinparent(self,wid,*args):
        wid.get_parent_window().destroy()

    def on_syncclocksbutton_clicked(self,*args):
        self.run_script(self.scripts.get('sync_clocks',None))
    def on_freespacebutton_clicked(self,*args):
        self.run_script(self.scripts.get('free_space',None))
    def on_startdaemonsbutton_clicked(self,*args):
        self.run_script(self.scripts.get('start_daemons',None))
    def on_killdaemonsbutton_clicked(self,*args):
        self.run_script(self.scripts.get('kill_daemons',None))


    def run_script(self,script=None):
        if script==None or script=='':
            return
        self.mywaiter.set_layout('<b>Do you really want to run '+script+'?</b>','Cancel','Run')
        self.mywaiter.set_exit_func(self.run_script_helper,[script])
    def run_script_helper(self,script=None):
        if self.status['localstatus']==RUNNING:
            self.Log('Do not run scripts while taking data!')
            return
        self.Log('WARNING: executing '+script)
        p1 = Popen(['bash',script], stdout=PIPE)
        output = p2.communicate()[0]
        self.Log(output)


class waiter:
    def __init__(self,gm_):
        self.reset()
        self.gm=gm_
        self.dialog=self.gm.get_object("WaitingWindow")
        self.dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)
    def reset(self):
        self.forcewaitexit=False
        self.waitingexit=True
        self.exit_func = None
        self.back_func = None
        self.exit_func_args = []
        self.back_func_args = []
        self.condition = None
    def on_waitbutton1_clicked_(self,*args):
        self.dialog.hide()
        self.waitingexit=False
    def on_waitbutton2_clicked_(self,*args):
        self.dialog.hide()
        self.forcewaitexit=True
    def set_layout(self,message,label1,label2,color=None):
        gtkcolor=None
        if color:
            gtkcolor=gtk.gdk.color_parse(str(color))
        self.gm.get_object('WaitingWindow').modify_bg(gtk.STATE_NORMAL,gtkcolor)
        self.gm.get_object('waitquestion').set_label(str(message))
        if label1:
            self.gm.get_object('waitbutton1').set_label(str(label1))
            self.gm.get_object('waitbutton1').set_sensitive(True)
        else:
            self.gm.get_object('waitbutton1').set_label('')
            self.gm.get_object('waitbutton1').set_sensitive(False)
        if label2:
            self.gm.get_object('waitbutton2').set_label(str(label2))
            self.gm.get_object('waitbutton2').set_sensitive(True)
        else:
            self.gm.get_object('waitbutton2').set_label('')
            self.gm.get_object('waitbutton2').set_sensitive(False)
    def set_condition(self,func,args):
        self.condition = func
        self.conditionargs = args
    def set_exit_func(self,func,args):
        self.exit_func = func
        self.exit_func_args = args
    def set_back_func(self,func,args):
        self.back_func = func
        self.back_func_args = args
    def run(self):
        self.dialog.show()
        gobject.idle_add(self.generalwaitwindow_helper)
    def generalwaitwindow_helper(self):
        isgood = self.forcewaitexit
        if self.condition!=None:
            isgood = (isgood or self.condition(*(self.conditionargs)))
        if isgood:
            self.waitingexit=False
        if self.waitingexit:
            return True
        else:
            if isgood:
                if self.exit_func!=None:
                    self.exit_func(*(self.exit_func_args))
            else:
                if self.back_func!=None:
                    self.back_func(*(self.back_func_args))
            self.dialog.hide()
            return False

class BrowserTab:

    def dropfirst(self,*args):
        args[1](*(args[2:]))
    def myloaduri(self,*args):
        url = args[0].get_text()
        if url.find('://')==-1:
            url = 'http://'+url
        args[1](url)
    def barupdater(self,view,frame,request,action,decision,entry):
        entry.set_text(request.get_uri())

    def destroy(self,wid,nb,tablist,*args):
        nb.remove_page(nb.get_current_page())
        if nb.get_n_pages()==0:
            BrowserTab(nb,tablist)
        tablist.remove(self)
        del self            

    def __init__(self,nb,tablist,address=None):
        
        self.vbox = gtk.VBox()
        self.hbox = gtk.HBox()
        self.closebutton = gtk.Button('Close tab','gtk-close')
        self.backbutton = gtk.Button('Back','gtk-go-back')
        self.refreshbutton = gtk.Button('Refresh','gtk-refresh')
        self.urlentry = gtk.Entry()
        self.newtab = gtk.Button('New tab','gtk-add')

        self.hbox.pack_start(self.closebutton,False,False)
        self.hbox.pack_start(self.backbutton,False,False)
        self.hbox.pack_start(self.urlentry)
        self.hbox.pack_start(self.refreshbutton,False,False)
        self.hbox.pack_start(self.newtab,False,False)
        self.vbox.pack_start(self.hbox,False,False)

        self.scrw = gtk.ScrolledWindow()
        self.scrw.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        self.wv = webkit.WebView()
        self.scrw.add_with_viewport(self.wv)
        self.vbox.pack_start(self.scrw)

        self.backbutton.connect('clicked',self.dropfirst,self.wv.go_back)
        self.closebutton.connect('clicked',self.destroy,nb,tablist)
        self.urlentry.connect('activate',self.myloaduri,self.wv.load_uri)
        self.refreshbutton.connect('clicked',self.dropfirst,self.wv.reload)
        self.newtab.connect('clicked',self.dropfirst,BrowserTab,nb,tablist)
        self.wv.connect('navigation-policy-decision-requested',self.barupdater,self.urlentry)

        self.lab = gtk.Label('Browser')
        nb.append_page(self.vbox,self.lab)
        nb.show_all()
        nb.set_current_page(-1)
        tablist.append(self)

        if address:
            self.wv.load_uri(address)


# MAIN
if __name__ == "__main__":
    mygui = H4GtkGui()
    gtk.settings_get_default().props.gtk_button_images = True
    gtk.main()



