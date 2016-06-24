# pbuild

Private developer build facility

Table of Contents:

* [What is pbuild] (#what-is-pbuild)
* [Assumptions] (#assumptions)
* [Command Quialifiers to pbuild] (#command-qualifiers-to-pbuild)
* [Environment Variables] (#environment-variables)
* [Valid Projects] (#valid-projects)
* [Settings that Modify Behavior] (#settings-that-modify-behavior)
* [Per-Project Configuration Options] (#per-project-configuration-options)
* [Output description for Progress Setting] (#output-description-for-progress-setting)
* [Support for testrun attributes and names] (#support-for-testrun-attributes-and-names)
* [Keyboard Input] (#keyboard-input)

-----

### What is pbuild?

pbuild (private build) is a utility that allows a developer to verify
code changes compile and run unit tests on a wide variety of different
platforms simultaneously.

pbuild will allow you to do a build across all our platforms using
your git clones under your own accounts. So, since you’re using your
own account, if you have a problem on a host, you simply need to go to
the appropriate directory and everything is left intact to work on
resolving the problem. pbuild supports checking out a branch in git
if you ask it to, and making a target of your choice (default target
is 'testrun'). There are other options as well. pbuild supports
running on any or all of your development hosts.

pbuild is driven by an initialization file to define the hosts to
use. A sample configuration file can be found in the same location as
pbuild itself, and should contain config_sample with either
config_hosts_core or config_hosts_nip appended to that, depending on
what s closer to the machine list that you want. The configuration
file is normally stored in ~/.pbuild, but this can be customized via
environment variable PBUILD.

pbuild, by default, stores log files from the builds in your home directory
(~/). This can be customized via the configuration file. See the sample
configuration file for details.

pbuild fully supports terminating the builds via ^C. Upon termination,
pbuild will kill all child processes, causing remote build operations to
terminate.

To run pbuild, you can do "python pbuild.py" with any command line
options.

While running, pbuild will show status like this:

```
Tag                           Host Name                     Status

aix_5.3                       scxaix1                       Done (18:55)
aix_6.1                       scxaix3-3                     Done (23:30)
hp_v2_ia64                    scxhpi10                      Done (21:45)
hp_v2_risc                    scxhpr3                       Done (24:55)
hp_v3_ia64                    scxhpi1
hp_v3_risc                    scxhpr2                       Done (27:00)
mac_10.5                      scx-mac04                     Done (07:15)
redhat_4_x86                  scxrhel4-01                   Done (23:50)
redhat_5_x86                  scxcore-rhel50-01             Done (11:55)
sun_5.10_sparc                scxsun12                      Done (24:40)
sun_5.10_x86                  scxcore-solx86-01             Done (23:50)
sun_5.8_sparc                 scxsun03-s8
sun_5.9_sparc                 scxsun14                      Done (24:30)
suse_10_x86                   scxcore-suse01                Done (12:35)
suse_9_x86                    scxsles9-01

Elapsed Time:  27:45
```

In this example, hosts scxhpi1, scxsun03-s8, and scxsles9-01 are still
building. All other hosts have completed (with time to complete). If
a build fails, status is "Failed" (bolded).


###Assumptions:

1. For simplicity, pbuild assumes that you're using [certificates
everywhere][]. This means that you can type "ssh
<hostname>" from one Unix/Linux host to go directly to some other
Unix/Linux host without username/password prompts.<br><br>
pbuild, when starting, will verify that all required SSH keys are
stored in your ~/.ssh/known_hosts file. If you have modified your
configuration file, pbuild will run this verification step again to
double check that all your hosts can be reached. This can be forced
with --initialize.

[certificates everywhere]: https://github.com/Microsoft/ostc-docs/blob/master/setup-sshkeys.md

2. pbuild assumes that you're using 'bash' as your shell. If important,
it can be changed to support other shells. But to date it has no such
support.


### Command Qualifiers to pbuild

Please do ```pbuild --help``` for latest/greatest information:

```
Usage: pbuild.py [option-list] [host-list]   (use --help or -h for help)

pbuild will allow you to do a build across all platforms using your own git
clones. If a build problem occurs, all files are left completely intact,
simplifying the steps you must perform to replicate the problem. pbuild
supports a wide variety of options, specified below.  For more information,
view the README file checked in with pbuild.

Options:
  -h, --help            show this help message and exit
  --abortOnError        Immediately aborts when the first remote build fails
                        (for future - do not use yet)
  --attributes=TEST_ATTRS
                        Specifies the unit test attributes that you wish to
                        use to restrict unit tests
  -b BRANCH, --branch=BRANCH
                        Selects the branch for the top level project or
                        superproject
  -d, --debug           Build targets in DEBUG mode
  --clone               Forces a new clone of the repository, even if
                        repository already exists
  --command=COMMAND     Executes the specified command string rather than
                        buiding/running a command script to perform a remote
                        build
  --exclude=EXCLUDE     Overrides default exclude list from configuration file
                        (if any); comma-separated list of hosts to exclude
                        from the build
  --initialize          Verify public keys in known_hosts file
  -l, --list            List host configuration information and exit
  --logdir=LOGDIR       Overrides 'logdir' from configuration file
  --logdir_prior=LOGDIR_PRIOR
                        Overrides 'logdir_prior' from configuration file
  --nodebug             Build targets in NODEBUG mode
  --nocurses            Disable curses for dynamic screen updating (may be
                        useful for diagnostic purposes)
  --select=SELECT       Select specification to build (only build hosts with
                        this select specification)
  --settings=SETTINGS   Overrides default settings from program and
                        configuration file (i.e. 'ShowSummary,LogFile')
  -s SUBPROJECT, --subproject=SUBPROJECT
                        Comma-separated list of subproject:branch pairs to
                        select branches in subprojects, like "opsmgr:jeff-
                        sun,pal:jeff-sun"
  -t TARGET, --target=TARGET
                        Specifies the build target to use for the 'make'
                        command (default: 'testrun').  Set target as empty
                        string to avoid the 'make' step (useful to, say, undo
                        changes on a host)
  --tests=TESTS         Specifies the subset of unit tests that you wish to
                        run (if the target includes "testrun"); may be a
                        comma-separated list
```


### Environment Variables

Environment variables that modify and control PBUILD behavior:

Env Variable | Purpose
------------ | -------
PBUILD | Path where the PBUILD configuraiton file can be found. By default, this is ~/.pbuild unless the PBUILD environment variable is set.


### Valid Projects

Projects are specified in per-project configuration options as well as host
entries. Valid projects are defined as follows:

Project | Purpose
------- | -------
Apache | Apache OMI Provider
MySQL  | MySQL OMI Provider
OM | Operations Manager (OMI Provider)
OMI | Open Management Infrastructure
OMI | Operations Insight
PAL | Platform Abstraction Layer


### Settings that Modify Behavior

Settings are set to "reasonable defaults for most people" automatically. By
that, I mean that settings are the most logical and trouble-free settings, but
not necessarily the "nicest" settings.

Settings can be overridden by the configuration file, or by the command line
qualifier "--settings". A setting can be prefixed by "no" to disable it; if
it is not prefixed by "no", then the setting is enabled.

Settings that can be controlled:

Setting | Purpose
------- | -------
CheckValidity | Verify, when the .pbuild file is modified, that all locations are valid and are set up on each machine. This is the default behavior and serves to catch build problems early. But, for very experienced PBUILD users, you may wish to disable this.
Debug | Build code in DEBUG mode.
DeleteLogfiles | Prior to starting a build, delete all variations of log files that will be written for that build. This is useful to avoid clutter when using "LogfileRename" (described below).
DiagnoseErrors | Leaves temporary build script intact on destination system in case of internal problems with pbuild.
LogfileRename | After a build, the log files are renamed to indicate if the final build status was successful or unsuccessful.
LogfileSelect | This option will choose a name for the logfile that includes the selector that is being used for the build. This allows multiple instances of PBUILD to be run concurrently against different selectors.
Progress | Display progress updates for the build. This results in a lot of screen updates during the build, and is thus a setting that can be disabled.
SummaryScreen | Show a summary screen at the end of a build. This appears to be needed for putty users (for some reason, curses clears the screen when you're using putty).<br><br>Nice to disable if you can (cleaner screen output).

Default settings are:

```
CheckValidity, Debug, DeleteLogfiles, NoDiagnoseErrors, NoLogfileRename, NoLogfileSelect, Progress, SummaryScreen
```


### Per-Project Configuration Options

PBUILD supports per-project configuration options. This is useful if you need
to set project-specific options. Two such options are currently supported:

```
make_target : project : options
configure_options : project : options
```

Spaces around the `:` separators in the above example are optional. Note that
fields (project or option fields) must not contain any `:` characters.


### Output description for Progress setting

If you run pbuild with the `Progress` setting (the default), then pbuild will
display a line under the status column like:

```
  - <operation> <lines>
```

For example, you may see a line like:

```
  - make pal (619)
```

This means that the build is currently executing the `make pal` step, and
that 619 lines of log text have been received since the `make pal` step was
started.

Note that if the first byte is a `?` rather than a `-`, as in:

```
  ? make pal (619)
```

this means that no log text has been received for 31 seconds or more (in other
words, the host does not appear to be responding). Once the host performs
additional work, the `?` will change back to a `-`.


### Support for testrun attributes and names

Qualifier `-attributes` can be used to only run certain tests with attributes set
in the test source files. Prepend a `-` to include the opposite setting.

Today, only attribute *SLOW* is defined in tests, and is defined to be any test
that takes "a while" to run.

For example: `-attributes=-SLOW` will only run tests that are not marked as slow tests

Qualifer `-tests` can be used to restrict tests that are run, or to ignore tests
that are run. Prepend a `-` to a test name to ignore a certain test.

For example: `-tests=-atomic` will run all tests except those with *atomic* in their name.
`-tests=atomic,condition` will only run tests with *atomic* or *condition* in their names

Configuration tag `test_attributes` will form default attribute specification.
Configuration tag `test_list` will form the default unit test specification.


### Keyboard Input

Once every poll interval the keyboard is polled for input. The following
characters are recognized:

Character | Purpose | Description
--------- | ------- | -----------
`r` | Redraw Screen | Useful if an SSH error corrupts your screen (if a host is down, for example).
`^C` | Abort | There's actually no special handling for this since none is needed. Causes pbuild to abort processing, cleaning up all remote processes and aborting the build across all systems.
