#!/usr/bin/env python

import pygtk
pygtk.require('2.0')
import gtk
import gobject
from datetime import datetime
from zmq import *
from h4dbclasses import *

class H4GtkGui:

    def configure(self):

        self.debug=False

        self.pubsocket_bind_address='tcp://*:6888'

        self.nodes=[
            ('RC','tcp://pcethtb2.cern.ch:6002'),
            ('RO1','tcp://localhost:6901'),
            ('RO2','tcp://localhost:6902'),
            ('EVTB','tcp://localhost:6903')
            ]

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
            'error': 'GUI_ERROR'
            }
        self.rsdict={ #imported from H4DAQ/interface/Command.hpp 
            0:'START',
            1:'INIT',
            2:'INITIALIZED',
            3:'BEGINSPILL',
            4:'CLEARED',
            5:'CLEARBUSY',
            6:'WAITTRIG',
            7:'READ',
            8:'ENDSPILL',
            9:'RECVBUFFER',
            10:'SENTBUFFER',
            11:'SPILLCOMPLETED',
            12:'BYE',
            13:'ERROR'
            }
        self.remotestatus_juststarted=0
        self.remotestatus_betweenruns=2
        self.remotestatus_betweenspills=3
        self.remotestatus_restartafterpause=4
        self.remotestatuses_datataking=[5,6,7]
        self.remotestatuses_running=[3,4,5,6,7,8,9,10,11]
        self.remotestatuses_stopped=[0,1,2,12]

    def __init__(self):

        self.configure()

        self.status={
            'localstatus': 'STARTED',
            'runnumber': 0,
            'spillnumber': 0,
            'evinrun': 0,
            'evinspill': 0,
            'lastbuiltspill':0
            }
        self.remotestatus={}
        self.remotestatuscode={}
        self.remoterunnr={}
        self.remotespillnr={}
        for node,addr in self.nodes:
            self.remotestatuscode[node]=self.remotestatus_juststarted
            self.remotestatus[node]=self.rsdict[self.remotestatuscode[node]]
            self.remoterunnr[node]=0
            self.remotespillnr[node]=0
        self.allbuttons=['createbutton','startbutton','pausebutton','stopbutton']
        self.allrunblock=['runtypebutton','runnumberspinbutton','tablexspinbutton','tableyspinbutton',
                          'runstarttext','runstoptext','runtext','daqstringentry','pedfrequencyspinbutton',
                          'beamparticlebox','beamenergyentry','beamsigmaxentry','beamsigmayentry',
                          'beamintensityentry','beamtiltxentry','beamtiltyentry']

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
        self.keepalivecounter={}
        for node,addr in self.nodes:
            self.sub[node] = self.context.socket(SUB)
            self.sub[node].connect(addr)
            self.sub[node].setsockopt(SUBSCRIBE,'')
            self.poller.register(self.sub[node],POLLIN)
            self.keepalivecounter[node]=True
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
                self.keepalivecounter[node]=True
                self.proc_message(node,message)
        return True
    def check_keepalive(self):
        for node in self.sub.keys():
            if (self.keepalivecounter[node]==False):
                self.set_alarm('Lost connection with '+str(node),1)
            else:
                self.unset_alarm('Lost connection with '+str(node))
            self.keepalivecounter[node]=False
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
            except ValueError:
                self.Log('Impossible to interpret message: <'+msg+'>')
                True
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

