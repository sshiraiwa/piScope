import os
import wx
from ifigure.utils.wx3to4 import GridSizer


class FindPanel(wx.Panel):
    def __init__(self, parent, id, *args, **kargs):
        wx.Panel.__init__(self, parent, id,
                          style=wx.FRAME_FLOAT_ON_PARENT | wx.CLOSE_BOX)

        self.SetSizer(wx.BoxSizer(wx.VERTICAL))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.GetSizer().Add(sizer, 1, wx.EXPAND | wx.ALL, 1)
        self.GetSizer().Add(sizer2, 1, wx.EXPAND | wx.ALL, 1)
        label = wx.StaticText(self)
        label.SetLabel('Find : ')
        label2 = wx.StaticText(self)
        label2.SetLabel('Replace : ')
        from ifigure.utils.edit_list import TextCtrlCopyPasteGeneric
        self.txt = TextCtrlCopyPasteGeneric(self, wx.ID_ANY, '',
                                            style=wx.TE_PROCESS_ENTER)
        self.txt2 = TextCtrlCopyPasteGeneric(self, wx.ID_ANY, '',
                                             style=wx.TE_PROCESS_ENTER)
        self.btn_bw = wx.Button(self, wx.ID_ANY, 'Backward')
        self.btn_fw = wx.Button(self, wx.ID_ANY, 'Forward')
        gsizer = GridSizer(1, 2)
        gsizer.Add(self.btn_bw, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        gsizer.Add(self.btn_fw, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        self.btn_cl = wx.Button(self, wx.ID_ANY, 'x', size=(25, -1))

        #from ifigure.ifigure_config import icondir
        #imageFile =os.path.join(icondir, '16x16', 'close.png')
        # bitmap=wx.Bitmap(imageFile)
        #self.btn_cl = wx.BitmapButton(self, bitmap=bitmap)

        self.Bind(wx.EVT_BUTTON, parent.onHitFW, self.btn_fw)
        self.Bind(wx.EVT_BUTTON, parent.onHitBW, self.btn_bw)
        self.Bind(wx.EVT_BUTTON, parent.onHitCL, self.btn_cl)
        self.Bind(wx.EVT_TEXT_ENTER, parent.onRunFind, self.txt)

        self.btn_replace = wx.Button(self, wx.ID_ANY, 'Replace')
        self.btn_replaceall = wx.Button(self, wx.ID_ANY, 'Replace All')
        self.Bind(wx.EVT_BUTTON, parent.onReplace, self.btn_replace)
        self.Bind(wx.EVT_BUTTON, parent.onReplaceAll, self.btn_replaceall)

        sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.txt, 1, wx.ALL | wx.EXPAND)
        sizer.Add(gsizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(self.btn_cl, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        sizer2.Add(label2, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        sizer2.Add(self.txt2, 1, wx.ALL | wx.EXPAND)
        sizer2.Add(self.btn_replace, 0, wx.ALL | wx.EXPAND)
        sizer2.Add(self.btn_replaceall, 0, wx.ALL | wx.EXPAND)

        self.Layout()
        self.Fit()

    def get_find_text(self):
        return str(self.txt.GetValue())

    def get_replace_text(self):
        return str(self.txt2.GetValue())


class PanelWithFindPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.find_panel = FindPanel(self, wx.ID_ANY)
        self._find_shown = False
        self.SetSizer(wx.BoxSizer(wx.VERTICAL))

    def ToggleFindPanel(self):
        if self._find_shown:
            nb = self.GetChildren()[1]
            stc = nb.GetCurrentPage()
            stc.SetFocus()
            self.GetSizer().Detach(self.find_panel)
            self._find_shown = False
        else:
            self.GetSizer().Add(self.find_panel, 0, wx.EXPAND)
            self._find_shown = True
        self.Layout()

    def get_findpanel_shown(self):
        return self._find_shown

    def onHitCL(self, evt):
        self.ToggleFindPanel()

    def find_forward(self):
        nb = self.GetChildren()[1]
        stc = nb.GetCurrentPage()
        txt = self.find_panel.get_find_text()

        l1, l2 = stc.GetSelection()
        for i in range(l2-l1):
            stc.CharRight()
        stc.SearchAnchor()
        flag = stc.SearchNext(0, txt)
        if flag != -1:
            l1, l2 = stc.GetSelection()
            stc.SetCurrentPos(l2)
            stc.SetSelection(l1, l2)
        return flag

    def onHitFW(self, evt):
        nb = self.GetChildren()[1]
        stc = nb.GetCurrentPage()
        flag = self.find_forward()
        stc.EnsureCaretVisible()
        evt.Skip()

    def onHitBW(self, evt):
        nb = self.GetChildren()[1]
        stc = nb.GetCurrentPage()
        txt = self.find_panel.get_find_text()

        stc.SearchAnchor()
        flag = stc.SearchPrev(0, txt)
        if flag != -1:
            l1, l2 = stc.GetSelection()
            stc.SetCurrentPos(l1)
            stc.SetSelection(l1, l2)
        stc.EnsureCaretVisible()
        evt.Skip()

    def onRunFind(self, evt):
        self.onHitFW(evt)
        evt.Skip()

    def replace_once(self):
        nb = self.GetChildren()[1]
        stc = nb.GetCurrentPage()
        txt = self.find_panel.get_replace_text()
        if len(txt) != 0:
            l1, l2 = stc.GetSelection()
            stc.Replace(l1, l2, txt)
            return True
        return False

    def onReplace(self, evt):
        flag2 = self.replace_once()
        evt.Skip()

    def onReplaceAll(self, evt):

        nb = self.GetChildren()[1]
        stc = nb.GetCurrentPage()
        stc.SetCurrentPos(0)
        pos = stc.GetCurrentPos()
        while(1):
            flag = self.find_forward()
            if flag == -1:
                break
            flag = self.replace_once()
            if not flag:
                break
        stc.EnsureCaretVisible()
        evt.Skip()
