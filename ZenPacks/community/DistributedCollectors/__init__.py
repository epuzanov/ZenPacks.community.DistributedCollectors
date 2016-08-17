################################################################################
#
# This program is part of the DistributedCollectors Zenpack for Zenoss.
# Copyright (C) 2010 Egor Puzanov.
#
# This program can be used under the GNU General Public License version 2
# You can find full information here: http://www.zenoss.com/oss
#
################################################################################

import Globals
import os
import socket
import cgi
import transaction
import logging
import fileinput
from time import strftime
try:
    from Products.ZenUI3.browser.streaming import StreamingView
    from Products.ZenUtils.jsonutils import unjson, json
except ImportError:
    from Products.ZenUtils.json import unjson, json
    class StreamingView:
        def __init__(self, context, request):
            self.context = context
            self.request = request
            self.out = request.RESPONSE

        def __call__(self):
            header,footer=self.context.commandTestOutput().split('OUTPUT_TOKEN')
            self.out.write(str(header))
            self.stream()
            self.out.write(str(footer))

        def stream(self):
            return

        def write(self, data=''):
            ''' Output (maybe partial) result text.
            '''
            startLine = '<tr><td class="tablevalues">'
            endLine = '</td></tr>\n'
            if self.out:
                if not isinstance(data, list):
                    data = [data]
                for l in data:
                    if not isinstance(l, str):
                        l = str(l)
                    l = l.strip()
                    l = cgi.escape(l)
                    l = l.replace('\n', endLine + startLine)
                    self.out.write(startLine + l + endLine)

skinsDir = os.path.join(os.path.dirname(__file__), 'skins')
from Products.CMFCore.DirectoryView import registerDirectory
if os.path.isdir(skinsDir):
    registerDirectory(skinsDir, globals())

from Products.ZenWidgets import messaging
from Products.ZenUtils.Utils \
    import monkeypatch, zenPath, binPath, executeCommand, executeStreamCommand
from Products.ZenModel.PerformanceConf import performancePath

log = logging.getLogger('.'.join(['zen', __name__]))

COMMAND_TIMEOUT=240

MASTER_DAEMON_LIST_FILE=zenPath('etc/master_daemons.txt')

DEFAULT_MASTER_DAEMONS=['zeoctl', 'zopectl', 'zeneventd', 'zenhub', 'zenjobs',
                        'zenactions', 'zenactiond']

zpDir = zenPath('ZenPacks')
updConfZenBin = zenPath('bin/updateConfigs')
updConfBin = os.path.join(os.path.dirname(__file__), 'bin/updateConfigs')

class UpdateRemoteCollectorView(StreamingView):
    def write(self, data=''):
        StreamingView.write(self, '  '.join((strftime('%Y-%m-%d %H:%M:%S,000'),
            'INFO', 'zen.updateCollector:', data)))

    def stream(self):
        daemons=[d['name'] for d in self.context.dmd.About.getZenossDaemonStates() \
                if d['msg'] == 'Up' and d['name'] not in DEFAULT_MASTER_DAEMONS]
        if 'zeneventserver' in daemons:
            daemons.remove('zeneventserver') 
        if 'zenrrdcached' not in daemons:
            daemons.append('zenrrdcached')
        if 'zenrender' not in daemons:
            daemons.append('zenrender')
        if os.path.exists(MASTER_DAEMON_LIST_FILE):
            for line in fileinput.input(MASTER_DAEMON_LIST_FILE):
                line = line.strip()
                if line in daemons:
                    daemons.remove(line)
        df = open('%s/daemons.txt'%zpDir, 'w')
        df.write('%s\n'%'\n'.join(daemons))
        df.close()
        data = unjson(self.request.get('data'))
        ids = data['uids']
        if not ids:
            self.write('No Remote Collectors were selected')
        command = data['command']
        if command == 'add':
            new_id = ids[0]
            self.context.manage_addMonitor(new_id, submon='Performance')
