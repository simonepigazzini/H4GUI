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

