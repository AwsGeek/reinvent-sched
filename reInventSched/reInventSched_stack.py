import os
from aws_cdk import (
    core,
    aws_iam,
    aws_lambda,
    aws_events,
    aws_apigateway,
    aws_stepfunctions,
    aws_events_targets,
    aws_secretsmanager,
    aws_stepfunctions_tasks
)

class reInventSchedStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)


        #--
        #  Secrets
        #--------------------#
        
        # Twitter secrets are stored external to this stack
        twitter_secret = aws_secretsmanager.Secret.from_secret_attributes(self, 'twitter_secret', 
            secret_arn = os.environ['TWITTER_SECRET_ARN'])


        #--
        #  Layers
        #--------------------#
        
        # Each of these dependencies is used in 2 or more functions, extracted to layer for ease of use
        twitter_layer = aws_lambda.LayerVersion(self, 'twitter_layer',
            code = aws_lambda.AssetCode('layers/twitter_layer'),
            compatible_runtimes = [aws_lambda.Runtime.PYTHON_2_7, aws_lambda.Runtime.PYTHON_3_6])

        boto_layer = aws_lambda.LayerVersion(self, 'boto_layer',
            code = aws_lambda.AssetCode('layers/boto_layer'),
            compatible_runtimes = [aws_lambda.Runtime.PYTHON_3_6])


        #--
        #  Functions
        #--------------------#

        twitter_crc_func = aws_lambda.Function(self, "twitter_crc_func", 
            code = aws_lambda.AssetCode('functions/twitter_crc_func'),
            handler = "lambda.handler",
            layers = [twitter_layer], 
            runtime = aws_lambda.Runtime.PYTHON_2_7,
            environment = {
                'twitter_secret': twitter_secret.secret_arn})
        twitter_secret.grant_read(twitter_crc_func.role)

        twitter_webhook_func = aws_lambda.Function(self, "twitter_webhook_func", 
            code = aws_lambda.AssetCode('functions/twitter_webhook_func'),
            handler = "lambda.handler",
            layers = [boto_layer, twitter_layer], 
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            environment = {
                'twitter_secret': twitter_secret.secret_arn})
        twitter_secret.grant_read(twitter_webhook_func.role)
        
        # Allow the function to publish tweets to EventBridge
        twitter_webhook_func.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions = ["events:PutEvents"],
                resources = ["*"]))
                
        # Use API Gateway as the webhook endpoint
        twitter_api = aws_apigateway.LambdaRestApi(self, 'twitter_api', 
            handler = twitter_webhook_func,
            proxy = False)
            
        # Tweets are POSTed to the endpoint
        twitter_api.root.add_method('POST')
        
        # Handles twitter CRC validation requests via GET to the webhook
        twitter_api.root.add_method('GET', aws_apigateway.LambdaIntegration(twitter_crc_func))


        parse_tweet_func = aws_lambda.Function(self, "parse_tweet_func", 
            code = aws_lambda.AssetCode('functions/parse_tweet_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6)


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

        parse_tweet_job = aws_stepfunctions.Task(self, 'parse_tweet_job',
            task = aws_stepfunctions_tasks.InvokeFunction(parse_tweet_func))

        get_sessions_job = aws_stepfunctions.Task(self, 'get_sessions_job',
            task = aws_stepfunctions_tasks.InvokeFunction(get_sessions_func),
            input_path = "$.codes",
            result_path = "$.sessions")

        create_schedule_job = aws_stepfunctions.Task(self, 'create_schedule_job', 
            task = aws_stepfunctions_tasks.InvokeFunction(create_schedule_func),
            input_path = "$.sessions",
            result_path = "$.schedule")


        #--
        #  State Machines
        #--------------------#

        schedule_machine = aws_stepfunctions.StateMachine(self, "schedule_machine",
            definition = aws_stepfunctions.Chain
                .start(parse_tweet_job)
                .next(get_sessions_job)
                .next(create_schedule_job))
                
        # A rule to filter reInventSched tweet events
        reinvent_sched_rule = aws_events.Rule(self, "reinvent_sched_rule", 
            event_pattern = {
                "source": ["reInventSched"]})
                
        # Matching events start the image pipline
        reinvent_sched_rule.add_target(
            aws_events_targets.SfnStateMachine(schedule_machine, 
                input = aws_events.RuleTargetInput.from_event_path("$.detail")))
                