#            self.context.Performance[new_id].renderurl = 'http://%s:8090/%s'%(
#                                                    socket.getfqdn(), new_id)
            self.context.Performance[new_id].renderurl='http://%s:8091' % new_id
            transaction.commit()
        for id in ids:
            self.write('%s Remote Collector %s'%(command.capitalize(), id))
            self.write('Stopping zenoss daemons')
            executeStreamCommand('ssh %s "zenoss stop"'%id,
                                        self.write, timeout=COMMAND_TIMEOUT)
            if command in ('update', 'remove'):
                self.write('Revert Remote Collector configuration')
                executeStreamCommand('ssh %s %s localhost localhost'%(id,
                            updConfZenBin), self.write, timeout=COMMAND_TIMEOUT)
            self.write('Remove ZenPacks files from Remote Collector')
            executeStreamCommand('ssh %s rm -fr %s'%(id, zpDir),
                                            self.write, timeout=COMMAND_TIMEOUT)
            if command in ('add', 'update'):
                self.write('Copy ZenPacks files to Remote Collector')
                executeStreamCommand('find %s -print | cpio -oc | ssh -C %s "cd / && cpio -ic 2>/dev/null"'%(
                                zpDir, id), self.write, timeout=COMMAND_TIMEOUT)
                self.write('Update Remote Collector configuration')
                executeStreamCommand('ssh %s %s %s %s'%(id, updConfBin,
                    socket.getfqdn(), id), self.write, timeout=COMMAND_TIMEOUT)
            self.write('Starting zenoss daemons')
            executeStreamCommand('ssh %s "zenoss start"'%id,
                    self.write, timeout=COMMAND_TIMEOUT)
        if command == 'remove':
            self.context.manage_removeMonitor(ids=ids, submon='Performance')
            transaction.commit()
        self.write('All Tasks Finished')
        os.unlink('%s/daemons.txt'%zpDir)


@monkeypatch('Products.ZenModel.Device.Device')
def setPerformanceMonitor(self, performanceMonitor,
                            newPerformanceMonitor=None, REQUEST=None):
    """
    Set the performance monitor for this device.
    If newPerformanceMonitor is passed in create it

    @permission: ZEN_CHANGE_DEVICE
    """
    if newPerformanceMonitor:
        #self.dmd.RenderServer.moveRRDFiles(self.id,
        #    newPerformanceMonitor, performanceMonitor, REQUEST)
        performanceMonitor = newPerformanceMonitor

    obj = self.getDmdRoot("Monitors").getPerformanceMonitor(
                                                    performanceMonitor)
    try:
        if self.getPerformanceServerName() == performanceMonitor: raise
        if self.getPerformanceServer().renderurl == '/zport/RenderServer':
            self.dmd.RenderServer.packageRRDFiles(self.id)
            self.dmd.RenderServer.deleteRRDFiles(self.id)
        else:
            os.system('ssh %s tar -C%s -czf - . > %s/%s.tgz'%(
                                    self.getPerformanceServer().id,
                                    performancePath('/Devices/%s'%self.id),
                                    self.dmd.RenderServer.tmpdir, self.id))
            os.system('ssh %s rm -fr %s'%(self.getPerformanceServer().id,
                                    performancePath('/Devices/%s'%self.id)))
        if obj.renderurl == '/zport/RenderServer':
            self.dmd.RenderServer.unpackageRRDFiles(self.id)
        else:
            os.system('cat %s/%s.tgz | ssh %s "(mkdir -p %s && tar -C%s -xzf - )"'%(
                                    self.dmd.RenderServer.tmpdir,self.id,obj.id,
                                    performancePath('/Devices/%s'%self.id),
                                    performancePath('/Devices/%s'%self.id)))
        os.unlink('%s/%s.tgz'%(self.dmd.RenderServer.tmpdir, self.id))
    except:
        pass
    self.addRelation("perfServer", obj)
    self.setLastChange()

    if REQUEST:
        messaging.IMessageSender(self).sendToBrowser(
            'Monitor Changed',
            'Performance monitor has been set to %s.' % performanceMonitor
        )
        return self.callZenScreen(REQUEST)

