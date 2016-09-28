#coding: utf-8
#
##
# Class builder - queues commands to execute and performs them
#

import copy
import curses
import curses.wrapper
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from config import Configuration
from config import MachineItem
from project import *

## 
# Buildhost class - oversees the build process for a particular host
#
class BuildHost(threading.Thread):
    ##
    # Ctor
    # \param[in] Key to machines hash (to uniquely identify this host entry)
    # \param[in] Configuration class (for pbuild configuration)
    def __init__(self, machineKey, config):
        threading.Thread.__init__(self)
        self.display_line = 0
        self.finished = False

        self.config = config

        self.tag = config.machines[machineKey].GetTag()
        self.hostname = config.machines[machineKey].GetHost()

        self.path = config.machines[machineKey].GetPath()
        self.project = config.machines[machineKey].GetProject()
        self.logPrefix = config.GetLogfilePrefix()
        self.deleteLogfiles = config.GetSetting('DeleteLogfiles')
        self.diagnoseErrors = config.GetSetting('DiagnoseErrors')
        self.renameLogfiles = config.GetSetting('LogfileRename')
        self.showProgress = config.GetSetting('Progress')

        # Construct the generic project definitions

        factory = ProjectFactory(self.project)
        assert factory.Validate()
        self.projectDefs = factory.Create()

        # And build the queue of commands to run for the project

        self.queue = []
        self.BuildQueue(self.queue)

        # Initialize variables for status handling
        #
        # Flag meaning:
        #   bLogActivity:   Set to True whenever activity to the log has occurred
        #   cLogSubLines:   Total number of lines written in this section
        #   sActivityText:  Text showing current activity of subprocess
        #   cActivityTime:  Time of last update (maintained by display code)

        self.bLogActivity = True
        self.cLogSubLines = 0
        self.sActivityText = 'starting up'
        self.tActivityTime = 0

        # Support for setting 'LogfileSelect'
        #
        # If 'LogfileSelect' is specified, then logfiles are named with the
        # selector name (if a selector name is known).  This will allow several
        # instances of pbuild to be run concurrently against independent
        # selectors by not conflicting in the log file naming conventions.

        self.selectSpec = ''

        if config.GetSetting('LogfileSelect'):
            self.selectSpec = '-None'

            # If we have a selector specification, use it
            if config.GetSelectSpecification() != '':
               self.selectSpec = '-%s' % config.GetSelectSpecification()

    ##
    # Build queue of operations to initialize the environment on destination
    #
    def BuildQueueInitialize(self, queue):
        # Build a command script to execute on remote system
        queue.append('# Try to find login profile to execute')
        queue.append('if [ -f /etc/profile ]; then')
        queue.append('    echo "Sourcing /etc/profile"')
        queue.append('    . /etc/profile')
        queue.append('fi')
        queue.append('if [ -f ~/.bash_profile ]; then')
        queue.append('    echo "Sourcing ~/.bash_profile"')
        queue.append('    . ~/.bash_profile')
        queue.append('elif [ -f ~/.bash_login ]; then')
        queue.append('    echo "Sourcing ~/.bash_login"')
        queue.append('    . ~/.bash_login')
        queue.append('elif [ -f ~/.profile ]; then')
        queue.append('    echo "Sourcing ~/.profile"')
        queue.append('    . ~/.profile')
        queue.append('else')
        queue.append('    echo "ERROR: Unable to find login files to source!"')
        queue.append('fi')
        queue.append('')
        queue.append('# Hacks for the HP platform (normally dealt with by /etc/profile)')
        queue.append('set +u')
        queue.append('[ -e /etc/PATH ] && export PATH=$PATH:`cat /etc/PATH`')
        queue.append('if [ -z "$PKG_CONFIG_PATH" -a -d /usr/local/lib/pkgconfig ]; then')
        queue.append('    export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig')
        queue.append('fi')
        queue.append('')
        queue.append('echo')

        commandLine = ' '
        commandLine.join(sys.argv)
        queue.append('echo \'Command line: %s\'' % commandLine.join(sys.argv).replace('\'', '"'))
        queue.append('echo "Starting at:  `date`"')
        queue.append('EXITSTATUS=0')

        # Support the -command qualifier
        if self.config.options.command:
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing custom command')
            queue.append('echo "Command: %s"' % self.config.options.command)
            queue.append('cd %s || exit $?' % self.path)
            queue.append(self.config.options.command)
            queue.append('EXITSTATUS=$?')
            queue.append('exit $EXITSTATUS')
            return


    ##
    # Build queue of operations to clean up writable files on destination
    #
    # Note: "paths" should generally NOT be a list with new project-based clean mechanism
    #       (although, technically, it will work)
    #
    def BuildQueueCleanup(self, queue):
        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing git cleanup')
        queue.append('date')
        # Basic steps are:
        #   1. git stash (in each subproject)
        #   2. git fetch (in each subproject)
        queue.append('git stash')
        queue.append('git submodule foreach git stash')
        #
        queue.append('git fetch --recurse-submodules')


    ##
    # Build queue of operations to perform on the remote systems
    #
    def BuildQueue(self, queue):
        self.BuildQueueInitialize(queue)

        # Normally done by 'pbuild --init', but verify in case --init disabled
        # Note that some hosts don't support "-o HashKnownHosts=no", so try twice
        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing git validation')
        queue.append('date')
        queue.append('grep github.com, ~/.ssh/known_hosts > /dev/null 2> /dev/null || ssh -o StrictHostKeyChecking=no -o HashKnownHosts=no -T git@github.com')
        queue.append('grep github.com, ~/.ssh/known_hosts > /dev/null 2> /dev/null || ssh -o StrictHostKeyChecking=no -T git@github.com')

        # If directory doesn't exist, automatically clone
        queue.append('create_repo_clone()')
        queue.append('{')
        queue.append('    echo')
        queue.append('    echo ========================= Performing git clone')
        queue.append('    date')
        queue.append('    echo \'Cloning project %s\'' % self.projectDefs.GetCloneSource())
        queue.append('    mkdir -p %s' % self.path)
        queue.append('    rm -rf %s' % self.path)
        queue.append('    git clone --recursive %s %s || exit $?'
                            % (self.projectDefs.GetCloneSource(), self.path))
        queue.append('    DID_WE_CLONE=1')
        queue.append('}')
        queue.append('DID_WE_CLONE=0')
        queue.append('')
        queue.append('if [ ! -d %s -o ! -d %s/.git ]; then' % (self.path, self.path))
        queue.append('    create_repo_clone')

        if self.config.options.clone:
            queue.append('else')
            queue.append('    create_repo_clone')

        queue.append('fi')

        # Change into the user directory for build purposes (it better exist by now!)
        queue.append('cd %s || exit $?' % self.path)

        # We only need to clean up the repo if we didn't just clone it ...
        queue.append('if [ $DID_WE_CLONE -eq 0 ]; then')
        self.BuildQueueCleanup(queue)
        queue.append('fi')

        # One way or another, we have a clean repository, so get it in a known state:
        #
        #   1. git checkout origin/master (in each subproject)
        #   2. Apply --branch and --subproject as needed

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing git checkout origin/master')
        queue.append('date')
        queue.append('git checkout origin/master')
        queue.append('git submodule foreach git checkout origin/master')

        if self.config.options.branch:
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing Applying --branch qualifier')
            queue.append('date')
            queue.append('# Applying branch \'origin/%s\' to project' % self.config.options.branch)
            queue.append('git checkout origin/%s || exit $?' % self.config.options.branch)
            queue.append('git submodule update || exit $?')

        if self.config.options.subproject:
            subprojectList = self.config.options.subproject.split(',')
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing Applying --subproject qualifier')
            queue.append('date')
            for subproject in subprojectList:
                # Subproject spec looks like: <dir>:<branch>
                subproject_dir, subproject_branch = subproject.split(':')
                queue.append('echo "Applying branch \'origin/%s\' to subproject \'%s\'"'
                             % (subproject_branch, subproject_dir))
                queue.append('if [ ! -d "%s" ]; then' % subproject_dir)
                queue.append('    echo "Directory \'%s\' not found for subproject spec \'%s\'"'
                             % (subproject_dir, subproject))
                queue.append('    exit 1')
                queue.append('fi')
                queue.append('cd %s || exit $?' % subproject_dir)
                queue.append('git checkout origin/%s || exit $?' % subproject_branch)
                queue.append('cd %s || exit $?' % self.path)
            queue.append('echo')

        # Clean up the repostories of any existing (unnecessary files)
        # We do this step here to properly handle any changes to .gitignore

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing git clean')
        queue.append('date')
        queue.append('sudo git clean -fdx || exit $?')
        queue.append('sudo git submodule foreach git clean -fdx || exit $?')

        # Get ready to build

        queue.append('cd %s || exit $?' % self.projectDefs.GetBuildDirectory())

        # Now generate the remainder of the command script

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing Determining debug/release')
        queue.append('date')

        config_options = self.projectDefs.GetConfigureQualifiers()
        if self.projectDefs.GetProjectName() in self.config.configure_options:
            config_options = self.config.configure_options[self.projectDefs.GetProjectName()]

        if self.config.options.debug:
            queue.append('echo "Performing DEBUG build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s --enable-debug)"' % config_options)
            queue.append('./configure %s --enable-debug' % config_options)
            queue.append('EXITSTATUS=$?')
        else:
            queue.append('echo "Performing RELEASE build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s)"' % config_options)
            queue.append('./configure %s' % config_options)
            queue.append('EXITSTATUS=$?')
        queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')

        if self.projectDefs.GetMakeDependencies():
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing make depend')
            queue.append('date')
            queue.append('make depend')
            queue.append('echo')

        if len(self.config.options.target) != 0:
            # Our target is?
            target = self.projectDefs.GetTargets()
            if self.config.options.target != "target_default":
                target = self.config.options.target

            queue.append('')
            queue.append('echo')
            queue.append('echo \'========================= Performing make ' + target + '\'')
            queue.append('date')

            # Set up test restrictions if appropriate
            if self.config.GetTestAttributes() != '':
                queue.append('SCX_TESTRUN_ATTRS=\"%s\"; export SCX_TESTRUN_ATTRS' % self.config.GetTestAttributes())

            if self.config.GetTestList() != '':
                queue.append('SCX_TESTRUN_NAMES=\"%s\"; export SCX_TESTRUN_NAMES' % self.config.GetTestList())

            queue.append('echo \'========================= Performing make %s ' % target + '\'')
            queue.append('make %s ' % target)
            queue.append('MAKE_STATUS=$?')
            queue.append('if [ $MAKE_STATUS -ne 0 ]; then')
            queue.append('    EXITSTATUS=$MAKE_STATUS')
            queue.append('fi')                
            queue.append('')

        if len(self.projectDefs.GetPostBuildCommands()) > 0:
            queue.append('echo \'========================= Performing post build steps\'')
            queue.append('POSTSTATUS=0')
            for command in self.projectDefs.GetPostBuildCommands():
                queue.append('if [ $POSTSTATUS -eq 0 ]; then')
                queue.append('    echo \'========================= Performing Executing %s ' % command + '\'')

                queue.append('    ' + command)
                queue.append('    POSTSTATUS=$?')
                queue.append('fi')
            queue.append('if [ $POSTSTATUS -ne 0 ]; then')
            queue.append('    EXITSTATUS=%POSTSTATUS')
            queue.append('fi')

        queue.append('echo')
        queue.append('echo Ending at:  `date`')

    ##
    # Perform a build on a remote system (execute the command script already copied).
    #
    # Upon completion, <object>.process.returncode will contain the exit status for
    # the remote build.
    def DoBuild(self):
        # If we're doing logfile renaming, active logs start as 'active-'
        if self.renameLogfiles:
            activeStr = 'active-'
        else:
            activeStr = ''

        outfname = '%s%s%s%s.log' % (self.logPrefix, activeStr, self.tag, self.selectSpec)

        if self.deleteLogfiles:
            for prefix in [ '', 'active-', 'done-', 'failed-' ]:
                try:
                    os.remove('%s%s%s%s.log' % (self.logPrefix, prefix, self.tag, self.selectSpec))
                except OSError:
                    # If the file doesn't exist, that's fine
                    pass
        else:
            try:
                os.remove(outfname)
            except OSError:
                # If the file doesn't exist, that's fine
                pass

        # Open the output file and launch the subprocess
        #
        # Slightly different behavior based on "ShowProgress" setting
        # (solely for performance benefit - otherwise not really needed)
        if self.showProgress:
            outf = open(outfname, 'a+', 1)

            self.process = subprocess.Popen(
                ['ssh', '-A', self.hostname, 'chmod 755 ' + self.destinationName + '; bash ' + self.destinationName],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
                )

            # Handle output from the subprocess
            while True:
                line = self.process.stdout.readline()
                if line == '':
                    break

                # Track out line count, save off any "state" lines, and save output
                self.bLogActivity = True
                self.cLogSubLines += 1

                if line.startswith('========================= Performing '):
                    self.sActivityText = line.rstrip()[37:]
                    self.cLogSubLines = 0
                outf.write(line)

                if line.startswith("make: warning:  Clock skew detected."):
                    outf.write("FATAL ERROR: Terminating process due to clock skew!");
                    outf.write("*** Check destination system to verify remote build was killed! ***")
                    self.process.terminate()

            self.process.communicate()
        else:
            outf = open(outfname, 'a+')

            self.process = subprocess.Popen(
                ['ssh', self.hostname, 'chmod 755 ' + self.destinationName + '; bash ' + self.destinationName],
                stdin=subprocess.PIPE,
                stdout=outf,
                stderr=outf
                )

        self.process.wait()
        outf.close()

        if self.renameLogfiles:
            # Determine the final name for the logfile
            if self.process.returncode == 0:
                completionStr = 'done-'
            else:
                completionStr = 'failed-'

            newfname = '%s%s%s%s.log' % (self.logPrefix, completionStr, self.tag, self.selectSpec)
            os.rename(outfname, newfname)

    ##
    # Generate a command script to execute a remote build and copy it to the remote system.
    # This is done by creating a local temporary file, then copying that file to the remote
    # host.  Upon exit from this function, the local temporary file is deleted.
    #
    # \returns
    # Status from copy of command script to remote system (normally zero)
    def GenerateCommandScript(self):
        self.destinationName = '/tmp/%(LOGNAME)s_%(HOST)s_%(PID)d.sh' \
            % {'LOGNAME': os.environ['LOGNAME'], 'HOST': self.tag, 'PID': os.getpid() }

        # Prepend commands to go to the proper directory and delete our
        # temporary command script.
        #
        # Add nice support for the emacs editor along the way ...
        # Note: Disabled for now.  Causes performance issues with some verisons of
        #	emacs.  Disable, maybe enable via option if requested.
        #self.queue.insert(0, 'echo \'-*- mode: compilation -*-\'')

        # In case of internal errors, leave temporary command script around
        if not self.diagnoseErrors:
            self.queue.insert(1, 'rm ' + self.destinationName)
        else:
            self.queue.insert(1, 'echo \'Executing script %s\'' % self.destinationName)

        self.queue.insert(2, 'echo "Executing on host $HOSTNAME (%(TAG)s: %(HOST)s)"' \
                              % {'TAG' : self.tag, 'HOST' : self.hostname } )
        self.queue.insert(3, '')

        # We assume that $EXITSTATUS was previously set by project-specific queue code
        self.queue.append('echo ========================= Performing Finishing up\; status=$EXITSTATUS')
        self.queue.append('exit $EXITSTATUS')

        # Generate a temporary file with all of our commands

        tmpfile = tempfile.NamedTemporaryFile()

        for command in self.queue:
            tmpfile.write(command + '\n')

        tmpfile.flush()

        # Copy the temporary command file to the destination host

        self.process = subprocess.Popen(
            ['scp', '-q', tmpfile.name, self.hostname + ':' + self.destinationName],
            stdin=subprocess.PIPE
            )

        # If the process isn't running yet, the wait() will fail - handle that
        waitComplete = False
        for i in range(60):
            try:
                self.process.wait()
                waitComplete = True
                break
            except OSError:
                time.sleep(1)

        # Last try - if this fails, we get a stack trace (which is fine)
        if waitComplete == False:
            self.process.wait()

        # Temporary file deleted on exit of this function ...

        return self.process.returncode

    def run(self):
        if self.GenerateCommandScript() == 0:
            self.DoBuild()
        else:
            # We aren't going to run, so create an empty log file with an error in it
            if self.renameLogfiles:
                completionStr = 'failed-'
            else:
                completionStr = ''

            outfname = '%s%s%s%s.log' % (self.logPrefix, completionStr, self.tag, self.selectSpec)
            outf = open(outfname, 'w+')
            outf.write("ERROR: SCP process did not properly copy script for host: %s\n" % self.hostname)
            outf.close()

        return

