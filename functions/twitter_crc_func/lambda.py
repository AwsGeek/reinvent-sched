import os
import json
import hmac
import boto3
import base64
import hashlib
import twitter

session = boto3.session.Session()
sm = session.client('secretsmanager')

twitter_secret = json.loads(sm.get_secret_value(SecretId=os.environ['twitter_secret'])['SecretString'])

consumer_secret = twitter_secret['consumer_secret'].encode('utf-8')

def handler(event, context):
    print (json.dumps(event))
    result = {
        "statusCode": 400
    }
    
    try:
        # an exception will be thrown if the key doesn't exit. easier to ask for forgiveness than permission 
        httpMethod = event["requestContext"]['httpMethod'] 
        if httpMethod == "GET":
            crc_token = event["queryStringParameters"]['crc_token']
            
            # creates HMAC SHA-256 hash from incomming token and our consumer secret
            sha256_hash_digest = hmac.new(consumer_secret, msg=crc_token, digestmod=hashlib.sha256).digest()
        
            # construct response data with base64 encoded hash
            response = {
              'response_token': 'sha256=' + base64.b64encode(sha256_hash_digest)
            }
        
            # returns properly formatted json response
            result = {
                "statusCode": 200,
                "body": json.dumps(response)    
            }

    except KeyError:
        pass

    return result;