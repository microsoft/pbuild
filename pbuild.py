#coding: utf-8
#
##
# Contains main program to do distributed developer builds
#

from optparse import OptionParser
import sys
import os
from stat import *

from config import Configuration
from config import MachineItem
from builder import Builder

##
# Main program class
#
class pbuild:
    ##
    # Handle program parameters
    #
    def ParseParameters(self):
        # Get all command line parameters and arguments
        parser = OptionParser(
            usage="usage: %prog [option-list] [host-list]   (use --help or -h for help)",
            description=
                "pbuild will allow you to do a build across all platforms using your own "
                "git clones. If a build problem occurs, all files are left completely intact, "
                "simplifying the steps you must perform to replicate the problem. "
                "pbuild supports a wide variety of options, specified below.  For more "
                "information, view the README file checked in with pbuild."
            )

        parser.add_option("", "--abortOnError",
                          action="store_true", dest="abort", default=False,
                          help="Immediately aborts when the first remote build fails (for future - do not use yet)")

        parser.add_option("", "--attributes",
                          type="string",
                          dest="test_attrs",
                          help="Specifies the unit test attributes that you wish to use to restrict unit tests")

        parser.add_option("-b", "--branch",
                          type="string",
                          dest="branch",
                          help="Selects the branch for the top level project or superproject")

        parser.add_option("-d", "--debug",
                          action="store_true", dest="debug", default=False,
                          help="Build targets in DEBUG mode")

        parser.add_option("", "--clone",
                          action="store_true", dest="clone", default=False,
                          help="Forces a new clone of the repository, even if repository already exists")

        parser.add_option("", "--command",
                          type="string",
                          dest="command",
                          help="Executes the specified command string rather than buiding/running a command script to perform a remote build")

        parser.add_option("", "--exclude",
                          type="string",
                          dest="exclude",
                          help="Overrides default exclude list from configuration file (if any); comma-separated list of hosts to exclude from the build")

        parser.add_option("", "--initialize",
                          action="store_true", dest="initialize", default=False,
                          help="Verify public keys in known_hosts file")

        parser.add_option("-l", "--list",
                          action="store_true", dest="list", default=False,
                          help="List host configuration information and exit")

        parser.add_option("", "--logdir",
                          type="string",
                          dest="logdir",
                          help="Overrides 'logdir' from configuration file")

        parser.add_option("", "--logdir_prior",
                          type="string",
                          dest="logdir_prior",
                          help="Overrides 'logdir_prior' from configuration file")

        parser.add_option("", "--nodebug",
                          action="store_true", dest="nodebug", default=False,
                          help="Build targets in NODEBUG mode")

        parser.add_option("", "--nocurses",
                          action="store_true", dest="nocurses", default=False,
                          help="Disable curses for dynamic screen updating (may be useful for diagnostic purposes)")

        parser.add_option("", "--select",
                          type="string",
                          dest="select",
                          help="Select specification to build (only build hosts with this select specification)")

        parser.add_option("", "--settings",
                          type="string",
                          dest="settings",
                          help="Overrides default settings from program and configuration file (i.e. 'ShowSummary,LogFile')")

        parser.add_option("-s", "--subproject",
                          type="string",
                          dest="subproject",
                          help="Comma-separated list of subproject:branch pairs to select branches in subprojects, like \"opsmgr:jeff-sun,pal:jeff-sun\"")

        parser.add_option("-t", "--target",
                          type="string",
                          default="target_default",
                          dest="target",
                          help="Specifies the build target to use for the 'make' command (default: 'testrun').  Set target as empty string to avoid the 'make' step (useful to, say, undo changes on a host)")

        parser.add_option("", "--tests",
                          type="string",
                          dest="tests",
                          help="Specifies the subset of unit tests that you wish to run (if the target includes \"testrun\"); may be a comma-separated list")

        (options, args) = parser.parse_args()

        # Basic error checking

        if len(args) and options.list:
            parser.error('Option --list conflicts with other specified options\n')

        if options.list and options.command:
            parser.error('Option --command conflicts with option --list\n')

        if options.debug and options.nodebug:
            parser.error('Options --debug and --nodebug conflict with one another')

        if options.branch or options.debug or options.nodebug or options.subproject:
            # We're doing some kind of a build: Be sure there's no conflict with other qualifiers
            if options.command:
                parser.error('Option --command conflicts with other specified options\n')

        # Save command line arguments for later interpretation
        self.options = options
        self.args = args

    ##
    # Main program
    #
    def main(self):

        # Get command line parameters
        self.ParseParameters()

        # Go load configuration information
        config = Configuration(self.options, self.args)
        config.LoadConfigurationFile()

        # Support for the --list qualifier
        if self.options.list:
            print "Logfile Directory:", config.GetLogfilePrefix()
            print "Select:           ", config.GetSelectSpecification()
            print "Settings:         ", config.currentSettings
            print "\n"
            print "%-20s %-10s %s" % ("Machine Tag", "Project", "Host Address")
            print "%-20s %-10s %s\n" % ("-----------", "-------", "------------")

            # We really prefer to list sorted by tags, so do so
            machines_byTag = {}
            for key in config.machines.keys():
                machines_byTag[config.machines[key].GetTag()] = config.machines[key]
            for key in sorted(machines_byTag.keys()):
                print "%-20s %-10s %s" % (machines_byTag[key].GetTag() + ':', machines_byTag[key].GetProject(), machines_byTag[key].GetHost())
            return 0

        # Go start the build process (and return resulting status)
        build = Builder(config)
        return build.StartBuild()


if __name__ == '__main__':
    exitStatus = pbuild().main()
    if exitStatus:
        sys.exit( exitStatus )

    # Fall through for successful exit
