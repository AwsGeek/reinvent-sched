import os
import json
import boto3
import twitter

session = boto3.session.Session()
sns = session.client('sns')
sm = session.client('secretsmanager')
eb = session.client('events')

twitter_secret = json.loads(sm.get_secret_value(SecretId=os.environ['twitter_secret'])['SecretString'])

api = twitter.Api(consumer_key = twitter_secret['consumer_key'],
                  consumer_secret = twitter_secret['consumer_secret'],
                  access_token_key = twitter_secret['access_token_key'],
                  access_token_secret = twitter_secret['access_token_secret'])

res = api.VerifyCredentials()
user_id = str(res.id)

def handler(event, context):
    print (json.dumps(event))
    result = {
        "statusCode": 200
    }
    
    try:
        # an exception will be thrown if the key doesn't exit. easier to ask for forgiveness than permission 
        if event["requestContext"]['httpMethod'] == "POST":
            
            # Queue up each tweet for processing
            body = json.loads(event["body"])
            for_user_id = body['for_user_id']
            
            if for_user_id == user_id: # @reInventSChed
                for tweet in body['tweet_create_events']:
                    
                    # Ignore retweets        
                    if 'retweeted_status' in tweet:
                        print(f"Ignoring retweet {tweet['id']}")
                        continue
            
                    # Don't respond to ourself
                    if tweet['user']['id_str'] == user_id: # @reInventSched 
                        print(f"Ignoring our own tweet {tweet['id']}")
                        continue
                    
                    response = eb.put_events(
                        Entries=[{
                            'Source': 'reInventSched',
                            'DetailType': 'tweet',
                            'Detail': json.dumps(tweet)
                        }])               
                    print(response)

            # returns properly formatted json response
            result['statusCode'] : 200
            
    except KeyError:
        pass 

    return result