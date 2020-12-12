""" All the needed threads to let the program not freeze as the typical asshole """
import wx
import os
import threading
import subprocess
import time
import source.funs_n_cons_2 as utils
import source.result_dialog as rd
import zipfile
import source.constants as const

from configparser import ConfigParser

# Define notification event for thread completion
EVT_BUILDRESULT_ID = wx.NewId()
EVT_PLAYRESULT_ID = wx.NewId()

# Some extra constants.
BUILD_SUCCESS = 1
BUILD_CANCELED = 0
BUILD_ERROR = -1
BUILD_SKIPPED = -2

def EVT_BUILDRESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_BUILDRESULT_ID, func)
def EVT_PLAYRESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_PLAYRESULT_ID, func)


class BuildResultEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_BUILDRESULT_ID)
        self.data = data

class BuildProject(threading.Thread):
    """Worker Thread Class."""
    def __init__(self, notify_window):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)
        self.ui = notify_window
        self.abort = False
        self.start()

    def run(self):
        """Run Worker Thread."""
        
        # First for all, check the main flags
        noacs = self.ui.flags[0].GetValue();
        versioned = self.ui.flags[1].GetValue();
        packed = self.ui.flags[2].GetValue();
        
        
        # Make sure you're on the working directory where you will start the build.
        rootdir = self.ui.rootdir
        os.chdir(rootdir)
        
        parts = self.ui.projectparts
        
        current = 1
        total = len(parts)
        for part in parts:
            if part.skip: total -= 1
        
        if total == 0: 
            wx.PostEvent(self.ui, BuildResultEvent(BUILD_SKIPPED))
            return
        
        output = (0,[])
        # Good, now start.
        for part in parts:
            output = part.BuildPart(self, versioned, noacs, current, total)
            if not part.skip: current += 1
            if output[0] != 0 or self.abort:
                wx.PostEvent(self.ui, BuildResultEvent(output[0]))
                return
        
        # Files are built, now, we should pack them if flagged to do so.
        
        if packed:
            config = ConfigParser()
            config.read("project.ini")
            
            distDir  = const.ini_prop('zip_dir',  'dist\packed');
            fileName = const.ini_prop('zip_name', 'project');
            
            if not os.path.exists(distDir):
                os.mkdir(distDir)
                self.ui.AddToLog(distDir + " directory created to allocate the packed projects.")
                    
            if versioned: fileName += "_" + const.ini_prop('tag_relase','v0') + '.zip'
            else        : fileName += "_" + "DEV" + '.zip'
            
            
            destination = os.path.join(distDir, fileName)
            distzip = zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED)
            current = 1
            for file in output[1]:
                if self.abort: distzip.close(); return None
                os.chdir(file[0])
                distzip.write(file[1])
                utils.printProgress (self.ui, current, len(output[1]), '> Packed: ', 'files. (' + file[1] + ')')
                current += 1
                
            distzip.close()
            self.ui.AddToLog("> {0} Packed up Sucessfully".format(fileName))
            # print(file_list)
        
        os.chdir(rootdir)
        wx.PostEvent(self.ui, BuildResultEvent(BUILD_SUCCESS))

    def call_abort(self):
        self.abort = True

class PlayResultEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_PLAYRESULT_ID)
        self.data = data

class PlayProject(threading.Thread):
    """This thread will just run the project! """
    def __init__(self, notify_window, sourceport, iwad, test_map, ex_params, pwads):
        threading.Thread.__init__(self)
        self.ui = notify_window
        self.sourceport = sourceport
        self.iwad       = iwad
        self.test_map   = test_map
        self.ex_params  = ex_params
        self.pwads      = pwads
        self.start()

    def run(self):
        
        exe_path = const.ini_prop(self.sourceport + '_path', '?');
        
        exe_path = utils.relativePath(exe_path)
        
        if exe_path == '?' or not os.path.isdir(exe_path): 
            msg = "Could'nt find " + self.sourceport + ".exe"
            msg += "\nCheck the path in the project.ini, override "+ self.sourceport + "_path, and try again."
            dlg = wx.MessageDialog(self.ui, msg, "Running error").ShowModal()
            return
        
        os.chdir(exe_path)
        
        pwadlist = []
        for pwad in self.pwads:
            pwadlist.extend(["-file"] + [os.path.join(pwad[1], pwad[0])])
            # -stdout
        
        fullcmd     = [self.sourceport + ".exe", "-iwad", self.iwad, '+map', self.test_map] + pwadlist + self.ex_params.split() + ["-stdout"]
        
        """
        fullcmd     = ["zandronum.exe", "-iwad", "doom2.wad" , "-file", std_path]
        subprocess.call(fullcmd+ filelist + ['+map', map_test])
        """
        p = subprocess.Popen(fullcmd, stdout=subprocess.PIPE)
        out, err = p.communicate()
            
        os.chdir(self.ui.rootdir)
        wx.PostEvent(self.ui, PlayResultEvent(out.decode("ansi")))
        
        