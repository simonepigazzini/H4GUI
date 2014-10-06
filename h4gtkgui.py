#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pygst
import gst
import datetime
from zmq import *
from h4dbclasses import *

class H4GtkGui:

    def configure(self):

        self.debug=False
        self.activatesounds=False

        self.pubsocket_bind_address='tcp://*:5566'

        self.nodes=[
            ('RC','tcp://pcethtb2.cern.ch:6002'),
            ('RO1','tcp://pcethtb1.cern.ch:6002'),
#            ('RO2','tcp://localhost:6902'),
            ('EVTB','tcp://pcethtb2.cern.ch:6502'),
#            ('table','tcp://cms-h4-01:6999')
            ]

        self.keepalive={}
        self.keepalive['RC']=True
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
            'tablepos': 'TABLE_IS'
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
        self.remotestatuses_datataking=[6,7,8]
        self.remotestatuses_running=[4,5,6,7,8,9,10,11,12]
        self.remotestatuses_stopped=[0,1,2,13,14]

    def __init__(self):

        self.configure()

        self.status={
            'localstatus': 'STARTED',
            'runnumber': 0,
            'spillnumber': 0,
            'evinrun': 0,
            'evinspill': 0,
            'table_status': (0,0,'TAB_DONE')
            }
        self.remotestatus={}
        self.remotestatuscode={}
        self.remoterunnr={}
        self.remotespillnr={}
        self.remoteevinspill={}
        for node,addr in self.nodes:
            self.remotestatuscode[node]=self.remotestatus_juststarted
            self.remotestatus[node]=self.rsdict[self.remotestatuscode[node]]
            self.remoterunnr[node]=0
            self.remotespillnr[node]=0
            self.remoteevinspill[node]=0
        self.localspilldb={}
        self.remoteispaused=False
        self.allbuttons=['createbutton','startbutton','pausebutton','stopbutton']
        self.allrunblock=['runtypebutton','runnumberspinbutton','tablexspinbutton','tableyspinbutton',
                          'runstarttext','runstoptext','runtext','daqstringentry','pedfrequencyspinbutton',
                          'beamparticlebox','beamenergyentry','beamsigmaxentry','beamsigmayentry',
                          'beamintensityentry','beamtiltxentry','beamtiltyentry']
        self.playlevel=0
        self.global_veto_alarm=False
        self.autostop_max_events=-1

        gtk.rc_parse('.h4gtkrc')
        self.gm = gtk.Builder()
        self.gm.add_from_file("H4GtkGui.glade")
        self.gm.connect_signals(self)
        self.mainWindow = self.gm.get_object("MainWindow")
        self.mainWindow.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        self.set_spinbuttons_properties()

        self.confdb = DataTakingConfigHandler()
        self.confblock = DataTakingConfig()
        self.confdb.confblock = self.confblock
        self.start_network()

        self.gotostatus('INIT')
        self.mainWindow.show()

        self.mywaiter = waiter(self.gm)


        self.aliveblinkstatus=False
        gobject.timeout_add(1000,self.change_color_blinkingalive)
        self.alarms={}
        self.alarmblinkstatus=False
        gobject.timeout_add(500,self.check_alarm)

        gobject.idle_add(self.update_gui_statuscounters)


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
        gobject.timeout_add(1000,self.check_keepalive)
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
        parts = msg.split(' ')
        if len(parts)<1:
            return
        tit = parts[0]
        parts = parts[1:]
        if tit==self.gui_in_messages['status']:
            oldstatus=self.remotestatus[node]
            try:
                if len(parts)>0:
                    self.remotestatuscode[node]=int(parts[0])
                if len(parts)>1:
                    self.remoterunnr[node]=int(parts[1])
                if len(parts)>2:
                    self.remotespillnr[node]=int(parts[2])
                if len(parts)>3:
                    self.remoteevinspill[node]=int(parts[3])
                if len(parts)>4 and str(parts[4])=='PAUSED':
                    self.remoteispaused=True
                else:
                    self.remoteispaused=False
            except ValueError:
                self.Log('Impossible to interpret message: <'+msg+'>')
                True
            if node=='RC':
                if self.remotestatuscode[node]>=5 and self.remotestatuscode[node]<=11:
                    self.localspilldb[self.remotespillnr[node]]=self.remoteevinspill[node]
            self.remotestatus[node]=self.rsdict[self.remotestatuscode[node]]
            if self.remotestatuscode[node] in self.remotestatuses_datataking:
                self.remotestatus[node]='DATATAKING'
            self.update_gui_statuscounters()
            if not oldstatus==self.remotestatus[node]:
                self.Log('Status change for '+str(node)+': '+str(oldstatus)+' -> '+str(self.remotestatus[node]))
                if node=='RC':
                    self.processrccommand(self.remotestatus[node])
        elif tit=='GUI_LOG':
            self.Log(str().join(['[',str(node),']: '].extend(parts)))
        elif tit=='GUI_ERROR':
            level = int(parts[0])
            parts=parts[1:]
            message=str().join(['[',str(node),' ERROR]: ']).extend(parts)
            self.Log(message)
            self.set_alarm(message,level)
        elif tit=='GUI_SPS':
            self.flash_sps(str(parts[0]))
        elif tit==self.gui_in_messages['tablepos']:
            self.status['table_position']=(float(parts[0]),float(parts[1]),str(parts[2]))
            if node in self.keep.keys():
                self.keepalive['table']=True