@monkeypatch('Products.ZenModel.MonitorClass.MonitorClass')
def manage_addRemoteMonitor(self, id=None, submon=None, REQUEST=None):
    'Add an object of sub_class, from a module of the same name'
    if REQUEST:
        REQUEST['data'] = json({'uids':[id], 'command':'add'})
        UpdateRemoteCollectorView(self, REQUEST)()
        messaging.IMessageSender(self).sendToBrowser(
            'Remote Collector Created',
            'Remote collector %s was created.' % id
        )
        return self.callZenScreen(REQUEST)


@monkeypatch('Products.ZenModel.MonitorClass.MonitorClass')
def manage_updateRemoteMonitors(self, ids=None, submon="", REQUEST=None):
    'Update an object from this one'
    if REQUEST:
        REQUEST['data'] = json({'uids':ids, 'command':'update'})
        UpdateRemoteCollectorView(self, REQUEST)()
        messaging.IMessageSender(self).sendToBrowser(
            'Remote Collectors Updated',
            'Updated remote collectors: %s' % (', '.join(ids))
        )
        return self.callZenScreen(REQUEST)

@monkeypatch('Products.ZenModel.MonitorClass.MonitorClass')
def manage_removeRemoteMonitors(self, ids=None, submon="", REQUEST=None):
    'Remove an object from this one'
    if REQUEST:
        REQUEST['data'] = json({'uids':ids, 'command':'remove'})
        UpdateRemoteCollectorView(self, REQUEST)()
        messaging.IMessageSender(self).sendToBrowser(
            'Remote Collectors Deleted',
            'Deleted remote collectors: %s' % (', '.join(ids))
        )
        return self.callZenScreen(REQUEST)

@monkeypatch('Products.ZenModel.PerformanceConf.PerformanceConf')
def _executeZenModelerCommand(self, zenmodelerOpts, *args):
    """
    Execute zenmodeler and return result

    @param zenmodelerOpts: zenmodeler command-line options
    @type zenmodelerOpts: string
    @param REQUEST: Zope REQUEST object
    @type REQUEST: Zope REQUEST object
    @return: results of command
    @rtype: string
    """
    zm = binPath('zenmodeler')
    zenmodelerCmd = [zm]
    zenmodelerCmd.extend(zenmodelerOpts)
    if zenmodelerOpts[3] != 'localhost':
        zenmodelerCmd.extend(['--hubhost', socket.getfqdn()])
        zenmodelerCmd = ['/usr/bin/ssh', zenmodelerOpts[3]] + zenmodelerCmd
    if len(args) == 3:
        background, REQUEST, write = args
        if background:
#            log.info('queued job: %s', " ".join(zenmodelerCmd))
            result = self.dmd.JobManager.addJob(SubprocessJob,zenmodelerCmd)
        else: result = executeCommand(zenmodelerCmd, REQUEST, write)
    else:
        result = executeCommand(zenmodelerCmd, args[0])
    return result

@monkeypatch('Products.ZenModel.PerformanceConf.PerformanceConf')
def _executeZenDiscCommand(self, deviceName, devicePath= "/Discovered", 
                               performanceMonitor="localhost",
                               background=False, REQUEST=None):
    """
    Execute zendisc on the new device and return result

    @param deviceName: Name of a device
    @type deviceName: string
    @param devicePath: DMD path to create the new device in
    @type devicePath: string
    @param performanceMonitor: DMD object that collects from a device
    @type performanceMonitor: DMD object
    @param background: should command be scheduled job?
    @type background: boolean
    @param REQUEST: Zope REQUEST object
    @type REQUEST: Zope REQUEST object
    @return:
    @rtype:
    """
    zendiscCmd = self._getZenDiscCommand(deviceName, devicePath,
                                             performanceMonitor, REQUEST)
    if background:
