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
        self.dependentProjects = [ ]
        self.makeDependencies = False
        self.projectName = ""
        self.sourceDirectory = ""
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
    # Directory where sources are stored. This is only used to verify if we
    # must initially fetch all files from source control, and can be any
    # directory under source control for the project.
    #
    def GetSourceDirectory(self):
        return self.sourceDirectory

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
        self.makeDependencies = False
        self.projectName = "apache"
        self.sourceDirectory = "apache/source"
        self.targets = "all test"

class ProjectMySQL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "mysql/build"
        self.cloneSource = "git@github.com:Microsoft/Build-MySQL-Provider.git"
        self.makeDependencies = False
        self.projectName = "mysql"
        self.sourceDirectory = "mysql/source"
        self.targets = "all test"

class ProjectOM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "opsmgr/build"
        self.cloneSource = "git@github.com:Microsoft/Build-SCXcore.git"
        self.makeDependencies = False
        self.projectName = "om"
        self.sourceDirectory = "opsmgr/source"
        self.targets = "all test"

class ProjectOMI(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "Unix"
        self.cloneSource = "git@github.com:Microsoft/omi.git"
        self.makeDependencies = False
        self.projectName = "omi"
        self.sourceDirectory = "Unix"
        self.targets = "all"

class ProjectOMS(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "omsagent/build"
        self.cloneSource = "git@github.com:Microsoft/Build-OMS-Agent-for-Linux.git"
        self.makeDependencies = False
        self.projectName = "oms"
        self.sourceDirectory = "omsagent/source"
        self.targets = "all"

class ProjectPAL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cloneSource = "git@github.com:Microsoft/pal.git"
        self.makeDependencies = False
        self.projectName = "pal"
        self.sourceDirectory = "source"
        self.targets = "all test"

