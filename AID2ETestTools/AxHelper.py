# =============================================================================
## @file    AxHelper.py
#  @authors Derek Anderson
#  @date    09.29.2025
# -----------------------------------------------------------------------------
## @brief Module to convert AID2E config
#    files to Ax-compliant dictionaries
# =============================================================================

from pydoc import locate
import ast

from ax.api.configs import ChoiceParameterConfig, RangeParameterConfig
from ax.service.ax_client import ObjectiveProperties

def GetStatusQuo(config):
    """GetStatusQuo

    Helper method to convert a dictionary of
    AID2E parameter options into a dictionary
    of the form:

      {parameter_name : default_value}

    Can be used to get the 'status_quo' when
    doing, e.g., Bandit Optimization.

    Args:
      config: dictionary to convert
    Returns:
      a dictionary of the form
        {parameter_name : default_value}
    """

    # extract parameters
    inPars = config["parameters"]

    # iterate through parameters
    statusQuo = dict()
    for inParKey, inParVal in inPars.items():

        # extract relevant info
        name    = inParKey
        default = inParVal["default"]
        vType   = inParVal["value_type"]
        rType   = locate(vType)

        # append to dict
        statusQuo[name] = rType(default)

    # return dictionary of defaults
    return statusQuo

def ConvertParamConfig(config):
    """ConvertParamConfig

    Helper method to convert a dictionary of
    AID2E parameter options into a list of
    Ax-compliant definitions.

    This is relevant for when interacting with
    the ax.service.ax_client.AxClient API.

    Args:
      config: dictionary to convert
    Returns:
      a tuple containing:
        a list of ax-compliant parameter definitions
        a list of parameter constraints
    """

    # extract parameters & constraints
    inPars = config["parameters"]
    inCons = config["constraints"]

    # iterate through parameters
    outPars = list()
    for inParKey, inParVal in inPars.items():

        # extract relevant info
        name  = inParKey
        pType = inParVal["param_type"]
        vType = inParVal["value_type"]

        # if needed, extra bounds
        bounds = None
        if pType == "range": 
            lLimit = ast.literal_eval(inParVal["lower"])
            uLimit = ast.literal_eval(inParVal["upper"])
            bounds = [lLimit, uLimit]

        # if needed, extract domain
        domain = None
        if "domain" in inParVal:
            domain = ast.literal_eval(inParVal["domain"])

        # create output ax parameter
        outPar = dict()
        outPar["name"]       = name
        outPar["type"]       = pType
        outPar["value_type"] = vType

        # add bounds/domain as needed
        if bounds is not None:
            outPar["bounds"] = bounds 
        if domain is not None:
            outPar["values"] = domain

        # append parameter to list
        outPars.append(outPar)

    # if any constraints are provided,
    # pass them onto Ax
    outCons = None
    if inCons:
        outCons = inCons

    # return list of parameters
    return (outPars, outCons)

def CreateParamList(config):
    """CreateParamList

    Helper method to create a list of Ax
    parameters from a dictionary of AID2E
    parameter options.

    This is relevant for when interacting with the
    ax.Client API.

    Args:
      config: dictionary to process
    Returns:
      a tuple containing:
        a string-representation of a list of ax parameters
        a list of parameter constraints
    """

    # extract parameters & constraints
    inPars = config["parameters"]
    inCons = config["constraints"]

    # iterate through parameters
    outPars = list()
    for inParKey, inParVal in inPars.items():

        # extract relevant info
        name  = inParKey
        pType = inParVal["param_type"]
        vType = inParVal["value_type"]

        # if needed, extra bounds
        bounds = None
        if pType == "range":
            lLimit = ast.literal_eval(inParVal["lower"])
            uLimit = ast.literal_eval(inParVal["upper"])
            bounds = [lLimit, uLimit]

        # if needed, extract domain
        domain = None
        if "domain" in inParVal:
            domain = ast.literal_eval(inParVal["domain"])

        # if needed, check for ordering
        ordered = True
        if "is_ordered" in inParVal:
            ordered = ast.literal_eval(iParVal["is_ordered"])

        # create output ax parameter
        outPar = None
        if pType == "choice":
            outPar = ChoiceParameterConfig(
                name = name,
                values = domain,
                parameter_type = vType,
                is_ordered = ordered
            )
        elif pType == "range":
            outPar = RangeParameterConfig(
                name = name,
                parameter_type = vType,
                bounds = bounds
            )

        # append parameter to list
        outPars.append(outPar)

    # if any constraints are provided,
    # pass them onto Ax
    outCons = None
    if inCons:
        outCons = inCons

    # return list of parameters
    return (outPars, outCons)

def ConvertObjectConfig(config):
    """ConvertObjectConfig

    Helper method to convert a dictionary of
    AID2E objective options into a dictionary
    of  AxClient-compliant objectives.

    This is relevant for when interacting with
    the ax.service.ax_client.AxClient API.

    Args:
      config: dictionary to convert
    Returns:
      a tuple containing:
        a dictionary of ax-compliant objectives
        a list of constraints
    """

    # extract objectives
    inObjs = config["objectives"]

    # interate through them
    outObjs     = dict()
    constraints = list()
    for inObjKey, inObjVal in inObjs.items():

        # extract name and minimize vs. maximize
        key  = inObjKey
        goal = inObjVal["goal"]

        # if provided, extract threshold
        ref = None
        if "threshold" in inObjVal:
            ref = inObjVal["threshold"]

        # add contraint if provided
        if "constraint" in inObjVal:
            constraints.append(inObjVal["constraint"])

        # turn on/off minimization as appropriate
        if goal == "minimize":
            outObjs[key] = ObjectiveProperties(minimize = True, threshold = ref)
        else:
            outObjs[key] = ObjectiveProperties(minimize = False, threshold = ref)

    # if any constraints were provided,
    # pass them on to Ax
    outCons = None
    if constraints:
        outCons = constraints

    # return dictionary of objectives
    return (outObjs, outCons)

def CreateObjectiveNames(config):
    """CreateObjectiveNames

    Helper method to create a string of objective
    names to be provided to the Ax Client.

    This is relevant for when interacting with the
    ax.Client API.

    Args:
      config: dictionary to process
    Returns:
      a tuple containing:
        a string defining a list of objective names
        a list of constraints
    """

    # extract objectives
    inObjs = config["objectives"]

    # interate through them
    outNames    = ""
    constraints = list()
    for inObjKey, inObjVal in inObjs.items():

        # extract relevant info
        key  = inObjKey
        goal = inObjVal["goal"]

        # add constraint if provided
        if "constraint" in inObjVal:
            constraints.append(inObjVal["constraints"])

        # turn on/off minimization as appropriate
        sKeyAndGoal = ""
        if goal == "minimize":
            sKeyAndGoal = "-" + key
        else:
            sKeyAndGoal = key

        # append name to the string
        if outNames != "":
            outNames += ","
        outNames += sKeyAndGoal

    # if any constraints were provided,
    # pass them on to Ax
    outCons = None
    if constraints:
        outCons = constraints

    # return string of names
    return (outNames, outCons)

# end =========================================================================
