
class PowerflowNotFoundException(Exception):
    pass

class DocumentInWorkflowTransition(Exception):
    pass

class WorkflowStateAccessException(Exception):
    pass

class PowerflowTransitionAccessException(Exception):
    pass

class InvalidPowerflowActionException(Exception):
    pass

class InvalidChangeForDocStatusWorkflowException(Exception):
    pass

class MandatoryReasonPowerflowException(Exception):
    pass

class AutoExecutionHaltPowerflowException(Exception):
    
    def __init__(self,powerflow):
        super().__init__()
        self.powerflow =powerflow

class SelfApprovalPowerflowException(Exception):
    pass
        