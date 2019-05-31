import wx, ifigure, os, sys
import pickle as pickle
import ifigure.server
import numpy as np

import ifigure.utils.debug as debug
from ifigure.mto.treedict import TreeDict
from ifigure.utils.cbook import text_repr
## shell_variable
EvtShellEnter= wx.NewEventType()
EVT_SHELL_ENTER = wx.PyEventBinder(EvtShellEnter, 1)

try:
   from ifigure.version import ifig_version
except:
   ifig_version = 'dev'

dprint1, dprint2, dprint3 = debug.init_dprints('SimpleShell')

import wx.py.shell #(wx4 removed this) wx.lib.shell
from os.path import expanduser, abspath

from ifigure.utils.wx3to4 import isWX3

import time
import _thread
from threading import Timer, Thread
try:
    from queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x
    
ON_POSIX = 'posix' in sys.builtin_module_names

sx_print_to_consol = False

def enqueue_output(p, queue):
    while True:
        line = p.stdout.readline()
        queue.put(line)
        if p.poll() is not None: 
           queue.put(p.stdout.read())
           break
    queue.put('process terminated')
    
def run_in_thread(p):
    q = Queue()
    t = Thread(target=enqueue_output, args=(p, q))
    t.daemon = True # thread dies with the program
    t.start()

    lines = ["\n"]
    line = ''
    alive = True
    app = wx.GetApp().TopWindow
    if sx_print_to_consol:
        write_cmd = app.proj_tree_viewer.consol.log.AppendText
    else:
        write_cmd = app.shell.WriteTextAndPrompt
    while True:
        time.sleep(0.01)                
        try:  line = q.get_nowait() # or q.get(timeout=.1)
        except Empty:
            if len(lines) != 0:
               wx.CallAfter(write_cmd, ''.join(lines))                   
            lines = []
        except:
            import traceback
            traceback.print_exc()
            break
        else: # got line
            lines.append(line)
        if line.startswith('process terminated'):
            if len(lines) > 1:
               wx.CallAfter(write_cmd, ''.join(lines[:-1]))                                  
            break
    return

def sx(strin = ''):
    if strin == '': return
    if strin.startswith('cd '):
        dest =strin[3:] 
        dest = abspath(expanduser(dest))
        os.chdir(dest)
        txt = os.getcwd()    
    else:
        import subprocess as sp
        p = sp.Popen(strin, shell = True, stdout=sp.PIPE , stderr=sp.STDOUT)
        t = Thread(target=run_in_thread, args = (p,))
        t.daemon = True # thread dies with the program
        t.start()
        #run_in_thread(p)           
        #txt = ''.join(p.stdout.readlines())
class ShellBase(wx.py.shell.Shell):
    def setBuiltinKeywords(self):
        '''
        this overwrite the origial setBuiltinKeywords
        '''
        import builtins
        builtins.exit = builtins.quit = \
             self.quit
        
    def OnKeyDown(self, evt):

       if evt.GetKeyCode()==wx.WXK_UP:
          self.OnHistoryReplace(1)
          return
       if evt.GetKeyCode()==wx.WXK_DOWN:
          self.OnHistoryReplace(-1)
          return

       if hasattr(evt, 'RawControlDown'):
           mod =(evt.RawControlDown()+ 
                 evt.AltDown()*2+
                 evt.ShiftDown()*4+
                 evt.MetaDown()*8)
       else:
           mod =(evt.ControlDown()+ 
                 evt.AltDown()*2+
                 evt.ShiftDown()*4+
                 evt.MetaDown()*8)
           
       if evt.GetKeyCode() == 78 and mod==1:  #control + N (next command)
#          self.OnHistoryReplace(-1)
          self.LineDown()
          return 
       if evt.GetKeyCode() == 80 and mod==1:  #ctrl + P (prev command)