##
# Builder class - oversees the overall build process
#
class Builder:
    ##
    # Ctor.
    # \param[in] Configuration class
    def __init__(self, config):
        self.config = config;

    ##
    # Formats and returns command line to fit within a list
    # where no one string exceeds a length
    #
    def FormatCommandLine(self, width):
        stringList = []
        curStr = ""

        for item in sys.argv:
            # Deal with spaces within the argument
            if item.find(' ') != -1:
                if item.find('=') != -1:
                    item = item.replace('=', '="', 1)
                else:
                    item = item.replace(' ', ' "', 1)
                item = item + '"'
            if len(curStr) + len(item) >= width:
                stringList.append(curStr)
                curStr = "  "
            curStr = curStr + item + " "

        stringList.append(curStr)
        return stringList

    ##
    # Move log files to prior log directory if desired
    #
    def MoveLogfiles(self):
        # Just return if we're not doing logfile moving
        if self.config.GetLogfilePriorPrefix() == '':
            return

        # Figure out the log file prefixes based on configuration
        if self.config.GetSetting('LogfileRename'):
            prefixStr = [ 'active-', 'done-', 'failed-' ]
        else:
            prefixStr = [ '' ]

        # For each machine/prefix combination, move the log file
        for machine in sorted(self.config.machines.keys()):
            # To keep the prior log directory from becoming a garbage dump, we
            # delete prior logs if we'll be moving any existing logs (based on
            # configuration setting 'DeleteLogFiles')

            if self.config.GetSetting('DeleteLogfiles'):
                # Do we have any existing log files to move for this host?
                existingLogs = False
                for prefix in prefixStr:
                    srcfname = '%s%s%s.log' % (self.config.GetLogfilePrefix(), prefix, machine)
                    try:
                        os.stat(srcfname)
                        existingLogs = True
                        break
                    except OSError:
                        # If the file doesn't exist, that's fine
                        pass

                # If so, then delete all variations of the log file from prior ...
                if existingLogs:
                    for prefix in prefixStr:
                        dstfname = '%s%s%s.log' % (self.config.GetLogfilePriorPrefix(), prefix, machine)
                        try:
                            os.remove(dstfname)
                        except OSError:
                            # If the file doesn't exist, that's fine
                            pass

            # And finally, move the 'current' logs to the prior directory
            for prefix in prefixStr:
                srcfname = '%s%s%s.log' % (self.config.GetLogfilePrefix(), prefix, machine)
                dstfname = '%s%s%s.log' % (self.config.GetLogfilePriorPrefix(), prefix, machine)

                try:
                    os.rename(srcfname, dstfname)
                except OSError:
                    # If the file doesn't exist, that's fine
                    pass

    ##
    # Perform processing (and screen updates)
    #
    def ProcessUpdates(self, stdscr, hosts):
        startTime = time.time()
        stdscr.nodelay(1)
        (height, width) = stdscr.getmaxyx()

        # Verify that our screen is large enough.  Account for:
        #    . Three blank lines (after header, after host list, and before elapsed time)
        #    . "Host Count"
        #    . "Selector"
        #    . "Command Line" * 2
        #    . "Elapsed Time"
        #    . A "home" line for the cursor
        lastLine = 0
        hostCount = 0
        for host in hosts:
            lastLine = max(lastLine, host.display_line)
            hostCount = hostCount + 1

        lastLine += 9
        if height < lastLine or width < 80:
            return -1

        # Indentation locations:
        IndentTag = 0
        IndentHost = 20
        IndentStatus = 45
        statusLen = width - IndentStatus - 1

        # Print the headings on the screen
        stdscr.addstr(0, IndentTag, "Tag", curses.A_UNDERLINE)
        stdscr.addstr(0, IndentHost, "Host Name", curses.A_UNDERLINE)
        stdscr.addstr(0, IndentStatus, "Status", curses.A_UNDERLINE)

        # Begin processing on each of our hosts
        lastLine = 0
        for host in hosts:
            host.start()
            stdscr.addstr(host.display_line, IndentTag,  host.tag[0:IndentHost-IndentTag-1])
            stdscr.addstr(host.display_line, IndentHost, host.hostname[0:IndentStatus-IndentHost-1])
            lastLine = max(lastLine, host.display_line)

        lastLine = lastLine + 2
        stdscr.addstr(lastLine, 0, 'Host Count:')
        stdscr.addstr(lastLine, 15, '%d' % hostCount)

        lastLine = lastLine + 1
        stdscr.addstr(lastLine, 0, 'Selector:')
        if self.config.GetSelectSpecification() != '':
            stdscr.addstr(lastLine, 15, self.config.GetSelectSpecification())
        else:
            stdscr.addstr(lastLine, 15, '<None>')

        lastLine = lastLine + 1
        stdscr.addstr(lastLine, 0, 'Command Line:')
        for line in self.FormatCommandLine(width - 15):
            stdscr.addstr(lastLine, 15, line)
            lastLine = lastLine + 1

        lastLine = lastLine + 1
        stdscr.addstr(lastLine, 0, 'Elapsed Time:')
        stdscr.addstr(lastLine, 15, '00:00')
        stdscr.addstr(lastLine + 1, 0, '')
        stdscr.refresh()

        # Wait for each of the hosts to complete processing
        failCount = 0
        while True:
            time.sleep(1)

            # See if we have some user input
            #   "r":	Refresh screen

            c = stdscr.getch()
            if c == ord('R') or c == ord('r'):
                stdscr.clearok(1)

            # Come up with a pretty way to display elapsed time
            currentTime = hostTime = (time.time() - startTime) + 0.5
            hostHH = int(hostTime / 60 / 60)
            hostTime = hostTime - (hostHH * 60 * 60)
            hostMM = int(hostTime / 60)
            hostSS = hostTime - (hostMM * 60)
            if hostHH:
                timeDisplay = '%02d:%02d:%02d' % (hostHH, hostMM, hostSS)
            else:
                timeDisplay = '%02d:%02d' % (hostMM, hostSS)

            # See if we can finish up any threads
            threadsLeft = False
            for host in hosts:
                if not host.finished and not host.isAlive():
                    host.join()
                    host.finished = True
                    if host.process.returncode == 0:
                        host.completionStatus = "Done (%s)" % timeDisplay
                        stdscr.addstr(host.display_line, IndentStatus,
                                      "%-*.*s" % (statusLen, statusLen, host.completionStatus))
                    else:
                        failCount += 1
                        host.completionStatus = "Failed (%s)" % timeDisplay
                        stdscr.addstr(host.display_line, IndentTag,  host.tag, curses.A_BOLD)
                        stdscr.addstr(host.display_line, IndentHost, host.hostname, curses.A_BOLD)
                        stdscr.addstr(host.display_line, IndentStatus,
                                      "%-*.*s" % (statusLen, statusLen, host.completionStatus),
                                      curses.A_BOLD)

                if not host.finished:
                    threadsLeft = True

                    # Any activity on host?  Update display if requested ...
                    if host.showProgress:
                        if host.bLogActivity:
                            host.bLogActivity = False
                            host.tActivityTime = currentTime

                            displayString = "%s (%d)" % (host.sActivityText, host.cLogSubLines)
                            stdscr.addstr(host.display_line, IndentStatus,
                                          "- %-*.*s" % (statusLen-2, statusLen-2, displayString))
                        elif currentTime > (host.tActivityTime + 30):
                            # No activity for a long time?  Indicate that ...
                            stdscr.addstr(host.display_line, IndentStatus, "?")

            stdscr.addstr(lastLine, 15, timeDisplay)
            stdscr.addstr(lastLine + 1, 0, '')
            stdscr.refresh()

            # Support --abortOnError behavior
            if self.config.options.abort and failCount != 0:
                # Mark all remaining hosts as "Aborted"
                for host in hosts:
                    if not host.finished:
                        host.completionStatus = "Aborted (%s)" % timeDisplay
                        stdscr.addstr(host.display_line, IndentStatus,
                                      "%-*.*s" % (statusLen, statusLen, host.completionStatus))
                        host.process.terminate()
                stdscr.refresh()

                return failCount

            # Check if any threads are left
            if not threadsLeft:
                break

        # All done
        return failCount

    ##
    # Perform processing (without curses)
    #
    def ProcessUpdatesWithoutCurses(self, hosts):
        # Begin processing on each of our hosts
        lastLine = 0
        for host in hosts:
            host.start()
            print "Starting host %s (%s)" % (host.hostname, host.tag)

        # Wait for each of the hosts to complete processing
        failCount = 0
        while True:
            time.sleep(1)

            # See if we can finish up any threads
            threadsLeft = False
            for host in hosts:
                if not host.finished and not host.isAlive():
                    host.join()
                    host.finished = True
                    if host.process.returncode == 0:
                        print "Completed host %s (%s)" % (host.hostname, host.tag)
                        host.completionStatus = "Done"
                    else:
                        failCount += 1
                        print "FAILED: Host %s (%s)" % (host.hostname, host.tag)
                        host.completionStatus = "Failed"

                if not host.finished:
                    threadsLeft = True

            # Support --abortOnError behavior
            if self.config.options.abort and failCount != 0:
                print "ABORTING due to failed build and --abortOnError"

                # Mark all remaining hosts as "Aborted"
                for host in hosts:
                    if not host.finished:
                        host.completionStatus = "Aborted"
                        host.process.terminate()

                return failCount

            # Check if any threads are left
            if not threadsLeft:
                break

        # All done
        return failCount

    ##
    # Perform a build across remote systems
    #
    def StartBuild(self):
        # Build the host list:
        # Either the one specified at launch, or all of the machines in configuraiton
        hosts = []
        if len(self.config.machineKeys):
            for entry in sorted(self.config.machineKeys):
                hosts.append( BuildHost(entry, self.config) )
        else:
            for key in sorted(self.config.machines.keys()):
                hosts.append( BuildHost(key, self.config) )

        # Figure out where each host will display it's data (sort by tag)
        tags = []
        for host in hosts:
            tags.append( host.tag )
        tags = sorted(tags)

        for host in hosts:
            host.display_line = tags.index(host.tag) + 2

        # Sanity check - each host should have a non-zero display line
        for host in hosts:
            assert host.display_line != 0

        # Move the log files to the prior log file directory
        self.MoveLogfiles()

        #
        # Go perform the build (and update the screen with progress)
        #

        failCount = 0
        if not self.config.options.nocurses:
            failCount = curses.wrapper(self.ProcessUpdates, hosts)
            if failCount == -1:
                print "ABORTING - Screen size is too small to use curses"
                return failCount
        else:
            failCount = self.ProcessUpdatesWithoutCurses(hosts)
            print

        # Print final completion status if configured

        if self.config.GetSetting('SummaryScreen'):
            print "Final status:\n"

            # We really prefer to list sorted by tags, so do so
            hosts_byTag = {}
            for host in hosts:
                hosts_byTag[host.tag] = host
            for key in sorted(hosts_byTag.keys()):
                print "%-19s %-25s %s" % (hosts_byTag[key].tag, hosts_byTag[key].hostname, hosts_byTag[key].completionStatus)
            print

        # All done

        return failCount