# RUN STATUS AND COUNTERS, GUI ELEMENTS SENSITIVITY AND MANIPULATION
    def update_gui_statuscounters(self):
        self.status['runnumber']=self.remoterunnr['RC']
        self.status['spillnumber']=self.remotespillnr['RC']
        if not self.gm.get_object('runstatuslabel').get_text()==self.remotestatus['RC']:
            self.gm.get_object('runstatuslabel').set_text(self.remotestatus['RC'])
            self.flash_widget(self.gm.get_object('runstatusbox'),'yellow')
        self.gm.get_object('ro1label').set_text( str(' ').join(('Data readout unit 1:',self.remotestatus['RO1'])))
        self.gm.get_object('ro2label').set_text( str(' ').join(('Data readout unit 2:',self.remotestatus['RO2'])))
        self.gm.get_object('evtblabel').set_text(str(' ').join(('Event builder:',self.remotestatus['EVTB'])))
        self.gm.get_object('runnumberlabel').set_text(str().join(['Run number: ',str(self.status['runnumber'])]))
        self.gm.get_object('spillnumberlabel').set_text(str().join(['Spill number: ',str(self.status['spillnumber'])]))
        self.gm.get_object('evinrunlabel').set_text(str().join(['Total #events in run: ',str(self.status['evinrun'])]))
        self.gm.get_object('evinspilllabel').set_text(str().join(['Nr. of events in spill ',str(self.status['lastbuiltspill']),': ',str(self.status['evinspill'])]))
        return True
    def set_sens(self,wids,value):
        for wid in wids:
            if not self.gm.get_object(str(wid)):
                self.Log(str().join(('ERROR ',wid)))
            self.gm.get_object(str(wid)).set_sensitive(value)
    def set_label(self,wid,value):
        self.gm.get_object(str(wid)).set_label(str(value))
    def set_gtkcombobox_entry(self,button,newentry):
        for index in xrange(len(button.get_model())):
            if newentry==button.get_model()[index][0]:
                button.set_active(index)
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
        self.init_gtkcombobox(self.gm.get_object('daqstringentry'),['DAQCONF1','DAQCONF2'])
        self.init_gtkcombobox(self.gm.get_object('beamparticlebox'),['Electron','Positron','Pion','Muon'])
        gobject.idle_add(self.define_sensitivity_runtext)
    def read_gtkcombobox_status(self,button):
        tree_iter = button.get_active_iter()
        thisentry=None
        if tree_iter:
            model = button.get_model()
            thisentry = model[tree_iter][0]
        return thisentry
    def read_gtkcomboboxentry_string(self,button):
        return str(button.child.get_text())
    def set_gtkcombobox_options(self,button,mylist):
        entrylist = gtk.ListStore(str)
        for entry in mylist:
            entrylist.append([entry])
        button.set_model(entrylist)
        button.set_active(-1)
    def update_comboboxentry(self,button):
        output = self.read_gtkcombobox_status(button)
        if output:
            newtext=str(output)
            button.child.set_text(newtext)
    def init_gtkcombobox(self,button,mylist):
        self.set_gtkcombobox_options(button,mylist) 
        renderer_text = gtk.CellRendererText()
        button.pack_start(renderer_text, True)
        button.add_attribute(renderer_text, "text", 0)       
    def set_gtkspinbutton(self,button,value):
        button.set_value(value or 0)
    def set_gtkentry(self,button,value):
        out = ''
        if value:
            out=str(value)
        button.set_text(out)
    def get_text_from_textbuffer(self,bufname):
        buf=self.gm.get_object(bufname)
        out=buf.get_text(buf.get_start_iter(),buf.get_end_iter())
        return out
    def define_sensitivity_runtext(self):
        if self.status['localstatus'] in ['STARTED','PAUSED']:
            if self.confblock.r['run_number']==self.status['runnumber']:
                self.gm.get_object('runtext').set_sensitive(True)
            else:
                self.gm.get_object('runtext').set_sensitive(False)
        return True

