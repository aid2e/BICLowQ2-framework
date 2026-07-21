# =============================================================================
## @file    GeometryEditor.py
#  @authors Connor Pecar,
#           with modifications by Derek Anderson
#  @date    09.02.2025
# -----------------------------------------------------------------------------
## @brief Class to generate and edit modified compact
#    files for a trial.
# =============================================================================

import os
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from EICMOBOTestTools import ConfigParser
from EICMOBOTestTools import FileManager

class GeometryEditor:
    """GeometryEditor

    A class to generate and edit modified
    geometry (config and compact) files
    for a trial.
    """

    def __init__(self, run, tag):
        """constructor accepting arguments

        Args:
          run: runtime configuration file
        """
        self.cfgRun  = ConfigParser.ReadJsonFile(run)
        self.runPath = self.cfgRun["run_path"] + "/" + tag
        self.geoDir  = pathlib.PurePath(self.cfgRun["det_path"]).name
        self.detPath = self.runPath + "/" + self.geoDir
        self.cmakePath = self.cfgRun["cmake_path"]

    def __GetCompact(self, param, tag):
        """GetCompact

        Checks if the compact file associated with a parameter
        and a particular tag exists and returns the path to it.
        If it doesn't exist, it creates it.

        Args:
          param: a parameter, structured according to parameter config file
          tag:   the tag associated with the current trial
        Returns:
          path to compact file associated with parameter and tag
        """

        # extract path and create relevant name
        oldCompact = self.detPath + "/" + param["compact"]
        newCompact = oldCompact
        if not oldCompact.endswith(tag + ".xml"):
            newCompact = FileManager.GetNewName(oldCompact, tag)

        # if new compact does not exist, create it
        if not os.path.exists(newCompact):
            shutil.copyfile(oldCompact, newCompact)

        # and return path
        return newCompact

    def __GetConfig(self, tag):
        """GetConfig

        Checks if the configuration file associated
        a particular tag exists and returns the path
        to it. If it doesn't exist, it creates it.

        Args:
          tag: the tag associated with the current trial
        Returns:
          path to the config file with tag
        """

        # extract path and create relevant name
        install   = self.detPath + "/install/share/epic/"
        oldConfig = install + self.cfgRun["det_config"] + ".xml"
        newConfig = oldConfig
        if not oldConfig.endswith(tag + ".xml"):
            newConfig = FileManager.GetNewName(oldConfig, tag)

        # if new config does not exist, create it
        if not os.path.exists(newConfig):
            shutil.copyfile(oldConfig, newConfig)

        # and return path
        return newConfig

    def __GetFile(self, file, tag, ext = ".xml"):
        """GetFile

        Checks if a file associated with a particular
        tag exists and returns the path to it. If it
        doesn't exist, it creates it.

        Args:
          file: the file to get/be created
          tag:  the tag associated with the current trial
          ext:  the extension of the file
        Returns:
          path to the file with tag
        """

        # create relevant name
        newFile = file
        if not file.endswith(tag + ext):
            newFile = FileManager.GetNewName(file, tag, ext)

        # if new file does not exist, create it
        if not os.path.exists(newFile):
            shutil.copyfile(file, newFile)

        # and return path
        return newFile

    def __IsPatternInFile(self, pattern, file):
        """IsPatternInFile

        Checks if a provided pattern (eg. a
        file name) is in a file, and returns
        true or false of it is or isn't.

        Args:
          pattern: the pattern to look for
          file:    the file to look in
        Returns:
          whether or not pattern was found
        """

        # iterate through lines until pattern is found
        found = False
        with open(file, 'r') as lines:
            for iLine, line in enumerate(lines, start=1):
                if re.search(pattern, line):
                    found = True
                    break

        # return whether or not pattern was ever found
        return found

    def CopyGeoToRunDir(self):
        """CopyGeoToRunDir

        Copies geometry specifed by `cmake_path` to run
        directory of trial. Should be called BEFORE
        calling `EditCompact`, `EditRelatedFiles`, or
        `DoGeoRecomp`.
        """
        FileManager.MakeDir(self.runPath) # makes run dir if needed
        if os.path.exists(self.detPath ):
            subprocess.run(["rm", "-r", self.detPath])
        shutil.copytree(
            self.cmakePath,
            self.detPath,
            ignore=shutil.ignore_patterns('.*')
        )

    def EditCompact(self, param, value, tag):
        """EditCompact

        Updates the value of a parameter in the compact
        file associated with it and the provided tag.

        Args:
          param: the parameter and its associated compact file
          value: the value to update to
          tag:   the tag associated with the current trial
        """

        # get path to compact file to edit, and
        # parse the xml
        fileToEdit = self.__GetCompact(param, tag)
        treeToEdit = ET.parse(fileToEdit)
 
        # extract relevant info from parameter
        path, elem, unit = ConfigParser.GetPathElementAndUnits(param)

        # now find and edit the relevant info 
        elemToEdit = treeToEdit.getroot().find(path)
        if unit != '':
            elemToEdit.set(elem, "{}*{}".format(value, unit))
        else:
            elemToEdit.set(elem, "{}".format(value))

        # save edits and exit
        treeToEdit.write(fileToEdit)
        return

    def EditRelatedFiles(self, param, tag):
        """EditRelatedFiles

        Updates _all_ xml files related to a
        provided parameter, including related
        config files and intermediaries.

        Args:
          param: the parameter and its associated compact file
          tag:   the tag associated with the current trial
        """

        # step 1:grab old & new compact files
        #   associated with parameter
        oldCompact = param["compact"]
        newCompact = FileManager.GetNewName(oldCompact, tag)

        # step 2: split old compact path into directories
        #   relative to self.detPath to search in
        split = oldCompact.split('/')

        # step 3: now iterate upwards through sequence
        #   of directories to check to find related
        #   files
        path    = ""
        steps   = len(split) + 1
        queries = [split[-1]]
        for step in range(2, steps):

            # step 3(a): loop through all files in directory
            search = '/'.join(part for part in split[0:steps - step])
            root   = self.detPath + '/' + search
            new    = list()
            for file in os.listdir(self.detPath + "/" + search):

                full = root + "/" + file
                if os.path.isdir(full):
                    continue

                # step 3(a)(i): check if any files include
                #   any of the files related to the compact
                for query in queries:
                    if self.__IsPatternInFile(query, full):

                        # step3(a)(ii): if it does, create
                        #   new version with filenames
                        #   updated accordingly
                        copy     = self.__GetFile(full, tag)
                        update   = FileManager.GetNewName(query, tag)
                        editable = pathlib.Path(copy)
                        text     = editable.read_text(encoding="utf-8")

                        # if the query + tag already exists in
                        # file, no need to do anything
                        edited = text
                        if update not in text:
                            edited = text.replace(query, update)

                        # save text and add file queries
                        editable.write_text(edited, encoding="utf-8")
                        if file not in new:
                            new.append(file)

            # step 3(b): add any new related files to list
            #   and update relative paths
            path = split[-step] + "/" + path
            add  = path.split("/")[0]

            queries.extend(new)
            queries[:] = [f"{add}/{query}" for query in queries]

        # step 4: now identify all YAML configurations
        #   that contain one of the updated files
        config  = self.detPath + "/configurations"
        
        # create configurations directory if it doesn't exist
        if not os.path.exists(config):
            os.makedirs(config)
        
        for file in os.listdir(config):

            full = config + "/" + file
            if os.path.isdir(full):
                continue

            # step 4(a): check if any updated compact files'
            #   stems appear in configuration
            for query in queries:
                stem = os.path.splitext(os.path.basename(query))[0]
                if self.__IsPatternInFile(stem, full):

                    # step 4(b): if it does, create new
                    #   version and update stems
                    #   accordingly
                    copy     = self.__GetFile(full, tag, ".yml")
                    update   = FileManager.GetNewName(stem, tag, "")
                    editable = pathlib.Path(copy)
                    text     = editable.read_text(encoding="utf-8")

                    # like before, if stem + tag already exists
                    # in config file, no need to do anything
                    edited = text
                    if update not in text:
                        edited = text.replace(stem, update)

                    # save text and iterate
                    editable.write_text(edited, encoding="utf-8")

    def MakeConfigCopyCommand(self, tag):
        """MakeConfigCopyCOmmand

        If using default config (epic.xml), then we'll need
        to create a modified default config from epic_full.xml
        (which is identical).

        Args:
          tag: the tag to be applied
        Returns:
          command to be run
        """
        # -- FIXME this is a stopgap! This won't work for generic
        #    DD4hep geometries! This will be dealt with when we
        #    transition to AID2E-framework...
        installPath = self.detPath + "/install/share/epic/"
        fullConfig  = installPath + FileManager.GetNewName("epic_full.xml", tag)
        defConfig   = installPath + FileManager.GetNewName("epic.xml", tag)
        return "cp " + fullConfig + " " + defConfig

    def MakeGeoRecompileCommand(self):
        """MakeGeoRecompileCommand

        Generates command to recompile
        geometry after making edits.

        Returns:
          commands to be run
        """
        # Return recompilation commands
        return "\n".join([
            f'cd {self.detPath}',
            f'cmake -B build -S {self.detPath} -DCMAKE_INSTALL_PREFIX=install',
            'cmake --build build',
            'cmake --install build',
            'cd -'
        ])

    def MakeOverlapCheckCommand(self, tag):
        """MakeOverlapCheckCommand

        Generates commands to run overlap check
        and exit subprocess if an overlap is
        found.

        Args:
          tag: tag associated with current trial
        Returns:
          commands to be run
        """

        # make sure output directory
        # exists for trial
        outDir = self.cfgRun["out_path"] + "/" + tag
        FileManager.MakeDir(outDir)

        # command to do overlap check
        log = outDir + "/" + FileManager.MakeOutName("geo", tag)
        run = self.cfgRun["overlap_check"] + " -c $DETECTOR_PATH/$DETECTOR_CONFIG.xml > " + log + " 2>&1"

        # command(s) to exit if there were any overlaps
        checks = [
            f'grep -F "Number of illegal overlaps/extrusions : " {log} | while IFS= read -r line; do',
            '  lastChar="${line: -1}"',
            '  if [[ $lastChar =~ ^[0-9]$ ]]; then',
            '    if (( lastChar > 0 )); then',
            '      exit 9',
            '    fi',
            '  fi',
            'done'
        ]
        check = "\n".join(checks)

        # return full command
        return run + "\n" + check

    def MakeBuildScript(self, tag, config):
        """MakeBuildScript

        Generates single script to build geometry
        and test for overlaps.

        Args:
          tag:    the tag associated with the current trial
          config: the detector config file to use
        Returns:
          path to the script created
        """

        # construct script name
        geoScript  = FileManager.MakeScriptName(tag, "", "", "geo")
        scriptPath = self.runPath + "/" + geoScript

        # make commands
        build    = self.MakeGeoRecompileCommand()
        detector = FileManager.MakeDetSetCommands(
            self.detPath,
            self.cfgRun["det_config"],
            tag
        )
        overlap = self.MakeOverlapCheckCommand(tag)

        # compose script
        with open(scriptPath, 'w') as script:
            script.write("#!/bin/bash\n\n")
            script.write("set -e\n\n")
            script.write(build + "\n\n")
            script.write(detector + "\n\n")
            script.write(overlap + "\n\n")

        # make sure script can be run
        os.chmod(scriptPath, 0o777)

        # return path to script
        return scriptPath

# end =========================================================================
