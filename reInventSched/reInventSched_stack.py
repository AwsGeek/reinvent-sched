import os
from aws_cdk import (
    core,
    aws_iam,
    aws_lambda,
    aws_events,
    aws_dynamodb,
    aws_apigateway,
    aws_stepfunctions,
    aws_events_targets,
    aws_secretsmanager,
    aws_stepfunctions_tasks
)

class reInventSchedStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)


        # A cache to temporarily hold session info
        session_cache_table = aws_dynamodb.Table(self, 'session_cache_table',
          partition_key = { 'name': 'code', 'type': aws_dynamodb.AttributeType.STRING },
          billing_mode = aws_dynamodb.BillingMode.PAY_PER_REQUEST,
          time_to_live_attribute = 'expires')


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

        # Handles CRC validation requests from Twitter
        twitter_crc_func = aws_lambda.Function(self, "twitter_crc_func", 
            code = aws_lambda.AssetCode('functions/twitter_crc_func'),
            handler = "lambda.handler",
            layers = [twitter_layer], 
            runtime = aws_lambda.Runtime.PYTHON_2_7,
            environment = {
                'twitter_secret': twitter_secret.secret_arn})
                
        # Grant this function the ability to read Twitter credentials                
        twitter_secret.grant_read(twitter_crc_func.role)

        # Handle schedule requests from Twitter
        twitter_webhook_func = aws_lambda.Function(self, "twitter_webhook_func", 
            code = aws_lambda.AssetCode('functions/twitter_webhook_func'),
            handler = "lambda.handler",
            layers = [boto_layer, twitter_layer], 
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            environment = {
                'twitter_secret': twitter_secret.secret_arn})
                
        # Grant this function permission to read Twitter credentials                
        twitter_secret.grant_read(twitter_webhook_func.role)
        
        # Grant this function permission to publish tweets to EventBridge
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

        # Extract relevant info from the tweet, including session codes
        parse_tweet_func = aws_lambda.Function(self, "parse_tweet_func", 
            code = aws_lambda.AssetCode('functions/parse_tweet_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6)

        # Get session information for requested codes
        get_sessions_func = aws_lambda.Function(self, "get_sessions_func", 
            code = aws_lambda.AssetCode('functions/get_sessions_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            timeout = core.Duration.seconds(60),
            layers = [boto_layer], 
            environment = {
                'CACHE_TABLE': session_cache_table.table_name,
                'LOCAL_CACHE_TTL': str(1 * 60 * 60),  # Cache sessions locally for 1 hour
                'REMOTE_CACHE_TTL': str(12 * 60 * 60)}) # Cache sessions removely for 12 hours
                
        # This functions needs permissions to read and write to the table
        session_cache_table.grant_write_data(get_sessions_func)            
        session_cache_table.grant_read_data(get_sessions_func)            

        # Create a schedule without conflicts
        create_schedule_func = aws_lambda.Function(self, "create_schedule_func", 
            code = aws_lambda.AssetCode('functions/create_schedule_func'),
            handler = "lambda.handler",
            runtime = aws_lambda.Runtime.PYTHON_3_6,
            timeout = core.Duration.seconds(60))

        # Tweet the response to the user
        tweet_schedule_func = aws_lambda.Function(self, "tweet_schedule_func", 
            code = aws_lambda.AssetCode('functions/tweet_schedule_func'),
            handler = "lambda.handler",
            layers = [boto_layer, twitter_layer], 
            runtime = aws_lambda.Runtime.PYTHON_3_6,            
            environment = {
                'twitter_secret': twitter_secret.secret_arn})
        twitter_secret.grant_read(tweet_schedule_func.role)

        #--
        #  States
        #--------------------#

        # Step 4
        tweet_schedule_job = aws_stepfunctions.Task(self, 'tweet_schedule_job', 
            task = aws_stepfunctions_tasks.InvokeFunction(tweet_schedule_func))

        # Step 3
        create_schedule_job = aws_stepfunctions.Task(self, 'create_schedule_job', 
            task = aws_stepfunctions_tasks.InvokeFunction(create_schedule_func),
            input_path = "$.sessions",
            result_path = "$.schedule")
        create_schedule_job.next(tweet_schedule_job)

        # Step 2 - Get associated sessions (scrape or cache)
        get_sessions_job = aws_stepfunctions.Task(self, 'get_sessions_job',
            task = aws_stepfunctions_tasks.InvokeFunction(get_sessions_func),
            input_path = "$.codes",
            result_path = "$.sessions")
        get_sessions_job.next(create_schedule_job)

        # Shortcut if no session codes are supplied
        check_num_codes = aws_stepfunctions.Choice(self, 'check_num_codes')
        check_num_codes.when(aws_stepfunctions.Condition.number_greater_than('$.num_codes', 0), get_sessions_job)
        check_num_codes.otherwise(aws_stepfunctions.Succeed(self, "no_codes"))

        # Step 1 - Parse incoming tweet and prepare for scheduling
        parse_tweet_job = aws_stepfunctions.Task(self, 'parse_tweet_job',
            task = aws_stepfunctions_tasks.InvokeFunction(parse_tweet_func))
        parse_tweet_job.next(check_num_codes)

        #--
        #  State Machines
        #--------------------#

        schedule_machine = aws_stepfunctions.StateMachine(self, "schedule_machine",
            definition = parse_tweet_job)
                
        # A rule to filter reInventSched tweet events
        reinvent_sched_rule = aws_events.Rule(self, "reinvent_sched_rule", 
            event_pattern = {
                "source": ["reInventSched"]})
                
        # Matching events start the image pipline
        reinvent_sched_rule.add_target(
            aws_events_targets.SfnStateMachine(schedule_machine, 
                input = aws_events.RuleTargetInput.from_event_path("$.detail")))
                
