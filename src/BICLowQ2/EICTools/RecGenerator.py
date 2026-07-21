# =============================================================================
## @file    RecGenerator.py
#  @authors Derek Anderson
#  @date    09.10.2025
# -----------------------------------------------------------------------------
## @brief Class to generate commands and scripts to run
#    eicrecon for a trial.
# =============================================================================

import os
import pathlib

from EICMOBOTestTools import ConfigParser
from EICMOBOTestTools import FileManager

class RecGenerator:
    """RecGenerator

    A class to generate commands and scripts
    to run eicrecon for a trial.
    """

    def __init__(self, run):
        """constructor accepting arguments

        Args:
          run: runtime configuration file
        """
        self.cfgRun = ConfigParser.ReadJsonFile(run)
        self.argParams = dict()

    def __AddValueToArg(self, arg, value, units = ''):
        """AddValueToArg

        Adds a parameter's value and units to
        an EICrecon argument.

        Args:
          arg:   the argument to add to
          value: the value to add
          units: the units to add
        """
        if units != '':
            arg += "{}*{}".format(value, units)
        else:
            arg += "{}".format(value)
        return arg

    # FIXME this is not thread-safe!
    def ClearArgs(self):
        """ClearArgs

        Clear dictionary of arguments to apply
        """
        self.argParams.clear()

    def AddParamToArgs(self, param, value):
        """AddParamToArgs

        Adds a parameter to dictionary
        of arguments to apply.

        Args:
            param: the parameter to add
            value: the value it's going to take

        """

        # grab info and current value
        # of argument
        path   = param["path"]
        units  = param["units"]
        argVal = ""
        if path in self.argParams:
            argVal = self.argParams[path]

        # if dealing with a vector, then  will have to
        # insert value in appropriate component
        if param["is_vector"]:

            # update length of vector if need be
            index   = param["index"]
            nCommas = argVal.count(',')
            if index > nCommas:
                for i in range(index - nCommas):
                    argVal += ','

            # and then insert value at appropriate index
            if argVal.count(',') == 0:
                argVal = self.__AddValueToArg(argVal, value, units)
            else:
                parts        = argVal.split(',')
                parts[index] = self.__AddValueToArg(parts[index], value, units)
                argVal       = ",".join(parts)

        # otherwise dealing with a scalar, and
        # can just add value to argument
        else:
            self.__AddValueToArg(argVal, value, units)

        # save updated/new arg
        self.argParams[path] = argVal

    def MakeCommand(self, tag, label, steer):
        """MakeCommand

        Generates command to run reconstruction
        executable (eicrecon) on provided inputs
        for a given tag.

        Args:
          tag:   the tag associated with the current trial
          label: the label associated with the input
          steer: the input steering file
        Returns:
          command to be run
        """

        # construct input/output names
        steeTag = FileManager.ConvertSteeringToTag(steer)
        inFile  = FileManager.MakeOutName("sim", tag, label, steeTag)
        outFile = FileManager.MakeOutName("rec", tag, label, steeTag)

        # make sure output directory
        # exists for trial
        outDir = self.cfgRun["out_path"] + "/" + tag
        FileManager.MakeDir(outDir)

        # construct list of collections to make
        icollect = 0
        collects = ""
        for collect in self.cfgRun["rec_collect"]:
            if icollect + 1 < len(self.cfgRun["rec_collect"]):
                collects = collects + collect + ","
            else:
                collects = collects + collect
            icollect = icollect + 1

        # construct output arguments
        outArg  = "-Ppodio:output_file=" + outDir + "/" + outFile
        collArg = "-Ppodio:output_collections=" + collects

        # construct most of command
        command = self.cfgRun["rec_exec"] + " " + outArg + " " + collArg
        for param, value in self.argParams.items():
            command = command + " -P" + param + "=\"" + value + "\""

        # return command with input file attached
        command = command + " " + outDir + "/" + inFile
        return command

    def MakeScript(self, tag, label, steer, config, command):
        """MakeScript

        Generates single script to run reconstruction executable
        (eicrecon) on provided inputs for a given tag.

        Args:
          tag:     the tag associated with the current trial
          label:   the label associated with the input
          steer:   the input steering file
          config:  the detector config file to use
          command: the command to be run
        Returns:
          path to the script created
        """

        # make sure run directory
        # exists for trial
        runDir = self.cfgRun["run_path"] + "/" + tag
        FileManager.MakeDir(runDir)

        # construct script name
        steeTag   = FileManager.ConvertSteeringToTag(steer)
        recScript = FileManager.MakeScriptName(tag, label, steeTag, "rec")
        recPath   = runDir + "/" + recScript
        detPath   = runDir + "/" + pathlib.PurePath(self.cfgRun["det_path"]).name

        # make commands to set detector config
        setDet = FileManager.MakeDetSetCommands(
            detPath,
            config,
            tag
        )

        # if an eicrecon installation is specified,
        # make command to set that
        setRecInstall = None
        if "eicrecon_setup" in self.cfgRun:
            setRecInstall = FileManager.MakeRecSetCommands(
                self.cfgRun["eicrecon_setup"]
            )

        # compose script
        with open(recPath, 'w') as script:
            script.write("#!/bin/bash\n\n")
            script.write(setDet + "\n\n")
            if setRecInstall:
                script.write(setRecInstall + "\n\n")
            script.write(command)

        # make sure script can be run
        os.chmod(recPath, 0o777)

        # return path to script
        return recPath

# end =========================================================================
