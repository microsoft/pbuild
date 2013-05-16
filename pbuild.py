#coding: utf-8
#
##
# Contains main program to do distributed developer builds
#

from optparse import OptionParser
import sys

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
                "workspaces. If a build problem occurs, all files are left completely intact, "
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

        parser.add_option("", "--branch",
                          type="string",
                          dest="branch",
                          help="Branch specification to build (only build hosts with this branch specification)")

        parser.add_option("", "--cache",
                          type="string",
                          dest="cache",
                          help="Specifies 'make cache' settings to be specified on the build host (if not specified, 'make cache' settings are unchanged on the destination host)")

        parser.add_option("", "--command",
                          type="string",
                          dest="command",
                          help="Executes the specified command string rather than buiding/running a command script to perform a remote build")

        parser.add_option("", "--exclude",
                          type="string",
                          dest="exclude",
                          help="Overrides default exclude list from configuration file (if any); comma-separated list of hosts to exclude from the build")

        parser.add_option("-f", "--full",
                          action="store_true", dest="full", default=False,
                          help="Perform a full build (does --cache=NOUNIT --target='all testrun')")

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

        parser.add_option("", "--nocleanup",
                          action="store_true", dest="nocleanup", default=False,
                          help="Skip the 'tf undo' cleanup at the end of a build")

        parser.add_option("", "--nocurses",
                          action="store_true", dest="nocurses", default=False,
                          help="Disable curses for dynamic screen updating (may be useful for diagnostic purposes)")

        parser.add_option("", "--settings",
                          type="string",
                          dest="settings",
                          help="Overrides default settings from program and configuration file (i.e. 'ShowSummary,LogFile')")

        parser.add_option("-s", "--shelveset",
                          type="string",
                          dest="shelveset",
                          help="Specifies the shelveset name to unshelve prior to the build; may be a comma-separated list")

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

        if options.cache \
                or options.full \
                or options.nocleanup \
                or options.shelveset:
            # We're doing some kind of a build: Be sure there's no conflict with other qualifiers
            if len(args) and options.list:
                parser.error('Option --list conflicts with other specified options\n')

            if options.command:
                parser.error('Option --command conflicts with other specified options\n')

        if options.list and options.command:
                parser.error('Option --command conflicts with option --list\n')

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
            if config.GetBranchSpecification() != '':
                print "Branch:           ", config.GetBranchSpecification()
            else:
                print "Branch:            <None>"
            print "Settings:         ", config.currentSettings
            print "\n"
            print "%-20s -10s %s" % ("Machine Tag", "Project", "Host Address")
            print "%-20s -10s %s\n" % ("-----------", "-------", "------------")
            for key in sorted(config.machines.keys()):
                print "%-20s %s" % (key + ':', config.machines[key].GetProject(), config.machines[key].GetHost())
            return 0

        # Go start the build process (and return resulting status)
        build = Builder(config)
        return build.StartBuild()


if __name__ == '__main__':
    exitStatus = pbuild().main()
    if exitStatus:
        sys.exit( exitStatus )

    # Fall through for successful exit
