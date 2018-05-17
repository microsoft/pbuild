# coding: utf-8
#
# Copyright (c) Microsoft Corporation.  All rights reserved.
#
##
# Module containing base classes to define project characteristics
#
# Date:   2014-10-20
#

##
# Class containing machine defitions
#
class ProjectFactory:
    ##
    # Ctor.
    # \param[in] Project name
    def __init__(self, project):
        self.project = project.lower()

    ##
    # Return true if a project is valid (false otherwise)
    #
    def Validate(self):
        if self.project in ['apache', 'cm', 'docker', 'dsc', 'mysql', 'om', 'omi', 'omikits', 'oms', 'pal', 'psrp']:
            return True

        return False

    def Create(self):
        if self.project == 'apache':
            return ProjectApache()
        elif self.project == 'cm':
            return ProjectCM()
        elif self.project == 'docker':
            return ProjectDocker()
        elif self.project == 'dsc':
            return ProjectDsc()
        elif self.project == 'mysql':
            return ProjectMySQL()
        elif self.project == 'om':
            return ProjectOM()
        elif self.project == 'omi':
            return ProjectOMI()
        elif self.project == 'omikits':
		    return ProjectOMIKITS()
        elif self.project == 'oms':
            return ProjectOMS()
        elif self.project == 'pal':
            return ProjectPAL()
        elif self.project == 'psrp':
            return ProjectPSRP()
        else:
            # Whoops, this project hasn't been implemented
            raise NotImplementedError

class Project:
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = ""
        self.cloneSource = ""
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = []
        self.makeDependencies = False
        self.projectName = ""
        self.targets = []
        self.postBuildSteps = []

    ##
    # Define Get() methods to fetch internal data
    #

    ##
    # Get the build directory where we should perform builds from.  This may
    # be "." if the base directory is to be used.
    #
    def GetBuildDirectory(self):
        return self.buildDirectory

    ##
    # Get the git location to clone the project from. This allows us to
    # clone a brand new repository if needed.
    #
    def GetCloneSource(self):
        return self.cloneSource

    ##
    # Check if this project uses a configure script
    #
    def UsesConfigureScript(self):
        return self.usesConfigureScript

    ##
    # Get the configure qualifiers to run the configure script with
    #
    def GetConfigureQualifiers(self):
        return self.configureQuals

    ##
    # Is the subproject (passed in) valid for this project?
    #
    def ValidateSubproject(self, sub):
        if sub.lower() in self.subProjects:
            return True
        else:
            return False

    ##
    # Does the project require a separate 'make depend' step?
    #
    def GetMakeDependencies(self):
        return self.makeDependencies

    ##
    # What is the short name of this project?
    #
    def GetProjectName(self):
        return self.projectName.lower()

    ##
    # Get the default list of targets to build (make <targets>)
    #
    def GetTargets(self):
        return self.targets

    ##
    # Get the list of post-build commands to run
    #
    def GetPostBuildCommands(self):
        return self.postBuildSteps
	
##
# Project Definitions for each supported project
#
class ProjectApache(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "apache/build"
        self.cloneSource = "git@github.com:Microsoft/Build-Apache-Provider.git"
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = ["apache", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "apache"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectCM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "configmgr/Unix"
        self.cloneSource = "git@github.com:Microsoft/Build-SCXcm.git"
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = ["configmgr", "omi", "pal"]
        self.makeDependencies = True
        self.projectName = "cm"
        self.targets = "all release test"
        self.postBuildSteps = []

class ProjectDocker(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "docker/build"
        self.cloneSource = "git@github.com:Microsoft/Build-Docker-Provider.git"
        self.usesConfigureScript = True
        self.configureQuals = "--enable-ulinux"
        self.subProjects = ["docker", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "docker"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectDsc(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "dsc"
        self.cloneSource = "git@github.com:Microsoft/Build-PowerShell-DSC-for-Linux.git"
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = ["dsc", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "dsc"
        self.targets = "all"
        self.postBuildSteps = []

class ProjectMySQL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "mysql/build"
        self.cloneSource = "git@github.com:Microsoft/Build-MySQL-Provider.git"
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = ["mysql", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "mysql"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectOM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "opsmgr/build"
        self.cloneSource = "git@github.com:Microsoft/Build-SCXcore.git"
        self.usesConfigureScript = True
        self.configureQuals = "--enable-system-build"
        self.subProjects = ["omi", "opsmgr", "pal"]
        self.makeDependencies = False
        self.projectName = "om"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectOMI(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "omi/Unix"
        self.cloneSource = "git@github.com:Microsoft/Build-omi.git"
        self.usesConfigureScript = True
        self.configureQuals = "--dev"
        self.subProjects = ["omi", "pal"]
        self.makeDependencies = False
        self.projectName = "omi"
        self.targets = "clean"  # Do 'make clean' just do something (regress is all inclusive)
        self.postBuildSteps = ["./regress"]

class ProjectOMIKITS(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "omi/Unix"
        self.cloneSource = "git@github.com:Microsoft/Build-omi.git"
        self.usesConfigureScript = True
        self.configureQuals = "--enable-system-build --enable-native-kits"
        self.subProjects = ["omi", "pal"]
        self.makeDependencies = False
        self.projectName = "omi"
        self.targets = " "  # Do 'make clean' just do something (regress is all inclusive)
        self.postBuildSteps = ["echo -n The OMI native kit is here: ; echo -n `hostname`; echo -n :; cd ./../Packages; pwd; echo;ls -R"]
				
class ProjectOMS(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "omsagent/build"
        self.cloneSource = "git@github.com:Microsoft/Build-OMS-Agent-for-Linux.git"
        self.usesConfigureScript = True
        self.configureQuals = "--enable-ulinux"
        self.subProjects = ["dsc", "omi", "omsagent", "opsmgr", "pal"]
        self.makeDependencies = False
        self.projectName = "oms"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectPAL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cloneSource = "git@github.com:Microsoft/pal.git"
        self.usesConfigureScript = True
        self.configureQuals = ""
        self.subProjects = [ ]
        self.makeDependencies = False
        self.projectName = "pal"
        self.targets = "all test"
        self.postBuildSteps = []

class ProjectPSRP(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "."
        self.cloneSource = "git@github.com:PowerShell/psl-omi-provider.git"
        self.usesConfigureScript = False
        self.configureQuals = ""
        self.subProjects = ["omi", "pal"]
        self.makeDependencies = False
        self.projectName = "psrp"
        self.targets = "release-ulinux"
        self.postBuildSteps = [ ]