#          self.OnHistoryReplace(1)
          self.LineUp()
          return 
       if evt.GetKeyCode() == 68 and mod==1:  #ctrl + D (delete)
          self.CharRight()
          self.DeleteBackNotLine()
          self.st_flag = True
          return 
       if evt.GetKeyCode() == 70 and mod==1:  #ctrl + F (forward)
          self.CharRight()
          return 
       if evt.GetKeyCode() == 66 and mod==1:  #ctrol + B (back)
          self.CharLeft()
          return 
       if evt.GetKeyCode() == 89 and mod==1:  #ctrl + Y (paste)
          self.Paste()
          self.st_flag = True
          return
       if evt.GetKeyCode() == 87 and mod==1:  #ctrl + W (cut)
          self.Cut()
          self.st_flag = True
          return
       if evt.GetKeyCode() == 87 and mod==2:  #alt + W (copy)
          self.Copy()
          self.st_flag = True
          return
       if evt.GetKeyCode() == 90 and mod==1:  #ctrl + Z (cut)
          self.st_flag = True
          import ifigure.events
          ifigure.events.SendUndoEvent(self.lvar["proj"], w=self)
          return
       if evt.GetKeyCode() == 69 and mod==1:  #ctrl + E (end of line)
          self.LineEnd()
          return 
       if evt.GetKeyCode() == 75 and mod==1:  #ctrl + K (cut the rest)
          self.LineEndExtend()
          self.Cut()
          self.st_flag = True
          return 
       if evt.GetKeyCode() == 65 and mod==1:  #ctrl + A (beginning)
          self.Home()
          self.CharRight()
          self.CharRight()
          self.CharRight()
          self.CharRight()
          return 

       if evt.GetKeyCode() == wx.WXK_RETURN:
           self.st_flag = True

       if (evt.ControlDown() == False and
           evt.AltDown() == False  and
           evt.MetaDown() == False and
           evt.GetKeyCode() > 31  and
           evt.GetKeyCode() < 127):
           self.st_flag = True
#       print 'setting search text', self.st, self.historyIndex
       super(ShellBase, self).OnKeyDown(evt)
        


class simple_shell_droptarget(wx.TextDropTarget):
    def __init__(self, obj):
        wx.TextDropTarget.__init__(self)
        self.obj=obj

    def OnDropText(self, x, y, indata):
        app=self.obj.GetTopLevelParent()
        txt=app._text_clip
        app._text_clip=''
#        print txt, x, y
        txt.strip('\n\r')
        txt ='\n... '.join(txt.split('\n'))

        pos = self.obj.PositionFromPoint(wx.Point(x,y))
        self.obj.GotoPos(pos)
        self.obj.write(txt)
        self.obj.GotoPos(pos+len(txt))
        if isWX3:
            wx.CallAfter(self.obj.SetSTCFocus, True) 
            wx.CallLater(100, self.obj.SetFocus)
        return True
        #return super(simple_shell_droptarget, self).OnDropText(x, y, indata)

    def OnDragOver(self, x, y, default):
        self.obj.DoDragOver(x, y, default)
        return super(simple_shell_droptarget, self).OnDragOver(x, y, default)

class FakeSimpleShell(wx.Panel):
    def __init__(self, parent=None, *args, **kargs):
       super(FakeSimpleShell, self).__init__(parent, *args, **kargs)
       self.ch = None   ### command history panel

#       self.chistory=collections.deque(maxlen=100)
       self.lvar = {}
       self._no_record = False

    def set_command_history(self, panel):
        self.ch = panel
    def set_proj(self, proj):
       self.lvar["proj"]=proj

    def set_tipw(self, w):
        self.tipw = w                     
    def write_history(self):
       ### save last 300 command history
       from ifigure.ifigure_config import rcdir
       file = os.path.join(rcdir, "command_history")
       f=open(file, 'w')
       f.close()

class SimpleShell(ShellBase):
    #   arrow key up/down are trapped to work as history
    #   this might be possible by configuration file!?
    #
    SHELL=None
    def __init__(self, parent=None):
       self.ch = None   ### command history panel

