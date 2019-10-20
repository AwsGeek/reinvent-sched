from aws_cdk import (
    core,
    aws_lambda,
    aws_stepfunctions,
    aws_stepfunctions_tasks
)

class reInventSchedStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)


        #--
        #  Layers
        #--------------------#
        
        twitter_layer = aws_lambda.LayerVersion(self, 'twitter_layer',
            code = aws_lambda.AssetCode('layers/twitter_layer'),
            compatible_runtimes = [aws_lambda.Runtime.PYTHON_2_7, aws_lambda.Runtime.PYTHON_3_6])

        boto_layer = aws_lambda.LayerVersion(self, 'boto_layer',
            code = aws_lambda.AssetCode('layers/boto_layer'),
            compatible_runtimes = [aws_lambda.Runtime.PYTHON_3_6])


        #--
        #  Functions
        #--------------------#

        get_sessions_func = aws_lambda.Function(self, "get_sessions_func", 
            code = aws_lambda.AssetCode('functions/get_sessions_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            timeout = core.Duration.seconds(60))

        create_schedule_func = aws_lambda.Function(self, "create_schedule_func", 
            code = aws_lambda.AssetCode('functions/create_schedule_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            timeout = core.Duration.seconds(60))


        #--
        #  States
        #--------------------#

        get_sessions_job = aws_stepfunctions.Task(self, 'get_sessions_job',
            task = aws_stepfunctions_tasks.InvokeFunction(get_sessions_func))

        create_schedule_job = aws_stepfunctions.Task(self, 'create_schedule_job', 
            task = aws_stepfunctions_tasks.InvokeFunction(create_schedule_func))


        #--
        #  State Machines
        #--------------------#

        schedule_machine = aws_stepfunctions.StateMachine(self, "schedule_machine",
            definition = aws_stepfunctions.Chain
                .start(get_sessions_job)
                .next(create_schedule_job))
