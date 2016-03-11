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
        if self.project in ['apache', 'mysql', 'om', 'omi', 'oms', 'pal']:
            return True

        return False

    def Create(self):
        if self.project == 'apache':
            return ProjectApache()
        elif self.project == 'mysql':
            return ProjectMySQL()
        elif self.project == 'om':
            return ProjectOM()
        elif self.project == 'omi':
            return ProjectOMI()
        elif self.project == 'oms':
            return ProjectOMS()
        elif self.project == 'pal':
            return ProjectPAL()
        else:
            # Whoops, this project hasn't been implemented
            raise NotImplementedError


class Project:
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = ""
        self.cloneSource = ""
        self.configureQuals = ""
        self.subProjects = []
        self.makeDependencies = False
        self.projectName = ""
        self.targets = []

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
# Project Definitions for each supported project
#

class ProjectApache(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "apache/build"
        self.cloneSource = "git@github.com:Microsoft/Build-Apache-Provider.git"
        self.configureQuals = ""
        self.subProjects = ["apache", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "apache"
        self.targets = "all test"

class ProjectMySQL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "mysql/build"
        self.cloneSource = "git@github.com:Microsoft/Build-MySQL-Provider.git"
        self.configureQuals = ""
        self.subProjects = ["mysql", "omi", "pal"]
        self.makeDependencies = False
        self.projectName = "mysql"
        self.targets = "all test"

class ProjectOM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "opsmgr/build"
        self.cloneSource = "git@github.com:Microsoft/Build-SCXcore.git"
        self.configureQuals = "--enable-system-build"
        self.subProjects = ["omi", "opsmgr", "pal"]
        self.makeDependencies = False
        self.projectName = "om"
        self.targets = "all test"

class ProjectOMI(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "Unix"
        self.cloneSource = "git@github.com:Microsoft/omi.git"
        self.configureQuals = ""
        self.subProjects = [ ]
        self.makeDependencies = False
        self.projectName = "omi"
        self.targets = "all"

class ProjectOMS(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "omsagent/build"
        self.cloneSource = "git@github.com:Microsoft/Build-OMS-Agent-for-Linux.git"
        self.configureQuals = "--enable-ulinux"
        self.subProjects = ["dsc", "omi", "omsagent", "opsmgr", "pal"]
        self.makeDependencies = False
        self.projectName = "oms"
        self.targets = "all"

class ProjectPAL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cloneSource = "git@github.com:Microsoft/pal.git"
        self.configureQuals = ""
        self.subProjects = [ ]
        self.makeDependencies = False
        self.projectName = "pal"
        self.targets = "all test"

