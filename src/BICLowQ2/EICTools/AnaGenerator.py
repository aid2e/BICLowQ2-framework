# =============================================================================
## @file    AnaGenerator.py
#  @authors Derek Anderson
#  @date    09.19.2025
# -----------------------------------------------------------------------------
## @brief Class to generate commands and scripts to run
#    analyses/objectives for a trial.
# =============================================================================

import os
import stat
import sys

from EICMOBOTestTools import ConfigParser
from EICMOBOTestTools import FileManager

class AnaGenerator:
    """AnaGenerator

    A class to generate commands and scripts
    to run analyses/objectives for a trial.
    """

    def __init__(self, run, ana):
        """constructor accepting arguments

        Args:
          run: runtime configuration file
          ana: objectives configuration file
        """
        self.cfgRun = ConfigParser.ReadJsonFile(run)
        self.cfgAna = ConfigParser.ReadJsonFile(ana)

    def GetDummyValue(self, objective):
        """GetDummyObjective

        Returns a dummy value for the specified
        objective. This is used when trials fail
        due to non-infrastructural reasons (e.g.
        a parameterization generates overlaps)

        Args:
          objective: the objective to get a dummy value for
        Returns:
          a dummy value that's above or below the objective's
          threshold
        """

        # if minimizing, put dummy value *above* threshold
        # and if maximizing, put dummy value *below* threshold,
        scale = 2.0
        if self.cfgAna["objectives"][objective]["goal"] == "maximize":
            scale = 0.5

        # now return scaled threshold
        return scale * self.cfgAna["objectives"][objective]["threshold"]

    def MakeMergeCommand(self, tag, label, stage = "rec"):
        """MakeMergeCommand

        Generates command to merge reconstructed
        output ahead of analysis scripts.

        Args:
          tag:   the tag associated with the current trial
          label: the label associated with the input
          stage: the stage (sim vs. reco) to merge
        Returns:
          the merging command and the path to the merge output
        """

        # get output directory
        outDir = self.cfgRun["out_path"] + "/" + tag

        # make path to merged file
        mergeFile = FileManager.MakeOutName(stage, tag, label, "", "", "merge")
        mergePath = outDir + "/" + mergeFile

        # make path to files to merge
        toMergeFiles = FileManager.MakeOutName(stage, tag, label, '*')
        toMergePaths = outDir + "/" + toMergeFiles

        # construct command
        command = "hadd -f " + mergePath + " " + toMergePaths

        # return command and path to merged file
        return command, mergePath

    def MakeCommand(self, tag, label, analysis, simfile, recfile):
        """MakeCommand

        Generates command to run a specified analysis
        executable on provided input.

        Args:
          tag:      the tag associated with the current trial
          label:    the label associated with the input
          analysis: the tag associated with the analysis being run
          simfile:  the path to the sim-level input
          recfile:  the path to the rec-level input
        Returns:
          tuple of the command to be run and the output file
        """

        # make sure output directory
        # exists for trial
        outDir = self.cfgRun["out_path"] + "/" + tag
        FileManager.MakeDir(outDir)

        # construct output name
        outFile = FileManager.MakeOutName("ana", tag, label, "", analysis)
        outPath = outDir + "/" + outFile

        # construct executable path
        exeName = self.cfgAna["objectives"][analysis]["exec"]
        exeDir = self.cfgAna["objectives"][analysis]["path"]
        exePath = exeDir + "/" + exeName

        # construct and return command
        command = self.cfgAna["objectives"][analysis]["rule"]
        command = command.replace("<EXEC>", exePath)
        command = command.replace("<OUTPUT>", outPath)
        command = command.replace("<SIM>", simfile)
        command = command.replace("<RECO>", recfile)
        return command, outPath

    def MakeScript(self, tag, label, analysis, command):
        """MakeScript

        Generates single script to run analysis executable
        for a given tag.

        Args:
          tag:      the tag associated with the current trial
          label:    the label associated with the input
          analysis: the tag associated with the analysis being run
          command:  the command to be run
        Returns:
          path to the script created
        """

        # make sure run directory
        # exists for trial
        runDir = self.cfgRun["run_path"] + "/" + tag
        FileManager.MakeDir(runDir)

        # construct script name
        anaScript = FileManager.MakeScriptName(tag, label, "", "ana", analysis)
        anaPath   = runDir + "/" + anaScript

        # compose script
        with open(anaPath, 'w') as script:
            script.write("#!/bin/bash\n\n")
            script.write(command)

        # make sure script can be run
        os.chmod(anaPath, 0o777)

        # return path to script
        return anaPath

# end =========================================================================
