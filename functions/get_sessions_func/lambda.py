import os
import re
import bs4
import json
import boto3
import datetime
import requests
import dateparser

from botocore.exceptions import ClientError

headers = {'User-Agent': 'Mozila/5.0 (Macintosh; Intel Mac OS X 10_1_5) ApleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.261.102 Safari/537.36', 'Content-Type': 'text/plain'} 
rs = requests.Session() 

def get_ids_for_code(code):

    response = rs.get(f"https://www.portal.reinvent.awsevents.com/connect/processSearchFilters.do?searchPhrase={code}", headers=headers)
        
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    results = soup.findAll("div", { "class" : "resultRow sessionRow" })

    ids = [x['id'].split('_',1)[1] for x in results]
    print(f"Retrieved {len(ids)} IDs for session {code}: {', '.join(ids)}")
    
    return ids


local_cache = {}
def get_cached_sesssions(code):

    now = int(datetime.datetime.now().timestamp())

    sessions = []
    if code in local_cache and local_cache[code]['expires'] >= now:
        sessions = local_cache[code]['sessions']
        print(f"Using {code} from local cache")
    else:
        sessions = get_remote_cached_sessions(code)

    return sessions
    
local_ttl = int(os.environ['LOCAL_CACHE_TTL'])
def put_cached_sessions(code, sessions):
    now = int(datetime.datetime.now().timestamp())

    if sessions:
        local_cache[code] = {'sessions': sessions, 'expires': now + local_ttl }
        put_remote_cached_sessions(code, sessions)

    print(f"Added {code} to local cache")

ddb_client = boto3.client('dynamodb')
ddb_resource = boto3.resource('dynamodb')
cache_table = ddb_resource.Table(os.environ['CACHE_TABLE'])

def get_remote_cached_sessions(code):

    now = int(datetime.datetime.now().timestamp())

    sessions = []
    try:
        response = cache_table.get_item(Key={ 'code': code })
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print(response)
        if 'Item' in response:
            item = response['Item']
            sessions = json.loads(item['sessions'])
    
    return sessions

remote_ttl = int(os.environ['REMOTE_CACHE_TTL'])
def put_remote_cached_sessions(code, sessions):
    now = int(datetime.datetime.now().timestamp())

    if sessions:
        try:
            cache_table.put_item(Item={'code': code,
                                 'sessions': json.dumps(sessions),
                                 'expires': now + remote_ttl})
        except ClientError as e:
            print(e.response['Error']['Message'])
        
    print(f"Added {code} to remote cache")

def get_sessions_for_code(code):

    sessions = get_cached_sesssions(code)
    if not sessions:

        for id in get_ids_for_code(code):

            url = 'https://www.portal.reinvent.awsevents.com/connect/dwr/call/plaincall/ConnectAjax.getSchedulingJSON.dwr'
            data = {
                "callCount": 1, 
                "windowName": "",
                "c0-scriptName": "ConnectAjax",
                "c0-methodName": "getSchedulingJSON",
                "c0-id": 0,
                "c0-param0": f"{id}",
                "c0-param1": "boolean:false",
                "batchId": 6,
                "instanceId": 0,
                "page": "%2Fconnect%2Fsearch.ww",
                "scriptSessionId": "aa$GdZcE0UHnrOn2rs*Baug1rnm/JuuLapm-fcKKw5gVn"
            }
            response = rs.post(url, headers=headers, data=data, verify=True)
    
            # There are so many things wrong with this, don't even start
            regex = r"\\\"startTime\\\":\\\"([a-zA-Z0-9:, ]+)\\\",\\\"endTime\\\":\\\"([a-zA-Z0-9 ,:]+)\\\",\\\"room\\\":\\\"([a-zA-Z0-9| ]+),"
            matches = re.search(regex, response.text, re.MULTILINE)
            
            if matches: # no matches if there's no schedule yet
                start = matches.group(1)
                end = matches.group(2)
                venue = matches.group(3)
                
                start = dateparser.parse(start)
                end = dateparser.parse(end)
                end = end.replace(year = start.year, month=start.month, day=start.day)
                timestamp = start.timestamp()
                duration = (end - start).seconds
        
                response = rs.get(f"https://www.portal.reinvent.awsevents.com/connect/sessionDetail.ww?SESSION_ID={id}", headers=headers)
                soup = bs4.BeautifulSoup(response.content, "html.parser")
                detail = soup.find("div", { "class" : "detailHeader" }).get_text(strip=True)
                codex = detail.split(' ',2)[0]
        
                sessions.append({"key": f"{code}-{int(timestamp)}", "code": code, "codex": codex, "venue": venue, "start": str(start), "day": start.day, "timestamp": int(timestamp), "duration": duration})

        put_cached_sessions(code, sessions)

    return sessions

def handler(code, context):
  
    return get_sessions_for_code(code)