#       self.chistory=collections.deque(maxlen=100)
       self.lvar = {}
       self._no_record = False

       sc = os.path.join(os.path.dirname(ifigure.__file__), 'startup.py')
       txt = '    --- Welcome to piScope ('+ifig_version+')---'
       super(SimpleShell, self).__init__(parent, 
            locals=self.lvar,
            startupScript=sc, introText=txt)
       if os.getenv('PYTHONSTARTUP') is not None:
           file = os.getenv('PYTHONSTARTUP')
           if os.path.exists(file):
                dprint1('running startup file', file)
                txt = 'Running user startup file '+file
                self.push('print %r' % txt)
                exec(compile(open(file, "rb").read(), file, 'exec'), globals(), self.lvar)

       self.SetDropTarget(simple_shell_droptarget(self))
    
       from ifigure.ifigure_config import rcdir
       file = os.path.join(rcdir, "command_history")
       try:
          f=open(file, 'r')
          self.history=pickle.load(f)
          f.close 
       except Exception:
          print((sys.exc_info()[:2]))
       if self.history[-1] != '#end of history':
          self.history.append('#end of history')

       SimpleShell.SHELL=self
       self.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
       self.Bind(wx.EVT_LEFT_UP, self.onLeftUp)


       self.st = '' ## search txt
       self.st_flag = False

       self._auto_complete = True
    def setBuiltinKeywords(self):
        '''
        this overwrite the origial setBuiltinKeywords
        '''
        import builtins
        builtins.exit = builtins.quit = \
             self.quit
        builtins.sx = sx
    def set_command_history(self, panel):
        self.ch = panel

    def quit(self):
        self.GetTopLevelParent().onQuit()

    def set_proj(self, proj):
       self.lvar["proj"]=proj

    def write_history(self):
       ### save last 300 command history
       from ifigure.ifigure_config import rcdir
       file = os.path.join(rcdir, "command_history")
       f=open(file, 'w')
       h = self.history[0:1000]
       h.append(self.history[-1])
       pickle.dump(h, f)
       f.flush()
       f.close()

    def autoCompleteShow(self, command, offset=0):
        #
        #   add treeobject method to menu
        #   only does autocomplete when caret is at the end of line
        #
        if self._auto_complete:
             if (self.GetCurrentPos() !=
                 self.GetLineEndPosition(self.GetCurrentLine())):
                 return
             """Display auto-completion popup list."""
             self.AutoCompSetAutoHide(self.autoCompleteAutoHide)
             self.AutoCompSetIgnoreCase(self.autoCompleteCaseInsensitive)
             list = self.interp.getAutoCompleteList(command,
                    includeMagic=self.autoCompleteIncludeMagic,
                    includeSingle=self.autoCompleteIncludeSingle,
                    includeDouble=self.autoCompleteIncludeDouble)
             try:
                 self.lvar['_tmp_'] = None                
                 txt ='if isinstance(command, TreeDict): _tmp_='+command+'get_children()'
                 code = compile(txt, '<string>', 'exec')
                 exec(code, globals(), self.lvar)
             except:
                 pass

             if self.lvar['_tmp_'] is not None:
                 list = list + [x[0] for x in self.lvar['_tmp_']]
                 list.sort(lambda x, y: cmp(x.upper(), y.upper()))                  
             if list:
                 options = ' '.join(list)
                 #offset = 0
#                 self.AutoCompSetMaxWidth(3)
                 self.AutoCompShow(offset, options)
           
#            super(SimpleShell, self).autoCompleteShow(command, offset=offset)

    def autoCallTipShow(self, command, insertcalltip = True, forceCallTip = False):
#        super(SimpleShell, self).autoCallTipShow(*args, **kargs)
#        return
        (name, argspec, tip) = self.interp.getCallTip(command)
        self._no_record = False
        self.tipw.update(name, argspec, tip)
        if not self.autoCallTip and not forceCallTip:
            return
        if not self._auto_complete: return
        startpos = self.GetCurrentPos()
        if argspec and insertcalltip and self.callTipInsert:
            self.write(argspec + ')')
            endpos = self.GetCurrentPos()
            self.SetSelection(startpos, endpos)
        return
     
        name = str(command).split('(')[-2]
        s = ''
        for c in name:
            if not c.isalnum() and c != '.' and c != '_': s = c   
        if s != '': name = name.split(s)[-1]

        self._no_record = True
        self.lvar['_tmp_'] = None
        txt = '_tmp_='+name
        try:
           code = compile(txt, '<string>', 'exec')
           exec(code, globals(), self.lvar)
        except:
#           dprint1(txt)
           pass
#        try:
#           self.push(txt, True)
#        except:
#           pass
        self._no_record = False
        if '_tmp_' in self.lvar:
            self.tipw.update(self.lvar['_tmp_'])                    

    def set_tipw(self, w):
        self.tipw = w                     


    def OnHistoryInsert(self, step):
#       print "history insert", step
       super(SimpleShell, self).OnHistoryInsert(step)

       
    def OnHistoryReplace(self, step):
       #print "history replace", step
       if self.st_flag:
           txt, pos=self.GetCurLine()
           self.st = self.getCommand(txt) 
           self.st_flag = False
#       print self.st, self.historyIndex
       if self.st != '':
          tmp_idx = self.historyIndex
          rep = 0
          fail_flag = False
          while (-2 < tmp_idx < len(self.history)):
              rep = rep +step
              tmp_idx = tmp_idx + step            
              try:
                 st = self.history[tmp_idx]
                 if st[0:len(self.st)] == self.st: 
                     break
              except:
                 fail_flag = True
          if not fail_flag:
             super(SimpleShell, self).OnHistoryReplace(rep)
          return
