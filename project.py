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
        if self.project in ['apache', 'cm', 'mysql', 'om', 'omi', 'oms', 'pal', 'vmm']:
            return True

        return False

    def Create(self):
        if self.project == 'apache':
            return ProjectApache()
        elif self.project == 'cm':
            return ProjectCM()
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
        elif self.project == 'vmm':
            return ProjectVMM()
        else:
            # Whoops, this project hasn't been implemented
            raise NotImplementedError


class Project:
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = ""
        self.cleanPaths = [ ]
        self.cleanList = [ ]
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
    # Get the (list of) directories for which we do revert any files via source control
    #
    def GetCleanPaths(self):
        # Assume we're at the base of the enlistment for build project
        return self.cleanPaths

    ##
    # Get the (list of) directories were we delete writable files. This is
    # combined with the clean paths such that each cleanPath/cleanList
    # combination is clensed of writable files.
    #
    def GetCleanList(self):
        # Assume we're at the base of the enlistment for build project
        return self.cleanList

    ##
    # Get list of dependent projects. These projects are also cleaned prior
    # to cleaning up actual project, allowing all dependent code to be in a
    # known state.
    #
    def GetDependentProjects(self):
        return self.dependentProjects

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
        self.buildDirectory = "build"
        self.cleanPaths = [ "." ]
        self.cleanList = [ "docs", "installer", "source", "test" ]
        self.dependentProjects = [ "omi", "pal" ]
        self.makeDependencies = False
        self.projectName = "apache"
        self.sourceDirectory = "source"
        self.targets = "all test"

class ProjectCM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "Unix"
        self.cleanPaths = [ ".." ]
        self.cleanList = [ "build", "opensource", "Unix/opensource", "Unix/src", "Unix/shared", "Unix/tools" ]
        self.dependentProjects = [ "omi", "pal" ]
        self.makeDependencies = True
        self.projectName = "cm"
        self.sourceDirectory = "Unix/src"
        self.targets = "all release test"

class ProjectMySQL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cleanPaths = [ "." ]
        self.cleanList = [ "installer", "source", "test" ]
        self.dependentProjects = [ "omi", "pal" ]
        self.makeDependencies = False
        self.projectName = "mysql"
        self.sourceDirectory = "source"
        self.targets = "all test"

class ProjectOM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cleanPaths = [ "." ]
        self.cleanList = [ "docs", "installer", "source", "test", "tools" ]
        self.dependentProjects = [ "omi", "pal" ]
        self.makeDependencies = False
        self.projectName = "om"
        self.sourceDirectory = "source"
        self.targets = "all test"

class ProjectOMI(Project):
    ##
    # Ctor.
    def __init__(self):
        # There's a LOT of directories to avoid output dirs.  We assume that 'make cleandist'
        # is complete (thus no cleanList for this project)

        self.buildDirectory = "Unix"
        self.cleanPaths = [ "../omi" ]
        self.cleanList = [ ]
        self.dependentProjects = [ ]
        self.makeDependencies = False
        self.projectName = "omi"
        self.sourceDirectory = "Unix"
        self.targets = "all"

class ProjectOMS(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cleanPaths = [ "." ]
        self.cleanList = [ "installer", "source", "test" ]
        self.dependentProjects = [ "omi", "pal" ]
        self.makeDependencies = False
        self.projectName = "oms"
        self.sourceDirectory = "source"
        self.targets = "all"

class ProjectPAL(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "build"
        self.cleanPaths = [ "../pal" ]
        self.cleanList = [ "installer", "source", "test" ]
        self.dependentProjects = [ ]
        self.makeDependencies = False
        self.projectName = "pal"
        self.sourceDirectory = "source"
        self.targets = "all test"

class ProjectVMM(Project):
    ##
    # Ctor.
    def __init__(self):
        self.buildDirectory = "dev"
        self.cleanPaths = [ "." ]
        self.cleanList = [ "dev/src" ]
        self.dependentProjects = [ "pal" ]
        self.makeDependencies = False
        self.projectName = "vmm"
        self.sourceDirectory = "dev"
        self.targets = "all release test"

