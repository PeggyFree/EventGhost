# -*- coding: utf-8 -*-
#
# This file is part of EventGhost.
# Copyright (C) 2005-2009 Lars-Peter Voss <bitmonster@eventghost.org>
#
# EventGhost is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by the
# Free Software Foundation;
#
# EventGhost is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import eg
import wx
from threading import Thread
from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW, PIPE, Popen
from eg.WinApi import IsWin64
from win32file import Wow64DisableWow64FsRedirection, Wow64RevertWow64FsRedirection
from eg.WinApi.Dynamic import (
    sizeof, byref, WaitForSingleObject, FormatError,
    CloseHandle, INFINITE, GetExitCodeProcess, DWORD,
    SHELLEXECUTEINFO, SEE_MASK_NOCLOSEPROCESS, windll
)
from time import time as ttime
from codecs import open as code_open
from os import devnull, remove
from os.path import join

def popen(cmd, si):
    return Popen(
        'cmd /C %s' % cmd,
        stdout = PIPE,
        stderr = open(devnull),
        startupinfo = si,
        shell = False
    )


class Command(eg.ActionBase):
    name = "Windows Command"
    description = "Executes a single windows Command line statement."
    iconFile = "icons/Execute"
    class text:
        Command = "Command Line:"
        waitCheckbox = "Wait until command is terminated before proceeding"
        eventCheckbox = "Trigger event when command is terminated"
        wow64Checkbox = "Disable WOW64 filesystem redirection for this command"
        eventSuffix = "WindowsCommand"
        disableParsing = "Disable parsing of string"
        additionalSuffix = "Additional Suffix:"
        payload = "Use result as payload"
        runAsAdminCheckbox = "Run as Administrator (UAC prompt will appear if UAC is enabled!)"


    def __call__(
        self,
        command = '',
        waitForCompletion = True,
        triggerEvent = False,
        additionalSuffix = "",
        disableParsingCommand = True,
        disableParsingAdditionalSuffix = True,
        payload = False,
        disableWOW64=False,
        runAsAdmin = False,
    ):
        prefix = self.plugin.info.eventPrefix
        suffix = self.text.eventSuffix
        if additionalSuffix != "":
            suffix = "%s.%s" % (suffix, additionalSuffix)
        if not disableParsingCommand:
            command = eg.ParseString(command)
        if not disableParsingAdditionalSuffix:
            additionalSuffix = eg.ParseString(additionalSuffix)

        processInformation = self.processInformation = SHELLEXECUTEINFO()
        processInformation.cbSize = sizeof(processInformation)
        processInformation.hwnd = 0
        processInformation.lpFile = 'cmd.exe'
        if waitForCompletion or triggerEvent:
            si = STARTUPINFO()
            si.dwFlags |= STARTF_USESHOWWINDOW
            proc = popen("chcp", si) #DOS console codepage
            data = proc.communicate()[0]
            if not proc.returncode:
                cp = "cp" + data.split()[-1].replace(".", "")
            proc.stdout.close()
            filename = join(
                eg.folderPath.TemporaryFiles,
                "EventGhost-output-%s.txt" % ttime()
            )
            processInformation.lpParameters = '/C %s > %s' % (command, filename)
            processInformation.fMask = SEE_MASK_NOCLOSEPROCESS
        else:
            processInformation.lpParameters = '/C %s' % command
        if runAsAdmin:
            processInformation.lpVerb = "runas"
        processInformation.nShow = 0
        processInformation.hInstApp = 0

        disableWOW64 = disableWOW64 and IsWin64()
        if disableWOW64:
            prevVal = Wow64DisableWow64FsRedirection()
        if not windll.shell32.ShellExecuteExW(byref(processInformation)):
            raise self.Exception(FormatError())
        if disableWOW64:
            Wow64RevertWow64FsRedirection(prevVal)
        if waitForCompletion:
            WaitForSingleObject(processInformation.hProcess, INFINITE)
            exitCode = DWORD()
            if not GetExitCodeProcess(
                processInformation.hProcess,
                byref(exitCode)
            ):
                raise self.Exception(FormatError())
            try:
                data = code_open(filename, 'r', cp)
                lines = data.readlines()
                returnValue = "".join(lines)
                data.close()
                remove(filename)
            except:
                returnValue = ""

            if triggerEvent:
                if payload:
                    eg.TriggerEvent(
                        suffix,
                        prefix = prefix,
                        payload = returnValue.rstrip()
                    )
                else:
                    eg.TriggerEvent(suffix, prefix = prefix)
            CloseHandle(processInformation.hProcess)
            return returnValue.rstrip()
        elif triggerEvent:
            te = self.TriggerEvent(processInformation, suffix, prefix, filename, cp, payload)
            te.start()
        else:
            CloseHandle(processInformation.hProcess)



    class TriggerEvent(Thread):

        def __init__(self, processInformation, suffix, prefix, filename, cp, pld):
            Thread.__init__(self)
            self.processInformation = processInformation
            self.suffix = suffix
            self.prefix = prefix
            self.filename = filename
            self.cp = cp
            self.pld = pld

        def run(self):
            WaitForSingleObject(self.processInformation.hProcess, INFINITE)
            exitCode = DWORD()
            if not GetExitCodeProcess(
                self.processInformation.hProcess,
                byref(exitCode)
            ):
                raise self.Exception(FormatError())
            CloseHandle(self.processInformation.hProcess)
            if hasattr(self.processInformation, "hThread"):
                CloseHandle(self.processInformation.hThread)
            if self.pld:
                try:
                    data = code_open(self.filename, 'r', self.cp)
                    lines = data.readlines()
                    returnValue = "".join(lines)
                    data.close()
                    remove(self.filename)
                except:
                    returnValue = ""

                eg.TriggerEvent(
                    self.suffix,
                    prefix = self.prefix,
                    payload = returnValue.rstrip()
                )
            else:
                eg.TriggerEvent(self.suffix, prefix = self.prefix)


    def GetLabel(self, command = '', *dummyArgs):
        return "%s: %s" % (self.name, command)


    def Configure(
        self,
        command = '',
        waitForCompletion = True,
        triggerEvent = False,
        additionalSuffix = "",
        disableParsingCommand = True,
        disableParsingAdditionalSuffix = False,
        payload = False,
        disableWOW64=False,
        runAsAdmin = False,
    ):
        panel = eg.ConfigPanel()
        text = self.text
        commandCtrl = panel.TextCtrl(command)
        disableParsingCommandBox = panel.CheckBox(
            bool(disableParsingCommand),
            text.disableParsing
        )
        waitCheckBox = panel.CheckBox(
            bool(waitForCompletion),
            text.waitCheckbox
        )
        eventCheckBox = panel.CheckBox(
            bool(triggerEvent),
            text.eventCheckbox
        )
        pldCheckBox = panel.CheckBox(
            bool(payload),
            text.payload
        )
        additionalSuffixCtrl = panel.TextCtrl(additionalSuffix)
        disableParsingAdditionalSuffixBox = panel.CheckBox(
            bool(disableParsingAdditionalSuffix),
            text.disableParsing
        )
        wow64CheckBox = panel.CheckBox(
            bool(disableWOW64),
            text.wow64Checkbox
        )
        runAsAdminCheckBox = panel.CheckBox(
            bool(runAsAdmin),
            text.runAsAdminCheckbox
        )

        SText = panel.StaticText
        lowerSizer2 = wx.GridBagSizer(2, 0)
        lowerSizer2.AddGrowableCol(1)
        lowerSizer2.AddGrowableCol(3)
        stTxt = SText(text.additionalSuffix)
        lowerSizer2.AddMany([
            ((eventCheckBox), (0, 0), (1, 1), wx.ALIGN_BOTTOM),
            ((1, 1), (0, 1), (1, 1), wx.EXPAND),
            (pldCheckBox, (0, 2), (1, 1)),
            (stTxt, (1, 2), (1, 1), wx.ALIGN_BOTTOM),
            (additionalSuffixCtrl, (2, 2)),
            (disableParsingAdditionalSuffixBox, (3, 2)),
            ((1, 1), (0, 3), (1, 1), wx.EXPAND),
        ])

        def onEventCheckBox(evt = None):
            enable = eventCheckBox.GetValue()
            stTxt.Enable(enable)
            additionalSuffixCtrl.Enable(enable)
            disableParsingAdditionalSuffixBox.Enable(enable)
            disableParsingAdditionalSuffixBox.SetValue(enable)
            pldCheckBox.Enable(enable)
            if not enable:
                additionalSuffixCtrl.ChangeValue("")
            if evt:
                pldCheckBox.SetValue(False)
                evt.Skip()
        eventCheckBox.Bind(wx.EVT_CHECKBOX, onEventCheckBox)
        onEventCheckBox()

        panel.sizer.AddMany([
            (SText(text.Command)),
            ((1, 2)),
            (commandCtrl, 0, wx.EXPAND),
            ((1, 2)),
            (disableParsingCommandBox),
            ((10, 15)),
            (waitCheckBox),
            ((10, 8)),
            (lowerSizer2, 0, wx.EXPAND),
            ((10, 8)),
            (wow64CheckBox),
            ((10, 8)),
            (runAsAdminCheckBox),
        ])

        while panel.Affirmed():
            panel.SetResult(
                commandCtrl.GetValue(),
                waitCheckBox.GetValue(),
                eventCheckBox.GetValue(),
                additionalSuffixCtrl.GetValue(),
                disableParsingCommandBox.GetValue(),
                disableParsingAdditionalSuffixBox.GetValue(),
                pldCheckBox.GetValue(),
                wow64CheckBox.GetValue(),
                runAsAdminCheckBox.GetValue()
            )