#          while (-2 < self.historyIndex < len(self.history)):
#             super(SimpleShell, self).OnHistoryReplace(step)
#             if self.historyIndex == -1: break
#             if self.historyIndex == len(self.history)-1: break
#             try:
#                 st = self.history[self.historyIndex]
#             except:
#                 print len(self.history), self.historyIndex
#                 import traceback
#                 traceback.print_exc()
#                 break
#             if st[0:len(self.st)] == self.st: 
#                 break
       else:
          super(SimpleShell, self).OnHistoryReplace(step)

    def list_func(self):
        llist = self.list_locals()
        for objname, t in llist:
            if t == 'function': print(objname)

    def get_shellvar(self, name):
        return self.lvar[name]

    def set_shellvar(self, name, value):
        self.lvar[name] = value

    def del_shellvar(self, name):
        del self.lvar[name]

    def has_shellvar(self, name):
        return name in  self.lvar

    def list_locals(self):
        import types

        llist = []
        #        tlist = [(getattr(types, name), 
        #                  str(getattr(types, name)).split("'")[1]) 
        #                  for name in dir(types) if not name.startswith('_')]
        tlist = {getattr(types, name):
                 str(getattr(types, name)).split("'")[1]
                 for name in dir(types) if not name.startswith('_')}
        
        for key in list(self.lvar.keys()):
            if not key.startswith('_'):
                val = self.lvar[key]
                t0 = type(val).__name__
                text = text_repr(val)
                if hasattr(val, 'shape'):
                    llist.append((key, t0, text, str(val.shape)))                
                else:
                    llist.append((key, t0, text, ''))                                       

                       
                #                for t, name in tlist:
                #                    if t0 == t: 
                #                       llist.append((key, name,))
                #                       break
        return llist
       

    def list_module(self):
        pass

    def execute_text(self, text):
        self.Execute(text)
        return

    def execute_and_hide_main(self, text):
        self.Execute(text)
        self.Execute('import wx;wx.GetApp().TopWindow.goto_no_mainwindow()')
        
    def onLeftDown(self, e):
        self.Bind(wx.EVT_MOTION, self.onDragInit)
        e.Skip()

    def onLeftUp(self, e):
        self.Unbind(wx.EVT_MOTION)
        e.Skip()

    def onDragInit(self, e):
        self.Unbind(wx.EVT_MOTION)
        sel = self.GetSelectedText()
        if sel == '':
           e.Skip()
           return
        """ Begin a Drag Operation """
        # Create a Text Data Object, which holds the text that is to be dragged
        #app=wx.GetApp()
        p = self
        while p.GetParent() is not None:
           p = p.GetParent()  
        
        p._text_clip=sel

        tdo = wx.TextDataObject(sel)
        tds = wx.DropSource(self)
        tds.SetData(tdo)
        tds.DoDragDrop(True)
        
    def SendShellEnterEvent(self):
        evt=wx.PyCommandEvent(EvtShellEnter)
        handler=self.GetEventHandler()
        wx.PostEvent(handler, evt)
                
    def addHistory(self, *args, **kargs):
#        print  args, kargs
        if args[0].startswith('sx'):
            args = list(args)
            try:
                args[0] = '!'+args[0].split('"')[1]
            except IndexError:
                return
            args = tuple(args)
        if self._no_record: return
        wx.py.shell.Shell.addHistory(self, *args, **kargs)
#        print wx.GetApp().IsMainLoopRunning()
        if wx.GetApp().IsMainLoopRunning():
           self.SendShellEnterEvent()        
        if self.ch is not None:
           try:
               self.ch.append_text(args[0])
           except UnicodeError:
               print("unicode error")
               pass
           
    def GetContextMenu(self):
        menu = super(SimpleShell, self).GetContextMenu()
        menu.AppendSeparator()
        if self.tipw.IsShown():
            f1 = menu.Append(wx.ID_ANY, "Hide Help")
            self.Bind(wx.EVT_MENU, self.onHideHelp, f1)                    
        else:
            f1 = menu.Append(wx.ID_ANY, "Show Help")
            self.Bind(wx.EVT_MENU, self.onShowHelp, f1)
        if self._auto_complete:
            f2 = menu.Append(wx.ID_ANY, "Auto Complete Off")
            self.Bind(wx.EVT_MENU, self.onAutoCompOff, f2)
        else:
            f2 = menu.Append(wx.ID_ANY, "Auto Complete On")
            self.Bind(wx.EVT_MENU, self.onAutoCompOn, f2)
            
        return menu

    def onShowHelp(self, evt):
        self.tipw.Show()

    def onHideHelp(self, evt):
        self.tipw.Hide()
        
    def onAutoCompOn(self, evt):
        self._auto_complete = True
     
    def onAutoCompOff(self, evt):
        self._auto_complete = False

    def WriteTextAndPrompt(self, txt):
        self.WriteText(txt)
        self.prompt()
       
