import os
import re
import bs4
import datetime
import requests
import dateparser

headers = {'User-Agent': 'Mozila/5.0 (Macintosh; Intel Mac OS X 10_1_5) ApleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.261.102 Safari/537.36', 'Content-Type': 'text/plain'} 
rs = requests.Session() 

local_cache = {}

def get_ids_for_code(code):

    response = rs.get(f"https://www.portal.reinvent.awsevents.com/connect/processSearchFilters.do?searchPhrase={code}", headers=headers)
        
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    results = soup.findAll("div", { "class" : "resultRow sessionRow" })

    ids = [x['id'].split('_',1)[1] for x in results]
    print(f"Retrieved {len(ids)} IDs for session {code}: {', '.join(ids)}")
    
    return ids

ttl = int(os.environ['LOCAL_CACHE_TTL'])
def get_cached_sesssions(code):

    now = int(datetime.datetime.now().timestamp())

    sessions = []
    if code in local_cache and local_cache[code]['expires'] >= now:
        sessions = local_cache[code]['sessions']
        print(f"Using {code} from local cache")

    return sessions
    
def set_cached_sessions(code, sessions):
    now = int(datetime.datetime.now().timestamp())

    if sessions:
        local_cache[code] = {'sessions': sessions, 'expires': now + ttl }

    print(f"Added {code} to local cache")


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

        set_cached_sessions(code, sessions)

    return sessions

def handler(codes, context):
  
    schedule = []  

    priority = len(codes)
    for code in codes:
        
        code = code.strip()
        
        sessions = get_sessions_for_code(code)
        for session in sessions:
            session['priority'] = priority
            
        priority = priority - 1
        schedule = schedule + sessions   
    
    print(f"Retrieved {len(schedule)} sessions including repeats")    
    
    return schedule