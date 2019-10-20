import re

def extract_codes(text):

    # A simple regex to extract session codes (without suffix like -L or -R)
    regex = r"((ACT|ADM|ENT|OIG|AIM|EUC|OPN|ALX|FSI|PNU|ANT|GAM|RET|API|GPS[a-zA-Z]{0,3}|ROB|ARC|HLC|SEC|ARV|IOT|STG|AUT|LFS|STP|BLC|MDS|SVS|CMP|MFG|TLC|CMY|MGT|TRH|CON|MKT|WIN|DAT|MOB|WPS|DOP|NET|WPT)\d{2,4})"
    matches = re.finditer(regex, text, re.IGNORECASE)

    codes = [match.group(1).upper() for match in matches]

    # Remove dups while maintaining order
    seen = set()
    seen_add = seen.add
    
    codes = [x for x in codes if not (x in seen or seen_add(x))]
    print(f"Received {len(codes)} unique codes: {', '.join(codes)}")
    
    return codes
    
    
def handler(event, context):
  
    user_name = event['user']['screen_name']
    tweet_id = event['id_str'] 

    text =  event['text']
    if event['truncated'] == True:
        text = event['extended_tweet']['full_text']

    codes = extract_codes(text)
    
    return { 'user': user_name, 'codes': codes, 'tweet': tweet_id }