# RUN STATUS AND COUNTERS, GUI ELEMENTS SENSITIVITY AND MANIPULATION
    def update_gui_statuscounters(self):
        self.status['runnumber']=self.remoterunnr['RC']
        self.status['spillnumber']=self.remotespillnr['RC']
        self.status['evinrun']=sum(self.localspilldb.values())
        self.status['evinspill']=self.remoteevinspill['RC']
        if not self.gm.get_object('runstatuslabel').get_text().split(' ')[-1]==self.remotestatus['RC']:
            self.gm.get_object('runstatuslabel').set_text(str(' ').join(('Run controller:',self.remotestatus['RC'])))
            self.flash_widget(self.gm.get_object('runstatusbox'),'green')
        if 'RO1' in [x[0] for x in self.nodes]:
            self.gm.get_object('ro1label').set_text( str(' ').join(('Data readout unit 1:',self.remotestatus['RO1'])))
        if 'RO2' in [x[0] for x in self.nodes]:
            self.gm.get_object('ro2label').set_text( str(' ').join(('Data readout unit 2:',self.remotestatus['RO2'])))
        if 'EVTB' in [x[0] for x in self.nodes]:
            self.gm.get_object('evtblabel').set_text(str(' ').join(('Event builder:',self.remotestatus['EVTB'])))
        self.gm.get_object('runnumberlabel').set_text(str().join(['Run number: ',str(self.status['runnumber'])]))
        self.gm.get_object('spillnumberlabel').set_text(str().join(['Spill number: ',str(self.status['spillnumber'])]))
        self.gm.get_object('evinrunlabel').set_text(str().join(['Total #events in run: ',str(self.status['evinrun'])]))
        self.gm.get_object('evinspilllabel').set_text(str().join(['Nr. of events in spill: ',str(self.status['evinspill'])]))
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
        self.init_gtkcombobox(self.gm.get_object('runtypebutton'),['PHYSICS','PEDESTAL'])
        self.init_gtkcombobox(self.gm.get_object('beamparticlebox'),['Electron','Positron','Pion','Muon'])
        gobject.idle_add(self.define_sensitivity_runtext)

    def define_sensitivity_runtext(self):
        if self.status['localstatus'] in ['STARTED','PAUSED','STOPPED']:
            if self.confblock.r['run_number']==self.status['runnumber']:
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
        if value:
            out=str(value)
        button.set_text(out)
    def get_gtkentry(self,button):
        return button.get(text)

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
    def processrccommand(self,command):
        rc=self.remotestatuscode['RC']
        if rc in self.remotestatuses_stopped:
            if self.status['localstatus'] in ['RUNNING','PAUSED']:
                self.gotostatus('STOPPED')
            else:
                self.gotostatus('INIT')
        else:
            if not self.remoteispaused:
                self.gotostatus('RUNNING')
            else:
                self.gotostatus('PAUSED')
    def remotecheckpaused(self,whatiwant):
        return (self.remoteispaused==whatiwant)

    def createrun(self):
        if self.status['localstatus']=='CREATED':
            self.gotostatus('INIT')
            return
        self.get_gui_confblock()
        self.confblock = self.confdb.read_from_db(runnr=self.confblock.r['run_number'])
        self.gotostatus('CREATED')
        self.confblock.r['run_end_user_comment']=''
        self.confblock.r['run_starttime']=''
        self.confblock.r['run_endtime']=''
        self.confblock.r['run_comment']=''
        self.update_gui_confblock()

    def startrun(self):
        for node,val in self.remotestatuscode.iteritems():
            if node in ['RC','RO1','RO2','EVTB']:
                if val!=self.remotestatus_betweenruns:
                    self.Log('Node %s not ready for STARTRUN'%(str(node),))
                    return
        self.get_gui_confblock()
        self.status['evinrun']=0
        self.localspilldb.clear()
        self.confblock.r['run_starttime']=str(datetime.datetime.utcnow().isoformat())
        self.confblock=self.confdb.add_into_db(self.confblock)
        self.update_gui_confblock()
        self.Log('Sending START for run '+str(self.confblock.r['run_number']))
        self.send_message(str(' ').join([str(self.gui_out_messages['startrun']),str(self.confblock.r['run_number']),str(self.confblock.t['run_type_description']),str(self.confblock.t['ped_frequency'])]))        
        self.mywaiter.reset()
        self.mywaiter.set_layout('Waiting for transition to running status','Go back','Force transition')
        self.mywaiter.set_condition(self.remstatus_is,[self.remotestatuses_running])
        self.mywaiter.set_exit_func(self.gotostatus,['RUNNING'])
        self.mywaiter.run()
 
    def pauserun(self):
        if self.status['localstatus']=='RUNNING':
            self.Log('Sending PAUSE for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['pauserun'])
            self.mywaiter.reset()
            self.mywaiter.set_layout('Do you want to pause?','Go back','Force transition')
            self.mywaiter.set_condition(self.remotecheckpaused,[True])
            self.mywaiter.set_exit_func(self.gotostatus,['PAUSED'])
            self.mywaiter.set_back_func(self.gotostatus,['RUNNING'])
            self.mywaiter.run()
        else:
            self.Log('Sending RESUME for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['restartrun'])
            self.mywaiter.reset()
            self.mywaiter.set_layout('Do you want to resume?','Go back','Force transition')
            self.mywaiter.set_condition(self.remotecheckpaused,[False])
            self.mywaiter.set_exit_func(self.gotostatus,['RUNNING'])
            self.mywaiter.set_back_func(self.gotostatus,['PAUSED'])
            self.mywaiter.run()

    def remstatus_is(self,whichstatus):
        return (self.remotestatuscode['RC'] in whichstatus)

    def stoprun(self):
        self.Log('Sending STOP for run '+str(self.confblock.r['run_number']))
        self.send_message(self.gui_out_messages['stoprun'])
        self.gui_go_to_runnr(self.status['runnumber'])
        self.confblock.r['run_endtime']=str(datetime.datetime.utcnow().isoformat())
        self.mywaiter.reset()
        self.mywaiter.set_layout('Waiting for run to stop','Go back','Force transition')
        self.mywaiter.set_condition(self.remstatus_is,[[self.remotestatus_betweenruns]])
        self.mywaiter.set_exit_func(self.gotostatus,['STOPPED'])
        self.mywaiter.run()

    def closerun(self):
        self.get_gui_confblock()
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
        if not self.table_is_ok(self.confblock.r['table_horizontal_position'],self.confblock.r['table_vertical_position']):
            message+=' <b>TABLE WILL BE MOVED TO X=%s, Y=%s</b>'%(str(self.confblock.r['table_horizontal_position']),str(self.confblock.r['table_vertical_position']),)
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Cancel','Start',color='green')
        self.mywaiter.set_exit_func(self.set_table_position,[self.confblock.r['table_horizontal_position'],self.confblock.r['table_vertical_position'],self.startrun])
        self.mywaiter.run()

    def on_pausebutton_clicked(self,*args):
        if self.status['localstatus']=='RUNNING':
            message = 'Do you want to pause?'
        elif self.status['localstatus']=='PAUSED':
            message = 'Do you want to resume?'
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Cancel','Yes')
        self.mywaiter.set_exit_func(self.pauserun,[])
        self.mywaiter.run()
    def on_stopbutton_clicked(self,*args):
        if self.status['localstatus']=='STOPPED':
            self.closerun()
        else:
            self.mywaiter.reset()
            self.mywaiter.set_layout('Do you want to stop?','Cancel','Yes',color='orange')
            self.mywaiter.set_exit_func(self.stoprun,[])
            self.mywaiter.run()
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
            self.set_sens(['createbutton','startbutton'],True)
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
    def set_table_position(self,newx,newy,exitfunc=None):
        if self.get_table_position()[2]!='TAB_DONE':
            self.Log('ERROR: trying to move table while table is not stopped')
            return False
        if self.status['table_status']!=(newx,newy,'TAB_DONE'):
            self.send_message('SET_TABLE_POSITION %s %s' % (newx,newy,))
        message='Waiting for table to move to '+str(newx)+' '+str(newy)
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,None,'Force ACK table moving')
        self.mywaiter.set_condition(self.table_is_ok,[newx,newy])
        if exitfunc:
            self.mywaiter.set_exit_func(exitfunc,[])
        self.mywaiter.run()
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
        if self.global_veto_alarm:
            self.clear_alarms()

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
    def on_eventbox_image_button_press_event(self,mybox,*args):
        self.show_plot_display(self.imagenames.get(mybox.get_child().get_name(),None))
    def show_plot_display(self,imagefile=None):
        self.gm.get_object('imagelargedisplay').set_from_file(imagefile)
        self.gm.get_object('PlotDisplayWindow').show()
    def on_imageeventbox_button_press_event(self,*args):
        self.gm.get_object('PlotDisplayWindow').hide()
            
    def on_maxevtoggle_toggled(self,button,*args):
        if button.get_active():
            self.autostop_max_events=int(self.gm.get_object('maxeventry').get_text())
        else:
            self.autostop_max_events=-1

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

# MAIN
if __name__ == "__main__":
    mygui = H4GtkGui()
    gtk.main()



