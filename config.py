# coding: utf-8
#
# Copyright (c) Microsoft Corporation.  All rights reserved.
#
##
# Module containing base classes to load configuration
#
# Date:   2008-11-14
#

import os
from stat import *
import subprocess
import sys

##
# Class containing machine defitions
#
class MachineItem:
    ##
    # Ctor.
    # \param[in] Host key
    # \param[in] Machine address
    # \param[in] Destination path
    def __init__(self, host, path, project):
        self.host = host
        self.path = path
        self.project = project

    ##
    # Return the host name associated with an entry
    #
    def GetHost(self):
        return self.host

    ##
    # Return the directory path associated with an entry
    #
    def GetPath(self):
        return self.path

    ##
    # Return the project associated with an entry
    #
    def GetProject(self):
        return self.project


##
# Class containing generic logic for loading and handling configuration file
#
class Configuration:
    ##
    # Ctor.
    # \param[in] configuration Configuration map.
    #
    def __init__(self, options, args):
        self.options = options
        self.args = args

        self.hostlist = []
        self.machines = {}
        self.machines_allbranches = {}
        self.currentSettings = {}
        self.excludeList = []
        self.cacheSetting = ''
        self.test_attr = ''
        self.test_list = ''

        if self.options.branch != None:
            self.branch = self.options.branch
        else:
            self.branch = ''

        # Define the valid settings options (can be prefixed with "no")
        # Set the default settings along the way.  Can be overridden by:
        #   1. Configuration file
        #   2. Command line option

        self.validSettings = [ 'deletelogfiles', 'diagnoseerrors', 'logfilebranch', 'logfilerename', 'progress', 'summaryscreen', 'tfproxstart' ]
        self.ParseSettings('defaults', 'DeleteLogfiles,NoDiagnoseErrors,NoLogfileBranch,NoLogfileRename,Progress,SummaryScreen,TFProxStart')

        # Default location for PBUILD logfiles (include trailing "/" in path)
        self.logfilePrefix = os.path.join(os.path.expanduser('~'), '')
        self.logfilePriorPrefix = ''

        # Configuration file is in ~/.pbuild, or overridden via PBUILD (env)
        # (If PBUILD defined but empty, just revert to the default)
        try:
            self.configurationFilename = os.environ['PBUILD']
        except KeyError:
            self.configurationFilename = ''

        if len(self.configurationFilename) == 0:
            self.configurationFilename = os.path.join(os.path.expanduser('~'), '.pbuild')

        # Data structure for parsing "cache" qualifier
        #
        # This is a list of valid cache types (with proper capitalization).
        # Each entry represents a valid option for the "cache" qualifier.
        #
        # For each entry in the cache parse data structure:
        # If the second entry is a tuple, the tuple represents valid options.
        # If the second entry is a string, a simple substitution is performed.
        #
        # Entries with tuples are expected to be specified as: "key=value"
        # Entries without tuples are expected to be specified as: "key" (no '=')

        self.cacheParseData = (
                ( "BUILD_TYPE",             ("Debug", "Release")),
                ( "BUILD_PROFILING",        ("false", "prof",  "purify",  "gprof",  "quantify")),
                ( "BUILD_PEGASUS",          ("true",  "false")),
                ( "BUILD_PEGASUS_DEBUG",    ("true",  "false")),
                ( "SCX_STACK_ONLY",         ("true",  "false")),

                ( "RESET",        "BUILD_TYPE=Release BUILD_PROFILING=false BUILD_PEGASUS=true BUILD_PEGASUS_DEBUG=false UNITTESTS_SUBSET= " ),
                ( "DEBUG",        "BUILD_TYPE=Debug BUILD_PEGASUS_DEBUG=true" ),
                ( "RELEASE",      "BUILD_TYPE=Release BUILD_PEGASUS_DEBUG=false" ),
                ( "NOUNITTESTS",  "UNITTESTS_SUBSET=" ),
                ( "SCXONLY",      "BUILD_PEGASUS=false" ),
                ( "ALL",          "BUILD_PEGASUS=true" )
            )

    ##
    # Get the branch to build.  If empty, no branch specifications are allowed
    # (for backwards compatibility).
    #
    def GetBranchSpecification(self):
        return self.branch.lower()

    ##
    # Get the configuration filename.  Controlled by environment variable
    # 'PBUILD', defaults to '~./pbuild'.
    #
    def GetConfigurationFilename(self):
        return self.configurationFilename

    ##
    # Get the log file prefix - the directory path to write the log files to
    #
    # This method should return a trailing "/" in the directory path (so we
    # can simply append the filename that we need).
    #
    def GetLogfilePrefix(self):
        return self.logfilePrefix

    ##
    # Get the prior log file prefix - the directory path to save prior log files to
    #
    # This method should return a trailing "/" in the directory path (so we
    # can simply append the filename that we need).  If this method returns
    # the empty string, then no prior logfile directory is defined.
    #
    def GetLogfilePriorPrefix(self):
        return self.logfilePriorPrefix

    ##
    # Get a settings value
    # \throw if setting is not valid
    #
    def GetSetting(self, setting):
        if setting.lower() in self.currentSettings:
            return self.currentSettings[setting.lower().strip()]
        else:
            raise KeyError

    ##
    # Get the test attributes - the list of attributes that tests are restricted to
    #
    def GetTestAttributes(self):
        return self.test_attr

    ##
    # Get the test list - the list of test names to include or exclude from the run
    #
    def GetTestList(self):
        return self.test_list

    ##
    # Parse cache settings
    #
    # Cache settings can be space or comma delimited.  Each cache setting can
    # be of the form "shortcut" or "key=value".  For ease of entry:
    #   > Abbreviations are allowed as long as they're unique
    #   > Case is not important
    #
    # When a matching entry is found, we substitute exactly since Makefiles do
    # care about case and do not allow abbreviations.
    # 
    def ParseCacheSpec(self, cachestring):
        cacheReturn = ''
        cachelist = cachestring.replace(',', ' ').split()
        for entry in cachelist:
            # Strip off any '=' parameter, and do some basic validation
            entrylist = entry.split('=')
            if len(entrylist) == 2 and len(entrylist[0]) > 0 and len(entrylist[1]) > 0:
                (key, value) = entrylist
            elif len(entrylist) == 1 and len(entrylist[0]) > 0:
                (key, value) = (entrylist[0], None)
            else:
                sys.stderr.write('Invalid cache setting: %s\n' % entry)
                sys.exit(-1)

            #
            # Try to find a match in our valid cache parse list
            #
            matchKey = None
            matchValue = None

            for element in self.cacheParseData:
                assert isinstance(element[1], tuple) or isinstance(element[1], str)
                if len(entrylist) == 2 and isinstance(element[1], tuple):
                    # Handle cache specifications like "key=value"

                    # If this entry doesn't match user spec, move along
                    if not element[0].lower().startswith(key.lower()):
                        continue

                    # Check for non-unique specification
                    if matchKey:
                        sys.stderr.write('Cache key \'%s\' is not unique\n' % key)
                        sys.exit(-1)
                    matchKey = element[0]

                    # We have a match, so try to find matching value
                    for valueEntry in element[1]:
                        if valueEntry.lower().startswith(value.lower()):
                            if matchValue:
                                sys.stderr.write('Cache key \'%s\' has value \'%s\' that is not unique\n' % (key, value))
                                sys.exit(-1)
                            matchValue = valueEntry

                    # Handle exact match as a special case (one key is substring of another)
                    if element[0].lower() == key.lower():
                        break

                elif len(entrylist) == 1 and isinstance(element[1], str):
                    # Handle cache specifications like "key"

                    if element[0].lower().startswith(key.lower()):
                        if matchKey or matchValue:
                            sys.stderr.write('Cache key \'%s\' is not unique\n' % key)
                            sys.exit(1)
                        matchValue = element[1]

            if matchKey and matchValue:
                # Add a new setting like 'key=value'
                cacheReturn = '%s%s=%s ' % (cacheReturn, matchKey, matchValue)
            elif matchValue:
                # Add a new setting (simple substitution)
                cacheReturn = '%s%s ' % (cacheReturn, matchValue)
            else:
                sys.stderr.write('Unmatched cache setting: %s\n' % entry)
                sys.exit(-1)

        return cacheReturn

    ##
    # Parse a settings string and set the appropriate settings
    #
    def ParseSettings(self, source, settings):
        settingsList = settings.lower().replace(',', ' ').split()

        for entry in settingsList:
            # Check for negative ('no' prefix)
            positive = True
            if entry.startswith('no'):
                entry = entry.replace('no', '', 1)
                positive = False

            if entry in self.validSettings:
                self.currentSettings[entry] = positive
            else:
                sys.stderr.write('Invalid setting found in %s: [no]%s\n' % (source, entry))
                sys.exit(-1)

    ##
    # Parse a host name entry from the configuration file
    #
    # Host entries can be of the following format:
    #       tag  host  directory	           (does not allow projects or branches)
    # host: tag  host  directory  branch           (does not allow projects - only OM)
    # host: tag  host  directory  branch  project  (allows both branches and projects)
    #
    def ParseHostEntry(self, elements, keylist, hostlist, keylist_global):
        line = elements.rstrip()
        elements = elements.rstrip().split()
        project = ""

        # Was both a branch and project specified on this host entry?
        if len(elements) == 5:
            if self.GetBranchSpecification() == '':
                sys.stderr.write('Branches disabled with branch specification on host entry - offending line:\n'
                                 + '\'' + line.rstrip() + '\'\n')
                sys.exit(-1)

            project = elements[4].lower()
            if project <> 'om' and project <> 'cm' and project <> 'nw' and project <> 'vmm' and project <> 'omi':
                raise IOError('Bad project in configuration file - offending line: \'' + line.rstrip() + '\'')

            # No match for this branch?  Just skip the host entry ...
            if elements[3].lower() != self.GetBranchSpecification():
                # But first: Add this machine to the list of machines for all branches
                branch_key = "%s<>branch_sep<>%s" % (elements[3], elements[0])

                if branch_key in keylist_global:
                    sys.stderr.write('Duplicate key "%s" found in configuration for branch "%s"\n'
                                     % (branch_key, elements[3]))
                    sys.exit(-1)

                keylist_global.append(branch_key)
                self.machines_allbranches[branch_key] = MachineItem(elements[1], elements[2], "")

                return


        # Was a branch specified on this host entry (without a project)?
        elif len(elements) == 4:
            # If we're allowing branches, then a branch must be specified for the build
            if self.GetBranchSpecification() == '':
                sys.stderr.write('Branches disabled with branch specification on host entry - offending line:\n'
                                 + '\'' + line.rstrip() + '\'\n')
                sys.exit(-1)

            # No match for this branch?  Just skip the host entry ...
            if elements[3].lower() != self.GetBranchSpecification():
                # But first: Add this machine to the list of machines for all branches
                branch_key = "%s<>branch_sep<>%s" % (elements[3], elements[0])

                if branch_key in keylist_global:
                    sys.stderr.write('Duplicate key "%s" found in configuration for branch "%s"\n'
                                     % (branch_key, elements[3]))
                    sys.exit(-1)

                keylist_global.append(branch_key)
                self.machines_allbranches[branch_key] = MachineItem(elements[1], elements[2], "")

                return

        elif len(elements) == 3:
            if self.GetBranchSpecification() != '':
                sys.stderr.write('Branches enabled without branch specification on host entry - offending line:\n'
                                 + '\'' + line.rstrip() + '\'\n')
                sys.exit(-1)

        else:
            raise IOError('Bad configuration file - offending line: \'' + line.rstrip() + '\'')

        if elements[0] in keylist:
            sys.stderr.write('Duplicate key "%s" found in configuration\n' % elements[0])
            sys.exit(-1)

        if elements[1] in hostlist:
            sys.stderr.write('Duplicate host "%s" found in configuration\n' % elements[1])
            sys.exit(-1)

        # Add to list of machines for all branches
        if len(elements) > 3:
            branch_key = "%s<>branch_sep<>%s" % (elements[3], elements[0])
        else:
            branch_key = "<>branch_sep<>%s" % elements[0]

        if branch_key in keylist_global:
            sys.stderr.write('Duplicate key "%s" found in configuration for branch "%s"\n'
                             % (branch_key, elements[3]))
            sys.exit(-1)

        keylist_global.append(branch_key)
        self.machines_allbranches[branch_key] = MachineItem(elements[1], elements[2], "")

        # Add to list of machines to process (branch-specific)
        keylist.append(elements[0])
        hostlist.append(elements[1])
        self.machines[elements[0]] = MachineItem(elements[1], elements[2], project)

    ##
    # Parse a test attribute string and set the appropriate settings
    #
    # For now, attributes can only be: 'SLOW' or '-SLOW'.
    #
    # We allow mixed case, but beyond that, simple validation (no abbreviations).
    # This can be extended if list of test attributes gets more extensive.
    #
    def ParseTestAttributes(self, source, attributes):
        if attributes == '' or attributes.lower() == 'slow' or attributes.lower() == '-slow':
            self.test_attr = attributes.upper()
        else:
            sys.stderr.write('Invalid test attribute found in %s: %s\n' % (source, attributes))
            sys.exit(-1)

    ##
    # Read and parse the configuration file
    #
    def LoadConfigurationFile(self):
        # (Keep track of a global keylist for all branches for --initialize)
        keylist = []
        hostlist = []
        keylist_global = []

        # Load the configuration file - and verify it, line by line
        f = open(self.configurationFilename, 'r')

        for line in f:
            if line.strip() != "" and not line.lstrip().startswith('#'):
                # Strip off any in-line comment
                line = line.split('#')[0]

                elements = line.rstrip().split(':')

                # No header at all: Assume it's a host
                if len(elements) == 1:
                    self.ParseHostEntry(line.rstrip(), keylist, hostlist, keylist_global)

                # Also allow "host:" to explicitly define a host
                elif len(elements) == 2 and elements[0].strip().lower() == "host":
                    self.ParseHostEntry(elements[1].rstrip(), keylist, hostlist, keylist_global)

                # Allow "branch:" to sepcify default branch to build for all builds
                elif len(elements) == 2 and elements[0].strip().lower() == "branch":
                    self.branch = elements[1].strip()
                    if self.options.branch != None:
                        self.branch = self.options.branch

                # Allow "cache:" to specify default cache settings for all builds
                elif len(elements) == 2 and elements[0].strip().lower() == "cache":
                    self.cacheSetting = self.ParseCacheSpec(elements[1].strip())

                # Allow "exclude:" to specify a list of hosts to exclude
                elif len(elements) == 2 and elements[0].strip().lower() == "exclude":
                    self.excludeList = elements[1].strip().split(',')

                # Allow "logdir:" to specify the directory used for log files
                elif len(elements) == 2 and elements[0].strip().lower() == "logdir":
                    self.logfilePrefix = elements[1].strip().replace('~/', os.path.join(os.path.expanduser('~'), ''))
                    # Include trailing "/" in path
                    self.logfilePrefix = os.path.join(self.logfilePrefix, '')

                # Allow "logdir_prior:" to specify the directory used for prior log files
                elif len(elements) == 2 and elements[0].strip().lower() == "logdir_prior":
                    self.logfilePriorPrefix = elements[1].strip().replace('~/', os.path.join(os.path.expanduser('~'), ''))
                    # Include trailing "/" in path
                    self.logfilePriorPrefix = os.path.join(self.logfilePriorPrefix, '')

                # Allow "settings:" to override the default settings
                elif len(elements) == 2 and elements[0].strip().lower() == "settings":
                    self.ParseSettings("configuration file", elements[1].strip())

                # Allow "test_attributes:" to specify the test attributes to use
                elif len(elements) == 2 and elements[0].strip().lower() == "test_attributes":
                    self.ParseTestAttributes("configuration file", elements[1].strip())

                # Allow "test_names:" to specify the list of tests to run or exclude
                elif len(elements) == 2 and elements[0].strip().lower() == "test_list":
                    self.test_list = elements[1].strip()

                else:
                    raise IOError('Bad configuration file - offending line: \'' + line.rstrip() + '\'')
        f.close()

        # Handle override for cache settings in the configuration file by command line
        if self.options.cache != None:
            self.cacheSetting = self.ParseCacheSpec(self.options.cache)

        # Handle override for exclude list in the configuration file by command line
        if self.options.exclude != None:
            self.excludeList = self.options.exclude.replace(',', ' ').split()

        # Handle override for logdir (and logdir_prior) in the configuration file by command line
        if self.options.logdir != None:
            self.logfilePrefix = self.options.logdir.replace('~/', os.path.join(os.path.expanduser('~'), ''))

            # Include trailing "/" in path
            self.logfilePrefix = os.path.join(self.logfilePrefix, '')

        if self.options.logdir_prior != None:
            self.logfilePriorPrefix = self.options.logdir_prior.replace('~/', os.path.join(os.path.expanduser('~'), ''))

            # Include trailing "/" in path
            self.logfilePriorPrefix = os.path.join(self.logfilePriorPrefix, '')

        # Handle override for settings in configuration file by command line
        # (As optimization, --nocurses forces no progress updates)
        if self.options.settings != None:
            self.ParseSettings("command line", self.options.settings)

        if self.options.nocurses:
            self.ParseSettings('optimization', 'NoProgress')

        # Handle override for test attributes in configuration file by command line
        if self.options.test_attrs != None:
            self.ParseTestAttributes("command line", self.options.test_attrs)

        # Handle override for test list in the configuration file by command line
        if self.options.tests != None:
            self.test_list = self.options.tests

        # Try to write a file to the log directory to be certain we can!
        # (and, in case it's defined, test the prior log directory as well)
        self.VerifyLogdirWritable(self.GetLogfilePrefix())
        if self.GetLogfilePriorPrefix() != '':
            self.VerifyLogdirWritable(self.GetLogfilePriorPrefix())

        # Be sure we have at least one host to deal with ...
        if len(keylist) == 0:
            if self.GetBranchSpecification() != '':
                sys.stderr.write('No host entries found for branch \''
                                 + self.GetBranchSpecification()
                                 + '\' in pbuild configuration file\n')
            else:
                sys.stderr.write('No host entries found in pbuild configuration file\n')

            sys.exit(-1)

        # Final processing:
        #   Be sure that we have all of our SSH host keys set up
        #   Validate the host list
        self.InitializeSSH()
        self.ValidateHostList()

    ##
    # Initialize SSH known hosts
    #
    # We use file '~/.pbuild_init' to track when we were last initialized.
    # If configuration file is newer than initialization file, we init again.
    # This helps insure that we have SSH certificates for all of the hosts.
    #
    def InitializeSSH(self):
        pbuildInitialized = False
        initFilename = os.path.join(os.path.expanduser('~'), '.pbuild_init')
        try:
            initStat = os.stat(initFilename)
            configStat = os.stat(self.GetConfigurationFilename())

            if configStat[ST_MTIME] < initStat[ST_MTIME]:
                pbuildInitialized = True
        except OSError:
            pass

        if pbuildInitialized and not self.options.initialize:
            return True

        # Try and remove the file if it exists
        try:
            os.remove(initFilename)
        except OSError:
            # If the file doesn't exist, that's fine
            pass

        # We use complete host list rather than hosts specified on command line
        # Also, we 'cd' to base directory on host to verify that it exists
        hostsOK = True
        for key in sorted(self.machines_allbranches.keys()):
            (branch, tag) = key.split('<>branch_sep<>', 1)

            if branch == '':
                print "Checking host:", self.machines_allbranches[key].GetHost()
            else:
                print "Checking host: %s (Branch: %s)" % (self.machines_allbranches[key].GetHost(), branch)

            process = subprocess.Popen(
                ['ssh', self.machines_allbranches[key].GetHost(), 'cd %s' % (self.machines_allbranches[key].GetPath())],
                stdin=subprocess.PIPE
                )
            process.wait()

            if process.returncode != 0:
                hostsOK = False

        if hostsOK:
            # If all hosts are okay, create marker file
            initFile = open(initFilename, 'w')
            initFile.close()

        return hostsOK

    ##
    # Normalize host specification
    #
    # We support host specifications (in list of machines to include) in one of two
    # forms: host "tags" (used for log file names), and DNS name/IP number.  However,
    # code in pbuild expects hosts to solely be in "tag" form.
    #
    # This function will "normalize" host specifications.  Input is any supported
    # form, output is the associated tag.
    #
    def NormalizeHostSpec(self, hostSpec):
        try:
            # Do the easy thing first: is the entry a tag for a host?
            if self.machines[hostSpec]:
                return hostSpec;
        except KeyError:
            # Nope - so loop thorugh our list of hosts looking that way
            for key in self.machines:
                if self.machines[key].GetHost() == hostSpec:
                    return key;

        sys.stderr.write('Failed to identify host \'%s\' in configuration\n' % hostSpec)
        sys.exit(-1)

    ##
    # Validate specific list of hosts if one was specified
    #
    # For a match, we allow either the entry tag for a host or the hostname itself
    # Take care to not allow the same machine to be specified twice in the resulting list
    #
    def ValidateHostList(self):
        # Build a list of machines to process (if none, we simply process all hosts)
        for entry in self.args:
            host = self.NormalizeHostSpec(entry)
            self.hostlist.append(host)

        # Support the list of machines to exclude if one was specified
        if len(self.excludeList):
            # If no hosts specified to include, then let's include all hosts
            fAllHosts = False
            if len(self.hostlist) == 0:
                for key in sorted(self.machines.keys()):
                    self.hostlist.append(key)
                fAllHosts = True

            # Now exclude each of the hosts specified in the exclude list
            for entry in self.excludeList:
                host = self.NormalizeHostSpec(entry)

                # If host wasn't in our list, then must be specific list of
                # hosts to build - that's not an error condition
                #
                # Don't remove host that's specifically included in include list
                if host in self.hostlist and fAllHosts:
                    self.hostlist.remove(host)

        # Okay, we're done.  State of the world:
        #
        # If self.hostlist is empty, then all machines should be processed
        # Else self.hostlist is the list of tags to process (perhaps pruned by the exclude list)

    ##
    # Verify that our logfile directory is writable
    #
    def VerifyLogdirWritable(self, dirpath):
        # Try to write a file to the log directory to be certain we can!
        outfname = dirpath + '.pbuild_logtest.log'

        try:
            try:
                os.remove(outfname)
            except OSError:
                # Problems removing for now?  That's fine
                pass

            # Open the output file
            outf = open(outfname, 'a+')
            outf.close()

            os.remove(outfname)
        except:
            sys.stderr.write('Error writing or deleting during logfile write test - filename \'%s\'\n' % outfname)
            sys.exit(-1)
