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

        # Support for setting 'LogfileBranch'
        #
        # If 'LogfileBranch' is specified, then logfiles are named with the
        # branch name (if a branch name is known).  This will allow several
        # instances of pbuild to be run concurrently against independent
        # branches by not conflicting in the log file naming conventions.

        self.branchSpec = ''

        if config.GetSetting('LogfileBranch'):
            self.branchSpec = '-None'

            # If we have a branch specification, use it
            if config.GetBranchSpecification() != '':
               self.branchSpec = '-%s' % config.GetBranchSpecification()

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
            queue.append(self.config.options.command)
            queue.append('EXITSTATUS=$?')
            queue.append('exit $EXITSTATUS')
            return

        # Start up the TFS Proxy (tfprox) if it's not already running
        #
        # Note: It may be started via inetd.  If so, then it should be in the /etc/services file.
        # If not in /etc/services file, then just try and start (harmless if already running).
        #
        # (If using container file, it's assumed we're not using Teamprise)

        if self.config.GetSetting('TFProxStart') and not self.config.options.container:
            queue.append('echo')
            queue.append('echo ========================= Performing starting TFProxy')
            queue.append('cat /etc/services | grep tfprox | grep 8080 || sudo /opt/tfprox/bin/tfprox -b')


    ##
    # Build queue of operations to clean up writable files on destination
    #
    # Note: "paths" should generally NOT be a list with new project-based clean mechanism
    #       (although, technically, it will work)
    #
    def BuildQueueCleanup(self, queue, paths, cleanList):
        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing tf undo / cleanup')
        queue.append('date')
        for dir in paths:
            queue.append('tf undo -recursive %s' % dir)
            # Can't check status - 'tf undo' returns an error with nothing to undo
        queue.append('echo The following files are being deleted:')
        for pathDir in paths:
            for cleanDir in cleanList:
                queue.append('find %s/%s -type f -perm -u+w -print -exec rm {} \;' % (pathDir, cleanDir) )
        queue.append('echo')

    ##
    # Clean methods for specific projects (assumed that we're at base of enlistment for build project)
    #
    def BuildQueueCleanup_OMI(self, queue):
        # There's a LOT of directories to avoid output dirs.  We assume that 'make cleandist'
        # is complete (thus no cleanList for this project)
        cleanPaths = [ "../omi" ]
        cleanList = [ ]
        self.BuildQueueCleanup(queue, cleanPaths, cleanList)

    def BuildQueueCleanup_PAL(self, queue):
        cleanPaths = [ "../pal" ]
        cleanList = [ "installer", "source", "test" ]
        self.BuildQueueCleanup(queue, cleanPaths, cleanList)

    def BuildQueueCleanup_CM(self, queue):
        self.BuildQueueCleanup_OMI(queue)
        self.BuildQueueCleanup_PAL(queue)

        cleanPaths = [ ".." ]
        cleanList = [ "build", "opensource", "Unix/opensource", "Unix/src", "Unix/shared", "Unix/tools" ]
        self.BuildQueueCleanup(queue, cleanPaths, cleanList)

    def BuildQueueCleanup_OM(self, queue):
        self.BuildQueueCleanup_OMI(queue)
        self.BuildQueueCleanup_PAL(queue)

        cleanPaths = [ "." ]
        cleanList = [ "docs", "installer", "source", "test", "tools" ]
        self.BuildQueueCleanup(queue, cleanPaths, cleanList)

    def BuildQueueCleanup_VMM(self, queue):
        self.BuildQueueCleanup_PAL(queue)

        cleanPaths = [ "." ]
        cleanList = [ "src" ]
        self.BuildQueueCleanup(queue, cleanPaths, cleanList)

    ##
    # Build queue of operations to perform on the remote systems
    #
    def BuildQueue(self, queue):
        if self.project == 'om':
            self.BuildQueue_OM(queue)
        elif self.project == 'cm':
            self.BuildQueue_CM(queue)
        elif self.project == 'vmm':
            self.BuildQueue_VMM(queue)
        elif self.project == 'nip':
            self.BuildQueue_NIP(queue)
        else:
            raise NotImplementedError

    ##
    # Build queue of operations to perform on the remote systems (for OM)
    #
    def BuildQueue_OM(self, queue):
        self.BuildQueueInitialize(queue)
        self.BuildQueueCleanup_OM(queue)

        # Support handling if initial 'tf get' was not done
        #
        # We will retry the 'tf get' later if this wasn't needed; this ordering
        # helps insure that old build was cleaned up with old Makefiles
        queue.append('NEEDS_TFGET=0')
        queue.append('')
        queue.append('if [ ! -d build ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing initial tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('else')
        queue.append('  NEEDS_TFGET=1')
        queue.append('fi')

        # Now generate the remainder of the command script
        queue.append('if [ ! -d build ]; then')
        queue.append('  echo "Error: \'build\' subdirectory does not exist!"')
        queue.append('  exit -1')
        queue.append('fi')
        queue.append('BASE_DIRECTORY=`pwd -P`')
        queue.append('cd build || exit $?')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing make distclean')
        queue.append('date')
        queue.append('chmod ug+x ./configure; ./configure')
        queue.append('make distclean')
        queue.append('echo')

        queue.append('')
        queue.append('if [ ${NEEDS_TFGET} -ne 0 ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('fi')

        if self.config.options.shelveset:
            shelvesetList = self.config.options.shelveset.split(',')
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing tf unshelve')
            queue.append('date')
            for shelveset in shelvesetList:
                queue.append('echo \'Unshelving shelveset: %s\'' % shelveset)
                queue.append('tf unshelve "%s"' % shelveset)
                queue.append('EXITSTATUS=$?')
                queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
            queue.append('echo')

        # Clean again - in case the shelveset - or tf get - fixed up clean code
        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing make distclean')
        queue.append('date')
        queue.append('chmod ug+x ./configure; ./configure')
        queue.append('make distclean')
        queue.append('echo')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing Determining debug/release')
        queue.append('date')

        config_options = ''
        if 'om' in self.config.configure_options:
            config_options = self.config.configure_options['om']

        if not self.config.options.debug:
            queue.append('echo "Performing RELEASE build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s)"' % config_options)
            queue.append('./configure %s' % config_options)
            queue.append('EXITSTATUS=$?')
        else:
            queue.append('echo "Performing DEBUG build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s --enable-debug)"' % config_options)
            queue.append('./configure %s --enable-debug' % config_options)
            queue.append('EXITSTATUS=$?')
        queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')

        if len(self.config.options.target) != 0:
            # Our target is?
            target = "all testrun"
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

            queue.append('make ' + target)
            queue.append('EXITSTATUS=$?')

        queue.append('echo')
        queue.append('echo Ending at:  `date`')

        # Only clean up if the make was successful and we unshelved something
        if not self.config.options.nocleanup and self.config.options.shelveset:
            queue.append('')
            queue.append('if [ $EXITSTATUS = 0 ]; then')
            queue.append('cd $BASE_DIRECTORY')
            self.BuildQueueCleanup_OM(queue)
            queue.append('fi')
            queue.append('')

    ##
    # Build queue of operations to perform on the remote systems (for CM)
    #
    def BuildQueue_CM(self, queue):
        self.BuildQueueInitialize(queue)
        self.BuildQueueCleanup_CM(queue)

        # Support handling if initial 'tf get' was not done
        #
        # We will retry the 'tf get' later if this wasn't needed; this ordering
        # helps insure that old build was cleaned up with old Makefiles
        queue.append('NEEDS_TFGET=0')
        queue.append('')
        queue.append('if [ ! -d Unix ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing initial tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('else')
        queue.append('  NEEDS_TFGET=1')
        queue.append('fi')

        # Now generate the remainder of the command script
        queue.append('if [ ! -d Unix ]; then')
        queue.append('  echo "Error: \'build\' subdirectory does not exist!"')
        queue.append('  exit -1')
        queue.append('fi')
        queue.append('BASE_DIRECTORY=`pwd -P`')
        queue.append('cd Unix || exit $?')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing make distclean')
        queue.append('date')
        queue.append('chmod ug+x ./configure; ./configure')
        queue.append('make distclean')
        queue.append('echo')

        queue.append('')
        queue.append('if [ ${NEEDS_TFGET} -ne 0 ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('fi')

        if self.config.options.shelveset:
            shelvesetList = self.config.options.shelveset.split(',')
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing tf unshelve')
            queue.append('date')
            for shelveset in shelvesetList:
                queue.append('echo \'Unshelving shelveset: %s\'' % shelveset)
                queue.append('tf unshelve "%s"' % shelveset)
                queue.append('EXITSTATUS=$?')
                queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
            queue.append('echo')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing Determining debug/release')
        queue.append('date')

        config_options = ''
        if 'cm' in self.config.configure_options:
            config_options = self.config.configure_options['cm']

        if not self.config.options.debug:
            queue.append('echo "Performing RELEASE build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s)"' % config_options)
            queue.append('./configure %s' % config_options)
            queue.append('EXITSTATUS=$?')
        else:
            queue.append('echo "Performing DEBUG build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s --enable-debug)"' % config_options)
            queue.append('./configure %s --enable-debug' % config_options)
            queue.append('EXITSTATUS=$?')
        queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing make depend')
        queue.append('date')
        queue.append('make depend')
        queue.append('echo')

        if len(self.config.options.target) != 0:
            # Our target is?
            target = "all release test"
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

        queue.append('echo')
        queue.append('echo Ending at:  `date`')

        # Only clean up if the make was successful and we unshelved something
        if not self.config.options.nocleanup and self.config.options.shelveset:
            queue.append('')
            queue.append('if [ $EXITSTATUS = 0 ]; then')
            queue.append('cd $BASE_DIRECTORY')
            self.BuildQueueCleanup_CM(queue)
            queue.append('fi')
            queue.append('')

    ##
    # Build queue of operations to perform on the remote systems (for VMM)
    #
    def BuildQueue_VMM(self, queue):
        self.BuildQueueInitialize(queue)
        self.BuildQueueCleanup_VMM(queue)

        # Support handling if initial 'tf get' was not done
        #
        # We will retry the 'tf get' later if this wasn't needed; this ordering
        # helps insure that old build was cleaned up with old Makefiles
        queue.append('NEEDS_TFGET=0')
        queue.append('')
        queue.append('if [ ! -d src ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing initial tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('else')
        queue.append('  NEEDS_TFGET=1')
        queue.append('fi')

        # Now generate the remainder of the command script
        queue.append('if [ ! -d src ]; then')
        queue.append('  echo "Error: \'src\' subdirectory does not exist!"')
        queue.append('  exit -1')
        queue.append('fi')
        queue.append('BASE_DIRECTORY=`pwd -P`')

        queue.append('')
        queue.append('echo')
        queue.append('echo ========================= Performing make distclean')
        queue.append('date')
        queue.append('make distclean')
        queue.append('echo')
        queue.append('')

        queue.append('')
        queue.append('if [ ${NEEDS_TFGET} -ne 0 ]; then')
        queue.append('  echo')
        queue.append('  echo ========================= Performing tf get')
        queue.append('  date')
        queue.append('  tf get')
        queue.append('  EXITSTATUS=$?')
        queue.append('  [ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
        queue.append('  echo')
        queue.append('fi')

        if self.config.options.shelveset:
            shelvesetList = self.config.options.shelveset.split(',')
            queue.append('')
            queue.append('echo')
            queue.append('echo ========================= Performing tf unshelve')
            queue.append('date')
            for shelveset in shelvesetList:
                queue.append('echo \'Unshelving shelveset: %s\'' % shelveset)
                queue.append('tf unshelve "%s"' % shelveset)
                queue.append('EXITSTATUS=$?')
                queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')
            queue.append('echo')

        config_options = ''
        if 'vmm' in self.config.configure_options:
            config_options = self.config.configure_options['vmm']

        if not self.config.options.debug:
            queue.append('echo "Performing RELEASE build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s)"' % config_options)
            queue.append('./configure %s' % config_options)
            queue.append('EXITSTATUS=$?')
        else:
            queue.append('echo "Performing DEBUG build"')
            if config_options:
                queue.append('echo "  (Configuration options: %s --enable-debug)"' % config_options)
            queue.append('./configure %s --enable-debug' % config_options)
            queue.append('EXITSTATUS=$?')
        queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')

        if len(self.config.options.target) != 0:
            # Our target is?
            target = "all test release"
            if self.config.options.target != "target_default":
                target = self.config.options.target

            queue.append('')
            queue.append('echo')
            queue.append('echo \'========================= Performing make ' + target + '\'')
            queue.append('date')

            queue.append('echo \'========================= Performing make %s ' % target + '\'')
            queue.append('make %s ' % target)
            queue.append('MAKE_STATUS=$?')
            queue.append('if [ $MAKE_STATUS -ne 0 ]; then')
            queue.append('    EXITSTATUS=$MAKE_STATUS')
            queue.append('fi')        

        queue.append('echo')
        queue.append('echo Ending at:  `date`')

        # Only clean up if the make was successful and we unshelved something
        if not self.config.options.nocleanup and self.config.options.shelveset:
            queue.append('')
            queue.append('if [ $EXITSTATUS = 0 ]; then')
            queue.append('cd $BASE_DIRECTORY')
            self.BuildQueueCleanup_VMM(queue)
            queue.append('fi')
            queue.append('')

    ##
    # Build queue of operations to perform on the remote systems (for non-integrated builds)
    #
    def BuildQueue_NIP(self, queue):
        self.BuildQueueInitialize(queue)

        # Prior to writing the script, the script name is written to variable $SCRIPTNAME

        queue.append('echo')
        queue.append('echo ========================= Performing Starting NIP build')
        queue.append('')
        queue.append('# This script is a bundle file for PBUILD non-integrated projects.  In this')
        queue.append('# model, the PBUILD-generated command script contains both commands to perform')
        queue.append('# the build as well as the package itself to build.  It is the job of this')
        queue.append('# script to separate the .tar container file from the command script, unpack')
        queue.append('# the .tar container file, and perform the build.')
        queue.append('')
        queue.append('# Note: We can\'t use \'sed\' to strip the script from the binary package.')
        queue.append('# That doesn\'t work on AIX 5, where \`sed\` did strip the binary package')
        queue.append('# AND null bytes, created a corrupted stream.')
        queue.append('')
        queue.append('set +e')
        queue.append('# set -x')
        queue.append('')
        queue.append('PATH=/usr/bin:/bin')
        queue.append('umask 022')
        queue.append('')
        queue.append('# Can\'t use something like \'readlink -e $0\' because that doesn\'t work everywhere')
        queue.append('# And HP doesn\'t define $PWD in a sudo environment, so we define our own')
        queue.append('case $0 in')
        queue.append('    /*|~*)')
        queue.append('        SCRIPT_INDIRECT="`dirname $0`"')
        queue.append('        ;;')
        queue.append('    *)')
        queue.append('        PWD="`pwd`"')
        queue.append('        SCRIPT_INDIRECT="`dirname $PWD/$0`"')
        queue.append('        ;;')
        queue.append('esac')
        queue.append('SCRIPT_DIR="`(cd \"$SCRIPT_INDIRECT\"; pwd -P)`"')
        queue.append('SCRIPT="$SCRIPT_DIR/`basename $0`"')
        queue.append('')
        queue.append('# These symbols will get replaced during the bundle creation process.')
        queue.append('#')
        queue.append('')
        queue.append('SCRIPT_LEN=<SCRIPT_LEN>')
        queue.append('SCRIPT_LEN_PLUS_ONE=<SCRIPT_LEN+1>')
        queue.append('')

        queue.append('echo')
        queue.append('echo ========================= Performing Clensing prior builds')
        queue.append('rm -rf %s/*' % self.path)
        queue.append('')

        queue.append('echo')
        queue.append('echo ========================= Performing Extracting binary payload')
        queue.append('TAIL_CQUAL=""')
        queue.append('[ `uname` != "SunOS" ] && TAIL_CQUAL="-n"')
        queue.append('tail $TAIL_CQUAL +${SCRIPT_LEN_PLUS_ONE} "${SCRIPT}" | tar xf -')
        queue.append('EXITSTATUS=$?')

        if not self.diagnoseErrors:
            queue.append('[ -n "${SCRIPTNAME}" ] && rm ${SCRIPTNAME}')

        queue.append('if [ ${EXITSTATUS} -ne 0 ]')
        queue.append('then')
        queue.append('    echo "Failed: could not extract the install bundle."')
        queue.append('    exit ${EXITSTATUS}')
        queue.append('fi')
        queue.append('echo "Binary payload has been extracted successfully ..."')

        if len(self.config.options.target) != 0:
            # Our target is?
            target = "all tests"
            if self.config.options.target != "target_default":
                target = self.config.options.target

            if not target.lower().startswith('none;'):
                queue.append('echo')
                queue.append('echo ========================= Performing Determining debug/release')
                queue.append('date')

                config_options = ''
                if 'nip' in self.config.configure_options:
                    config_options = self.config.configure_options['nip']

                    if not self.config.options.debug:
                        queue.append('echo "Performing RELEASE build"')
                        if config_options:
                            queue.append('echo "  (Configuration options: %s)"' % config_options)
                        queue.append('./configure %s' % config_options)
                        queue.append('EXITSTATUS=$?')
                    else:
                        queue.append('echo "Performing DEBUG build"')
                        if config_options:
                            queue.append('echo "  (Configuration options: %s --enable-debug)"' % config_options)
                        queue.append('./configure %s --enable-debug' % config_options)
                        queue.append('EXITSTATUS=$?')
                    queue.append('[ $EXITSTATUS != 0 ] && exit $EXITSTATUS')

                # Start running the 'make' targets
                # Split our targets into a list
                targets = target.split()

                for target in targets:
                    queue.append('')
                    queue.append('echo')
                    queue.append('echo \'========================= Performing make %s ' % target + '\'')
                    queue.append('date')
                    queue.append('make %s ' % target)
                    queue.append('MAKE_STATUS=$?')
                    queue.append('if [ $MAKE_STATUS -ne 0 ]; then')
                    queue.append('    EXITSTATUS=$MAKE_STATUS')
                    queue.append('    exit $EXITSTATUS')
                    queue.append('fi')

            else:
                # We have a target like: "none;<something>" - treat "<something>" like a command
                command = target.split(';', 1)[1]
                queue.append('')
                queue.append('echo')
                queue.append('echo \'========================= Performing Command: %s ' % command + '\'')
                queue.append('date')
                queue.append('echo "Executing: %s"' % command)
                queue.append(command)
                queue.append('EXITSTATUS=$?')
                queue.append('[ $EXITSTATUS -ne 0 ] && echo "Command execution failed!"')

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

        outfname = '%s%s%s%s.log' % (self.logPrefix, activeStr, self.tag, self.branchSpec)

        if self.deleteLogfiles:
            for prefix in [ '', 'active-', 'done-', 'failed-' ]:
                try:
                    os.remove('%s%s%s%s.log' % (self.logPrefix, prefix, self.tag, self.branchSpec))
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
                ['ssh', self.hostname, 'chmod 755 ' + self.destinationName + '; bash ' + self.destinationName],
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

            newfname = '%s%s%s%s.log' % (self.logPrefix, completionStr, self.tag, self.branchSpec)
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
        if not self.diagnoseErrors and not self.config.options.container:
            self.queue.insert(1, 'rm ' + self.destinationName)
        else:
            self.queue.insert(1, 'echo \'Executing script %s\'' % self.destinationName)

        self.queue.insert(2, 'echo "Executing on host $HOSTNAME (%(TAG)s: %(HOST)s)"' \
                              % {'TAG' : self.tag, 'HOST' : self.hostname } )
        self.queue.insert(3, 'cd %s || exit $?' % self.path)
        self.queue.insert(4, '')

        # We assume that $EXITSTATUS was previously set by project-specific queue code
        self.queue.append('echo ========================= Performing Finishing up\; status=$EXITSTATUS')
        self.queue.append('exit $EXITSTATUS')

        # If we're a container file:
        #   Leave a marker so primary script knows our own name ($SCRIPTNAME)
        #   Do script length substitutions
        if self.config.options.container:
            self.queue.insert(2, 'SCRIPTNAME=\'%s\'' % self.destinationName)

            # WARNING: DO NOT MODIFY LENGTH OF self.queue AFTER THIS POINT!

            self.queue = [ line.replace('<SCRIPT_LEN>', str( len(self.queue)) )
                           for line in self.queue ]
            self.queue = [ line.replace('<SCRIPT_LEN+1>', str( len(self.queue)+1) )
                           for line in self.queue ]

        # Generate a temporary file with all of our commands

        tmpfile = tempfile.NamedTemporaryFile()

        for command in self.queue:
            tmpfile.write(command + '\n')

        # Append our container file if we have one

        if self.config.options.container:
            containerFile = file(self.config.options.container, 'rb')
            shutil.copyfileobj( containerFile, tmpfile )
            containerFile.close()

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

            outfname = '%s%s%s%s.log' % (self.logPrefix, completionStr, self.tag, self.branchSpec)
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
        #    . "Branch"
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
        stdscr.addstr(lastLine, 0, 'Branch:')
        if self.config.GetBranchSpecification() != '':
            stdscr.addstr(lastLine, 15, self.config.GetBranchSpecification())
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