#        log.info('queued job: %s', " ".join(zendiscCmd))
        result = self.dmd.JobManager.addJob(SubprocessJob,
                                                zendiscCmd)
    else:
        result = executeCommand(zendiscCmd, REQUEST)
    return result

@monkeypatch('Products.ZenModel.PerformanceConf.PerformanceConf')
def _getZenDiscCommand(self, deviceName, devicePath,
                           performanceMonitor, REQUEST=None):

    zm = binPath('zendisc')
    zendiscCmd = [zm]
    zendiscOptions = ['run', '--now','-d', deviceName,
                     '--monitor', performanceMonitor,
                     '--deviceclass', devicePath]
    if REQUEST:
        zendiscOptions.append("--weblog")
    zendiscCmd.extend(zendiscOptions)
    if performanceMonitor != 'localhost':
        zendiscCmd.extend(['--hubhost', socket.getfqdn()])
        zendiscCmd = ['/usr/bin/ssh', performanceMonitor] + zendiscCmd
#    log.info('local zendiscCmd is "%s"' % ' '.join(zendiscCmd))
    return zendiscCmd


from Products.ZenModel.ZenPack import ZenPackBase
from Products.ZenModel.ZenMenu import ZenMenu

class ZenPack(ZenPackBase):
    def install(self, app):
        self.replaceString(zenPath('bin/zenoss'),'	#C="$C zenrender"','	C="$C zenrender"')
        if os.path.exists(zenPath('etc/DAEMONS_TXT_ONLY')) and os.path.exists(zenPath('etc/daemons.txt')):
            self.replaceString(zenPath('etc/daemons.txt'),'','zenrender')
        ZenPackBase.install(self, app)
        self.installMenuItems(app.zport.dmd)

    def upgrade(self, app):
        ZenPackBase.upgrade(self, app)
        self.installMenuItems(app.zport.dmd)

    def remove(self, app, leaveObjects=False):
        self.replaceString(zenPath('bin/zenoss'),'	C="$C zenrender"','	#C="$C zenrender"')
        if os.path.exists(zenPath('etc/DAEMONS_TXT_ONLY')) and os.path.exists(zenPath('etc/daemons.txt')):
            self.replaceString(zenPath('etc/daemons.txt'),'zenrender','')
        self.removeMenuItems(app.zport.dmd)
        ZenPackBase.remove(self, app, leaveObjects)

    def installMenuItems(self, dmd):
        self.removeMenuItems(dmd)
        menu = dmd.zenMenus.PerformanceMonitor_list
        menu.manage_addZenMenuItem(
            "addRPMonitor",
            action="dialog_addRemoteMonitor",
            description="Add Remote Monitor...",
            isdialog=True,
            permissions=('Manage DMD',),
            ordering=70.0)
        menu.manage_addZenMenuItem(
            "updateRPMonitor",
            action="dialog_updateRemoteMonitors",
            description="Update Remote Monitors...",
            isdialog=True,
            permissions=('Manage DMD',),
            ordering=60.0)
        menu.manage_addZenMenuItem(
            "removeRPMonitor",
            action="dialog_removeRemoteMonitors",
            description="Delete Remote Monitors...",
            isdialog=True,
            permissions=('Manage DMD',),
            ordering=50.0)

    def removeMenuItems(self, dmd):
        menu = dmd.zenMenus.PerformanceMonitor_list
        items = []
        for i in ["addRPMonitor", "updateRPMonitor", "removeRPMonitor"]:
            if hasattr(menu.zenMenuItems, i): items.append(i)
        if len(items) > 0: menu.manage_deleteZenMenuItem(tuple(items))

    def replaceString(self, path, search, repl):
        for line in fileinput.input(path, inplace=1):
            if search != '': newline = line.strip('\n').replace(search, repl) 
            elif fileinput.lineno() == 4: newline = "%s\n%s"(line.strip('\n'), repl)
            else: newline = line.strip('\n')
            if repl == newline == '' and  line.strip('\n') != '':continue
            print newline