# ALARMS
    def Log(self,mytext):
        mybuffer=self.gm.get_object('rclogbuffer')
        mybuffer.insert(mybuffer.get_end_iter(),str(mytext)+'\n')
    def set_alarm(self,msg='Error_Generic',level=1):        
        self.alarms[msg]=level
        if level==0:
            self.unset_alarm(msg)
    def unset_alarm(self,msg):
        self.alarms.pop(msg,None)
    def clear_alarms(self):
        self.alarms.clear()
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
            if mylevel>=2:
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
            self.gotostatus('RUNNING')
    def createrun(self):
        if self.remotestatuscode['RC']!=self.remotestatus_betweenruns:
            return
        if self.status['localstatus']=='CREATED':
            self.gotostatus('INIT')
            return
        self.get_gui_confblock()
        self.confblock = self.confdb.read_from_db(runnr=self.confblock.r['run_number'])
        self.confblock.show()
        self.gotostatus('CREATED')
        self.confblock.r['run_end_user_comment']=''
        self.confblock.r['run_starttime']=''
        self.confblock.r['run_endtime']=''
        self.confblock.r['run_comment']=''
        self.update_gui_confblock()
    def startrun(self):
        if self.remotestatuscode['RC']!=self.remotestatus_betweenruns:
            return
        self.get_gui_confblock()
        self.confblock.r['run_starttime']=str(datetime.utcnow().isoformat())
        self.confblock=self.confdb.add_into_db(self.confblock)
        self.confblock.show()
        self.update_gui_confblock()
        self.Log('Sending START for run '+str(self.confblock.r['run_number']))
        self.send_message(str(' ').join([str(self.gui_out_messages['startrun']),str(self.confblock.r['run_number']),str(self.confblock.t['run_type_description']),str(self.confblock.t['ped_frequency'])]))
        message = 'Waiting for transition to '+str('|').join(self.remotestatuses_running)
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Go back','Force transition')
        self.mywaiter.set_condition(self.table_is_ok_and_remotestatus,[newx,newy,self.remotestatuses_running])
        self.mywaiter.set_exit_function(self.gotostatus,['RUNNING'])
        self.mywaiter.run()
    def pauserun(self): # IMPL DEBUG
        if not self.status['localstatus']=='PAUSED':
            self.Log('Sending PAUSE for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['pauserun'])
            self.mywaiter.reset()
            self.mywaiter.set_layout(message,'Go back','Force transition')
            self.mywaiter.set_condition(self.remstatus_is,[[self.remotestatus_betweenspills]])
            self.mywaiter.set_exit_function(self.gotostatus,['PAUSED'])
#            mywaiter.set_back_function(self.gotostatus,'PAUSED')
            self.mywaiter.run()
        else:
            self.Log('Sending RESUME for run '+str(self.confblock.r['run_number']))
            self.send_message(self.gui_out_messages['resumerun'])
            self.mywaiter.reset()
            self.mywaiter.set_layout(message,'Go back','Force transition')
            self.mywaiter.set_condition(self.remstatus_is,[[self.remotestatus_restartafterpause]])
            self.mywaiter.set_exit_function(self.gotostatus,['RUNNING'])
#            mywaiter.set_back_function(self.gotostatus,'RUNNING')
            self.mywaiter.run()
    def remstatus_is(self,whichstatus):
        return (self.remotestatuscode['RC'] in whichstatus)
    def stoprun(self):
        self.Log('Sending STOP for run '+str(self.confblock.r['run_number']))
        self.send_message(self.gui_out_messages['stoprun'])
        self.gui_go_to_runnr(self.status['runnumber'])
        self.confblock.r['run_endtime']=str(datetime.utcnow().isoformat())
        mywaiter.reset()
        mywaiter.set_layout(message,'Go back','Force transition')
        mywaiter.set_condition(self.remstatus_is,[[self.remotestatus_betweenruns]])
        mywaiter.set_exit_function(self.gotostatus,['STOPPED'])
        mywaiter.run()
    def closerun(self):
        self.get_gui_confblock()
        self.confblock=self.confdb.update_to_db(self.confblock)
        self.gotostatus('INIT')

# PROCESS SIGNALS
    def on_buttonquit_clicked(self,*args):
        self.mywaiter.reset()
        self.mywaiter.set_layout('Do you want to quit the GUI?','Cancel','Yes')
        self.mywaiter.set_exit_func(gtk.main_quit,[])
        self.mywaiter.run()        
    def on_quitbuttonRC_clicked(self,*args):
        self.Log("Request to quit run controller from GUI user")
#        self.askconfirmation('Do you really want to quit the DAQ?',self.send_message,self.gui_out_messages['die']) #IMPL
    def on_createbutton_clicked(self,*args):
        self.createrun()
    def on_startbutton_clicked(self,*args):
        message = 'Do you want to start?'
        self.mywaiter.reset()
        self.mywaiter.set_layout(message,'Cancel','Start')
        self.mywaiter.set_exit_func(self.startrun,[])
        self.mywaiter.run()
#        self.askconfirmation('Do you want to start?',self.startrun) #IMPL
    def on_pausebutton_clicked(self,*args):
        return
#        self.askconfirmation('Do you want to pause?',self.pauserun) #IMPL
    def on_stopbutton_clicked(self,*args):
        if self.status['localstatus']=='STOPPED':
            self.closerun()
            return
        else:
            self.askconfirmation('Do you want to stop?',self.stoprun)
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
    def on_daqstringentry_changed(self,button):
        self.update_comboboxentry(button)
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
        self.set_gtkentry(self.gm.get_object('runstarttext').child,(self.confblock.r['run_start_user_comment']))
        self.set_gtkentry(self.gm.get_object('runstoptext').child,(self.confblock.r['run_end_user_comment']))
        self.set_gtkentry(self.gm.get_object('daqstringentry').child,(self.confblock.d['daq_type_description']))
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
        self.confblock.r['run_start_user_comment']=self.gm.get_object('runstarttext').child.get_text()
        self.confblock.r['run_end_user_comment']=self.gm.get_object('runstoptext').child.get_text()
        self.confblock.t['run_type_description']=self.read_gtkcombobox_status(self.gm.get_object('runtypebutton'))
        self.confblock.t['ped_frequency']         =self.gm.get_object('pedfrequencyspinbutton').get_value()
        self.confblock.d['daq_type_description']=self.gm.get_object('daqstringentry').child.get_text()
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
        self.Log(str().join(['Local status:',self.status['localstatus'],'->',status]))
        if status=='INIT':
            if self.status['localstatus']=='CREATED':
                self.confblock=self.confdb.read_from_db(runnr=self.run_temp_)
            else:
                self.confblock=self.confdb.read_from_db(runnr=self.confdb.get_highest_run_number())
            self.update_gui_confblock()
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['createbutton'],True)
            self.set_label('stopbutton','STOP RUN')
            self.set_label('createbutton','CREATE RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)
        if status=='CREATED':
            self.run_temp_=self.confblock.r['run_number']
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,True)
            self.set_sens(['runnumberspinbutton','runstoptext'],False)
            self.set_sens(['createbutton','startbutton'],True)
            self.set_label('createbutton','CANCEL')
            self.gm.get_object('runnumberspinbutton').set_visibility(False)
        if status=='STARTED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['pausebutton','stopbutton'],True)
            self.set_sens(['runtext'],True)
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('createbutton','CREATE RUN')
            self.gm.get_object('runnumberspinbutton').set_visibility(True)
        if status=='PAUSED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['runnumberspinbutton'],True)
            self.set_sens(['pausebutton','stopbutton'],True)
            self.set_sens(['runtext'],True)
            self.set_label('pausebutton','RESUME RUN')
        if status=='STOPPED':
            self.set_sens(self.allbuttons,False)
            self.set_sens(self.allrunblock,False)
            self.set_sens(['stopbutton'],True)
            self.set_sens(['runtext'],True)
            self.set_sens(['runstoptext'],True)
            self.set_label('pausebutton','PAUSE RUN')
            self.set_label('stopbutton','CLOSE RUN')
        self.status['localstatus']=status


# TABLE POSITION HANDLING
    def get_table_position(self):
        # IMPL
        #        return (x,y,status)
        return (float(0),float(0),'STOPPED')
    def set_table_position(self,newx,newy):
        if self.get_table_position()==(newx,newy,'STOPPED'):
            return
        message='Waiting for table to move to '+str(newx)+' '+str(newy)
        gobject.idle_add(self.generalwaitwindow,message,None,'Force ACK table moving',self.get_table_position(),(newx,newy,'STOPPED'))
    def table_is_ok_and_remotestatus(self,newx,newy,newstatus,gotostatus):
        return (self.get_table_position==(newx,newy,'STOPPED') and newstatus==self.remotestatuscode['RC'])

    def on_waitbutton1_clicked(self,*args):
        self.mywaiter.on_waitbutton1_clicked_(args)
    def on_waitbutton2_clicked(self,*args):
        self.mywaiter.on_waitbutton2_clicked_(args)



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
    def set_layout(self,message,label1,label2):
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
            isgood = (isgood or self.condition(*(self.condition_args)))
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
            return False











# MAIN
if __name__ == "__main__":
    mygui = H4GtkGui()
    gtk.main()



