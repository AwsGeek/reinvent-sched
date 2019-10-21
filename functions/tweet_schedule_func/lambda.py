import os
import json
import boto3
import twitter
import dateparser

session = boto3.session.Session()
sm = session.client('secretsmanager')
twitter_secret = json.loads(sm.get_secret_value(SecretId=os.environ['twitter_secret'])['SecretString'])

api = twitter.Api(consumer_key = twitter_secret['consumer_key'],
                  consumer_secret = twitter_secret['consumer_secret'],
                  access_token_key = twitter_secret['access_token_key'],
                  access_token_secret = twitter_secret['access_token_secret'])

def handler(event, context):

    schedule = event['schedule']
    schedule.sort(key=lambda x: x['timestamp'], reverse=False)
    
    # Shortcut of nothing to send
    if not len(schedule):
        return
  
    sessions = event['sessions']
    sessions = {x['key']: x for x in sessions}

    codes = event['codes']
    
    lines = [f"{len(schedule)} of {len(codes)} sessions scheduled:"]
    
    for session in schedule:
        start = dateparser.parse(session['start'])
        lines.append(f"*  {session['codex']} - {start:%a %H:%M} at {session['venue']}")

    valid_codes = list(set([x['code'] for x in event['sessions']]))
    invalid_codes = [x for x in codes if x not in valid_codes]
        
    scheduled_codes = list(set([x['code'] for x in schedule]))
    unscheduled_codes = [x for x in codes if x not in scheduled_codes and x not in invalid_codes]
        
    if unscheduled_codes:
        lines.append(f"Unable to schedule these sessions due to conflicts: {', '.join(unscheduled_codes)}")
        
    if invalid_codes:
        lines.append(f"Unable to find these sessions: {', '.join(invalid_codes)}")

    message = f"@{event['user_name']} "
    for line in lines:
        if len(message) + len(line) + 1 > 160:
            print(f"Sending:")
            print(message)
            
            res = api.PostUpdate(message, in_reply_to_status_id=event['tweet_id'])
            message = f"@{event['user_name']}\n{line}"
        else:
            message += f"\n{line}"

    res = api.PostUpdate(message, in_reply_to_status_id=event['tweet_id'])
    print(f"Sending:")
    print(message)
